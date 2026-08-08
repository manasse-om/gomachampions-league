from django.core.management.base import BaseCommand
from django.db.models import Q
from core.models import Match, Team


class Command(BaseCommand):
    help = "Remplace TBD par le vainqueur des matchs source (bracket intégral)."

    def handle(self, *args, **options):
        tbd = Team.objects.filter(abbreviation="TBD").first()
        if not tbd:
            self.stdout.write(self.style.ERROR("Team placeholder 'TBD' introuvable."))
            return

        deps = Match.objects.filter(
            Q(source_home_match__isnull=False) | Q(source_away_match__isnull=False)
        ).select_related("source_home_match", "source_away_match", "phase")

        updated = 0

        for m in deps:
            if m.is_played:
                continue

            changed = False

            if m.source_home_match_id:
                w = m.source_home_match.winner
                desired = w if w else tbd
                if m.home_team_id != desired.id:
                    m.home_team = desired
                    changed = True

            if m.source_away_match_id:
                w = m.source_away_match.winner
                desired = w if w else tbd
                if m.away_team_id != desired.id:
                    m.away_team = desired
                    changed = True

            if changed:
                m.save(update_fields=["home_team", "away_team"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"OK: sync terminé. Matchs mis à jour: {updated}"))