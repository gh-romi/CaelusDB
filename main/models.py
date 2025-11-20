from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db.models import Sum

# PK je vzdy vytvoren automaticky pro kazdou tabulku


# --- NEZÁVISLÉ TABULKY (ČÍSELNÍKY) ---

class Role(models.Model):
    nazev_role = models.CharField(max_length=100)  # text

    def __str__(self):
        return self.nazev_role


class Aerolinky(models.Model):
    nazev = models.CharField(max_length=255)  # text
    kod_iata = models.CharField(max_length=3, unique=True)  # text
    zeme_registrace = models.CharField(max_length=100, blank=True, null=True)  # text

    def __str__(self):
        return self.nazev


class Letiste(models.Model):
    nazev_letiste = models.CharField(max_length=255)  # text
    kod_iata = models.CharField(max_length=3, unique=True)  # text
    mesto = models.CharField(max_length=100)  # text
    zeme = models.CharField(max_length=100)  # text

    def __str__(self):
        return f"{self.nazev_letiste} ({self.kod_iata})"


# --- ZÁVISLÉ TABULKY (ÚROVEŇ 1) ---


class TridySedadel(models.Model):
    nazev_tridy = models.CharField(max_length=100)  # text
    popis = models.TextField(blank=True, null=True)  # text

    # FK - VAZBA 1:N (Jedna aerolinka může mít více tříd)
    id_aerolinky = models.ForeignKey(
        Aerolinky,
        on_delete=models.CASCADE,  # Pokud smažu aerolinku, smažou se i její třídy
        null=True,  # Povoluje NULL pro globální třídy
        blank=True
    )

    def __str__(self):
        return self.nazev_tridy


class Letadla(models.Model):
    model = models.CharField(max_length=100)  # text
    kapacita_sedadel = models.PositiveIntegerField()  # int
    datum_vyroby = models.DateField()  # time

    # FK (VAZBA 1:N)
    id_aerolinky = models.ForeignKey(
        Aerolinky,
        on_delete=models.PROTECT,  # Zabraňuje smazání aerolinky, pokud má přiřazená letadla
        related_name="letadla"  # umožňuje definovat název pro zpětný dotaz
    )

    def __str__(self):
        return f"{self.model} ({self.id})"


# Tento správce ví, jak vytvářet uživatele pomocí e-mailu
class CustomUserManager(BaseUserManager):
    """
    Vlastní správce modelu uživatele, kde je e-mail unikátním
    identifikátorem pro autentizaci namísto uživatelského jména.
    """

    def _create_user(self, email, password, **extra_fields):
        """
        Vytvoří a uloží uživatele se zadaným e-mailem a heslem.
        """
        if not email:
            raise ValueError('Email musí být nastaven')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # set_password se postará o hashování
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Vytvoří a uloží superuživatele se zadaným e-mailem a heslem.
        Toto je metoda, která selhala v chybové hlášce.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuživatel musí mít is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuživatel musí mít is_superuser=True.')

        # Voláme našeho vlastního helpera, který NEVYŽADUJE 'username'
        return self._create_user(email, password, **extra_fields)


class Uzivatele(AbstractUser):
    """
        Dědíme z AbstractUser, takže automaticky získáváme pole:
        - username (pokud chcete, můžete ho odstranit a používat email)
        - email (můžeme ho nastavit jako hlavní)
        - first_name, last_name
        - HESLO (automaticky spravované Djangem!)
        - is_staff, is_active, is_superuser
        - ... a další
        """

    # first_name = models.CharField(max_length=150)
    # last_name = models.CharField(max_length=150, blank=True)

    username = None  # Deaktivace pole username, které jsme zdědili
    email = models.EmailField(unique=True)

    # --- ZDE VLASTNÍ POLE ---
    telefon = models.CharField(max_length=20, blank=True, null=True)  # text
    cislo_pasu = models.CharField(max_length=50, blank=True, null=True)  # text

    # FK (VAZBA 1:N) s možností NULL
    id_aerolinky = models.ForeignKey(
        Aerolinky,
        on_delete=models.SET_NULL,  # Pokud smažu aerolinku, uživatel zůstane, ale vazba se zruší
        null=True,  # Povoluje NULL (pro zákazníky)
        blank=True,
        related_name="zamestnanci"
    )

    # --- MANUÁLNÍ M:N VAZBA ---
    # Toto pole říká Djangu: "Pro M:N vztah s 'Role' použij ručně
    # vytvořenou tabulku 'Role_uzivatel'"
    role = models.ManyToManyField(
        Role,
        through='RoleUzivatel',  # Název spojovací tabulky
        related_name="uzivatele"
    )

    USERNAME_FIELD = 'email'  # pole 'email' je teď hlavní přihlašovací pole

    # Seznam polí, která bude Django vyžadovat při tvorbě superuživatele.
    # 'email' a 'password' jsou vyžadovány automaticky.
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email


# --- ZÁVISLÉ TABULKY (ÚROVEŇ 2) ---


class Lety(models.Model):
    cislo_letu = models.CharField(max_length=10)  # text
    cas_odletu = models.DateTimeField()  # time
    cas_priletu = models.DateTimeField()  # time

    # Více FK
    id_letiste_odletu = models.ForeignKey(Letiste, on_delete=models.PROTECT, related_name="odlety")
    id_letiste_priletu = models.ForeignKey(Letiste, on_delete=models.PROTECT, related_name="prilety")
    id_letadla = models.ForeignKey(Letadla, on_delete=models.PROTECT)
    id_aerolinky = models.ForeignKey(Aerolinky, on_delete=models.PROTECT)

    # --- AUTOMATICKA M:N VAZBA ---
    # Toto pole vytvoří na pozadí spojovací tabulku 'Lety_posadka'
    # která bude obsahovat 'id_letu' a 'id_uzivatele'.
    # Let a Uživatel (jako posádka) mají vazbu M:N.
    posadka = models.ManyToManyField(
        settings.AUTH_USER_MODEL,  # vazba na Uzivatel
        related_name="lety"  # Umožní najít všechny lety pro daného uživatele (clena posadky)
    )

    def __str__(self):
        return self.cislo_letu


class InventarLetu(models.Model):
    pocet_mist_k_prodeji = models.PositiveIntegerField()  # int
    cena = models.DecimalField(max_digits=10, decimal_places=2)

    # FK
    id_letu = models.ForeignKey(Lety, on_delete=models.CASCADE)  # Pokud smažu let, smažou se i inventary
    id_tridy = models.ForeignKey(
        TridySedadel,
        on_delete=models.PROTECT  # Zabraňuje smazání tridy, pokud má přiřazene inventary
    )

    class Meta:
        # Zajišťuje, že nemůžeme mít dvě definice inventáře pro stejnou třídu na stejném letu
        unique_together = ('id_letu', 'id_tridy')

    # --- NOVÁ VALIDAČNÍ METODA ---
    def clean(self):
        # 1. Získáme celkovou kapacitu letadla pro tento let
        # (Cesta: Inventar -> Let -> Letadlo -> kapacita)
        kapacita_letadla = self.id_letu.id_letadla.kapacita_sedadel

        # 2. Spočítáme, kolik míst už je obsazeno v OSTATNÍCH inventářích tohoto letu.
        # Použijeme .exclude(id=self.id), abychom nepočítali sami sebe (při úpravě záznamu).
        obsazeno_jinde = InventarLetu.objects.filter(
            id_letu=self.id_letu
        ).exclude(id=self.id).aggregate(Sum('pocet_mist_k_prodeji'))['pocet_mist_k_prodeji__sum'] or 0

        # 3. Kolik míst chceme zabrat my + co je už zabrané
        celkem_po_ulozeni = obsazeno_jinde + self.pocet_mist_k_prodeji

        # 4. Kontrola
        if celkem_po_ulozeni > kapacita_letadla:
            zbyva_mist = kapacita_letadla - obsazeno_jinde
            raise ValidationError(
                f"Nelze uložit! Překročena kapacita letadla ({kapacita_letadla} míst). "
                f"V jiných třídách je již definováno {obsazeno_jinde} míst. "
                f"Pro tuto třídu zbývá maximálně {zbyva_mist} míst."
            )


class Rezervace(models.Model):
    datum_rezervace = models.DateTimeField(auto_now_add=True)  # time (automaticky)
    celkova_cena = models.DecimalField(max_digits=10, decimal_places=2)  # int

    # Výběr z možností
    STATUS_CHOICES = [
        ('NEZAPLACENO', 'Nezaplaceno'),
        ('ZAPLACENO', 'Zaplaceno'),
        ('STORNOVANO', 'Stornováno'),
    ]
    status_platby = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEZAPLACENO'
    )

    # FK
    id_uzivatele = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    def __str__(self):
        return f"Rezervace {self.id} - {self.status_platby}"


# --- ZÁVISLÉ TABULKY (ÚROVEŇ 3) ---

class Letenky(models.Model):
    cislo_sedadla = models.CharField(max_length=4)  # text
    cena_letenky = models.DecimalField(max_digits=10, decimal_places=2)  # int

    # FK
    id_rezervace = models.ForeignKey(Rezervace, on_delete=models.CASCADE)
    id_letu = models.ForeignKey(Lety, on_delete=models.CASCADE)
    id_tridy = models.ForeignKey(TridySedadel, on_delete=models.PROTECT)

    def __str__(self):
        return f"Letenka {self.id} ({self.cislo_sedadla})"


# --- MANUÁLNÍ SPOJOVACÍ TABULKA (PRO M:N VAZBU) ---

class RoleUzivatel(models.Model):
    """
    MANUÁLNÍ SPOJOVACÍ TABULKA:
    Tato tabulka spojuje 'Uzivatele' a 'Role' a přidává extra data.
    """
    # RUČNÍ PRIMÁRNÍ KLÍČ (PK)
    id_prirazeni = models.AutoField(primary_key=True)

    # Cizí klíče pro M:N vazbu
    id_uzivatele = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id_role = models.ForeignKey(Role, on_delete=models.CASCADE)

    # Extra data ve spojovací tabulce
    plati_od = models.DateTimeField(auto_now_add=True)
    plati_do = models.DateTimeField(null=True, blank=True)  # Povoluje NULL pro trvalé role

    class Meta:
        # Zajišťuje, že jeden uživatel nemůže mít stejnou roli přiřazenou vícekrát
        # ve stejný čas
        unique_together = ('id_uzivatele', 'id_role', 'plati_do')

