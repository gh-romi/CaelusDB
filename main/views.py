
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import Group

from django.contrib.auth.decorators import login_required  # Pro @login_required
from .forms import PublicRegistrationForm, UserProfileForm  # Pro UserProfileForm
from django.db.models import Min
from django.shortcuts import render
from .models import Lety, Letiste, InventarLetu, Role, RoleUzivatel, Letenky, Rezervace
import json
from django.utils import timezone
from datetime import timedelta


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
        self.segmenty = lety_list  # Seznam letů (1 nebo 2)
        self.pocet_prestupu = len(lety_list) - 1
        self.celkova_cena = 0
        self.je_vyprodano = False

        # Vypočítat "Cenu od" (součet nejnižších cen segmentů)
        for let in self.segmenty:
            cena = InventarLetu.objects.filter(
                id_letu=let,
                pocet_mist_k_prodeji__gt=0
            ).aggregate(Min('cena'))['cena__min']

            if cena is None:
                self.je_vyprodano = True
                break
            self.celkova_cena += cena

        # Data pro zobrazení v kartě
        self.prvni_let = self.segmenty[0]
        self.posledni_let = self.segmenty[-1]
        self.cas_odletu = self.prvni_let.cas_odletu
        self.cas_priletu = self.posledni_let.cas_priletu

        # IDčka pro URL (např "10" nebo "10-25")
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
        if datum: prime_lety = prime_lety.filter(cas_odletu__date__gte=datum)  # Změněno na >=

        for let in prime_lety:
            vysledne_cesty.append(Cesta([let]))

        # --- 2. LETY S PŘESTUPEM (jen pokud známe start i cíl) ---
        if odkud_id and kam_id:
            # Najdeme všechny lety z bodu A (start)
            lety_start = Lety.objects.filter(id_letiste_odletu_id=odkud_id)
            if datum: lety_start = lety_start.filter(cas_odletu__date__gte=datum)

            # Najdeme všechny lety do bodu B (cíl)
            # (Datum zatím neřešíme, musí navazovat na první let)
            lety_cil = Lety.objects.filter(id_letiste_priletu_id=kam_id)
            if datum: lety_cil = lety_cil.filter(cas_odletu__date__gte=datum)

            # Hledáme spojení
            # (Tohle je zjednodušené řešení. V reálu by se to dělalo efektivněji přes DB dotazy,
            # ale pro školní projekt je Python cyklus čitelnější)

            min_cas_na_prestup = timedelta(hours=1)  # Min 1 hodina na přestup
            max_cas_na_prestup = timedelta(hours=24)  # Max 24 hodin čekání

            for let1 in lety_start:
                for let2 in lety_cil:
                    # Podmínka 1: Místo příletu 1 se musí rovnat místu odletu 2
                    if let1.id_letiste_priletu == let2.id_letiste_odletu:

                        # Podmínka 2: Časová návaznost
                        cas_cekani = let2.cas_odletu - let1.cas_priletu

                        if min_cas_na_prestup <= cas_cekani <= max_cas_na_prestup:
                            # Máme shodu! Vytvoříme cestu se 2 segmenty
                            vysledne_cesty.append(Cesta([let1, let2]))

    # Seřadíme výsledky podle ceny (nejlevnější nahoře)
    # (Poznámka: lambda funkce řadí podle vypočtené ceny)
    vysledne_cesty.sort(key=lambda x: x.celkova_cena if not x.je_vyprodano else 999999)

    context = {
        'cesty': vysledne_cesty,  # Už neposíláme 'lety', ale 'cesty'
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

    if not zobrazit_vse:
        # Výchozí stav: Jen budoucí rezervace
        # Řešíme podle data vytvoření rezervace (jednodušší a bez duplicit)
        # nebo podle data odletu prvního letu (logičtější, ale pozor na duplicity)

        # Tady používám 'letenky__id_letu__cas_odletu', což může způsobit duplicity v SQL JOINu
        rezervace_qs = rezervace_qs.filter(letenky__id_letu__cas_odletu__gte=timezone.now())

    # Aplikace filtrů (pokud jsou zadány)
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

    return render(request, 'main/moje_rezervace.html', {
        'rezervace_list': rezervace_list,
        'zobrazit_vse': zobrazit_vse
    })


@login_required
def detail_moje_rezervace(request, rezervace_id):
    # Načteme rezervaci a ověříme vlastníka
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    return render(request, 'main/detail_moje_rezervace.html', {
        'rezervace': rezervace
    })


@login_required
def smazat_rezervaci(request, rezervace_id):
    rezervace = get_object_or_404(Rezervace, pk=rezervace_id, id_uzivatele=request.user)

    if request.method == 'POST':
        # Povolíme smazání jen nezaplacené rezervace
        if rezervace.status_platby == 'NEZAPLACENO':
            rezervace.delete()
            # Přesměrujeme zpět na seznam
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
