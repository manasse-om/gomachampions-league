import random
from datetime import datetime, timedelta
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


def get_or_create_phase(competition, name):
    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name=name,
        defaults={
            "order": KNOCKOUT_ORDER.get(name, 99),
            "is_active": False
        },
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


def create_two_legs(phase, home_1, away_1, home_2, away_2,
                    dt1, dt2, src_home=None, src_away=None):
    """Crée un match aller et un match retour."""
    leg1 = Match.objects.create(
        phase=phase,
        home_team=home_1,
        away_team=away_1,
        match_leg="aller",
        scheduled_date=dt1,
        matchday=0,
        is_played=False,
        source_home_match=src_home,
        source_away_match=src_away,
    )
    leg2 = Match.objects.create(
        phase=phase,
        home_team=home_2,
        away_team=away_2,
        match_leg="retour",
        first_leg=leg1,
        scheduled_date=dt2,
        matchday=0,
        is_played=False,
        source_home_match=src_away,
        source_away_match=src_home,
    )
    return leg1, leg2


class Command(BaseCommand):
    help = "Génère le bracket adaptatif (12 à 36 équipes)."

    def add_arguments(self, parser):
        parser.add_argument("--competition-id", type=int, default=None)
        parser.add_argument("--start-date", type=str, default=None)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        # --- Compétition ---
        competition = (
            Competition.objects.filter(pk=options["competition_id"]).first()
            if options["competition_id"]
            else Competition.objects.filter(is_active=True).first()
        )
        if not competition:
            raise CommandError("Aucune compétition trouvée.")

        # --- Date de base ---
        if options["start_date"]:
            try:
                d = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
                base_dt = timezone.make_aware(
                    datetime.combine(d, datetime.min.time())
                )
            except ValueError:
                raise CommandError("Format invalide. Utilise YYYY-MM-DD.")
        else:
            base_dt = timezone.localtime(timezone.now()).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # --- Classement ligue ---
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
            raise CommandError(
                f"Il faut au moins 12 équipes. Actuel: {n_teams}"
            )

        fmt = get_competition_format(n_teams)
        self.stdout.write(self.style.WARNING(f"Format: {fmt['label']}"))

        teams = list(teams_qs)
        direct = fmt['direct_qualified']
        p_ties = fmt['playoff_ties']
        p_participants = fmt['playoff_participants']
        bracket = fmt['bracket']

        # Distribution selon le classement
        direct_teams = teams[:direct]                        # Top → qualifiés directs
        seeded = teams[direct:direct + p_ties]               # Seeded barrages (pos d+1 à d+p_ties)
        unseeded = teams[direct + p_ties:direct + p_participants]  # Unseeded barrages

        self.stdout.write(
            f"  Direct: {len(direct_teams)} | "
            f"Seeded: {len(seeded)} | "
            f"Unseeded: {len(unseeded)} | "
            f"Éliminés: {fmt['eliminated_after_league']}"
        )

        # --- Créer les phases nécessaires ---
        phases = {
            name: get_or_create_phase(competition, name)
            for name in fmt['phases']
        }

        # --- Reset si demandé ---
        if options["reset"]:
            Match.objects.filter(
                phase__competition=competition,
                phase__name__in=KNOCKOUT_PHASES
            ).delete()
            self.stdout.write(self.style.WARNING("Ancien bracket supprimé."))

        tbd = get_tbd_team()

        with transaction.atomic():
            # -----------------------------------------------
            # BARRAGES
            # Seeded (mieux classé) reçoit le retour
            # Unseeded reçoit l'aller
            # Appariement : meilleur seeded vs pire unseeded
            # -----------------------------------------------
            playoff_deciders = []

            if p_ties > 0:
                pairings = list(zip(seeded, list(reversed(unseeded))))

                for idx, (seed, unseed) in enumerate(pairings, start=1):
                    dt1 = base_dt + timedelta(minutes=idx * 2)
                    dt2 = base_dt + timedelta(days=1, minutes=idx * 2)

                    leg1 = Match.objects.create(
                        phase=phases["playoff"],
                        home_team=unseed,   # Unseeded reçoit l'aller
                        away_team=seed,
                        match_leg="aller",
                        scheduled_date=dt1,
                        matchday=0,
                        is_played=False,
                    )
                    leg2 = Match.objects.create(
                        phase=phases["playoff"],
                        home_team=seed,     # Seeded reçoit le retour ✅
                        away_team=unseed,
                        match_leg="retour",
                        first_leg=leg1,
                        scheduled_date=dt2,
                        matchday=0,
                        is_played=False,
                    )
                    playoff_deciders.append(leg2)

            # -----------------------------------------------
            # BRACKET SELON FORMAT
            # -----------------------------------------------
            if bracket == 'round_16':
                q_deciders = self._build_r16(
                    phases, direct_teams, playoff_deciders,
                    tbd, base_dt, p_ties
                )
                day_sf = 9
            else:
                q_deciders = self._build_qf_direct(
                    phases, direct_teams, playoff_deciders,
                    tbd, base_dt
                )
                day_sf = 6

            # -----------------------------------------------
            # DEMI-FINALES (aller-retour)
            # -----------------------------------------------
            s_deciders = []
            for s in range(2):
                a = q_deciders[s * 2]
                b = q_deciders[s * 2 + 1]
                dt1 = base_dt + timedelta(
                    days=day_sf, minutes=(s + 1) * 2
                )
                dt2 = base_dt + timedelta(
                    days=day_sf + 1, minutes=(s + 1) * 2
                )

                leg1 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="aller",
                    scheduled_date=dt1,
                    matchday=0, is_played=False,
                    source_home_match=b,
                    source_away_match=a,
                )
                leg2 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="retour",
                    first_leg=leg1,
                    scheduled_date=dt2,
                    matchday=0, is_played=False,
                    source_home_match=a,
                    source_away_match=b,
                )
                s_deciders.append(leg2)

            # -----------------------------------------------
            # FINALE (match unique)
            # -----------------------------------------------
            dt_final = base_dt + timedelta(days=day_sf + 4, minutes=2)
            Match.objects.create(
                phase=phases["final"],
                home_team=tbd, away_team=tbd,
                match_leg="unique",
                scheduled_date=dt_final,
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

    def _build_r16(self, phases, direct_teams, playoff_deciders,
                   tbd, base_dt, p_ties):
        """
        8es de finale : direct_teams vs vainqueurs barrages.
        Tirage aléatoire. Direct reçoit le retour (avantage domicile).
        """
        # Mélanger pour le tirage
        shuffled_direct = list(direct_teams)
        shuffled_playoffs = list(playoff_deciders)
        random.shuffle(shuffled_direct)
        random.shuffle(shuffled_playoffs)

        r16_deciders = []
        n = len(shuffled_direct)  # = 8 normalement

        for i in range(n):
            top = shuffled_direct[i]
            src = shuffled_playoffs[i] if i < len(shuffled_playoffs) else None

            dt1 = base_dt + timedelta(days=3, minutes=(i + 1) * 2)
            dt2 = base_dt + timedelta(days=4, minutes=(i + 1) * 2)

            # Aller : vainqueur barrage reçoit (TBD ou connu)
            home_aller = tbd if src else top
            away_aller = top if src else tbd

            leg1 = Match.objects.create(
                phase=phases["round_16"],
                home_team=home_aller,
                away_team=away_aller,
                match_leg="aller",
                scheduled_date=dt1,
                matchday=0, is_played=False,
                source_home_match=src,
            )
            # Retour : direct reçoit ✅
            leg2 = Match.objects.create(
                phase=phases["round_16"],
                home_team=top,
                away_team=tbd,
                match_leg="retour",
                first_leg=leg1,
                scheduled_date=dt2,
                matchday=0, is_played=False,
                source_away_match=src,
            )
            r16_deciders.append(leg2)

        # QUARTS depuis R16 deciders
        return self._build_qf_from_r16(
            phases, r16_deciders, tbd, base_dt
        )

    def _build_qf_from_r16(self, phases, r16_deciders, tbd, base_dt):
        """Quarts de finale depuis les 8 décideurs R16."""
        q_deciders = []
        for q in range(4):
            a = r16_deciders[q * 2]
            b = r16_deciders[q * 2 + 1]
            dt1 = base_dt + timedelta(days=6, minutes=(q + 1) * 2)
            dt2 = base_dt + timedelta(days=7, minutes=(q + 1) * 2)

            leg1 = Match.objects.create(
                phase=phases["quarter"],
                home_team=tbd, away_team=tbd,
                match_leg="aller",
                scheduled_date=dt1,
                matchday=0, is_played=False,
                source_home_match=b,
                source_away_match=a,
            )
            leg2 = Match.objects.create(
                phase=phases["quarter"],
                home_team=tbd, away_team=tbd,
                match_leg="retour",
                first_leg=leg1,
                scheduled_date=dt2,
                matchday=0, is_played=False,
                source_home_match=a,
                source_away_match=b,
            )
            q_deciders.append(leg2)

        return q_deciders

    def _build_qf_direct(self, phases, direct_teams,
                          playoff_deciders, tbd, base_dt):
        """
        Format QF : direct_teams vs vainqueurs barrages → QF.
        """
        shuffled_direct = list(direct_teams)
        shuffled_playoffs = list(playoff_deciders)
        random.shuffle(shuffled_direct)
        random.shuffle(shuffled_playoffs)

        q_deciders = []
        n = len(shuffled_direct)

        for i in range(n):
            top = shuffled_direct[i]
            src = shuffled_playoffs[i] if i < len(shuffled_playoffs) else None

            dt1 = base_dt + timedelta(days=3, minutes=(i + 1) * 2)
            dt2 = base_dt + timedelta(days=4, minutes=(i + 1) * 2)

            leg1 = Match.objects.create(
                phase=phases["quarter"],
                home_team=tbd if src else top,
                away_team=top if src else tbd,
                match_leg="aller",
                scheduled_date=dt1,
                matchday=0, is_played=False,
                source_home_match=src,
            )
            leg2 = Match.objects.create(
                phase=phases["quarter"],
                home_team=top,
                away_team=tbd,
                match_leg="retour",
                first_leg=leg1,
                scheduled_date=dt2,
                matchday=0, is_played=False,
                source_away_match=src,
            )
            q_deciders.append(leg2)

        return q_deciders