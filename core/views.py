from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .decorators import role_required   # ← Ligne magique
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, F
from django.utils import timezone
from .models import Team, Competition, Phase, Match, Group, News, UserProfile
from .forms import TeamRegistrationForm, MatchResultForm
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.core.management import call_command
from io import StringIO
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from .forms import CompetitionForm
from django.contrib.auth.forms import UserCreationForm
from functools import wraps
from .models import AdminLog
import os
from django.views.decorators.http import require_GET
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.db import transaction
from django.http import JsonResponse
from django.db import connection
import random
from django.db.models import Count, Q
from django.utils.crypto import get_random_string
from .forms import SimplePasswordResetForm
from django.db.models import Prefetch
from .forms import MatchRescheduleForm
from .models import AdminLog
from datetime import datetime, time
from django.utils import timezone
from django.shortcuts import render, redirect
from .decorators import role_required
from .models import Competition, Match, AdminLog
from django.db.models import Max, Min


# ==========================================
# PAGE D'ACCUEIL
# ==========================================


def home(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()

    n_teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").count() if competition else 0

    fmt = get_competition_format(n_teams) if n_teams >= 12 else None
    top_n = fmt['direct_qualified'] if fmt else 8

    active_teams = Team.objects.filter(
        payment_validated=True,
        played__gt=0,
        competition=competition
    ).exclude(abbreviation="TBD") if competition else Team.objects.none()

    best_attack = active_teams.order_by('-goals_for').first()
    best_defense = active_teams.order_by('goals_against').first()
    top_winner = active_teams.order_by('-wins').first()

    top_teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").order_by(
        '-points', '-goals_for'
    )[:top_n] if competition else []

    upcoming_matches = Match.objects.filter(
        is_played=False,
        scheduled_date__gte=timezone.now(),
        phase__competition=competition
    ).order_by('scheduled_date')[:3]

    latest_news = News.objects.filter(
        is_published=True
    ).order_by('-created_at')[:3]

    context = {
        'competition': competition,
        'top_teams': top_teams,
        'upcoming_matches': upcoming_matches,
        'latest_news': latest_news,
        'best_attack': best_attack,
        'best_defense': best_defense,
        'top_winner': top_winner,
        'fmt': fmt,
        'top_n': top_n,
    }
    return render(request, 'core/home.html', context)

# ==========================================
# INSCRIPTION D'UN JOUEUR (AVEC PAIEMENT)
# ==========================================
def register_team(request):
    competition = Competition.objects.filter(is_active=True, registration_open=True).first()

    if not competition:
        messages.error(request, _("Les inscriptions sont fermées."))
        return redirect('home')

    if competition.is_registration_full:
        messages.error(request, _(f"Le nombre maximum d'équipes ({competition.max_teams}) a été atteint."))
        return redirect('home')

    if request.method == 'POST':
        # ✅ CORRIGÉ: passer la compétition au formulaire
        form = TeamRegistrationForm(request.POST, request.FILES, competition=competition)

        if form.is_valid():
            team = form.save(commit=False)
            username = form.cleaned_data['abbreviation'].lower()
            password = form.cleaned_data.get('password')

            # ✅ CAS 1 : joueur de la saison précédente (compte User existe déjà)
            existing_user = User.objects.filter(username=username).first()

            if existing_user:
                # Vérifier qu'il n'est pas déjà inscrit dans CETTE compétition
                already_registered = Team.objects.filter(
                    user=existing_user,
                    competition=competition
                ).exists()

                if already_registered:
                    messages.error(request, _("Vous êtes déjà inscrit dans cette compétition."))
                    return render(request, 'core/register_team.html', {
                        'form': form,
                        'competition': competition,
                        'remaining_slots': competition.max_teams - competition.registered_teams_count,
                    })

                # Réutiliser le compte existant
                user = existing_user

                # Mettre à jour le mot de passe si fourni
                if password:
                    user.set_password(password)
                    user.first_name = form.cleaned_data['player_name']
                    user.save()

                messages.info(request, _(
                    "Compte existant détecté. Votre nouvelle équipe a été créée pour cette saison."
                ))

            else:
                # ✅ CAS 2 : nouveau joueur → créer le compte
                if not password:
                    messages.error(request, _("Le mot de passe est obligatoire."))
                    return render(request, 'core/register_team.html', {
                        'form': form,
                        'competition': competition,
                        'remaining_slots': competition.max_teams - competition.registered_teams_count,
                    })

                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=form.cleaned_data['player_name'],
                    email=f"{username}@gomacl.local"
                )

                if hasattr(user, "userprofile"):
                    user.userprofile.role = "player"
                    user.userprofile.save()

            # ✅ Créer la Team pour CETTE compétition
            team.user = user
            team.competition = competition
            team.payment_validated = False
            team.save()

            messages.success(
                request,
                "✅ Inscription réussie ! Rejoignez le groupe WhatsApp et envoyez la preuve de paiement pour validation."
            )
            return redirect('home')

        else:
            messages.error(request, _("Inscription refusée : corrige les champs en rouge puis réessaie."))

    else:
        # ✅ CORRIGÉ: passer la compétition au formulaire vide aussi
        form = TeamRegistrationForm(competition=competition)

    context = {
        'form': form,
        'competition': competition,
        'remaining_slots': competition.max_teams - competition.registered_teams_count if competition else 0,
    }
    return render(request, 'core/register_team.html', context)
# ==========================================
# LISTE DES ÉQUIPES
# ==========================================
def teams_list(request):
    competition = Competition.objects.filter(is_active=True).first()

    # ✅ CORRIGÉ: filtrer par compétition active
    teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ) if competition else Team.objects.none()

    context = {
        'teams': teams,
        'competition': competition,
    }
    return render(request, 'core/teams_list.html', context)


# ==========================================
# CLASSEMENT GÉNÉRAL
# ==========================================
def standings(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()

    teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").annotate(
        diff_buts=F('goals_for') - F('goals_against')
    ).order_by(
        '-points', '-diff_buts', '-goals_for'
    ) if competition else Team.objects.none()

    n_teams = teams.count()
    fmt = get_competition_format(n_teams) if n_teams >= 12 else None

    direct_end = fmt['direct_qualified'] if fmt else 8
    playoff_end = direct_end + fmt['playoff_participants'] if fmt else 24

    context = {
        'teams': teams,
        'competition': competition,
        'fmt': fmt,
        'direct_end': direct_end,
        'playoff_end': playoff_end,
    }
    return render(request, 'core/standings.html', context)

# ==========================================
# CALENDRIER DES MATCHS
# ==========================================


def fixtures(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    today = timezone.localdate()
    fmt = None

    if competition:
        n_teams = Team.objects.filter(
            payment_validated=True,
            competition=competition
        ).exclude(abbreviation="TBD").count()
        fmt = get_competition_format(n_teams) if n_teams >= 12 else None

        phases = Phase.objects.filter(
            competition=competition
        ).prefetch_related(
            Prefetch(
                'matches',
                queryset=Match.objects.select_related(
                    'home_team', 'away_team', 'phase'
                ).order_by('scheduled_date')
            )
        )
        for ph in phases:
            ph.today_matches = [
                m for m in ph.matches.all()
                if timezone.localtime(m.scheduled_date).date() == today
            ]
    else:
        phases = []

    return render(request, 'core/fixtures.html', {
        'competition': competition,
        'phases': phases,
        'today': today,
        'fmt': fmt,
    })


# ==========================================
# RÉSULTATS DES MATCHS
# ==========================================
def results(request):
    """
    Tous les résultats des matchs joués
    """
    played_matches = Match.objects.filter(is_played=True).order_by('-played_date')
    
    context = {
        'matches': played_matches,
    }
    return render(request, 'core/results.html', context)


# ==========================================
# TABLEAU ÉLIMINATOIRE (BRACKET)
# ==========================================

def _tie_payload(return_match: Match):
    leg1 = return_match.first_leg
    team_a = return_match.home_team
    team_b = return_match.away_team

    leg1_a = leg1_b = None
    if leg1 and leg1.is_played:
        if leg1.home_team_id == team_a.id:
            leg1_a, leg1_b = leg1.home_score, leg1.away_score
        else:
            leg1_a, leg1_b = leg1.away_score, leg1.home_score

    leg2_a = return_match.home_score if return_match.is_played else None
    leg2_b = return_match.away_score if return_match.is_played else None

    agg = return_match.aggregate_score
    winner = return_match.winner

    return {
        "match": return_match,
        "team_a": team_a,
        "team_b": team_b,
        "leg1": leg1,
        "leg1_a": leg1_a,
        "leg1_b": leg1_b,
        "leg2_a": leg2_a,
        "leg2_b": leg2_b,
        "agg_a": agg["home"] if agg else None,
        "agg_b": agg["away"] if agg else None,
        "winner_id": winner.id if winner else None,
        "is_forfeit": return_match.is_forfeit,
        "pen_a": return_match.home_penalties,
        "pen_b": return_match.away_penalties,
    }

def bracket(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        return render(request, "core/bracket.html", {"competition": None})

    def get_returns(phase_name):
        return Match.objects.filter(
            phase__competition=competition,
            phase__name=phase_name,
            match_leg="retour",
        ).select_related(
            "phase",
            "home_team", "away_team",
            "first_leg",
            "first_leg__home_team",
            "first_leg__away_team",
        ).order_by("id")

    n_teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").count()

    fmt = get_competition_format(n_teams) if n_teams >= 12 else None
    bracket_type = fmt['bracket'] if fmt else 'round_16'

    playoff_ties = [_tie_payload(m) for m in get_returns("playoff")]
    r16_ties = []
    if bracket_type == 'round_16':
        r16_ties = [_tie_payload(m) for m in get_returns("round_16")]

    qf_ties = [_tie_payload(m) for m in get_returns("quarter")]
    sf_ties = [_tie_payload(m) for m in get_returns("semi")]

    def split_halves(lst):
        mid = len(lst) // 2
        return lst[:mid], lst[mid:]

    playoff_left, playoff_right = split_halves(playoff_ties)
    r16_left, r16_right = split_halves(r16_ties)
    qf_left, qf_right = split_halves(qf_ties)
    sf_left, sf_right = split_halves(sf_ties)

    final_match = Match.objects.filter(
        phase__competition=competition,
        phase__name="final",
        match_leg="unique",
    ).select_related(
        "phase", "home_team", "away_team"
    ).order_by("id").first()

    return render(request, "core/bracket.html", {
        "competition": competition,
        "fmt": fmt,
        "bracket_type": bracket_type,
        "n_teams": n_teams,
        "playoff_left": playoff_left,
        "playoff_right": playoff_right,
        "r16_left": r16_left,
        "r16_right": r16_right,
        "qf_left": qf_left,
        "qf_right": qf_right,
        "sf_left": sf_left,
        "sf_right": sf_right,
        "playoff_ties": playoff_ties,
        "r16_ties": r16_ties,
        "qf_ties": qf_ties,
        "sf_ties": sf_ties,
        "final_match": final_match,
    })

# ==========================================
# RÈGLEMENT
# ==========================================
def rules(request):
    """
    Règlement de la compétition
    """
    competition = Competition.objects.filter(is_active=True).first()
    
    context = {
        'competition': competition,
    }
    return render(request, 'core/rules.html', context)


# ==========================================
# À PROPOS
# ==========================================
def about(request):
    """
    Page À propos (organisateurs)
    """
    organizers = [
        {'name': 'Manassé Ombeni', 'role': _('Organisateur principal')},
        {'name': 'Job Badesire', 'role': _('Co-organisateur')},
        {'name': 'Héritier DJO', 'role': _('Co-organisateur')},
        {'name': 'Joachim', 'role': _('Co-organisateur')},
        {'name': 'Ildephonse', 'role': _('Co-organisateur')},
    ]
    
    context = {
        'organizers': organizers,
    }
    return render(request, 'core/about.html', context)


# ==========================================
# ACTUALITÉS
# ==========================================
def news_list(request):
    """
    Liste des actualités
    """
    news = News.objects.filter(is_published=True)
    
    context = {
        'news': news,
    }
    return render(request, 'core/news_list.html', context)


def news_detail(request, pk):
    """
    Détail d'une actualité
    """
    news = get_object_or_404(News, pk=pk, is_published=True)
    
    context = {
        'news': news,
    }
    return render(request, 'core/news_detail.html', context)


# =CONNEXION=========================================
def user_login(request):
    """
    Page de connexion
    """
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, _("Connexion réussie !"))

            # ✅ Redirection unique vers HOME (sauf si next est fourni)
            return redirect(next_url) if next_url else redirect('home')
        else:
            messages.error(request, _("Nom d'utilisateur ou mot de passe incorrect."))

    return render(request, 'core/login.html', {"next": next_url})

# ==========================================
# DÉCONNEXION
# ==========================================
def user_logout(request):
    """
    Déconnexion
    """
    logout(request)
    messages.success(request, _("Vous êtes déconnecté."))
    return redirect('home')


# ==========================================
# DASHBOARD ADMIN
# ==========================================
@login_required
def dashboard(request):

    if not hasattr(request.user, 'userprofile'):
        return redirect('home')

    if request.user.userprofile.role not in [
        'superadmin', 'organisateur', 'paiement', 'match'
    ]:
        messages.error(request, "Accès refusé.")
        return redirect('home')

    # ✅ CORRIGÉ: filtrer par compétition active
    competition = Competition.objects.filter(is_active=True).first()

    total_teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).count()

    pending_teams = Team.objects.filter(
        payment_validated=False,
        competition=competition
    ).count()

    total_matches = Match.objects.filter(
        phase__competition=competition
    ).count()

    played_matches = Match.objects.filter(
        is_played=True,
        phase__competition=competition
    ).count()

    return render(request, 'core/dashboard.html', {
        'total_teams': total_teams,
        'pending_teams': pending_teams,
        'total_matches': total_matches,
        'played_matches': played_matches,
    })

# ==========================================
# ENCODER UN RÉSULTAT (ADMIN)
# ==========================================
@login_required
def encode_result(request, match_id):

    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role not in [
        'superadmin',
        'organisateur',
        'match'
    ]:
        messages.error(request, _("Accès refusé."))
        return redirect('home')

    match = get_object_or_404(Match, pk=match_id)

    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            match = form.save(commit=False)
            match.is_played = True
            match.played_date = timezone.now()
            match.save()  # ✅ signals => recalcul auto si phase league

            if match.phase.name == 'final':
                return redirect('champion_page')
            
            messages.success(request, _("Résultat enregistré avec succès !"))
            return redirect('fixtures')

            if match.phase and match.phase.name == "league":
                messages.success(request, _("Résultat enregistré. Classement mis à jour automatiquement."))
            else:
                messages.success(request, _("Résultat enregistré avec succès !"))

            return redirect('fixtures')
    else:
        form = MatchResultForm(instance=match)

    return render(request, 'core/encode_result.html', {
        'form': form,
        'match': match,
    })

# ==========================================
# FONCTION : METTRE À JOUR LES STATS
# ==========================================
def update_team_stats(match):
    """
    Met à jour les statistiques des équipes
    ⚠️ Utilisé uniquement pour la phase de ligue
    """
    home_team = match.home_team
    away_team = match.away_team
    
    if match.is_forfeit:
        if match.forfeit_team == home_team:
            away_team.wins += 1
            away_team.points += 3
            away_team.goals_for += 3
            away_team.played += 1
            
            home_team.losses += 1
            home_team.goals_against += 3
            home_team.played += 1
        else:
            home_team.wins += 1
            home_team.points += 3
            home_team.goals_for += 3
            home_team.played += 1
            
            away_team.losses += 1
            away_team.goals_against += 3
            away_team.played += 1
    else:
        home_team.played += 1
        away_team.played += 1
        
        home_team.goals_for += match.home_score
        home_team.goals_against += match.away_score
        
        away_team.goals_for += match.away_score
        away_team.goals_against += match.home_score
        
        if match.home_score > match.away_score:
            home_team.wins += 1
            home_team.points += 3
            away_team.losses += 1
        elif match.home_score < match.away_score:
            away_team.wins += 1
            away_team.points += 3
            home_team.losses += 1
        else:
            home_team.draws += 1
            away_team.draws += 1
            home_team.points += 1
            away_team.points += 1
    
    home_team.save()
    away_team.save()


# ==========================================
# MES MATCHS (POUR LES JOUEURS)
# ==========================================
@login_required
def my_matches(request):
    """
    Afficher les matchs de l'utilisateur connecté
    """
    # Récupérer l'équipe de l'utilisateur
    try:
        team = Team.objects.get(user=request.user)
    except Team.DoesNotExist:
        messages.error(request, _("Vous n'avez pas d'équipe associée."))
        return redirect('home')
    
    # Vérifier si le paiement est validé
    if not team.payment_validated:
        messages.warning(request, _("Votre inscription est en attente de validation du paiement."))
    
    # Récupérer tous les matchs de cette équipe
    upcoming_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        is_played=False
    ).order_by('scheduled_date')
    
    played_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        is_played=True
    ).order_by('-played_date')[:10]
    
    context = {
        'team': team,
        'upcoming_matches': upcoming_matches,
        'played_matches': played_matches,
    }
    return render(request, 'core/my_matches.html', context)


# ==========================================
# SIGNALER UN PROBLÈME
# ==========================================
@login_required
def report_match(request, match_id):
    """
    Signaler un problème sur un match
    """
    match = get_object_or_404(Match, pk=match_id)
    
    # Vérifier que l'utilisateur est bien impliqué dans ce match
    try:
        team = Team.objects.get(user=request.user)
    except Team.DoesNotExist:
        messages.error(request, _("Vous n'avez pas d'équipe associée."))
        return redirect('home')
    
    if match.home_team != team and match.away_team != team:
        messages.error(request, _("Vous n'êtes pas impliqué dans ce match."))
        return redirect('my_matches')
    
    # Vérifier que le match n'est pas déjà joué
    if match.is_played:
        messages.error(request, _("Ce match a déjà été joué."))
        return redirect('my_matches')
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        details = request.POST.get('details', '')
        
        match.reported = True
        match.reported_by = team
        match.report_reason = reason
        match.report_details = details
        match.report_date = timezone.now()
        match.save()
        
        messages.success(request, _("Signalement envoyé avec succès. L'admin va examiner votre demande."))
        return redirect('my_matches')
    
    context = {
        'match': match,
        'team': team,
    }
    return render(request, 'core/report_match.html', context)


# ==========================================
# MATCHS SIGNALÉS (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'match'])
def reported_matches(request):

    reported = Match.objects.filter(
        reported=True,
        is_played=False
    ).order_by('report_date')

    deadline = timezone.now() - timedelta(hours=48)

    late_matches = Match.objects.filter(
        is_played=False,
        is_forfeit=False,
        scheduled_date__lt=deadline
    ).exclude(reported=True).order_by('scheduled_date')

    return render(request, 'core/reported_matches.html', {
        'reported_matches': reported,
        'late_matches': late_matches,
    })


# ==========================================
# APPLIQUER UN FORFAIT (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'match'])
def apply_forfeit_manual(request, match_id):
    match = get_object_or_404(Match, pk=match_id)

    if request.method == 'POST':
        forfeit_team_id = request.POST.get('forfeit_team')
        forfeit_team = get_object_or_404(Team, pk=forfeit_team_id)

        match.is_forfeit = True
        match.is_played = True
        match.forfeit_team = forfeit_team
        match.played_date = timezone.now()

        if forfeit_team == match.home_team:
            match.home_score = 0
            match.away_score = 3
        else:
            match.home_score = 3
            match.away_score = 0

        match.save()  # ✅ signals => recalcul auto si phase league

        if match.phase and match.phase.name == "league":
            messages.success(request, "Forfait appliqué. Classement mis à jour automatiquement.")
        else:
            messages.success(request, "Forfait appliqué.")

        return redirect('reported_matches')

    return render(request, 'core/apply_forfait.html', {'match': match})

# ==========================================
# ACTIONS ADMIN : GÉNÉRER LE CALENDRIER
# ==========================================
@role_required(['superadmin', 'organisateur'])
def generate_calendar(request):
    # Redirige vers la génération adaptative
    return redirect('league_generate_8_matchdays')

# ==========================================
# ACTIONS ADMIN : VÉRIFIER LES FORFAITS
# ==========================================
@role_required(['superadmin', 'organisateur'])
def check_forfeits_view(request):
    competition = Competition.objects.filter(is_active=True).first()
    deadline = timezone.now() - timedelta(hours=48)

    late_matches = Match.objects.filter(
        phase__competition=competition,
        is_played=False,
        is_forfeit=False,
        scheduled_date__lt=deadline
    ).count()

    messages.success(
        request,
        f"Vérification terminée. {late_matches} match(s) en retard détecté(s)."
    )
    return redirect('reported_matches')


# ==========================================
# ACTIONS ADMIN : GÉNÉRER LES PLAYOFFS
# ==========================================
@role_required(['superadmin', 'organisateur'])
def generate_playoffs_view(request):
    # Redirige vers la génération UCL bracket adaptative
    return redirect('generate_ucl_bracket_view')


# ==========================================
# ACTIONS ADMIN : RÉINITIALISER LA COMPÉTITION
# ==========================================
@role_required(['superadmin'])
def reset_competition_view(request):

    if request.method == 'POST':
        call_command('reset_competition', '--confirm')
        messages.warning(request, "Compétition réinitialisée.")
        return redirect('dashboard')

    return render(request, 'core/confirm_reset.html')


# ==========================================
# VALIDATION DES PAIEMENTS (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'paiement'])
def pending_payments(request):

    pending_teams = Team.objects.filter(
        payment_validated=False
    ).order_by('-created_at')

    return render(request, 'core/pending_payments.html', {
        'pending_teams': pending_teams,
    })


@role_required(['superadmin', 'organisateur', 'paiement'])
def validate_payment(request, team_id):

    team = get_object_or_404(Team, pk=team_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            team.payment_validated = True
            team.payment_validated_by = request.user
            team.payment_validated_at = timezone.now()
            team.save()

            AdminLog.objects.create(
                user=request.user,
                action=f"Validation paiement {team.team_name}"
            )

        elif action == 'reject':
            team.delete()

        return redirect('pending_payments')

    return render(request, 'core/validate_payment.html', {
        'team': team,
    })


@role_required(['superadmin', 'organisateur', 'match'])
def download_calendar_pdf(request):
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    phases = Phase.objects.filter(competition=competition).prefetch_related('matches')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="calendrier_goma_cl.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 40
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, competition.name)
    y -= 30

    p.setFont("Helvetica", 10)

    for phase in phases:
        p.drawString(50, y, phase.get_name_display())
        y -= 20

        for match in phase.matches.all():
            line = f"{match.scheduled_date.strftime('%d/%m/%Y %H:%M')} - {match.home_team.team_name} vs {match.away_team.team_name}"
            p.drawString(60, y, line)
            y -= 15

            if y < 50:
                p.showPage()
                p.setFont("Helvetica", 10)
                y = height - 40

        y -= 10

    p.save()
    return response


@role_required(['superadmin', 'organisateur'])
def backup_database(request):
    response = HttpResponse(content_type='application/json')
    filename = f"backup_gomacl_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    output = StringIO()
    call_command('dumpdata', stdout=output)
    response.write(output.getvalue())
    return response



def download_rules_pdf(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()
    elements = []

    title_style = styles["Heading1"]
    normal_style = styles["Normal"]

    elements.append(Paragraph("GOMA CHAMPIONS LEAGUE 2026", title_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("REGLEMENT OFFICIEL", styles["Heading2"]))
    elements.append(Spacer(1, 0.5 * inch))

    content = render_to_string("core/rules_pdf_content.html")

    for line in content.split("\n"):
        elements.append(Paragraph(line, normal_style))
        elements.append(Spacer(1, 0.2 * inch))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Reglement_GomaCL_{datetime.now().strftime("%Y%m%d")}.pdf"'

    return response


@role_required(['superadmin', 'organisateur'])
def manage_competition(request):
    competition = Competition.objects.first()
    return render(request, 'core/manage_competition.html', {
        'competition': competition
    })

@role_required(['superadmin', 'organisateur'])
def manage_teams(request):
    teams = Team.objects.all()
    return render(request, 'core/manage_teams.html', {
        'teams': teams
    })

@role_required(['superadmin', 'organisateur', 'match'])
def manage_matches(request):
    matches = Match.objects.all().order_by('-scheduled_date')
    return render(request, 'core/manage_matches.html', {
        'matches': matches
    })

@role_required(['superadmin', 'organisateur'])
def competition_list(request):
    competitions = Competition.objects.all()
    return render(request, 'core/admin/competition_list.html', {
        'competitions': competitions
    })


@role_required(['superadmin', 'organisateur'])
@role_required(['superadmin', 'organisateur'])
def competition_create(request):
    form = CompetitionForm(request.POST or None)
    if form.is_valid():
        # ✅ CORRIGÉ: désactiver toutes les compétitions actives avant d'en créer une nouvelle
        Competition.objects.filter(is_active=True).update(
            is_active=False,
            registration_open=False
        )
        form.save()
        messages.success(request, "Compétition créée avec succès ! L'ancienne saison a été archivée.")
        return redirect('competition_list')
    return render(request, 'core/admin/competition_form.html', {
        'form': form,
        'title': 'Créer une compétition'
    })


@role_required(['superadmin', 'organisateur'])
def competition_edit(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    form = CompetitionForm(request.POST or None, instance=competition)
    if form.is_valid():
        form.save()
        messages.success(request, "Compétition modifiée avec succès !")
        return redirect('competition_list')
    return render(request, 'core/admin/competition_form.html', {
        'form': form,
        'title': 'Modifier la compétition'
    })


@role_required(['superadmin', 'organisateur'])
def competition_delete(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    competition.delete()
    messages.success(request, "Compétition supprimée.")
    return redirect('competition_list')

@role_required(['superadmin', 'organisateur'])
def team_list(request):
    teams = Team.objects.all()
    return render(request, 'core/admin/team_list.html', {
        'teams': teams
    })


@role_required(['superadmin', 'organisateur'])
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk)
    team.delete()
    messages.success(request, "Équipe supprimée avec succès.")
    return redirect('team_list')


@login_required
def edit_my_team(request):
    team = get_object_or_404(Team, user=request.user)

    form = TeamRegistrationForm(request.POST or None, instance=team)

    if form.is_valid():
        form.save()
        return redirect('my_matches')

    return render(request, 'core/edit_my_team.html', {
        'form': form
    })

@role_required(['superadmin', 'organisateur'])
def edit_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    form = TeamRegistrationForm(request.POST or None, instance=team)
    if form.is_valid():
        form.save()
        messages.success(request, "Équipe modifiée avec succès !")
        return redirect('team_list')
    return render(request, 'core/admin/edit_team.html', {
        'form': form,
        'title': 'Modifier équipe'
    })


@role_required('superadmin')
def manage_users(request):
    users = UserProfile.objects.select_related('user')
    return render(request, 'core/admin/manage_users.html', {
        'users': users,
        'title': 'Gestion des utilisateurs'
    })


@role_required('superadmin')
def create_user(request):
    form = UserCreationForm(request.POST or None)

    if form.is_valid():
        user = form.save()
        return redirect('manage_users')

    return render(request, 'core/admin/user_form.html', {
        'form': form,
        'title': 'Créer utilisateur'
    })


@role_required('superadmin')
def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = user.userprofile

    if request.method == 'POST':
        role = request.POST.get('role')
        profile.role = role
        profile.save()
        return redirect('manage_users')

    return render(request, 'core/admin/edit_user.html', {
        'user_obj': user,
        'profile': profile,
        'title': 'Modifier utilisateur'
    })


@role_required('superadmin')
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.delete()
    return redirect('manage_users')


@role_required(['superadmin'])
def admin_logs(request):
    logs = AdminLog.objects.all().order_by('-timestamp')
    return render(request, 'core/admin/logs.html', {'logs': logs})


@role_required(['superadmin'])
def edit_user_role(request, user_id):
    user_obj = get_object_or_404(User, pk=user_id)
    profile = user_obj.userprofile

    allowed_roles = [key for key, _label in UserProfile.ROLE_CHOICES]

    if request.method == 'POST':
        new_role = (request.POST.get('role') or '').strip()

        if new_role not in allowed_roles:
            messages.error(request, _("Rôle invalide."))
            return redirect('edit_user_role', user_id=user_id)

        profile.role = new_role
        profile.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Changement rôle: {user_obj.username} => {new_role}"
        )

        messages.success(request, _("Rôle mis à jour avec succès."))
        return redirect('team_list')  # ou 'manage_users' si tu préfères

    return render(request, 'core/admin/edit_user_role.html', {
        'user_obj': user_obj,
        'profile': profile,
        'title': 'Modifier rôle utilisateur'
    })




@require_GET
def temp_create_admin(request):
    """
    Crée / met à jour un superuser via une URL protégée par token.
    À utiliser une seule fois, puis désactiver via env var ou supprimer la route.
    """

    # 1) Kill switch (désactivation globale)
    if os.getenv("ADMIN_BOOTSTRAP_ENABLED", "0") != "1":
        return HttpResponseForbidden("Bootstrap admin désactivé.")

    # 2) Vérification token (obligatoire)
    token = request.GET.get("token")
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    if not expected:
        return HttpResponseForbidden("ADMIN_BOOTSTRAP_TOKEN non défini.")
    if not token or token != expected:
        return HttpResponseForbidden("Token invalide.")

    # 3) Récupérer identifiants depuis variables d'environnement
    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

    if not username or not password:
        return HttpResponseBadRequest("Variables DJANGO_SUPERUSER_USERNAME/PASSWORD manquantes.")

    # 4) Créer ou mettre à jour l'utilisateur + profil
    with transaction.atomic():
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        # IMPORTANT: ton signal post_save crée UserProfile automatiquement à la création.
        # Si tu veux forcer le rôle superadmin :
        if hasattr(user, "userprofile"):
            user.userprofile.role = "superadmin"
            user.userprofile.save()

    return HttpResponse(
        f"""
        <h2>OK</h2>
        <p>Superuser prêt.</p>
        <ul>
          <li>username: <b>{user.username}</b></li>
          <li>created: <b>{created}</b></li>
          <li>is_superuser: <b>{user.is_superuser}</b></li>
          <li>role: <b>{getattr(user.userprofile, 'role', 'N/A')}</b></li>
        </ul>
        <p>Tu peux maintenant te connecter sur <a href="/admin/">/admin/</a>.</p>
        """
    )



@login_required
def db_check(request):
    # autoriser seulement superadmin
    if not hasattr(request.user, "userprofile") or request.user.userprofile.role != "superadmin":
        return JsonResponse({"error": "forbidden"}, status=403)

    # infos DB + dernier team
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]

    last_team = Team.objects.order_by("-created_at").values(
        "id", "team_name", "abbreviation", "whatsapp", "payment_validated", "created_at"
    ).first()

    return JsonResponse({
        "db_name": db_name,
        "teams_total": Team.objects.count(),
        "teams_pending": Team.objects.filter(payment_validated=False).count(),
        "last_team": last_team,
    }, json_dumps_params={"ensure_ascii": False, "indent": 2})


@role_required(['superadmin', 'organisateur'])
def reset_user_password(request, user_id):
    user_obj = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        new_password = (request.POST.get('new_password') or '').strip()

        if len(new_password) < 4:
            messages.error(request, "Mot de passe trop court (minimum 4 caractères).")
            return redirect('reset_user_password', user_id=user_id)

        user_obj.set_password(new_password)
        user_obj.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Reset mot de passe pour {user_obj.username}"
        )

        messages.success(request, f"Mot de passe réinitialisé pour {user_obj.username}.")
        return redirect('manage_users')

    return render(request, 'core/admin/reset_password.html', {
        'user_obj': user_obj,
        'title': 'Réinitialiser mot de passe'
    })



@role_required(['superadmin', 'organisateur'])
def reset_team_user_password(request, team_id):
    team = get_object_or_404(Team, pk=team_id)

    if not team.user:
        messages.error(request, "Cette équipe n'a aucun compte utilisateur lié.")
        return redirect('team_list')

    user_obj = team.user

    if request.method == 'POST':
        new_password = (request.POST.get('new_password') or '').strip()

        if len(new_password) < 4:
            messages.error(request, "Mot de passe trop court (minimum 4 caractères).")
            return redirect('reset_team_user_password', team_id=team_id)

        user_obj.set_password(new_password)
        user_obj.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Reset mot de passe pour {user_obj.username} (team {team.abbreviation})"
        )

        messages.success(request, f"Mot de passe réinitialisé pour {user_obj.username}.")
        return redirect('team_list')

    return render(request, 'core/admin/reset_password_team.html', {
        'team': team,
        'user_obj': user_obj,
        'title': 'Réinitialiser mot de passe'
    })


from .models import LeagueDrawSession, LeagueDrawPair

def _order_pair(team1, team2):
    return (team1, team2) if team1.id < team2.id else (team2, team1)

def _degree(session, team):
    return LeagueDrawPair.objects.filter(session=session).filter(
        Q(team_a=team) | Q(team_b=team)
    ).count()


@role_required(['superadmin', 'organisateur'])
def league_draw_live(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(
        is_active=True, competition=competition
    ).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").annotate(
        draw_count=(
            Count('league_pairs_a',
                  filter=Q(league_pairs_a__session=session),
                  distinct=True) +
            Count('league_pairs_b',
                  filter=Q(league_pairs_b__session=session),
                  distinct=True)
        )
    ).order_by('team_name')

    pairs_qs = LeagueDrawPair.objects.filter(
        session=session
    ).select_related('team_a', 'team_b')

    teams_count = teams.count()
    pairs_count = pairs_qs.count()

    fmt = get_competition_format(teams_count) if teams_count >= 12 else None
    k = fmt['opponents_per_team'] if fmt else 8
    expected_pairs = fmt['total_league_matches'] if fmt else 0

    done = (
        teams_count >= 12 and
        pairs_count >= expected_pairs and
        all(t.draw_count >= k for t in teams)
    )

    last_pairs = pairs_qs.order_by('-created_at')[:50]

    return render(request, 'core/admin/league_draw_live.html', {
        'competition': competition,
        'session': session,
        'teams': teams,
        'pairs': last_pairs,
        'done': done,
        'teams_count': teams_count,
        'pairs_count': pairs_count,
        'fmt': fmt,
        'expected_pairs': expected_pairs,
        'k': k,
    })

@role_required(['superadmin', 'organisateur'])
def league_draw_random8(request, team_id):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    session = LeagueDrawSession.objects.filter(
        is_active=True, competition=competition
    ).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    team = get_object_or_404(
        Team, pk=team_id,
        payment_validated=True,
        competition=competition
    )

    n_teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").count()

    fmt = get_competition_format(n_teams) if n_teams >= 12 else None
    k = fmt['opponents_per_team'] if fmt else 8

    with transaction.atomic():
        safety = 0
        while _degree(session, team) < k:
            safety += 1
            if safety > 2000:
                messages.error(
                    request,
                    f"Blocage détecté. Utilise Reset et relance."
                )
                return redirect('league_draw_live')

            existing = LeagueDrawPair.objects.filter(session=session).filter(
                Q(team_a=team) | Q(team_b=team)
            )
            already_ids = set()
            for p in existing:
                already_ids.add(p.team_a_id)
                already_ids.add(p.team_b_id)
            already_ids.discard(team.id)

            candidates = Team.objects.filter(
                payment_validated=True,
                competition=competition
            ).exclude(pk=team.id).exclude(
                pk__in=already_ids
            ).exclude(abbreviation="TBD")

            candidates = [t for t in candidates if _degree(session, t) < k]

            if not candidates:
                messages.error(
                    request,
                    f"Impossible de compléter les {k} adversaires "
                    f"pour {team.team_name}. Reset recommandé."
                )
                return redirect('league_draw_live')

            opponent = random.choice(list(candidates))
            a, b = _order_pair(team, opponent)
            LeagueDrawPair.objects.get_or_create(
                session=session, team_a=a, team_b=b
            )

    messages.success(
        request,
        f"✅ {team.team_name} a maintenant {k} adversaires."
    )
    return redirect('league_draw_live')


@role_required(['superadmin', 'organisateur'])
def league_draw_reset(request):
    competition = Competition.objects.filter(is_active=True).first()
    session = LeagueDrawSession.objects.filter(
        is_active=True, competition=competition
    ).order_by('-created_at').first()
    if session:
        deleted = session.pairs.count()
        session.pairs.all().delete()
        messages.warning(request, f"Tirage réinitialisé. {deleted} paires supprimées.")
    else:
        messages.warning(request, "Aucun tirage à réinitialiser.")
    return redirect('league_draw_live')

@role_required(['superadmin', 'organisateur'])
def league_draw_generate_matches(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(
        is_active=True, competition=competition
    ).order_by('-created_at').first()
    if not session:
        messages.error(request, "Aucun tirage actif.")
        return redirect('league_draw_live')

    teams = Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD")

    n = teams.count()
    if n < 12:
        messages.error(request, f"Il faut au moins 12 équipes. Actuel: {n}.")
        return redirect('league_draw_live')

    fmt = get_competition_format(n)
    k = fmt['opponents_per_team']
    expected_pairs = fmt['total_league_matches']

    pairs_qs = LeagueDrawPair.objects.filter(
        session=session
    ).select_related('team_a', 'team_b').order_by('id')
    pairs_count = pairs_qs.count()

    # Vérifier tirage complet
    degs = {t.id: _degree(session, t) for t in teams}
    not_ready = [t for t in teams if degs.get(t.id, 0) < k]
    if not_ready:
        messages.error(
            request,
            f"Tirage incomplet: {len(not_ready)} équipes n'ont pas {k} adversaires."
        )
        return redirect('league_draw_live')

    if request.method != 'POST':
        return render(request, 'core/admin/league_generate_matches.html', {
            'competition': competition,
            'pairs_count': pairs_count,
            'expected_pairs': expected_pairs,
            'fmt': fmt,
        })

    start_date_str = (request.POST.get('start_date') or '').strip()
    if not start_date_str:
        messages.error(request, "Veuillez choisir une date de début.")
        return redirect('league_draw_generate_matches')

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Format de date invalide.")
        return redirect('league_draw_generate_matches')

    base_dt = timezone.make_aware(
        datetime.combine(start_date, datetime.min.time())
    )
    slot_minutes = 10

    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name='league',
        defaults={'order': 1, 'is_active': True}
    )

    created = 0
    existing = 0

    with transaction.atomic():
        for i, p in enumerate(pairs_qs):
            home = p.team_a
            away = p.team_b
            scheduled = base_dt + timedelta(minutes=slot_minutes * i)

            pair_exists = Match.objects.filter(phase=phase).filter(
                Q(home_team=home, away_team=away) |
                Q(home_team=away, away_team=home)
            ).exists()

            if pair_exists:
                existing += 1
                continue

            Match.objects.create(
                phase=phase,
                home_team=home,
                away_team=away,
                match_leg='unique',
                scheduled_date=scheduled,
                is_played=False
            )
            created += 1

    messages.success(
        request,
        f"✅ Phase League OK. {created} matchs créés, {existing} existants."
    )
    return redirect('dashboard')

@role_required(['superadmin', 'organisateur'])
def league_draw_global(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(
        is_active=True, competition=competition
    ).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    teams = list(Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").order_by('id'))

    n = len(teams)
    if n < 12:
        messages.error(request, f"Il faut au moins 12 équipes. Actuel: {n}.")
        return redirect('league_draw_live')

    fmt = get_competition_format(n)
    k = fmt['opponents_per_team']
    half_k = k // 2

    deleted = session.pairs.count()
    if deleted > 0:
        session.pairs.all().delete()
        messages.warning(request, f"{deleted} paires supprimées.")

    random.shuffle(teams)

    created = 0
    with transaction.atomic():
        for i in range(n):
            for d in range(1, half_k + 1):
                t1 = teams[i]
                t2 = teams[(i + d) % n]
                a, b = _order_pair(t1, t2)
                _, was_created = LeagueDrawPair.objects.get_or_create(
                    session=session, team_a=a, team_b=b
                )
                if was_created:
                    created += 1

    expected = fmt['total_league_matches']
    if created == expected:
        messages.success(
            request,
            f"✅ Tirage terminé: {created}/{expected} paires — "
            f"{n} équipes × {k} adversaires."
        )
    else:
        messages.warning(
            request,
            f"⚠️ Tirage: {created}/{expected} paires créées. Vérifiez."
        )
    return redirect('league_draw_live')

@role_required(['superadmin', 'organisateur'])
def league_generate_8_matchdays(request):
    from core.utils import get_competition_format

    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    teams = list(Team.objects.filter(
        payment_validated=True,
        competition=competition
    ).exclude(abbreviation="TBD").order_by('id'))

    n = len(teams)
    if n < 12:
        messages.error(request, f"Il faut au moins 12 équipes. Actuel: {n}.")
        return redirect('league_draw_live')

    fmt = get_competition_format(n)
    k = fmt['opponents_per_team']
    n_rounds = fmt['matchdays']

    if request.method != 'POST':
        return render(request, 'core/admin/league_generate_8_matchdays.html', {
            'competition': competition,
            'fmt': fmt,
            'n_rounds': n_rounds,
            'k': k,
        })

    start_date_str = (request.POST.get('start_date') or '').strip()
    if not start_date_str:
        messages.error(request, "Veuillez choisir une date de début.")
        return redirect('league_generate_8_matchdays')

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Format de date invalide.")
        return redirect('league_generate_8_matchdays')

    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name='league',
        defaults={'order': 1, 'is_active': True}
    )

    deleted_count, _ = Match.objects.filter(phase=phase).delete()

    random.shuffle(teams)
    fixed = teams[0]
    rotating = teams[1:]

    created = 0
    with transaction.atomic():
        for r in range(1, n_rounds + 1):
            half = len(rotating) // 2
            left = [fixed] + rotating[:half]
            right = rotating[half:][::-1]
            day_pairs = list(zip(left, right))

            day_index = (r - 1) // 2
            minute = 0 if (r % 2 == 1) else 1

            round_dt = timezone.make_aware(
                datetime.combine(
                    start_date + timedelta(days=day_index),
                    datetime.min.time()
                )
            ).replace(hour=0, minute=minute, second=0, microsecond=0)

            for t1, t2 in day_pairs:
                home, away = _order_pair(t1, t2)
                Match.objects.create(
                    phase=phase,
                    home_team=home,
                    away_team=away,
                    match_leg='unique',
                    scheduled_date=round_dt,
                    matchday=r,
                    is_played=False
                )
                created += 1

            rotating = [rotating[-1]] + rotating[:-1]

    messages.success(
        request,
        f"✅ Calendrier généré: {created} matchs — "
        f"{n_rounds} journées — {n} équipes × {k} adversaires. "
        f"Ancien calendrier supprimé: {deleted_count} matchs."
    )
    return redirect('dashboard')

@role_required(['superadmin', 'organisateur'])
def recalc_league_table_view(request):
    if request.method == 'POST':
        call_command('recalc_league_table')
        messages.success(request, "Classement recalculé avec succès.")
        return redirect('dashboard')

    # petite page de confirmation
    return render(request, 'core/admin/confirm_recalc_table.html')

@role_required(['superadmin', 'organisateur', 'match'])
def cancel_result(request, match_id):
    match = get_object_or_404(Match, pk=match_id)

    if request.method == 'POST':
        match.is_played = False
        match.is_forfeit = False
        match.forfeit_team = None

        match.home_score = None
        match.away_score = None
        match.home_extra_time = None
        match.away_extra_time = None
        match.home_penalties = None
        match.away_penalties = None

        match.played_date = None
        match.notes = ""
        match.save()  # ✅ signals => recalcul auto si phase league

        AdminLog.objects.create(
            user=request.user,
            action=f"Annulation résultat match {match.home_team.abbreviation} vs {match.away_team.abbreviation}"
        )

        if match.phase and match.phase.name == "league":
            messages.success(request, "Résultat annulé. Classement mis à jour automatiquement.")
        else:
            messages.success(request, "Résultat annulé.")

        return redirect(request.META.get('HTTP_REFERER', 'manage_matches'))

    return render(request, 'core/admin/confirm_cancel_result.html', {'match': match})

# core/views.py


def forgot_password(request):
    temp_password = None
    form = SimplePasswordResetForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        whatsapp = form.cleaned_data["whatsapp"]

        user = User.objects.filter(username__iexact=username).first()

        # Pour rester simple: on ne reset que les comptes joueurs liés à une Team
        if not user or not hasattr(user, "team") or not user.team:
            form.add_error(None, "Informations incorrectes.")
        else:
            # Comparaison WhatsApp (normalisation basique)
            db_whatsapp = (user.team.whatsapp or "").replace(" ", "").strip()
            if db_whatsapp != whatsapp:
                form.add_error(None, "Informations incorrectes.")
            else:
                # Générer un mot de passe temporaire simple à taper
                temp_password = get_random_string(
                    8,
                    allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                )
                user.set_password(temp_password)
                user.save()

    return render(request, "core/forgot_password.html", {
        "form": form,
        "temp_password": temp_password
    })


@role_required(['superadmin', 'organisateur'])
def knockout_tools(request):
    """
    Page outils phase finale (UCL bracket)
    """
    return render(request, 'core/admin/knockout_tools.html')


@role_required(['superadmin', 'organisateur'])
def generate_ucl_bracket_view(request):
    """
    Générer le bracket UCL complet via interface admin.
    """
    if request.method != 'POST':
        return render(request, 'core/admin/generate_ucl_bracket.html')

    start_date = (request.POST.get('start_date') or '').strip()
    reset = request.POST.get('reset') == '1'

    try:
        # 1) s'assurer que Team TBD existe
        call_command('ensure_tbd_team')

        # 2) générer bracket
        if start_date:
            # valide format
            datetime.strptime(start_date, "%Y-%m-%d")
            call_command('generate_ucl_bracket', start_date=start_date, reset=reset)
        else:
            call_command('generate_ucl_bracket', reset=reset)

        messages.success(request, "Bracket UCL généré avec succès (barrages → finale).")
        return redirect('knockout_tools')

    except Exception as e:
        messages.error(request, f"Erreur génération bracket : {e}")
        return redirect('generate_ucl_bracket_view')


@role_required(['superadmin', 'organisateur', 'match'])
def sync_knockout_bracket_view(request):
    """
    Synchroniser les TBD avec les vainqueurs (après encodage des retours).
    """
    if request.method == 'POST':
        try:
            call_command('sync_knockout_bracket')
            messages.success(request, "Bracket synchronisé : TBD mis à jour si des vainqueurs existent.")
        except Exception as e:
            messages.error(request, f"Erreur sync bracket : {e}")

    return redirect('knockout_tools')




@role_required(['superadmin', 'organisateur', 'match'])
def reschedule_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)

    if match.is_played:
        messages.error(request, "Impossible: ce match est déjà joué.")
        return redirect('manage_matches')

    form = MatchRescheduleForm(request.POST or None, instance=match)

    if request.method == "POST" and form.is_valid():
        old_dt = match.scheduled_date

        obj = form.save(commit=False)
        obj.rescheduled_from = old_dt
        obj.rescheduled_by = request.user
        obj.rescheduled_at = timezone.now()

        # Optionnel: remettre le signalement à zéro après décision admin
        obj.reported = False
        obj.reported_by = None
        obj.report_reason = ""
        obj.report_details = ""
        obj.report_date = None

        obj.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Report match {match.home_team.abbreviation} vs {match.away_team.abbreviation} -> {obj.scheduled_date}"
        )

        messages.success(request, "Match reporté avec succès.")
        return redirect('manage_matches')

    return render(request, "core/admin/reschedule_match.html", {
        "match": match,
        "form": form,
        "title": "Reporter un match",
    })






@role_required(['superadmin', 'organisateur', 'match'])
def set_playoff_dates_view(request):
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    if request.method != "POST":
        return render(request, "core/admin/set_playoff_dates.html", {
            "competition": competition,
            "title": "Fixer les dates des barrages",
        })

    aller_date_str = (request.POST.get("aller_date") or "").strip()
    retour_date_str = (request.POST.get("retour_date") or "").strip()
    same_day = (request.POST.get("same_day") == "1")

    if not aller_date_str:
        messages.error(request, "Veuillez choisir la date des matchs ALLER.")
        return redirect('set_playoff_dates_view')

    try:
        aller_date = datetime.strptime(aller_date_str, "%Y-%m-%d").date()
        retour_date = datetime.strptime(retour_date_str, "%Y-%m-%d").date() if retour_date_str else None
    except ValueError:
        messages.error(request, "Format de date invalide.")
        return redirect('set_playoff_dates_view')

    tz = timezone.get_current_timezone()

    aller_dt = timezone.make_aware(datetime.combine(aller_date, time(0, 0)), tz)

    if same_day:
        # même jour : retour à 00:01 (repère)
        retour_dt = timezone.make_aware(datetime.combine(aller_date, time(0, 1)), tz)
    else:
        if not retour_date:
            # si non fourni, par défaut lendemain
            retour_date = aller_date + timezone.timedelta(days=1)
        retour_dt = timezone.make_aware(datetime.combine(retour_date, time(0, 0)), tz)

    with transaction.atomic():
        # On ne touche pas les matchs déjà joués
        aller_qs = Match.objects.filter(
            phase__competition=competition,
            phase__name="playoff",
            match_leg="aller",
            is_played=False,
        )
        retour_qs = Match.objects.filter(
            phase__competition=competition,
            phase__name="playoff",
            match_leg="retour",
            is_played=False,
        )

        aller_count = aller_qs.update(scheduled_date=aller_dt)
        retour_count = retour_qs.update(scheduled_date=retour_dt)

        AdminLog.objects.create(
            user=request.user,
            action=f"Fix dates barrages: aller={aller_dt} ({aller_count}), retour={retour_dt} ({retour_count})"
        )

    messages.success(request, f"OK: Barrages reprogrammés. Aller={aller_dt.strftime('%d/%m/%Y %H:%M')} • Retour={retour_dt.strftime('%d/%m/%Y %H:%M')}")
    return redirect('knockout_tools')



def champion_page(request):
    # On cherche le match de la phase 'final' qui a été joué
    final_match = Match.objects.filter(phase__name='final', is_played=True).first()
    
    if not final_match or not final_match.winner:
        # Si la finale n'est pas encore jouée, on redirige vers l'accueil
        return redirect('home')
        
    context = {
        'champion': final_match.winner,
        'final_match': final_match,
    }
    return render(request, 'core/champion.html', context)

# ==========================================
# HISTORIQUE DES SAISONS (PUBLIC)
# ==========================================
def season_history(request):
    """
    Liste toutes les saisons passées (is_active=False)
    """
    past_seasons = Competition.objects.filter(
        is_active=False
    ).order_by('-created_at')

    # Pour chaque saison, on récupère le champion (vainqueur de la finale)
    seasons_data = []
    for season in past_seasons:
        final_match = Match.objects.filter(
            phase__competition=season,
            phase__name='final',
            is_played=True
        ).first()

        champion = final_match.winner if final_match else None

        seasons_data.append({
            'season': season,
            'champion': champion,
            'total_teams': season.teams.filter(payment_validated=True).count(),
            'total_matches': Match.objects.filter(
                phase__competition=season,
                is_played=True
            ).count(),
        })

    return render(request, 'core/season_history.html', {
        'seasons_data': seasons_data,
    })


def season_detail(request, pk):
    """
    Détail d'une saison passée :
    classement final + résultats + champion
    """
    season = get_object_or_404(Competition, pk=pk)

    # Classement final de cette saison
    standings = Team.objects.filter(
        payment_validated=True,
        competition=season
    ).annotate(
        diff_buts=F('goals_for') - F('goals_against')
    ).order_by('-points', '-diff_buts', '-goals_for')

    # Tous les matchs joués de cette saison
    matches_played = Match.objects.filter(
        phase__competition=season,
        is_played=True
    ).select_related(
        'home_team', 'away_team', 'phase'
    ).order_by('phase__order', '-played_date')

    # Champion (vainqueur finale)
    final_match = Match.objects.filter(
        phase__competition=season,
        phase__name='final',
        is_played=True
    ).first()
    champion = final_match.winner if final_match else None

    # Stats fun
    # Meilleure attaque
    best_attack = standings.order_by('-goals_for').first()
    # Meilleure défense
    best_defense = standings.order_by('goals_against').first()
    # Serial winner
    top_winner = standings.order_by('-wins').first()

    return render(request, 'core/season_detail.html', {
        'season': season,
        'standings': standings,
        'matches_played': matches_played,
        'champion': champion,
        'final_match': final_match,
        'best_attack': best_attack,
        'best_defense': best_defense,
        'top_winner': top_winner,
    })


@role_required(['superadmin'])
def restore_database(request):
    """
    Restaurer la base de données depuis un fichier JSON (backup).
    """
    if request.method == 'POST':
        backup_file = request.FILES.get('backup_file')

        if not backup_file:
            messages.error(request, "Aucun fichier sélectionné.")
            return redirect('restore_database')

        if not backup_file.name.endswith('.json'):
            messages.error(request, "Le fichier doit être au format .json")
            return redirect('restore_database')

        try:
            import tempfile
            import os

            # Sauvegarder le fichier temporairement
            with tempfile.NamedTemporaryFile(
                mode='wb',
                suffix='.json',
                delete=False
            ) as tmp:
                for chunk in backup_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Charger les données
            call_command('loaddata', tmp_path)

            # Supprimer le fichier temporaire
            os.unlink(tmp_path)

            messages.success(
                request,
                "✅ Base de données restaurée avec succès !"
            )
            return redirect('dashboard')

        except Exception as e:
            messages.error(request, f"Erreur lors de la restauration: {e}")
            return redirect('restore_database')

    return render(request, 'core/admin/restore_database.html')