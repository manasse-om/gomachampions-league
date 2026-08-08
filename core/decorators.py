# core/decorators.py
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def role_required(allowed_roles):
    """
    Décorateur pour restreindre l'accès selon le rôle dans UserProfile.
    allowed_roles = liste ou string (ex: ['superadmin', 'organisateur'] ou 'superadmin')
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # 1) Auth
            if not request.user.is_authenticated:
                messages.warning(request, "Veuillez vous connecter pour continuer.")
                return redirect('login')

            # 2) Profil
            if not hasattr(request.user, 'userprofile'):
                messages.error(request, "Accès refusé : aucun profil utilisateur associé.")
                return redirect('home')

            # 3) Rôle
            if request.user.userprofile.role not in allowed_roles:
                messages.error(request, "Accès refusé : vous n'avez pas les droits nécessaires.")
                return redirect('dashboard')  # ou 'home' si tu préfères

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator