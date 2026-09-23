import random
from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from core.models import Competition, Team, Phase, Match
from core.utils import get_competition_format

KNOCKOUT_ORDER = {
    "playoff": 2,
    "round_16": 3,
    "quarter": 4,
    "semi": 5,
    "final": 6,
}
KNOCKOUT_PHASES = ["playoff", "round_16", "quarter", "semi", "final"]

# ⚙️ Configuration du calendrier des phases finales
# Chaque phase tient sur UNE SEULE JOURNÉE (aller + retour même jour)
# Fenêtre de jeu côté JS : 12h00 J → 12h59 J+1 (25h)
# 1 jour entre chaque phase → transition fluide (fenêtre ferme à 12h59, phase suivante ouvre à 12h00 le lendemain)
PHASE_DAY_OFFSETS = {
    "playoff": 0,       # J+0
    "round_16": 1,      # J+1
    "quarter": 2,       # J+2
    "semi": 3,          # J+3
    "final": 4,         # J+4
}
MATCH_HOUR = 12  # Heure de référence (12h00) — le JS calcule la fenêtre


def _phase_dt(base_dt, phase_name):
    """
    Retourne la datetime de la phase : jour J+offset à 12h00 (aware).
    Tous les matchs d'une même phase partagent cette datetime.
    """
    offset = PHASE_DAY_OFFSETS.get(phase_name, 0)
    target_date = base_dt.date() + timedelta(days=offset)
    naive = datetime.combine(target_date, time(MATCH_HOUR, 0, 0))
    return timezone.make_aware(naive)


def get_or_create_phase(competition, name):
    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name=name,
        defaults={"order": KNOCKOUT_ORDER.get(name, 99), "is_active": False},
    )
    desired = KNOCKOUT_ORDER.get(name)
    if desired and phase.order != desired:
        phase.order = desired
        phase.save(update_fields=["order"])
    return phase


def get_tbd_team():
    tbd = Team.objects.filter(abbreviation="TBD").first()
    if not tbd:
        raise CommandError(
            "Team TBD introuvable. Lance: python manage.py ensure_tbd_team"
        )
    return tbd


class Command(BaseCommand):
    help = "Génère le bracket adaptatif (12 à 36 équipes)."

    def add_arguments(self, parser):
        parser.add_argument("--competition-id", type=int, default=None)
        parser.add_argument("--start-date", type=str, default=None)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        competition = (
            Competition.objects.filter(pk=options["competition_id"]).first()
            if options["competition_id"]
            else Competition.objects.filter(is_active=True).first()
        )
        if not competition:
            raise CommandError("Aucune compétition trouvée.")

        existing = Match.objects.filter(
            phase__competition=competition,
            phase__name__in=KNOCKOUT_PHASES,
        ).exists()
        if existing and not options["reset"]:
            raise CommandError(
                "Un bracket existe déjà. Utilise --reset pour le regénérer."
            )

        if options["start_date"]:
            try:
                d = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
                base_dt = timezone.make_aware(
                    datetime.combine(d, time(MATCH_HOUR, 0, 0))
                )
            except ValueError:
                raise CommandError("Format invalide. Utilise YYYY-MM-DD.")
        else:
            today = timezone.localtime(timezone.now()).date()
            base_dt = timezone.make_aware(
                datetime.combine(today, time(MATCH_HOUR, 0, 0))
            )

        teams_qs = Team.objects.filter(
            payment_validated=True,
            competition=competition,
        ).exclude(
            abbreviation="TBD"
        ).annotate(
            diff=F("goals_for") - F("goals_against")
        ).order_by("-points", "-diff", "-goals_for", "team_name")

        n_teams = teams_qs.count()
        if n_teams < 12:
            raise CommandError(f"Il faut au moins 12 équipes. Actuel: {n_teams}")

        fmt = get_competition_format(n_teams)
        self.stdout.write(self.style.WARNING(f"Format: {fmt['label']}"))

        teams = list(teams_qs)
        direct = fmt['direct_qualified']
        p_ties = fmt['playoff_ties']
        p_participants = fmt['playoff_participants']
        bracket = fmt['bracket']

        direct_teams = teams[:direct]
        seeded = teams[direct:direct + p_ties]
        unseeded = teams[direct + p_ties:direct + p_participants]

        self.stdout.write(
            f"  Direct: {len(direct_teams)} | "
            f"Seeded: {len(seeded)} | "
            f"Unseeded: {len(unseeded)} | "
            f"Éliminés: {fmt['eliminated_after_league']}"
        )

        phases = {
            name: get_or_create_phase(competition, name)
            for name in fmt['phases']
        }

        if options["reset"]:
            Match.objects.filter(
                phase__competition=competition,
                phase__name__in=KNOCKOUT_PHASES,
            ).delete()
            self.stdout.write(self.style.WARNING("Ancien bracket supprimé."))

        tbd = get_tbd_team()

        with transaction.atomic():
            # -------- BARRAGES --------
            playoff_deciders = []
            if p_ties > 0:
                pairings = list(zip(seeded, list(reversed(unseeded))))
                phase_dt = _phase_dt(base_dt, "playoff")

                for seed, unseed in pairings:
                    leg1 = Match.objects.create(
                        phase=phases["playoff"],
                        home_team=unseed,
                        away_team=seed,
                        match_leg="aller",
                        scheduled_date=phase_dt,
                        matchday=0,
                        is_played=False,
                    )
                    leg2 = Match.objects.create(
                        phase=phases["playoff"],
                        home_team=seed,
                        away_team=unseed,
                        match_leg="retour",
                        first_leg=leg1,
                        scheduled_date=phase_dt,  # ← même jour
                        matchday=0,
                        is_played=False,
                    )
                    playoff_deciders.append(leg2)

            # -------- BRACKET --------
            if bracket == 'round_16':
                q_deciders = self._build_r16(
                    phases, direct_teams, playoff_deciders, tbd, base_dt
                )
            else:
                q_deciders = self._build_qf(
                    phases, direct_teams, playoff_deciders, tbd, base_dt
                )

            # -------- DEMI --------
            semi_dt = _phase_dt(base_dt, "semi")
            s_deciders = []
            for s in range(2):
                a = q_deciders[s * 2]
                b = q_deciders[s * 2 + 1]

                leg1 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="aller",
                    scheduled_date=semi_dt,
                    matchday=0, is_played=False,
                    source_home_match=b,
                    source_away_match=a,
                )
                leg2 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="retour",
                    first_leg=leg1,
                    scheduled_date=semi_dt,
                    matchday=0, is_played=False,
                    source_home_match=a,
                    source_away_match=b,
                )
                s_deciders.append(leg2)

            # -------- FINALE --------
            final_dt = _phase_dt(base_dt, "final")
            Match.objects.create(
                phase=phases["final"],
                home_team=tbd, away_team=tbd,
                match_leg="unique",
                scheduled_date=final_dt,
                matchday=0, is_played=False,
                source_home_match=s_deciders[0],
                source_away_match=s_deciders[1],
            )

        self.stdout.write(self.style.SUCCESS(
            f"OK: Bracket généré — {fmt['label']}"
        ))
        self.stdout.write(self.style.WARNING(
            "Ensuite: python manage.py sync_knockout_bracket"
        ))

    def _make_pair(self, phase, team_a, team_b, source_a, source_b,
                   scheduled_dt, tbd):
        """Crée un aller/retour, même journée, team_a reçoit au retour."""
        # ALLER
        if team_b is None:
            aller_home, aller_home_src = tbd, source_b
        else:
            aller_home, aller_home_src = team_b, None

        if team_a is None:
            aller_away, aller_away_src = tbd, source_a
        else:
            aller_away, aller_away_src = team_a, None

        leg1 = Match.objects.create(
            phase=phase,
            home_team=aller_home, away_team=aller_away,
            match_leg="aller",
            scheduled_date=scheduled_dt,
            matchday=0, is_played=False,
            source_home_match=aller_home_src,
            source_away_match=aller_away_src,
        )

        # RETOUR
        if team_a is None:
            retour_home, retour_home_src = tbd, source_a
        else:
            retour_home, retour_home_src = team_a, None

        if team_b is None:
            retour_away, retour_away_src = tbd, source_b
        else:
            retour_away, retour_away_src = team_b, None

        leg2 = Match.objects.create(
            phase=phase,
            home_team=retour_home, away_team=retour_away,
            match_leg="retour",
            first_leg=leg1,
            scheduled_date=scheduled_dt,  # ← même datetime que l'aller
            matchday=0, is_played=False,
            source_home_match=retour_home_src,
            source_away_match=retour_away_src,
        )
        return leg1, leg2

    def _pair_slots(self, direct_teams, playoff_deciders, n_slots):
        direct = list(direct_teams)
        playoffs = list(playoff_deciders)
        random.shuffle(playoffs)

        slots = []

        n_dvp = min(len(direct), len(playoffs), n_slots)
        for i in range(n_dvp):
            slots.append((direct[i], None, None, playoffs[i]))

        remaining_direct = direct[n_dvp:]
        while len(slots) < n_slots and len(remaining_direct) >= 2:
            a = remaining_direct.pop(0)
            b = remaining_direct.pop(-1)
            slots.append((a, b, None, None))

        remaining_playoffs = playoffs[n_dvp:]
        while len(slots) < n_slots and len(remaining_playoffs) >= 2:
            a = remaining_playoffs.pop(0)
            b = remaining_playoffs.pop(0)
            slots.append((None, None, a, b))

        if len(slots) != n_slots:
            raise CommandError(
                f"Impossible de générer {n_slots} matchs. "
                f"Direct={len(direct)}, Playoffs={len(playoffs)}"
            )
        return slots

    def _build_r16(self, phases, direct_teams, playoff_deciders, tbd, base_dt):
        n_slots = 8
        slots = self._pair_slots(direct_teams, playoff_deciders, n_slots)
        phase_dt = _phase_dt(base_dt, "round_16")

        r16_deciders = []
        for (a, b, src_a, src_b) in slots:
            _, leg2 = self._make_pair(
                phases["round_16"], a, b, src_a, src_b, phase_dt, tbd
            )
            r16_deciders.append(leg2)

        return self._build_qf_from_r16(phases, r16_deciders, tbd, base_dt)

    def _build_qf_from_r16(self, phases, r16_deciders, tbd, base_dt):
        phase_dt = _phase_dt(base_dt, "quarter")
        q_deciders = []
        for q in range(4):
            a = r16_deciders[q * 2]
            b = r16_deciders[q * 2 + 1]
            _, leg2 = self._make_pair(
                phases["quarter"], None, None, a, b, phase_dt, tbd
            )
            q_deciders.append(leg2)
        return q_deciders

    def _build_qf(self, phases, direct_teams, playoff_deciders, tbd, base_dt):
        n_slots = 4
        slots = self._pair_slots(direct_teams, playoff_deciders, n_slots)
        phase_dt = _phase_dt(base_dt, "quarter")

        q_deciders = []
        for (a, b, src_a, src_b) in slots:
            _, leg2 = self._make_pair(
                phases["quarter"], a, b, src_a, src_b, phase_dt, tbd
            )
            q_deciders.append(leg2)
        return q_deciders