from datetime import date, timedelta
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goma_cl.settings")
django.setup()

from core.models import Competition, Team

comp = Competition.objects.create(
    name="TEST - League Draw 36",
    format_type="ucl",
    max_teams=36,
    is_active=True,
    registration_open=False,
    registration_fee=1000,
    start_date=date.today(),
    end_date=date.today() + timedelta(days=60),
)

Competition.objects.exclude(id=comp.id).update(is_active=False)

created = 0
for i in range(1, 37):
    abbr = f"T{i:02d}"
    whatsapp = f"+24399988{i:04d}"

    team, was_created = Team.objects.get_or_create(
        abbreviation=abbr,
        defaults={
            "competition": comp,
            "player_name": f"Player {i:02d}",
            "team_name": f"Test Team {i:02d}",
            "whatsapp": whatsapp,
            "payment_validated": True,
        }
    )

    if not was_created:
        team.competition = comp
        team.player_name = f"Player {i:02d}"
        team.team_name = f"Test Team {i:02d}"
        team.whatsapp = whatsapp
        team.payment_validated = True
        team.save()

    created += 1

print("OK - competition:", comp.id, comp.name, "| teams:", created)