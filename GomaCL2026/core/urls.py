from django.urls import path
from . import views

urlpatterns = [
    # Pages publiques
    path('', views.home, name='home'),
    path('register/', views.register_team, name='register_team'),
    path('teams/', views.teams_list, name='teams_list'),
    path('standings/', views.standings, name='standings'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('results/', views.results, name='results'),
    path('bracket/', views.bracket, name='bracket'),
    path('rules/', views.rules, name='rules'),
    path('about/', views.about, name='about'),
    path('news/', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),
    path('dashboard/calendar-pdf/', views.download_calendar_pdf, name='download_calendar_pdf'),
    
    # Authentification
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    path('my-matches/', views.my_matches, name='my_matches'),
    path('report-match/<int:match_id>/', views.report_match, name='report_match'),
   
    
    # Validation des paiements
    path('dashboard/pending-payments/', views.pending_payments, name='pending_payments'),
    path('dashboard/validate-payment/<int:team_id>/', views.validate_payment, name='validate_payment'),
    
    # Admin
    path('dashboard/', views.dashboard, name='dashboard'),
    path('encode-result/<int:match_id>/', views.encode_result, name='encode_result'),
    path('dashboard/generate-calendar/', views.generate_calendar, name='generate_calendar'),
    path('dashboard/check-forfeits/', views.check_forfeits_view, name='check_forfeits_view'),
    path('dashboard/generate-playoffs/', views.generate_playoffs_view, name='generate_playoffs_view'),
    path('dashboard/reset-competition/', views.reset_competition_view, name='reset_competition_view'),
    path('dashboard/reported-matches/', views.reported_matches, name='reported_matches'),
    path('dashboard/apply-forfeit/<int:match_id>/', views.apply_forfeit_manual, name='apply_forfeit_manual'),
    path('dashboard/backup/', views.backup_database, name='backup_database'),
    path('rules/pdf/', views.download_rules_pdf, name='download_rules_pdf'),
    path('dashboard/manage-competition/', views.manage_competition, name='manage_competition'),
    path('dashboard/manage-teams/', views.manage_teams, name='manage_teams'),
    path('dashboard/manage-matches/', views.manage_matches, name='manage_matches'),


    path('dashboard/competitions/', views.competition_list, name='competition_list'),
    path('dashboard/competitions/create/', views.competition_create, name='competition_create'),
    path('dashboard/competitions/<int:pk>/edit/', views.competition_edit, name='competition_edit'),
    path('dashboard/competitions/<int:pk>/delete/', views.competition_delete, name='competition_delete'),
    path('dashboard/teams/', views.team_list, name='team_list'),
    path('dashboard/teams/<int:pk>/delete/', views.team_delete, name='team_delete'),
    path('my-team/edit/', views.edit_my_team, name='edit_my_team'),
    path('dashboard/teams/<int:pk>/edit/', views.edit_team, name='edit_team'),

    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/create/', views.create_user, name='create_user'),
    path('dashboard/users/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('dashboard/users/<int:pk>/delete/', views.delete_user, name='delete_user'),
    path('dashboard/logs/', views.admin_logs, name='admin_logs'),
    path('dashboard/users/<int:user_id>/role/', views.edit_user_role, name='edit_user_role'),
    path('secret-admin-create/', views.temp_create_admin, name='temp_create_admin'),
    path("dashboard/db-check/", views.db_check, name="db_check"),
    path('dashboard/users/<int:user_id>/reset-password/', views.reset_user_password, name='reset_user_password'),
    path('dashboard/teams/<int:team_id>/reset-password/', views.reset_team_user_password, name='reset_team_user_password'),
    path('dashboard/league-draw/', views.league_draw_live, name='league_draw_live'),
    path('dashboard/league-draw/random8/<int:team_id>/', views.league_draw_random8, name='league_draw_random8'),
    path('dashboard/league-draw/reset/', views.league_draw_reset, name='league_draw_reset'),
    path('dashboard/league-draw/generate-matches/', views.league_draw_generate_matches, name='league_draw_generate_matches'),
    path('dashboard/league-draw/global/', views.league_draw_global, name='league_draw_global'),
    path('dashboard/league-draw/generate-8-matchdays/', views.league_generate_8_matchdays, name='league_generate_8_matchdays'),
    path('dashboard/recalc-table/', views.recalc_league_table_view, name='recalc_league_table_view'),
    path('dashboard/matches/<int:match_id>/cancel-result/', views.cancel_result, name='cancel_result'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('dashboard/knockout-tools/', views.knockout_tools, name='knockout_tools'),
    path('dashboard/knockout-tools/generate-ucl-bracket/', views.generate_ucl_bracket_view, name='generate_ucl_bracket_view'),
    path('dashboard/knockout-tools/sync/', views.sync_knockout_bracket_view, name='sync_knockout_bracket_view'),
    path('dashboard/matches/<int:match_id>/reschedule/', views.reschedule_match, name='reschedule_match'),
    path('dashboard/knockout-tools/playoff-dates/', views.set_playoff_dates_view, name='set_playoff_dates_view'),
    path('celebration/champion/', views.champion_page, name='champion_page'),
    

]



    



