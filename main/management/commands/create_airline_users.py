from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from main.models import Aerolinky, Role, RoleUzivatel

User = get_user_model()


class Command(BaseCommand):
    help = 'Vytvoří posádku (2 piloty a 2 průvodčí) pro definované aerolinky'

    def handle(self, *args, **kwargs):
        # 1. Definice aerolinek a domén
        aerolinky_map = {
            "American Airlines": "aa.com",
            "Qantas": "qantas.com",
            "Singapore Airlines": "singaporeair.com",
            "Turkish Airlines": "turkishairlines.com",
            "KLM Royal Dutch Airlines": "klm.com",
            "Qatar Airways": "qatarairways.com",
            "Ryanair": "ryanair.com",
            "Delta Air Lines": "delta.com",
            "Air France": "airfrance.com",
            "Lufthansa": "lufthansa.com",
            "Smartwings": "wings.cz",
            "České aerolinie": "csa.cz",
        }

        # 2. Načtení rolí a skupin
        try:
            role_pilot = Role.objects.get(nazev_role="Pilot")
            role_pruvodci = Role.objects.get(nazev_role="Palubní průvodčí")
            grp_posadka, _ = Group.objects.get_or_create(name="Posadka")
            grp_uzivatel, _ = Group.objects.get_or_create(name="Přihlášený uživatel")
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("Chyba: Role 'Pilot' nebo 'Palubní průvodčí' neexistují. Spusťte nejprve setup_data."))
            return

        password = "vdcapp123"

        # 3. Smyčka přes aerolinky
        for nazev_aerolinky, domena in aerolinky_map.items():

            # Zkusíme najít aerolinku (musí už existovat z předchozích kroků)
            try:
                aerolinka = Aerolinky.objects.get(nazev=nazev_aerolinky)
            except Aerolinky.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Aerolinka '{nazev_aerolinky}' nenalezena. Přeskakuji."))
                continue

            self.stdout.write(f"Zpracovávám: {nazev_aerolinky}...")

            # Definice uživatelů pro tuto aerolinku
            users_config = [
                ("pilot1", role_pilot),
                ("pilot2", role_pilot),
                ("pruvodci1", role_pruvodci),
                ("pruvodci2", role_pruvodci),
            ]

            for prefix, role_obj in users_config:
                email = f"{prefix}@{domena}"

                # Vytvoření uživatele (jména necháváme prázdná)
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': "",  # Ponecháme prázdné
                        'last_name': "",  # Ponecháme prázdné
                        'id_aerolinky': aerolinka,
                        'is_active': True,
                        'is_staff': False  # Nemají přístup do adminu
                    }
                )

                if created:
                    user.set_password(password)
                    user.save()

                    # Přiřazení skupin
                    user.groups.add(grp_posadka)
                    user.groups.add(grp_uzivatel)

                    # Přiřazení Role (platnost navždy)
                    RoleUzivatel.objects.get_or_create(
                        id_uzivatele=user,
                        id_role=role_obj
                    )
                    self.stdout.write(f"  + Vytvořen: {email}")
                else:
                    self.stdout.write(f"  . Již existuje: {email}")

        self.stdout.write(self.style.SUCCESS('Hotovo! Všichni uživatelé byli zpracováni.'))

