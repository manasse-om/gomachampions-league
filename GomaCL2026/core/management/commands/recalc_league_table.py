from django.core.management.base import BaseCommand
from core.models import Team, Match

class Command(BaseCommand):
    help = "Recalculer les stats (phase league) à partir des matchs joués"

    def handle(self, *args, **options):
        # Charger toutes les équipes UNE SEULE FOIS (1 objet par team)
        teams = Team.objects.in_bulk()  # {id: Team}

        # Reset stats (en mémoire)
        for t in teams.values():
            t.played = 0
            t.wins = 0
            t.draws = 0
            t.losses = 0
            t.goals_for = 0
            t.goals_against = 0
            t.points = 0

        matches = Match.objects.filter(
            is_played=True,
            phase__name='league'
        ).values(
            'home_team_id', 'away_team_id',
            'is_forfeit', 'forfeit_team_id',
            'home_score', 'away_score'
        )

        for m in matches:
            home = teams.get(m['home_team_id'])
            away = teams.get(m['away_team_id'])
            if not home or not away:
                continue

            if m['is_forfeit']:
                # Forfait = 3-0
                if m['forfeit_team_id'] == home.id:
                    # away gagne
                    away.played += 1
                    away.wins += 1
                    away.points += 3
                    away.goals_for += 3

                    home.played += 1
                    home.losses += 1
                    home.goals_against += 3
                else:
                    # home gagne
                    home.played += 1
                    home.wins += 1
                    home.points += 3
                    home.goals_for += 3

                    away.played += 1
                    away.losses += 1
                    away.goals_against += 3

            else:
                hs = m['home_score'] or 0
                a_s = m['away_score'] or 0

                home.played += 1
                away.played += 1

                home.goals_for += hs
                home.goals_against += a_s

                away.goals_for += a_s
                away.goals_against += hs

                if hs > a_s:
                    home.wins += 1
                    home.points += 3
                    away.losses += 1
                elif hs < a_s:
                    away.wins += 1
                    away.points += 3
                    home.losses += 1
                else:
                    home.draws += 1
                    away.draws += 1
                    home.points += 1
                    away.points += 1

        # Sauvegarde en une fois (très important)
        Team.objects.bulk_update(
            teams.values(),
            ['played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'points']
        )

        self.stdout.write(self.style.SUCCESS("OK: Classement recalculé (phase league)."))