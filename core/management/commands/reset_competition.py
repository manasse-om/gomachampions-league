from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Match, Phase, Team, LeagueDrawSession, LeagueDrawPair


class Command(BaseCommand):
    help = "Réinitialise la compétition active (matchs, phases, stats équipes)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmer la réinitialisation'
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                "Ajoute --confirm pour confirmer la réinitialisation."
            ))
            return

        from core.models import Competition
        competition = Competition.objects.filter(is_active=True).first()
        if not competition:
            self.stdout.write(self.style.ERROR("Aucune compétition active."))
            return

        with transaction.atomic():
            # 1. Supprimer tous les matchs
            matches_deleted, _ = Match.objects.filter(
                phase__competition=competition
            ).delete()

            # 2. Supprimer toutes les phases
            phases_deleted, _ = Phase.objects.filter(
                competition=competition
            ).delete()

            # 3. Supprimer les sessions de tirage
            sessions = LeagueDrawSession.objects.filter(competition=competition)
            LeagueDrawPair.objects.filter(session__in=sessions).delete()
            sessions.delete()

            # 4. Réinitialiser les stats des équipes
            Team.objects.filter(competition=competition).update(
                played=0, wins=0, draws=0, losses=0,
                goals_for=0, goals_against=0, points=0
            )

        self.stdout.write(self.style.SUCCESS(
            f"Compétition '{competition.name}' réinitialisée.\n"
            f"  Matchs supprimés: {matches_deleted}\n"
            f"  Phases supprimées: {phases_deleted}\n"
            f"  Stats équipes remises à zéro."
        ))