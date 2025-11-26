import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from main.models import (
    Aerolinky, Letiste, Letadla, Lety,
    InventarLetu, TridySedadel, Role
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Vygeneruje 20 letů pro každou aerolinku včetně inventáře a posádky'

    def handle(self, *args, **kwargs):
        # 1. Příprava dat
        aerolinky = Aerolinky.objects.all()
        letiste_list = list(Letiste.objects.all())

        if not aerolinky.exists():
            self.stdout.write(self.style.ERROR("Chyba: Neexistují žádné aerolinky."))
            return
        if len(letiste_list) < 2:
            self.stdout.write(self.style.ERROR("Chyba: Je potřeba alespoň 2 letiště."))
            return

        # Zajistíme, že existují třídy sedadel
        trida_eco, _ = TridySedadel.objects.get_or_create(nazev_tridy="Economy", defaults={'popis': 'Standardní třída'})
        trida_bus, _ = TridySedadel.objects.get_or_create(nazev_tridy="Business", defaults={'popis': 'Luxusní třída'})

        # 2. Hlavní smyčka přes aerolinky
        for aero in aerolinky:
            self.stdout.write(f"Generuji lety pro: {aero.nazev}...")

            # Načteme zdroje aerolinky
            letadla = list(Letadla.objects.filter(id_aerolinky=aero))

            # Načteme zaměstnance této aerolinky podle rolí
            piloti = list(User.objects.filter(id_aerolinky=aero, role__nazev_role="Pilot"))
            pruvodci = list(User.objects.filter(id_aerolinky=aero, role__nazev_role="Palubní průvodčí"))

            if not letadla:
                self.stdout.write(self.style.WARNING(f"  -> Přeskakuji (nemá letadla)"))
                continue

            # 3. Vytvoření 50 letů
            for i in range(50):
                # A) Výběr trasy
                odkud = random.choice(letiste_list)
                # Vybereme 'kam', aby to nebylo stejné jako 'odkud'
                kam = random.choice([l for l in letiste_list if l != odkud])

                # B) Výběr letadla a času
                letadlo = random.choice(letadla)

                # Odlet náhodně v příštích 60 dnech
                den_odletu = timezone.now() + timedelta(days=random.randint(1, 60))
                cas_odletu = den_odletu.replace(
                    hour=random.randint(5, 22),
                    minute=random.choice([0, 15, 30, 45])
                )

                # Doba letu (náhodně 1 až 12 hodin)
                doba_letu = timedelta(hours=random.randint(1, 12), minutes=random.randint(0, 59))
                cas_priletu = cas_odletu + doba_letu

                # C) Vytvoření Letu
                cislo_letu = f"{aero.kod_iata}{random.randint(1000, 9999)}"

                let = Lety.objects.create(
                    cislo_letu=cislo_letu,
                    cas_odletu=cas_odletu,
                    cas_priletu=cas_priletu,
                    id_letiste_odletu=odkud,
                    id_letiste_priletu=kam,
                    id_letadla=letadlo,
                    id_aerolinky=aero
                )

                # D) Přiřazení posádky (2 piloti, 2 průvodčí)
                # Kontrola, zda má aerolinka dostatek personálu
                posadka_k_prirazeni = []
                if len(piloti) >= 2:
                    posadka_k_prirazeni.extend(random.sample(piloti, 2))
                elif len(piloti) == 1:
                    posadka_k_prirazeni.append(piloti[0])

                if len(pruvodci) >= 2:
                    posadka_k_prirazeni.extend(random.sample(pruvodci, 2))
                elif len(pruvodci) == 1:
                    posadka_k_prirazeni.append(pruvodci[0])

                if posadka_k_prirazeni:
                    let.posadka.set(posadka_k_prirazeni)

                # E) Vytvoření Inventáře (Economy + Business)
                kapacita_celkem = letadlo.kapacita_sedadel

                # Výpočet rozdělení (cca 80% Economy)
                kapacita_eco = int(kapacita_celkem * 0.8)
                kapacita_bus = kapacita_celkem - kapacita_eco  # Zbytek je Business

                # Generování ceny
                cena_eco = random.randint(50, 500)  # 50 - 500 USD
                cena_bus = cena_eco * 2  # Business je 2x dražší

                # Uložení Economy
                if kapacita_eco > 0:
                    InventarLetu.objects.create(
                        id_letu=let,
                        id_tridy=trida_eco,
                        pocet_mist_k_prodeji=kapacita_eco,
                        cena=cena_eco
                    )

                # Uložení Business
                if kapacita_bus > 0:
                    InventarLetu.objects.create(
                        id_letu=let,
                        id_tridy=trida_bus,
                        pocet_mist_k_prodeji=kapacita_bus,
                        cena=cena_bus
                    )

            self.stdout.write(f"  + Vytvořeno 50 letů.")

        self.stdout.write(self.style.SUCCESS('ÚSPĚCH: Všechny lety byly vygenerovány.'))
