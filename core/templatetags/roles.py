from django import template

register = template.Library()

@register.filter
def has_role(user, roles_csv: str):
    if not getattr(user, "is_authenticated", False):
        return False

    profile = getattr(user, "userprofile", None)
    if not profile:
        return False

    roles = [r.strip() for r in roles_csv.split(",") if r.strip()]
    return profile.role in roles