#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# ✅ Création automatique du superuser
python manage.py shell << END
from django.contrib.auth.models import User

username = "Ombenation"
email = "ombenation16@gmail.com"
password = "OMBENI2025"

if not User.objects.filter(username=username).exists():
    print("Creating superuser...")
    User.objects.create_superuser(username, email, password)
else:
    print("Superuser already exists.")
END