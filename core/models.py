from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver


# ==========================================
# MODÈLE : COMPÉTITION
# ==========================================
class Competition(models.Model):
    """
    Représente une compétition (ex: Goma Champions League 2026)
    """
    FORMAT_CHOICES = [
        ('ucl', _('Format UEFA Champions League')),
        ('group', _('Groupes + Élimination directe')),
    ]

    name = models.CharField(max_length=200, verbose_name=_("Nom de la compétition"))
    format_type = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='ucl', verbose_name=_("Format"))
    max_teams = models.IntegerField(default=36, verbose_name=_("Nombre max d'équipes"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    registration_open = models.BooleanField(default=True, verbose_name=_("Inscriptions ouvertes"))
    registration_fee = models.IntegerField(default=1000, verbose_name=_("Frais d'inscription (CDF)"))

    # Dates
    start_date = models.DateField(verbose_name=_("Date de début"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("Date de fin"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Compétition")
        verbose_name_plural = _("Compétitions")
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def registered_teams_count(self):
        return self.teams.filter(payment_validated=True).count()

    @property
    def pending_teams_count(self):
        return self.teams.filter(payment_validated=False).count()

    @property
    def is_registration_full(self):
        return self.registered_teams_count >= self.max_teams

    @property
    def total_collected(self):
        return self.registered_teams_count * self.registration_fee


# ==========================================
# MODÈLE : ÉQUIPE/JOUEUR
# ==========================================
class Team(models.Model):
    """
    Représente un joueur inscrit (= une équipe)
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Utilisateur"))

    # Relation avec la compétition
    competition = models.ForeignKey(
        Competition, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='teams',
        verbose_name=_("Compétition")
    )

    # Informations du joueur
    player_name = models.CharField(max_length=100, verbose_name=_("Nom du joueur"))
    team_name = models.CharField(max_length=100, verbose_name=_("Nom de votre équipe"))

    # ✅ CORRIGÉ: suppression de unique=True (géré par UniqueConstraint ci-dessous)
    abbreviation = models.CharField(max_length=5, verbose_name=_("Abréviation"))

    # Numéro WhatsApp
    phone_regex = RegexValidator(regex=r'^\+?\d{9,15}$', message=_("Format: '+243999999999'"))
    # ✅ CORRIGÉ: suppression de unique=True sur whatsapp (géré par UniqueConstraint)
    whatsapp = models.CharField(validators=[phone_regex], max_length=17, verbose_name=_("WhatsApp"))

    # Paiement (validation manuelle via WhatsApp)
    payment_validated = models.BooleanField(default=False, verbose_name=_("Paiement validé"))
    payment_validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_payments',
        verbose_name=_("Validé par")
    )
    payment_validated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date de validation"))

    # Statistiques
    played = models.IntegerField(default=0, verbose_name=_("Matchs joués"))
    wins = models.IntegerField(default=0, verbose_name=_("Victoires"))
    draws = models.IntegerField(default=0, verbose_name=_("Nuls"))
    losses = models.IntegerField(default=0, verbose_name=_("Défaites"))
    goals_for = models.IntegerField(default=0, verbose_name=_("Buts marqués"))
    goals_against = models.IntegerField(default=0, verbose_name=_("Buts encaissés"))
    points = models.IntegerField(default=0, verbose_name=_("Points"))

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Équipe")
        verbose_name_plural = _("Équipes")
        ordering = ['-points', '-goals_for']

        # ✅ CORRIGÉ: unicité par compétition (pas globale)
        # Même abréviation / même WhatsApp autorisés dans 2 saisons différentes
        constraints = [
            models.UniqueConstraint(
                fields=['abbreviation', 'competition'],
                name='unique_abbreviation_per_competition'
            ),
            models.UniqueConstraint(
                fields=['whatsapp', 'competition'],
                name='unique_whatsapp_per_competition'
            ),
        ]

    def __str__(self):
        return f"{self.team_name} ({self.abbreviation})"

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against


# ==========================================
# MODÈLE : PHASE
# ==========================================
class Phase(models.Model):
    """
    Représente une phase de la compétition
    """
    PHASE_CHOICES = [
        ('league', _('Phase de ligue')),
        ('playoff', _('Barrages')),
        ('round_16', _('8e de finale')),
        ('quarter', _('Quart de finale')),
        ('semi', _('Demi-finale')),
        ('final', _('Finale')),
    ]

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='phases', verbose_name=_("Compétition"))
    name = models.CharField(max_length=50, choices=PHASE_CHOICES, verbose_name=_("Phase"))
    order = models.IntegerField(default=0, verbose_name=_("Ordre"))
    is_active = models.BooleanField(default=False, verbose_name=_("Phase active"))

    class Meta:
        verbose_name = _("Phase")
        verbose_name_plural = _("Phases")
        ordering = ['order']

    def __str__(self):
        return f"{self.competition.name} - {self.get_name_display()}"


# ==========================================
# MODÈLE : MATCH
# ==========================================
class Match(models.Model):
    """
    Représente un match entre deux équipes
    """
    LEG_CHOICES = [
        ('unique', _('Match unique')),
        ('aller', _('Match aller')),
        ('retour', _('Match retour')),
    ]

    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name='matches', verbose_name=_("Phase"))
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches', verbose_name=_("Équipe domicile"))
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches', verbose_name=_("Équipe extérieur"))

    match_leg = models.CharField(max_length=10, choices=LEG_CHOICES, default='unique', verbose_name=_("Type de match"))

    first_leg = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='second_leg_match',
        verbose_name=_("Match aller")
    )

    source_home_match = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='advances_to_home',
        verbose_name=_("Source équipe domicile (vainqueur de)")
    )
    source_away_match = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='advances_to_away',
        verbose_name=_("Source équipe extérieur (vainqueur de)")
    )

    home_score = models.IntegerField(null=True, blank=True, verbose_name=_("Score domicile"))
    away_score = models.IntegerField(null=True, blank=True, verbose_name=_("Score extérieur"))
    home_extra_time = models.IntegerField(null=True, blank=True, verbose_name=_("Buts domicile (prolongation)"))
    away_extra_time = models.IntegerField(null=True, blank=True, verbose_name=_("Buts extérieur (prolongation)"))
    home_penalties = models.IntegerField(null=True, blank=True, verbose_name=_("Tirs au but domicile"))
    away_penalties = models.IntegerField(null=True, blank=True, verbose_name=_("Tirs au but extérieur"))

    is_played = models.BooleanField(default=False, verbose_name=_("Match joué"))
    is_forfeit = models.BooleanField(default=False, verbose_name=_("Forfait"))
    forfeit_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='forfeits',
        verbose_name=_("Équipe forfait")
    )

    scheduled_date = models.DateTimeField(verbose_name=_("Date prévue"))
    matchday = models.PositiveIntegerField(default=1, verbose_name=_("Journée"))
    played_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Date jouée"))

    rescheduled_from = models.DateTimeField(null=True, blank=True, verbose_name=_("Ancienne date"))
    rescheduled_reason = models.CharField(max_length=200, blank=True, verbose_name=_("Raison du report"))
    rescheduled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="rescheduled_matches",
        verbose_name=_("Reporté par")
    )
    rescheduled_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date du report"))

    screenshot = models.ImageField(upload_to='match_screenshots/', null=True, blank=True, verbose_name=_("Capture d'écran"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    reported = models.BooleanField(default=False, verbose_name=_("Signalé"))
    reported_by = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reports',
        verbose_name=_("Signalé par")
    )
    report_reason = models.CharField(max_length=200, blank=True, verbose_name=_("Raison"))
    report_details = models.TextField(blank=True, verbose_name=_("Détails du signalement"))
    report_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Date du signalement"))

    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matchs")
        ordering = ['scheduled_date']

    def __str__(self):
        leg_display = f" ({self.get_match_leg_display()})" if self.match_leg != 'unique' else ""
        return f"{self.home_team.abbreviation} vs {self.away_team.abbreviation}{leg_display}"

    @property
    def result(self):
        if not self.is_played:
            return "-"
        if self.is_forfeit:
            return _("Forfait")
        result = f"{self.home_score} - {self.away_score}"
        if self.home_extra_time is not None or self.away_extra_time is not None:
            result += f" (ap: {self.home_extra_time or 0} - {self.away_extra_time or 0})"
        if self.home_penalties is not None or self.away_penalties is not None:
            result += f" (tab: {self.home_penalties} - {self.away_penalties})"
        return result

    @property
    def is_late(self):
        if self.is_played:
            return False
        deadline = timezone.now() - timedelta(hours=48)
        return self.scheduled_date < deadline

    @property
    def aggregate_score(self):
        if self.match_leg != 'retour' or not self.first_leg:
            return None
        if not self.is_played or not self.first_leg.is_played:
            return None
        totals = {}
        totals[self.first_leg.home_team_id] = totals.get(self.first_leg.home_team_id, 0) + (self.first_leg.home_score or 0)
        totals[self.first_leg.away_team_id] = totals.get(self.first_leg.away_team_id, 0) + (self.first_leg.away_score or 0)
        totals[self.home_team_id] = totals.get(self.home_team_id, 0) + (self.home_score or 0) + (self.home_extra_time or 0)
        totals[self.away_team_id] = totals.get(self.away_team_id, 0) + (self.away_score or 0) + (self.away_extra_time or 0)
        return {
            "home": totals.get(self.home_team_id, 0),
            "away": totals.get(self.away_team_id, 0),
        }

    @property
    def winner(self):
        if not self.is_played:
            return None
        if self.is_forfeit:
            return self.away_team if self.forfeit_team == self.home_team else self.home_team
        if self.match_leg == 'retour' and self.first_leg:
            agg = self.aggregate_score
            if not agg:
                return None
            if agg['home'] > agg['away']:
                return self.home_team
            elif agg['away'] > agg['home']:
                return self.away_team
            else:
                if self.home_penalties is not None and self.away_penalties is not None:
                    if self.home_penalties > self.away_penalties:
                        return self.home_team
                    elif self.away_penalties > self.home_penalties:
                        return self.away_team
                return None
        home_total = (self.home_score or 0) + (self.home_extra_time or 0)
        away_total = (self.away_score or 0) + (self.away_extra_time or 0)
        if home_total > away_total:
            return self.home_team
        elif away_total > home_total:
            return self.away_team
        else:
            if self.home_penalties is not None and self.away_penalties is not None:
                if self.home_penalties > self.away_penalties:
                    return self.home_team
                elif self.away_penalties > self.home_penalties:
                    return self.away_team
            return None


# ==========================================
# MODÈLE : GROUPE (pour format groupes)
# ==========================================
class Group(models.Model):
    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE,
        related_name='groups',
        verbose_name=_("Compétition")
    )
    name = models.CharField(max_length=50, verbose_name=_("Nom du groupe"))
    teams = models.ManyToManyField(Team, related_name='groups', verbose_name=_("Équipes"))

    class Meta:
        verbose_name = _("Groupe")
        verbose_name_plural = _("Groupes")
        ordering = ['name']

    def __str__(self):
        return f"{self.competition.name} - {self.name}"


# ==========================================
# MODÈLE : ACTUALITÉ
# ==========================================
class News(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    content = models.TextField(verbose_name=_("Contenu"))
    image = models.ImageField(upload_to='news/', null=True, blank=True, verbose_name=_("Image"))
    is_published = models.BooleanField(default=True, verbose_name=_("Publié"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Actualité")
        verbose_name_plural = _("Actualités")
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ==========================================
# PROFIL UTILISATEUR (RÔLES)
# ==========================================
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('player', 'Joueur'),
        ('superadmin', 'Super Admin'),
        ('organisateur', 'Organisateur'),
        ('paiement', 'Modérateur Paiements'),
        ('match', 'Gestionnaire Matchs'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='player')

    def __str__(self):
        return f"{self.user.username} - {self.role}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = "superadmin" if instance.is_superuser else "player"
        UserProfile.objects.create(user=instance, role=role)


# ==========================================
# LOGS ADMIN
# ==========================================
class AdminLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action}"


# ==========================================
# TIRAGE PHASE LIGUE
# ==========================================
class LeagueDrawSession(models.Model):
    name = models.CharField(max_length=120, default="Tirage Ligue")
    competition = models.ForeignKey('Competition', on_delete=models.CASCADE, related_name='league_draw_sessions')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.competition.name}"


class LeagueDrawPair(models.Model):
    session = models.ForeignKey(LeagueDrawSession, on_delete=models.CASCADE, related_name='pairs')
    team_a = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='league_pairs_a')
    team_b = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='league_pairs_b')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['session', 'team_a', 'team_b'], name='unique_league_pair_per_session')
        ]

    def __str__(self):
        return f"{self.team_a.abbreviation} vs {self.team_b.abbreviation}"