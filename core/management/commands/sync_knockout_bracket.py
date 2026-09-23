from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from core.models import Match, Team, Competition

# Ordre croissant : playoff → final
PHASE_ORDER = {
    "playoff": 1,
    "round_16": 2,
    "quarter": 3,
    "semi": 4,
    "final": 5,
}


class Command(BaseCommand):
    help = "Remplace TBD par le vainqueur des matchs source (compétition active uniquement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--competition-id", type=int, default=None,
            help="ID de la compétition (défaut: compétition active)"
        )

    def handle(self, *args, **options):
        # --- Compétition ---
        competition = (
            Competition.objects.filter(pk=options["competition_id"]).first()
            if options["competition_id"]
            else Competition.objects.filter(is_active=True).first()
        )
        if not competition:
            raise CommandError("Aucune compétition active trouvée.")

        # --- TBD ---
        tbd = Team.objects.filter(abbreviation="TBD").first()
        if not tbd:
            raise CommandError(
                "Team placeholder 'TBD' introuvable. "
                "Lance: python manage.py ensure_tbd_team"
            )

        # --- Récupérer tous les matchs dépendants DE CETTE COMPÉTITION ---
        deps = Match.objects.filter(
            phase__competition=competition,
        ).filter(
            Q(source_home_match__isnull=False) | Q(source_away_match__isnull=False)
        ).select_related(
            "source_home_match", "source_away_match", "phase",
            "home_team", "away_team",
        )

        # --- Trier par ordre de phase pour propager en cascade ---
        deps = sorted(
            deps,
            key=lambda m: PHASE_ORDER.get(m.phase.name, 99)
        )

        updated = 0
        untouched = 0

        for m in deps:
            changed = False

            # --- Home ---
            if m.source_home_match_id:
                w = m.source_home_match.winner
                desired = w if w else tbd
                if m.home_team_id != desired.id:
                    m.home_team = desired
                    changed = True

            # --- Away ---
            if m.source_away_match_id:
                w = m.source_away_match.winner
                desired = w if w else tbd
                if m.away_team_id != desired.id:
                    m.away_team = desired
                    changed = True

            if changed:
                # ⚠️ On force l'update pour ne PAS déclencher le signal
                # knockout_auto_sync (évite la récursion infinie)
                Match.objects.filter(pk=m.pk).update(
                    home_team=m.home_team,
                    away_team=m.away_team,
                )
                updated += 1
            else:
                untouched += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: sync terminé. "
            f"Matchs mis à jour: {updated}, "
            f"inchangés: {untouched}, "
            f"compétition: '{competition.name}'."
        ))