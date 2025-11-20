from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
# Importujeme přímo třídu RoleUzivatel
from .models import RoleUzivatel

# Seznam rolí, které opravňují ke vstupu do Adminu
# (Pilot a Průvodčí zde záměrně chybí - ti do adminu nesmí)
ZAMESTNANECKE_ROLE = [
    "Admin aerolinky",
    "Správce tříd sedadel",
    "Správce letadel",
    "Správce letišť",
    "Správce letů"
]


@receiver(user_logged_in)
def aktualizuj_pristup_do_adminu(sender, user, request, **kwargs):
    """
    Tato funkce se spustí při každém přihlášení uživatele.
    Zkontroluje, zda má platnou zaměstnaneckou roli, a podle toho
    mu přidělí nebo odebere přístup do adminu (is_staff).
    """

    # 1. POJISTKA PRO SUPERADMINA
    # Pokud je to superuser, nic nekontrolujeme a necháme mu práva.
    if user.is_superuser:
        return

    # 2. KONTROLA ROLÍ
    # Používáme přímo 'RoleUzivatel' (ne 'models.RoleUzivatel')
    ma_platnou_roli = (RoleUzivatel.objects.filter(
        id_uzivatele=user,
        id_role__nazev_role__in=ZAMESTNANECKE_ROLE,
        plati_do__gte=timezone.now()
    ).exists() | RoleUzivatel.objects.filter(
        id_uzivatele=user,
        id_role__nazev_role__in=ZAMESTNANECKE_ROLE,
        plati_do__isnull=True
    ).exists())

    # 3. PŘIDĚLENÍ / ODEBRÁNÍ PRÁV
    if ma_platnou_roli:
        # Má roli -> měl by mít admin
        if not user.is_staff:
            user.is_staff = True
            user.save()
            print(f"Uživatel {user.email} získal přístup do adminu (má platnou roli).")
    else:
        # Nemá roli -> neměl by mít admin
        if user.is_staff:
            user.is_staff = False
            user.save()
            print(f"Uživatel {user.email} ztratil přístup do adminu (nemá platnou roli).")

