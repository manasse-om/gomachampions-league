import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Competition, Team


class Command(BaseCommand):
    help = "Crée une compétition de test + équipes validées"

    def add_arguments(self, parser):
        parser.add_argument('--teams', type=int, default=16)
        parser.add_argument('--name', type=str, default='Goma CL Test 2026')
        parser.add_argument('--reset', action='store_true')

    def handle(self, *args, **options):
        n_teams = options['teams']
        comp_name = options['name']

        if n_teams < 12 or n_teams > 36:
            self.stdout.write(self.style.ERROR(f"Nombre invalide: {n_teams}. Attendu: 12-36"))
            return

        # Reset optionnel
        if options['reset']:
            old = Competition.objects.filter(name=comp_name).first()
            if old:
                Team.objects.filter(competition=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING(f"Ancienne compétition supprimée."))

        # Créer compétition
        comp, created = Competition.objects.get_or_create(
            name=comp_name,
            defaults={
                'format_type': 'ucl',
                'max_teams': 36,
                'is_active': True,
                'registration_open': False,
                'registration_fee': 1000,
                'start_date': timezone.now().date() + timedelta(days=7),
            }
        )
        self.stdout.write(f"Compétition: {comp.name}")

        # Créer équipes
        cities = ['Goma', 'Bukavu', 'Kinshasa', 'Lubumbashi', 'Matadi',
                  'Kisangani', 'Bunia', 'Uvira', 'Butembo', 'Beni',
                  'Kalemie', 'Kolwezi', 'Likasi', 'Kikwit', 'Tshikapa',
                  'Mbandaka', 'Kindu', 'Isiro', 'Gemena', 'Boma']

        created_count = 0
        for i in range(1, n_teams + 1):
            username = f"testteam{i:02d}"
            abbreviation = f"T{i:02d}"

            user, u_new = User.objects.get_or_create(
                username=username,
                defaults={'first_name': f'Player {i}', 'email': f'{username}@test.local'}
            )
            if u_new:
                user.set_password('test1234')
                user.save()

            team, t_new = Team.objects.get_or_create(
                abbreviation=abbreviation,
                competition=comp,
                defaults={
                    'user': user,
                    'player_name': f'Player {i}',
                    'team_name': f"{cities[i % len(cities)]} FC",
                    'whatsapp': f'+2439{i:08d}'[:15],
                    'payment_validated': True,
                    'payment_validated_at': timezone.now(),
                }
            )
            if t_new:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: {created_count} équipes créées. "
            f"Comptes: testteam01 à testteam{n_teams:02d} (mdp: test1234)"
        ))