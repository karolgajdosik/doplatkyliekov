"""Vygeneruje statické podstránky pre Google zo site/data.json.

- /liek/<slug>/      stránka pre každé balenie lieku s lacnejšími alternatívami
- /latka/<slug>/     prehľad všetkých síl a balení jednej účinnej látky
- /lieky/            abecedný zoznam účinných látok
- /404.html, /sitemap.xml, /assets/style.css

Používa iba štandardnú knižnicu Pythonu, takže beží aj ako build príkaz v Cloudflare Pages:
  python3 scripts/build_pages.py
"""
import html
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://doplatkyliekov.sk"
GENERATED = ["liek", "latka", "lieky", "assets"]


# ---------- pomocné funkcie ----------

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def slugify(s, limit=60):
    s = re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")
    return s[:limit].rstrip("-")


def product_slug(name, kod):
    # rovnaká logika je v site/index.html (funkcia productSlug)
    return f"{slugify(name)}-{slugify(kod)}"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def eur(n):
    if n is None:
        return "–"
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",")
    return s + " €"


def type_label(t):
    if not t:
        return ""
    if t[0] == "O":
        return "Originál"
    if "B" in t:
        return "Biologický"
    if "G" in t:
        return "Generikum"
    return ""


def short_pack(pack):
    return re.sub(r"\s*\(.*$", "", pack or "").strip()


def plural_lieky(n):
    if n == 1:
        return "1 liek"
    if 2 <= n <= 4:
        return f"{n} lieky"
    return f"{n} liekov"


# ---------- šablóny ----------

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@500;600;700'
         '&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')

ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 28'%3E%3Crect x='10' y='2' "
        "width='8' height='24' rx='2' fill='%230f6b4f'/%3E%3Crect x='2' y='10' width='24' height='8' rx='2' "
        "fill='%230f6b4f'/%3E%3C/svg%3E")

EXTRA_CSS = """
a { color: var(--accent); }
.crumbs { display: flex; flex-wrap: wrap; gap: 4px 8px; font-size: 14px; color: var(--muted); }
.crumbs a { color: var(--muted); text-decoration: none; }
.crumbs a:hover { color: var(--accent); text-decoration: underline; }
.crumbs span[aria-hidden] { opacity: .6; }
.brand-link { display: flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; }
.page-h1 { font-size: clamp(28px, 5.5vw, 40px); line-height: 1.1; font-weight: 700; }
.page-sub { color: var(--muted); }
.row-name a { color: var(--ink); text-decoration: none; }
.row-name a:hover { color: var(--accent); text-decoration: underline; }
.row { cursor: default; }
.prices { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--line); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.prices div { background: var(--surface); padding: 12px 20px; display: grid; gap: 2px; }
.prices span { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
.prices b { font-family: var(--font-mono); font-weight: 500; font-size: 18px; }
.prices b.dop { color: var(--save); }
.cta { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; text-decoration: none; color: var(--accent); }
.cta:hover { text-decoration: underline; }
.glist { list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: var(--r); overflow: hidden; }
.glist li { background: var(--surface); padding: 14px 16px; display: grid; gap: 6px; }
.glist h3 { font-size: 17px; font-weight: 600; }
.glist .gline { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 12px; font-size: 14px; }
.glist .gline a { min-width: 0; overflow-wrap: anywhere; }
.glist .gline .mono { white-space: nowrap; }
.glist .save { color: var(--save); font-weight: 600; font-size: 13px; }
.az { display: flex; flex-wrap: wrap; gap: 6px; }
.az a { font-family: var(--font-mono); padding: 4px 9px; border: 1px solid var(--line); border-radius: 6px; text-decoration: none; color: var(--ink); }
.az a:hover { border-color: var(--accent); color: var(--accent); }
.letter { display: grid; gap: 8px; scroll-margin-top: 16px; }
.letter h2 { font-size: 22px; }
.cols { columns: 2 220px; column-gap: 24px; margin: 0; padding: 0; list-style: none; }
.cols li { break-inside: avoid; padding: 3px 0; }
.cols small { color: var(--muted); }
@media (max-width: 600px) { .prices { grid-template-columns: 1fr; } .prices div { padding-left: 16px; padding-right: 16px; } }
"""


def extract_css():
    page = (SITE / "index.html").read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", page, re.S)
    if not m:
        raise SystemExit("V site/index.html chýba <style>.")
    return m.group(1) + EXTRA_CSS


def page(title, description, path, body, jsonld=None):
    url = BASE + path
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
<link rel="icon" href="{ICON}">
{FONTS}
<link rel="stylesheet" href="/assets/style.css">
{ld}
</head>
<body>
<div class="wrap">
  <header>
    <a class="brand-link" href="/">
      <svg class="cross" viewBox="0 0 28 28" aria-hidden="true"><rect x="10" y="2" width="8" height="24" rx="2" fill="var(--accent)"/><rect x="2" y="10" width="24" height="8" rx="2" fill="var(--accent)"/></svg>
      <span class="brand-name">doplatkyliekov.sk</span>
    </a>
  </header>
{body}
  <footer>
    <p><a href="/">Vyhľadať liek</a> · <a href="/lieky/">Zoznam účinných látok</a></p>
    <p>Zdroj: Zoznam kategorizovaných liekov Ministerstva zdravotníctva SR, platný od {esc(PLATNOST)}. Ceny sú v eurách s DPH.</p>
    <p>Stránka slúži na informáciu a nenahrádza radu lekára ani lekárnika.</p>
  </footer>
</div>
</body>
</html>
"""


def crumbs(items):
    parts = []
    for i, (label, href) in enumerate(items):
        if i:
            parts.append('<span aria-hidden="true">›</span>')
        parts.append(f'<a href="{esc(href)}">{esc(label)}</a>' if href else f"<span>{esc(label)}</span>")
    return f'  <nav class="crumbs" aria-label="Navigácia">{"".join(parts)}</nav>'


def breadcrumb_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label, **({"item": BASE + href} if href else {})}
            for i, (label, href) in enumerate(items)
        ],
    }


NOTES = """
  <section class="notes">
    <div class="note">
      <h3>Ako vymeniť liek</h3>
      <p>Opýtajte sa lekárnika na lacnejšiu alternatívu. Môže vám ju vydať, ak lekár na recepte nevyznačil, že liek sa nesmie zamieňať. Pri pochybnostiach sa poraďte s lekárom.</p>
    </div>
    <div class="note">
      <h3>Čo znamená doplatok</h3>
      <p>Je to maximálna suma, ktorú zaplatíte v lekárni. Zvyšok konečnej ceny hradí zdravotná poisťovňa. Lekáreň vám môže dať zľavu, takže zaplatíte aj menej.</p>
    </div>
  </section>"""


# ---------- generovanie ----------

def build():
    global PLATNOST
    data = json.loads((SITE / "data.json").read_text(encoding="utf-8"))
    PLATNOST = data.get("platnost", "")
    lastmod = data.get("platnostIso") or None
    groups = data["groups"]

    for d in GENERATED:
        shutil.rmtree(SITE / d, ignore_errors=True)
    (SITE / "assets").mkdir(parents=True)
    (SITE / "assets" / "style.css").write_text(extract_css(), encoding="utf-8")

    # produkty a látky
    by_subst = defaultdict(list)
    products = []  # (group, item, slug)
    used = set()
    for g in groups:
        g["items"] = []
        for it in g["i"]:
            kod, name, pack, konc, uzp, dop, typ = it[:7]
            slug = product_slug(name, kod)
            n = 2
            base = slug
            while slug in used:
                slug = f"{base}-{n}"
                n += 1
            used.add(slug)
            p = {"kod": kod, "name": name, "pack": pack, "konc": konc, "uzp": uzp, "dop": dop, "typ": typ, "slug": slug}
            g["items"].append(p)
            products.append((g, p))
        by_subst[g["s"]].append(g)

    subst_slug = {}
    for s in by_subst:
        sl = slugify(s, 80) or "latka"
        while sl in subst_slug.values():
            sl += "-x"
        subst_slug[s] = sl

    urls = [("/", "1.0"), ("/lieky/", "0.6")]

    # --- stránky liekov ---
    for g, p in products:
        items = sorted([x for x in g["items"] if x["dop"] is not None], key=lambda x: (x["dop"], norm(x["name"])))
        cheapest = items[0] if items else None
        max_dop = max([x["dop"] for x in items] + [0.01])
        saving = (p["dop"] - cheapest["dop"]) if (cheapest and p["dop"] is not None) else 0
        s_url = f"/latka/{subst_slug[g['s']]}/"
        path = f"/liek/{p['slug']}/"
        pk = short_pack(p["pack"])

        if saving > 0.005:
            desc = (f"Doplatok za {p['name']} ({pk}) je {eur(p['dop'])}. Lacnejšia alternatíva s rovnakou látkou: "
                    f"{cheapest['name']} za {eur(cheapest['dop'])}. Ušetríte {eur(saving)} na balení.")
            verdict = (f'<div class="verdict"><p>Za <strong>{esc(p["name"])}</strong> doplácate {eur(p["dop"])}. '
                       f'Najlacnejšia alternatíva s rovnakou látkou, silou a balením je '
                       f'<strong><a href="/liek/{esc(cheapest["slug"])}/">{esc(cheapest["name"])}</a></strong> za {eur(cheapest["dop"])}.</p>'
                       f'<div class="big">−{eur(saving)}<small>na jednom balení</small></div></div>')
        elif len(items) > 1:
            desc = (f"Doplatok za {p['name']} ({pk}) je {eur(p['dop'])}. Patrí medzi najlacnejšie lieky s látkou "
                    f"{g['s']} v tejto sile a balení. Porovnanie {plural_lieky(len(items))}.")
            verdict = (f'<div class="verdict none"><p><strong>{esc(p["name"])}</strong> už patrí medzi najlacnejšie lieky '
                       f'v tejto skupine. Doplatok {eur(p["dop"])}.</p></div>')
        else:
            desc = (f"Doplatok za {p['name']} ({pk}) je {eur(p['dop'])}, konečná cena {eur(p['konc'])}, "
                    f"poisťovňa hradí {eur(p['uzp'])}. Účinná látka: {g['s']}.")
            verdict = (f'<div class="verdict none"><p><strong>{esc(p["name"])}</strong> nemá v zozname inú verziu '
                       f's rovnakou látkou, silou a balením. Pozrite si <a href="{s_url}">iné sily a balenia látky {esc(g["s"])}</a>.</p></div>')

        rows = []
        for x in items:
            cls = "row" + (" sel" if x is p else "") + (" best" if cheapest and x["dop"] == cheapest["dop"] else "")
            tags = []
            tl = type_label(x["typ"])
            if tl:
                tags.append(f'<span class="tag">{tl}</span>')
            if cheapest and x["dop"] == cheapest["dop"] and len(items) > 1:
                tags.append('<span class="tag best">Najnižší</span>')
            elif x["dop"] == 0:
                tags.append('<span class="tag zero">Bez doplatku</span>')
            name = esc(x["name"]) if x is p else f'<a href="/liek/{esc(x["slug"])}/">{esc(x["name"])}</a>'
            width = round(x["dop"] / max_dop * 100, 1)
            rows.append(
                f'<li class="{cls}"><div class="row-name">{name}<span class="tags">{"".join(tags)}</span></div>'
                f'<div class="row-dop">{eur(x["dop"])}</div><div class="row-pack">{esc(x["pack"])}</div>'
                f'<div class="row-sub">cena {eur(x["konc"])}</div>'
                f'<div class="track"><i style="width:{width}%"></i></div></li>')

        crumb_items = [("Domov", "/"), (g["s"], s_url), (p["name"], None)]
        body = f"""{crumbs(crumb_items)}
  <section style="display:grid;gap:8px">
    <p class="eyebrow">Doplatok za liek</p>
    <h1 class="page-h1">{esc(p['name'])}</h1>
    <p class="page-sub">{esc(p['pack'])}</p>
  </section>
  <section class="slip">
    <div class="slip-head">
      <p class="eyebrow">Účinná látka</p>
      <h2><a href="{s_url}">{esc(g['s'])}</a>, {esc(g['f'])}</h2>
      <div class="slip-meta"><span class="mono">ATC {esc(g['a'])}</span><span class="mono">ŠÚKL {esc(p['kod'])}</span><span>{type_label(p['typ']) or 'Liek'}</span></div>
    </div>
    <div class="prices">
      <div><span>Doplatok pacienta</span><b class="dop">{eur(p['dop'])}</b></div>
      <div><span>Hradí poisťovňa</span><b>{eur(p['uzp'])}</b></div>
      <div><span>Konečná cena</span><b>{eur(p['konc'])}</b></div>
    </div>
    {verdict}
    <ul class="rows">{''.join(rows)}</ul>
    <p class="slip-foot">Porovnanie liekov s rovnakou účinnou látkou, silou a veľkosťou balenia ({plural_lieky(len(items))}). Doplatok je maximálna suma v lekárni.</p>
  </section>
  <p><a class="cta" href="{s_url}">Všetky sily a balenia: {esc(g['s'])} →</a></p>
{NOTES}"""
        title = f"{p['name']} ({pk}) – doplatok a lacnejšie alternatívy"
        out = SITE / path.strip("/")
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page(title, desc, path, body, breadcrumb_ld(crumb_items)), encoding="utf-8")
        urls.append((path, "0.8"))

    # --- stránky látok ---
    for s, gs in by_subst.items():
        path = f"/latka/{subst_slug[s]}/"
        gs_sorted = sorted(gs, key=lambda g: norm(g["f"]))
        best_saving = 0
        lis = []
        for g in gs_sorted:
            items = sorted([x for x in g["items"] if x["dop"] is not None], key=lambda x: (x["dop"], norm(x["name"])))
            if not items:
                continue
            lo, hi = items[0], items[-1]
            gap = hi["dop"] - lo["dop"]
            best_saving = max(best_saving, gap)
            lines = "".join(
                f'<div class="gline"><a href="/liek/{esc(x["slug"])}/">{esc(x["name"])}</a><span class="mono">{eur(x["dop"])}</span></div>'
                for x in items)
            save = (f'<p class="save">Rozdiel v doplatku až {eur(gap)} na balení</p>' if gap > 0.005 else "")
            lis.append(f'<li><h3>{esc(g["f"])}</h3>{save}{lines}</li>')
        n_items = sum(len(g["items"]) for g in gs)
        desc = (f"Doplatky za lieky s účinnou látkou {s}: {plural_lieky(n_items)} v {len(gs)} "
                f"{'sile a balení' if len(gs) == 1 else 'silách a baleniach'}."
                + (f" Pri výbere lacnejšej verzie ušetríte až {eur(best_saving)} na balení." if best_saving > 0.005 else ""))
        crumb_items = [("Domov", "/"), ("Účinné látky", "/lieky/"), (s, None)]
        body = f"""{crumbs(crumb_items)}
  <section style="display:grid;gap:8px">
    <p class="eyebrow">Účinná látka · ATC {esc(gs[0]['a'])}</p>
    <h1 class="page-h1">{esc(s)}: doplatky za lieky</h1>
    <p class="page-sub">Lieky sú rozdelené podľa sily a veľkosti balenia. V rámci jednej skupiny ich poisťovňa hradí rovnako, líšia sa doplatkom.</p>
  </section>
  <ul class="glist">{''.join(lis)}</ul>
{NOTES}"""
        title = f"{s} – doplatky za lieky a lacnejšie alternatívy"
        out = SITE / path.strip("/")
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page(title, desc, path, body, breadcrumb_ld(crumb_items)), encoding="utf-8")
        urls.append((path, "0.7"))

    # --- abecedný zoznam ---
    letters = defaultdict(list)
    for s in sorted(by_subst, key=norm):
        first = norm(s)[:1].upper()
        letters[first if first.isalpha() else "#"].append(s)
    az = "".join(f'<a href="#p-{esc(k)}">{esc(k)}</a>' for k in letters)
    blocks = []
    for k, ss in letters.items():
        lis = "".join(
            f'<li><a href="/latka/{esc(subst_slug[s])}/">{esc(s)}</a> <small>{sum(len(g["items"]) for g in by_subst[s])}</small></li>'
            for s in ss)
        blocks.append(f'<section class="letter" id="p-{esc(k)}"><h2>{esc(k)}</h2><ul class="cols">{lis}</ul></section>')
    crumb_items = [("Domov", "/"), ("Účinné látky", None)]
    body = f"""{crumbs(crumb_items)}
  <section style="display:grid;gap:8px">
    <p class="eyebrow">{len(by_subst)} účinných látok</p>
    <h1 class="page-h1">Zoznam účinných látok</h1>
    <p class="page-sub">Všetky lieky hradené zdravotnými poisťovňami podľa účinnej látky. Číslo udáva počet balení v zozname.</p>
  </section>
  <nav class="az" aria-label="Písmená">{az}</nav>
  {''.join(blocks)}"""
    (SITE / "lieky").mkdir(exist_ok=True)
    (SITE / "lieky" / "index.html").write_text(
        page("Zoznam účinných látok – doplatky za lieky",
             f"Abecedný zoznam {len(by_subst)} účinných látok liekov hradených poisťovňou s doplatkami a lacnejšími alternatívami.",
             "/lieky/", body, breadcrumb_ld(crumb_items)),
        encoding="utf-8")

    # --- 404 ---
    body404 = """  <section style="display:grid;gap:12px">
    <h1 class="page-h1">Stránka sa nenašla</h1>
    <p class="page-sub">Liek mohol z úradného zoznamu vypadnúť alebo sa zmenil jeho názov. Skúste ho vyhľadať znova.</p>
    <p><a class="cta" href="/">Vyhľadať liek →</a></p>
  </section>"""
    (SITE / "404.html").write_text(page("Stránka sa nenašla", "Stránka sa nenašla.", "/404", body404), encoding="utf-8")

    # --- sitemap ---
    lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    sm = "".join(f"<url><loc>{BASE}{esc(u)}</loc>{lm}<priority>{pr}</priority></url>\n" for u, pr in urls)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + sm + "</urlset>\n", encoding="utf-8")

    print(f"Vygenerované: {len(products)} stránok liekov, {len(by_subst)} stránok látok, sitemap s {len(urls)} adresami.")


PLATNOST = ""

if __name__ == "__main__":
    build()
