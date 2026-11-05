"""Zdravotnícke pomôcky na webe: /pomocky/ (prehľad s vyhľadávaním) a /pomocky/<podskupina>/ (porovnanie doplatkov).

Zdroj: data/zp.json zo scripts/build_zp.py (zoznam kategorizovaných zdravotníckych pomôcok MZ SR, štvrťročný).
"""
import json
import re

UNIT = {"ks": "za kus", "bal": "za balenie", "pár": "za pár", "par": "za pár", "set": "za set"}
# krátke názvy hlavných skupín (plný názov je v zozname ministerstva)
SHORT = {"A": "Obväzy a hojenie rán", "B": "Inkontinencia", "D": "Diabetes", "F": "Stómia", "G": "Kompresívne pančuchy",
         "H": "Prsné epitézy", "J": "Ortézy a ortopedická obuv", "K": "Rehabilitačné a kompenzačné pomôcky",
         "L": "Vozíky, chodúľky, postele", "N": "Načúvacie prístroje", "O": "Zrakové pomôcky"}
POPULAR = ["D3.1", "D12", "D8", "D1", "B3.2", "B1.2", "B2", "G1.1", "J4", "N1.2", "K2.1", "L7"]


def sk(iso):
    return f"{int(iso[8:10])}. {int(iso[5:7])}. {iso[:4]}" if iso and len(iso) >= 10 else ""


def build_zp_pages(c):
    esc, eur, page, write, crumbs, breadcrumb_ld = c["esc"], c["eur"], c["page"], c["write"], c["crumbs"], c["breadcrumb_ld"]
    urls, SITE, DATA, slugify, odb = c["urls"], c["SITE"], c["DATA"], c["slugify"], c.get("odb", {})
    src = DATA / "zp.json"
    if not src.exists():
        return 0
    zp = json.loads(src.read_text(encoding="utf-8"))
    nxt = json.loads((DATA / "zp_next.json").read_text(encoding="utf-8")) if (DATA / "zp_next.json").exists() else None
    od, do = sk(zp["od"]), sk(zp["do"])
    groups = zp["groups"]
    used = set()
    for g in groups:
        base = slugify(g["k"].replace(".", "-") + " " + g["name"], 70) or g["k"].lower().replace(".", "-")
        sl, n = base, 2
        while sl in used:
            sl, n = f"{base}-{n}", n + 1
        used.add(sl)
        g["slug"] = sl
    platnost = f"Zoznam kategorizovaných zdravotníckych pomôcok MZ SR platný od {od} do {do}"

    def odb_names(pr):
        out, need_zp = [], False
        for code in re.split(r"[,\s]+", pr or ""):
            if not code:
                continue
            if code == "ZP":
                need_zp = True
                continue
            out.append(odb.get(code, code).split(" / ")[0])
        return out, need_zp

    def item_li(x):
        name = esc(x["n"]) + (f' <small class="muted">{esc(x["d"])}</small>' if x.get("d") else "")
        unit = UNIT.get(x.get("mj", ""), "")
        tags = []
        if nxt:
            nd = nxt["prices"].get(x["kod"], "gone")
            if nd == "gone":
                tags.append(f'<span class="tag warn">od {sk(nxt["od"])} mimo zoznamu</span>')
            elif nd is not None and x["dop"] is not None and abs(nd - x["dop"]) >= 0.01:
                tags.append(f'<span class="tag {"warn" if nd > x["dop"] else "good"}">od {sk(nxt["od"])}: {eur(nd)}</span>')
        names, need_zp = odb_names(x.get("pr"))
        who = ""
        if names:
            who = "Predpisuje: " + ", ".join(names[:6]) + (" a ďalší" if len(names) > 6 else "") + ". "
        if need_zp:
            who += "Úhrada so súhlasom poisťovne. "
        price = eur(x["dop"]) if x["dop"] is not None else "–"
        sub1 = (f'{esc(x["d"]) + " · " if x.get("d") else ""}{esc(unit)}: cena {eur(x["c"]) if x["c"] is not None else "–"}, '
                f'poisťovňa {eur(x["u"]) if x["u"] is not None else "–"}')
        sub2 = f'{esc(who)}Kód {esc(x["kod"])}{" · výrobca " + esc(x["v"]) if x.get("v") else ""}{" (" + esc(x["st"]) + ")" if x.get("st") else ""}'
        return (f'<li id="{esc(x["kod"])}"><div class="gline"><span class="zn">{esc(x["n"])} {"".join(tags)}</span>'
                f'<span class="mono">{price}</span><small>{sub1}</small><small>{sub2}</small></div></li>')

    # --- stránky podskupín ---
    for g in groups:
        items = g["i"]
        n0 = sum(1 for x in items if x["dop"] is not None and x["dop"] < 0.005)
        vals = [x["dop"] for x in items if x["dop"] is not None]
        letter = g["k"][0]
        parent = g["chain"][-2][1] if len(g["chain"]) >= 2 else zp["skupiny"].get(letter, "")
        crumb_items = [("Domov", "/"), ("Zdravotnícke pomôcky", "/pomocky/"), (g["name"], None)]
        lim = ""
        if g.get("lim"):
            lim = ('<section class="card"><h2>Koľko uhradí poisťovňa</h2><ul class="plain">'
                   + "".join(f"<li>{esc(l)}</li>" for l in g["lim"][:12])
                   + '</ul><p class="hint">Množstvové limity a indikačné obmedzenia podľa časti 2 zoznamu ministerstva. '
                     'Nad limit pomôcku poisťovňa neuhradí.</p></section>')
        summary = (f"V zozname je {len(items)} {'pomôcka' if len(items) == 1 else 'pomôcky' if 2 <= len(items) <= 4 else 'pomôcok'}"
                   f"{f', z toho {n0} bez doplatku' if n0 else ''}.")
        if vals and max(vals) > 0.005:
            summary += f" Doplatok je od {eur(min(vals))} do {eur(max(vals))} {UNIT.get(items[0].get('mj', ''), '')}."
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">{esc(parent)}</p>
    <h1 class="page-h1">{esc(g["name"])}: doplatky</h1>
    <p class="page-sub">{esc(summary)} Zoradené od najnižšieho doplatku.</p>
  </section>
  <section class="card"><h2>Pomôcky a doplatky</h2><ul class="glist">{''.join(item_li(x) for x in items)}</ul>
  <p class="hint">Doplatok je maximálny, výdajňa ho môže znížiť. Cena a úhrada sú uvedené {esc(UNIT.get(items[0].get('mj', ''), 'za jednotku'))}, ako ich uvádza ministerstvo.</p></section>
  {lim}
  <section class="card"><h2>Ako pomôcku dostať</h2><p>Pomôcku predpisuje lekár s odbornosťou uvedenou pri pomôcke, zvyčajne na poukaz. Vydá ju lekáreň alebo výdajňa zdravotníckych pomôcok. Ak doplácate, opýtajte sa na pomôcku z rovnakej skupiny bez doplatku, poisťovňa na ne prispieva rovnako.</p>
  <p><a href="/lekarne/?typ={'optiky' if letter in ('N', 'O') else 'pomocky'}">Kde ju vydajú: {'optiky a načúvacie prístroje' if letter in ('N', 'O') else 'výdajne pomôcok'} v okolí</a> · <a href="/lekarne/">lekárne v okolí</a>{'' if not g.get('lim') else ' · schválenie nad limit vybavíte na <a href="/lekarne/?typ=poistovne">pobočke poisťovne</a>'}</p></section>
  <p class="hint">Zdroj: {esc(platnost)}. <a href="/pomocky/">Všetky skupiny pomôcok</a></p>"""
        desc = f"{g['name']}: {summary} Podľa zoznamu ministerstva zdravotníctva platného od {od}."
        write(f"/pomocky/{g['slug']}/", page(f"{g['name']} – doplatky za zdravotnícke pomôcky", desc,
                                             f"/pomocky/{g['slug']}/", body, breadcrumb_ld(crumb_items)))
        urls.append((f"/pomocky/{g['slug']}/", "0.5"))

    # --- prehľad ---
    by_letter = {}
    for g in groups:
        by_letter.setdefault(g["k"][0], []).append(g)
    secs = []
    for letter in sorted(by_letter):
        gl = by_letter[letter]
        blocks, top = [], {}
        for g in gl:
            t = g["chain"][0] if g["chain"] else [g["k"], g["name"]]
            top.setdefault(t[0], [t[1], []])[1].append(g)
        for code, (tname, subs) in top.items():
            lis = []
            for g in subs:
                vals = [x["dop"] for x in g["i"] if x["dop"] is not None]
                n0 = sum(1 for v in vals if v < 0.005)
                lis.append(f'<li><a href="/pomocky/{esc(g["slug"])}/">{esc(g["name"])}</a> '
                           f'<small>{len(g["i"])} v zozname{f", {n0} bez doplatku" if n0 else ""}</small></li>')
            blocks.append(f'<h3>{esc(tname)}</h3><ul class="plain">{"".join(lis)}</ul>')
        secs.append(f'<section class="card" id="skupina-{letter.lower()}"><h2>{esc(SHORT.get(letter, letter))}</h2>'
                    f'<p class="hint">{esc(zp["skupiny"].get(letter, ""))}</p>{"".join(blocks)}</section>')
    pop = []
    idx = {g["k"]: g for g in groups}
    for k in POPULAR:
        g = idx.get(k) or next((x for x in groups if x["k"].startswith(k + ".")), None)
        if g:
            pop.append(f'<a class="chip" href="/pomocky/{esc(g["slug"])}/">{esc(g["name"][:48])}</a>')
    nav = "".join(f'<a class="chip" href="#skupina-{l.lower()}">{esc(SHORT.get(l, l))}</a>' for l in sorted(by_letter))
    n_all = zp.get("pocet") or sum(len(g["i"]) for g in groups)
    n_free = sum(1 for g in groups for x in g["i"] if x["dop"] is not None and x["dop"] < 0.005)
    crumb_items = [("Domov", "/"), ("Zdravotnícke pomôcky", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Platí od {od} do {do}</p>
    <h1 class="page-h1">Zdravotnícke pomôcky: koľko doplatíte</h1>
    <p class="page-sub">Testovacie prúžky, glukózové senzory, inkontinenčné pomôcky, ortézy, vozíky či načúvacie prístroje. V zozname ministerstva je {n_all} pomôcok, {n_free} z nich bez doplatku. Ministerstvo ho mení raz za štvrťrok.</p>
  </section>
  <section class="card">
    <label class="lbl" for="zp-q">Vyhľadať pomôcku</label>
    <input id="zp-q" type="search" autocomplete="off" placeholder="napr. prúžky, Seni, ortéza kolena" class="filter">
    <ul id="zp-out" class="plain" aria-live="polite"></ul>
    <p class="hint">Najčastejšie hľadané:</p><div class="chips">{''.join(pop)}</div>
  </section>
  <nav class="chips" aria-label="Skupiny pomôcok">{nav}</nav>
  {''.join(secs)}
  <p class="hint">Zdroj: <a href="https://www.health.gov.sk/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-zdravotnickych-pomocok/" rel="nofollow">{esc(platnost)}</a>. Doplatky sú maximálne, výdajňa ich môže znížiť.</p>"""
    write("/pomocky/", page("Zdravotnícke pomôcky – doplatky a úhrada poisťovne",
                            f"Doplatky za {n_all} zdravotníckych pomôcok: testovacie prúžky, senzory, inkontinenčné pomôcky, ortézy, vozíky. "
                            f"{n_free} bez doplatku. Podľa zoznamu ministerstva od {od}.",
                            "/pomocky/", body, breadcrumb_ld(crumb_items), script='<script src="/pomocky.js" defer></script>'))
    urls.append(("/pomocky/", "0.7"))
    # vyhľadávanie: [skupiny [slug, názov]], [položky [text, index skupiny, doplatok, kód]]
    gl = [[g["slug"], g["name"]] for g in groups]
    il = [[(x["n"] + " " + (x.get("d") or "")).strip(), gi, x["dop"], x["kod"]] for gi, g in enumerate(groups) for x in g["i"]]
    (SITE / "pomocky.json").write_text(json.dumps({"g": gl, "i": il}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(groups)
