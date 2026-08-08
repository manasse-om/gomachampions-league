from django.core.management.base import BaseCommand
from core.models import Team, Match, Competition


class Command(BaseCommand):
    help = "Recalculer les stats (phase league) à partir des matchs joués — compétition active uniquement"

    def handle(self, *args, **options):

        # ✅ CORRIGÉ: prendre la compétition active
        competition = Competition.objects.filter(is_active=True).first()
        if not competition:
            self.stdout.write(self.style.ERROR("Aucune compétition active trouvée."))
            return

        self.stdout.write(f"Recalcul pour : {competition.name}")

        # ✅ CORRIGÉ: charger uniquement les équipes de cette compétition
        teams = Team.objects.filter(competition=competition).in_bulk()  # {id: Team}

        # Reset stats (en mémoire)
        for t in teams.values():
            t.played = 0
            t.wins = 0
            t.draws = 0
            t.losses = 0
            t.goals_for = 0
            t.goals_against = 0
            t.points = 0

        # ✅ CORRIGÉ: uniquement les matchs de la phase league de cette compétition
        matches = Match.objects.filter(
            is_played=True,
            phase__name='league',
            phase__competition=competition   # ← filtre par compétition
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

        # Sauvegarde en une fois (bulk_update = très performant)
        Team.objects.bulk_update(
            teams.values(),
            ['played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'points']
        )

        self.stdout.write(self.style.SUCCESS(
            f"OK: Classement recalculé pour '{competition.name}'. {len(teams)} équipes mises à jour."
        ))