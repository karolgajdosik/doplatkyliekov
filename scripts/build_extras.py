"""Doplnkové stránky (volá build_pages.build):
  /data/         dáta pre novinárov: CSV na stiahnutie, RSS so zmenami doplatkov
  /pre-lekarov/  ťahák pre ambulancie na A4: bežné látky a lieky bez doplatku
  /vlozit/       kalkulačka doplatkov na vloženie do iných webov (+ /vlozit/okno/, /vlozit/embed.js)
"""
import csv
import datetime as dt
import io
import json
import re
from collections import defaultdict
from email.utils import format_datetime

STAV = {"R": "Prerušené dodávky", "Z": "Ukončené dodávky", "PR": "Ohlásené prerušenie", "PZ": "Ohlásené ukončenie"}
MESIACE = ["január", "február", "marec", "apríl", "máj", "jún", "júl", "august", "september", "október", "november", "december"]

# ťahák: ochorenie → látky (ATC), poradie v tabuľke; vyberané podľa toho, aké bežné sú v praxi všeobecného lekára
CHEAT = [
    ("Vysoký krvný tlak", ["C07AB07", "C07AB12", "C09AA05", "C09AA04", "C08CA01", "C08CA13", "C09CA07", "C09CA03", "C03BA11", "C02AC06", "C09BB04", "C09BX01"]),
    ("Cholesterol", ["C10AA05", "C10AA07", "C10AX09", "C10BA05", "C10BA06"]),
    ("Cukrovka", ["A10BA02", "A10BB09", "A10BH01", "A10BK01", "A10BK03", "A10BD07"]),
    ("Riedenie krvi", ["B01AF01", "B01AF02", "B01AE07", "B01AC04", "B01AC06"]),
    ("Žalúdok", ["A02BC02", "A02BC05", "A02BC01"]),
    ("Štítna žľaza", ["H03AA01"]),
    ("Prostata a močový mechúr", ["G04CA02", "G04BD08"]),
    ("Depresia a úzkosť", ["N06AB10", "N06AB06", "N06AX16", "N06AX11"]),
    ("Bolesť a zápal", ["M01AB05", "M01AC06", "N02AX02"]),
    ("Dna", ["M04AA01"]),
]


def brand_of(name):
    """Obchodný názov bez sily a formy: „CONTROLOC 40 mg“ → Controloc, „Rivaroxaban Accord 15 mg filmom…“ → Rivaroxaban Accord."""
    out = []
    for w in name.replace(",", " ").split():
        if any(ch.isdigit() for ch in w) or w.lower() in ("mg", "tbl", "tablety", "filmom", "tvrdé", "mäkké", "gastrorezistentné", "injekčný", "perorálny"):
            break
        out.append(w.capitalize() if w.isupper() and len(w) > 3 else w)
        if len(out) == 3:
            break
    return " ".join(out) or name.split()[0]


def _csv(rows, header):
    """CSV pre Excel v slovenskom prostredí: UTF-8 s BOM, bodkočiarka, desatinná čiarka."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(header)

    def cell(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.2f}".replace(".", ",")
        return v
    for r in rows:
        w.writerow([cell(v) for v in r])
    return "﻿" + buf.getvalue()


def build_extras(c):
    esc, eur, page, write, crumbs, breadcrumb_ld = c["esc"], c["eur"], c["page"], c["write"], c["crumbs"], c["breadcrumb_ld"]
    SITE, BASE, PLATNOST, cur_iso = c["SITE"], c["BASE"], c["PLATNOST"], c["cur_iso"]
    groups, nxt, vyp, history, urls = c["groups"], c["nxt"], c["vyp"], c["history"], c["urls"]
    subst_slug, month_articles, segno = c["subst_slug"], c["month_articles"], c["segno"]
    sk_date = c["sk_date"]
    today = dt.date.today()

    # ---------------- /data/ ----------------
    ddir = SITE / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    files = []
    rows = []
    for g in groups:
        valid = [it["dop"] for it in g["i"] if it["dop"] is not None]
        mn = min(valid) if valid else None
        for it in g["i"]:
            v = vyp.get(it["kod"]) or {}
            rows.append([it["kod"], it["name"], it["pack"], g["s"], g["a"], g["f"], c["type_label"](it.get("typ")),
                         it.get("konc"), it.get("uzp"), it["dop"], mn,
                         None if (it["dop"] is None or mn is None) else round(it["dop"] - mn, 2),
                         STAV.get(v.get("stav"), ""), v.get("od", ""), f"{BASE}/liek/{it['slug']}/"])
    rows.sort(key=lambda r: (r[3], r[5], r[9] if r[9] is not None else 999))
    txt = _csv(rows, ["kod_sukl", "nazov", "balenie", "ucinna_latka", "atc", "skupina", "typ", "cena_eur", "uhrada_poistovne_eur",
                      "doplatok_eur", "najnizsi_doplatok_v_skupine_eur", "rozdiel_oproti_najnizsiemu_eur", "vypadok", "vypadok_od", "url"])
    (ddir / "doplatky-aktualne.csv").write_text(txt, encoding="utf-8")
    files.append(("doplatky-aktualne.csv", f"Všetky hradené lieky s doplatkom, úhradou a najnižším doplatkom v skupine (platné od {PLATNOST})", len(rows)))

    if nxt:
        nxt_iso = nxt.get("platnostIso", "")
        ch = []
        for g in groups:
            for it in g["i"]:
                np_ = nxt["prices"].get(it["kod"])
                if np_ is None:
                    ch.append([it["kod"], it["name"], g["s"], it["dop"], None, None, "vypadne zo zoznamu"])
                    continue
                if it["dop"] is None or np_[2] is None:
                    continue
                d = round(np_[2] - it["dop"], 2)
                if abs(d) >= 0.01:
                    ch.append([it["kod"], it["name"], g["s"], it["dop"], np_[2], d, "zdraží" if d > 0 else ("bez doplatku" if np_[2] < 0.005 else "zlacnie")])
        ch.sort(key=lambda r: (r[6] != "zdraží", -(abs(r[5]) if r[5] is not None else 0)))
        fn = f"zmeny-{nxt_iso[:7]}.csv"
        (ddir / fn).write_text(_csv(ch, ["kod_sukl", "nazov", "ucinna_latka", "doplatok_teraz_eur", f"doplatok_od_{nxt_iso}_eur", "zmena_eur", "stav"]), encoding="utf-8")
        files.append((fn, f"Zmeny doplatkov od {sk_date(nxt_iso)} oproti súčasnému zoznamu", len(ch)))

    vrows = []
    for g in groups:
        for it in g["i"]:
            v = vyp.get(it["kod"])
            if v:
                vrows.append([it["kod"], it["name"], g["s"], STAV.get(v.get("stav"), v.get("stav")), v.get("od", "")])
    vrows.sort(key=lambda r: r[4], reverse=True)
    (ddir / "vypadky.csv").write_text(_csv(vrows, ["kod_sukl", "nazov", "ucinna_latka", "stav", "od"]), encoding="utf-8")
    files.append(("vypadky.csv", "Lieky s hláseným prerušením alebo ukončením dodávok (ŠÚKL, posledné 2 roky)", len(vrows)))

    if history:
        months = [h[0][:7] for h in history]
        hrows = []
        for g in groups:
            for it in g["i"]:
                hrows.append([it["kod"], it["name"], g["s"]] + [(p[it["kod"]][2] if it["kod"] in p and p[it["kod"]][2] is not None else None) for _, p in history])
        (ddir / "doplatky-historia.csv").write_text(_csv(hrows, ["kod_sukl", "nazov", "ucinna_latka"] + months), encoding="utf-8")
        files.append(("doplatky-historia.csv", f"Doplatok každého lieku po mesiacoch ({months[0]} až {months[-1]})", len(hrows)))

    # RSS: mesačné zmeny doplatkov (články)
    items = []
    for sl, t, d, _, iso in month_articles[:24]:
        pub = dt.datetime.fromisoformat(iso + "T06:00:00+01:00") if iso else dt.datetime.now(dt.timezone.utc)
        if pub.date() > today + dt.timedelta(days=40):
            continue
        items.append(f"<item><title>{esc(t)}</title><link>{BASE}/clanky/{sl}/</link><guid>{BASE}/clanky/{sl}/</guid>"
                     f"<pubDate>{format_datetime(pub)}</pubDate><description>{esc(d)}</description></item>")
    rss = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
           f'<title>Zmeny doplatkov za lieky – doplatkyliekov.sk</title><link>{BASE}/zmeny/</link>'
           f'<atom:link href="{BASE}/rss.xml" rel="self" type="application/rss+xml"/>'
           '<description>Každý mesiac: ktoré lieky zdražejú, zlacnejú alebo vypadnú zo zoznamu hradených liekov.</description>'
           f'<language>sk</language>{"".join(items)}</channel></rss>\n')
    (SITE / "rss.xml").write_text(rss, encoding="utf-8")

    def size(fn):
        n = (ddir / fn).stat().st_size
        return f"{n / 1024 / 1024:.1f} MB".replace(".", ",") if n > 1024 * 1024 else f"{round(n / 1024)} kB"
    trs = "".join(f'<tr><td><a href="/data/{fn}" download>{esc(fn)}</a></td><td>{esc(desc)}</td><td class="num">{n:,}</td><td class="num">{size(fn)}</td></tr>'.replace(",", " ")
                  for fn, desc, n in files)
    crumb_items = [("Domov", "/"), ("Dáta pre novinárov", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Otvorené dáta · aktualizované denne</p>
    <h1 class="page-h1">Dáta pre novinárov</h1>
    <p class="page-sub">Doplatky všetkých hradených liekov, mesačné zmeny a výpadky v tabuľkách na stiahnutie. Údaje sú zo Zoznamu kategorizovaných liekov MZ SR platného od {esc(PLATNOST)} a z hlásení ŠÚKL.</p>
  </section>
  <section class="card">
    <h2>Súbory na stiahnutie</h2>
    <div class="scroll"><table class="ltable">
      <thead><tr><th>Súbor</th><th>Obsah</th><th class="num">Riadkov</th><th class="num">Veľkosť</th></tr></thead>
      <tbody>{trs}</tbody>
    </table></div>
    <p class="hint">Súbory CSV sa otvoria priamo v Exceli: kódovanie UTF-8, oddeľovač bodkočiarka, desatinná čiarka. Doplatok je maximálny doplatok za balenie podľa zoznamu MZ SR; lekáreň ho môže znížiť.</p>
  </section>
  <section class="card">
    <h2>Zmeny každý mesiac</h2>
    <p>Prehľad, čo od budúceho mesiaca zdražie, zlacnie a vypadne, je na stránke <a href="/zmeny/">Zmeny doplatkov</a> a v <a href="/clanky/">mesačných článkoch</a>. Nové články môžete sledovať cez <a href="/rss.xml">RSS</a>.</p>
  </section>
  <section class="card">
    <h2>Ako citovať</h2>
    <p>Dáta môžete voľne použiť, aj komerčne (licencia <a href="https://creativecommons.org/licenses/by/4.0/deed.sk" rel="noopener">CC BY 4.0</a>). Uveďte prosím zdroj:</p>
    <blockquote>Zdroj: doplatkyliekov.sk podľa údajov MZ SR a ŠÚKL</blockquote>
    <p>Pôvodné údaje zverejňuje <a href="https://www.health.gov.sk/?zoznam-kategorizovanych-liekov" rel="noopener">Ministerstvo zdravotníctva SR</a> a <a href="https://www.sukl.sk/" rel="noopener">ŠÚKL</a>. Doplatok sa porovnáva v rámci skupiny liekov s rovnakou látkou, silou, liekovou formou a veľkosťou balenia, ako ju určuje zoznam MZ SR.</p>
  </section>
  <section class="card">
    <h2>Potrebujete iný prepočet?</h2>
    <p>Radi pripravíme údaje pre konkrétnu skupinu liekov, ochorenie alebo obdobie. Napíšte na <a href="mailto:kontakt@doplatkyliekov.sk">kontakt@doplatkyliekov.sk</a>.</p>
  </section>"""
    ld = breadcrumb_ld(crumb_items)
    dataset = {"@context": "https://schema.org", "@type": "Dataset", "name": "Doplatky za lieky na Slovensku",
               "description": "Doplatky všetkých liekov hradených z verejného zdravotného poistenia, mesačné zmeny a výpadky dodávok.",
               "url": f"{BASE}/data/", "license": "https://creativecommons.org/licenses/by/4.0/", "inLanguage": "sk",
               "creator": {"@type": "Organization", "name": "doplatkyliekov.sk", "url": BASE},
               "dateModified": today.isoformat(), "isBasedOn": "https://www.health.gov.sk/?zoznam-kategorizovanych-liekov",
               "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{BASE}/data/{fn}"} for fn, _, _ in files]}
    write("/data/", page("Dáta pre novinárov: doplatky za lieky na stiahnutie", "Doplatky všetkých hradených liekov, mesačné zmeny a výpadky ako CSV na stiahnutie. Otvorené dáta podľa MZ SR a ŠÚKL.",
                         "/data/", body, [ld, dataset]).replace('</head>', '<link rel="alternate" type="application/rss+xml" title="Zmeny doplatkov" href="/rss.xml">\n</head>', 1))
    urls.append(("/data/", "0.5"))

    # ---------------- /pre-lekarov/ ----------------
    use_next = bool(nxt and nxt.get("platnostIso") and dt.date.fromisoformat(nxt["platnostIso"]) - today <= dt.timedelta(days=6))
    valid_from = sk_date(nxt["platnostIso"]) if use_next else PLATNOST

    def price(it):
        if use_next:
            np_ = nxt["prices"].get(it["kod"])
            return None if np_ is None else np_[2]
        return it["dop"]
    by_atc = defaultdict(list)
    for g in groups:
        by_atc[g["a"]].append(g)
    sections = []
    for cond, atcs in CHEAT:
        trs = []
        for a in atcs:
            gs = [g for g in by_atc.get(a, []) if g["f"].startswith("p.o.")]
            if not gs:
                continue
            subst = gs[0]["s"]
            zero = defaultdict(int)  # značka → počet skupín (sila × balenie) bez doplatku
            cheapest = None
            n_groups = 0
            for g in gs:
                its = [(price(it), it) for it in g["i"]]
                its = [(p, it) for p, it in its if p is not None and (vyp.get(it["kod"]) or {}).get("stav") not in ("R", "Z")]
                if not its:
                    continue
                n_groups += 1
                for p, it in its:
                    brand = brand_of(it["name"])
                    if p < 0.005:
                        zero[brand] += 1
                    elif cheapest is None or p < cheapest[0]:
                        cheapest = (p, brand, g["f"])
            if not n_groups:
                continue
            top = sorted(zero.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            if top:
                cell = "0 € " + ", ".join(esc(b) for b, _ in top) + (f' <small>+{len(zero) - 3}</small>' if len(zero) > 3 else "")
                cls = "zero"
            else:
                cell = f"od {esc(eur(cheapest[0]))} <small>{esc(cheapest[1])}, {esc(re.sub(r'[(][^)]*[)]', '', cheapest[2].replace('p.o. ', '')).strip())}</small>" if cheapest else "–"
                cls = ""
            href = f"/latka/{subst_slug[subst]}/" if subst in subst_slug else "/"
            trs.append(f'<tr><td><a href="{href}">{esc(subst)}</a></td><td class="{cls}">{cell}</td></tr>')
        if trs:
            sections.append(f'<tbody><tr class="ch-cond"><th colspan="2">{esc(cond)}</th></tr>{"".join(trs)}</tbody>')
    qr = segno.make(BASE + "/pre-lekarov/", error="m").svg_inline(scale=1, border=0, dark="#000", light=None, omitsize=True).replace("<svg ", '<svg aria-hidden="true" ')
    crumb_items = [("Domov", "/"), ("Pre lekárov", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro no-print">
    <p class="eyebrow">Pre ambulancie · zostavené automaticky každý mesiac</p>
    <h1 class="page-h1">Najlacnejšie lieky: ťahák pre ambulanciu</h1>
    <p class="page-sub">Bežne predpisované látky a pri každej lieky bez doplatku, alebo ak taký nie je, liek s najnižším doplatkom. Jedna strana A4 na vytlačenie k počítaču v ambulancii.</p>
    <div class="print-btns"><button type="button" onclick="window.print()">Vytlačiť ťahák (A4)</button></div>
  </section>
  <section class="cheat" aria-label="Ťahák">
    <header class="ch-head">
      <div><h2>Najlacnejšie lieky pre pacienta</h2><p>Platné od {esc(valid_from)} · zoznam kategorizovaných liekov MZ SR</p></div>
      <div class="ch-qr">{qr}<span>Aktuálna verzia<br><b>doplatkyliekov.sk/pre-lekarov</b></span></div>
    </header>
    <table class="ch-table">
      <thead><tr><th>Účinná látka</th><th>0 € = bez doplatku aspoň v niektorej sile a balení · inak najnižší doplatok</th></tr></thead>
      {"".join(sections)}
    </table>
    <p class="ch-foot">Uvedené sú lieky na perorálne podanie bez hlásenia o prerušení alebo ukončení dodávok. Doplatok závisí od sily a veľkosti balenia; pri konkrétnom balení ho overte na doplatkyliekov.sk alebo v lekárni. Doplatok je maximálny, lekáreň ho môže znížiť. Informačný materiál, nie reklama na lieky.</p>
  </section>
  <style>
    .print-btns button {{ font: inherit; font-weight: 600; cursor: pointer; border-radius: 999px; border: 0; background: var(--accent); color: var(--accent-ink); padding: 12px 20px; margin-top: 8px; }}
    .cheat {{ background: #fff; color: #111; border-radius: 14px; padding: 24px; max-width: 900px; box-shadow: 0 10px 40px -20px #000; }}
    .ch-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; border-bottom: 2px solid #0a8f6f; padding-bottom: 10px; }}
    .ch-head h2 {{ font-family: var(--font-display); color: #0b3d33; font-size: 24px; margin: 0; }}
    .ch-head p {{ margin: 4px 0 0; color: #444; font-size: 14px; }}
    .ch-qr {{ display: flex; align-items: center; gap: 8px; font-size: 12px; color: #333; }}
    .ch-qr svg {{ width: 70px; height: 70px; }}
    .ch-table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 8px; }}
    .ch-table th, .ch-table td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #e3e3e3; vertical-align: top; color: #111; }}
    .ch-table thead th {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: #555; }}
    .ch-table .ch-cond th {{ background: #eef8f5; color: #0b3d33; font-size: 13px; padding-top: 7px; }}
    .ch-table td:first-child {{ width: 28%; font-weight: 600; }}
    .ch-table td:first-child a {{ color: #111; text-decoration: none; }}
    .ch-table td.zero {{ color: #075e49; font-weight: 600; }}
    .ch-table small {{ color: #666; }}
    .ch-foot {{ font-size: 12px; color: #555; margin: 10px 0 0; }}
    @media (max-width: 560px) {{ .cheat {{ padding: 14px; }} .ch-head {{ flex-direction: column; align-items: flex-start; }} .ch-table {{ font-size: 13px; }} }}
    @media print {{
      @page {{ size: A4; margin: 0; }}
      .site-head, .bottom-nav, footer, .crumbs, .no-print, .skip {{ display: none !important; }}
      html, body {{ background: #fff !important; padding: 0 !important; min-height: 0 !important; }}
      .wrap, main {{ display: block !important; padding: 0 !important; margin: 0 !important; max-width: none !important; }}
      .cheat {{ box-shadow: none; border-radius: 0; padding: 8mm 10mm 0; max-width: none; }}
      .ch-table {{ font-size: 8pt; line-height: 1.15; }} .ch-table th, .ch-table td {{ padding: 1px 5px; }}
      .ch-table .ch-cond th {{ padding-top: 2px; font-size: 8pt; }}
      .ch-head {{ padding-bottom: 4px; }} .ch-head h2 {{ font-size: 15pt; }} .ch-head p {{ font-size: 8.5pt; margin: 0; }} .ch-qr svg {{ width: 22mm; height: 22mm; }}
      .ch-foot {{ font-size: 7pt; margin-top: 4px; }}
      .ch-table tbody {{ break-inside: avoid; }}
    }}
  </style>"""
    write("/pre-lekarov/", page("Lieky bez doplatku: ťahák pre ambulancie (A4)", "Bežne predpisované látky a lieky, ktoré sú pri nich bez doplatku. Jedna strana A4 pre ambulanciu, aktualizovaná každý mesiac.",
                                "/pre-lekarov/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/pre-lekarov/", "0.5"))

    # ---------------- /vlozit/ ----------------
    snippet = '<div data-doplatky></div>\n<script src="https://doplatkyliekov.sk/vlozit/embed.js" async></script>'
    snippet_iframe = '<iframe src="https://doplatkyliekov.sk/vlozit/okno/" title="Porovnanie doplatkov za lieky" style="width:100%;max-width:640px;height:520px;border:0" loading="lazy"></iframe>'
    crumb_items = [("Domov", "/"), ("Kalkulačka na váš web", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Zadarmo pre lekárne, ambulancie, obce a kluby seniorov</p>
    <h1 class="page-h1">Kalkulačka doplatkov na váš web</h1>
    <p class="page-sub">Vložte na svoj web okno, v ktorom si návštevníci vyhľadajú liek a hneď uvidia jeho doplatok a lacnejšie lieky s rovnakou látkou. Údaje sa aktualizujú samy každý deň.</p>
  </section>
  <section class="card">
    <h2>Ako to bude vyzerať</h2>
    <div class="emb-preview"><div data-doplatky data-tema="auto"></div></div>
  </section>
  <section class="card">
    <h2>Kód na vloženie</h2>
    <p>Skopírujte tento kód a vložte ho na stránku tam, kde sa má kalkulačka zobraziť. Výška okna sa prispôsobí sama.</p>
    <pre class="emb-code" id="emb-code">{esc(snippet)}</pre>
    <div class="mine-tools"><button type="button" data-copy="emb-code">Skopírovať kód</button></div>
    <p class="hint">Farby: pridajte <code>data-tema="svetla"</code> alebo <code>data-tema="tmava"</code> k prvku <code>div</code>. Predvolene sa prispôsobí nastaveniu návštevníka.</p>
    <details><summary>Ak váš web nedovolí vložiť skript (napr. niektoré redakčné systémy)</summary>
      <p>Použite len okno (iframe) s pevnou výškou:</p>
      <pre class="emb-code" id="emb-code2">{esc(snippet_iframe)}</pre>
      <div class="mine-tools"><button type="button" data-copy="emb-code2">Skopírovať kód</button></div>
    </details>
  </section>
  <section class="card">
    <h2>Podmienky</h2>
    <ul>
      <li>Kalkulačka je zadarmo, bez registrácie a bez reklamy.</li>
      <li>Nepoužíva cookies ani nesleduje návštevníkov vášho webu. Hľadanie prebieha v prehliadači návštevníka.</li>
      <li>Prosíme, nemeňte ani neskrývajte odkaz na doplatkyliekov.sk v okne.</li>
      <li>Údaje majú informačný charakter a nenahrádzajú radu lekára ani lekárnika.</li>
    </ul>
    <p>Otázky alebo želania (napríklad iné farby): <a href="mailto:kontakt@doplatkyliekov.sk">kontakt@doplatkyliekov.sk</a>.</p>
  </section>
  <style>
    .emb-preview {{ max-width: 640px; }}
    .emb-code {{ white-space: pre-wrap; word-break: break-all; background: var(--surface-2, #0b1316); border: 1px solid var(--line); border-radius: 12px; padding: 14px; font-family: var(--font-mono); font-size: 13.5px; }}
    details summary {{ cursor: pointer; margin-top: 10px; }}
  </style>"""
    script = """<script src="/vlozit/embed.js" async></script>
<script>
document.querySelectorAll('[data-copy]').forEach(function (b) {
  b.addEventListener('click', function () {
    var t = document.getElementById(b.dataset.copy).textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { b.textContent = 'Skopírované'; },
      function () { var r = document.createRange(); r.selectNodeContents(document.getElementById(b.dataset.copy)); var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = 'Označené – stlačte Ctrl+C'; });
    setTimeout(function () { b.textContent = 'Skopírovať kód'; }, 2500);
  });
});
</script>"""
    write("/vlozit/", page("Kalkulačka doplatkov na váš web – zadarmo", "Vložte na web lekárne, ambulancie alebo obce okno na porovnanie doplatkov za lieky. Zadarmo, bez cookies, aktualizované denne.",
                           "/vlozit/", body, breadcrumb_ld(crumb_items), script))
    urls.append(("/vlozit/", "0.4"))
    okno = (c["ROOT"] / "templates" / "okno.html").read_text(encoding="utf-8").replace("{{PLATNOST}}", esc(PLATNOST))
    (SITE / "vlozit" / "okno").mkdir(parents=True, exist_ok=True)
    (SITE / "vlozit" / "okno" / "index.html").write_text(c["versioned"](okno), encoding="utf-8")
    return files
