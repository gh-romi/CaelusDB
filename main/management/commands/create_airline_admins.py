from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from main.models import Aerolinky, Role, RoleUzivatel

User = get_user_model()


class Command(BaseCommand):
    help = 'Vytvoří administrátory (admin1) pro definované aerolinky'

    def handle(self, *args, **kwargs):
        # 1. Definice aerolinek a domén (stejná mapa jako minule)
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
            # Role
            role_zakaznik = Role.objects.get(nazev_role="Zákazník")
            role_admin_aero = Role.objects.get(nazev_role="Admin aerolinky")

            # Skupiny (vytvoříme je, pokud neexistují)
            grp_uzivatel, _ = Group.objects.get_or_create(name="Přihlášený uživatel")
            grp_admin_aero, _ = Group.objects.get_or_create(name="Admin aerolinky")

        except Role.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"Chyba: Role neexistuje. {e}. Spusťte nejprve setup_data."))
            return

        password = "vdcapp123"

        # 3. Smyčka přes aerolinky
        for nazev_aerolinky, domena in aerolinky_map.items():

            # Najdeme aerolinku
            try:
                aerolinka = Aerolinky.objects.get(nazev=nazev_aerolinky)
            except Aerolinky.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Aerolinka '{nazev_aerolinky}' nenalezena. Přeskakuji."))
                continue

            self.stdout.write(f"Zpracovávám Admina pro: {nazev_aerolinky}...")

            # Definice uživatele
            email = f"admin1@{domena}"

            # Vytvoření uživatele
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': "Admin",
                    'last_name': nazev_aerolinky,
                    'id_aerolinky': aerolinka,
                    'is_active': True,
                    # is_staff=True nastavovat nemusíme,
                    # o to se postará náš signál v signals.py při prvním přihlášení
                }
            )

            if created:
                user.set_password(password)
                user.save()

                # A) Přiřazení skupin
                user.groups.add(grp_uzivatel)
                user.groups.add(grp_admin_aero)

                # B) Přiřazení Rolí (platnost navždy)
                # Role: Zákazník
                RoleUzivatel.objects.get_or_create(
                    id_uzivatele=user,
                    id_role=role_zakaznik
                )
                # Role: Admin aerolinky
                RoleUzivatel.objects.get_or_create(
                    id_uzivatele=user,
                    id_role=role_admin_aero
                )

                self.stdout.write(f"  + Vytvořen: {email}")
            else:
                self.stdout.write(f"  . Již existuje: {email}")

        self.stdout.write(self.style.SUCCESS('Hotovo! Administrátoři aerolinek byli vytvořeni.'))