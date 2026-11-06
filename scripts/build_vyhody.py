#!/usr/bin/env python3
"""Denná kontrola stránok poisťovní s benefitmi na doplatky za lieky → data/vyhody.json.

Prehľad na /vyhody-poistovni/ je písaný ručne. Tento skript každý deň stiahne zdrojové stránky poisťovní, overí,
že na nich sú stále kľúčové sumy (napr. 300 € Union, 400 € Dôvera, 450 € VšZP), a porovná všetky sumy v eurách
s predchádzajúcou kontrolou. Pri zmene zapíše vyhody_zmena.md (workflow z neho založí issue na GitHube)
a na stránke sa zobrazí, že podmienky preverujeme.

  python3 scripts/build_vyhody.py
"""
import datetime as dt
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "vyhody.json"
ALERT = ROOT / "vyhody_zmena.md"
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
SOURCES = [
    {"id": "union", "nazov": "Union – doplatky pre všetkých", "url": "https://www.union.sk/doplatky-za-lieky-pre-vsetkych/", "sumy": ["300"]},
    {"id": "union-deti", "nazov": "Union – doplatky pre deti", "url": "https://www.union.sk/vratenie-doplatkov-za-lieky-pre-deti/", "sumy": []},
    {"id": "dovera", "nazov": "Dôvera – 400 € za lieky", "url": "https://www.dovera.sk/poistenec/benefity/vsetky/400-eur-za-lieky", "sumy": ["400"]},
    {"id": "vszp", "nazov": "VšZP – Peňaženka zdravia",
     "url": "https://www.vszp.sk/o-nas/informacie-media/tlacove-spravy/az-450-eur-doplatky-za-lieky-dieteticke-potraviny-vszp-historicky-navysuje-financne-prispevky-penazenke-zdravia.html",
     "sumy": ["450"]},
    {"id": "vszp-podmienky", "nazov": "VšZP – podmienky Peňaženky zdravia",
     "url": "https://www.vszp.sk/o-nas/podmienky-pouzivania-elektronickych-sluzieb/vseobecne-podmienky-k-produktu-penazenka-zdravia.html", "sumy": []},
]


def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return e.code, ""
            print(f"  pokus {k + 1}: {url}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
        time.sleep(3 + 3 * k)
    return 0, ""


def main_text(h):
    """Text hlavného obsahu bez hlavičky, menu a pätičky."""
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<noscript.*?</noscript>", " ", h, flags=re.S | re.I)
    m = re.search(r"<main\b.*?</main>", h, re.S | re.I) or re.search(r"<article\b.*?</article>", h, re.S | re.I)
    if m:
        h = m.group(0)
    else:
        h = re.sub(r"<(header|nav|footer)\b.*?</\1>", " ", h, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def amounts(t):
    return sorted({re.sub(r"\s", "", a).replace(",00", "") for a in re.findall(r"(\d[\d ]{0,6}(?:,\d{2})?)\s*(?:€|eur\b|EUR\b)", t)},
                  key=lambda x: (len(x), x))


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    prev = {s["id"]: s for s in old.get("zdroje", [])}
    today = dt.date.today().isoformat()
    res, alerts = [], []
    for s in SOURCES:
        status, h = get(s["url"])
        p = prev.get(s["id"], {})
        if status != 200 or not h:
            # výpadok webu nie je zmena podmienok; pri trvalom 404 upozorníme
            item = {**p, "id": s["id"], "nazov": s["nazov"], "url": s["url"], "stav": "nedostupna" if status not in (404, 410) else "zmazana"}
            if status in (404, 410) and p.get("stav") != "zmazana":
                alerts.append(f"- **{s['nazov']}**: stránka už neexistuje ({status}) – {s['url']}")
            res.append(item)
            continue
        t = main_text(h)
        am = amounts(t)
        missing = [a for a in s["sumy"] if a not in am]
        item = {"id": s["id"], "nazov": s["nazov"], "url": s["url"], "stav": "ok" if not missing else "zmena",
                "sumy": am, "kontrola": today, "zmena_od": p.get("zmena_od", "")}
        if p.get("sumy") is not None and p.get("sumy") != am:
            added = [a for a in am if a not in p["sumy"]]
            removed = [a for a in p["sumy"] if a not in am]
            alerts.append(f"- **{s['nazov']}**: sumy na stránke sa zmenili (pribudli {', '.join(added) or '–'} €, "
                          f"zmizli {', '.join(removed) or '–'} €) – {s['url']}")
            item["zmena_od"] = today
        if missing:
            item["stav"] = "zmena"
            if p.get("stav") != "zmena":
                alerts.append(f"- **{s['nazov']}**: na stránke chýba suma {', '.join(missing)} € – {s['url']}")
        print(f"{s['id']}: {item['stav']}, sumy {am[:12]}")
        res.append(item)
    OUT.write_text(json.dumps({"kontrola": today, "zdroje": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    if alerts:
        ALERT.write_text("Automatická kontrola stránok poisťovní našla zmenu. Treba overiť a upraviť prehľad "
                         "na /vyhody-poistovni/ (VYHODY_OVERENE v scripts/build_pages.py).\n\n" + "\n".join(alerts) + "\n",
                         encoding="utf-8")
        print("ZMENA:\n" + "\n".join(alerts))


if __name__ == "__main__":
    main()
