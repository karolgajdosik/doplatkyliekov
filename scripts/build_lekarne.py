"""Stiahne lekárne na Slovensku z OpenStreetMap (Overpass API) do data/lekarne.json.

Údaje © prispievatelia OpenStreetMap, licencia ODbL – na webe treba uviesť zdroj.
  python3 scripts/build_lekarne.py
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "lekarne.json"
OUT_VYD = OUT.parent / "vydajne.json"
VYD_QUERY = ('[out:json][timeout:150];area["ISO3166-1"="SK"][admin_level=2]->.a;('
             'nwr["shop"="medical_supply"](area.a);nwr["shop"="orthopedics"](area.a);nwr["healthcare"="orthopedics"](area.a);'
             'nwr["shop"="hearing_aids"](area.a);nwr["healthcare"="audiologist"](area.a);nwr["shop"="optician"](area.a););out center tags;')
QUERY = ('[out:json][timeout:150];area["ISO3166-1"="SK"][admin_level=2]->.a;'
         '(node["amenity"="pharmacy"](area.a);way["amenity"="pharmacy"](area.a););out center tags;')
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]


PLACES = ('[out:json][timeout:150];area["ISO3166-1"="SK"][admin_level=2]->.a;'
          'node["place"~"^(city|town|village)$"]["name"](area.a);out;')


def fetch(query=QUERY):
    last = None
    for url in ENDPOINTS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(),
                                             headers={"User-Agent": "doplatkyliekov.sk (kontakt@doplatkyliekov.sk)"})
                with urllib.request.urlopen(req, timeout=200) as r:
                    return json.loads(r.read())
            except Exception as e:  # noqa: BLE001
                last = f"{url}: {e}"
                print("Overpass zlyhal:", last)
                time.sleep(10)
    raise SystemExit(f"Lekárne sa nepodarilo stiahnuť ({last})")


def row(e, default):
    t = e.get("tags", {})
    lat = e.get("lat") or e.get("center", {}).get("lat")
    lon = e.get("lon") or e.get("center", {}).get("lon")
    if lat is None:
        return None
    street = t.get("addr:street") or t.get("addr:place") or ""
    num = t.get("addr:housenumber") or t.get("addr:conscriptionnumber") or ""
    return [round(lat, 5), round(lon, 5), (t.get("name") or default).strip()[:80], f"{street} {num}".strip()[:80],
            (t.get("addr:city") or "").strip()[:50], (t.get("opening_hours") or "")[:120],
            (t.get("phone") or t.get("contact:phone") or "")[:40]]


def vydajne(places):
    """Výdajne zdravotníckych pomôcok, ortopedické potreby, načúvacie prístroje a optiky → data/vydajne.json."""
    out = []
    for e in fetch(VYD_QUERY).get("elements", []):
        t = e.get("tags", {})
        if t.get("amenity") == "pharmacy":
            continue  # lekáreň je už v lekarne.json
        shop, hc = t.get("shop", ""), t.get("healthcare", "")
        if shop == "optician":
            typ, default = "opt", "Optika"
            if not re.search(r"opti|očn|ocn|vision|okuliar|zrak|šošov|sosov|vizi|eye", (t.get("name") or "optika"), re.I):
                continue
        elif shop == "hearing_aids" or hc == "audiologist":
            typ, default = "sluch", "Načúvacie prístroje"
        else:
            typ, default = "zp", "Zdravotnícke potreby"
        r = row(e, default)
        if r:
            out.append(r + [typ])
    fill_city(out, places)
    if len(out) < 50:
        print(f"Výdajne: podozrivo málo ({len(out)}), súbor neprepisujem")
        return
    out.sort()
    OUT_VYD.write_text(json.dumps({"zdroj": "© prispievatelia OpenStreetMap (ODbL)", "vydajne": out}, ensure_ascii=False,
                                  separators=(",", ":")), encoding="utf-8")
    print(f"Výdajne: {len(out)} (pomôcky {sum(1 for x in out if x[7] == 'zp')}, optiky {sum(1 for x in out if x[7] == 'opt')}, "
          f"načúvacie {sum(1 for x in out if x[7] == 'sluch')})")


def fill_city(out, places):
    import math
    filled = 0
    for x in out:
        if x[4]:
            continue
        best, bd = None, 9e9
        for la, lo, nm, kind in places:
            dd = (la - x[0]) ** 2 + ((lo - x[1]) * math.cos(math.radians(x[0]))) ** 2
            if kind == "village":
                dd *= 1.6  # mesto má prednosť pred susednou dedinou
            if dd < bd:
                best, bd = nm, dd
        if best and math.sqrt(bd) * 111 < 8:
            x[4] = best
            filled += 1
    return filled


def main():
    d = fetch()
    out = []
    for e in d.get("elements", []):
        t = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None:
            continue
        street = t.get("addr:street") or t.get("addr:place") or ""
        num = t.get("addr:housenumber") or t.get("addr:conscriptionnumber") or ""
        out.append([round(lat, 5), round(lon, 5), (t.get("name") or "Lekáreň").strip()[:80], f"{street} {num}".strip()[:80],
                    (t.get("addr:city") or "").strip()[:50], (t.get("opening_hours") or "")[:120],
                    (t.get("phone") or t.get("contact:phone") or "")[:40]])
    # obec chýba pri väčšine lekární: doplníme najbližšiu obec (do 8 km) z OpenStreetMap
    places = []
    try:
        places = [(e["lat"], e["lon"], e["tags"]["name"], e["tags"].get("place")) for e in fetch(PLACES).get("elements", []) if "lat" in e]
        print(f"Obec doplnená pri {fill_city(out, places)} lekárňach")
    except SystemExit as e:
        print("Obce sa nepodarilo doplniť:", e)
    try:
        vydajne(places)
    except SystemExit as e:
        print("Výdajne sa nepodarilo stiahnuť:", e)
    if len(out) < 300:
        raise SystemExit(f"Podozrivo málo lekární ({len(out)}), súbor neprepisujem.")
    out.sort()
    OUT.write_text(json.dumps({"zdroj": "© prispievatelia OpenStreetMap (ODbL)", "lekarne": out}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"Lekárne: {len(out)}, s adresou {sum(1 for x in out if x[3])}, s otváracími hodinami {sum(1 for x in out if x[5])}")


if __name__ == "__main__":
    main()
