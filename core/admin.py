from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Team, Competition, Phase, Match, Group, News


# ==========================================
# ADMIN : ÉQUIPE
# ==========================================
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = [
        'team_name', 'abbreviation', 'player_name',
        'whatsapp', 'payment_validated',
        'points', 'played', 'wins',
        'draws', 'losses', 'goal_difference'
    ]
    list_filter = ['payment_validated', 'competition', 'created_at']
    search_fields = ['team_name', 'player_name', 'abbreviation', 'whatsapp']


# ==========================================
# ADMIN : COMPÉTITION
# ==========================================
@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'format_type', 'max_teams',
        'registered_teams_count',
        'pending_teams_count',
        'is_active', 'registration_open',
        'start_date'
    ]
    list_filter = ['format_type', 'is_active', 'registration_open']
    search_fields = ['name']


# ==========================================
# ADMIN : PHASE
# ==========================================
@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ['competition', 'name', 'order', 'is_active']
    list_filter = ['competition', 'name', 'is_active']


# ==========================================
# ADMIN : MATCH
# ==========================================
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'home_team',
        'away_team',
        'phase',
        'match_leg',
        'scheduled_date',
        'is_played'
    ]
    list_filter = [
        'phase',
        'match_leg',
        'is_played',
        'is_forfeit'
    ]
    search_fields = [
        'home_team__team_name',
        'away_team__team_name',
        'home_team__abbreviation',
        'away_team__abbreviation'
    ]
    date_hierarchy = 'scheduled_date'


# ==========================================
# ADMIN : GROUPE
# ==========================================
@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'competition']
    list_filter = ['competition']
    filter_horizontal = ['teams']


# ==========================================
# ADMIN : ACTUALITÉ
# ==========================================
@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_published', 'created_at']
    list_filter = ['is_published']
    search_fields = ['title']