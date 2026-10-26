"""Stiahne lekárne na Slovensku z OpenStreetMap (Overpass API) do data/lekarne.json.

Údaje © prispievatelia OpenStreetMap, licencia ODbL – na webe treba uviesť zdroj.
  python3 scripts/build_lekarne.py
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "lekarne.json"
QUERY = ('[out:json][timeout:150];area["ISO3166-1"="SK"][admin_level=2]->.a;'
         '(node["amenity"="pharmacy"](area.a);way["amenity"="pharmacy"](area.a););out center tags;')
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]


def fetch():
    last = None
    for url in ENDPOINTS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                             headers={"User-Agent": "doplatkyliekov.sk (kontakt@doplatkyliekov.sk)"})
                with urllib.request.urlopen(req, timeout=200) as r:
                    return json.loads(r.read())
            except Exception as e:  # noqa: BLE001
                last = f"{url}: {e}"
                print("Overpass zlyhal:", last)
                time.sleep(10)
    raise SystemExit(f"Lekárne sa nepodarilo stiahnuť ({last})")


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
    if len(out) < 300:
        raise SystemExit(f"Podozrivo málo lekární ({len(out)}), súbor neprepisujem.")
    out.sort()
    OUT.write_text(json.dumps({"zdroj": "© prispievatelia OpenStreetMap (ODbL)", "lekarne": out}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"Lekárne: {len(out)}, s adresou {sum(1 for x in out if x[3])}, s otváracími hodinami {sum(1 for x in out if x[5])}")


if __name__ == "__main__":
    main()
