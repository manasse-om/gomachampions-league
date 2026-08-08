import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'goma_cl.settings')
django.setup()

from django.utils import timezone
from datetime import date
from core.models import Competition, Team
from django.contrib.auth.models import User

# DÉSACTIVER LES ANCIENNES
Competition.objects.filter(is_active=True).update(is_active=False, registration_open=False)

# CRÉER LA COMPÉTITION
competition = Competition.objects.create(
    name="Goma Champions League 2026",
    format_type="ucl",
    max_teams=36,
    is_active=True,
    registration_open=False,
    registration_fee=2500,
    start_date=date(2026, 3, 1),
    end_date=date(2026, 7, 31),
)
print(f"Compétition créée: {competition.name} (id={competition.id})")

teams_data = [
    {"player": "Manassé Ombeni",     "team": "Real Goma FC",       "abbr": "RGF", "wa": "+243970000001"},
    {"player": "Job Badesire",       "team": "Volcano United",     "abbr": "VOU", "wa": "+243970000002"},
    {"player": "Héritier DJO",       "team": "Kivu Stars",         "abbr": "KVS", "wa": "+243970000003"},
    {"player": "Joachim Paluku",     "team": "Congo Warriors",     "abbr": "CGW", "wa": "+243970000004"},
    {"player": "Ildephonse Nyota",   "team": "Lake City FC",       "abbr": "LCF", "wa": "+243970000005"},
    {"player": "Patient Kiza",       "team": "Nyiragongo Boys",    "abbr": "NYB", "wa": "+243970000006"},
    {"player": "Gloire Furaha",      "team": "Lava Kings",         "abbr": "LVK", "wa": "+243970000007"},
    {"player": "Amani Bahati",       "team": "Goma Eagles",        "abbr": "GME", "wa": "+243970000008"},
    {"player": "Espoir Maisha",      "team": "Rutshuru FC",        "abbr": "RTF", "wa": "+243970000009"},
    {"player": "Fidèle Ndakala",     "team": "Masisi United",      "abbr": "MSU", "wa": "+243970000010"},
    {"player": "Bienfait Kasereka",  "team": "Walikale City",      "abbr": "WLC", "wa": "+243970000011"},
    {"player": "Josué Mapendo",      "team": "Butembo Tigers",     "abbr": "BTT", "wa": "+243970000012"},
    {"player": "Serge Matumaini",    "team": "Beni Lions",         "abbr": "BNL", "wa": "+243970000013"},
    {"player": "Grâce Kyaviro",      "team": "Lubero Rangers",     "abbr": "LBR", "wa": "+243970000014"},
    {"player": "Divin Amani",        "team": "Kasindi Port FC",    "abbr": "KPF", "wa": "+243970000015"},
    {"player": "Noël Bulonza",       "team": "Ishasha FC",         "abbr": "ISH", "wa": "+243970000016"},
    {"player": "Didier Mutombo",     "team": "Sake Warriors",      "abbr": "SKW", "wa": "+243970000017"},
    {"player": "Théodore Kambale",   "team": "Minova Stars",       "abbr": "MNS", "wa": "+243970000018"},
    {"player": "Arsène Kilosho",     "team": "Kalehe United",      "abbr": "KLU", "wa": "+243970000019"},
    {"player": "Christian Bahane",   "team": "Shabunda FC",        "abbr": "SHB", "wa": "+243970000020"},
    {"player": "Joël Ndoole",        "team": "Uvira City",         "abbr": "UVC", "wa": "+243970000021"},
    {"player": "Merci Nzigire",      "team": "Fizi Boys",          "abbr": "FZB", "wa": "+243970000022"},
    {"player": "David Muhindo",      "team": "Baraka United",      "abbr": "BRU", "wa": "+243970000023"},
    {"player": "Samuel Kasereka",    "team": "Mwenga Rangers",     "abbr": "MWR", "wa": "+243970000024"},
    {"player": "Exaucé Paluku",      "team": "Idjwi FC",           "abbr": "IDJ", "wa": "+243970000025"},
    {"player": "Parfait Nzanzu",     "team": "Virunga Boys",       "abbr": "VRB", "wa": "+243970000026"},
    {"player": "Jonathan Siviri",    "team": "Karisimbi United",   "abbr": "KRU", "wa": "+243970000027"},
    {"player": "Dieudonne Mateso",   "team": "Mikeno FC",          "abbr": "MKF", "wa": "+243970000028"},
    {"player": "Richard Kabuya",     "team": "Nyamasheke Stars",   "abbr": "NMS", "wa": "+243970000029"},
    {"player": "Freddy Mahamba",     "team": "Gisenyi United",     "abbr": "GSU", "wa": "+243970000030"},
    {"player": "Prince Nkuba",       "team": "Rubavu City FC",     "abbr": "RBC", "wa": "+243970000031"},
    {"player": "Willy Balagizi",     "team": "Musanze Eagles",     "abbr": "MSE", "wa": "+243970000032"},
    {"player": "Cédric Mugisha",     "team": "Kinigi Rangers",     "abbr": "KNR", "wa": "+243970000033"},
    {"player": "Dorcas Habimana",    "team": "Mulindi FC",         "abbr": "MLD", "wa": "+243970000034"},
    {"player": "Lionel Nshimiyimana","team": "Rushaki United",     "abbr": "RSU", "wa": "+243970000035"},
    {"player": "Arsène Tuyishime",   "team": "Gicumbi City FC",    "abbr": "GCF", "wa": "+243970000036"},
]

created = 0
for t in teams_data:
    username = t["abbr"].lower()
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"first_name": t["player"], "email": f"{username}@gomacl.local"}
    )
    user.set_password("gomacl2026")
    user.save()
    if hasattr(user, "userprofile"):
        user.userprofile.role = "player"
        user.userprofile.save()
    team, ok = Team.objects.get_or_create(
        abbreviation=t["abbr"],
        competition=competition,
        defaults={
            "user": user,
            "player_name": t["player"],
            "team_name": t["team"],
            "whatsapp": t["wa"],
            "payment_validated": True,
        }
    )
    if ok:
        created += 1
        print(f"OK: {t['abbr']} - {t['team']}")
    else:
        print(f"EXISTE: {t['abbr']}")

print(f"\nTERMINE!")
print(f"Equipes creees: {created}/36")
print(f"Equipes validees: {competition.registered_teams_count}")
print(f"Mot de passe: gomacl2026")
print(f"Username = abréviation minuscules (ex: rgf, vou...)")