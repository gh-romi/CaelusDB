document.addEventListener("DOMContentLoaded", function() {

    // GLOBAL STORE
    let STORE = {
        letadla: [],
        piloti: [],
        pruvodci: [],
        tridy: [],
        existujiciLety: [] // Jen {id, cislo, cas} pro našeptávač
    };

    const state = {
        selectedAirlineId: null,
        currentCapacity: 0,
        editingFlightId: null
    };

    // ELEMENTY
    const els = {
        selAerolinka: document.getElementById('select-aerolinka'),
        btnLoadAirline: document.getElementById('btn-load-airline'),
        inpCislo: document.getElementById('input-cislo-letu'),

        statCislo: document.getElementById('cislo-letu-status'),

        sugBoxLet: document.getElementById('let-suggestions'),
        btnLoadFlight: document.getElementById('btn-load-flight'),
        selLetadlo: document.getElementById('select-letadlo'),
        btnAddInv: document.getElementById('btn-add-inv'),
        contInv: document.getElementById('inventar-container'),
        btnCheck: document.getElementById('btn-check-collisions'),
        btnDelete: document.getElementById('btn-delete-flight'),
        resCollision: document.getElementById('collision-results'),
        // Inputy pro našeptávač letišť
        inpOdlet: document.getElementById('search-odlet'),
        hidOdlet: document.getElementById('id-letiste-odletu'),
        inpPrilet: document.getElementById('search-prilet'),
        hidPrilet: document.getElementById('id-letiste-priletu'),
        // Časy
        timeOdlet: document.getElementById('input-odlet'),
        timePrilet: document.getElementById('input-prilet')
    };

    // --- 1. START ---
    function init() {

        console.log("Startuji init()...");
        console.log("Data aerolinek:", DATA.aerolinky);
        console.log("Moje ID aerolinky:", DATA.activeAirlineId);

        setupFlightDurationCalc(); // volani funkce "vypocet doby letu"

        // Naplnění seznamu aerolinek
        els.selAerolinka.innerHTML = '<option value="">-- Vyberte aerolinku --</option>';
        DATA.aerolinky.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.innerText = a.nazev;
            if (DATA.activeAirlineId && parseInt(DATA.activeAirlineId) === a.id) {
                opt.selected = true;
            }
            els.selAerolinka.appendChild(opt);
        });

        // Superadmin vs Admin
        if (DATA.isSuperuser) {
            // Superadmin čeká na tlačítko
            els.btnLoadAirline.addEventListener('click', () => {
                const aid = els.selAerolinka.value;
                if(aid) fetchAirlineData(aid);
                else alert("Vyberte aerolinku!");
            });
            // Pokud je předvybráno z URL
            if (DATA.activeAirlineId) fetchAirlineData(DATA.activeAirlineId);
        } else {
            // Admin: auto load
            if (DATA.activeAirlineId) {
                els.selAerolinka.disabled = true;
                // Hidden input
                const h = document.createElement('input');
                h.type='hidden'; h.name='id_aerolinky'; h.value=DATA.activeAirlineId;
                els.selAerolinka.parentElement.appendChild(h);
                fetchAirlineData(DATA.activeAirlineId);
            }
        }
    }

    // --- 2. FETCH DAT AEROLINKY ---
    async function fetchAirlineData(aid) {
        state.selectedAirlineId = parseInt(aid);
        document.body.style.cursor = 'wait';
        try {
            const res = await fetch(`/api/load-airline-data/?airline_id=${aid}`);
            const d = await res.json();
            if(d.error) { alert(d.error); return; }

            // Uložení do STORE
            STORE.letadla = d.letadla;
            STORE.piloti = d.piloti;
            STORE.pruvodci = d.pruvodci;
            STORE.tridy = d.tridy;
            STORE.existujiciLety = d.existujici_lety;

            renderForms();
        } catch(e) { console.error(e); alert("Chyba při načítání dat."); }
        finally { document.body.style.cursor = 'default'; }
    }

    function renderForms() {
        // Letadla
        els.selLetadlo.innerHTML = '<option value="">-- Vyberte letadlo --</option>';
        STORE.letadla.forEach(l => {
            const opt = document.createElement('option');
            opt.value = l.id;
            opt.innerText = `${l.model} (Kap: ${l.kapacita_sedadel})`;
            opt.setAttribute('data-cap', l.kapacita_sedadel);
            els.selLetadlo.appendChild(opt);
        });

        // Posádka
        renderDualList('piloti', STORE.piloti);
        renderDualList('pruvodci', STORE.pruvodci);

        // Reset
        state.currentCapacity = 0;
        updateCapacity();
        els.btnAddInv.disabled = true;
    }

    // --- 3. NAČTENÍ LETU (EDITACE + KONTROLA) ---
    els.inpCislo.addEventListener('input', function() {
        const val = this.value.trim().toUpperCase();

        // Reset
        els.sugBoxLet.innerHTML = '';
        if (els.statCislo) els.statCislo.innerText = ''; // Pojistka kdyby element neexistoval

        if(val.length < 1) {
            els.sugBoxLet.style.display='none';
            return;
        }

        // 1. Kontrola existence (Barevný nápis)
        const exactMatch = STORE.existujiciLety.find(l => l.cislo_letu.toUpperCase() === val);

        if (els.statCislo) {
            if (exactMatch) {
                // Pokud editujeme tento let, je to OK
                if (state.editingFlightId && parseInt(state.editingFlightId) === exactMatch.id) {
                    els.statCislo.innerText = "✅ Aktuální";
                    els.statCislo.style.color = "green";
                } else {
                    els.statCislo.innerText = "❌ Už existuje";
                    els.statCislo.style.color = "red";
                }
            } else {
                els.statCislo.innerText = "✅ Volné";
                els.statCislo.style.color = "green";
            }
        }

        // 2. Našeptávač
        const matches = STORE.existujiciLety.filter(l => l.cislo_letu.toUpperCase().includes(val));
        if(matches.length > 0) {
            els.sugBoxLet.style.display = 'block';
            matches.forEach(l => {
                const d = document.createElement('div');
                d.className = 'suggestion-item';
                d.innerText = `${l.cislo_letu} (${new Date(l.cas_odletu).toLocaleDateString()})`;
                d.addEventListener('click', () => {
                    // 1. Vyplníme text
                    els.inpCislo.value = l.cislo_letu;

                    // 2. Skryjeme nabídku
                    els.sugBoxLet.style.display = 'none';

                    // 3. AUTOMATICKY KLIKNEME NA TLAČÍTKO "NAČÍST LET"
                    // To zajistí načtení dat a přepnutí stavu na "Aktuální"
                    els.btnLoadFlight.click();
                });
                els.sugBoxLet.appendChild(d);
            });
        } else {
            els.sugBoxLet.style.display='none';
        }
    });

    els.btnLoadFlight.addEventListener('click', async () => {
        const cislo = els.inpCislo.value;
        const found = STORE.existujiciLety.find(l => l.cislo_letu === cislo);
        if(!found) { alert("Let nenalezen!"); return; }

        try {
            const res = await fetch(`/api/load-flight-detail/?flight_id=${found.id}`);
            const flight = await res.json();
            if(flight.error) { alert(flight.error); return; }

            fillFlightForm(flight);
        } catch(e) { alert("Chyba při načítání detailu letu."); }
    });

    function fillFlightForm(f) {
        document.getElementById('flight-id').value = f.id;
        state.editingFlightId = f.id;

        // Zobrazit delete tlačítko
        els.btnDelete.style.display = 'block';

        // Vyplnit inputy
        els.timeOdlet.value = f.cas_odletu;
        els.timePrilet.value = f.cas_priletu;

        els.hidOdlet.value = f.id_letiste_odletu;
        els.inpOdlet.value = f.nazev_odletu;
        els.hidPrilet.value = f.id_letiste_priletu;
        els.inpPrilet.value = f.nazev_priletu;

        els.selLetadlo.value = f.id_letadla;
        els.selLetadlo.dispatchEvent(new Event('change')); // trigger capacity calc

        // Posádka
        renderDualList('piloti', STORE.piloti, f.posadka_ids);
        renderDualList('pruvodci', STORE.pruvodci, f.posadka_ids);

        // Inventář
        els.contInv.innerHTML = '';
        f.inventar.forEach(i => addInventoryRow(i.id_tridy, i.pocet_mist_k_prodeji, i.cena));

        // Spustíme ručně událost 'input', aby se přepočítal status "Už existuje" -> "Aktuální"
        els.inpCislo.dispatchEvent(new Event('input'));

        // --- NOVÝ ŘÁDEK: OKAMŽITĚ ZAVŘÍT NAŠEPTVÁČ ---
        // Protože ten dispatchEvent o řádek výše ho omylem znovu otevřel
        els.sugBoxLet.style.display = 'none';
    }

    // --- 4. SMAZÁNÍ LETU ---
    els.btnDelete.addEventListener('click', async () => {
        if(!confirm("Opravdu smazat tento let?")) return;
        const fid = document.getElementById('flight-id').value;
        try {
            const res = await fetch('/api/delete-flight/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                body: JSON.stringify({flight_id: fid})
            });
            const d = await res.json();
            if(d.success) { alert("Smazáno!"); window.location.reload(); }
            else alert("Chyba mazání: " + d.error);
        } catch(e) { alert("Chyba serveru."); }
    });

    // --- 5. KONTROLA KOLIZÍ ---
    els.btnCheck.addEventListener('click', async () => {
        const pIds = [];
        document.querySelectorAll('input[name="piloti_ids"], input[name="pruvodci_ids"]').forEach(i => pIds.push(parseInt(i.value)));
        const data = {
            flight_id: state.editingFlightId,
            cas_odletu: els.timeOdlet.value,
            cas_priletu: els.timePrilet.value,
            id_letadla: els.selLetadlo.value,
            posadka_ids: pIds
        };
        try {
            const res = await fetch('/api/check-collisions/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                body: JSON.stringify(data)
            });
            const r = await res.json();
            els.resCollision.innerHTML = '';
            if(r.warnings && r.warnings.length > 0) {
                r.warnings.forEach(w => {
                    const div = document.createElement('div');
                    div.className = 'alert alert-danger'; div.innerText = w;
                    els.resCollision.appendChild(div);
                });
            } else {
                els.resCollision.innerHTML = '<div class="alert alert-success">✅ Žádné kolize.</div>';
            }
        } catch(e) { alert("Chyba kontroly."); }
    });

    // --- POMOCNÉ FUNKCE (Autocomplete, DualList, Inventar) ---

    // Autocomplete (vylepšeno o zemi)
    function setupAC(inp, box, hid) {
        inp.addEventListener('input', function() {
            const val = this.value.toLowerCase();
            box.innerHTML = '';
            if(val.length < 2) { box.style.display='none'; return; }
            const matches = DATA.letiste.filter(l =>
                l.nazev_letiste.toLowerCase().includes(val) ||
                l.mesto.toLowerCase().includes(val) ||
                l.kod_iata.toLowerCase().includes(val) ||
                l.zeme.toLowerCase().includes(val)
            );
            if(matches.length>0) {
                box.style.display = 'block';
                matches.forEach(l => {
                    const d = document.createElement('div');
                    d.className = 'suggestion-item';
                    d.innerText = `${l.nazev_letiste} (${l.kod_iata}), ${l.mesto}, ${l.zeme}`;
                    d.addEventListener('click', () => {
                        inp.value = `${l.mesto} (${l.kod_iata})`;
                        hid.value = l.id;
                        box.style.display = 'none';
                    });
                    box.appendChild(d);
                });
            } else box.style.display='none';
        });
        document.addEventListener('click', e => { if(e.target!==inp) box.style.display='none'; });
    }
    setupAC(els.inpOdlet, document.getElementById('suggestions-odlet'), els.hidOdlet);
    setupAC(els.inpPrilet, document.getElementById('suggestions-prilet'), els.hidPrilet);

    // Dual List
    function renderDualList(type, people, selectedIds=[]) {
        const pool = document.getElementById(`pool-${type}`);
        const sel = document.getElementById(`selected-${type}`);
        pool.innerHTML=''; sel.innerHTML='';
        updateHiddenInputs(type);

        people.forEach(p => {
            const d = document.createElement('div');
            d.className = 'list-item';
            const name = p.first_name ? `${p.first_name} ${p.last_name}` : p.email;
            d.innerText = name;
            d.dataset.id = p.id;
            d.addEventListener('click', function() {
                // Move logic
                if(this.parentElement === pool) sel.appendChild(this);
                else pool.appendChild(this);
                updateHiddenInputs(type);
            });
            if(selectedIds.includes(p.id)) sel.appendChild(d);
            else pool.appendChild(d);
        });
        updateHiddenInputs(type); // Init inputs
    }

    function updateHiddenInputs(type) {
        const cont = document.getElementById(`container-${type}-ids`);
        cont.innerHTML = '';
        const children = document.getElementById(`selected-${type}`).children;
        for(let c of children) {
            const i = document.createElement('input');
            i.type='hidden'; i.name=`${type}_ids`; i.value=c.dataset.id;
            cont.appendChild(i);
        }
    }

    // Inventář & Kapacita
    let invCount = 0;
    els.selLetadlo.addEventListener('change', function() {
        const opt = this.options[this.selectedIndex];
        state.currentCapacity = opt.value ? parseInt(opt.getAttribute('data-cap')) : 0;
        els.btnAddInv.disabled = !opt.value;
        updateCapacity();
    });

    els.btnAddInv.addEventListener('click', () => addInventoryRow());

    function addInventoryRow(tid='', cnt='', prc='') {
        invCount++;
        const row = document.createElement('div');
        row.className = 'row align-items-end inv-row';
        row.style.background = '#f9f9f9'; row.style.padding='10px'; row.style.marginBottom='10px';

        // Vytvoříme SELECT zatím prázdný, naplníme ho funkcí updateClasses
        const selectHTML = `<select name="inv_trida_${invCount}" class="form-control inv-class-select" required></select>`;

        row.innerHTML = `
            <div class="col"><label>Třída</label>${selectHTML}</div>
            <div class="col"><label>Míst</label><input type="number" name="inv_pocet_${invCount}" class="form-control inv-pocet" min="1" value="${cnt}" required></div>
            <div class="col"><label>Cena</label><input type="number" name="inv_cena_${invCount}" class="form-control" min="0" step="0.01" value="${prc}" required></div>
            <div class="col" style="flex:0 0 50px"><button type="button" class="btn btn-delete" style="color:red">✕</button></div>
        `;
        els.contInv.appendChild(row);

        // Uložíme si vybranou hodnotu (pokud načítáme existující let) do data atributu, aby ji updateClasses obnovil
        const sel = row.querySelector('.inv-class-select');
        sel.dataset.value = tid;

        // Listeners
        sel.addEventListener('change', updateAvailableClasses); // Při změně přepočítat ostatní
        row.querySelector('.inv-pocet').addEventListener('input', updateCapacity);
        row.querySelector('.btn-delete').addEventListener('click', () => {
            row.remove();
            updateCapacity();
            updateAvailableClasses(); // Při smazání uvolnit třídu
        });

        updateCapacity();
        updateAvailableClasses(); // Spustit přepočet po přidání
    }

    function updateAvailableClasses() {
        const allSelects = document.querySelectorAll('.inv-class-select');

        // 1. Zjistíme, které třídy jsou už vybrané (hodnoty ostatních selectů)
        const selectedValues = Array.from(allSelects).map(s => s.value).filter(v => v);

        // 2. Projdeme všechny selecty a aktualizujeme jejich <option>
        allSelects.forEach(select => {
            const currentValue = select.value || select.dataset.value; // Aktuální hodnota nebo ta z načtení

            // Vyčistíme a znovu naplníme
            select.innerHTML = '<option value="">Vyberte třídu</option>';

            STORE.tridy.forEach(t => {
                // Podmínka: Třídu přidáme, pokud:
                // a) Není nikde jinde vybraná (selectedValues neobsahuje t.id)
                // b) NEBO je to právě ta vybraná v tomto selectu (currentValue == t.id)
                // c) NEBO je to nově přidaný řádek a třída je volná
                const isTaken = selectedValues.includes(String(t.id));
                const isMyValue = String(t.id) === String(currentValue);

                if (!isTaken || isMyValue) {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.innerText = t.nazev_tridy;
                    if (isMyValue) opt.selected = true;
                    select.appendChild(opt);
                } else {
                    // Volitelně: Můžeme přidat disabled option pro přehlednost
                    // const opt = document.createElement('option');
                    // opt.value = t.id; opt.innerText = t.nazev_tridy + " (obsazeno)"; opt.disabled = true;
                    // select.appendChild(opt);
                }
            });

            // Po prvním renderu smažeme dataset, už ho nepotřebujeme
            select.dataset.value = '';
        });
    }

    function updateCapacity() {
        let occ = 0;
        document.querySelectorAll('.inv-pocet').forEach(i => occ += parseInt(i.value)||0);
        const rem = state.currentCapacity - occ;
        document.getElementById('info-kapacita').innerText = state.currentCapacity;
        const elRem = document.getElementById('info-zbyva');
        elRem.innerText = rem;
        if(rem < 0) { elRem.style.color='red'; elRem.innerText += " (PŘEKROČENO!)"; }
        else if(rem < 10) elRem.style.color='orange';
        else elRem.style.color='#28a745';
    }

    function getCookie(name) {
        if (!document.cookie) return null;
        const xs = document.cookie.split(';');
        for (let x of xs) {
            const y = x.trim();
            if (y.startsWith(name + '=')) return decodeURIComponent(y.substring(name.length + 1));
        }
        return null;
    }

    // --- VÝPOČET DOBY LETU ---
    function setupFlightDurationCalc() {
        const tOdlet = document.getElementById('input-odlet');
        const tPrilet = document.getElementById('input-prilet');
        const elInfo = document.getElementById('info-doba-letu');
        const warnPrilet = document.getElementById('warn-prilet'); // Ujistěte se, že tento element v HTML existuje

        function calc() {
            const start = new Date(tOdlet.value);
            const end = new Date(tPrilet.value);

            if (isNaN(start) || isNaN(end)) {
                elInfo.innerText = "";
                return;
            }

            if (end <= start) {
                elInfo.innerText = "";
                if(warnPrilet) warnPrilet.style.display = 'block';
            } else {
                if(warnPrilet) warnPrilet.style.display = 'none';
                const diffMs = end - start;
                const diffHrs = Math.floor(diffMs / 3600000);
                const diffMins = Math.round(((diffMs % 3600000) / 60000));
                elInfo.innerText = `Doba letu: ${diffHrs}h ${diffMins}m`;
            }
        }

        tOdlet.addEventListener('change', calc);
        tPrilet.addEventListener('change', calc);
    }



    init();
});
