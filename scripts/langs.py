"""Cudzojazyčné verzie webu (maďarská a ukrajinská).

Preložené sú úvod, stránky liekov, AI asistent a ochranný limit; ostatné odkazy vedú na slovenské stránky (označené SK).
Každý jazyk je slovník textov; rozloženie a stránky skladá build_pages.py (funkcie *_l).
"""


def _hu_date(iso):
    y, m, d = iso[:10].split("-")
    return f"{y}. {m}. {d}."


def _uk_date(iso):
    y, m, d = iso[:10].split("-")
    return f"{d}.{m}.{y}"


HU = {
    "code": "hu", "locale": "hu_HU", "num": "hu-HU", "self": "Magyar nyelvű változat",
    "root": "/hu/", "drug": "/hu/gyogyszer/", "ai": "/hu/asszisztens/", "limit": "/hu/vedelmi-limit/",
    "date": _hu_date,
    # --- rozloženie ---
    "skip": "Ugrás a tartalomra", "brand_aria": "doplatkyliekov.sk – kezdőlap", "nav_aria": "Fő navigáció",
    "nav_top": [("/hu/", "Keresés", "", ""), ("/choroby/", "Betegségek (SK)", "", ""),
                ("/zmeny/", "Változások (SK)", "Változások", "m"), ("/vypadky/", "Kiesések (SK)", "Kiesések", "m"),
                ("/bez-doplatku/", "Térítésmentes (SK)", "Ingyenes", "m x-960"), ("/hu/vedelmi-limit/", "Védelmi limit", "Limit", "m x-960")],
    "menu": [
        ("Magyarul", [("/hu/", "Gyógyszer keresése"), ("/hu/asszisztens/", "MI asszisztens"), ("/hu/vedelmi-limit/", "Védelmi limit és visszatérítés")]),
        ("Szlovák nyelvű oldalak", [("/moje-lieky/", "Gyógyszereim (Moje lieky)"), ("/choroby/", "Gyógyszerek betegségek szerint"),
                                    ("/bez-doplatku/", "Térítésmentes gyógyszerek"), ("/zmeny/", "A térítési díjak változásai"),
                                    ("/vypadky/", "Szállítási kiesések"), ("/vyhody-poistovni/", "Biztosítói kedvezmények")]),
        ("A weboldalról", [("/", "Slovenská verzia"), ("/uk/", "Українська версія"), ("/o-nas/", "Rólunk (SK)"), ("/kontakt/", "Kapcsolat (SK)"),
                           ("/ochrana-sukromia/", "Adatvédelem (SK)"), ("/pristupnost/", "Akadálymentesség (SK)")]),
    ],
    "mine": "Gyógyszereim", "ai_lbl": "MI asszisztens", "ai_btn_title": "MI asszisztens – kérdezzen a gyógyszerekről",
    "theme_aria": "Világos vagy sötét mód", "theme_title": "Világos / sötét mód",
    "disp_aria": "Megjelenítés: színmód, betűméret, gyengénlátó mód", "disp_title": "Megjelenítés", "disp_lbl": "Megjelenítés", "menu_lbl": "Menü",
    "menu_h": "Menü", "menu_close": "Menü bezárása", "menu_disp": "Megjelenítés: világos mód, betűméret, gyengénlátóknak", "menu_all": "Összes oldal",
    "disp_h": "Megjelenítés", "disp_close": "Beállítások bezárása", "theme_legend": "Színmód",
    "t_dark": "Sötét", "t_light": "Világos", "t_auto": "Eszköz szerint", "fs": "Betűméret", "fs_minus": "Betű kicsinyítése", "fs_plus": "Betű nagyítása",
    "contrast": "Gyengénlátó mód",
    "contrast_desc": "Nagy kontraszt, nagyobb és jobban olvasható betűk, aláhúzott hivatkozások, animációk és áttetsző hatások nélkül.",
    "reset": "Eredeti megjelenítés visszaállítása", "set_note": "A beállítás csak ebben a böngészőben tárolódik.",
    "bottom": [("/hu/", "Keresés", "search"), ("/moje-lieky/", "Listám", "mine"), ("/hu/asszisztens/", "Asszisztens", "spark"),
               ("/hu/vedelmi-limit/", "Limit", "shield")],
    "bottom_aria": "Gyorslinkek", "foot_aria": "További oldalak",
    "foot_src": "Forrás: a Szlovák Egészségügyi Minisztérium kategorizált gyógyszerlistája (érvényes: {platnost}) és az ŠÚKL szállítási bejelentései. Az árak euróban, áfával értendők.",
    "foot_disc": "Az oldal tájékoztató jellegű, nem gyógyszerreklám, és nem helyettesíti az orvos vagy a gyógyszerész tanácsát. A gyógyszerek sorrendjét kizárólag a térítési díj határozza meg.",
    "crumbs_aria": "Navigáció", "home_lbl": "Kezdőlap", "illus_note": "Illusztráció",
    # --- stránka lieku ---
    "types": {"Originál": "Originális", "Generikum": "Generikum", "Biologický": "Biológiai"}, "type_default": "Gyógyszer",
    "tag_best": "Legalacsonyabb", "tag_zero": "Térítésmentes", "tag_vyp": "Kiesés", "price_row": "ár {}",
    "desc_save": "{name} ({pk}) térítési díja {dop}. Olcsóbb alternatíva azonos hatóanyaggal: {cname} {cdop}. Megtakarítás csomagonként {save}.",
    "verdict_save": "A(z) <strong>{name}</strong> térítési díja {dop}. A legolcsóbb, azonos hatóanyagú, hatáserősségű és kiszerelésű alternatíva: <strong>{clink}</strong>, {cdop}.",
    "per_pack": "csomagonként",
    "desc_cheap": "{name} ({pk}) térítési díja {dop}, a legolcsóbbak közé tartozik ({s}).",
    "verdict_cheap": "A(z) <strong>{name}</strong> már a legolcsóbbak közé tartozik ebben a csoportban. Térítési díj: {dop}.",
    "desc_single": "{name} ({pk}) térítési díja {dop}, végső ár {konc}. Hatóanyag: {s}.",
    "verdict_single": "A(z) <strong>{name}</strong> gyógyszernek nincs más változata azonos hatóanyaggal, hatáserősséggel és kiszereléssel.",
    "vyp": {"R": "Szünetel a szállítás", "Z": "Megszűnt a szállítás", "PR": "Bejelentett szállítási szünet", "PZ": "Bejelentett szállítás-megszűnés"},
    "vyp_text": "A forgalomba hozatali engedély jogosultjának bejelentése szerint {od}-i hatállyal.{extra}",
    "vyp_alt": " Elérhető alternatíva: {link} ({dop}).",
    "gone_title": "{nd}-i hatállyal kikerül a támogatott gyógyszerek listájából",
    "gone_text": "A biztosító ettől a naptól nem feltétlenül téríti. Beszéljen orvosával a helyettesítésről.",
    "change_title": "{nd}-i hatállyal a térítési díj {verb}: {dop}", "up": "nő", "down": "csökken", "change_now": "Jelenleg {dop}.",
    "hist_h": "A térítési díj alakulása", "lo": "Legalacsonyabb", "hi": "Legmagasabb", "now": "Most",
    "f_who": "Ki írhatja fel", "only_spec": "Csak szakorvos: {list} <small>(szakterület szlovákul)</small>", "any_doc": "Bármely orvos, a háziorvos is",
    "f_io": "Indikációs korlátozás", "io_val": "Igen, a biztosító csak meghatározott betegségeknél téríti",
    "f_gp": "Felírás", "gp_val": "Hatóanyagnévvel írják fel<small>A gyógyszertárban bármelyik ilyen hatóanyagú gyógyszert választhatja, például a legolcsóbbat.</small>",
    "f_lim": "Védelmi limit", "lim_val": 'A limitbe {pdop} számít bele<small><a href="{limit}">Hogyan működik a védelmi limit</a></small>',
    "f_subst": "Hatóanyag", "f_drz": "Forgalomba hozatali engedély jogosultja", "f_kod": "ŠÚKL-kód / ATC",
    "qs": ["Van olcsóbb alternatívája ennek a gyógyszernek?", "Mennyi számít bele a védelmi limitbe?", "Ki írhatja fel nekem?"],
    "ai_h": "Kérdezze az MI asszisztenst", "ai_aria": "Kérdések az asszisztensnek",
    "ai_hint": "Mesterséges intelligencia válaszol a weboldal adatai alapján. Nem helyettesíti az orvost vagy a gyógyszerészt.",
    "eyebrow": "Gyógyszer térítési díja", "mine_add": "Mentés a Gyógyszereim közé", "subst_eyebrow": "Hatóanyag",
    "prices": ("Térítési díj", "A biztosító fizeti", "Végső ár"),
    "slip_foot": "Azonos hatóanyagú, hatáserősségű és kiszerelésű gyógyszerek összehasonlítása ({n}). A térítési díj a gyógyszertárban fizetendő legmagasabb összeg.",
    "about_h": "A gyógyszerről",
    "notes": [("Hogyan cserélhető a gyógyszer", "Kérdezze meg a gyógyszerészt olcsóbb alternatíváról. Kiadhatja, ha az orvos a recepten nem jelölte, hogy a gyógyszer nem cserélhető. Kétség esetén beszéljen orvosával."),
              ("Mi a térítési díj", "A gyógyszertárban fizetendő legmagasabb összeg (doplatok). A végső ár többi részét az egészségbiztosító fizeti. A gyógyszertár kedvezményt is adhat.")],
    "drug_title": "{name} ({pk}) – térítési díj és olcsóbb alternatívák", "chart_aria": "A térítési díj alakulása",
    # --- asistent ---
    "ai_sugg": ["Mennyi a térítési díja a Concor 10 mg-nak?", "Van olcsóbb alternatíva a Xarelto 20 mg helyett?",
                "Mennyit térít vissza a biztosító, ha nyugdíjas vagyok?", "Mely vérnyomáscsökkentők térítésmentesek?",
                "Mi változik {next}-i hatállyal?", "Melyik biztosító téríti vissza a gyerekeknek a térítési díjat?"],
    "ai_sugg_nonext": "Mi változik jövő hónaptól?",
    "ai_crumb": "MI asszisztens", "ai_eyebrow": "MI asszisztens · béta", "ai_h1": "Kérdezzen a gyógyszerekről és a térítési díjakról",
    "ai_sub": "Az asszisztens a weboldal teljes tartalmában keres: térítési díjak és olcsóbb alternatívák, változások, szállítási kiesések, gyógyszerek betegségek szerint, védelmi limit és a biztosítók kedvezményei.",
    "ai_notice": '<strong>Mesterséges intelligencia válaszol.</strong> Egy nyelvi modell a weboldal adatai alapján válaszol, és tévedhet, ezért ellenőrizze az adatokat a gyógyszer oldalán. Nem helyettesíti az orvost vagy a gyógyszerészt. Ne adja meg nevét, születési számát vagy más személyes adatát. <a href="/ochrana-sukromia/#asistent" lang="sk">Adatkezelés (szlovákul)</a>',
    "ai_ctx": "Gyógyszer:", "ai_chat": "Beszélgetés az asszisztenssel", "ai_q": "Az Ön kérdése", "ai_ph": "Írja be kérdését…",
    "ai_mic": "Kérdés hanggal", "ai_send": "Kérdés elküldése", "ai_try": "Próbálja megkérdezni", "ai_new": "Új beszélgetés",
    "ai_title": "MI asszisztens – kérdések a gyógyszerekről és térítési díjakról",
    "ai_desc": "Kérdezze az MI asszisztenst a szlovákiai gyógyszerek térítési díjáról, olcsóbb alternatívákról, kiesésekről és a védelmi limitről.",
    # --- ochranný limit ---
    "lim_crumb": "Védelmi limit",
    "lim_title": "Védelmi limit 2026 – mennyit térít vissza a biztosító a gyógyszerekért",
    "lim_desc": "Védelmi limit (ochranný limit) Szlovákiában 2026: limitek nyugdíjasoknak, ŤZP igazolvánnyal rendelkezőknek és gyermekeknek, mi számít bele, kalkulátor.",
    "lim_body": """
  <section class="intro">
    <p class="eyebrow">Védelmi limit (ochranný limit)</p>
    <h1 class="page-h1">Mennyit térít vissza a biztosító a térítési díjakból</h1>
    <p class="page-sub">A nyugdíjasoknak, a ŤZP igazolvánnyal rendelkezőknek, a rokkantnyugdíjasoknak és a kisgyermekeknek az egészségbiztosító visszatéríti a negyedéves limit feletti térítési díjakat. Nem kell kérvényezni.</p>
  </section>
  <section class="card">
    <h2>Kalkulátor</h2>
    <form class="calc" id="calc">
      <label for="skupina">Kicsoda Ön
        <select id="skupina">
          <option value="dieta">6 év alatti gyermek</option>
          <option value="ztp">ŤZP igazolvánnyal rendelkező vagy rokkantnyugdíjas</option>
          <option value="dochodca" selected>Öregségi vagy előrehozott öregségi nyugdíjas</option>
          <option value="iny">Egyik sem</option>
        </select>
      </label>
      <label for="prijem" id="prijem-wrap">Nyugdíja és jövedelme
        <select id="prijem">
          <option value="nizky">Nyugdíj havonta legfeljebb 914,40 € és összjövedelem negyedévente legfeljebb 2 743,20 €</option>
          <option value="vyssi" selected>Magasabb</option>
        </select>
      </label>
      <label for="suma">Beszámítható térítési díjak negyedévente (€)
        <input id="suma" type="number" inputmode="decimal" min="0" step="0.01" value="45">
      </label>
      <p class="result" id="vysledok" aria-live="polite"></p>
    </form>
    <p class="hint">Tájékoztató számítás a 2026-os szabályok szerint. A pontos összeget az egészségbiztosító erősíti meg.</p>
  </section>
  <section class="card">
    <h2>Negyedéves limitek (2026)</h2>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Kinek</th><th>Limit</th><th>Feltétel</th></tr></thead>
      <tbody>
        <tr><td>6 év alatti gyermek</td><td class="num">0 €</td><td>Jövedelemtől függetlenül. A legolcsóbb helyettesítő gyógyszer térítési díját már a gyógyszertárban sem fizeti.</td></tr>
        <tr><td>ŤZP igazolvánnyal rendelkező, rokkantnyugdíjas</td><td class="num">0 €</td><td>Nyugdíj havonta legfeljebb 914,40 € és összjövedelem negyedévente legfeljebb 2 743,20 €</td></tr>
        <tr><td>Öregségi vagy előrehozott öregségi nyugdíjas</td><td class="num">0 €</td><td>Nyugdíj havonta legfeljebb 914,40 € és összjövedelem negyedévente legfeljebb 2 743,20 €</td></tr>
        <tr><td>ŤZP igazolvánnyal rendelkező, rokkantnyugdíjas</td><td class="num">12 €</td><td>Magasabb jövedelem esetén</td></tr>
        <tr><td>Öregségi vagy előrehozott öregségi nyugdíjas</td><td class="num">30 €</td><td>Magasabb jövedelem esetén</td></tr>
      </tbody>
    </table></div>
  </section>
  <section class="prose article">
    <h2>Mi számít bele</h2>
    <p>A limitbe nem a teljes kifizetett térítési díj számít bele, hanem csak <strong>a legolcsóbb helyettesítő gyógyszer térítési díja</strong> azonos hatóanyaggal. Ha drágább márkát választ, a különbözetet Ön fizeti, és a biztosító nem téríti vissza. Minden gyógyszer oldalán megtalálja, mennyi számít bele a limitbe.</p>
    <p>Példa: öregségi nyugdíjas, havi 700 € nyugdíjjal és más jövedelem nélkül: negyedéves jövedelme 2 100 € (700 × 3), ez 2 743,20 € alatt van, ezért limitje 0 €.</p>
    <h2>Hogyan kapja vissza a pénzt</h2>
    <ul>
      <li>A biztosító maga összesíti a térítési díjakat a gyógyszertárak adataiból, nem kell blokkokat küldeni.</li>
      <li>A limit feletti összeget a negyedév végét követő 90 napon belül fizeti vissza, általában bankszámlára.</li>
      <li>Ha a visszatérítés 3 €-nál kevesebb, átkerül a következő negyedévre.</li>
    </ul>
    <p>A biztosítók a törvényen felül saját kedvezményeket is adnak, például a gyermekek térítési díjának visszatérítését: <a href="/vyhody-poistovni/" lang="sk">a biztosítók kedvezményei (szlovákul)</a>.</p>
  </section>""",
    "lim_js": {"none": "A törvényes védelmi limit Önre nem vonatkozik. Egyes biztosítók azonban saját programokkal térítik vissza a térítési díjakat.",
               "limit": "Az Ön limitje <b>{l}</b> negyedévente. ",
               "zero": "A legolcsóbb helyettesítő gyógyszer térítési díját már a gyógyszertárban sem kellene fizetnie.",
               "back": "A biztosító körülbelül <b>{b}</b> összeget térít vissza.",
               "carry": "A {b} túlfizetés kevesebb mint 3 €, ezért átkerül a következő negyedévre.",
               "notyet": "Nem lépte túl a limitet, visszatérítés még nem jár."},
    # --- úvodná stránka (preklad slovenskej šablóny) ---
    "home": {
        "Nájdite lacnejší liek s rovnakou účinnou látkou. Porovnanie doplatkov za lieky na predpis podľa úradného zoznamu Ministerstva zdravotníctva SR.":
            "Találjon olcsóbb gyógyszert azonos hatóanyaggal. A vényköteles gyógyszerek térítési díjainak összehasonlítása a Szlovák Egészségügyi Minisztérium hivatalos listája alapján.",
        '<meta property="og:title" content="Doplatky liekov – nájdite lacnejší liek">': '<meta property="og:title" content="Gyógyszerek térítési díja – találjon olcsóbbat">',
        "Rovnaká účinná látka, nižší doplatok. Porovnajte doplatky za lieky na predpis.": "Azonos hatóanyag, alacsonyabb térítési díj. Hasonlítsa össze a vényköteles gyógyszerek térítési díját.",
        "Porovnanie doplatkov za lieky hradené zdravotnou poisťovňou podľa údajov MZ SR.": "A szlovákiai egészségbiztosító által támogatott gyógyszerek térítési díjainak összehasonlítása.",
        "<title>Doplatky liekov – nájdite lacnejší liek</title>": "<title>Gyógyszerek térítési díja Szlovákiában – találjon olcsóbbat</title>",
        "<h1>Rovnaká účinná látka, <em>nižší doplatok.</em></h1>": "<h1>Azonos hatóanyag, <em>alacsonyabb térítési díj.</em></h1>",
        "Zadajte názov lieku z balenia alebo receptu. Ukážeme lieky s rovnakou látkou, ktoré poisťovňa hradí rovnako, a koľko za ne doplatíte.":
            "Írja be a gyógyszer nevét a dobozról vagy a receptről. Megmutatjuk az azonos hatóanyagú gyógyszereket, amelyeket a biztosító egyformán térít, és hogy mennyit fizet értük a gyógyszertárban.",
        ">Hľadať liek alebo účinnú látku<": ">Gyógyszer vagy hatóanyag keresése<",
        'placeholder="napr. Concor, Controloc, metformín"': 'placeholder="pl. Concor, Controloc, metformin"',
        'aria-label="Nájdené lieky"': 'aria-label="Talált gyógyszerek"',
        'aria-label="Príklady"': 'aria-label="Példák"',
        'aria-label="Rýchle odkazy"': 'aria-label="Gyorslinkek"',
        ">Bežné tablety a kapsuly<": ">Gyakori tabletták és kapszulák<",
        "<h2>Kde sa najviac preplatí</h2>": "<h2>Hol fizet a legtöbbet feleslegesen</h2>",
        "<h2>Časté ochorenia</h2>": '<h2>Gyakori betegségek <small class="mono">(szlovákul)</small></h2>',
        ">Všetky ochorenia →<": ">Összes betegség →<",
        "<h2>Ako to funguje</h2>": "<h2>Hogyan működik</h2>",
        '<details><summary>Ako vymeniť liek za lacnejší</summary><p>Opýtajte sa lekárnika na lacnejšiu alternatívu. Môže vám ju vydať, ak lekár na recepte nevyznačil, že liek sa nesmie zamieňať. Pri pochybnostiach sa poraďte s lekárom.</p></details>':
            '<details><summary>Hogyan cserélhető olcsóbbra a gyógyszer</summary><p>Kérdezze meg a gyógyszerészt olcsóbb alternatíváról. Kiadhatja, ha az orvos a recepten nem jelölte, hogy a gyógyszer nem cserélhető. Kétség esetén beszéljen orvosával.</p></details>',
        '<details><summary>Čo znamená doplatok</summary><p>Je to maximálna suma, ktorú zaplatíte v lekárni. Zvyšok konečnej ceny hradí zdravotná poisťovňa. Lekáreň vám môže dať zľavu, takže zaplatíte aj menej. Voľnopredajné lieky v úradnom zozname nie sú.</p></details>':
            '<details><summary>Mi a térítési díj (doplatok)</summary><p>A gyógyszertárban fizetendő legmagasabb összeg. A végső ár többi részét az egészségbiztosító fizeti. A gyógyszertár kedvezményt is adhat. A vény nélküli gyógyszerek nem szerepelnek a hivatalos listában.</p></details>',
        '<details><summary>Čo sú generiká</summary><p>Generikum obsahuje rovnakú účinnú látku v rovnakej sile ako originál a musí mať preukázaný rovnaký účinok. Líši sa výrobcom, názvom, obalom a často cenou. <a href="/clanky/co-su-generika/">Viac o generikách</a></p></details>':
            '<details><summary>Mik a generikumok</summary><p>A generikum ugyanazt a hatóanyagot tartalmazza ugyanolyan erősségben, mint az eredeti gyógyszer, és igazoltan ugyanúgy hat. Gyártójában, nevében, csomagolásában és gyakran árában különbözik.</p></details>',
        '<details><summary>Ochranný limit</summary><p>Dôchodcom, ľuďom s preukazom ŤZP a malým deťom vracia poisťovňa doplatky nad štvrťročný limit. <a href="/ochranny-limit/">Koľko vám vrátia</a></p></details>':
            '<details><summary>Védelmi limit</summary><p>A nyugdíjasoknak, a ŤZP igazolvánnyal rendelkezőknek és a kisgyermekeknek a biztosító visszatéríti a negyedéves limit feletti térítési díjakat. <a href="/hu/vedelmi-limit/">Mennyit kaphat vissza</a></p></details>',
        "t[0] === 'O' ? 'Originál' : /B/.test(t) ? 'Biologický' : /G/.test(t) ? 'Generikum' : ''": "t[0] === 'O' ? 'Originális' : /B/.test(t) ? 'Biológiai' : /G/.test(t) ? 'Generikum' : ''",
        "'Porovnanie doplatkov'": "'Térítési díjak összehasonlítása'",
        "list.length + (list.length === 1 ? ' liek v skupine' : list.length < 5 ? ' lieky v skupine' : ' liekov v skupine')": "list.length + ' gyógyszer a csoportban'",
        "el('a', 'detail-link', 'Stránka lieku ' + item.name + ' →')": "el('a', 'detail-link', item.name + ' – részletek →')",
        "p.append('Za ', Object.assign(el('strong'), { textContent: item.name }), ' doplácate ' + eur(item.dop) + '. Najlacnejšia alternatíva je ', Object.assign(el('strong'), { textContent: cheapest.name }), ' za ' + eur(cheapest.dop) + '.');":
            "p.append('A(z) ', Object.assign(el('strong'), { textContent: item.name }), ' térítési díja ' + eur(item.dop) + '. A legolcsóbb alternatíva: ', Object.assign(el('strong'), { textContent: cheapest.name }), ', ' + eur(cheapest.dop) + '.');",
        "el('small', null, 'na jednom balení')": "el('small', null, 'csomagonként')",
        "list.length > 1 ? ' už patrí medzi najlacnejšie lieky v tejto skupine. Doplatok ' + eur(item.dop) + '.' : ' nemá v zozname inú verziu s rovnakou látkou, silou a balením.'":
            "list.length > 1 ? ' már a legolcsóbbak közé tartozik ebben a csoportban. Térítési díj: ' + eur(item.dop) + '.' : ' gyógyszernek nincs más változata azonos hatóanyaggal, erősséggel és kiszereléssel.'",
        "'Balení za rok'": "'Csomag évente'",
        "'Menej balení'": "'Kevesebb csomag'",
        "'Viac balení'": "'Több csomag'",
        "res.replaceChildren('Ročne ušetríte ',": "res.replaceChildren('Éves megtakarítás: ',",
        "'tag best', 'Najnižší'": "'tag best', 'Legalacsonyabb'",
        "'tag zero', 'Bez doplatku'": "'tag zero', 'Térítésmentes'",
        "' · poisťovňa hradí '": "' · a biztosító fizeti: '",
        "'Doplatok je maximálna suma v lekárni. Poisťovňa hradí pri všetkých liekoch v skupine rovnakú alebo podobnú sumu. Kliknutím na liek otvoríte jeho stránku s podrobnosťami.'":
            "'A térítési díj a gyógyszertárban fizetendő legmagasabb összeg. A biztosító a csoport minden gyógyszerére azonos vagy hasonló összeget fizet. Kattintson egy gyógyszerre a részletes adatokért.'",
        "'Nenašli sme liek s týmto názvom. Skúste názov účinnej látky.'": "'Nem találtunk ilyen nevű gyógyszert. Próbálja a hatóanyag nevével.'",
        "el('small', null, 'na balení')": "el('small', null, 'csomagonként')",
        "Údaje o liekoch sa nepodarilo načítať. Obnovte stránku.": "A gyógyszeradatokat nem sikerült betölteni. Frissítse az oldalt.",
        "<span>Odfotiť krabičku alebo recept</span>": "<span>A doboz vagy a recept lefényképezése</span>",
        "Liek rozpozná umelá inteligencia. Fotku neukladáme. Na recepte zakryte meno a rodné číslo.": "A gyógyszert mesterséges intelligencia ismeri fel. A fotót nem tároljuk. A recepten takarja le a nevét és a születési számát.",
    },
    "tiles": lambda nd, n_vyp, n_zero: [
        ("/hu/asszisztens/", "spark", "MI asszisztens", "Kérdezzen saját szavaival a gyógyszerekről és a térítési díjakról", ""),
        ("/moje-lieky/", "mine", "Gyógyszereim (SK)", "Mentse el gyógyszereit, kövesse a díjakat és a kieséseket", ""),
        ("/zmeny/", "trend", f"Változások {nd}" if nd else "Változások", "Mi lesz olcsóbb és drágább (szlovákul)", ""),
        ("/vypadky/", "alert", "Szállítási kiesések", f"{n_vyp} gyógyszer szállítása szünetel (szlovákul)", " warn"),
        ("/bez-doplatku/", "zero", "Térítésmentes gyógyszerek", f"{n_zero} gyógyszer teljesen támogatott (szlovákul)", ""),
        ("/hu/vedelmi-limit/", "shield", "Védelmi limit", "Mennyit térít vissza a biztosító", ""),
    ],
}


UK = {
    "code": "uk", "locale": "uk_UA", "num": "uk-UA", "self": "Українська версія",
    "root": "/uk/", "drug": "/uk/liky/", "ai": "/uk/asystent/", "limit": "/uk/zakhysnyi-limit/",
    "date": _uk_date,
    # --- rozloženie ---
    "skip": "Перейти до змісту", "brand_aria": "doplatkyliekov.sk – головна", "nav_aria": "Головна навігація",
    "nav_top": [("/uk/", "Пошук", "", ""), ("/choroby/", "Хвороби (SK)", "", ""),
                ("/zmeny/", "Зміни (SK)", "Зміни", "m"), ("/vypadky/", "Перебої (SK)", "Перебої", "m"),
                ("/bez-doplatku/", "Без доплати (SK)", "Без доплати", "m x-960"), ("/uk/zakhysnyi-limit/", "Захисний ліміт", "Ліміт", "m x-960")],
    "menu": [
        ("Українською", [("/uk/", "Пошук ліків"), ("/uk/asystent/", "ШІ-асистент"), ("/uk/zakhysnyi-limit/", "Захисний ліміт і повернення доплат")]),
        ("Сторінки словацькою", [("/moje-lieky/", "Мої ліки (Moje lieky)"), ("/choroby/", "Ліки за хворобами"),
                                 ("/bez-doplatku/", "Ліки без доплати"), ("/zmeny/", "Зміни доплат"),
                                 ("/vypadky/", "Перебої з постачанням"), ("/vyhody-poistovni/", "Пільги страхових компаній")]),
        ("Про сайт", [("/", "Slovenská verzia"), ("/hu/", "Magyar nyelvű változat"), ("/o-nas/", "Про нас (SK)"), ("/kontakt/", "Контакти (SK)"),
                      ("/ochrana-sukromia/", "Захист даних (SK)"), ("/pristupnost/", "Доступність (SK)")]),
    ],
    "mine": "Мої ліки", "ai_lbl": "ШІ-асистент", "ai_btn_title": "ШІ-асистент – запитайте про ліки та доплати",
    "theme_aria": "Світлий або темний режим", "theme_title": "Світлий / темний режим",
    "disp_aria": "Відображення: колірний режим, розмір шрифту, режим для людей зі слабким зором", "disp_title": "Відображення",
    "disp_lbl": "Відображення", "menu_lbl": "Меню",
    "menu_h": "Меню", "menu_close": "Закрити меню", "menu_disp": "Відображення: світлий режим, шрифт, для людей зі слабким зором", "menu_all": "Усі сторінки",
    "disp_h": "Відображення", "disp_close": "Закрити налаштування", "theme_legend": "Колірний режим",
    "t_dark": "Темний", "t_light": "Світлий", "t_auto": "Як на пристрої", "fs": "Розмір шрифту", "fs_minus": "Зменшити шрифт", "fs_plus": "Збільшити шрифт",
    "contrast": "Режим для людей зі слабким зором",
    "contrast_desc": "Високий контраст, більший і чіткіший шрифт, підкреслені посилання, без анімацій і прозорих ефектів.",
    "reset": "Відновити початкове відображення", "set_note": "Налаштування зберігається лише в цьому браузері.",
    "bottom": [("/uk/", "Пошук", "search"), ("/moje-lieky/", "Мої ліки", "mine"), ("/uk/asystent/", "Асистент", "spark"),
               ("/uk/zakhysnyi-limit/", "Ліміт", "shield")],
    "bottom_aria": "Швидкі посилання", "foot_aria": "Інші сторінки",
    "foot_src": "Джерело: Перелік категоризованих ліків Міністерства охорони здоров'я Словаччини (чинний з {platnost}) та повідомлення ŠÚKL про постачання ліків. Ціни в євро з ПДВ.",
    "foot_disc": "Сайт має інформаційний характер, не є рекламою ліків і не замінює пораду лікаря чи фармацевта. Порядок ліків визначає виключно розмір доплати.",
    "crumbs_aria": "Навігація", "home_lbl": "Головна", "illus_note": "Ілюстрація",
    # --- stránka lieku ---
    "types": {"Originál": "Оригінал", "Generikum": "Генерик", "Biologický": "Біологічний"}, "type_default": "Ліки",
    "tag_best": "Найнижча", "tag_zero": "Без доплати", "tag_vyp": "Перебої", "price_row": "ціна {}",
    "desc_save": "{name} ({pk}): доплата {dop}. Дешевша альтернатива з тією ж діючою речовиною: {cname} {cdop}. Економія {save} на одній упаковці.",
    "verdict_save": "Доплата за <strong>{name}</strong> становить {dop}. Найдешевша альтернатива з тією ж діючою речовиною, дозуванням і упаковкою: <strong>{clink}</strong>, {cdop}.",
    "per_pack": "на упаковці",
    "desc_cheap": "{name} ({pk}): доплата {dop}, одні з найдешевших ліків у групі ({s}).",
    "verdict_cheap": "<strong>{name}</strong> уже належить до найдешевших у цій групі. Доплата: {dop}.",
    "desc_single": "{name} ({pk}): доплата {dop}, кінцева ціна {konc}. Діюча речовина: {s}.",
    "verdict_single": "Ліки <strong>{name}</strong> не мають іншої версії з тією ж діючою речовиною, дозуванням і упаковкою.",
    "vyp": {"R": "Постачання призупинено", "Z": "Постачання припинено", "PR": "Оголошено призупинення постачання", "PZ": "Оголошено припинення постачання"},
    "vyp_text": "За повідомленням власника реєстраційного посвідчення, з {od}.{extra}",
    "vyp_alt": " Доступна альтернатива: {link} ({dop}).",
    "gone_title": "З {nd} ліки виключають зі списку, який компенсує страхова компанія",
    "gone_text": "З цього дня страхова компанія може їх не компенсувати. Порадьтеся з лікарем щодо заміни.",
    "change_title": "З {nd} доплата {verb}: {dop}", "up": "зросте", "down": "знизиться", "change_now": "Зараз {dop}.",
    "hist_h": "Як змінювалася доплата", "lo": "Найнижча", "hi": "Найвища", "now": "Зараз",
    "f_who": "Хто може виписати", "only_spec": "Лише лікар-спеціаліст: {list} <small>(спеціальність словацькою)</small>", "any_doc": "Будь-який лікар, зокрема загальної практики",
    "f_io": "Обмеження за показаннями", "io_val": "Так, страхова компанія компенсує лише при певних захворюваннях",
    "f_gp": "Рецепт", "gp_val": "Виписується за назвою діючої речовини<small>В аптеці можна вибрати будь-які ліки з цією речовиною, наприклад найдешевші.</small>",
    "f_lim": "Захисний ліміт", "lim_val": 'До ліміту зараховується {pdop}<small><a href="{limit}">Як працює захисний ліміт</a></small>',
    "f_subst": "Діюча речовина", "f_drz": "Власник реєстраційного посвідчення", "f_kod": "Код ŠÚKL / ATC",
    "qs": ["Чи є дешевша альтернатива цим лікам?", "Скільки зараховується до захисного ліміту?", "Хто може мені їх виписати?"],
    "ai_h": "Запитайте ШІ-асистента", "ai_aria": "Запитання до асистента",
    "ai_hint": "Відповідає штучний інтелект на основі даних цього сайту. Не замінює лікаря чи фармацевта.",
    "eyebrow": "Доплата за ліки", "mine_add": "Зберегти в Мої ліки", "subst_eyebrow": "Діюча речовина",
    "prices": ("Доплата", "Сплачує страхова", "Кінцева ціна"),
    "slip_foot": "Порівняння ліків з тією ж діючою речовиною, дозуванням і упаковкою ({n}). Доплата – максимальна сума, яку ви сплатите в аптеці.",
    "about_h": "Про ліки",
    "notes": [("Як замінити ліки", "Запитайте фармацевта про дешевшу альтернативу. Він може її видати, якщо лікар не зазначив у рецепті, що ліки не можна замінювати. Якщо сумніваєтеся, порадьтеся з лікарем."),
              ("Що таке доплата", "Максимальна сума, яку ви сплатите в аптеці (словацькою doplatok). Решту кінцевої ціни сплачує медична страхова компанія. Аптека може надати знижку.")],
    "drug_title": "{name} ({pk}) – доплата і дешевші альтернативи", "chart_aria": "Як змінювалася доплата",
    # --- asistent ---
    "ai_sugg": ["Яка доплата за Concor 10 mg?", "Чи є дешевша альтернатива до Xarelto 20 mg?",
                "Скільки поверне страхова компанія, якщо я пенсіонер?", "Які ліки від тиску без доплати?",
                "Що зміниться з {next}?", "Яка страхова компанія повертає доплати за ліки для дітей?"],
    "ai_sugg_nonext": "Що зміниться з наступного місяця?",
    "ai_crumb": "ШІ-асистент", "ai_eyebrow": "ШІ-асистент · бета", "ai_h1": "Запитайте про ліки та доплати",
    "ai_sub": "Асистент шукає в усьому вмісті сайту: доплати й дешевші альтернативи, зміни, перебої з постачанням, ліки за хворобами, захисний ліміт і пільги страхових компаній.",
    "ai_notice": '<strong>Відповідає штучний інтелект.</strong> Мовна модель відповідає на основі даних сайту і може помилятися, тому перевіряйте дані на сторінці ліків. Не замінює лікаря чи фармацевта. Не вказуйте своє ім\'я, rodné číslo чи інші особисті дані. <a href="/ochrana-sukromia/#asistent" lang="sk">Захист даних (словацькою)</a>',
    "ai_ctx": "Ліки:", "ai_chat": "Розмова з асистентом", "ai_q": "Ваше запитання", "ai_ph": "Напишіть запитання…",
    "ai_mic": "Запитати голосом", "ai_send": "Надіслати запитання", "ai_try": "Спробуйте запитати", "ai_new": "Нова розмова",
    "ai_title": "ШІ-асистент – запитання про ліки та доплати у Словаччині",
    "ai_desc": "Запитайте ШІ-асистента про доплати за ліки у Словаччині, дешевші альтернативи, перебої з постачанням і захисний ліміт.",
    # --- ochranný limit ---
    "lim_crumb": "Захисний ліміт",
    "lim_title": "Захисний ліміт 2026 – скільки поверне страхова компанія за ліки",
    "lim_desc": "Захисний ліміт (ochranný limit) у Словаччині 2026: ліміти для пенсіонерів, людей з посвідченням ŤZP і дітей, що зараховується, калькулятор.",
    "lim_body": """
  <section class="intro">
    <p class="eyebrow">Захисний ліміт (ochranný limit)</p>
    <h1 class="page-h1">Скільки доплат поверне страхова компанія</h1>
    <p class="page-sub">Пенсіонерам, людям з посвідченням ŤZP (особа з тяжкою інвалідністю), пенсіонерам по інвалідності та малим дітям медична страхова компанія повертає доплати понад квартальний ліміт. Подавати заяву не потрібно.</p>
  </section>
  <section class="card">
    <h2>Калькулятор</h2>
    <form class="calc" id="calc">
      <label for="skupina">Хто ви
        <select id="skupina">
          <option value="dieta">Дитина до 6 років</option>
          <option value="ztp">Людина з посвідченням ŤZP або пенсіонер по інвалідності</option>
          <option value="dochodca" selected>Пенсіонер за віком або достроковий пенсіонер</option>
          <option value="iny">Ніхто з перелічених</option>
        </select>
      </label>
      <label for="prijem" id="prijem-wrap">Ваша пенсія і дохід
        <select id="prijem">
          <option value="nizky">Пенсія не більше 914,40 € на місяць і загальний дохід не більше 2 743,20 € за квартал</option>
          <option value="vyssi" selected>Вищі</option>
        </select>
      </label>
      <label for="suma">Доплати, що зараховуються, за квартал (€)
        <input id="suma" type="number" inputmode="decimal" min="0" step="0.01" value="45">
      </label>
      <p class="result" id="vysledok" aria-live="polite"></p>
    </form>
    <p class="hint">Орієнтовний розрахунок за правилами 2026 року. Точну суму підтвердить медична страхова компанія.</p>
  </section>
  <section class="card">
    <h2>Квартальні ліміти (2026)</h2>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Для кого</th><th>Ліміт</th><th>Умова</th></tr></thead>
      <tbody>
        <tr><td>Дитина до 6 років</td><td class="num">0 €</td><td>Незалежно від доходу. Доплату за найдешевші замінні ліки не сплачуєте навіть в аптеці.</td></tr>
        <tr><td>Людина з посвідченням ŤZP, пенсіонер по інвалідності</td><td class="num">0 €</td><td>Пенсія не більше 914,40 € на місяць і загальний дохід не більше 2 743,20 € за квартал</td></tr>
        <tr><td>Пенсіонер за віком або достроковий пенсіонер</td><td class="num">0 €</td><td>Пенсія не більше 914,40 € на місяць і загальний дохід не більше 2 743,20 € за квартал</td></tr>
        <tr><td>Людина з посвідченням ŤZP, пенсіонер по інвалідності</td><td class="num">12 €</td><td>При вищому доході</td></tr>
        <tr><td>Пенсіонер за віком або достроковий пенсіонер</td><td class="num">30 €</td><td>При вищому доході</td></tr>
      </tbody>
    </table></div>
  </section>
  <section class="prose article">
    <h2>Що зараховується</h2>
    <p>До ліміту зараховується не вся сплачена доплата, а лише <strong>доплата за найдешевші замінні ліки</strong> з тією ж діючою речовиною. Якщо ви обираєте дорожчу марку, різницю сплачуєте самі, і страхова компанія її не поверне. На сторінці кожних ліків видно, скільки зараховується до ліміту.</p>
    <p>Приклад: пенсіонер за віком з пенсією 700 € на місяць і без інших доходів має квартальний дохід 2 100 € (700 × 3). Це менше ніж 2 743,20 €, тому його ліміт 0 €.</p>
    <h2>Як отримати гроші назад</h2>
    <ul>
      <li>Страхова компанія сама підсумовує доплати за даними аптек, чеки надсилати не потрібно.</li>
      <li>Суму понад ліміт повертає протягом 90 днів після закінчення кварталу, зазвичай на банківський рахунок.</li>
      <li>Якщо сума до повернення менша ніж 3 €, вона переноситься на наступний квартал.</li>
    </ul>
    <p>Понад закон страхові компанії мають і власні пільги, наприклад повернення доплат за ліки для дітей: <a href="/vyhody-poistovni/" lang="sk">пільги страхових компаній (словацькою)</a>.</p>
  </section>""",
    "lim_js": {"none": "Законний захисний ліміт на вас не поширюється. Деякі страхові компанії, однак, повертають доплати за власними програмами.",
               "limit": "Ваш ліміт <b>{l}</b> за квартал. ",
               "zero": "Доплату за найдешевші замінні ліки вам не мали б нараховувати вже в аптеці.",
               "back": "Страхова компанія поверне приблизно <b>{b}</b>.",
               "carry": "Переплата {b} менша ніж 3 €, тому переноситься на наступний квартал.",
               "notyet": "Ви не перевищили ліміт, повернення поки що не передбачене."},
    # --- úvodná stránka ---
    "home": {
        "Nájdite lacnejší liek s rovnakou účinnou látkou. Porovnanie doplatkov za lieky na predpis podľa úradného zoznamu Ministerstva zdravotníctva SR.":
            "Знайдіть дешевші ліки з тією ж діючою речовиною. Порівняння доплат за рецептурні ліки у Словаччині за офіційним переліком Міністерства охорони здоров'я.",
        '<meta property="og:title" content="Doplatky liekov – nájdite lacnejší liek">': '<meta property="og:title" content="Доплати за ліки у Словаччині – знайдіть дешевші">',
        "Rovnaká účinná látka, nižší doplatok. Porovnajte doplatky za lieky na predpis.": "Та сама діюча речовина, менша доплата. Порівняйте доплати за рецептурні ліки.",
        "Porovnanie doplatkov za lieky hradené zdravotnou poisťovňou podľa údajov MZ SR.": "Порівняння доплат за ліки, які компенсує словацька медична страхова компанія.",
        "<title>Doplatky liekov – nájdite lacnejší liek</title>": "<title>Доплати за ліки у Словаччині – знайдіть дешевші</title>",
        "<h1>Rovnaká účinná látka, <em>nižší doplatok.</em></h1>": "<h1>Та сама діюча речовина, <em>менша доплата.</em></h1>",
        "Zadajte názov lieku z balenia alebo receptu. Ukážeme lieky s rovnakou látkou, ktoré poisťovňa hradí rovnako, a koľko za ne doplatíte.":
            "Введіть назву ліків з упаковки або рецепта латиницею. Покажемо ліки з тією ж речовиною, які страхова компанія компенсує однаково, і скільки ви за них доплатите в аптеці.",
        ">Hľadať liek alebo účinnú látku<": ">Пошук ліків або діючої речовини<",
        'placeholder="napr. Concor, Controloc, metformín"': 'placeholder="напр. Concor, Controloc, metformin"',
        'aria-label="Nájdené lieky"': 'aria-label="Знайдені ліки"',
        'aria-label="Príklady"': 'aria-label="Приклади"',
        'aria-label="Rýchle odkazy"': 'aria-label="Швидкі посилання"',
        ">Bežné tablety a kapsuly<": ">Поширені таблетки та капсули<",
        "<h2>Kde sa najviac preplatí</h2>": "<h2>Де переплачують найбільше</h2>",
        "<h2>Časté ochorenia</h2>": '<h2>Поширені хвороби <small class="mono">(словацькою)</small></h2>',
        ">Všetky ochorenia →<": ">Усі хвороби →<",
        "<h2>Ako to funguje</h2>": "<h2>Як це працює</h2>",
        '<details><summary>Ako vymeniť liek za lacnejší</summary><p>Opýtajte sa lekárnika na lacnejšiu alternatívu. Môže vám ju vydať, ak lekár na recepte nevyznačil, že liek sa nesmie zamieňať. Pri pochybnostiach sa poraďte s lekárom.</p></details>':
            '<details><summary>Як замінити ліки на дешевші</summary><p>Запитайте фармацевта про дешевшу альтернативу. Він може її видати, якщо лікар не зазначив у рецепті, що ліки не можна замінювати. Якщо сумніваєтеся, порадьтеся з лікарем.</p></details>',
        '<details><summary>Čo znamená doplatok</summary><p>Je to maximálna suma, ktorú zaplatíte v lekárni. Zvyšok konečnej ceny hradí zdravotná poisťovňa. Lekáreň vám môže dať zľavu, takže zaplatíte aj menej. Voľnopredajné lieky v úradnom zozname nie sú.</p></details>':
            '<details><summary>Що таке доплата (doplatok)</summary><p>Максимальна сума, яку ви сплатите в аптеці. Решту кінцевої ціни сплачує медична страхова компанія. Аптека може надати знижку. Ліків без рецепта в офіційному переліку немає.</p></details>',
        '<details><summary>Čo sú generiká</summary><p>Generikum obsahuje rovnakú účinnú látku v rovnakej sile ako originál a musí mať preukázaný rovnaký účinok. Líši sa výrobcom, názvom, obalom a často cenou. <a href="/clanky/co-su-generika/">Viac o generikách</a></p></details>':
            '<details><summary>Що таке генерики</summary><p>Генерик містить ту саму діючу речовину в тому ж дозуванні, що й оригінал, і має доведено таку саму дію. Відрізняється виробником, назвою, упаковкою і часто ціною.</p></details>',
        '<details><summary>Ochranný limit</summary><p>Dôchodcom, ľuďom s preukazom ŤZP a malým deťom vracia poisťovňa doplatky nad štvrťročný limit. <a href="/ochranny-limit/">Koľko vám vrátia</a></p></details>':
            '<details><summary>Захисний ліміт</summary><p>Пенсіонерам, людям з посвідченням ŤZP і малим дітям страхова компанія повертає доплати понад квартальний ліміт. <a href="/uk/zakhysnyi-limit/">Скільки вам повернуть</a></p></details>',
        "t[0] === 'O' ? 'Originál' : /B/.test(t) ? 'Biologický' : /G/.test(t) ? 'Generikum' : ''": "t[0] === 'O' ? 'Оригінал' : /B/.test(t) ? 'Біологічний' : /G/.test(t) ? 'Генерик' : ''",
        "'Porovnanie doplatkov'": "'Порівняння доплат'",
        "list.length + (list.length === 1 ? ' liek v skupine' : list.length < 5 ? ' lieky v skupine' : ' liekov v skupine')": "'Ліків у групі: ' + list.length",
        "el('a', 'detail-link', 'Stránka lieku ' + item.name + ' →')": "el('a', 'detail-link', item.name + ' – докладніше →')",
        "p.append('Za ', Object.assign(el('strong'), { textContent: item.name }), ' doplácate ' + eur(item.dop) + '. Najlacnejšia alternatíva je ', Object.assign(el('strong'), { textContent: cheapest.name }), ' za ' + eur(cheapest.dop) + '.');":
            "p.append('Доплата за ', Object.assign(el('strong'), { textContent: item.name }), ' становить ' + eur(item.dop) + '. Найдешевша альтернатива: ', Object.assign(el('strong'), { textContent: cheapest.name }), ', ' + eur(cheapest.dop) + '.');",
        "el('small', null, 'na jednom balení')": "el('small', null, 'на одній упаковці')",
        "list.length > 1 ? ' už patrí medzi najlacnejšie lieky v tejto skupine. Doplatok ' + eur(item.dop) + '.' : ' nemá v zozname inú verziu s rovnakou látkou, silou a balením.'":
            "list.length > 1 ? ' уже належить до найдешевших у цій групі. Доплата: ' + eur(item.dop) + '.' : ' не має в переліку іншої версії з тією ж речовиною, дозуванням і упаковкою.'",
        "'Balení za rok'": "'Упаковок на рік'",
        "'Menej balení'": "'Менше упаковок'",
        "'Viac balení'": "'Більше упаковок'",
        "res.replaceChildren('Ročne ušetríte ',": "res.replaceChildren('За рік заощадите ',",
        "'tag best', 'Najnižší'": "'tag best', 'Найнижча'",
        "'tag zero', 'Bez doplatku'": "'tag zero', 'Без доплати'",
        "' · poisťovňa hradí '": "' · страхова сплачує '",
        "'Doplatok je maximálna suma v lekárni. Poisťovňa hradí pri všetkých liekoch v skupine rovnakú alebo podobnú sumu. Kliknutím na liek otvoríte jeho stránku s podrobnosťami.'":
            "'Доплата – максимальна сума в аптеці. Страхова компанія сплачує за всі ліки в групі однакову або подібну суму. Натисніть на ліки, щоб відкрити їхню сторінку з подробицями.'",
        "'Nenašli sme liek s týmto názvom. Skúste názov účinnej látky.'": "'Ліків з такою назвою не знайдено. Спробуйте назву діючої речовини латиницею.'",
        "el('small', null, 'na balení')": "el('small', null, 'на упаковці')",
        "Údaje o liekoch sa nepodarilo načítať. Obnovte stránku.": "Не вдалося завантажити дані про ліки. Оновіть сторінку.",
        "<span>Odfotiť krabičku alebo recept</span>": "<span>Сфотографувати упаковку або рецепт</span>",
        "Liek rozpozná umelá inteligencia. Fotku neukladáme. Na recepte zakryte meno a rodné číslo.": "Ліки розпізнає штучний інтелект. Фото ми не зберігаємо. На рецепті закрийте ім'я та rodné číslo.",
    },
    "tiles": lambda nd, n_vyp, n_zero: [
        ("/uk/asystent/", "spark", "ШІ-асистент", "Запитайте своїми словами про ліки та доплати", ""),
        ("/moje-lieky/", "mine", "Мої ліки (SK)", "Збережіть свої ліки, стежте за доплатами і перебоями", ""),
        ("/zmeny/", "trend", f"Зміни з {nd}" if nd else "Зміни доплат", "Що подешевшає і подорожчає (словацькою)", ""),
        ("/vypadky/", "alert", "Перебої з постачанням", f"Ліків з перебоями: {n_vyp} (словацькою)", " warn"),
        ("/bez-doplatku/", "zero", "Ліки без доплати", f"Повністю компенсованих ліків: {n_zero} (словацькою)", ""),
        ("/uk/zakhysnyi-limit/", "shield", "Захисний ліміт", "Скільки поверне страхова компанія", ""),
    ],
}

LANGS = {"hu": HU, "uk": UK}
