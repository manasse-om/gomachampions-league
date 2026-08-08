from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Team, Match, Competition
import re


# ==========================================
# FORMULAIRE : INSCRIPTION / MODIFICATION ÉQUIPE
# ==========================================
class TeamRegistrationForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=4,
        required=False,  # obligatoire seulement à la création (voir clean)
        label=_('Mot de passe')
    )

    class Meta:
        model = Team
        fields = ['player_name', 'team_name', 'abbreviation', 'whatsapp']

        widgets = {
            'player_name': forms.TextInput(attrs={'class': 'form-control'}),
            'team_name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '5',
                'style': 'text-transform: uppercase;',
            }),
            'whatsapp': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+243999999999',
            }),
        }

    def __init__(self, *args, **kwargs):
        # ✅ CORRIGÉ: on reçoit la compétition active depuis la vue
        self.competition = kwargs.pop('competition', None)
        super().__init__(*args, **kwargs)

    def clean_abbreviation(self):
        abbr = (self.cleaned_data.get('abbreviation') or '').upper().strip()

        if not abbr:
            raise ValidationError(_("Abréviation obligatoire."))

        if len(abbr) < 2 or len(abbr) > 5:
            raise ValidationError(_("Abréviation: 2 à 5 caractères."))

        if not abbr.isalnum():
            raise ValidationError(_("Abréviation: lettres et chiffres seulement (pas d'espaces)."))

        # ✅ CORRIGÉ: vérifier uniquement dans la compétition active
        # (même abréviation autorisée dans une autre saison)
        qs = Team.objects.filter(abbreviation=abbr)
        if self.competition:
            qs = qs.filter(competition=self.competition)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(_(
                "Cette abréviation est déjà utilisée dans cette compétition."
            ))

        return abbr

    def clean_whatsapp(self):
        whatsapp = (self.cleaned_data.get('whatsapp') or '').replace(" ", "").strip()

        if not whatsapp:
            raise ValidationError(_("Numéro WhatsApp obligatoire."))

        if not re.match(r'^\+?\d{9,15}$', whatsapp):
            raise ValidationError(_("WhatsApp invalide. Exemple: +243999999999"))

        # ✅ CORRIGÉ: vérifier uniquement dans la compétition active
        # (même numéro autorisé pour une nouvelle saison)
        qs = Team.objects.filter(whatsapp=whatsapp)
        if self.competition:
            qs = qs.filter(competition=self.competition)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(_(
                "Ce numéro WhatsApp est déjà enregistré pour cette compétition."
            ))

        return whatsapp

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')

        # À la création uniquement: password obligatoire
        if not self.instance.pk and not password:
            raise ValidationError(_("Le mot de passe est obligatoire."))

        return cleaned_data

    def save(self, commit=True):
        team = super().save(commit=False)
        password = self.cleaned_data.get('password')

        # Si modification: si password fourni, on change le password du user lié
        if password and team.user:
            team.user.set_password(password)
            team.user.save()

        if commit:
            team.save()

        return team


# ==========================================
# FORMULAIRE : RÉSULTAT D'UN MATCH
# ==========================================
class MatchResultForm(forms.ModelForm):

    class Meta:
        model = Match
        fields = [
            'home_score', 'away_score',
            'home_extra_time', 'away_extra_time',
            'home_penalties', 'away_penalties',
            'is_forfeit', 'forfeit_team',
            'notes'
        ]

        widgets = {
            'home_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'home_extra_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_extra_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'home_penalties': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_penalties': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_forfeit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'forfeit_team': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_forfeit = cleaned_data.get('is_forfeit')
        home_score = cleaned_data.get('home_score')
        away_score = cleaned_data.get('away_score')
        home_pen = cleaned_data.get('home_penalties')
        away_pen = cleaned_data.get('away_penalties')

        if is_forfeit:
            return cleaned_data

        if home_score is None or away_score is None:
            raise ValidationError(_('Veuillez entrer les scores des deux équipes.'))

        if home_pen is not None and away_pen is not None:
            if home_pen == away_pen:
                raise ValidationError(_('Les tirs au but ne peuvent pas être égaux.'))

        return cleaned_data


# ==========================================
# FORMULAIRE : COMPÉTITION
# ==========================================
class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = [
            'name',
            'format_type',
            'max_teams',
            'registration_fee',
            'is_active',
            'registration_open',
            'start_date',
            'end_date'
        ]


class SimplePasswordResetForm(forms.Form):
    username = forms.CharField(
        label=_("Nom d'utilisateur (abréviation)"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: gom"})
    )
    whatsapp = forms.CharField(
        label=_("Numéro WhatsApp"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+243999999999"})
    )

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip().lower()

    def clean_whatsapp(self):
        w = (self.cleaned_data.get("whatsapp") or "").replace(" ", "").strip()
        if not re.match(r'^\+?\d{9,15}$', w):
            raise forms.ValidationError(_("WhatsApp invalide. Exemple: +243999999999"))
        return w


class MatchRescheduleForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["scheduled_date", "rescheduled_reason"]
        widgets = {
            "scheduled_date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "rescheduled_reason": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: problème réseau / coupure courant / accord des 2 joueurs..."
            }),
        }

    def clean_scheduled_date(self):
        dt = self.cleaned_data["scheduled_date"]
        if not dt:
            raise forms.ValidationError(_("Date obligatoire."))
        return dt