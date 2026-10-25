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
import math
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "data"
BASE = "https://doplatkyliekov.sk"
GENERATED = ["ai", "asistent", "pristupnost", "choroby", "bez-doplatku", "statistiky", "liek", "latka", "lieky", "skupina", "skupiny", "zmeny", "vypadky", "ochranny-limit", "assets",
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


PACK_RE = re.compile(r"^(tbl|cps|drg|tob|lyo)[a-z .]*?\s(\d+)", re.I)


def pack_count(pack):
    """Počet tabliet/kapsúl v balení pre pevné perorálne lieky, inak None."""
    m = PACK_RE.match(pack or "")
    if not m:
        return None
    n = int(m.group(2))
    return n if 1 <= n <= 1000 else None


def unit_words(pack):
    """(jednotné číslo, genitív množného čísla) podľa liekovej formy."""
    f = (pack or "").split(" ")[0].lower()
    return {"tbl": ("tableta", "tabliet"), "cps": ("kapsula", "kapsúl"), "drg": ("dražé", "dražé")}.get(f, ("kus", "kusov"))


def lean_groups(groups):
    """Ľahké dáta pre prehliadač: [kód, názov, balenie, konečná cena, úhrada, doplatok, typ, započítateľný doplatok, kusov]."""
    return [{"a": g["a"], "s": g["s"], "f": g["f"],
             "i": [[it["kod"], it["name"], it["pack"], it["konc"], it["uzp"], it["dop"], it.get("typ"),
                    it.get("pdop"), pack_count(it["pack"])] for it in g["i"]]}
            for g in groups]


# ochorenia → ATC predpony (len orientačné zaradenie podľa ATC klasifikácie)
CONDITIONS = [
    ("vysoky-krvny-tlak", "vysoký krvný tlak", "Lieky na vysoký krvný tlak", ["C02", "C03", "C07", "C08", "C09"],
     "Lieky na liečbu vysokého krvného tlaku (hypertenzie) patria medzi najčastejšie predpisované lieky. Mnohé sa užívajú roky, preto sa rozdiel v doplatku výrazne prejaví."),
    ("cholesterol", "vysoký cholesterol", "Lieky na cholesterol", ["C10"],
     "Lieky na znižovanie cholesterolu a tukov v krvi, napríklad statíny a ezetimib, vrátane ich kombinácií."),
    ("cukrovka", "cukrovka", "Lieky na cukrovku", ["A10"],
     "Inzulíny a lieky na zníženie hladiny cukru v krvi pri cukrovke (diabetes mellitus)."),
    ("stitna-zlaza", "štítna žľaza", "Lieky na štítnu žľazu", ["H03"],
     "Lieky pri zníženej alebo zvýšenej činnosti štítnej žľazy. Pri týchto liekoch lekári neodporúčajú zbytočne striedať výrobcov."),
    ("riedenie-krvi", "riedenie krvi", "Lieky na riedenie krvi", ["B01"],
     "Lieky proti zrážaniu krvi (antikoagulanciá a antiagreganciá), napríklad po infarkte, mŕtvici alebo pri fibrilácii predsiení."),
    ("srdce", "choroby srdca", "Lieky na srdce", ["C01"],
     "Lieky pri srdcovom zlyhaní, poruchách rytmu a angíne pectoris."),
    ("astma-chochp", "astma a CHOCHP", "Lieky na astmu a CHOCHP", ["R03"],
     "Inhalačné a iné lieky pri astme a chronickej obštrukčnej chorobe pľúc."),
    ("alergia", "alergia", "Lieky na alergiu", ["R06", "R01AD", "S01G"],
     "Antihistaminiká, nosové spreje s kortikoidmi a očné kvapky pri alergii."),
    ("zaludok-reflux", "žalúdok a pálenie záhy", "Lieky na žalúdok a pálenie záhy", ["A02"],
     "Lieky znižujúce tvorbu žalúdočnej kyseliny, napríklad omeprazol či pantoprazol, pri refluxe a vredovej chorobe."),
    ("bolest-zapal", "bolesť a zápal", "Lieky na bolesť a zápal", ["M01A", "N02A", "N02B"],
     "Lieky proti bolesti a protizápalové lieky hradené poisťovňou."),
    ("migrena", "migréna", "Lieky na migrénu", ["N02C"],
     "Lieky na liečbu a predchádzanie záchvatov migrény."),
    ("depresia-uzkost", "depresia a úzkosť", "Lieky na depresiu a úzkosť", ["N06A", "N05B"],
     "Antidepresíva a lieky proti úzkosti."),
    ("spanok", "poruchy spánku", "Lieky na spanie", ["N05C"],
     "Hypnotiká a sedatíva hradené poisťovňou."),
    ("psychiatria", "psychózy", "Lieky na psychózy a bipolárnu poruchu", ["N05A"],
     "Antipsychotiká používané pri schizofrénii, bipolárnej poruche a ďalších ochoreniach."),
    ("epilepsia", "epilepsia", "Lieky na epilepsiu", ["N03"],
     "Antiepileptiká. Pri týchto liekoch je zámena výrobcu citlivá, vždy ju konzultujte s lekárom."),
    ("parkinson", "Parkinsonova choroba", "Lieky na Parkinsonovu chorobu", ["N04"],
     "Lieky zmierňujúce príznaky Parkinsonovej choroby."),
    ("demencia", "demencia", "Lieky na demenciu", ["N06D"],
     "Lieky pri Alzheimerovej chorobe a iných demenciách."),
    ("osteoporoza", "osteoporóza", "Lieky na osteoporózu", ["M05"],
     "Lieky posilňujúce kosti pri osteoporóze."),
    ("dna", "dna", "Lieky na dnu", ["M04"],
     "Lieky znižujúce kyselinu močovú a lieky pri záchvate dny."),
    ("prostata-mocovy-mechur", "prostata a močový mechúr", "Lieky na prostatu a močový mechúr", ["G04"],
     "Lieky pri zväčšenej prostate a pri hyperaktívnom močovom mechúre."),
    ("glaukom", "zelený zákal", "Lieky na zelený zákal (glaukóm)", ["S01E"],
     "Očné kvapky znižujúce vnútroočný tlak."),
    ("antibiotika", "infekcie", "Antibiotiká", ["J01"],
     "Antibiotiká na liečbu bakteriálnych infekcií hradené poisťovňou."),
    ("pohlavne-hormony", "hormonálna liečba", "Pohlavné hormóny", ["G03"],
     "Lieky s pohlavnými hormónmi hradené poisťovňou, napríklad pri hormonálnej substitučnej liečbe."),
]


COND_LABELS = {
    "C09": "ACE inhibítory a sartany", "M01A": "Nesteroidové protizápalové lieky", "N02A": "Opioidy",
    "N02B": "Iné lieky proti bolesti", "N02C": "Lieky na migrénu", "N06A": "Antidepresíva", "N05B": "Anxiolytiká",
    "N05C": "Hypnotiká a sedatíva", "N05A": "Antipsychotiká", "N06D": "Lieky na demenciu",
    "S01E": "Lieky na glaukóm", "R01AD": "Nosové spreje s kortikoidmi", "S01G": "Očné lieky pri alergii",
}


def conditions_for(atc):
    return [c for c in CONDITIONS if any(atc.startswith(x) for x in c[3])]


def year_calc(p, cheapest):
    """Kalkulačka ročného doplatku (len pre tablety a kapsuly). Predvolený výpočet je v HTML, JS ho prepočíta."""
    ks = pack_count(p["pack"])
    if not ks or p["dop"] is None:
        return ""
    one, many = unit_words(p["pack"])
    best = cheapest if (cheapest and cheapest["dop"] is not None and p["dop"] - cheapest["dop"] > 0.005) else None
    year = 365 / ks * p["dop"]
    packs = 365 / ks
    best_html = ""
    if best:
        by = 365 / ks * best["dop"]
        best_html = (f'<p class="yc-best">S liekom <a href="/liek/{esc(best["slug"])}/">{esc(best["name"])}</a> by ste doplatili '
                     f'<b data-yc="best">{eur(by)}</b> ročne. Ušetríte <b class="save" data-yc="save">{eur(year - by)}</b> za rok.</p>')
    attrs = f'data-ks="{ks}" data-dop="{p["dop"]}"' + (f' data-best="{best["dop"]}"' if best else "")
    return f"""
  <section class="card year-calc" {attrs}>
    <h2>Koľko doplatíte za rok</h2>
    <label class="yc-dose">Koľko {esc(many)} užívate denne
      <span class="yc-input"><button type="button" data-step="-0.5" aria-label="Menej">−</button><input type="number" inputmode="decimal" min="0.25" max="20" step="0.25" value="1" aria-label="Počet denne"><button type="button" data-step="0.5" aria-label="Viac">+</button></span>
    </label>
    <p class="yc-out">Balenie ({ks} {esc(many if ks >= 5 else one)}) vám vydrží <b data-yc="days">{ks} dní</b>. Za rok spotrebujete približne <b data-yc="packs">{packs:.1f}</b> balenia a doplatíte <b class="big-num" data-yc="year">{eur(year)}</b>.</p>
    {best_html}
    <p class="hint">Orientačný výpočet pri nepretržitom užívaní 365 dní a dnešnom doplatku. Dávkovanie vždy určuje lekár.</p>
  </section>"""


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
         '<meta name="theme-color" content="#05090b">'
         '<link rel="manifest" href="/manifest.webmanifest">'
         '<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">'
         '<meta name="apple-mobile-web-app-capable" content="yes">'
         '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
         '<meta name="apple-mobile-web-app-title" content="Doplatky">')

CAPSULE = ('<svg class="capsule" width="40" height="22" viewBox="0 0 40 22" aria-hidden="true"><rect x="1" y="1" width="38" height="20" rx="10" '
           'fill="none" stroke="var(--accent)" stroke-width="2"/><path d="M11 1h9v20h-9a10 10 0 0 1 0-20z" fill="var(--accent)"/></svg>')

ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' "
        "rx='8' fill='%2305090b'/%3E%3Crect x='4' y='10' width='24' height='12' rx='6' fill='none' stroke='%2345f0c0' "
        "stroke-width='2'/%3E%3Cpath d='M10 10h6v12h-6a6 6 0 0 1 0-12z' fill='%2345f0c0'/%3E%3C/svg%3E")


# ---------- spoločné rozloženie: hlavička, menu, zobrazenie, spodná lišta, pätička ----------

def _svg(d):
    return (f'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{d}</svg>')


IC = {
    "search": _svg('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
    "mine": _svg('<path d="M6 3h12v18l-6-4.5L6 21z"/>'),
    "heart": _svg('<path d="M20.4 5.6a5 5 0 0 0-7.1 0L12 6.9l-1.3-1.3a5 5 0 0 0-7.1 7.1L12 21l8.4-8.3a5 5 0 0 0 0-7.1z"/><path d="M3.5 12h4l1.5-3 3 6 1.5-3h7"/>'),
    "shield": _svg('<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>'),
    "menu": _svg('<path d="M4 6h16M4 12h16M4 18h16"/>'),
    "trend": _svg('<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>'),
    "alert": _svg('<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17.5v.5"/>'),
    "zero": _svg('<circle cx="12" cy="12" r="9"/><path d="M9 12.5l2 2 4-4.5"/>'),
    "sun": _svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    "moon": _svg('<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>'),
    "auto": _svg('<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>'),
    "spark": _svg('<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'),
    "bell": _svg('<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
}

# skript v <head>: použije uloženú voľbu zobrazenia ešte pred vykreslením (bez bliknutia)
PREFS_HEAD = ("<script>(function(){var d=document.documentElement;d.dataset.theme='dark';d.dataset.fs='1';"
              "try{var s=JSON.parse(localStorage.getItem('zobrazenie.v1')||'{}');if(s.t)d.dataset.theme=s.t;"
              "if(s.f!=null)d.dataset.fs=s.f;if(s.c)d.dataset.contrast='high';}catch(e){}var t=d.dataset.theme;"
              "d.dataset.eff=(t==='light'||(t==='auto'&&window.matchMedia&&matchMedia('(prefers-color-scheme: light)').matches))?'light':'dark';})();</script>")

# (adresa, názov, krátky názov na mobil, triedy: m = aj na mobile, x-960 / x-1100 = skryť pod danou šírkou)
NAV_TOP = [("/", "Vyhľadať", "", ""), ("/choroby/", "Ochorenia", "", ""),
           ("/zmeny/", "Zmeny", "Zmeny", "m"), ("/vypadky/", "Výpadky", "Výpadky", "m"),
           ("/bez-doplatku/", "Bez doplatku", "Bez doplatku", "m x-960"), ("/ochranny-limit/", "Ochranný limit", "Limit", "m x-960"),
           ("/statistiky/", "Štatistiky", "", "x-1100")]

MENU = [
    ("Lieky", [("/", "Vyhľadať liek"), ("/asistent/", "AI asistent"), ("/choroby/", "Lieky podľa ochorenia"), ("/bez-doplatku/", "Lieky bez doplatku"),
               ("/skupiny/", "Lieky podľa skupín"), ("/lieky/", "Účinné látky")]),
    ("Pre vás", [("/moje-lieky/", "Moje lieky"), ("/ochranny-limit/", "Ochranný limit a prehľad doplatkov"),
                 ("/upozornenia/sprava/", "Upozornenia e-mailom"), ("/clanky/", "Články a návody")]),
    ("Zmeny a dostupnosť", [("/zmeny/", "Zmeny doplatkov"), ("/vypadky/", "Výpadky liekov"), ("/statistiky/", "Doplatky v číslach")]),
    ("O webe", [("/o-nas/", "O nás"), ("/kontakt/", "Kontakt"), ("/ochrana-sukromia/", "Ochrana súkromia"),
                ("/pristupnost/", "Vyhlásenie o prístupnosti")]),
]


def _cur(href, path):
    if href == "/":
        return ' aria-current="page"' if path == "/" else ""
    return ' aria-current="page"' if path.startswith(href) else ""


def site_header(path):
    def nav_link(h, t, short, cls):
        classes = (cls + (" ai-link" if h == "/asistent/" else "")).strip()
        label = f'<span class="l">{esc(t)}</span><span class="s">{esc(short)}</span>' if short else esc(t)
        return f'<a href="{h}"{_cur(h, path)}{f" class=\"{classes}\"" if classes else ""}>{IC["spark"] if h == "/asistent/" else ""}{label}</a>'
    links = "".join(nav_link(*x) for x in NAV_TOP)
    return f"""<a class="skip" href="#obsah">Preskočiť na obsah</a>
<header class="site-head">
  <div class="site-head-in">
    <a class="brand-link" href="/" aria-label="doplatkyliekov.sk – úvod">{CAPSULE}<span class="brand-name">doplatky<b>liekov</b>.sk</span></a>
    <nav class="top-nav" aria-label="Hlavná navigácia">{links}</nav>
    <a class="head-btn mine" href="/moje-lieky/"{_cur("/moje-lieky/", path)}>{IC["mine"]}<span class="lbl">Moje lieky</span><span data-mine-count hidden></span></a>
    <a class="head-btn ai-btn" href="/asistent/"{_cur("/asistent/", path)} aria-label="AI asistent" title="AI asistent – opýtajte sa na lieky a doplatky">{IC["spark"]}<span class="lbl">AI asistent</span></a>
    <button type="button" class="head-btn theme-btn" data-theme-toggle aria-label="Prepnúť svetlý alebo tmavý režim" title="Svetlý / tmavý režim"><span class="to-light">{IC["sun"]}</span><span class="to-dark">{IC["moon"]}</span></button>
    <button type="button" class="head-btn disp" data-open="zobrazenie" aria-haspopup="dialog" aria-controls="zobrazenie" aria-label="Zobrazenie: farebný režim, veľkosť písma, režim pre slabozrakých" title="Zobrazenie: farebný režim, veľkosť písma, režim pre slabozrakých"><span class="aa" aria-hidden="true">Aa</span><span class="lbl">Zobrazenie</span></button>
    <button type="button" class="head-btn menu-btn" data-open="menu" aria-haspopup="dialog" aria-controls="menu">{IC["menu"]}<span class="lbl">Menu</span></button>
  </div>
</header>"""


def site_panels(path):
    groups = "".join(
        f'<section><h3>{esc(g)}</h3><ul>' + "".join(f'<li><a href="{h}"{_cur(h, path) if h != "/" else ""}>{esc(t)}</a></li>' for h, t in items)
        + "</ul></section>" for g, items in MENU)
    return f"""<div class="sheet-backdrop" hidden data-close></div>
<div class="sheet" id="menu" role="dialog" aria-modal="true" aria-labelledby="menu-h" hidden>
  <div class="sheet-head"><h2 id="menu-h">Menu</h2><button type="button" class="sheet-close" data-close aria-label="Zavrieť menu">×</button></div>
  <button type="button" class="head-btn menu-display" data-open="zobrazenie"><span class="aa" aria-hidden="true">Aa</span>Zobrazenie: svetlý režim, písmo, pre slabozrakých</button>
  <nav class="menu-groups" aria-label="Všetky stránky">{groups}</nav>
</div>
<div class="sheet settings" id="zobrazenie" role="dialog" aria-modal="true" aria-labelledby="zob-h" hidden>
  <div class="sheet-head"><h2 id="zob-h">Zobrazenie</h2><button type="button" class="sheet-close" data-close aria-label="Zavrieť nastavenia zobrazenia">×</button></div>
  <fieldset class="set-group">
    <legend>Farebný režim</legend>
    <div class="seg">
      <label>{IC["moon"]}<input type="radio" name="theme" value="dark">Tmavý</label>
      <label>{IC["sun"]}<input type="radio" name="theme" value="light">Svetlý</label>
      <label>{IC["auto"]}<input type="radio" name="theme" value="auto">Podľa zariadenia</label>
    </div>
  </fieldset>
  <div class="set-group">
    <p class="set-label" id="fs-label">Veľkosť písma</p>
    <div class="fs-row" role="group" aria-labelledby="fs-label">
      <button type="button" class="minus" data-fs="-1" aria-label="Zmenšiť písmo">A−</button>
      <output id="fs-out" aria-live="polite">100 %</output>
      <button type="button" class="plus" data-fs="1" aria-label="Zväčšiť písmo">A+</button>
    </div>
  </div>
  <label class="switch">
    <strong>Režim pre slabozrakých</strong>
    <input type="checkbox" role="switch" id="set-contrast">
    <small>Vysoký kontrast, väčšie a čitateľnejšie písmo, podčiarknuté odkazy, bez animácií a priehľadných efektov.</small>
  </label>
  <button type="button" class="set-reset" id="set-reset">Obnoviť pôvodné zobrazenie</button>
  <p class="set-note">Voľba sa uloží len v tomto prehliadači.</p>
</div>"""


def bottom_nav(path):
    items = [("/", "Hľadať", "search"), ("/moje-lieky/", "Moje lieky", "mine"), ("/asistent/", "Asistent", "spark"),
             ("/choroby/", "Ochorenia", "heart")]
    out = []
    for h, t, ic in items:
        badge = '<span data-mine-count hidden></span>' if ic == "mine" else ""
        out.append(f'<a href="{h}"{_cur(h, path)}>{IC[ic]}{badge}<span>{esc(t)}</span></a>')
    out.append(f'<button type="button" data-open="menu" aria-haspopup="dialog" aria-controls="menu">{IC["menu"]}<span>Menu</span></button>')
    return f'<nav class="bottom-nav" aria-label="Rýchle odkazy">{"".join(out)}</nav>'


def site_footer(platnost_html):
    cols = "".join(
        f'<section><h2>{esc(g)}</h2><ul>' + "".join(f'<li><a href="{h}">{esc(t)}</a></li>' for h, t in items) + "</ul></section>"
        for g, items in [MENU[0], (MENU[1][0], MENU[1][1] + MENU[2][1]), MENU[3]])
    return f"""<footer>
    <nav class="foot-cols" aria-label="Ďalšie stránky">{cols}</nav>
    <p>Zdroj: Zoznam kategorizovaných liekov Ministerstva zdravotníctva SR, platný od {platnost_html}, a hlásenia o dodávkach liekov ŠÚKL. Ceny sú v eurách s DPH.</p>
    <p>Stránka slúži na informáciu, nie je reklamou na lieky a nenahrádza radu lekára ani lekárnika. Poradie liekov určuje výlučne výška doplatku.</p>
  </footer>"""


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
[hidden] { display: none !important; }
.mine-tools .danger { color: var(--save); border-color: var(--save); }
.mine-tools .danger.armed { background: var(--save); color: var(--bg); }
/* ročný doplatok */
.year-calc .yc-dose { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px 16px; font-weight: 600; }
.yc-input { display: inline-flex; align-items: center; border: 1px solid var(--line-strong); border-radius: 999px; overflow: hidden; background: var(--raise); }
.yc-input button { font: inherit; font-size: 20px; width: 44px; height: 42px; border: 0; background: transparent; color: var(--ink); cursor: pointer; }
.yc-input button:hover { background: var(--accent-soft); color: var(--accent); }
.yc-input input { width: 64px; height: 42px; border: 0; background: transparent; color: var(--ink); text-align: center; font-family: var(--font-mono); font-size: 18px; font-weight: 600; -moz-appearance: textfield; }
.yc-input input::-webkit-inner-spin-button, .yc-input input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.yc-out { font-size: 17px; line-height: 1.7; }
.yc-out b { font-family: var(--font-mono); font-weight: 600; }
.yc-out .big-num { color: var(--save); font-size: 22px; }
.yc-best { padding: 14px 16px; border-radius: var(--r); background: var(--accent-soft); border: 1px solid var(--line-strong); line-height: 1.6; }
.yc-best b { font-family: var(--font-mono); }
.yc-best .save { color: var(--accent); font-size: 19px; }
.purpose a.cond { border-color: rgba(255, 178, 107, .35); }
.purpose a.cond:hover { border-color: var(--save); color: var(--save); }
.stats3.big b { font-size: 26px; color: var(--accent); }
.card h2 small.mono { font-size: 12px; color: var(--faint); font-weight: 400; margin-left: 6px; }
.cond-list a { border-left: 3px solid var(--accent); }
/* lieky bez doplatku */
.filter { font: inherit; font-size: 17px; color: var(--ink); background: var(--raise); border: 1px solid var(--line-strong); border-radius: 999px; padding: 14px 20px; width: 100%; }
.filter:focus-visible { outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }
.zero-group { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 0 18px; }
.zero-group summary { cursor: pointer; display: flex; justify-content: space-between; gap: 12px; align-items: baseline; padding: 18px 0; font-weight: 600; font-size: 17px; list-style: none; }
.zero-group summary::-webkit-details-marker { display: none; }
.zero-group summary::before { content: "+"; font-family: var(--font-mono); color: var(--accent); margin-right: 10px; }
.zero-group[open] summary::before { content: "−"; }
.zero-group summary span { flex: 1; }
.zero-group summary small { color: var(--muted); font-weight: 400; font-size: 14px; white-space: nowrap; }
.zero-group .glist { padding-bottom: 18px; }
.zero-group .glist li { background: transparent; }
/* tracker ochranného limitu */
.tr-quarter { display: flex; align-items: center; justify-content: center; gap: 16px; font-family: var(--font-display); font-size: 18px; }
.tr-quarter button, .tr-row button, .mine-tools button, .shared-banner button, .install-card button { font: inherit; font-size: 16px; font-weight: 600; cursor: pointer; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--raise); color: var(--ink); padding: 10px 18px; }
.tr-quarter button { width: 44px; height: 44px; padding: 0; font-size: 22px; }
.tr-quarter button:hover, .mine-tools button:hover { border-color: var(--accent); color: var(--accent); }
.tr-row button[type=submit], .shared-banner button, .install-card button { background: var(--accent); color: var(--accent-ink); border-color: transparent; }
.tr-row button[disabled] { opacity: .45; cursor: not-allowed; }
.tr-add { display: grid; gap: 12px; position: relative; }
.tr-add label { display: grid; gap: 6px; font-weight: 600; font-size: 15px; }
.tr-add input { font: inherit; font-weight: 400; font-size: 17px; color: var(--ink); background: var(--raise); border: 1px solid var(--line-strong); border-radius: 12px; padding: 12px 14px; min-width: 0; color-scheme: dark; }
.tr-add input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.tr-row { display: grid; grid-template-columns: 100px minmax(0, 1fr) auto; gap: 12px; align-items: end; }
.tr-results { list-style: none; margin: 0; padding: 6px; display: grid; gap: 2px; background: var(--surface-solid); border: 1px solid var(--line-strong); border-radius: var(--r); max-height: 320px; overflow: auto; }
.tr-results button { width: 100%; text-align: left; font: inherit; color: var(--ink); background: transparent; border: 0; border-radius: 10px; padding: 10px 12px; display: grid; gap: 2px; cursor: pointer; }
.tr-results button:hover { background: var(--accent-soft); }
.tr-results small { color: var(--muted); font-size: 13px; }
.tr-none, .tr-empty { color: var(--muted); padding: 10px 12px; }
.tr-picked { font-size: 14px; color: var(--accent); min-height: 1.4em; }
.tr-more { font-size: 15px; color: var(--muted); }
.linkish { font: inherit; background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
.tr-list li { grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 12px; }
.tr-name { min-width: 0; overflow-wrap: anywhere; font-weight: 500; }
.tr-sum { display: grid; gap: 8px; padding: 18px 20px; border-radius: var(--r); background: var(--accent-soft); border: 1px solid var(--line-strong); font-size: 17px; line-height: 1.55; }
.tr-sum b { font-family: var(--font-mono); color: var(--accent); font-size: 19px; }
.tr-sum b.save { color: var(--save); }
/* Moje lieky: dávkovanie, nástroje, zdieľanie, inštalácia */
.mine-dose { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: 14px; color: var(--muted); }
.mine-dose input { width: 64px; font: inherit; font-family: var(--font-mono); font-size: 15px; color: var(--ink); background: var(--raise); border: 1px solid var(--line-strong); border-radius: 8px; padding: 4px 8px; margin: 0 4px; }
.mine-year { color: var(--muted); }
.mine-tools { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; }
.mine-tools a { font-size: 15px; }
.mine-tools .form-msg { flex-basis: 100%; }
.shared-banner { border-color: var(--save); margin-bottom: 18px; }
.shared-banner .linkish { margin-left: 8px; }
.install-card { border-color: var(--line-strong); }
.print-only { display: none; }
@media (max-width: 560px) {
  .tr-row { grid-template-columns: 90px minmax(0, 1fr); }
  .tr-row button { grid-column: 1 / -1; }
  .stats3.big b { font-size: 20px; }
}
@media print {
  :root { --ink: #000; --muted: #333; --accent: #000; --save: #000; }
  body { background: #fff !important; color: #000; font-size: 12pt; }
  body::before, body::after, .topbar, .crumbs, footer, .mine-tools, .install-card, .mine-btn, .card:has(.alert-form),
  body:has(#moje-root) .intro, #moje-root > .mine-summary, #moje-root > ul, .shared-banner { display: none !important; }
  .card, .slip, .glist li { background: #fff !important; border-color: #bbb !important; box-shadow: none !important; }
  .wrap { max-width: none; gap: 12px; }
  .print-only { display: block; }
  .print-only, .print-only * { color: #000 !important; text-shadow: none !important; }
  table.print-only { display: table; }
  .print-head { display: grid; gap: 4px; margin-bottom: 12px; }
  .print-head b { font-size: 18pt; }
  .print-table { width: 100%; border-collapse: collapse; font-size: 10.5pt; }
  .print-table th, .print-table td { border: 1px solid #999; padding: 6px 8px; text-align: left; vertical-align: top; }
  .print-table th { background: #eee; }
  .print-note { margin-top: 14px; font-size: 10.5pt; }
}
"""


BOOKMARK = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M6 3h12v18l-6-4.5L6 21z"/></svg>')


def mine_button(p):
    return (f'<button type="button" class="mine-btn" data-kod="{esc(p["kod"])}" data-name="{esc(p["name"])}" '
            f'data-slug="{esc(p["slug"])}" aria-pressed="false">{BOOKMARK}<span class="mine-label">Pridať do Mojich liekov</span></button>')


def alert_form(kod=None, heading="Upozorníme vás na zmenu"):
    data_kod = f' data-kod="{esc(kod)}"' if kod else ""
    return f"""
  <section class="card">
    <h2>{esc(heading)}</h2>
    <p class="page-sub">Pošleme vám e-mail, len keď sa zmení doplatok vašich liekov, keď výrobca ohlási výpadok alebo keď pribudne lacnejšia alternatíva. Bez reklamy, odhlásiť sa dá jedným kliknutím.</p>
    <form class="alert-form"{data_kod} novalidate>
      <div class="fields">
        <label class="hp" aria-hidden="true">Web <input name="web" tabindex="-1" autocomplete="off"></label>
        <input type="email" name="email" id="alert-email" autocomplete="email" placeholder="vas@email.sk" aria-label="E-mailová adresa" required>
        <button type="submit">Chcem upozornenia</button>
      </div>
      <label class="consent"><input type="checkbox" name="consent" id="alert-consent"> <span>Súhlasím so spracovaním e-mailu a zoznamu mojich liekov na zasielanie upozornení podľa <a href="/ochrana-sukromia/">zásad ochrany súkromia</a>.</span></label>
      <label class="consent"><input type="checkbox" name="digest"> <span>Raz mesačne mi pošlite aj krátky prehľad, čo zlacnie, zdražie a má výpadok (nepovinné).</span></label>
      <p class="form-msg" aria-live="polite"></p>
    </form>
    <p class="hint">Už dostávate upozornenia? <a href="/upozornenia/sprava/">Upraviť alebo zrušiť upozornenia</a></p>
  </section>"""


def ai_card(p):
    from urllib.parse import quote
    qs = ["Je k tomuto lieku lacnejšia alternatíva?", "Koľko sa mi započíta do ochranného limitu?", "Kto mi ho môže predpísať?"]
    links = "".join(f'<a href="/asistent/?kod={esc(p["kod"])}&amp;q={quote(q)}">{esc(q)}</a>' for q in qs)
    return f"""
  <section class="card ai-card">
    <h2>{IC["spark"]}Opýtajte sa AI asistenta</h2>
    <nav class="cond-chips" aria-label="Otázky pre asistenta">{links}</nav>
    <p class="hint">Odpovedá umelá inteligencia z údajov tohto webu. Nenahrádza lekára ani lekárnika.</p>
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
{PREFS_HEAD}
{FONTS}
<link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/assets/pages.css">
{ld}
</head>
<body>
{site_header(path)}
<div class="wrap">
<main id="obsah">
{body}
</main>
  {site_footer(esc(PLATNOST))}
</div>
{bottom_nav(path)}
{site_panels(path)}
<script src="/ui.js" defer></script>
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


ASSET_VER = {}  # verzie štýlov a skriptov podľa obsahu, aby prehliadač ani aplikácia nepoužili starú verziu


def compute_versions():
    import hashlib
    for name in ("style.css", "assets/pages.css", "ui.js", "moje.js", "limit.js", "sprava.js", "asistent.js"):
        f = SITE / name
        if f.exists():
            ASSET_VER["/" + name] = hashlib.sha1(f.read_bytes()).hexdigest()[:10]


def versioned(html_text):
    for url, v in ASSET_VER.items():
        attr = "href" if url.endswith(".css") else "src"
        html_text = html_text.replace(f'{attr}="{url}"', f'{attr}="{url}?v={v}"')
    return html_text


def write(path, content):
    content = versioned(content)
    out = SITE / path.strip("/")
    if path.endswith("/"):
        out.mkdir(parents=True, exist_ok=True)
        out = out / "index.html"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


# ---------- graf histórie ----------

def history_chart(points, next_point=None, unit=" €", aria="Vývoj doplatku", zero=True):
    """points: [(iso, hodnota)], next_point: (iso, hodnota) alebo None. Vráti inline SVG."""
    if len(points) < 2:
        return ""
    allp = points + ([next_point] if next_point else [])
    W, H, L, R, T, B = 400, 200, 54, 14, 14, 34  # malé súradnice = čitateľné popisy aj na mobile
    n = len(allp)
    vmax = max(v for _, v in allp)
    raw = max(1.0, vmax * 1.1) / 4  # 4 dieliky s okrúhlymi hodnotami
    mag = 10 ** math.floor(math.log10(raw))
    tick = next(m * mag for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10) if m * mag >= raw)
    top = tick * 4

    def x(i):
        return L + (W - L - R) * (i / (n - 1))

    def y(v):
        return T + (H - T - B) * (1 - v / top)

    parts = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    ticks = 4
    for k in range(ticks + 1):
        v = top * k / ticks
        yy = y(v)
        parts.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        lbl = f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        if v >= 1000:
            lbl = f"{v:,.0f}".replace(",", " ")
        parts.append(f'<text x="{L - 6}" y="{yy + 5:.1f}" text-anchor="end">{lbl}{unit}</text>')
    xs = [x(i) for i in range(len(points))]
    ys = [y(v) for _, v in points]
    line = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys))
    area = f"{xs[0]:.1f},{y(0):.1f} " + line + f" {xs[-1]:.1f},{y(0):.1f}"
    parts.append(f'<polygon class="area" points="{area}"/>')
    parts.append(f'<polyline class="line" points="{line}"/>')
    # popisy osi x: prvý, posledný a každý január
    min_gap = (W - L - R) * 0.2  # popisy januárov nesmú zasahovať do prvého a posledného
    for i, (iso, _) in enumerate(allp):
        yr, mo = int(iso[:4]), int(iso[5:7])
        edge = i == 0 or i == n - 1
        if edge or (mo == 1 and x(i) - x(0) >= min_gap and x(n - 1) - x(i) >= min_gap):
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

    if load("full.json") is not None:  # ľahké dáta pre vyhľadávač, Moje lieky a tracker limitu
        (SITE / "data.json").write_text(json.dumps({"platnost": full.get("platnost"), "platnostIso": full.get("platnostIso"),
                                                    "groups": lean_groups(groups)}, ensure_ascii=False, separators=(",", ":")),
                                        encoding="utf-8")
    for d in GENERATED:
        shutil.rmtree(SITE / d, ignore_errors=True)
    (SITE / "assets").mkdir(parents=True)
    (SITE / "assets" / "pages.css").write_text(extract_css(), encoding="utf-8")
    compute_versions()

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
            about.append(("Štandardných dávok v balení", f'{p["sdl"]:g}<small>Počet dávok podľa zoznamu ministerstva.</small>'))
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
        conds = conditions_for(g["a"])
        if chain or conds:
            purpose = ('<div class="purpose"><span class="eyebrow">Na čo je</span>' +
                       "".join(f'<a href="/skupina/{esc(k.lower())}/">{esc(v)}</a>' for k, v in chain) +
                       "".join(f'<a class="cond" href="/choroby/{c[0]}/">{esc(c[2])}</a>' for c in conds) + "</div>")

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
{year_calc(p, cheapest)}
{hist_html}
{presc_html}
{about_html}
{ai_card(p)}
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
    zm_counts = None
    zm_ups = zm_downs = zm_gone = []
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
        zm_counts = (len(ups), len(downs), len(gone), sk_date(nxt["platnostIso"]))
        zm_ups, zm_downs, zm_gone = ups, downs, gone

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
  <section class="card tracker" id="tracker">
    <h2>Môj prehľad doplatkov</h2>
    <p class="page-sub">Zapisujte si lieky na predpis, ktoré si kúpite. Spočítame, koľko sa vám za štvrťrok započíta do limitu a koľko vám poisťovňa približne vráti. Údaje zostávajú len v tomto prehliadači.</p>
    <div class="tr-quarter"><button type="button" data-q="-1" aria-label="Predchádzajúci štvrťrok">‹</button><b id="tr-qlabel">–</b><button type="button" data-q="1" aria-label="Ďalší štvrťrok">›</button></div>
    <form class="tr-add" id="tr-add" autocomplete="off">
      <label class="tr-search">Liek
        <input type="search" id="tr-q" placeholder="Začnite písať názov lieku" aria-autocomplete="list" aria-controls="tr-results">
      </label>
      <ul class="tr-results" id="tr-results" role="listbox" hidden></ul>
      <div class="tr-row">
        <label>Balení <input type="number" id="tr-n" min="1" max="99" step="1" value="1" inputmode="numeric"></label>
        <label>Dátum <input type="date" id="tr-d"></label>
        <button type="submit" id="tr-submit" disabled>Pridať</button>
      </div>
      <p class="tr-picked" id="tr-picked" aria-live="polite"></p>
    </form>
    <p class="tr-more"><button type="button" class="linkish" id="tr-mine">Pridať lieky z Mojich liekov</button> · <button type="button" class="linkish" id="tr-manual">Zadať sumu ručne</button></p>
    <ul class="glist tr-list" id="tr-list"></ul>
    <div class="tr-sum" id="tr-sum" aria-live="polite"></div>
    <p class="hint">Pri každom lieku počítame so sumou, ktorá sa podľa zoznamu ministerstva započíta do limitu (doplatok za najlacnejší náhradný liek), platnou v deň, keď ste ho pridali. Poisťovňa počíta podľa skutočných výdajov v lekárni.</p>
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
                                   "Koľko vám poisťovňa vráti za doplatky za lieky: limity pre dôchodcov, ŤZP a deti na rok 2026, čo sa započítava, kalkulačka a prehľad vašich doplatkov.",
                                   "/ochranny-limit/", body, breadcrumb_ld(crumb_items), script + '<script src="/limit.js" defer></script>'))

    # --- lieky podľa ochorenia ---
    def subst_line(s, gs):
        allit = [x for g in gs for x in g["i"] if x["dop"] is not None]
        if not allit:
            return ""
        lo = min(allit, key=lambda x: x["dop"])
        gaps = [sorted_items(g) for g in gs]
        gap = max([it[-1]["dop"] - it[0]["dop"] for it in gaps if len(it) > 1] + [0])
        extra = f' · rozdiel až {eur(gap)}' if gap >= 0.5 else ""
        return (f'<li><div class="gline"><a href="/latka/{esc(subst_slug[s])}/">{esc(s)}</a>'
                f'<span class="mono">od {eur(lo["dop"])}</span>'
                f'<small>{plural_lieky(len(allit))}{extra}</small></div></li>')

    def top_savings(gs, limit=10):
        rows = []
        for g in gs:
            it = sorted_items(g)
            if len(it) > 1 and it[-1]["dop"] - it[0]["dop"] >= 1:
                rows.append((it[-1]["dop"] - it[0]["dop"], g, it[0], it[-1]))
        rows.sort(key=lambda r: -r[0])
        return "".join(
            f'<li><div class="gline"><a href="/liek/{esc(lo["slug"])}/">{esc(g["s"])}</a>'
            f'<span class="mono save">−{eur(gap)}</span>'
            f'<small>{esc(g["f"])}</small>'
            f'<small><a href="/liek/{esc(hi["slug"])}/">{esc(hi["name"])}</a> {eur(hi["dop"])} → '
            f'<a href="/liek/{esc(lo["slug"])}/">{esc(lo["name"])}</a> {eur(lo["dop"])}</small></div></li>'
            for gap, g, lo, hi in rows[:limit])

    cond_cards = []
    for slug, short, title, prefixes, intro in CONDITIONS:
        gs_all = [g for g in groups if any(g["a"].startswith(x) for x in prefixes)]
        if not gs_all:
            continue
        path = f"/choroby/{slug}/"
        items_all = [x for g in gs_all for x in g["i"] if x["dop"] is not None]
        zero_n = sum(1 for x in items_all if x["dop"] == 0)
        substs_all = {g["s"] for g in gs_all}
        sections = []
        for pre in prefixes:
            gs = [g for g in gs_all if g["a"].startswith(pre)]
            if not gs:
                continue
            by_s = defaultdict(list)
            for g in gs:
                by_s[g["s"]].append(g)
            order = sorted(by_s, key=lambda s: (-sum(len(g["i"]) for g in by_s[s]), norm(s)))
            label = COND_LABELS.get(pre) or atc_names.get(pre) or pre
            sections.append(f'<section class="card"><h2>{esc(label)} <small class="mono">{esc(pre)}</small></h2>'
                            f'<ul class="glist">{"".join(subst_line(s, by_s[s]) for s in order)}</ul></section>')
        top = top_savings(gs_all)
        top_html = (f'<section class="card"><h2>Kde ušetríte najviac</h2><p class="hint">Skupiny s rovnakou látkou, '
                    f'silou a balením, v ktorých je rozdiel medzi najdrahšou a najlacnejšou verziou najväčší.</p>'
                    f'<ul class="glist">{top}</ul></section>') if top else ""
        crumb_items = [("Domov", "/"), ("Lieky podľa ochorenia", "/choroby/"), (title, None)]
        desc = (f"{title}: {plural_lieky(len(items_all))} hradených poisťovňou, {len(substs_all)} účinných látok, "
                f"{zero_n} bez doplatku. Porovnajte doplatky a nájdite lacnejšiu alternatívu.")
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Lieky podľa ochorenia</p>
    <h1 class="page-h1">{esc(title)}: doplatky a lacnejšie alternatívy</h1>
    <p class="page-sub">{esc(intro)} Liek vždy vyberá lekár. Tu zistíte, koľko doplácate a či existuje lacnejšia verzia s rovnakou látkou.</p>
  </section>
  <div class="stats3 big">
    <div><span>Účinných látok</span><b>{len(substs_all)}</b></div>
    <div><span>Balení v zozname</span><b>{len(items_all)}</b></div>
    <div><span>Bez doplatku</span><b>{zero_n}</b></div>
  </div>
  {top_html}
  {''.join(sections)}
  <p class="hint">Zaradenie liekov vychádza z ATC klasifikácie a je orientačné. Niektoré lieky sa používajú aj pri iných ochoreniach.</p>
  <p><a class="cta" href="/bez-doplatku/">Lieky bez doplatku →</a></p>
{NOTES}"""
        write(path, page(f"{title} – doplatky a lacnejšie alternatívy", desc, path, body, breadcrumb_ld(crumb_items)))
        urls.append((path, "0.8"))
        cond_cards.append(f'<li><a href="{path}"><strong>{esc(title)}</strong>'
                          f'<span>{len(substs_all)} látok · {plural_lieky(len(items_all))} · {zero_n} bez doplatku</span></a></li>')
    crumb_items = [("Domov", "/"), ("Lieky podľa ochorenia", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Prehľad</p>
    <h1 class="page-h1">Lieky podľa ochorenia</h1>
    <p class="page-sub">Vyberte oblasť a porovnajte doplatky za lieky hradené poisťovňou. Pri každej látke vidíte najnižší doplatok a rozdiel medzi najdrahšou a najlacnejšou verziou.</p>
  </section>
  <ul class="article-list cond-list">{''.join(cond_cards)}</ul>"""
    write("/choroby/", page("Lieky podľa ochorenia – doplatky", "Lieky na tlak, cholesterol, cukrovku, štítnu žľazu a ďalšie ochorenia: porovnanie doplatkov a lacnejšie alternatívy.", "/choroby/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/choroby/", "0.8"))

    # --- lieky bez doplatku ---
    zero_by_l1 = defaultdict(lambda: defaultdict(list))
    for g, p in products:
        if p["dop"] == 0:
            zero_by_l1[g["a"][:1]][g["s"]].append((g, p))
    blocks = []
    for code in sorted(zero_by_l1):
        substs = zero_by_l1[code]
        n = sum(len(v) for v in substs.values())
        inner = "".join(
            f'<li><h3><a href="/latka/{esc(subst_slug[s])}/">{esc(s)}</a></h3>' + "".join(
                f'<div class="gline"><a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a><span class="mono">0,00 €</span>'
                f'<small>{esc(short_pack(p["pack"]))}</small></div>' for g, p in sorted(substs[s], key=lambda t: norm(t[1]["name"])))
            + "</li>" for s in sorted(substs, key=norm))
        blocks.append(f'<details class="zero-group"><summary><span>{esc(atc_names.get(code, code))}</span>'
                      f'<small>{plural_lieky(n)}</small></summary><ul class="glist">{inner}</ul></details>')
    zero_total = sum(1 for _, p in products if p["dop"] == 0)
    crumb_items = [("Domov", "/"), ("Lieky bez doplatku", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Zoznam platný od {esc(PLATNOST)}</p>
    <h1 class="page-h1">Lieky bez doplatku</h1>
    <p class="page-sub">{plural_lieky(zero_total)} poisťovňa hradí v plnej výške, v lekárni za ne nedoplácate nič. Ak užívate liek s doplatkom, pozrite sa, či v jeho skupine nie je verzia bez doplatku, a opýtajte sa lekára alebo lekárnika.</p>
  </section>
  <input class="filter" type="search" placeholder="Filtrovať podľa názvu alebo látky" aria-label="Filtrovať" data-filter=".zero-group">
  {''.join(blocks)}
  <p class="hint">Na lieky na predpis bez doplatku stále potrebujete recept. Niektoré majú preskripčné alebo indikačné obmedzenie, podrobnosti nájdete na stránke lieku.</p>"""
    script = """<script>
(function () {
  var inp = document.querySelector('input[data-filter]'); if (!inp) return;
  function n(s) { return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase(); }
  inp.addEventListener('input', function () {
    var q = n(inp.value.trim());
    document.querySelectorAll('.zero-group').forEach(function (d) {
      var any = false;
      d.querySelectorAll('li').forEach(function (li) { var ok = !q || n(li.textContent).indexOf(q) >= 0; li.hidden = !ok; any = any || ok; });
      d.hidden = !any; if (q) d.open = any;
    });
  });
})();
</script>"""
    write("/bez-doplatku/", page(f"Lieky bez doplatku ({zero_total}) – plne hradené poisťovňou",
                                 f"Zoznam {plural_lieky(zero_total)} bez doplatku, ktoré zdravotná poisťovňa hradí v plnej výške, rozdelený podľa skupín a účinných látok.",
                                 "/bez-doplatku/", body, breadcrumb_ld(crumb_items), script))
    urls.append(("/bez-doplatku/", "0.8"))

    # --- štatistiky a trendy ---
    months = []  # (iso, priemerný doplatok, počet, bez doplatku)
    for iso, prices in history:
        vals = [v[2] for v in prices.values() if v and v[2] is not None]
        if vals:
            months.append((iso, sum(vals) / len(vals), len(vals), sum(1 for v in vals if v == 0)))
    stats_html = ""
    if len(months) >= 2:
        avg_chart = history_chart([(m[0], round(m[1], 2)) for m in months], aria="Priemerný doplatok za balenie")
        zero_chart = history_chart([(m[0], m[3]) for m in months], unit="", aria="Počet liekov bez doplatku")
        cnt_chart = history_chart([(m[0], m[2]) for m in months], unit="", aria="Počet liekov v zozname")
        f0, l0 = months[0], months[-1]
        stats_html = f"""
  <section class="card">
    <h2>Priemerný doplatok za balenie</h2>
    {avg_chart}
    <div class="stats3">
      <div><span>{MESIACE[int(f0[0][5:7]) - 1]} {f0[0][:4]}</span><b>{eur(f0[1])}</b></div>
      <div><span>{MESIACE[int(l0[0][5:7]) - 1]} {l0[0][:4]}</span><b>{eur(l0[1])}</b></div>
      <div><span>Zmena</span><b>{'+' if l0[1] >= f0[1] else '−'}{eur(abs(l0[1] - f0[1]))}</b></div>
    </div>
    <p class="hint">Jednoduchý priemer maximálnych doplatkov všetkých balení v zozname ministerstva, bez ohľadu na to, koľko sa ich predá.</p>
  </section>
  <section class="card">
    <h2>Lieky bez doplatku</h2>
    {zero_chart}
    <p class="hint">Počet balení, ktoré poisťovňa hradí v plnej výške. Teraz {l0[3]} z {l0[2]} ({l0[3] / l0[2] * 100:.0f} %).</p>
  </section>
  <section class="card">
    <h2>Počet liekov v zozname</h2>
    {cnt_chart}
  </section>"""
    # najväčšie zmeny za 12 mesiacov
    movers_html = ""
    if history:
        cur_m = cur_iso[:7] if cur_iso else history[-1][0][:7]
        cy, cm = int(cur_m[:4]), int(cur_m[5:7])
        target = f"{cy - 1}-{cm:02d}-01"
        base = next((h for h in history if h[0] == target), None) or history[0]
        ups_y, downs_y = [], []
        for g, p in products:
            old = base[1].get(p["kod"])
            if not old or old[2] is None or p["dop"] is None:
                continue
            if p["konc"] is None or p["konc"] > 150 or max(old[2], p["dop"]) > 60 or p.get("su") in ("A", "AS"):
                continue  # drahé a nemocničné lieky by zoznam skreslili
            d = round(p["dop"] - old[2], 2)
            if abs(d) >= 0.5:
                (ups_y if d > 0 else downs_y).append((d, g, p, old[2]))
        ups_y.sort(key=lambda t: -t[0])
        downs_y.sort(key=lambda t: t[0])

        def mv(lst, cls):
            return "".join(
                f'<li><div class="gline"><a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a>'
                f'<span class="mono {cls}">{"+" if d > 0 else "−"}{eur(abs(d))}</span>'
                f'<small>{esc(short_pack(p["pack"]))} · {eur(o)} → {eur(p["dop"])}</small></div></li>' for d, g, p, o in lst[:15])
        since = f"{MESIACE[int(base[0][5:7]) - 1]} {base[0][:4]}"
        movers_html = f"""
  <section class="card"><h2>Najväčšie zdraženia od {since}</h2><p class="hint">Zvýšenie doplatku o 0,50 € a viac: {plural_lieky(len(ups_y))}. Bežné lieky s konečnou cenou do 150 €.</p><ul class="glist">{mv(ups_y, "up") or "<li>Žiadne.</li>"}</ul></section>
  <section class="card"><h2>Najväčšie zlacnenia od {since}</h2><p class="hint">Zníženie doplatku o 0,50 € a viac: {plural_lieky(len(downs_y))}. Bežné lieky s konečnou cenou do 150 €.</p><ul class="glist">{mv(downs_y, "down") or "<li>Žiadne.</li>"}</ul></section>"""
    # podľa skupín
    l1_rows = []
    for code in lvl1:
        its = [p for g, p in products if g["a"].startswith(code) and p["dop"] is not None]
        if not its:
            continue
        l1_rows.append((atc_names[code], code, len(its), sum(p["dop"] for p in its) / len(its),
                        sum(1 for p in its if p["dop"] == 0) / len(its) * 100))
    l1_rows.sort(key=lambda r: -r[2])
    tbl = "".join(f'<tr><td><a href="/skupina/{c.lower()}/">{esc(n)}</a></td><td class="num">{k}</td>'
                  f'<td class="num">{eur(a)}</td><td class="num">{z:.0f} %</td></tr>' for n, c, k, a, z in l1_rows)
    n_vyp = sum(1 for _, p in products if vyp.get(p["kod"], {}).get("stav") in ("R", "Z"))
    gap_list = []
    for g in groups:
        it = sorted_items(g)
        if len(it) > 1:
            gap_list.append(it[-1]["dop"] - it[0]["dop"])
    crumb_items = [("Domov", "/"), ("Štatistiky", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Údaje k {esc(PLATNOST)}</p>
    <h1 class="page-h1">Doplatky za lieky v číslach</h1>
    <p class="page-sub">Ako sa vyvíjajú doplatky za lieky hradené poisťovňou podľa mesačných zoznamov ministerstva zdravotníctva. Údaje môžete citovať so zdrojom doplatkyliekov.sk.</p>
  </section>
  <div class="stats3 big">
    <div><span>Balení v zozname</span><b>{len(products)}</b></div>
    <div><span>Bez doplatku</span><b>{zero_total}</b></div>
    <div><span>Prerušené dodávky</span><b>{n_vyp}</b></div>
  </div>
  <div class="stats3 big">
    <div><span>Skupín s výberom</span><b>{len(gap_list)}</b></div>
    <div><span>Rozdiel ≥ 5 €</span><b>{sum(1 for x in gap_list if x >= 5)}</b></div>
    <div><span>Rozdiel ≥ 10 €</span><b>{sum(1 for x in gap_list if x >= 10)}</b></div>
  </div>
  {stats_html}
  {movers_html}
  <section class="card">
    <h2>Podľa skupín liečiv</h2>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Skupina</th><th>Balení</th><th>Priemerný doplatok</th><th>Bez doplatku</th></tr></thead>
      <tbody>{tbl}</tbody>
    </table></div>
  </section>
  <p class="hint">Skupina s výberom = lieky s rovnakou účinnou látkou, silou a veľkosťou balenia, z ktorých si pacient môže vybrať. Rozdiel = medzi najvyšším a najnižším doplatkom v skupine. Pre médiá: <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>"""
    write("/statistiky/", page("Doplatky za lieky v číslach – štatistiky a trendy",
                               f"Vývoj doplatkov za lieky na Slovensku: priemerný doplatok, lieky bez doplatku, najväčšie zdraženia a zlacnenia. Údaje k {PLATNOST}.",
                               "/statistiky/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/statistiky/", "0.7"))

    # --- adresy liekov pre zdieľaný zoznam (Moje lieky) ---
    (SITE / "slugs.json").write_text(json.dumps({p["kod"]: p["slug"] for _, p in products}, separators=(",", ":")),
                                     encoding="utf-8")

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
  <div class="print-only print-head"><b>Zoznam užívaných liekov</b><span id="print-date"></span><span>doplatkyliekov.sk · údaje zo zoznamu MZ SR platného od {esc(PLATNOST)}</span></div>
  <section id="moje-root" aria-live="polite"><p class="page-sub">Načítavam…</p></section>
  <div class="mine-tools" id="mine-tools" hidden>
    <button type="button" id="mine-print">Vytlačiť pre lekára</button>
    <button type="button" id="mine-share">Zdieľať zoznam</button>
    <button type="button" id="mine-ics" hidden>Pripomienky do kalendára</button>
    <a href="/ochranny-limit/#tracker">Prehľad doplatkov pre ochranný limit</a>
    <p class="form-msg" id="mine-tools-msg" aria-live="polite"></p>
  </div>
{alert_form(None, "Upozornenia e-mailom")}
  <section class="card" id="push-card" hidden>
    <h2>Upozornenia v telefóne</h2>
    <p class="page-sub">Notifikácia príde, keď sa zmení doplatok vašich liekov, výrobca ohlási výpadok, pribudne lacnejšia alternatíva alebo keď vám o pár dní dôjde balenie. Funguje bez e-mailu, len na tomto zariadení.</p>
    <label class="consent"><input type="checkbox" id="push-consent"> <span>Súhlasím, aby sa zoznam mojich liekov a dátumy, kedy mi dôjdu, uložili na zasielanie notifikácií podľa <a href="/ochrana-sukromia/#notifikacie">zásad ochrany súkromia</a>.</span></label>
    <div class="mine-tools"><button type="button" id="push-on">Zapnúť notifikácie</button><button type="button" id="push-off" hidden>Vypnúť notifikácie</button></div>
    <p class="form-msg" aria-live="polite"></p>
  </section>
  <section class="card install-card" id="install-card" hidden>
    <h2>Doplatky ako aplikácia v mobile</h2>
    <p class="page-sub" id="install-text">Pridajte si web na plochu telefónu. Otvorí sa ako aplikácia a Moje lieky budete mať vždy po ruke, aj bez internetu.</p>
    <button type="button" id="install-btn" hidden>Nainštalovať aplikáciu</button>
  </section>"""
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
    <h2>Nie je to reklama na lieky</h2>
    <p>Web preberá úradné údaje o cenách a úhradách v nezmenenej podobe a zobrazuje všetky hradené lieky rovnako. Neobsahuje propagačné tvrdenia o účinku liekov a výrobcovia ani lekárne zaň neplatia. Reklama na lieky viazané na lekársky predpis a na lieky hradené z verejného zdravotného poistenia je voči verejnosti zakázaná (zákon č. 147/2001 Z. z. o reklame), preto takúto reklamu na webe nikdy nezverejníme.</p>
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
    <p>Web nepoužíva cookies ani iné nástroje na sledovanie alebo reklamu. Návštevnosť meriame službou Cloudflare Web Analytics, ktorá nepoužíva cookies, neukladá nič do vášho zariadenia, nevytvára profily návštevníkov a poskytuje nám len súhrnné údaje (napríklad počet zobrazení stránok). Hosting zabezpečuje Cloudflare, Inc., ktorý pri doručovaní stránok technicky spracúva IP adresy na zabezpečenie a ochranu pred útokmi.</p>
    <h2>Údaje uložené vo vašom zariadení</h2>
    <p>Niektoré funkcie, o ktoré sami požiadate, si ukladajú údaje do úložiska vášho prehliadača (localStorage). Ide o ukladanie nevyhnutné na poskytnutie funkcie, ktorú výslovne požadujete, preto podľa § 109 ods. 8 zákona č. 452/2021 Z. z. o elektronických komunikáciách nevyžaduje súhlas. Tieto údaje zostávajú vo vašom zariadení, neodosielame ich a nemáme k nim prístup.</p>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Názov</th><th>Na čo slúži</th><th>Kedy vznikne</th></tr></thead>
      <tbody>
        <tr><td class="mono">mojeLieky.v1</td><td>zoznam vašich liekov a dávkovanie</td><td>keď uložíte liek do Mojich liekov</td></tr>
        <tr><td class="mono">limitTracker.v1, limitSettings.v1</td><td>váš prehľad doplatkov a nastavenie kalkulačky ochranného limitu</td><td>keď zapíšete nákup</td></tr>
        <tr><td class="mono">zobrazenie.v1</td><td>farebný režim, veľkosť písma a režim pre slabozrakých</td><td>keď zmeníte zobrazenie</td></tr>
        <tr><td class="mono">push.v1</td><td>identifikátor zariadenia pre notifikácie</td><td>keď zapnete notifikácie</td></tr>
        <tr><td class="mono">upozornenia.t</td><td>tajný odkaz na správu vašich e-mailových upozornení</td><td>keď potvrdíte prihlásenie alebo otvoríte odkaz na správu</td></tr>
        <tr><td>vyrovnávacia pamäť aplikácie</td><td>uložené stránky a údaje o liekoch, aby web fungoval aj bez internetu</td><td>pri návšteve webu</td></tr>
      </tbody>
    </table></div>
    <p>Všetko vymažete vymazaním údajov stránky v nastaveniach prehliadača. Jednotlivé položky odstránite aj priamo na webe (odobratím liekov, nákupov alebo tlačidlom Obnoviť pôvodné zobrazenie).</p>
    <h2 id="notifikacie">Upozornenia v telefóne (notifikácie)</h2>
    <p>Ak si zapnete notifikácie, uložíme technickú adresu vášho zariadenia pre doručovanie notifikácií (poskytuje ju prehliadač, napríklad Google, Apple alebo Mozilla), kódy liekov z Mojich liekov a vypočítané dátumy, kedy vám balenie dôjde. Účel: posielať vám upozornenia na zmeny doplatkov, výpadky, lacnejšie alternatívy a blížiaci sa koniec balenia. Právny základ: váš výslovný súhlas (čl. 6 ods. 1 písm. a) a čl. 9 ods. 2 písm. a) GDPR). Údaje uchovávame, kým notifikácie nevypnete, alebo kým prehliadač adresu nezruší; potom ich vymažeme. Údaje sú uložené u Cloudflare, Inc.; notifikácie doručuje služba výrobcu prehliadača.</p>
    <h2 id="asistent">AI asistent</h2>
    <p>Keď položíte otázku AI asistentovi, text otázky, predchádzajúce otázky a odpovede z tej istej konverzácie a prípadne kód lieku, zo stránky ktorého sa pýtate, spracuje jazykový model umelej inteligencie, ktorý vygeneruje odpoveď. Model beží v službe Cloudflare Workers AI (Cloudflare, Inc., USA); ak ho v budúcnosti nahradíme modelom Claude, odpoveď vygeneruje spoločnosť Anthropic PBC (USA). Otázky ani odpovede neukladáme; konverzácia sa uchováva len v tejto karte prehliadača (sessionStorage) a po jej zatvorení zmizne. Poskytovatelia modelov podľa svojich podmienok nepoužívajú tieto údaje na trénovanie modelov. Prenos do USA prebieha na základe primeraných záruk (štandardné zmluvné doložky). <strong>Nezadávajte meno, rodné číslo, adresu ani iné údaje, podľa ktorých by sa dalo zistiť, kto ste.</strong> Právny základ: plnenie vašej žiadosti o odpoveď a náš oprávnený záujem na poskytovaní služby (čl. 6 ods. 1 písm. b) a f) GDPR). Odpovede generuje umelá inteligencia a môžu byť nepresné.</p>
    <p>Ak otázku položíte hlasom, reč prevedie na text priamo váš prehliadač alebo operačný systém (napríklad Google alebo Apple) podľa ich pravidiel; k nám príde len výsledný text otázky. Mikrofón sa zapne až po ťuknutí na tlačidlo a prehliadač si najprv vyžiada vaše povolenie.</p>
    <h2>Moje lieky</h2>
    <p>Zoznam Moje lieky a prehľad doplatkov pre ochranný limit sa ukladajú len vo vašom prehliadači (pozri vyššie). Ak zoznam liekov zdieľate odkazom, kódy liekov sú súčasťou odkazu a vidí ich každý, komu ho pošlete.</p>
    <h2>Upozornenia e-mailom</h2>
    <p>Ak sa prihlásite na upozornenia, spracúvame:</p>
    <ul>
      <li>vašu e-mailovú adresu,</li>
      <li>zoznam liekov, o ktorých vás máme informovať (kódy ŠÚKL),</li>
      <li>dátum prihlásenia a potvrdenia a údaj o tom, aké upozornenia sme vám už poslali,</li>
      <li>či chcete dostávať mesačný prehľad zmien (len ak ste ho zvolili).</li>
    </ul>
    <p><strong>Účel:</strong> zasielanie upozornení na zmeny doplatkov, výpadky dodávok a nové lacnejšie alternatívy vašich liekov. <strong>Právny základ:</strong> váš výslovný súhlas (čl. 6 ods. 1 písm. a) a čl. 9 ods. 2 písm. a) GDPR). Zoznam liekov môže nepriamo vypovedať o vašom zdraví, preto ho spracúvame len s vaším výslovným súhlasom a nepoužívame ho na žiadny iný účel.</p>
    <p><strong>Doba uchovávania:</strong> do odvolania súhlasu. Súhlas odvoláte kedykoľvek odkazom v každom e-maile, na stránke <a href="/upozornenia/sprava/">Správa upozornení</a> alebo e-mailom na {CONTACT}; údaje potom hneď vymažeme. Nepotvrdené prihlásenia mažeme po 7 dňoch.</p>
    <p><strong>Sprostredkovatelia:</strong> Cloudflare, Inc., USA (uloženie údajov) a Sendinblue SAS (Brevo), Francúzsko (odosielanie e-mailov); pre AI asistenta Cloudflare, Inc. (Workers AI), prípadne Anthropic PBC, USA. Prenos údajov do USA sa riadi rámcom ochrany údajov EÚ – USA (EU-U.S. Data Privacy Framework), resp. štandardnými zmluvnými doložkami. Údaje nepredávame ani neposkytujeme tretím stranám na marketing.</p>
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

    # --- AI asistent ---
    crumb_items = [("Domov", "/"), ("AI asistent", None)]
    nd_q = f"Čo sa mení od {zm_counts[3]}?" if zm_counts else "Čo sa mení od budúceho mesiaca?"
    sugg = ["Koľko doplatím za Concor 10 mg?", "Je lacnejšia náhrada za Xarelto 20 mg?", "Ktoré lieky na tlak sú bez doplatku?",
            "Koľko mi vráti poisťovňa, ak som dôchodca?", nd_q, "Ktoré lieky na cukrovku majú výpadok?"]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">{IC["spark"]} AI asistent · beta</p>
    <h1 class="page-h1">Opýtajte sa na lieky a doplatky</h1>
    <p class="page-sub">Asistent hľadá v celom obsahu webu: doplatky a lacnejšie alternatívy, zmeny od budúceho mesiaca, výpadky, lieky podľa ochorenia, ochranný limit aj návody.</p>
  </section>
  <div class="ai-notice" role="note">
    <strong>Odpovedá umelá inteligencia.</strong> Jazykový model odpovedá z údajov tohto webu a môže sa mýliť, preto si údaje overte na stránke lieku. Nenahrádza lekára ani lekárnika. Nezadávajte meno, rodné číslo ani iné osobné údaje. <a href="/ochrana-sukromia/#asistent">Ako spracúvame otázky</a>
  </div>
  <p class="ai-ctx" id="ai-ctx" hidden>Pýtate sa na liek <b>…</b></p>
  <section class="ai-chat" aria-label="Konverzácia s asistentom">
    <div class="ai-log" id="ai-log" aria-live="polite"></div>
    <form class="ai-form" id="ai-form" autocomplete="off">
      <label for="ai-q" class="sr-only">Vaša otázka</label>
      <textarea id="ai-q" rows="1" maxlength="600" placeholder="Napíšte otázku…"></textarea>
      <button type="button" id="ai-mic" class="ai-mic" aria-label="Položiť otázku hlasom" title="Položiť otázku hlasom" hidden><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button>
      <button type="submit" id="ai-send" aria-label="Odoslať otázku"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
    </form>
    <div class="ai-sugg" id="ai-sugg"><p class="eyebrow">Skúste sa opýtať</p>{"".join(f'<button type="button">{esc(x)}</button>' for x in sugg)}</div>
    <button type="button" class="linkish ai-new" id="ai-new" hidden>Začať novú konverzáciu</button>
  </section>"""
    write("/asistent/", page("AI asistent – otázky o liekoch a doplatkoch",
                             "Opýtajte sa AI asistenta na doplatky, lacnejšie alternatívy, zmeny, výpadky liekov a ochranný limit. Odpovedá z údajov MZ SR a ŠÚKL.",
                             "/asistent/", body, breadcrumb_ld(crumb_items), '<script src="/asistent.js" defer></script>'))
    urls.append(("/asistent/", "0.7"))

    # --- správa upozornení (zrušenie, odobratie liekov) ---
    body = f"""{crumbs([("Domov", "/"), ("Upozornenia e-mailom", None)])}
  <section class="intro">
    <p class="eyebrow">Upozornenia e-mailom</p>
    <h1 class="page-h1">Správa upozornení</h1>
    <p class="page-sub">Tu upravíte, na ktoré lieky vám posielame upozornenia, alebo ich úplne zrušíte. Pri zrušení vymažeme váš e-mail aj zoznam liekov.</p>
  </section>
  <section class="card" id="sprava-root" aria-live="polite">
    <p class="page-sub">Načítavam…</p>
  </section>
  <section class="card" id="sprava-link">
    <h2>Nemáte odkaz na správu?</h2>
    <p class="page-sub">Zadajte e-mail, na ktorý chodia upozornenia. Ak je prihlásený, pošleme naň odkaz, cez ktorý upozornenia upravíte alebo zrušíte. Odkaz nájdete aj v každom e-maile s upozornením.</p>
    <form class="alert-form" id="manage-link-form" novalidate>
      <div class="fields">
        <label class="hp" aria-hidden="true">Web <input name="web" tabindex="-1" autocomplete="off"></label>
        <input type="email" name="email" autocomplete="email" placeholder="vas@email.sk" aria-label="E-mailová adresa" required>
        <button type="submit">Poslať odkaz</button>
      </div>
      <p class="form-msg" aria-live="polite"></p>
    </form>
  </section>"""
    html_page = page("Správa upozornení – doplatkyliekov.sk", "Úprava alebo zrušenie e-mailových upozornení na zmeny doplatkov a výpadky liekov.",
                     "/upozornenia/sprava/", body, script='<script src="/sprava.js" defer></script>')
    write("/upozornenia/sprava/", html_page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex">'))

    # --- vyhlásenie o prístupnosti ---
    crumb_items = [("Domov", "/"), ("Prístupnosť", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Vyhlásenie o prístupnosti</p>
    <h1 class="page-h1">Prístupnosť webu</h1>
    <p class="page-sub">Chceme, aby web doplatkyliekov.sk mohol používať každý, aj ľudia so zrakovým, sluchovým, pohybovým alebo kognitívnym znevýhodnením a starší ľudia.</p>
  </section>
  <section class="article">
    <h2>Čo web ponúka</h2>
    <ul>
      <li><strong>Zobrazenie</strong> (tlačidlo Aa v hornej lište): tmavý, svetlý alebo automatický režim podľa zariadenia, zväčšenie písma až na 150 % a režim pre slabozrakých s vysokým kontrastom, väčším písmom, podčiarknutými odkazmi a bez animácií.</li>
      <li>Ovládanie klávesnicou vrátane viditeľného zvýraznenia aktívneho prvku a odkazu „Preskočiť na obsah“.</li>
      <li>Štruktúrované nadpisy, popisy formulárov a orientačných prvkov pre čítačky obrazovky.</li>
      <li>Grafy majú textový popis a najdôležitejšie hodnoty sú uvedené aj v texte pod nimi.</li>
      <li>Rozloženie sa prispôsobí mobilu aj zväčšeniu v prehliadači bez vodorovného posúvania.</li>
      <li>Rešpektujeme nastavenie zariadenia „obmedziť pohyb“.</li>
      <li>AI asistent umožňuje klásť otázky vlastnými slovami namiesto prehľadávania tabuliek; odpovede sa čítačke obrazovky oznamujú automaticky.</li>
    </ul>
    <h2>Stav súladu</h2>
    <p>Web sa snaží spĺňať úroveň AA pravidiel WCAG 2.2 a harmonizovanej normy EN 301 549. Je čiastočne v súlade: prístupnosť sme kontrolovali vlastným testovaním, nie nezávislým auditom.</p>
    <p>Známe obmedzenia:</p>
    <ul>
      <li>Grafy vývoja doplatkov sú obrázky s textovým popisom; jednotlivé mesačné hodnoty čítačka obrazovky neprečíta.</li>
      <li>Údaje preberáme zo zoznamu ministerstva v pôvodnom znení, preto názvy balení obsahujú skratky (napríklad „tbl flm“ = filmom obalené tablety).</li>
      <li>Odkazy na externé stránky (ŠÚKL, ministerstvo) nemáme pod kontrolou.</li>
    </ul>
    <h2>Spätná väzba</h2>
    <p>Ak narazíte na prekážku, napíšte nám na <a href="mailto:{CONTACT}">{CONTACT}</a>. Pokúsime sa ju odstrániť alebo vám požadovanú informáciu poskytneme inak.</p>
    <p>Vyhlásenie bolo vypracované {sk_date(dt.date.today().isoformat())}.</p>
  </section>"""
    write("/pristupnost/", page("Vyhlásenie o prístupnosti – doplatkyliekov.sk",
                                "Ako je web doplatkyliekov.sk prístupný: svetlý a tmavý režim, zväčšenie písma, režim pre slabozrakých, ovládanie klávesnicou.",
                                "/pristupnost/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/pristupnost/", "0.3"))

    # --- úvodná stránka zo šablóny ---
    tpl = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    tiles = [
        ("/moje-lieky/", "mine", "Moje lieky", "Uložte si lieky a sledujte doplatky, zmeny a výpadky", ""),
        ("/choroby/", "heart", "Lieky podľa ochorenia", "Tlak, cholesterol, cukrovka, štítna žľaza a ďalšie", ""),
    ]
    if zm_counts:
        n_up, n_down, n_gone, nd_txt = zm_counts
        tiles.append(("/zmeny/", "trend", f"Zmeny od {nd_txt}", f"{n_down} zlacnení, {n_up} zdražení, {n_gone} vypadne", ""))
    else:
        tiles.append(("/zmeny/", "trend", "Zmeny doplatkov", "Nový zoznam ministerstva na budúci mesiac", ""))
    tiles += [
        ("/vypadky/", "alert", "Výpadky liekov", f"{plural_lieky(n_vyp)} s prerušenými dodávkami", " warn"),
        ("/bez-doplatku/", "zero", "Lieky bez doplatku", f"{plural_lieky(zero_total)} plne hradených poisťovňou", ""),
        ("/ochranny-limit/", "shield", "Ochranný limit", "Koľko vám vráti poisťovňa a prehľad doplatkov", ""),
    ]
    tiles_html = "".join(f'<a class="tile{cls}" href="{h}">{IC[ic]}<strong>{esc(t)}</strong><span>{esc(sub)}</span></a>'
                         for h, ic, t, sub, cls in tiles)
    conds_html = "".join(f'<a href="/choroby/{c[0]}/">{esc(c[1][:1].upper() + c[1][1:])}</a>' for c in CONDITIONS[:8])
    for k, v in {"PREFS_HEAD": PREFS_HEAD, "HEADER": site_header("/"), "TILES": tiles_html, "CONDS": conds_html,
                 "FOOTER": site_footer(esc(PLATNOST)), "BOTTOM": bottom_nav("/"), "PANELS": site_panels("/")}.items():
        tpl = tpl.replace(f"<!--{k}-->", v)
    (SITE / "index.html").write_text(versioned(tpl), encoding="utf-8")

    # --- výsledky prihlásenia na upozornenia ---
    for sl, title, text in [
        ("potvrdene", "Prihlásenie je potvrdené", "Ďakujeme. Keď sa zmení doplatok niektorého z vašich liekov, výrobca ohlási výpadok alebo pribudne lacnejšia alternatíva, pošleme vám e-mail. Upozornenia môžete kedykoľvek upraviť alebo zrušiť na stránke Správa upozornení alebo odkazom v každom e-maile."),
        ("odhlasene", "Boli ste odhlásený", "Upozornenia vám už posielať nebudeme a vaše údaje sme vymazali. Zoznam Moje lieky vo vašom prehliadači zostáva."),
        ("chyba", "Odkaz je neplatný alebo vypršal", "Odkaz na potvrdenie platí 7 dní. Prihláste sa prosím znova na stránke Moje lieky."),
    ]:
        body = f"""  <section class="intro">
    <p class="eyebrow">Upozornenia e-mailom</p>
    <h1 class="page-h1">{esc(title)}</h1>
    <p class="page-sub">{esc(text)}</p>
    <p><a class="cta" href="/moje-lieky/">Moje lieky →</a> {'<a class="cta" href="/upozornenia/sprava/">Správa upozornení →</a>' if sl == "potvrdene" else ""}</p>
  </section>"""
        html_page = page(title, text, f"/upozornenia/{sl}/", body, script='<script src="/sprava.js" defer></script>' if sl == "potvrdene" else "").replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex">')
        write(f"/upozornenia/{sl}/", html_page)

    # --- 404 ---
    body404 = """  <section class="intro">
    <h1 class="page-h1">Stránka sa nenašla</h1>
    <p class="page-sub">Liek mohol z úradného zoznamu vypadnúť alebo sa zmenil jeho názov. Skúste ho vyhľadať znova.</p>
    <p><a class="cta" href="/">Vyhľadať liek →</a></p>
  </section>"""
    (SITE / "404.html").write_text(versioned(page("Stránka sa nenašla", "Stránka sa nenašla.", "/404", body404)), encoding="utf-8")

    # --- údaje pre AI asistenta (/ai/…) ---
    def strip_html(t):
        t = re.sub(r"<(br|/p|/li|/h2|/h3|/tr)[^>]*>", "\n", t)
        t = re.sub(r"<[^>]+>", "", t)
        t = html.unescape(t)
        return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()

    ai_dir = SITE / "ai"
    shutil.rmtree(ai_dir, ignore_errors=True)
    (ai_dir / "g").mkdir(parents=True)
    gi_of = {}
    for gi, g in enumerate(groups):
        gi_of[id(g)] = gi
    search_items = [[p["kod"], p["name"], gi_of[id(g)]] for g, p in products]
    group_meta = [[g["s"], g["f"], g["a"]] for g in groups]
    (ai_dir / "search.json").write_text(json.dumps({"platnost": PLATNOST, "next": nxt["platnostIso"] if nxt else None,
                                                    "items": search_items, "groups": group_meta},
                                                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    shards = defaultdict(dict)
    for gi, g in enumerate(groups):
        rows = []
        for x in sorted(g["i"], key=lambda x: (x["dop"] is None, x["dop"] or 0)):
            flags = []
            if x.get("po"):
                flags.append("predpisuje len: " + ", ".join(odb.get(c, c) for c in x["po"]))
            if x.get("io"):
                flags.append("indikačné obmedzenie" + (" so súhlasom poisťovne" if "ZP" in x["io"] else ""))
            if x.get("gp"):
                flags.append("predpis názvom látky")
            if x.get("olpl"):
                flags.append("recept s modrým pruhom")
            c = next_change(x)
            nx = None if not c else ("vypadne" if c["gone"] else c["dop"])
            st = vyp.get(x["kod"])
            rows.append([x["kod"], x["name"], x["pack"], x["dop"], x["konc"], x["uzp"], x.get("pdop"), type_label(x.get("typ")),
                         x["slug"], "; ".join(flags), nx, [st["stav"], st["od"]] if st else None])
        shards[gi // 100][str(gi)] = {"s": g["s"], "f": g["f"], "a": g["a"], "atc": (atc_chain(g["a"])[-1][1] if atc_chain(g["a"]) else ""),
                                      "latka": f"/latka/{subst_slug[g['s']]}/",
                                      "cond": [c[2] for c in conditions_for(g["a"])], "i": rows}
    for n, d in shards.items():
        (ai_dir / "g" / f"{n}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    conds_ai = {}
    for slug, short, title, prefixes, intro in CONDITIONS:
        gs_all = [g for g in groups if any(g["a"].startswith(x) for x in prefixes)]
        by_s = defaultdict(list)
        for g in gs_all:
            by_s[g["s"]].append(g)
        subs = []
        for s_, gs in by_s.items():
            its = [x for g in gs for x in g["i"] if x["dop"] is not None]
            if its:
                gaps = [sorted_items(g) for g in gs]
                gap = max([it[-1]["dop"] - it[0]["dop"] for it in gaps if len(it) > 1] + [0])
                subs.append([s_, min(x["dop"] for x in its), len(its), round(gap, 2), f"/latka/{subst_slug[s_]}/"])
        subs.sort(key=lambda r: -r[2])
        conds_ai[slug] = {"nazov": title, "kluc": short, "url": f"/choroby/{slug}/", "popis": intro, "latky": subs[:40]}
    (ai_dir / "conds.json").write_text(json.dumps(conds_ai, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    docs = []
    for sl, t, d, html_body in articles:
        for part in re.split(r"(?=<h2>)", html_body):
            txt = strip_html(part)
            if txt:
                docs.append({"t": t, "u": f"/clanky/{sl}/", "x": txt[:1800]})
    docs += [
        {"t": "Ochranný limit 2026", "u": "/ochranny-limit/", "k": "ochranný limit spoluúčasť dôchodca dôchodok vráti vrátenie preplatok ŤZP invalidný dieťa štvrťrok príjem", "x": (
            "Ochranný limit (limit spoluúčasti) na štvrťrok v roku 2026: dieťa do 6 rokov 0 € bez ohľadu na príjem; "
            "držiteľ preukazu ŤZP alebo invalidný dôchodca a starobný alebo predčasný starobný dôchodca 0 € ak má dôchodok do 914,40 € mesačne "
            "a celkový príjem do 2 743,20 € za štvrťrok; pri vyššom príjme ŤZP a invalidní dôchodcovia 12 €, starobní dôchodcovia 30 €. "
            "Do limitu sa počíta len doplatok za najlacnejší náhradný liek (započítateľný doplatok), nie celý zaplatený doplatok. "
            "Poisťovňa sčíta doplatky sama z údajov lekární, netreba posielať bločky. Sumu nad limit vráti do 90 dní po skončení štvrťroka, "
            "preplatok pod 3 € sa prenáša do ďalšieho štvrťroka. Ľudia s nulovým limitom a deti do 6 rokov doplatok za najlacnejší náhradný liek "
            "v lekárni vôbec neplatia. Započítavajú sa lieky, pomôcky a dietetické potraviny na predpis čiastočne hradené poisťovňou, voľnopredajné nie. "
            "Na stránke Ochranný limit je kalkulačka a prehľad, kam si môžete zapisovať nákupy. "
            "Príklad 1: starobný dôchodca s dôchodkom 700 € mesačne a bez iných príjmov má štvrťročný príjem 2 100 € (700 × 3), "
            "čo je pod 2 743,20 €, a dôchodok je pod 914,40 €, preto má limit 0 €: poisťovňa mu vráti všetky započítateľné doplatky za štvrťrok "
            "a doplatok za najlacnejší náhradný liek by nemal platiť už v lekárni. "
            "Príklad 2: starobný dôchodca s dôchodkom 1 100 € mesačne má limit 30 €; ak mu za štvrťrok vznikli započítateľné doplatky 50 €, "
            "poisťovňa mu vráti 20 €.")},
        {"t": "Ako vymeniť liek za lacnejší", "u": "/clanky/ako-usetrit-na-liekoch/", "k": "vymeniť zameniť lacnejší lekárnik recept generikum", "x": (
            "Lekárnik môže vydať liek s rovnakou účinnou látkou, silou a veľkosťou balenia od iného výrobcu, ak lekár na recepte nevyznačil, "
            "že liek sa nesmie zamieňať. Ak lekár predpisuje názvom účinnej látky, môžete si vybrať ktorýkoľvek liek s touto látkou. "
            "O zmene sa poraďte s lekárom alebo lekárnikom, najmä pri liekoch na epilepsiu, štítnu žľazu alebo riedenie krvi.")},
        {"t": "Čo je doplatok", "u": "/", "x": (
            "Doplatok je maximálna suma, ktorú pacient zaplatí v lekárni za liek na predpis. Zvyšok konečnej ceny hradí zdravotná poisťovňa (úhrada). "
            "Lekáreň môže dať zľavu. Lieky s rovnakou látkou, silou a balením poisťovňa hradí rovnako, líšia sa doplatkom. "
            "Údaje sú zo Zoznamu kategorizovaných liekov Ministerstva zdravotníctva SR, ktorý sa mení každý mesiac. Voľnopredajné lieky v ňom nie sú.")},
        {"t": "Moje lieky", "u": "/moje-lieky/", "x": (
            "Na stránke lieku kliknite na Pridať do Mojich liekov. Zoznam sa uloží len v prehliadači. Ukáže doplatky, lacnejšie alternatívy, "
            "ročný doplatok podľa dávkovania, zmeny od budúceho mesiaca a výpadky. Dá sa vytlačiť pre lekára alebo zdieľať odkazom.")},
        {"t": "Upozornenia e-mailom", "u": "/upozornenia/sprava/", "k": "upozornenie email odhlásiť zrušiť prihlásiť", "x": (
            "Na stránke lieku alebo v Mojich liekoch zadajte e-mail a súhlas. Po potvrdení e-mailom vám pošleme upozornenie, keď sa zmení doplatok, "
            "výrobca ohlási výpadok alebo pribudne lacnejšia alternatíva. Upozornenia upravíte alebo zrušíte na stránke Správa upozornení "
            "alebo odkazom v každom e-maile.")},
        {"t": "Aplikácia a zobrazenie", "u": "/pristupnost/", "x": (
            "Web sa dá pridať na plochu telefónu ako aplikácia (Safari: Zdieľať, Pridať na plochu). Tlačidlo Aa v hornej lište mení farebný režim "
            "(tmavý, svetlý, podľa zariadenia), veľkosť písma a zapína režim pre slabozrakých s vysokým kontrastom.")},
        {"t": "O webe a zdroje údajov", "u": "/o-nas/", "x": (
            f"Web doplatkyliekov.sk prevádzkuje {OPERATOR}. Nie je prepojený s výrobcami, lekárňami ani poisťovňami a nie je reklamou na lieky. "
            f"Zdroje: Zoznam kategorizovaných liekov MZ SR (platný od {PLATNOST}) a hlásenia ŠÚKL o prerušení dodávok. Kontakt: {CONTACT}.")},
    ]
    if zm_counts:
        n_up, n_down, n_gone, nd_txt = zm_counts
        mon = MESIACE_GEN[int(nxt["platnostIso"][5:7]) - 1]
        docs.append({"t": f"Zmeny doplatkov od {nd_txt}", "u": "/zmeny/",
                     "k": f"zmeny mení zmena budúci mesiac {mon} nový zoznam zdražie zlacnie stúpne klesne vypadne", "x": (
            f"Podľa nového zoznamu ministerstva od 1. {mon} {nxt['platnostIso'][:4]}: doplatok stúpne pri {n_up} liekoch, klesne pri {n_down}, "
            f"zo zoznamu hradených liekov vypadne {n_gone}. "
            + ("Najväčšie zvýšenia: " + "; ".join(f"{p['name']} z {eur(p['dop'])} na {eur(c['dop'])} (/liek/{p['slug']}/)" for d, g, p, c in zm_ups[:6]) + ". " if zm_ups else "")
            + ("Najväčšie zníženia: " + "; ".join(f"{p['name']} z {eur(p['dop'])} na {eur(c['dop'])} (/liek/{p['slug']}/)" for d, g, p, c in zm_downs[:6]) + ". " if zm_downs else "")
            + ("Vypadnú zo zoznamu: " + "; ".join(f"{p['name']} (/liek/{p['slug']}/)" for g, p in zm_gone[:6]) + ". " if zm_gone else "")
            + "Zoznam všetkých zmien je na stránke Zmeny doplatkov (/zmeny/).")})
    docs.append({"t": "Výpadky liekov", "u": "/vypadky/", "k": "výpadok výpadky nedostupný chýba prerušené dodávky", "x": (
        f"Podľa hlásení ŠÚKL má prerušené alebo ukončené dodávky {plural_lieky(n_vyp)} hradených poisťovňou. "
        "Pri každom je uvedená dostupná alternatíva s rovnakou látkou. Dostupnosť v konkrétnej lekárni sa líši.")})
    docs.append({"t": "Doplatky v číslach", "u": "/statistiky/", "x": (
        f"V zozname je {plural_lieky(len(products))}, bez doplatku {zero_total}. "
        + (f"Jednoduchý priemer doplatku za balenie bol {eur(months[0][1])} v {MESIACE[int(months[0][0][5:7]) - 1]} {months[0][0][:4]} "
           f"a {eur(months[-1][1])} v {MESIACE[int(months[-1][0][5:7]) - 1]} {months[-1][0][:4]}." if len(months) >= 2 else ""))})
    (ai_dir / "docs.json").write_text(json.dumps(docs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

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
