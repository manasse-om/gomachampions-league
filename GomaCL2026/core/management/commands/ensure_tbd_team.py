from django.core.management.base import BaseCommand
from core.models import Team

class Command(BaseCommand):
    help = "Crée l'équipe placeholder TBD (À déterminer) si elle n'existe pas."

    def handle(self, *args, **options):
        tbd, created = Team.objects.get_or_create(
            abbreviation="TBD",
            defaults={
                "player_name": "TBD",
                "team_name": "À déterminer",
                "whatsapp": "+243000000000",
                "payment_validated": False,
                "competition": None,
                "user": None,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS("OK: Team 'TBD' créée."))
        else:
            self.stdout.write(self.style.WARNING("OK: Team 'TBD' existe déjà."))

        self.stdout.write(self.style.SUCCESS(f"TBD id={tbd.id}, team_name='{tbd.team_name}'"))