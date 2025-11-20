from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from django.utils import timezone
from . import models
from .forms import CustomUserCreationForm, CustomUserChangeForm


# --- POMOCNÁ FUNKCE ---
def ma_platnou_roli(user, role_nazvy):
    if user.is_superuser: return True
    if isinstance(role_nazvy, str): role_nazvy = [role_nazvy]

    return (models.RoleUzivatel.objects.filter(
        id_uzivatele=user,
        id_role__nazev_role__in=role_nazvy,
        plati_do__gte=timezone.now()
    ).exists() | models.RoleUzivatel.objects.filter(
        id_uzivatele=user,
        id_role__nazev_role__in=role_nazvy,
        plati_do__isnull=True
    ).exists())


# --- 1. UŽIVATELÉ A ROLE (INLINE) ---

class RoleUzivatelInline(admin.TabularInline):
    model = models.RoleUzivatel
    extra = 1

    # Inline dědí oprávnění od rodiče (UserAdmin),
    # ale pro jistotu můžeme omezit smazání rolí jiných aerolinek,
    # pokud bychom to hrotili. Pro teď stačí logika v UserAdmin.


class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'id_aerolinky')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Osobní údaje', {'fields': ('first_name', 'last_name')}),
        ('Firemní zařazení', {'fields': ('id_aerolinky', 'telefon', 'cislo_pasu')}),
        ('Oprávnění', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Důležitá data', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'password2'),
        }),
    )
    inlines = [RoleUzivatelInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Admin aerolinky vidí jen své zaměstnance
        if request.user.id_aerolinky and ma_platnou_roli(request.user, "Admin aerolinky"):
            return qs.filter(id_aerolinky=request.user.id_aerolinky)
        return qs.none()

    # -- Oprávnění pro Admina aerolinky --
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    # -- Logika formulářů --
    def get_inlines(self, request, obj=None):
        if obj is None:
            return []
        else:
            return self.inlines

    def save_related(self, request, form, formsets, change):
        if change:
            super().save_related(request, form, formsets, change)
        else:
            for formset in formsets: self.save_formset(request, form, formset, change=change)

    def save_model(self, request, obj, form, change):
        # Pokud Admin aerolinky vytváří uživatele, automaticky mu přiřadí svou aerolinku
        if not request.user.is_superuser and not obj.id_aerolinky:
            obj.id_aerolinky = request.user.id_aerolinky
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            # Admin aerolinky nemůže změnit aerolinku zaměstnance (přesunout ho ke konkurenci)
            return ('id_aerolinky', 'is_superuser', 'user_permissions')
        return ()


# --- 2. AEROLINKY (VLASTNÍ FIRMA) ---

class AerolinkyAdmin(admin.ModelAdmin):
    list_display = ('nazev', 'kod_iata', 'zeme_registrace')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if request.user.id_aerolinky and ma_platnou_roli(request.user, "Admin aerolinky"):
            return qs.filter(id=request.user.id_aerolinky.id)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_add_permission(self, request):
        # Povolit jen pokud je to superuser
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # Povolit jen pokud je to superuser
        return request.user.is_superuser


# --- 3. LETADLA ---

class LetadlaAdmin(admin.ModelAdmin):
    list_display = ('model', 'kapacita_sedadel', 'id_aerolinky')
    list_filter = ('id_aerolinky',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if request.user.id_aerolinky and ma_platnou_roli(request.user, ["Správce letadel", "Admin aerolinky"]):
            return qs.filter(id_aerolinky=request.user.id_aerolinky)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user,
                                                                             ["Správce letadel", "Admin aerolinky"])

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user,
                                                                       ["Správce letadel", "Admin aerolinky"])

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user,
                                                                               ["Správce letadel", "Admin aerolinky"])

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user,
                                                                               ["Správce letadel", "Admin aerolinky"])

    def get_readonly_fields(self, request, obj=None):
        # ZMĚNA: Už nepoužíváme readonly, protože to pole úplně schovávalo z formuláře.
        # Místo toho ho "zamkneme" v get_form.
        return ()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # Pokud to není superadmin (tzn. je to Správce nebo Admin aerolinky)
        if not request.user.is_superuser:
            # 1. Pokud má uživatel aerolinku, předvyplníme ji a zamkneme
            if request.user.id_aerolinky:
                field = form.base_fields['id_aerolinky']
                field.initial = request.user.id_aerolinky
                field.disabled = True  # Uživatel ho vidí, ale nemůže změnit (je šedé)
                field.help_text = "Letadlo bude automaticky přiřazeno k vaší aerolince."
            else:
                # Pokud aerolinku NEMÁ (chyba v nastavení uživatele), pole zůstane prázdné a editovatelné,
                # ale uložení pravděpodobně selže, což správce upozorní.
                pass

        return form

    def save_model(self, request, obj, form, change):
        # Pojistka: Pokud formulář z nějakého důvodu neposlal aerolinku (např. hack),
        # doplníme ji natvrdo tady.
        if not request.user.is_superuser and not obj.id_aerolinky:
            obj.id_aerolinky = request.user.id_aerolinky
        super().save_model(request, obj, form, change)


# --- 4. LETY (UPRAVENO PRO ZÁKAZNÍKA) ---


class LetyAdmin(admin.ModelAdmin):
    list_display = ('cislo_letu', 'id_letiste_odletu', 'id_letiste_priletu', 'cas_odletu', 'id_aerolinky')
    list_filter = ('id_aerolinky',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs

        # 1. Zákazník vidí VŠECHNY lety (aby si mohl vybrat)
        if ma_platnou_roli(request.user, "Zákazník"):
            return qs

        # 2. Správce/Admin vidí jen své lety
        if request.user.id_aerolinky and ma_platnou_roli(request.user, ["Správce letů", "Admin aerolinky"]):
            return qs.filter(id_aerolinky=request.user.id_aerolinky)

        # 3. Posádka vidí jen své lety
        if ma_platnou_roli(request.user, ["Pilot", "Palubní průvodčí"]):
            return qs.filter(posadka=request.user)

        return qs.none()

    # --- Oprávnění ---

    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        # Zákazník může vidět lety
        return base and ma_platnou_roli(request.user,
                                        ["Správce letů", "Admin aerolinky", "Pilot", "Palubní průvodčí", "Zákazník"])

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user,
                                                                       ["Správce letů", "Admin aerolinky"])

    def has_change_permission(self, request, obj=None):
        # DŮLEŽITÉ: Pokud má uživatel roli Zákazník (vidí vše), musíme se ujistit,
        # že jako Admin aerolinky může měnit JEN SVOJE lety.
        has_perm = super().has_change_permission(request, obj) and ma_platnou_roli(request.user,
                                                                                   ["Správce letů", "Admin aerolinky"])

        if has_perm and obj is not None and not request.user.is_superuser:
            # Pokud edituje konkrétní objekt, musí patřit jeho aerolince
            return obj.id_aerolinky == request.user.id_aerolinky
        return has_perm

    def has_delete_permission(self, request, obj=None):
        # Stejná pojistka pro mazání
        has_perm = super().has_delete_permission(request, obj) and ma_platnou_roli(request.user,
                                                                                   ["Správce letů", "Admin aerolinky"])
        if has_perm and obj is not None and not request.user.is_superuser:
            return obj.id_aerolinky == request.user.id_aerolinky
        return has_perm

    # ... (formfield_for_foreignkey a manytomany zůstávají stejné) ...
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser and user.id_aerolinky and ma_platnou_roli(user, ["Správce letů", "Admin aerolinky"]):
            if db_field.name == "id_letadla":
                kwargs["queryset"] = models.Letadla.objects.filter(id_aerolinky=user.id_aerolinky)
            if db_field.name == "id_aerolinky":
                kwargs["queryset"] = models.Aerolinky.objects.filter(id=user.id_aerolinky.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        user = request.user
        if not user.is_superuser and user.id_aerolinky and ma_platnou_roli(user, ["Správce letů", "Admin aerolinky"]):
            if db_field.name == "posadka":
                role_names = ['Pilot', 'Palubní průvodčí']
                kwargs["queryset"] = models.Uzivatele.objects.filter(id_aerolinky=user.id_aerolinky,
                                                                     role__nazev_role__in=role_names)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None and not request.user.is_superuser and request.user.id_aerolinky:
            try:
                form.base_fields['id_aerolinky'].initial = request.user.id_aerolinky
            except (KeyError, AttributeError):
                pass
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.id_aerolinky:
            # Pokud je to admin/správce, vynutíme jeho aerolinku (zákazník lety nevytváří)
            obj.id_aerolinky = request.user.id_aerolinky
        super().save_model(request, obj, form, change)


# --- 5. INVENTÁŘ LETŮ ---

class InventarLetuAdmin(admin.ModelAdmin):
    list_display = ('id_letu', 'id_tridy', 'pocet_mist_k_prodeji', 'cena')
    list_filter = ('id_letu__id_aerolinky',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        # Vidí jen inventář své aerolinky
        if request.user.id_aerolinky and ma_platnou_roli(request.user, ["Správce letů", "Admin aerolinky"]):
            return qs.filter(id_letu__id_aerolinky=request.user.id_aerolinky)
        return qs.none()

    # --- Oprávnění ---
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user,
                                                                             ["Správce letů", "Admin aerolinky"])

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user,
                                                                       ["Správce letů", "Admin aerolinky"])

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user,
                                                                               ["Správce letů", "Admin aerolinky"])

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user,
                                                                               ["Správce letů", "Admin aerolinky"])

    # --- NOVÉ: Filtrování roletek (Lety a Třídy) ---
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Pokud není superuser a má aerolinku + správnou roli
        if not request.user.is_superuser and request.user.id_aerolinky and ma_platnou_roli(request.user,
                                                                                           ["Správce letů",
                                                                                            "Admin aerolinky"]):

            # 1. Filtr pro Lety: Jen lety mé aerolinky
            if db_field.name == "id_letu":
                kwargs["queryset"] = models.Lety.objects.filter(id_aerolinky=request.user.id_aerolinky)

            # 2. Filtr pro Třídy: Jen mé třídy nebo globální
            if db_field.name == "id_tridy":
                kwargs["queryset"] = models.TridySedadel.objects.filter(
                    Q(id_aerolinky=request.user.id_aerolinky) |
                    Q(id_aerolinky__isnull=True)
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# --- 6. TŘÍDY SEDADEL ---

class TridySedadelAdmin(admin.ModelAdmin):
    list_display = ('nazev_tridy', 'id_aerolinky', 'popis')
    list_filter = ('id_aerolinky',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        if request.user.id_aerolinky and ma_platnou_roli(request.user, ["Správce tříd sedadel", "Admin aerolinky"]):
            return qs.filter(id_aerolinky=request.user.id_aerolinky)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user, ["Správce tříd sedadel",
                                                                                            "Admin aerolinky"])

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user,
                                                                       ["Správce tříd sedadel", "Admin aerolinky"])

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user, ["Správce tříd sedadel",
                                                                                              "Admin aerolinky"])

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user, ["Správce tříd sedadel",
                                                                                              "Admin aerolinky"])

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.id_aerolinky:
            obj.id_aerolinky = request.user.id_aerolinky
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser: return ('id_aerolinky',)
        return ()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None and not request.user.is_superuser and request.user.id_aerolinky:
            try:
                form.base_fields['id_aerolinky'].initial = request.user.id_aerolinky
            except (KeyError, AttributeError):
                pass
        return form


# --- 7. LETIŠTĚ ---

class LetisteAdmin(admin.ModelAdmin):
    list_display = ('nazev_letiste', 'kod_iata', 'mesto', 'zeme')

    # Admin aerolinky vidí letiště (potřebuje je pro lety), ale nemůže je měnit
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user,
                                                                             ["Správce letišť", "Admin aerolinky",
                                                                              "Správce letů"])

    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user, "Správce letišť")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user, "Správce letišť")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user, "Správce letišť")


# --- 8. REZERVACE (IMPLEMENTOVÁNO PRO ZÁKAZNÍKA) ---


class RezervaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'datum_rezervace', 'celkova_cena', 'status_platby', 'id_uzivatele')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs

        # --- ZMĚNA: ODSTRANĚNA LOGIKA PRO ZÁKAZNÍKA ---
        # Zákazník v adminu své rezervace neuvidí. Musí jít na frontend.

        # Admin aerolinky vidí rezervace s letenkami jeho firmy
        if request.user.id_aerolinky and ma_platnou_roli(request.user, "Admin aerolinky"):
            return qs.filter(letenky__id_letu__id_aerolinky=request.user.id_aerolinky).distinct()

        return qs.none()

    def save_model(self, request, obj, form, change):
        # Pokud rezervaci vytváří Zákazník, automaticky ho přiřadíme jako vlastníka
        if not request.user.is_superuser and ma_platnou_roli(request.user, "Zákazník") and not obj.id_uzivatele_id:
            obj.id_uzivatele = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        # Zákazník nemůže měnit vlastníka rezervace ani datum
        if not request.user.is_superuser and not ma_platnou_roli(request.user, "Admin aerolinky"):
            return ('id_uzivatele', 'datum_rezervace')
        return ()

    # --- Oprávnění ---

    def has_view_permission(self, request, obj=None):
        # --- ZMĚNA: Vidí jen Admin aerolinky (nebo superuser) ---
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_add_permission(self, request):
        # Admin aerolinky může teoreticky vytvořit rezervaci manuálně
        return super().has_add_permission(request) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_change_permission(self, request, obj=None):
        # ... (zde použijte logiku pro Admina aerolinky z minula) ...
        if request.user.is_superuser: return True
        if ma_platnou_roli(request.user, "Admin aerolinky"):
            if obj:
                return obj.letenky_set.filter(id_letu__id_aerolinky=request.user.id_aerolinky).exists()
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        # ... (zde použijte logiku pro Admina aerolinky z minula) ...
        if ma_platnou_roli(request.user, "Admin aerolinky"):
            if obj:
                return obj.letenky_set.filter(id_letu__id_aerolinky=request.user.id_aerolinky).exists()
            return True
        return super().has_delete_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # 1. Zákazník může smazat SVOU rezervaci
        if ma_platnou_roli(request.user, "Zákazník"):
            if obj and obj.id_uzivatele != request.user:
                return False
            return True

        # 2. Admin aerolinky může smazat rezervaci TÝKAJÍCÍ SE JEHO AEROLINKY
        if ma_platnou_roli(request.user, "Admin aerolinky"):
            if obj:
                return obj.letenky_set.filter(id_letu__id_aerolinky=request.user.id_aerolinky).exists()
            return True

        return super().has_delete_permission(request, obj)


# --- 9. LETENKY (IMPLEMENTOVÁNO PRO ZÁKAZNÍKA) ---


class LetenkyAdmin(admin.ModelAdmin):
    list_display = ('cislo_sedadla', 'cena_letenky', 'id_letu', 'id_rezervace')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs

        # 1. Zákazník vidí letenky spojené s JEHO rezervacemi
        if ma_platnou_roli(request.user, "Zákazník"):
            return qs.filter(id_rezervace__id_uzivatele=request.user)

        # 2. Admin aerolinky vidí letenky SVOJÍ firmy
        if request.user.id_aerolinky and ma_platnou_roli(request.user, "Admin aerolinky"):
            return qs.filter(id_letu__id_aerolinky=request.user.id_aerolinky)

        return qs.none()

    # --- Oprávnění ---
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and ma_platnou_roli(request.user,
                                                                             ["Admin aerolinky", "Zákazník"])

    # Letenky vytváří/maže Admin aerolinky (nebo systém), zákazník je jen vidí
    def has_add_permission(self, request):
        return super().has_add_permission(request) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and ma_platnou_roli(request.user, "Admin aerolinky")


# --- REGISTRACE ---
admin.site.register(models.Uzivatele, CustomUserAdmin)
admin.site.register(models.Role)
admin.site.register(models.Letiste, LetisteAdmin)
admin.site.register(models.Aerolinky, AerolinkyAdmin)
admin.site.register(models.Letadla, LetadlaAdmin)
admin.site.register(models.Lety, LetyAdmin)
admin.site.register(models.InventarLetu, InventarLetuAdmin)
admin.site.register(models.TridySedadel, TridySedadelAdmin)
admin.site.register(models.Rezervace, RezervaceAdmin)
admin.site.register(models.Letenky, LetenkyAdmin)
