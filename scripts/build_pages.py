"""Vygeneruje statické podstránky webu doplatkyliekov.sk z dát v priečinku data/.

- /liek/<slug>/        každé balenie lieku: doplatok, alternatívy, história, zmena v budúcom mesiaci,
                       kto predpisuje, indikačné obmedzenia, výrobca, výpadky, ochranný limit
- /latka/<slug>/       všetky sily a balenia jednej účinnej látky
- /skupina/<atc>/      lieky podľa ATC skupiny (napr. „Betablokátory“)
- /skupiny/            prehľad ATC skupín
- /lieky/              abecedný zoznam účinných látok
- /zmeny/              zmeny doplatkov od budúceho mesiaca
- /vypadky/            lieky s hláseným prerušením dodávok
- /ochranny-limit/     vysvetlenie a kalkulačka ochranného limitu
- /404.html, /sitemap.xml, /assets/style.css

Používa iba štandardnú knižnicu Pythonu, takže beží aj ako build príkaz v Cloudflare Pages:
  python3 scripts/build_pages.py
"""
import datetime as dt
import html
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "data"
BASE = "https://doplatkyliekov.sk"
GENERATED = ["liek", "latka", "lieky", "skupina", "skupiny", "zmeny", "vypadky", "ochranny-limit", "assets",
             "moje-lieky", "o-nas", "kontakt", "ochrana-sukromia", "clanky", "upozornenia"]
OPERATOR = "Karol Gajdošík"          # prevádzkovateľ webu (fyzická osoba)
CONTACT = "kontakt@doplatkyliekov.sk"  # presmerované cez Cloudflare Email Routing
SUKL_DB = ("https://www.sukl.sk/hlavna-stranka/slovenska-verzia/databazy-a-servis/"
           "vyhladavanie-liekov-zdravotnickych-pomocok-a-zmien-v-liekovej-databaze?page_id=235")
SUKL_VYPADKY = "https://portal.sukl.sk/PreruseniePublic/?act=PrerusenieOznList"
MESIACE = ["jan", "feb", "mar", "apr", "máj", "jún", "júl", "aug", "sep", "okt", "nov", "dec"]
MESIACE_GEN = ["januára", "februára", "marca", "apríla", "mája", "júna", "júla", "augusta", "septembra",
               "októbra", "novembra", "decembra"]


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


def plural(n, one, few, many):
    if n == 1:
        return f"1 {one}"
    if 2 <= n <= 4:
        return f"{n} {few}"
    return f"{n} {many}"


def plural_lieky(n):
    return plural(n, "liek", "lieky", "liekov")


def sk_date(iso):
    y, m, d = (int(x) for x in iso[:10].split("-"))
    return f"{d}. {m}. {y}"


def sk_date_long(iso):
    y, m, d = (int(x) for x in iso[:10].split("-"))
    return f"{d}. {MESIACE_GEN[m - 1]} {y}"


def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ---------- šablóny ----------

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600'
         '&family=Onest:wght@400;500;600&family=Unbounded:wght@500;600;700&display=swap">'
         '<meta name="theme-color" content="#05090b">')

CAPSULE = ('<svg class="capsule" viewBox="0 0 40 22" aria-hidden="true"><rect x="1" y="1" width="38" height="20" rx="10" '
           'fill="none" stroke="var(--accent)" stroke-width="2"/><path d="M11 1h9v20h-9a10 10 0 0 1 0-20z" fill="var(--accent)"/></svg>')

ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' "
        "rx='8' fill='%2305090b'/%3E%3Crect x='4' y='10' width='24' height='12' rx='6' fill='none' stroke='%2345f0c0' "
        "stroke-width='2'/%3E%3Cpath d='M10 10h6v12h-6a6 6 0 0 1 0-12z' fill='%2345f0c0'/%3E%3C/svg%3E")

EXTRA_CSS = """
/* doplnky štýlu pre podstránky; základ je v /style.css */
.crumbs { display: flex; flex-wrap: wrap; gap: 6px 10px; font-size: 14px; color: var(--muted); align-items: center; }
.crumbs a { color: var(--muted); text-decoration: none; }
.crumbs a:hover { color: var(--accent); }
.crumbs span[aria-hidden] { color: var(--faint); }
.page-h1 { font-size: clamp(30px, 6.6vw, 48px); line-height: 1.08; font-weight: 700; }
.page-sub { color: var(--muted); max-width: 62ch; font-size: 17px; }
.intro { display: grid; gap: 12px; }
.row-name a { color: var(--ink); text-decoration: none; }
.row-name a:hover { color: var(--accent); }
.row { cursor: default; }
.prices { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-bottom: 1px solid var(--line); }
.prices div { padding: 18px 24px; display: grid; gap: 6px; min-width: 0; }
.prices div + div { border-left: 1px solid var(--line); }
.prices span { font-family: var(--font-mono); font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .14em; }
.prices b { font-family: var(--font-mono); font-weight: 600; font-size: 24px; letter-spacing: -0.02em; white-space: nowrap; }
.prices b.dop { color: var(--save); text-shadow: 0 0 22px rgba(255, 150, 60, 0.35); }
.cta { display: inline-flex; align-items: center; gap: 10px; font-weight: 600; text-decoration: none; color: var(--accent); border: 1px solid var(--line-strong); border-radius: 999px; padding: 10px 18px; background: var(--surface); justify-self: start; }
.cta:hover { border-color: var(--accent); box-shadow: 0 0 22px -6px var(--glow); }
.purpose { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 15px; }
.purpose .eyebrow { margin-right: 4px; }
.purpose a { text-decoration: none; border: 1px solid var(--line-strong); border-radius: 999px; padding: 5px 13px; color: var(--ink); background: var(--surface); }
.purpose a:hover { border-color: var(--accent); color: var(--accent); }
.alert { display: grid; gap: 6px; padding: 18px 20px 18px 22px; border-radius: var(--r); border: 1px solid var(--line); background: var(--surface); position: relative; overflow: hidden; }
.alert::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--muted); }
.alert strong { font-family: var(--font-display); font-size: 17px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.35; }
.alert p { font-size: 16px; color: var(--muted); }
.alert.warn { background: var(--save-soft); border-color: rgba(255, 178, 107, 0.25); }
.alert.warn::before { background: var(--save); box-shadow: 0 0 14px var(--save); }
.alert.warn strong { color: var(--save); }
.alert.good { background: var(--accent-soft); border-color: var(--line-strong); }
.alert.good::before { background: var(--accent); box-shadow: 0 0 14px var(--glow); }
.alert.good strong { color: var(--accent); }
.card { padding: 24px; display: grid; gap: 18px; }
.card h2 { font-size: 21px; font-weight: 600; }
.card .hint, .hint { font-size: 14px; color: var(--muted); }
.facts-dl { display: grid; grid-template-columns: minmax(0, 12em) minmax(0, 1fr); gap: 0 20px; margin: 0; }
.facts-dl dt, .facts-dl dd { padding: 12px 0; border-top: 1px solid var(--line); }
.facts-dl dt:first-of-type, .facts-dl dd:first-of-type { border-top: 0; padding-top: 0; }
.facts-dl dt { color: var(--muted); font-size: 15px; }
.facts-dl dd { margin: 0; min-width: 0; overflow-wrap: anywhere; font-weight: 500; }
.facts-dl dd small { display: block; color: var(--muted); font-size: 14px; margin-top: 4px; font-weight: 400; line-height: 1.5; }
details.io { border: 1px solid var(--line); border-radius: var(--r); padding: 14px 16px; background: var(--accent-soft); }
details.io + details.io { margin-top: -6px; }
details.io summary { cursor: pointer; font-weight: 600; color: var(--accent); }
details.io p { white-space: pre-line; font-size: 15px; margin-top: 10px; color: var(--ink); line-height: 1.6; }
details.io .code { display: block; margin-top: 8px; font-family: var(--font-mono); font-size: 12px; color: var(--muted); }
.chart { width: 100%; max-width: 560px; height: auto; display: block; overflow: visible; }
.chart text { font-family: var(--font-mono); font-size: 16px; fill: var(--muted); }
@media (min-width: 641px) { .chart text { font-size: 12px; } }
.chart .grid { stroke: var(--line); stroke-width: 1; }
.chart .line { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; filter: drop-shadow(0 0 6px var(--glow)); }
.chart .area { fill: var(--accent-soft); }
.chart .dot { fill: var(--bg); stroke: var(--accent); stroke-width: 2; }
.chart .dot.end { fill: var(--accent); filter: drop-shadow(0 0 6px var(--glow)); }
.chart .next { fill: none; stroke: var(--save); stroke-width: 3; stroke-dasharray: 6 6; }
.chart .dot.nx { fill: var(--save); stroke: var(--save); }
.stats3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.stats3 div { display: grid; gap: 4px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; min-width: 0; }
.stats3 span { font-family: var(--font-mono); color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; }
.stats3 b { font-family: var(--font-mono); font-weight: 600; font-size: 16px; overflow-wrap: anywhere; }
.glist { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.glist li { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: 16px 18px; display: grid; gap: 8px; min-width: 0; }
.card .glist li { background: transparent; }
.glist h3 { font-size: 17px; font-weight: 600; }
.glist .gline { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 16px; font-size: 16px; align-items: baseline; }
.glist .gline + .gline { border-top: 1px solid var(--line); padding-top: 8px; }
.glist .gline a { min-width: 0; overflow-wrap: anywhere; text-decoration: none; color: var(--ink); font-weight: 500; }
.glist .gline a:hover { color: var(--accent); }
.glist .gline .mono { white-space: nowrap; font-weight: 600; }
.glist .gline small { grid-column: 1 / -1; color: var(--muted); font-size: 14px; line-height: 1.5; }
.glist .gline small a { color: var(--accent); font-weight: 500; }
.glist .save { color: var(--save); font-weight: 600; font-size: 14px; }
.glist .up { color: var(--save); }
.glist .down { color: var(--accent); }
.az { display: flex; flex-wrap: wrap; gap: 8px; }
.az a { font-family: var(--font-mono); min-width: 38px; text-align: center; padding: 6px 10px; border: 1px solid var(--line-strong); border-radius: 10px; text-decoration: none; color: var(--ink); background: var(--surface); }
.az a:hover { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 16px -6px var(--glow); }
.letter { display: grid; gap: 12px; scroll-margin-top: 16px; }
.letter h2 { font-size: 22px; }
.letter h2 a { color: var(--ink); text-decoration: none; }
.letter h2 a:hover { color: var(--accent); }
.cols { columns: 2 240px; column-gap: 28px; margin: 0; padding: 0; list-style: none; }
.cols li { break-inside: avoid; padding: 6px 0; border-bottom: 1px solid var(--line); }
.cols li a { text-decoration: none; color: var(--ink); }
.cols li a:hover { color: var(--accent); }
.cols small { color: var(--faint); font-family: var(--font-mono); margin-left: 6px; }
.ltable { width: 100%; border-collapse: collapse; font-size: 16px; }
.ltable th, .ltable td { text-align: left; padding: 12px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.ltable th { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); font-weight: 500; }
.ltable td.num { font-family: var(--font-mono); white-space: nowrap; color: var(--accent); font-weight: 600; }
.scroll { overflow-x: auto; }
.calc { display: grid; gap: 18px; }
.calc label { display: grid; gap: 8px; font-weight: 600; font-size: 16px; }
.calc select, .calc input { font: inherit; font-weight: 400; font-size: 17px; color: var(--ink); background: var(--raise); border: 1px solid var(--line-strong); border-radius: 12px; padding: 12px 14px; width: 100%; max-width: 460px; }
.calc select:focus-visible, .calc input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.calc .result { padding: 18px 20px; border-radius: var(--r); background: var(--accent-soft); border: 1px solid var(--line-strong); font-size: 17px; line-height: 1.55; }
.calc .result b { font-family: var(--font-mono); color: var(--accent); font-size: 20px; }
.prose { display: grid; gap: 14px; max-width: 65ch; }
.prose h2 { font-size: 22px; font-weight: 600; margin-top: 12px; }
.prose ul { margin: 0; padding-left: 22px; display: grid; gap: 8px; }
.prose li::marker { color: var(--accent); }
@media (max-width: 640px) {
  .prices { grid-template-columns: 1fr; }
  .prices div { padding: 14px 18px; }
  .prices div + div { border-left: 0; border-top: 1px solid var(--line); }
  .facts-dl { grid-template-columns: 1fr; }
  .facts-dl dt { padding-bottom: 2px; }
  .facts-dl dd { border-top: 0; padding-top: 0; }
  .facts-dl dt:first-of-type { padding-top: 0; }
  .card { padding: 20px 18px; }
  .stats3 { grid-template-columns: 1fr 1fr; }
  .stats3 div:last-child { grid-column: 1 / -1; }
}
"""


BOOKMARK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M6 3h12v18l-6-4.5L6 21z"/></svg>')


def mine_button(p):
    return (f'<button type="button" class="mine-btn" data-kod="{esc(p["kod"])}" data-name="{esc(p["name"])}" '
            f'data-slug="{esc(p["slug"])}" aria-pressed="false">{BOOKMARK}<span class="mine-label">Pridať do Mojich liekov</span></button>')


def alert_form(kod=None, heading="Upozorníme vás na zmenu"):
    data_kod = f' data-kod="{esc(kod)}"' if kod else ""
    return f"""
  <section class="card">
    <h2>{esc(heading)}</h2>
    <p class="page-sub">Pošleme vám e-mail, len keď sa zmení doplatok vašich liekov alebo keď výrobca ohlási výpadok. Bez reklamy, odhlásiť sa dá jedným kliknutím.</p>
    <form class="alert-form"{data_kod} novalidate>
      <div class="fields">
        <label class="hp" aria-hidden="true">Web <input name="web" tabindex="-1" autocomplete="off"></label>
        <input type="email" name="email" id="alert-email" autocomplete="email" placeholder="vas@email.sk" aria-label="E-mailová adresa" required>
        <button type="submit">Chcem upozornenia</button>
      </div>
      <label class="consent"><input type="checkbox" name="consent" id="alert-consent"> <span>Súhlasím so spracovaním e-mailu a zoznamu mojich liekov na zasielanie upozornení podľa <a href="/ochrana-sukromia/">zásad ochrany súkromia</a>.</span></label>
      <p class="form-msg" aria-live="polite"></p>
    </form>
  </section>"""


def extract_css():
    return EXTRA_CSS


PLATNOST = ""


def page(title, description, path, body, jsonld=None, script=""):
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
<link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/assets/pages.css">
{ld}
</head>
<body>
<div class="wrap">
  <header class="topbar">
    <a class="brand-link" href="/">
      {CAPSULE}
      <span class="brand-name">doplatky<b>liekov</b>.sk</span>
    </a>
    <a class="mine-link" href="/moje-lieky/">{BOOKMARK}Moje lieky <span data-mine-count hidden></span></a>
  </header>
{body}
  <footer>
    <nav aria-label="Ďalšie stránky"><a href="/">Vyhľadať liek</a><a href="/moje-lieky/">Moje lieky</a><a href="/skupiny/">Lieky podľa skupín</a><a href="/lieky/">Účinné látky</a><a href="/zmeny/">Zmeny doplatkov</a><a href="/vypadky/">Výpadky</a><a href="/ochranny-limit/">Ochranný limit</a><a href="/clanky/">Články</a></nav>
    <nav aria-label="O webe"><a href="/o-nas/">O nás</a><a href="/kontakt/">Kontakt</a><a href="/ochrana-sukromia/">Ochrana súkromia</a></nav>
    <p>Zdroj: Zoznam kategorizovaných liekov Ministerstva zdravotníctva SR, platný od {esc(PLATNOST)}, a hlásenia o dodávkach liekov ŠÚKL. Ceny sú v eurách s DPH.</p>
    <p>Stránka slúži na informáciu a nenahrádza radu lekára ani lekárnika.</p>
  </footer>
</div>
<script src="/moje.js" defer></script>
{script}
</body>
</html>
"""


def crumbs(items):
    parts = []
    for i, (lbl, href) in enumerate(items):
        if i:
            parts.append('<span aria-hidden="true">›</span>')
        parts.append(f'<a href="{esc(href)}">{esc(lbl)}</a>' if href else f"<span>{esc(lbl)}</span>")
    return f'  <nav class="crumbs" aria-label="Navigácia">{"".join(parts)}</nav>'


def breadcrumb_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": lbl, **({"item": BASE + href} if href else {})}
            for i, (lbl, href) in enumerate(items)
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


def write(path, content):
    out = SITE / path.strip("/")
    if path.endswith("/"):
        out.mkdir(parents=True, exist_ok=True)
        out = out / "index.html"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


# ---------- graf histórie ----------

def history_chart(points, next_point=None):
    """points: [(iso, dop)], next_point: (iso, dop) alebo None. Vráti inline SVG."""
    if len(points) < 2:
        return ""
    allp = points + ([next_point] if next_point else [])
    W, H, L, R, T, B = 400, 200, 54, 14, 14, 34  # malé súradnice = čitateľné popisy aj na mobile
    n = len(allp)
    vmax = max(v for _, v in allp)
    top = max(1.0, vmax * 1.15)
    step = 5 if top <= 25 else 10 if top <= 60 else 50 if top <= 300 else 100 if top <= 600 else 500
    top = (int(top / step) + 1) * step if top % step else top

    def x(i):
        return L + (W - L - R) * (i / (n - 1))

    def y(v):
        return T + (H - T - B) * (1 - v / top)

    parts = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Vývoj doplatku">']
    ticks = 4
    for k in range(ticks + 1):
        v = top * k / ticks
        yy = y(v)
        parts.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        lbl = f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        parts.append(f'<text x="{L - 6}" y="{yy + 5:.1f}" text-anchor="end">{lbl} €</text>')
    xs = [x(i) for i in range(len(points))]
    ys = [y(v) for _, v in points]
    line = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys))
    area = f"{xs[0]:.1f},{y(0):.1f} " + line + f" {xs[-1]:.1f},{y(0):.1f}"
    parts.append(f'<polygon class="area" points="{area}"/>')
    parts.append(f'<polyline class="line" points="{line}"/>')
    # popisy osi x: prvý, posledný a každý január
    for i, (iso, _) in enumerate(allp):
        yr, mo = int(iso[:4]), int(iso[5:7])
        if i == 0 or i == n - 1 or mo == 1:
            anchor = "start" if i == 0 else "end" if i == n - 1 else "middle"
            parts.append(f'<text x="{x(i):.1f}" y="{H - 6}" text-anchor="{anchor}">{MESIACE[mo - 1]} {yr}</text>')
    for i, (a, b) in enumerate(zip(xs, ys)):
        if i == len(xs) - 1:
            parts.append(f'<circle class="dot end" cx="{a:.1f}" cy="{b:.1f}" r="4.5"/>')
    if next_point:
        nx, ny = x(n - 1), y(next_point[1])
        parts.append(f'<polyline class="next" points="{xs[-1]:.1f},{ys[-1]:.1f} {nx:.1f},{ny:.1f}"/>')
        parts.append(f'<circle class="dot nx" cx="{nx:.1f}" cy="{ny:.1f}" r="4.5"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------- generovanie ----------

def build():
    global PLATNOST
    full = load("full.json")
    if full is None:  # záložný režim: len základné dáta
        lean = json.loads((SITE / "data.json").read_text(encoding="utf-8"))
        full = {"platnost": lean["platnost"], "platnostIso": lean.get("platnostIso"), "groups": [
            {"a": g["a"], "s": g["s"], "f": g["f"], "i": [
                {"kod": i[0], "name": i[1], "pack": i[2], "konc": i[3], "uzp": i[4], "dop": i[5], "typ": i[6]}
                for i in g["i"]]} for g in lean["groups"]]}
    ref = load("ref.json", {}) or {}
    nxt = load("next.json")
    vyp_all = load("vypadky.json", {}) or {}
    vyp = vyp_all.get("lieky", {})
    # staré hlásenia bez obnovenia dodávok považujeme za neaktuálne (držitelia často obnovenie nenahlásia)
    cutoff = (dt.date.today() - dt.timedelta(days=730)).isoformat()
    vyp = {k: v for k, v in vyp.items() if v.get("od", "") >= cutoff}
    PLATNOST = full.get("platnost", "")
    cur_iso = full.get("platnostIso") or ""
    lastmod = cur_iso or None
    groups = full["groups"]
    atc_names = ref.get("atc", {})
    drz_names = ref.get("drz", {})
    staty = ref.get("staty", {})
    odb = ref.get("odbornosti", {})
    io_texts = ref.get("io", {})
    io_kod = ref.get("io_kod", {})

    # história cien
    hist_files = sorted((DATA / "history").glob("*.json")) if (DATA / "history").exists() else []
    history = []  # [(iso, {kod: [konc, uzp, dop]})]
    for f in hist_files:
        history.append((f.stem + "-01", json.loads(f.read_text(encoding="utf-8"))))
    history = [h for h in history if not cur_iso or h[0] <= cur_iso]

    for d in GENERATED:
        shutil.rmtree(SITE / d, ignore_errors=True)
    (SITE / "assets").mkdir(parents=True)
    (SITE / "assets" / "pages.css").write_text(extract_css(), encoding="utf-8")

    # produkty, látky, skupiny
    by_subst = defaultdict(list)
    products = []
    used = set()
    for g in groups:
        for p in g["i"]:
            slug = product_slug(p["name"], p["kod"])
            base, n = slug, 2
            while slug in used:
                slug = f"{base}-{n}"
                n += 1
            used.add(slug)
            p["slug"] = slug
            products.append((g, p))
        by_subst[g["s"]].append(g)
    by_kod = {p["kod"]: (g, p) for g, p in products}

    subst_slug = {}
    for s in by_subst:
        sl = slugify(s, 80) or "latka"
        while sl in subst_slug.values():
            sl += "-x"
        subst_slug[s] = sl

    def atc_chain(code):
        """[(kód, názov)] pre ATC úroveň 1 a 2, ktoré máme v číselníku."""
        out = []
        for k in (code[:1], code[:3]):
            if k in atc_names:
                out.append((k, atc_names[k]))
        return out

    urls = [("/", "1.0"), ("/lieky/", "0.6"), ("/skupiny/", "0.6"), ("/zmeny/", "0.7"),
            ("/vypadky/", "0.7"), ("/ochranny-limit/", "0.7")]

    def sorted_items(g):
        return sorted([x for x in g["i"] if x["dop"] is not None], key=lambda x: (x["dop"], norm(x["name"])))

    def next_change(p):
        if not nxt:
            return None
        np_ = nxt["prices"].get(p["kod"])
        if np_ is None:
            return {"gone": True}
        return {"gone": False, "konc": np_[0], "uzp": np_[1], "dop": np_[2],
                "diff": None if (np_[2] is None or p["dop"] is None) else round(np_[2] - p["dop"], 2)}

    def vyp_text(state):
        if not state:
            return None
        s, od = state["stav"], sk_date(state["od"])
        return {"R": ("Prerušené dodávky", f"Držiteľ registrácie ohlásil prerušenie dodávok od {od}. Liek môže byť v lekárňach nedostupný."),
                "Z": ("Ukončené dodávky", f"Držiteľ registrácie ohlásil ukončenie dodávok od {od}."),
                "PR": ("Ohlásené prerušenie dodávok", f"Držiteľ registrácie ohlásil prerušenie dodávok od {od}."),
                "PZ": ("Ohlásené ukončenie dodávok", f"Držiteľ registrácie ohlásil ukončenie dodávok od {od}.")}.get(s)

    # --- stránky liekov ---
    for g, p in products:
        items = sorted_items(g)
        cheapest = items[0] if items else None
        available = [x for x in items if vyp.get(x["kod"], {}).get("stav") not in ("R", "Z")]
        max_dop = max([x["dop"] for x in items] + [0.01])
        saving = (p["dop"] - cheapest["dop"]) if (cheapest and p["dop"] is not None) else 0
        s_url = f"/latka/{subst_slug[g['s']]}/"
        path = f"/liek/{p['slug']}/"
        pk = short_pack(p["pack"])
        chain = atc_chain(g["a"])
        change = next_change(p)
        vstate = vyp.get(p["kod"])
        vt = vyp_text(vstate)

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
        if chain:
            desc += f" Skupina: {chain[-1][1]}."

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
            if vyp.get(x["kod"], {}).get("stav") in ("R", "Z"):
                tags.append('<span class="tag">Výpadok</span>')
            name = esc(x["name"]) if x is p else f'<a href="/liek/{esc(x["slug"])}/">{esc(x["name"])}</a>'
            width = round(x["dop"] / max_dop * 100, 1)
            rows.append(
                f'<li class="{cls}"><div class="row-name">{name}<span class="tags">{"".join(tags)}</span></div>'
                f'<div class="row-dop">{eur(x["dop"])}</div><div class="row-pack">{esc(x["pack"])}</div>'
                f'<div class="row-sub">cena {eur(x["konc"])}</div>'
                f'<div class="track"><i style="width:{width}%"></i></div></li>')

        # upozornenia
        alerts = []
        if vt:
            extra = ""
            alts = [x for x in available if x is not p]
            if alts:
                a0 = alts[0]
                extra = (f' Dostupná alternatíva s rovnakou látkou: <a href="/liek/{esc(a0["slug"])}/">{esc(a0["name"])}</a> '
                         f'(doplatok {eur(a0["dop"])}).')
            alerts.append(f'<div class="alert warn"><strong>{vt[0]}</strong><p>{esc(vt[1])}{extra} '
                          f'Zdroj: <a href="{SUKL_VYPADKY}" rel="nofollow">hlásenia ŠÚKL</a>.</p></div>')
        if change and nxt:
            nd = sk_date_long(nxt["platnostIso"])
            if change["gone"]:
                alerts.append(f'<div class="alert warn"><strong>Od {nd} liek v zozname hradených liekov nie je</strong>'
                              f'<p>Poisťovňa ho od tohto dátumu nemusí hradiť. Poraďte sa s lekárom o náhrade.</p></div>')
            elif change["diff"] is not None and abs(change["diff"]) >= 0.01:
                up = change["diff"] > 0
                alerts.append(f'<div class="alert {"warn" if up else "good"}"><strong>Od {nd} doplatok '
                              f'{"stúpne" if up else "klesne"} na {eur(change["dop"])}</strong>'
                              f'<p>Dnes {eur(p["dop"])}, {"o " + eur(abs(change["diff"])) + (" viac" if up else " menej")} na balení. '
                              f'Údaj je z nového zoznamu ministerstva, ktorý už bol zverejnený.</p></div>')
        alerts_html = "\n    ".join(alerts)

        # história
        points = []
        for iso, prices in history:
            v = prices.get(p["kod"])
            if v and v[2] is not None:
                points.append((iso, v[2]))
        next_point = None
        if change and not change["gone"] and change["dop"] is not None and nxt:
            next_point = (nxt["platnostIso"], change["dop"])
        chart = history_chart(points, next_point)
        hist_html = ""
        if chart:
            vals = [v for _, v in points]
            first_iso = points[0][0]
            hist_html = f"""
  <section class="card">
    <h2>Vývoj doplatku</h2>
    {chart}
    <div class="stats3">
      <div><span>Najnižší</span><b>{eur(min(vals))}</b></div>
      <div><span>Najvyšší</span><b>{eur(max(vals))}</b></div>
      <div><span>Od {MESIACE[int(first_iso[5:7]) - 1]} {first_iso[:4]}</span><b>{eur(vals[0])} → {eur(vals[-1])}</b></div>
    </div>
    <p class="hint">Maximálny doplatok podľa mesačných zoznamov ministerstva{', prerušovaná čiara ukazuje doplatok od ' + sk_date(nxt['platnostIso']) if next_point else ''}.</p>
  </section>"""

        # predpis a úhrada
        facts = []
        po = p.get("po") or []
        if po:
            names = [odb.get(c, c) for c in po]
            facts.append(("Kto môže predpísať", "Len lekár so špecializáciou: " + ", ".join(names) +
                          "<small>Preskripčné obmedzenie podľa zoznamu ministerstva. Všeobecný lekár ho môže predpísať "
                          "spravidla len na odporúčanie špecialistu.</small>"))
        elif "kod" in p and "po" in p:
            facts.append(("Kto môže predpísať", "Ktorýkoľvek lekár, aj všeobecný<small>Liek nemá preskripčné obmedzenie.</small>"))
        io_flag = p.get("io", "")
        if io_flag:
            zp = "ZP" in io_flag
            facts.append(("Indikačné obmedzenie", "Áno, poisťovňa ho hradí len pri určených ochoreniach" +
                          ("<small>Úhrada navyše vyžaduje predchádzajúci súhlas zdravotnej poisťovne.</small>" if zp else
                           "<small>Podmienky úhrady nájdete nižšie.</small>")))
        if p.get("gp"):
            facts.append(("Predpis", "Lekár predpisuje názvom účinnej látky<small>V lekárni si tak môžete vybrať "
                          "ktorýkoľvek liek s touto látkou, napríklad ten s najnižším doplatkom.</small>"))
        if p.get("olpl"):
            facts.append(("Osobitný recept", "Predpisuje sa na recept so šikmým modrým pruhom"
                          "<small>Liek obsahuje omamnú alebo psychotropnú látku.</small>"))
        su = p.get("su", "")
        if su in ("A", "AS"):
            facts.append(("Spôsob úhrady", "Liek podáva lekár, poisťovňa ho uhrádza priamo zdravotníckemu zariadeniu"
                          + ("" if su == "A" else "<small>Čiastočne uhrádzaný.</small>")))
        elif su == "V":
            facts.append(("Spôsob úhrady", "Vakcína na povinné alebo odporúčané očkovanie"))
        elif su == "I":
            facts.append(("Spôsob úhrady", "Plne uhrádzaný poisťovňou"))
        if p.get("pdop") is not None:
            facts.append(("Ochranný limit", f"Do limitu sa započíta {eur(p['pdop'])}"
                          f'<small>Prepočítaný doplatok za najlacnejší náhradný liek podľa zoznamu ministerstva. <a href="/ochranny-limit/">Ako funguje ochranný limit</a></small>'))
        if p.get("podm"):
            facts.append(("Kategorizácia", f"Podmienená od {esc(p['podm'])}"))
        elif p.get("docas"):
            facts.append(("Kategorizácia", f"Dočasná od {esc(p['docas'])}"))

        io_html = ""
        codes = io_kod.get(p["kod"], [])
        if io_flag and codes:
            blocks = "".join(
                f'<details class="io"><summary>Podmienka úhrady {i + 1}</summary><p>{esc(io_texts.get(c, ""))}</p>'
                f'<span class="code">Kód {esc(c)}</span></details>'
                for i, c in enumerate(codes[:12]) if io_texts.get(c))
            if blocks:
                io_html = blocks

        presc_html = ""
        if facts or io_html:
            dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in facts)
            presc_html = f"""
  <section class="card">
    <h2>Predpis a úhrada</h2>
    <dl class="facts-dl">{dl}</dl>
    {io_html}
  </section>"""

        about = []
        about.append(("Účinná látka", f'<a href="{s_url}">{esc(g["s"])}</a>, {esc(g["f"])}'))
        if chain:
            about.append(("Skupina liečiv", " › ".join(f'<a href="/skupina/{esc(k.lower())}/">{esc(v)}</a>' for k, v in chain)))
        about.append(("Typ", type_label(p["typ"]) or "Liek"))
        if p.get("drz"):
            nm = drz_names.get(p["drz"], p["drz"])
            st = staty.get(p.get("stat", ""), p.get("stat", ""))
            about.append(("Držiteľ registrácie", esc(nm) + (f"<small>{esc(st)}</small>" if st else "")))
        if p.get("sdl"):
            about.append(("Dávok v balení", f'{p["sdl"]:g}'))
        about.append(("Kód ŠÚKL", f'<span class="mono">{esc(p["kod"])}</span>'))
        about.append(("ATC kód", f'<span class="mono">{esc(g["a"])}</span>'))
        about.append(("Príbalový leták", f'<a href="{SUKL_DB}" rel="nofollow">Databáza liekov ŠÚKL</a>'
                      f'<small>Vyhľadajte kód {esc(p["kod"])} alebo názov lieku.</small>'))
        about_html = f"""
  <section class="card">
    <h2>O lieku</h2>
    <dl class="facts-dl">{"".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in about)}</dl>
  </section>"""

        purpose = ""
        if chain:
            purpose = ('<div class="purpose"><span class="eyebrow">Na čo je</span>' +
                       "".join(f'<a href="/skupina/{esc(k.lower())}/">{esc(v)}</a>' for k, v in chain) + "</div>")

        crumb_items = [("Domov", "/")]
        if chain:
            crumb_items.append((chain[-1][1], f"/skupina/{chain[-1][0].lower()}/"))
        crumb_items += [(g["s"], s_url), (p["name"], None)]
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Doplatok za liek</p>
    <h1 class="page-h1">{esc(p['name'])}</h1>
    <p class="page-sub">{esc(p['pack'])}</p>
    {purpose}
    {mine_button(p)}
  </section>
    {alerts_html}
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
{hist_html}
{presc_html}
{about_html}
{alert_form(p["kod"])}
  <p><a class="cta" href="{s_url}">Všetky sily a balenia: {esc(g['s'])} →</a></p>
{NOTES}"""
        title = f"{p['name']} ({pk}) – doplatok a lacnejšie alternatívy"
        write(path, page(title, desc, path, body, breadcrumb_ld(crumb_items)))
        urls.append((path, "0.8"))

    # --- stránky látok ---
    for s, gs in by_subst.items():
        path = f"/latka/{subst_slug[s]}/"
        gs_sorted = sorted(gs, key=lambda g: norm(g["f"]))
        best_saving = 0
        lis = []
        for g in gs_sorted:
            items = sorted_items(g)
            if not items:
                continue
            gap = items[-1]["dop"] - items[0]["dop"]
            best_saving = max(best_saving, gap)
            lines = "".join(
                f'<div class="gline"><a href="/liek/{esc(x["slug"])}/">{esc(x["name"])}</a><span class="mono">{eur(x["dop"])}</span></div>'
                for x in items)
            save = (f'<p class="save">Rozdiel v doplatku až {eur(gap)} na balení</p>' if gap > 0.005 else "")
            lis.append(f'<li><h3>{esc(g["f"])}</h3>{save}{lines}</li>')
        n_items = sum(len(g["i"]) for g in gs)
        chain = atc_chain(gs[0]["a"])
        desc = (f"Doplatky za lieky s účinnou látkou {s}: {plural_lieky(n_items)} v {len(gs)} "
                f"{'sile a balení' if len(gs) == 1 else 'silách a baleniach'}."
                + (f" Pri výbere lacnejšej verzie ušetríte až {eur(best_saving)} na balení." if best_saving > 0.005 else "")
                + (f" Skupina: {chain[-1][1]}." if chain else ""))
        crumb_items = [("Domov", "/")]
        if chain:
            crumb_items.append((chain[-1][1], f"/skupina/{chain[-1][0].lower()}/"))
        else:
            crumb_items.append(("Účinné látky", "/lieky/"))
        crumb_items.append((s, None))
        purpose = ""
        if chain:
            purpose = ('<div class="purpose"><span class="eyebrow">Skupina</span>' +
                       "".join(f'<a href="/skupina/{esc(k.lower())}/">{esc(v)}</a>' for k, v in chain) + "</div>")
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Účinná látka · ATC {esc(gs[0]['a'])}</p>
    <h1 class="page-h1">{esc(s)}: doplatky za lieky</h1>
    <p class="page-sub">Lieky sú rozdelené podľa sily a veľkosti balenia. V rámci jednej skupiny ich poisťovňa hradí rovnako, líšia sa doplatkom.</p>
    {purpose}
  </section>
  <ul class="glist">{''.join(lis)}</ul>
{NOTES}"""
        write(path, page(f"{s} – doplatky za lieky a lacnejšie alternatívy", desc, path, body, breadcrumb_ld(crumb_items)))
        urls.append((path, "0.7"))

    # --- ATC skupiny ---
    subst_by_atc = defaultdict(set)
    for s, gs in by_subst.items():
        for g in gs:
            subst_by_atc[g["a"][:1]].add(s)
            subst_by_atc[g["a"][:3]].add(s)
    lvl1 = sorted(k for k in atc_names if len(k) == 1 and subst_by_atc.get(k))
    for code in sorted(k for k in atc_names if len(k) in (1, 3) and subst_by_atc.get(k)):
        name = atc_names[code]
        path = f"/skupina/{code.lower()}/"
        substs = sorted(subst_by_atc[code], key=norm)
        crumb_items = [("Domov", "/"), ("Skupiny liekov", "/skupiny/")]
        if len(code) == 3 and code[:1] in atc_names:
            crumb_items.append((atc_names[code[:1]], f"/skupina/{code[:1].lower()}/"))
        crumb_items.append((name, None))
        sub_html = ""
        if len(code) == 1:
            subs = sorted(k for k in atc_names if len(k) == 3 and k.startswith(code) and subst_by_atc.get(k))
            if subs:
                sub_html = ('<section class="card"><h2>Podskupiny</h2><ul class="cols">' + "".join(
                    f'<li><a href="/skupina/{k.lower()}/">{esc(atc_names[k])}</a> <small>{len(subst_by_atc[k])}</small></li>'
                    for k in subs) + "</ul></section>")
        lis = []
        for s in substs:
            gs = [g for g in by_subst[s] if g["a"].startswith(code)]
            allit = [x for g in gs for x in g["i"] if x["dop"] is not None]
            if not allit:
                continue
            lo = min(allit, key=lambda x: x["dop"])
            lis.append(f'<li><div class="gline"><a href="/latka/{esc(subst_slug[s])}/">{esc(s)}</a>'
                       f'<span class="mono">od {eur(lo["dop"])}</span>'
                       f'<small>{plural_lieky(len(allit))} · {plural(len(gs), "sila a balenie", "sily a balenia", "síl a balení")}</small></div></li>')
        n_s = len(substs)
        desc = (f"{name}: doplatky za lieky hradené poisťovňou. {plural(n_s, 'účinná látka', 'účinné látky', 'účinných látok')} "
                f"s porovnaním doplatkov a lacnejšími alternatívami.")
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Skupina liečiv · ATC {esc(code)}</p>
    <h1 class="page-h1">{esc(name)}</h1>
    <p class="page-sub">{plural(n_s, 'účinná látka', 'účinné látky', 'účinných látok')} hradených poisťovňou. Pri každej je uvedený najnižší doplatok.</p>
  </section>
  {sub_html}
  <ul class="glist">{''.join(lis)}</ul>"""
        write(path, page(f"{name} – lieky a doplatky", desc, path, body, breadcrumb_ld(crumb_items)))
        urls.append((path, "0.6"))

    blocks = []
    for code in lvl1:
        subs = sorted(k for k in atc_names if len(k) == 3 and k.startswith(code) and subst_by_atc.get(k))
        lis = "".join(f'<li><a href="/skupina/{k.lower()}/">{esc(atc_names[k])}</a> <small>{len(subst_by_atc[k])}</small></li>' for k in subs)
        blocks.append(f'<section class="letter"><h2><a href="/skupina/{code.lower()}/">{esc(atc_names[code])}</a></h2><ul class="cols">{lis}</ul></section>')
    crumb_items = [("Domov", "/"), ("Skupiny liekov", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Anatomicko-terapeuticko-chemická klasifikácia</p>
    <h1 class="page-h1">Lieky podľa skupín</h1>
    <p class="page-sub">Lieky hradené poisťovňou rozdelené podľa toho, na čo sa používajú. Číslo udáva počet účinných látok.</p>
  </section>
  {''.join(blocks)}"""
    write("/skupiny/", page("Lieky podľa skupín – doplatky", "Prehľad skupín liekov hradených zdravotnými poisťovňami podľa ATC klasifikácie s doplatkami.", "/skupiny/", body, breadcrumb_ld(crumb_items)))

    # --- abecedný zoznam látok ---
    letters = defaultdict(list)
    for s in sorted(by_subst, key=norm):
        first = norm(s)[:1].upper()
        letters[first if first.isalpha() else "#"].append(s)
    az = "".join(f'<a href="#p-{esc(k)}">{esc(k)}</a>' for k in letters)
    blocks = []
    for k, ss in letters.items():
        lis = "".join(
            f'<li><a href="/latka/{esc(subst_slug[s])}/">{esc(s)}</a> <small>{sum(len(g["i"]) for g in by_subst[s])}</small></li>'
            for s in ss)
        blocks.append(f'<section class="letter" id="p-{esc(k)}"><h2>{esc(k)}</h2><ul class="cols">{lis}</ul></section>')
    crumb_items = [("Domov", "/"), ("Účinné látky", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">{len(by_subst)} účinných látok</p>
    <h1 class="page-h1">Zoznam účinných látok</h1>
    <p class="page-sub">Všetky lieky hradené zdravotnými poisťovňami podľa účinnej látky. Číslo udáva počet balení v zozname. Lieky môžete prehliadať aj <a href="/skupiny/">podľa skupín</a>.</p>
  </section>
  <nav class="az" aria-label="Písmená">{az}</nav>
  {''.join(blocks)}"""
    write("/lieky/", page("Zoznam účinných látok – doplatky za lieky",
                          f"Abecedný zoznam {len(by_subst)} účinných látok liekov hradených poisťovňou s doplatkami a lacnejšími alternatívami.",
                          "/lieky/", body, breadcrumb_ld(crumb_items)))

    # --- zmeny od budúceho mesiaca ---
    crumb_items = [("Domov", "/"), ("Zmeny doplatkov", None)]
    if nxt:
        nd = sk_date_long(nxt["platnostIso"])
        ups, downs, gone = [], [], []
        for g, p in products:
            c = next_change(p)
            if not c:
                continue
            if c["gone"]:
                gone.append((g, p))
            elif c["diff"] is not None and abs(c["diff"]) >= 0.01:
                (ups if c["diff"] > 0 else downs).append((c["diff"], g, p, c))
        ups.sort(key=lambda t: -t[0])
        downs.sort(key=lambda t: t[0])
        new_kods = [k for k in nxt["prices"] if k not in by_kod]

        def change_list(lst, cls):
            return "".join(
                f'<li><div class="gline"><a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a>'
                f'<span class="mono {cls}">{"+" if d > 0 else "−"}{eur(abs(d))}</span>'
                f'<small>{esc(short_pack(p["pack"]))} · {eur(p["dop"])} → {eur(c["dop"])}</small></div></li>'
                for d, g, p, c in lst[:150])
        gone_html = "".join(
            f'<li><div class="gline"><a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a><span class="mono">{eur(p["dop"])}</span>'
            f'<small>{esc(short_pack(p["pack"]))} · {esc(g["s"])}</small></div></li>' for g, p in gone[:200])
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Nový zoznam platí od {nd}</p>
    <h1 class="page-h1">Zmeny doplatkov od {nd}</h1>
    <p class="page-sub">Ministerstvo zverejňuje zoznam hradených liekov vopred. Porovnali sme ho s aktuálnym zoznamom. Vyšší doplatok: {plural_lieky(len(ups))}, nižší doplatok: {plural_lieky(len(downs))}, vypadne zo zoznamu: {plural_lieky(len(gone))}.</p>
  </section>
  <section class="card"><h2>Doplatok stúpne ({len(ups)})</h2><ul class="glist">{change_list(ups, "up") or "<li>Žiadne zvýšenia.</li>"}</ul>{'<p class="hint">Zobrazených 150 najväčších zmien.</p>' if len(ups) > 150 else ''}</section>
  <section class="card"><h2>Doplatok klesne ({len(downs)})</h2><ul class="glist">{change_list(downs, "down") or "<li>Žiadne zníženia.</li>"}</ul>{'<p class="hint">Zobrazených 150 najväčších zmien.</p>' if len(downs) > 150 else ''}</section>
  <section class="card"><h2>Vypadnú zo zoznamu ({len(gone)})</h2><p class="hint">Tieto lieky poisťovňa od {nd} nemusí hradiť. Nové lieky v zozname: {len(new_kods)}.</p><ul class="glist">{gone_html or "<li>Žiadne.</li>"}</ul></section>"""
        desc = (f"Zmeny doplatkov za lieky od {nd}: vyšší doplatok {plural_lieky(len(ups))}, nižší {plural_lieky(len(downs))}, "
                f"zo zoznamu vypadne {plural_lieky(len(gone))}. Podľa nového zoznamu ministerstva.")
        write("/zmeny/", page(f"Zmeny doplatkov za lieky od {nd}", desc, "/zmeny/", body, breadcrumb_ld(crumb_items)))
    else:
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <h1 class="page-h1">Zmeny doplatkov</h1>
    <p class="page-sub">Ministerstvo zatiaľ nezverejnilo zoznam na budúci mesiac. Zvyčajne ho zverejní v druhej polovici mesiaca. Hneď ako bude k dispozícii, nájdete tu všetky zmeny doplatkov.</p>
  </section>"""
        write("/zmeny/", page("Zmeny doplatkov za lieky", "Zmeny doplatkov za lieky od budúceho mesiaca.", "/zmeny/", body, breadcrumb_ld(crumb_items)))

    # --- výpadky ---
    crumb_items = [("Domov", "/"), ("Výpadky liekov", None)]
    rows_r, rows_p = [], []
    for g, p in products:
        st = vyp.get(p["kod"])
        if not st:
            continue
        alts = [x for x in sorted_items(g) if x is not p and vyp.get(x["kod"], {}).get("stav") not in ("R", "Z")]
        alt = (f'Alternatíva: <a href="/liek/{esc(alts[0]["slug"])}/">{esc(alts[0]["name"])}</a> ({eur(alts[0]["dop"])})'
               if alts else "Bez dostupnej alternatívy s rovnakou silou a balením")
        li = (f'<li><div class="gline"><a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a>'
              f'<span class="mono">od {sk_date(st["od"])}</span>'
              f'<small>{esc(short_pack(p["pack"]))} · {esc(g["s"])}</small><small>{alt}</small></div></li>')
        (rows_r if st["stav"] == "R" else rows_p if st["stav"] in ("PR", "PZ") else []).append((st["od"], li))
    rows_r.sort(reverse=True)
    rows_p.sort()
    vdate = vyp_all.get("datum")
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Podľa hlásení ŠÚKL{(' k ' + sk_date(vdate)) if vdate else ''}</p>
    <h1 class="page-h1">Výpadky liekov hradených poisťovňou</h1>
    <p class="page-sub">Lieky, pri ktorých držiteľ registrácie ohlásil Štátnemu ústavu pre kontrolu liečiv prerušenie dodávok. Pri každom uvádzame dostupnú alternatívu s rovnakou látkou, silou a balením.</p>
  </section>
  <section class="card"><h2>Prerušené dodávky ({len(rows_r)})</h2><ul class="glist">{''.join(li for _, li in rows_r) or '<li>Žiadne hlásené prerušenia.</li>'}</ul></section>
  <section class="card"><h2>Ohlásené do budúcna ({len(rows_p)})</h2><ul class="glist">{''.join(li for _, li in rows_p) or '<li>Žiadne.</li>'}</ul></section>
  <p class="hint">Zdroj: <a href="{SUKL_VYPADKY}" rel="nofollow">Hlásenia o prerušení, ukončení a obnovení dodávok, ŠÚKL</a>. Dostupnosť v konkrétnej lekárni sa môže líšiť.</p>"""
    write("/vypadky/", page("Výpadky liekov – prerušené dodávky a alternatívy",
                            f"Aktuálny zoznam {plural_lieky(len(rows_r))} hradených poisťovňou s prerušenými dodávkami podľa ŠÚKL a ich dostupné alternatívy.",
                            "/vypadky/", body, breadcrumb_ld(crumb_items)))

    # --- ochranný limit ---
    crumb_items = [("Domov", "/"), ("Ochranný limit", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Limit spoluúčasti</p>
    <h1 class="page-h1">Ochranný limit: koľko vám poisťovňa vráti za doplatky</h1>
    <p class="page-sub">Dôchodcom, ľuďom s preukazom ŤZP, invalidným dôchodcom a malým deťom vracia zdravotná poisťovňa doplatky za lieky nad štvrťročný limit. Nemusíte o nič žiadať.</p>
  </section>
  <section class="card">
    <h2>Kalkulačka</h2>
    <form class="calc" id="calc">
      <label for="skupina">Kto ste
        <select id="skupina">
          <option value="dieta">Dieťa do 6 rokov</option>
          <option value="ztp">Držiteľ preukazu ŤZP alebo invalidný dôchodca</option>
          <option value="dochodca" selected>Starobný alebo predčasný starobný dôchodca</option>
          <option value="iny">Nikto z uvedených</option>
        </select>
      </label>
      <label for="prijem" id="prijem-wrap">Váš dôchodok a príjem
        <select id="prijem">
          <option value="nizky">Dôchodok do 914,40 € mesačne a celkový príjem do 2 743,20 € za štvrťrok</option>
          <option value="vyssi" selected>Vyšší</option>
        </select>
      </label>
      <label for="suma">Započítateľné doplatky za štvrťrok (€)
        <input id="suma" type="number" inputmode="decimal" min="0" step="0.01" value="45">
      </label>
      <p class="result" id="vysledok" aria-live="polite"></p>
    </form>
    <p class="hint">Orientačný výpočet podľa pravidiel na rok 2026. Presnú sumu vám potvrdí vaša zdravotná poisťovňa.</p>
  </section>
  <section class="card">
    <h2>Limity na štvrťrok (2026)</h2>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Kto</th><th>Limit</th><th>Podmienka</th></tr></thead>
      <tbody>
        <tr><td>Dieťa do 6 rokov</td><td class="num">0 €</td><td>Bez ohľadu na príjem. Doplatok za najlacnejší náhradný liek sa neplatí už v lekárni.</td></tr>
        <tr><td>Držiteľ preukazu ŤZP, invalidný dôchodca</td><td class="num">0 €</td><td>Dôchodok do 914,40 € mesačne a celkový príjem do 2 743,20 € za štvrťrok</td></tr>
        <tr><td>Starobný alebo predčasný starobný dôchodca</td><td class="num">0 €</td><td>Dôchodok do 914,40 € mesačne a celkový príjem do 2 743,20 € za štvrťrok</td></tr>
        <tr><td>Držiteľ preukazu ŤZP, invalidný dôchodca</td><td class="num">12 €</td><td>Pri vyššom príjme</td></tr>
        <tr><td>Starobný alebo predčasný starobný dôchodca</td><td class="num">30 €</td><td>Pri vyššom príjme</td></tr>
      </tbody>
    </table></div>
  </section>
  <section class="prose">
    <h2>Čo sa započítava</h2>
    <p>Do limitu sa nepočíta celý doplatok, ktorý zaplatíte, ale len <strong>doplatok za najlacnejší náhradný liek</strong> s rovnakou účinnou látkou. Ak si vyberiete drahšiu značku, rozdiel platíte sami a poisťovňa vám ho nevráti.</p>
    <p>Na stránke každého lieku na tomto webe nájdete v časti <em>Predpis a úhrada</em> presnú sumu, ktorá sa za jedno balenie započíta do limitu.</p>
    <p>Započítavajú sa lieky, zdravotnícke pomôcky a dietetické potraviny na lekársky predpis, ktoré poisťovňa čiastočne hradí. Voľnopredajné lieky sa nepočítajú.</p>
    <h2>Ako dostanete peniaze späť</h2>
    <ul>
      <li>Poisťovňa doplatky sčíta sama z údajov z lekární, nemusíte posielať bločky ani žiadosť.</li>
      <li>Sumu nad limit vráti do 90 dní po skončení štvrťroka, zvyčajne na bankový účet.</li>
      <li>Ak je preplatok nižší ako 3 €, prenesie sa do ďalšieho štvrťroka.</li>
      <li>Ľudia s nulovým limitom a deti do 6 rokov doplatok za najlacnejší náhradný liek v lekárni vôbec neplatia.</li>
    </ul>
    <p>Niektoré poisťovne majú nad rámec zákona vlastné programy, napríklad preplácanie doplatkov deťom. Podrobnosti zistíte u svojej poisťovne.</p>
  </section>"""
    script = """<script>
(function () {
  var f = document.getElementById('calc'); if (!f) return;
  var sk = document.getElementById('skupina'), pr = document.getElementById('prijem'), wrap = document.getElementById('prijem-wrap');
  var su = document.getElementById('suma'), out = document.getElementById('vysledok');
  function eur(n) { return n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function calc() {
    var g = sk.value, low = pr.value === 'nizky', s = parseFloat((su.value || '0').replace(',', '.')) || 0;
    wrap.hidden = (g === 'dieta' || g === 'iny');
    if (g === 'iny') { out.innerHTML = 'Zákonný ochranný limit sa na vás nevzťahuje. Niektoré poisťovne však majú vlastné programy na preplácanie doplatkov.'; return; }
    var limit = g === 'dieta' ? 0 : low ? 0 : (g === 'ztp' ? 12 : 30);
    var back = Math.max(0, s - limit);
    var txt = 'Váš limit je <b>' + eur(limit) + '</b> za štvrťrok. ';
    if (limit === 0) txt += 'Doplatok za najlacnejší náhradný liek by ste nemali platiť už v lekárni.';
    else if (back >= 3) txt += 'Poisťovňa vám vráti približne <b>' + eur(back) + '</b>.';
    else if (back > 0) txt += 'Preplatok ' + eur(back) + ' je nižší ako 3 €, preto sa prenesie do ďalšieho štvrťroka.';
    else txt += 'Limit ste neprekročili, preplatok zatiaľ nevzniká.';
    out.innerHTML = txt;
  }
  f.addEventListener('input', calc); f.addEventListener('change', calc); f.addEventListener('submit', function (e) { e.preventDefault(); });
  calc();
})();
</script>"""
    write("/ochranny-limit/", page("Ochranný limit doplatkov za lieky 2026 – kalkulačka",
                                   "Koľko vám poisťovňa vráti za doplatky za lieky: limity pre dôchodcov, ŤZP a deti na rok 2026, čo sa započítava a kalkulačka preplatku.",
                                   "/ochranny-limit/", body, breadcrumb_ld(crumb_items), script))

    # --- alerts.json pre Moje lieky ---
    alert_items = {}
    for g, p in products:
        a = {}
        c = next_change(p)
        if c and (c["gone"] or (c["diff"] is not None and abs(c["diff"]) >= 0.01)):
            a["n"] = None if c["gone"] else c["dop"]
        st = vyp.get(p["kod"])
        if st:
            a["v"] = [st["stav"], st["od"]]
        if a:
            alert_items[p["kod"]] = a
    (SITE / "alerts.json").write_text(json.dumps({
        "platnost": cur_iso, "next": nxt["platnostIso"] if nxt else None,
        "vypadkyDatum": vyp_all.get("datum"), "items": alert_items}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- Moje lieky ---
    crumb_items = [("Domov", "/"), ("Moje lieky", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Uložené len vo vašom prehliadači</p>
    <h1 class="page-h1">Moje lieky</h1>
    <p class="page-sub">Prehľad liekov, ktoré užívate: aktuálny doplatok, lacnejšia alternatíva, zmeny od budúceho mesiaca a výpadky dodávok. Zoznam nikam neposielame, zostáva v tomto zariadení.</p>
  </section>
  <section id="moje-root" aria-live="polite"><p class="page-sub">Načítavam…</p></section>
{alert_form(None, "Upozornenia e-mailom")}"""
    write("/moje-lieky/", page("Moje lieky – sledovanie doplatkov", "Uložte si lieky, ktoré užívate, a sledujte ich doplatky, zmeny a výpadky na jednom mieste.", "/moje-lieky/", body, breadcrumb_ld(crumb_items)))

    # --- čísla do textov ---
    gap_groups = 0
    for g in groups:
        it = sorted_items(g)
        if len(it) > 1 and it[-1]["dop"] - it[0]["dop"] >= 1:
            gap_groups += 1
    zero_cnt = sum(1 for _, p in products if p["dop"] == 0)

    # --- O nás ---
    crumb_items = [("Domov", "/"), ("O nás", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">O projekte</p>
    <h1 class="page-h1">Prečo vznikol doplatkyliekov.sk</h1>
  </section>
  <section class="article">
    <p>Za rovnaký liek môžete v lekárni doplácať veľmi rozdielne sumy. Rozhoduje to, ktorú značku si vyberiete. Údaje o doplatkoch síce zverejňuje Ministerstvo zdravotníctva SR, ale ako rozsiahle tabuľky, v ktorých sa bežný človek ťažko vyzná. Tento web ich prekladá do zrozumiteľnej podoby.</p>
    <p>V aktuálnom zozname je {plural_lieky(len(products))} hradených poisťovňou. Pri {gap_groups} skupinách liekov s rovnakou látkou, silou a balením ušetríte výberom lacnejšej verzie aspoň 1&nbsp;€ na balení a {zero_cnt} balení je úplne bez doplatku.</p>
    <h2>Odkiaľ sú údaje</h2>
    <ul>
      <li><strong>Zoznam kategorizovaných liekov</strong> Ministerstva zdravotníctva SR: ceny, úhrady poisťovní, doplatky, preskripčné a indikačné obmedzenia. Ministerstvo ho vydáva každý mesiac a my ho sťahujeme automaticky, vrátane zoznamu na budúci mesiac, keď je zverejnený.</li>
      <li><strong>Hlásenia o dodávkach liekov</strong> Štátneho ústavu pre kontrolu liečiv (ŠÚKL): prerušenia, ukončenia a obnovenia dodávok. Kontrolujeme ich každý deň.</li>
    </ul>
    <h2>Nezávislosť</h2>
    <p>Web nie je prepojený so žiadnym výrobcom liekov, lekárňou ani zdravotnou poisťovňou. Poradie liekov určuje výlučne výška doplatku. Ak niekedy na webe pribudnú odkazy na internetové lekárne, budú zreteľne označené a na poradie liekov nebudú mať vplyv.</p>
    <h2>Dôležité upozornenie</h2>
    <p>Údaje majú informačný charakter. Doplatok v zozname je maximálny a lekáreň môže dať zľavu. O zmene lieku sa vždy poraďte s lekárom alebo lekárnikom. Ak nájdete chybu, napíšte nám na <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
    <p>Prevádzkovateľ: {esc(OPERATOR)}.</p>
  </section>"""
    write("/o-nas/", page("O nás – doplatkyliekov.sk", "Kto prevádzkuje doplatkyliekov.sk, odkiaľ sú údaje o doplatkoch za lieky a ako často ich aktualizujeme.", "/o-nas/", body, breadcrumb_ld(crumb_items)))

    # --- Kontakt ---
    crumb_items = [("Domov", "/"), ("Kontakt", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Kontakt</p>
    <h1 class="page-h1">Napíšte nám</h1>
    <p class="page-sub">Našli ste chybu v údajoch, máte nápad na zlepšenie alebo otázku k webu? Ozvite sa.</p>
  </section>
  <section class="card">
    <dl class="facts-dl">
      <dt>E-mail</dt><dd><span class="mono" style="user-select:all">{CONTACT}</span><small>Odpovedáme spravidla do niekoľkých pracovných dní.</small></dd>
      <dt>Prevádzkovateľ</dt><dd>{esc(OPERATOR)}</dd>
    </dl>
    <p class="hint">Na otázky o vašej liečbe, dávkovaní či vhodnosti lieku nevieme odpovedať. S tými sa obráťte na svojho lekára alebo lekárnika.</p>
  </section>"""
    write("/kontakt/", page("Kontakt – doplatkyliekov.sk", "Kontakt na prevádzkovateľa webu doplatkyliekov.sk.", "/kontakt/", body, breadcrumb_ld(crumb_items)))

    # --- Ochrana súkromia ---
    crumb_items = [("Domov", "/"), ("Ochrana súkromia", None)]
    today_sk = sk_date(dt.date.today().isoformat())
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Zásady ochrany osobných údajov</p>
    <h1 class="page-h1">Ochrana súkromia</h1>
    <p class="page-sub">Platné od {today_sk}. Stručne: nepoužívame reklamné ani sledovacie cookies a osobné údaje spracúvame len vtedy, ak sa sami prihlásite na upozornenia e-mailom.</p>
  </section>
  <section class="article">
    <h2>Kto spracúva údaje</h2>
    <p>Prevádzkovateľom webu doplatkyliekov.sk a prevádzkovateľom osobných údajov je {esc(OPERATOR)}, kontakt: <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
    <h2>Prehliadanie webu</h2>
    <p>Web nepoužíva cookies na sledovanie ani reklamu. Návštevnosť meriame službou Cloudflare Web Analytics, ktorá nepoužíva cookies, nevytvára profily návštevníkov a poskytuje nám len súhrnné údaje (napríklad počet zobrazení stránok). Hosting zabezpečuje Cloudflare, Inc., ktorý pri doručovaní stránok technicky spracúva IP adresy na zabezpečenie a ochranu pred útokmi.</p>
    <h2>Moje lieky</h2>
    <p>Zoznam liekov, ktorý si uložíte v sekcii Moje lieky, sa ukladá iba vo vašom prehliadači (localStorage). Nikam ho neodosielame a nemáme k nemu prístup. Vymažete ho odobratím liekov alebo vymazaním údajov prehliadača.</p>
    <h2>Upozornenia e-mailom</h2>
    <p>Ak sa prihlásite na upozornenia, spracúvame:</p>
    <ul>
      <li>vašu e-mailovú adresu,</li>
      <li>zoznam liekov, o ktorých vás máme informovať (kódy ŠÚKL),</li>
      <li>dátum prihlásenia a potvrdenia a údaj o tom, aké upozornenia sme vám už poslali.</li>
    </ul>
    <p><strong>Účel:</strong> zasielanie upozornení na zmeny doplatkov a výpadky dodávok vašich liekov. <strong>Právny základ:</strong> váš výslovný súhlas (čl. 6 ods. 1 písm. a) a čl. 9 ods. 2 písm. a) GDPR). Zoznam liekov môže nepriamo vypovedať o vašom zdraví, preto ho spracúvame len s vaším výslovným súhlasom a nepoužívame ho na žiadny iný účel.</p>
    <p><strong>Doba uchovávania:</strong> do odvolania súhlasu. Súhlas odvoláte kedykoľvek odkazom v každom e-maile alebo e-mailom na {CONTACT}; údaje potom bez zbytočného odkladu vymažeme. Nepotvrdené prihlásenia mažeme po 7 dňoch.</p>
    <p><strong>Sprostredkovatelia:</strong> Cloudflare, Inc., USA (uloženie údajov) a Sendinblue SAS (Brevo), Francúzsko (odosielanie e-mailov). Prenos údajov do USA sa riadi rámcom ochrany údajov EÚ – USA (EU-U.S. Data Privacy Framework), resp. štandardnými zmluvnými doložkami. Údaje nepredávame ani neposkytujeme tretím stranám na marketing.</p>
    <h2>Vaše práva</h2>
    <p>Máte právo na prístup k údajom, ich opravu, vymazanie, obmedzenie spracúvania, prenosnosť a právo kedykoľvek odvolať súhlas. Žiadosti posielajte na {CONTACT}. Máte tiež právo podať sťažnosť Úradu na ochranu osobných údajov Slovenskej republiky (dataprotection.gov.sk).</p>
  </section>"""
    write("/ochrana-sukromia/", page("Ochrana súkromia – doplatkyliekov.sk", "Ako doplatkyliekov.sk spracúva osobné údaje: bez sledovacích cookies, Moje lieky len v prehliadači, upozornenia e-mailom so súhlasom.", "/ochrana-sukromia/", body, breadcrumb_ld(crumb_items)))

    # --- články ---
    articles = [
        ("ako-usetrit-na-liekoch", "Ako ušetriť na liekoch na predpis: 6 praktických krokov",
         "Šesť spôsobov, ako zaplatiť v lekárni menej za lieky na predpis: generiká, predpis názvom liečiva, ochranný limit a benefity poisťovní.",
         f"""<p>Doplatky za lieky sa pri dlhodobej liečbe sčítavajú. Pri lieku na tlak alebo cholesterol, ktorý užívate roky, môže rozdiel medzi najdrahšou a najlacnejšou verziou predstavovať desiatky eur ročne. V aktuálnom zozname je {gap_groups} skupín liekov, v ktorých lacnejšia verzia ušetrí aspoň 1&nbsp;€ na balení.</p>
    <h2>1. Zistite, koľko doplácate a koľko by ste mohli</h2>
    <p>Do <a href="/">vyhľadávania</a> zadajte názov lieku z balenia alebo receptu. Uvidíte všetky lieky s rovnakou účinnou látkou, silou a veľkosťou balenia, ktoré poisťovňa hradí rovnako, zoradené podľa doplatku.</p>
    <h2>2. Opýtajte sa lekárnika na lacnejšiu alternatívu</h2>
    <p>Lekárnik vám môže vydať liek s rovnakou účinnou látkou od iného výrobcu, ak lekár na recepte nevyznačil, že liek sa nesmie zamieňať. Stačí sa opýtať, či existuje verzia s nižším doplatkom.</p>
    <h2>3. Využite predpis názvom účinnej látky</h2>
    <p>Pri mnohých liekoch lekár predpisuje názov účinnej látky, nie konkrétnu značku. Vtedy si v lekárni môžete vybrať ktorýkoľvek liek s touto látkou. Na stránke každého lieku v časti <em>Predpis a úhrada</em> uvidíte, či to platí aj pre váš liek.</p>
    <h2>4. Skontrolujte, či máte nárok na ochranný limit</h2>
    <p>Dôchodcom, ľuďom s preukazom ŤZP, invalidným dôchodcom a deťom do 6 rokov vracia poisťovňa doplatky nad štvrťročný limit. Pozor, započítava sa len doplatok za najlacnejší náhradný liek. Viac v našom <a href="/ochranny-limit/">prehľade ochranného limitu</a>.</p>
    <h2>5. Pozrite si benefity svojej poisťovne</h2>
    <p>Zdravotné poisťovne majú vlastné programy, napríklad preplácanie doplatkov deťom alebo príspevky na lieky po splnení preventívnych prehliadok. Podmienky sa líšia, preto si ich overte priamo u svojej poisťovne.</p>
    <h2>6. Sledujte zmeny vopred</h2>
    <p>Doplatky sa menia každý mesiac. Ministerstvo zverejňuje nový zoznam vopred, takže zmeny vidíte skôr, než nastanú. Pozrite si <a href="/zmeny/">zmeny od budúceho mesiaca</a> alebo si lieky uložte do <a href="/moje-lieky/">Mojich liekov</a> a nechajte si poslať upozornenie.</p>
    <blockquote>O zmene lieku sa vždy poraďte s lekárom alebo lekárnikom, najmä ak užívate viac liekov naraz.</blockquote>"""),
        ("co-su-generika", "Čo sú generiká a sú rovnako účinné ako originál?",
         "Generikum obsahuje rovnakú účinnú látku ako originálny liek. Vysvetľujeme, ako sa schvaľuje, v čom sa líši a kedy byť pri zámene opatrný.",
         """<p>Generikum je liek, ktorý obsahuje rovnakú účinnú látku v rovnakom množstve a rovnakej liekovej forme ako pôvodný, takzvaný originálny liek. Na trh môže prísť po uplynutí patentovej ochrany originálu.</p>
    <h2>Ako sa schvaľuje</h2>
    <p>Výrobca generika musí liekovej agentúre preukázať, že jeho liek je s originálom <strong>bioekvivalentný</strong>: účinná látka sa v tele vstrebáva v rovnakom rozsahu a rovnakou rýchlosťou v rámci prísne stanovených limitov. Generiká podliehajú rovnakým požiadavkám na kvalitu a výrobu ako originály. Na Slovensku ich registruje Štátny ústav pre kontrolu liečiv alebo sú registrované centrálne pre celú Európsku úniu.</p>
    <h2>V čom sa môže líšiť</h2>
    <ul>
      <li>názvom, výrobcom, obalom, tvarom alebo farbou tablety,</li>
      <li>pomocnými látkami (napríklad farbivá či plnivá), čo je dôležité pri alergiách alebo intoleranciách,</li>
      <li>cenou a doplatkom, ktorý je často výrazne nižší.</li>
    </ul>
    <h2>Prečo je lacnejšie</h2>
    <p>Výrobca generika nemusí znova financovať vývoj a rozsiahle klinické štúdie účinnej látky, ktoré už absolvoval originál. Preto môže liek ponúknuť lacnejšie.</p>
    <h2>Kedy byť opatrnejší</h2>
    <p>Pri niektorých liekoch s úzkym terapeutickým rozpätím, napríklad pri niektorých liekoch na epilepsiu, na štítnu žľazu alebo na riedenie krvi, odporúčajú lekári zbytočne nestriedať výrobcov. Ak užívate takýto liek, zmenu vždy konzultujte s lekárom.</p>
    <blockquote>Na stránke každého lieku vidíte pri alternatívach označenie Originál alebo Generikum, takže hneď viete, o aký liek ide.</blockquote>"""),
        ("preco-sa-meni-doplatok", "Prečo sa mení doplatok za liek",
         "Doplatky za lieky sa menia každý mesiac. Vysvetľujeme, ako vzniká doplatok, čo je kategorizácia a prečo rovnaký liek môže zrazu stáť viac.",
         """<p>Doplatok je rozdiel medzi cenou lieku v lekárni a sumou, ktorú za liek uhradí zdravotná poisťovňa. Obe čísla určuje Zoznam kategorizovaných liekov, ktorý Ministerstvo zdravotníctva SR vydáva každý mesiac.</p>
    <h2>Čo je kategorizácia</h2>
    <p>Kategorizácia je proces, v ktorom ministerstvo rozhoduje, ktoré lieky budú hradené z verejného zdravotného poistenia, za akú najvyššiu cenu a v akej výške ich poisťovňa uhradí. Lieky s rovnakou účinnou látkou, silou a veľkosťou balenia tvoria skupinu, v ktorej poisťovňa hradí rovnakú alebo porovnateľnú sumu.</p>
    <h2>Prečo sa doplatok mení</h2>
    <ul>
      <li><strong>Zmena úhrady:</strong> keď na trh príde lacnejší liek, úhrada poisťovne pre celú skupinu sa môže znížiť. Výrobcovia drahších liekov, ktorí cenu neznížia, majú potom vyšší doplatok.</li>
      <li><strong>Zmena ceny:</strong> výrobca môže cenu lieku znížiť alebo zvýšiť v rámci povolenej maximálnej ceny.</li>
      <li><strong>Porovnávanie cien v EÚ:</strong> ministerstvo pravidelne porovnáva ceny liekov s ostatnými krajinami Únie a podľa toho upravuje maximálne ceny.</li>
      <li><strong>Vyradenie zo zoznamu:</strong> ak liek zo zoznamu vypadne, poisťovňa ho prestane hradiť a pacient platí celú cenu.</li>
    </ul>
    <h2>Ako sa dozviete o zmene vopred</h2>
    <p>Nový zoznam býva zverejnený pred začiatkom mesiaca, v ktorom platí. Na stránke <a href="/zmeny/">Zmeny doplatkov</a> porovnávame nový zoznam s aktuálnym. Pri každom lieku zároveň uvidíte graf vývoja doplatku za posledné mesiace.</p>"""),
    ]
    crumb_items = [("Domov", "/"), ("Články", None)]
    lis = "".join(f'<li><a href="/clanky/{sl}/"><strong>{esc(t)}</strong><span>{esc(d)}</span></a></li>' for sl, t, d, _ in articles)
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Návody a vysvetlenia</p>
    <h1 class="page-h1">Články</h1>
  </section>
  <ul class="article-list">{lis}</ul>"""
    write("/clanky/", page("Články o liekoch a doplatkoch", "Návody, ako ušetriť na liekoch na predpis, čo sú generiká a prečo sa menia doplatky.", "/clanky/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/clanky/", "0.6"))
    for sl, t, d, html_body in articles:
        path = f"/clanky/{sl}/"
        crumb_items = [("Domov", "/"), ("Články", "/clanky/"), (t, None)]
        ld = [breadcrumb_ld(crumb_items), {"@context": "https://schema.org", "@type": "Article", "headline": t,
              "description": d, "inLanguage": "sk", "author": {"@type": "Person", "name": OPERATOR},
              "publisher": {"@type": "Organization", "name": "doplatkyliekov.sk"}, "mainEntityOfPage": BASE + path}]
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Článok</p>
    <h1 class="page-h1">{esc(t)}</h1>
  </section>
  <section class="article">
    {html_body}
  </section>
  <p><a class="cta" href="/">Vyhľadať liek →</a></p>"""
        write(path, page(t, d, path, body, ld))
        urls.append((path, "0.6"))
    urls += [("/moje-lieky/", "0.5"), ("/o-nas/", "0.3"), ("/kontakt/", "0.3"), ("/ochrana-sukromia/", "0.2")]

    # --- výsledky prihlásenia na upozornenia ---
    for sl, title, text in [
        ("potvrdene", "Prihlásenie je potvrdené", "Ďakujeme. Keď sa zmení doplatok niektorého z vašich liekov alebo výrobca ohlási výpadok, pošleme vám e-mail. Odhlásiť sa môžete odkazom v každom e-maile."),
        ("odhlasene", "Boli ste odhlásený", "Upozornenia vám už posielať nebudeme a vaše údaje sme vymazali. Zoznam Moje lieky vo vašom prehliadači zostáva."),
        ("chyba", "Odkaz je neplatný alebo vypršal", "Odkaz na potvrdenie platí 7 dní. Prihláste sa prosím znova na stránke Moje lieky."),
    ]:
        body = f"""  <section class="intro">
    <p class="eyebrow">Upozornenia e-mailom</p>
    <h1 class="page-h1">{esc(title)}</h1>
    <p class="page-sub">{esc(text)}</p>
    <p><a class="cta" href="/moje-lieky/">Moje lieky →</a></p>
  </section>"""
        html_page = page(title, text, f"/upozornenia/{sl}/", body).replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex">')
        write(f"/upozornenia/{sl}/", html_page)

    # --- 404 ---
    body404 = """  <section class="intro">
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

    n_atc = len([u for u, _ in urls if u.startswith("/skupina/")])
    print(f"Vygenerované: {len(products)} stránok liekov, {len(by_subst)} látok, {n_atc} skupín, "
          f"sitemap s {len(urls)} adresami. História: {len(history)} mesiacov, "
          f"budúci zoznam: {'áno' if nxt else 'nie'}, výpadky: {len(vyp)}.")


if __name__ == "__main__":
    build()
