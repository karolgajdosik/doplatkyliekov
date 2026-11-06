"""Dietetické potraviny na webe: /dieteticke-potraviny/ (prehľad s vyhľadávaním) a /dieteticke-potraviny/<skupina>/.

Zdroj: data/dp.json zo scripts/build_dp.py (zoznam kategorizovaných dietetických potravín MZ SR, štvrťročný).
"""
import json
import re

BASE = "/dieteticke-potraviny/"
SHORT = {"V06C": "Metabolické ochorenia (fenylketonúria a iné)", "V06D": "Dojčenská výživa", "V06E": "Enterálna výživa (sondová a sipping)"}
INTRO = {
    "V06C": "Potraviny pri dedičných poruchách metabolizmu, napríklad fenylketonúrii, a nízkoproteínové či bezgluténové suroviny.",
    "V06D": "Špeciálna dojčenská výživa pri alergii na bielkovinu kravského mlieka, refluxe, nezrelosti alebo poruchách metabolizmu.",
    "V06E": "Výživa podávaná ústami (sipping) alebo sondou pri podvýžive, onkologických, obličkových či pečeňových ochoreniach.",
}
SU = {"I": "plne hradené", "S": "čiastočne hradené"}


def sk(iso):
    return f"{int(iso[8:10])}. {int(iso[5:7])}. {iso[:4]}" if iso and len(iso) >= 10 else ""


def build_dp_pages(c):
    esc, eur, page, write, crumbs, breadcrumb_ld = c["esc"], c["eur"], c["page"], c["write"], c["crumbs"], c["breadcrumb_ld"]
    urls, SITE, DATA, slugify, odb = c["urls"], c["SITE"], c["DATA"], c["slugify"], c.get("odb", {})
    src = DATA / "dp.json"
    if not src.exists():
        return 0
    dp = json.loads(src.read_text(encoding="utf-8"))
    nxt = json.loads((DATA / "dp_next.json").read_text(encoding="utf-8")) if (DATA / "dp_next.json").exists() else None
    od, do = sk(dp["od"]), sk(dp["do"])
    groups = dp["groups"]
    used = set()
    for g in groups:
        base = slugify(g["name"], 70) or g["k"].lower()
        sl, n = base, 2
        while sl in used:
            sl, n = f"{base}-{n}", n + 1
        used.add(sl)
        g["slug"] = sl
    platnost = f"Zoznam kategorizovaných dietetických potravín MZ SR platný od {od} do {do}"

    def who(pr):
        codes = [x for x in re.split(r"[,\s]+", pr or "") if x]
        names = [odb.get(x, x).split(" / ")[0] for x in codes]
        return ("Predpisuje: " + ", ".join(names[:6]) + (" a ďalší" if len(names) > 6 else "") + ". ") if names else ""

    def item_li(x):
        tags = []
        if nxt:
            nd = nxt["prices"].get(x["kod"], "gone")
            if nd == "gone":
                tags.append(f'<span class="tag warn">od {sk(nxt["od"])} mimo zoznamu</span>')
            elif nd is not None and x["dop"] is not None and abs(nd - x["dop"]) >= 0.01:
                tags.append(f'<span class="tag {"warn" if nd > x["dop"] else "good"}">od {sk(nxt["od"])}: {eur(nd)}</span>')
        if x.get("io"):
            tags.append('<span class="tag">len pri určenej diagnóze</span>')
        price = eur(x["dop"]) if x["dop"] is not None else "–"
        sub1 = (f'{esc(x["d"]) + " · " if x.get("d") else ""}cena {eur(x["c"]) if x["c"] is not None else "–"}, '
                f'poisťovňa {eur(x["u"]) if x["u"] is not None else "–"}'
                f'{" · " + str(int(x["kcal"])) + " kcal/100 g" if x.get("kcal") else ""}')
        sub2 = (f'{esc(who(x.get("pr")))}{"Množstvo je limitované. " if x.get("lim") else ""}Kód {esc(x["kod"])}'
                f'{" · výrobca " + esc(x["v"]) if x.get("v") else ""}')
        return (f'<li id="{esc(x["kod"])}"><div class="gline"><span class="zn">{esc(x["n"])} {"".join(tags)}</span>'
                f'<span class="mono">{price}</span><small>{sub1}</small><small>{sub2}</small></div></li>')

    for g in groups:
        items = g["i"]
        n0 = sum(1 for x in items if x["dop"] is not None and x["dop"] < 0.005)
        vals = [x["dop"] for x in items if x["dop"] is not None]
        parent = g["chain"][1][1] if len(g["chain"]) > 1 else dp["skupiny"].get(g["k"][:4], "")
        crumb_items = [("Domov", "/"), ("Dietetické potraviny", BASE), (g["name"][:60], None)]
        word = "potravina" if len(items) == 1 else "potraviny" if 2 <= len(items) <= 4 else "potravín"
        summary = f"V zozname je {len(items)} {word}{f', z toho {n0} bez doplatku' if n0 else ''}."
        if vals and max(vals) > 0.005:
            summary += f" Doplatok je od {eur(min(vals))} do {eur(max(vals))} za balenie."
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">{esc(parent)}</p>
    <h1 class="page-h1">{esc(g["name"])}: doplatky</h1>
    <p class="page-sub">{esc(summary)} Zoradené od najnižšieho doplatku.</p>
  </section>
  <section class="card"><h2>Potraviny a doplatky</h2><ul class="glist">{''.join(item_li(x) for x in items)}</ul>
  <p class="hint">Doplatok je maximálny za balenie, lekáreň ho môže znížiť.</p></section>
  <section class="card"><h2>Ako ju dostať</h2><p>Dietetickú potravinu predpisuje lekár so špecializáciou uvedenou pri potravine, často len pri určenej diagnóze a v obmedzenom množstve za mesiac. Vydá ju lekáreň. Ak doplácate, opýtajte sa lekára na potravinu z rovnakej skupiny bez doplatku.</p>
  <p><a href="/lekarne/">Lekárne v okolí</a> · <a href="/vyhody-poistovni/">výhody poisťovní na doplatky</a></p></section>
  <p class="hint">Zdroj: {esc(platnost)}. <a href="{BASE}">Všetky skupiny dietetických potravín</a></p>"""
        desc = f"{g['name']}: {summary} Podľa zoznamu ministerstva zdravotníctva platného od {od}."
        write(f"{BASE}{g['slug']}/", page(f"{g['name'][:70]} – doplatky", desc, f"{BASE}{g['slug']}/", body, breadcrumb_ld(crumb_items)))
        urls.append((f"{BASE}{g['slug']}/", "0.4"))

    secs = []
    for top in sorted(dp["skupiny"]):
        sub = {}
        for g in groups:
            if not g["k"].startswith(top):
                continue
            t = g["chain"][1] if len(g["chain"]) > 1 else [g["k"], g["name"]]
            sub.setdefault(t[0], [t[1], []])[1].append(g)
        if not sub:
            continue
        blocks = []
        for code in sorted(sub):
            tname, gs = sub[code]
            lis = []
            for g in gs:
                n0 = sum(1 for x in g["i"] if x["dop"] is not None and x["dop"] < 0.005)
                lis.append(f'<li><a href="{BASE}{esc(g["slug"])}/">{esc(g["name"])}</a> '
                           f'<small>{len(g["i"])} v zozname{f", {n0} bez doplatku" if n0 else ""}</small></li>')
            blocks.append(f'<h3>{esc(tname)}</h3><ul class="plain">{"".join(lis)}</ul>')
        secs.append(f'<section class="card" id="skupina-{top.lower()}"><h2>{esc(SHORT.get(top, top))}</h2>'
                    f'<p class="hint">{esc(INTRO.get(top, ""))}</p>{"".join(blocks)}</section>')
    nav = "".join(f'<a class="chip" href="#skupina-{t.lower()}">{esc(SHORT[t])}</a>' for t in sorted(dp["skupiny"]) if t in SHORT)
    n_all = dp.get("pocet") or sum(len(g["i"]) for g in groups)
    n_free = sum(1 for g in groups for x in g["i"] if x["dop"] is not None and x["dop"] < 0.005)
    crumb_items = [("Domov", "/"), ("Dietetické potraviny", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Platí od {od} do {do}</p>
    <h1 class="page-h1">Dietetické potraviny: koľko doplatíte</h1>
    <p class="page-sub">Enterálna výživa (sipping, sondová výživa), špeciálna dojčenská výživa a potraviny pri fenylketonúrii a iných poruchách metabolizmu. V zozname ministerstva je {n_all} potravín, {n_free} z nich bez doplatku. Ministerstvo ho mení raz za štvrťrok.</p>
  </section>
  <section class="card">
    <label class="lbl" for="zp-q">Vyhľadať potravinu</label>
    <input id="zp-q" type="search" autocomplete="off" placeholder="napr. Nutridrink, Fresubin, Nutrilon, PKU" class="filter" data-src="/dp.json" data-base="{BASE}">
    <ul id="zp-out" class="plain" aria-live="polite"></ul>
  </section>
  <nav class="chips" aria-label="Skupiny potravín">{nav}</nav>
  {''.join(secs)}
  <p class="hint">Zdroj: <a href="https://www.health.gov.sk/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-dietetickych-potravin/" rel="nofollow">{esc(platnost)}</a>. Doplatky sú maximálne, lekáreň ich môže znížiť.</p>"""
    write(BASE, page("Dietetické potraviny – doplatky a úhrada poisťovne",
                     f"Doplatky za {n_all} dietetických potravín: enterálna výživa, dojčenská výživa, potraviny pri fenylketonúrii. "
                     f"{n_free} bez doplatku. Podľa zoznamu ministerstva od {od}.",
                     BASE, body, breadcrumb_ld(crumb_items), script='<script src="/pomocky.js" defer></script>'))
    urls.append((BASE, "0.6"))
    gl = [[g["slug"], g["name"]] for g in groups]
    il = [[(x["n"] + " " + (x.get("d") or "")).strip(), gi, x["dop"], x["kod"]] for gi, g in enumerate(groups) for x in g["i"]]
    (SITE / "dp.json").write_text(json.dumps({"g": gl, "i": il}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(groups)
