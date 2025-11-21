
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import Group

from django.contrib.auth.decorators import login_required  # Pro @login_required
from .forms import PublicRegistrationForm, UserProfileForm  # Pro UserProfileForm
from django.db.models import Min
from django.shortcuts import render
import json
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator  # Přidejte import nahoru
from .models import Lety, Letiste, InventarLetu, Role, RoleUzivatel, Letenky, Rezervace
from decimal import Decimal  # Přidejte import pro výpočty cen


# --- POMOCNÁ FUNKCE PRO MAZÁNÍ ---
def vycistit_stare_rezervace():
    """
    Smaže nezaplacené rezervace starší než 30 minut.
    """
    limit_casu = timezone.now() - timedelta(minutes=30)
    Rezervace.objects.filter(
        status_platby='NEZAPLACENO',
        datum_rezervace__lt=limit_casu
    ).delete()


# Pomocná třída pro zobrazení výsledku (jednotný formát pro přímé i přestupní lety)
class Cesta:
    def __init__(self, lety_list):
        self.segmenty = lety_list
        self.pocet_prestupu = len(lety_list) - 1
        self.celkova_cena = 0
        self.je_vyprodano = False

        # Procházíme každý let v cestě (segment)
        for let in self.segmenty:
            # Najdeme všechny inventáře (třídy) pro tento let
            inventare = InventarLetu.objects.filter(id_letu=let)

            nejnizsi_cena_letu = None
            ma_volne_misto = False

            # Projdeme každou třídu a zjistíme, jestli je v ní místo
            for inv in inventare:
                # Kolik je kapacita
                kapacita = inv.pocet_mist_k_prodeji

                # Kolik už je prodáno letenek pro tento let a tuto třídu
                prodano = Letenky.objects.filter(id_letu=let, id_tridy=inv.id_tridy).count()

                # Je volno?
                if prodano < kapacita:
                    ma_volne_misto = True
                    # Hledáme nejnižší cenu z dostupných tříd
                    if nejnizsi_cena_letu is None or inv.cena < nejnizsi_cena_letu:
                        nejnizsi_cena_letu = inv.cena

            # Pokud jsme pro tento let nenašli žádnou třídu s volným místem
            if not ma_volne_misto:
                self.je_vyprodano = True
                self.celkova_cena = 0  # Nebo jiná hodnota, ale důležité je je_vyprodano
                break  # Stačí aby byl jeden segment vyprodán a celá cesta je k ničemu

            # Pokud místo je, přičteme nejnižší nalezenou cenu k celkové
            self.celkova_cena += nejnizsi_cena_letu

        self.prvni_let = self.segmenty[0]
        self.posledni_let = self.segmenty[-1]
        self.cas_odletu = self.prvni_let.cas_odletu
        self.cas_priletu = self.posledni_let.cas_priletu
        self.url_ids = "-".join([str(l.id) for l in self.segmenty])


def verejny_seznam_letu(request):
    vycistit_stare_rezervace()

    letiste_list = Letiste.objects.all().order_by('mesto')
    odkud_id = request.GET.get('odkud')
    kam_id = request.GET.get('kam')
    datum = request.GET.get('datum')
    je_vyhledavani = odkud_id or kam_id or datum

    vysledne_cesty = []

    if je_vyhledavani:
        # --- 1. PŘÍMÉ LETY ---
        prime_lety = Lety.objects.all().order_by('cas_odletu')
        if odkud_id: prime_lety = prime_lety.filter(id_letiste_odletu_id=odkud_id)
        if kam_id: prime_lety = prime_lety.filter(id_letiste_priletu_id=kam_id)
        if datum: prime_lety = prime_lety.filter(cas_odletu__date__gte=datum)

        for let in prime_lety:
            # Přímý let přidáme VŽDY, i když je vyprodán (aby se zobrazil červeně)
            vysledne_cesty.append(Cesta([let]))

        # --- 2. LETY S PŘESTUPEM ---
        if odkud_id and kam_id:
            lety_start = Lety.objects.filter(id_letiste_odletu_id=odkud_id)
            if datum: lety_start = lety_start.filter(cas_odletu__date__gte=datum)

            lety_cil = Lety.objects.filter(id_letiste_priletu_id=kam_id)
            if datum: lety_cil = lety_cil.filter(cas_odletu__date__gte=datum)

            min_cas = timedelta(hours=1)
            max_cas = timedelta(hours=24)

            for let1 in lety_start:
                for let2 in lety_cil:
                    if let1.id_letiste_priletu == let2.id_letiste_odletu:
                        cas_cekani = let2.cas_odletu - let1.cas_priletu
                        if min_cas <= cas_cekani <= max_cas:
                            cesta = Cesta([let1, let2])

                            # ZMĚNA (Vaše V1):
                            # Pokud je cesta s přestupem vyprodaná, VŮBEC JI NEUKAZUJEME
                            if not cesta.je_vyprodano:
                                vysledne_cesty.append(cesta)

    # Řazení: primárně čas, sekundárně cena (vyprodané nakonec)
    vysledne_cesty.sort(key=lambda x: (
        x.cas_odletu,
        x.celkova_cena if not x.je_vyprodano else 999999
    ))

    # Stránkování
    paginator = Paginator(vysledne_cesty, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'cesty': page_obj,
        'letiste_list': letiste_list,
        'je_vyhledavani': je_vyhledavani,
    }
    return render(request, 'main/index.html', context)


def rezervace_detail(request, flight_ids):

    vycistit_stare_rezervace()

    ids = flight_ids.split('-')
    segmenty = []

    # Načtení dat pro zobrazení (GET) - zůstává stejné
    for let_id in ids:
        let = get_object_or_404(Lety, pk=let_id)
        inventar = InventarLetu.objects.filter(id_letu=let, pocet_mist_k_prodeji__gt=0).order_by('cena')
        obsazena_sedadla = list(Letenky.objects.filter(id_letu=let).values_list('cislo_sedadla', flat=True))

        segmenty.append({
            'let': let,
            'inventar_list': inventar,
            'obsazena_sedadla_json': json.dumps(obsazena_sedadla),
            'kapacita': let.id_letadla.kapacita_sedadel
        })

    # --- ZPRACOVÁNÍ FORMULÁŘE (POST) ---
    if request.method == 'POST':
        # 1. Vytvoříme prázdnou rezervaci
        # Celkovou cenu zatím dáme 0, dopočítáme ji z letenek
        rezervace = Rezervace.objects.create(
            celkova_cena=0,
            status_platby='NEZAPLACENO',
            id_uzivatele=request.user
        )

        celkova_cena = 0

        # 2. Projdeme všechny lety a vytvoříme letenky
        for let_id in ids:
            # Získáme ID vybraného inventáře (z radio buttonu)
            inventar_id = request.POST.get(f'inventar_{let_id}')
            # Získáme vybrané sedadlo (z roletky)
            sedadlo = request.POST.get(f'sedadlo_{let_id}')

            # Načteme objekt inventáře (kvůli ceně a třídě)
            vybrany_inventar = get_object_or_404(InventarLetu, pk=inventar_id)

            # Vytvoříme letenku
            Letenky.objects.create(
                cislo_sedadla=sedadlo,
                cena_letenky=vybrany_inventar.cena,
                id_rezervace=rezervace,
                id_letu_id=let_id,  # Přímé přiřazení ID
                id_tridy=vybrany_inventar.id_tridy
            )

            # Přičteme cenu
            celkova_cena += vybrany_inventar.cena

        # 3. Aktualizujeme celkovou cenu rezervace
        rezervace.celkova_cena = celkova_cena
        rezervace.save()

        # 4. Přesměrujeme na platbu
        return redirect('platba', rezervace_id=rezervace.id)

    return render(request, 'main/rezervace_detail.html', {
        'segmenty': segmenty,
        'flight_ids_raw': flight_ids
    })


def registrace(request):
    if request.method == 'POST':
        form = PublicRegistrationForm(request.POST)
        if form.is_valid():
            # 1. Uložíme uživatele (vytvoří se v DB)
            user = form.save()

            # 2. Automatické přiřazení SKUPINY "Přihlášený uživatel"
            try:
                # ZDE JE TA OPRAVA:
                group = Group.objects.get(name='Přihlášený uživatel')
                user.groups.add(group)
            except Group.DoesNotExist:
                # Pro jistotu: pokud skupina neexistuje, nic se nestane (nebo print chyby)
                print("Chyba: Skupina 'Přihlášený uživatel' neexistuje!")

            # 3. Automatické přiřazení ROLE "Zákazník"
            try:
                role = Role.objects.get(nazev_role='Zákazník')
                RoleUzivatel.objects.create(
                    id_uzivatele=user,
                    id_role=role,
                    # plati_od se nastaví automaticky
                    # plati_do je NULL (navždy)
                )
            except Role.DoesNotExist:
                print("Chyba: Role 'Zákazník' neexistuje!")

            # 4. Rovnou uživatele přihlásíme
            login(request, user)

            # 5. Přesměrujeme na úvodní stránku
            return redirect('home')
    else:
        form = PublicRegistrationForm()

    return render(request, 'main/registrace.html', {'form': form})


@login_required
def muj_profil(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            # Přidáme zprávu o úspěchu (pokud to v šabloně podporujeme, jinak se jen uloží)
            return redirect('muj_profil')
    else:
        # Při načtení stránky předvyplníme formulář aktuálními daty
        form = UserProfileForm(instance=request.user)

    return render(request, 'main/profil.html', {'form': form})


def platba(request, rezervace_id):
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    if request.method == 'POST':
        # Simulace platby
        rezervace.status_platby = 'ZAPLACENO'
        # Zde bychom v reálu volali platební bránu
        rezervace.save()

        # ZMĚNA: Přesměrování na děkovnou stránku
        return redirect('potvrzeni_platby', rezervace_id=rezervace.id)

    return render(request, 'main/platba.html', {'rezervace': rezervace})


# --- NOVÁ FUNKCE ---
@login_required
def potvrzeni_platby(request, rezervace_id):
    # Načteme rezervaci (jen pro čtení detailů)
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    # Bezpečnostní kontrola: Pokud není zaplaceno, nemá tu co dělat
    if rezervace.status_platby != 'ZAPLACENO':
        return redirect('platba', rezervace_id=rezervace.id)

    return render(request, 'main/potvrzeni_platby.html', {'rezervace': rezervace})


@login_required
def moje_rezervace(request):
    # 1. Úklid
    vycistit_stare_rezervace()

    # 2. Základní queryset (bez distinct, zatím)
    rezervace_qs = Rezervace.objects.filter(id_uzivatele=request.user)

    datum_od = request.GET.get('datum_od')
    datum_do = request.GET.get('datum_do')
    zobrazit_vse = request.GET.get('zobrazit_vse') == 'on'

    # 1. ZÁKLADNÍ BEZPEČNOSTNÍ FILTR (Historie vs Budoucnost)
    if not zobrazit_vse:
        # Pokud není zaškrtnuto "zobrazit vše", VŽDY aplikujeme filtr na budoucnost.
        # To je naše "tvrdé dno". I když si uživatel do 'datum_od' dá rok 1990,
        # tento filtr ho nepustí dál než k dnešku.
        rezervace_qs = rezervace_qs.filter(letenky__id_letu__cas_odletu__gte=timezone.now())

    # 2. UŽIVATELSKÉ FILTRY (Aplikují se VŽDY, nad rámec základního filtru)
    # (Přesunuto ven z else bloku)
    if datum_od:
        rezervace_qs = rezervace_qs.filter(letenky__id_letu__cas_odletu__date__gte=datum_od)

    if datum_do:
        rezervace_qs = rezervace_qs.filter(letenky__id_letu__cas_odletu__date__lte=datum_do)

    # --- OPRAVA DUPLICIT ---
    # Použijeme .distinct() na úrovni SQL. V SQLite to funguje, ale nesmíme řadit podle pole z jiné tabulky.
    # Proto řadíme podle ID rezervace (což zhruba odpovídá času vytvoření).
    # Pokud chceme řadit podle času odletu, musíme použít Python (viz níže)

    rezervace_qs = rezervace_qs.distinct()

    # Převedeme na list a seřadíme v Pythonu (bezpečné proti duplicitám)
    rezervace_list = list(rezervace_qs)

    # Řadíme podle n-tice: (Čas odletu, ID rezervace)
    rezervace_list.sort(
        key=lambda r: (
            # 1. Kritérium: Čas odletu prvního letu (pokud letenka existuje)
            r.letenky_set.first().id_letu.cas_odletu if r.letenky_set.exists() else r.datum_rezervace,

            # 2. Kritérium: ID rezervace (menší ID = starší rezervace)
            r.id
        ),
        reverse=False  # Vzestupně (nejbližší čas / nejmenší ID nahoře)
    )

    # --- NOVÉ: STRÁNKOVÁNÍ ---
    # Zobrazíme 10 rezervací na stránku
    paginator = Paginator(rezervace_list, 10)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # -------------------------

    return render(request, 'main/moje_rezervace.html', {
        'rezervace_list': page_obj,  # Teď posíláme objekt stránky, ne celý seznam
        'zobrazit_vse': zobrazit_vse
    })


@login_required
def detail_moje_rezervace(request, rezervace_id):
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    # --- VÝPOČET STORNA ---
    refund_info = {
        'amount': 0,
        'percentage': 0,
        'is_late_cancellation': False
    }

    # Najdeme první let (podle času odletu), abychom určili limit
    prvni_letenka = rezervace.letenky_set.select_related('id_letu').order_by('id_letu__cas_odletu').first()

    if prvni_letenka:
        cas_odletu = prvni_letenka.id_letu.cas_odletu
        # Rozdíl mezi teď a odletem
        time_diff = cas_odletu - timezone.now()

        if time_diff > timedelta(hours=24):
            # Více než 24h -> Vracíme 100%
            refund_info['amount'] = rezervace.celkova_cena
            refund_info['percentage'] = 100
            refund_info['is_late_cancellation'] = False
        else:
            # Méně než 24h -> Vracíme 50% (Pozdní storno)
            refund_info['amount'] = rezervace.celkova_cena * Decimal('0.5')
            refund_info['percentage'] = 50
            refund_info['is_late_cancellation'] = True

    return render(request, 'main/detail_moje_rezervace.html', {
        'rezervace': rezervace,
        'refund_info': refund_info  # Posíláme data o vratce do šablony
    })


@login_required
def smazat_rezervaci(request, rezervace_id):
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    if request.method == 'POST':
        # ZMĚNA: Povolíme smazání KDYKOLIV (nejen když je NEZAPLACENO)
        # V reálném systému bychom zde volali bankovní API pro vrácení peněz ('refund')

        rezervace.delete()
        return redirect('moje_rezervace')

    return redirect('detail_moje_rezervace', rezervace_id=rezervace.id)


@login_required
def upravit_letenku(request, letenka_id):
    letenka = get_object_or_404(Letenky, pk=letenka_id, id_rezervace__id_uzivatele=request.user)

    # Kontrola: Úprava možná jen u nezaplacené rezervace
    if letenka.id_rezervace.status_platby != 'NEZAPLACENO':
        return redirect('detail_moje_rezervace', rezervace_id=letenka.id_rezervace.id)

    # Načteme data pro formulář (stejně jako v rezervace_detail)
    let = letenka.id_letu
    inventar = InventarLetu.objects.filter(id_letu=let, pocet_mist_k_prodeji__gt=0).order_by('cena')
    obsazena_sedadla = list(
        Letenky.objects.filter(id_letu=let).exclude(id=letenka.id).values_list('cislo_sedadla', flat=True))

    if request.method == 'POST':
        # Zpracování změny
        inventar_id = request.POST.get(f'inventar_{let.id}')
        sedadlo = request.POST.get(f'sedadlo_{let.id}')

        vybrany_inventar = get_object_or_404(InventarLetu, pk=inventar_id)

        # Aktualizace letenky
        letenka.cislo_sedadla = sedadlo
        letenka.cena_letenky = vybrany_inventar.cena
        letenka.id_tridy = vybrany_inventar.id_tridy
        letenka.save()

        # Přepočet ceny rezervace
        celkova_cena = sum(l.cena_letenky for l in letenka.id_rezervace.letenky_set.all())
        letenka.id_rezervace.celkova_cena = celkova_cena
        letenka.id_rezervace.save()

        return redirect('detail_moje_rezervace', rezervace_id=letenka.id_rezervace.id)

    return render(request, 'main/upravit_letenku.html', {
        'letenka': letenka,
        'let': let,
        'inventar_list': inventar,
        'obsazena_sedadla_json': json.dumps(obsazena_sedadla),
        'kapacita': let.id_letadla.kapacita_sedadel
    })


@login_required
def zmenit_sedadlo(request, letenka_id):
    # Načteme letenku a ověříme, že patří uživateli
    letenka = get_object_or_404(Letenky, pk=letenka_id, id_rezervace__id_uzivatele=request.user)
    let = letenka.id_letu

    # 1. Najdeme obsazená sedadla pro tento let
    # (Vynecháme ale MOJE současné sedadlo, abych si ho mohl vybrat znovu)
    obsazena_sedadla = list(
        Letenky.objects.filter(id_letu=let).exclude(id=letenka.id).values_list('cislo_sedadla', flat=True))

    # 2. Zjistíme kapacitu a index třídy pro generování písmen
    # Musíme najít, kolikátý inventář v pořadí cen to je (Economy=A, Business=B...)
    vsechny_inventare = InventarLetu.objects.filter(id_letu=let, pocet_mist_k_prodeji__gt=0).order_by('cena')

    class_index = 1
    moje_kapacita = 0

    for inv in vsechny_inventare:
        if inv.id_tridy == letenka.id_tridy:
            moje_kapacita = inv.pocet_mist_k_prodeji
            break
        class_index += 1

    # 3. Zpracování formuláře
    if request.method == 'POST':
        nove_sedadlo = request.POST.get(f'sedadlo_{let.id}')
        if nove_sedadlo:
            letenka.cislo_sedadla = nove_sedadlo
            letenka.save()
            return redirect('detail_moje_rezervace', rezervace_id=letenka.id_rezervace.id)

    return render(request, 'main/zmenit_sedadlo.html', {
        'letenka': letenka,
        'let': let,
        'obsazena_sedadla_json': json.dumps(obsazena_sedadla),
        'kapacita': moje_kapacita,
        'class_index': class_index
    })


@login_required
def moje_lety(request):
    # 1. Základní QuerySet: Lety, kde je uživatel v posádce
    # Používáme related_name='lety' z M:N vazby v modelu Lety
    lety_qs = request.user.lety.all()

    # 2. Filtrování (stejné jako u rezervací)
    datum_od = request.GET.get('datum_od')
    datum_do = request.GET.get('datum_do')
    zobrazit_vse = request.GET.get('zobrazit_vse') == 'on'

    if not zobrazit_vse:
        # Výchozí stav: Jen budoucí lety
        lety_qs = lety_qs.filter(cas_odletu__gte=timezone.now())

    if datum_od:
        lety_qs = lety_qs.filter(cas_odletu__date__gte=datum_od)
    if datum_do:
        lety_qs = lety_qs.filter(cas_odletu__date__lte=datum_do)

    # 3. Řazení (nejbližší nahoře)
    lety_qs = lety_qs.order_by('cas_odletu')

    # 4. Stránkování
    paginator = Paginator(lety_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'main/moje_lety.html', {
        'lety_list': page_obj,
        'zobrazit_vse': zobrazit_vse
    })


@login_required
def detail_moje_lety(request, let_id):
    # Načteme let, ale jen pokud je uživatel v posádce (bezpečnost)
    let = get_object_or_404(Lety, pk=let_id, posadka=request.user)

    # Získáme role uživatele pro QR kód (např. "Pilot, Vedoucí kabiny")
    # Použijeme related_name 'role' z modelu Uzivatele (resp. M:N RoleUzivatel)
    # Pozor: Model Uzivatele nemá přímý atribut 'role' pro názvy, musíme přes 'roleuzivatel_set' nebo 'role' M2M
    # V modelu Uzivatele máte: role = models.ManyToManyField(..., related_name="uzivatele")

    # Získáme názvy rolí jako string oddělený čárkou
    role_list = list(request.user.role.values_list('nazev_role', flat=True))
    role_str = ", ".join(role_list)

    return render(request, 'main/detail_moje_lety.html', {
        'let': let,
        'user_roles': role_str
    })
