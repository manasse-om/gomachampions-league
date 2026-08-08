import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import Competition, Team, Phase, Match


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
        defaults={"order": KNOCKOUT_ORDER.get(name, 99), "is_active": False},
    )
    # sécuriser l'ordre si déjà existant
    desired = KNOCKOUT_ORDER.get(name)
    if desired is not None and phase.order != desired:
        phase.order = desired
        phase.save(update_fields=["order"])
    return phase


def get_tbd_team():
    tbd = Team.objects.filter(abbreviation="TBD").first()
    if not tbd:
        raise CommandError("Team 'TBD' introuvable. Lance d'abord: python manage.py ensure_tbd_team")
    return tbd


def create_two_legs(phase, home_1, away_1, home_2, away_2, dt1, dt2):
    first = Match.objects.create(
        phase=phase,
        home_team=home_1,
        away_team=away_1,
        match_leg="aller",
        scheduled_date=dt1,
        matchday=0,
        is_played=False,
    )
    second = Match.objects.create(
        phase=phase,
        home_team=home_2,
        away_team=away_2,
        match_leg="retour",
        first_leg=first,
        scheduled_date=dt2,
        matchday=0,
        is_played=False,
    )
    return first, second


class Command(BaseCommand):
    help = "Génère le bracket UCL complet (barrages -> finale) à partir du classement league."

    def add_arguments(self, parser):
        parser.add_argument("--competition-id", type=int, default=None)
        parser.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD (optionnel)")
        parser.add_argument("--reset", action="store_true", help="Supprime l'ancien bracket (phases finales) avant génération")

    def handle(self, *args, **options):
        comp_id = options["competition_id"]

        if comp_id:
            competition = Competition.objects.filter(pk=comp_id).first()
        else:
            competition = Competition.objects.filter(is_active=True).first()

        if not competition:
            raise CommandError("Aucune compétition trouvée (active ou competition-id invalide).")

        # base datetime
        if options["start_date"]:
            try:
                d = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
                base_dt = timezone.make_aware(datetime.combine(d, datetime.min.time()))
            except ValueError:
                raise CommandError("Format start-date invalide. Utilise YYYY-MM-DD.")
        else:
            base_dt = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)

        # classement ligue (Top 24 utilisés)
        teams = Team.objects.filter(
            payment_validated=True,
            competition=competition
        ).annotate(
            diff=F("goals_for") - F("goals_against")
        ).order_by("-points", "-diff", "-goals_for", "team_name")

        if teams.count() < 24:
            raise CommandError(f"Il faut au moins 24 équipes validées. Actuel: {teams.count()}")

        top8 = list(teams[:8])                 # 1-8
        seeded_9_16 = list(teams[8:16])        # 9-16
        unseeded_17_24 = list(teams[16:24])    # 17-24

        phases = {name: get_or_create_phase(competition, name) for name in KNOCKOUT_PHASES}

        if options["reset"]:
            Match.objects.filter(
                phase__competition=competition,
                phase__name__in=KNOCKOUT_PHASES
            ).delete()

        tbd = get_tbd_team()

        with transaction.atomic():
            # -------------------------------------------------------
            # 1) BARRAGES déterministes:
            # 9v24, 10v23, ..., 16v17
            # Aller chez 17-24, Retour chez 9-16
            # -------------------------------------------------------
            playoff_deciders = []  # on garde les "retour" = match décisif

            pairings = list(zip(seeded_9_16, reversed(unseeded_17_24)))
            for idx, (seed, unseed) in enumerate(pairings, start=1):
                dt1 = base_dt + timedelta(minutes=idx * 2)                 # aller
                dt2 = base_dt + timedelta(days=1, minutes=idx * 2)         # retour
                _leg1, leg2 = create_two_legs(
                    phases["playoff"],
                    home_1=unseed, away_1=seed,     # aller: unseed reçoit
                    home_2=seed, away_2=unseed,     # retour: seed reçoit
                    dt1=dt1, dt2=dt2
                )
                playoff_deciders.append(leg2)

            # -------------------------------------------------------
            # 2) 8es: tirage aléatoire intégral
            # Top8 vs Vainqueurs barrages
            # Retour à domicile pour le Top8
            # -------------------------------------------------------
            random.shuffle(top8)
            random.shuffle(playoff_deciders)

            r16_deciders = []  # match retour des 8es

            for i, top in enumerate(top8, start=1):
                src = playoff_deciders[i - 1]  # vainqueur barrage i

                dt1 = base_dt + timedelta(days=3, minutes=i * 2)
                dt2 = base_dt + timedelta(days=4, minutes=i * 2)

                # Aller: chez le vainqueur du barrage (inconnu => TBD)
                leg1 = Match.objects.create(
                    phase=phases["round_16"],
                    home_team=tbd,
                    away_team=top,
                    match_leg="aller",
                    scheduled_date=dt1,
                    matchday=0,
                    is_played=False,
                    source_home_match=src,  # ✅ home = vainqueur du barrage
                )
                # Retour: chez le Top8
                leg2 = Match.objects.create(
                    phase=phases["round_16"],
                    home_team=top,
                    away_team=tbd,
                    match_leg="retour",
                    first_leg=leg1,
                    scheduled_date=dt2,
                    matchday=0,
                    is_played=False,
                    source_away_match=src,  # ✅ away = vainqueur du barrage
                )
                r16_deciders.append(leg2)

            # -------------------------------------------------------
            # 3) Quarts: bracket fixe
            # (R16-1 vs R16-2), (3 vs 4), (5 vs 6), (7 vs 8)
            # -------------------------------------------------------
            q_deciders = []
            for q_idx in range(4):
                a = r16_deciders[q_idx * 2]       # source A
                b = r16_deciders[q_idx * 2 + 1]   # source B

                dt1 = base_dt + timedelta(days=6, minutes=(q_idx + 1) * 2)
                dt2 = base_dt + timedelta(days=7, minutes=(q_idx + 1) * 2)

                leg1 = Match.objects.create(
                    phase=phases["quarter"],
                    home_team=tbd, away_team=tbd,
                    match_leg="aller",
                    scheduled_date=dt1,
                    matchday=0,
                    is_played=False,
                    source_home_match=b,  # home = winner B
                    source_away_match=a,  # away = winner A
                )
                leg2 = Match.objects.create(
                    phase=phases["quarter"],
                    home_team=tbd, away_team=tbd,
                    match_leg="retour",
                    first_leg=leg1,
                    scheduled_date=dt2,
                    matchday=0,
                    is_played=False,
                    source_home_match=a,  # home = winner A
                    source_away_match=b,  # away = winner B
                )
                q_deciders.append(leg2)

            # -------------------------------------------------------
            # 4) Demis: (Q1 vs Q2), (Q3 vs Q4)
            # -------------------------------------------------------
            s_deciders = []
            for s_idx in range(2):
                a = q_deciders[s_idx * 2]
                b = q_deciders[s_idx * 2 + 1]

                dt1 = base_dt + timedelta(days=9, minutes=(s_idx + 1) * 2)
                dt2 = base_dt + timedelta(days=10, minutes=(s_idx + 1) * 2)

                leg1 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="aller",
                    scheduled_date=dt1,
                    matchday=0,
                    is_played=False,
                    source_home_match=b,
                    source_away_match=a,
                )
                leg2 = Match.objects.create(
                    phase=phases["semi"],
                    home_team=tbd, away_team=tbd,
                    match_leg="retour",
                    first_leg=leg1,
                    scheduled_date=dt2,
                    matchday=0,
                    is_played=False,
                    source_home_match=a,
                    source_away_match=b,
                )
                s_deciders.append(leg2)

            # -------------------------------------------------------
            # 5) Finale: match unique
            # -------------------------------------------------------
            dt_final = base_dt + timedelta(days=13, minutes=2)
            Match.objects.create(
                phase=phases["final"],
                home_team=tbd,
                away_team=tbd,
                match_leg="unique",
                scheduled_date=dt_final,
                matchday=0,
                is_played=False,
                source_home_match=s_deciders[0],
                source_away_match=s_deciders[1],
            )

        self.stdout.write(self.style.SUCCESS("OK: Bracket UCL complet généré (barrages -> finale)."))
        self.stdout.write(self.style.WARNING("Ensuite: python manage.py sync_knockout_bracket (pour remplacer TBD par les vainqueurs)."))