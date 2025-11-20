import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CaelusDB_project.settings")
django.setup()

User = get_user_model()

# Načteme údaje z proměnných prostředí (které nastavíme na Renderu)
DJANGO_SUPERUSER_EMAIL = os.environ.get('DJANGO_SUPERUSER_EMAIL')
DJANGO_SUPERUSER_PASSWORD = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD:
    if not User.objects.filter(email=DJANGO_SUPERUSER_EMAIL).exists():
        print(f"Vytvářím superuživatele {DJANGO_SUPERUSER_EMAIL}...")
        User.objects.create_superuser(email=DJANGO_SUPERUSER_EMAIL, password=DJANGO_SUPERUSER_PASSWORD)
        print("Superuživatel byl úspěšně vytvořen!")
    else:
        print("Superuživatel již existuje.")
else:
    print("Chybí proměnné prostředí pro vytvoření superuživatele. Přeskakuji.")
