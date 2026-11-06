#!/usr/bin/env python3
"""Register liekov ŠÚKL (všetky registrované lieky) → data/register.json.

Zdroj: verejné úložisko ŠÚKL, Zoznam_liekov/zoznam_liekov_aktualny.zip (zoznam_liekov.xlsx, list Export_lieky_R).
Ukladá:
  vydaj: kód ŠÚKL → spôsob výdaja (R na predpis, Rx na predpis s obmedzením, Rb osobitné tlačivo, F bez predpisu)
         len pre lieky v zozname kategorizovaných liekov (data/full.json),
  nazov: kód ŠÚKL → názov v registri (z neho sa skladá adresa stránky lieku na sukl.sk so SPC a letákom),
  neh:   registrované lieky mimo zoznamu kategorizovaných (poisťovňa ich nehradí): [názov, výdaj, látka, ATC].
Spúšťa sa mesačne (mesacne.yml).

  python3 scripts/build_register.py               (sťahuje)
  python3 scripts/build_register.py --raw ZIP     (lokálny archív)
"""
import datetime as dt
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
URLS = ["https://www.sukl.sk/verejne/Zoznam_liekov/zoznam_liekov_aktualny.zip",
        "https://sukl.sk/verejne/Zoznam_liekov/zoznam_liekov_aktualny.zip"]
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
VYDAJ = {"R", "Rx", "Rb", "F"}
SKIP_ATC = ("V09", "V10")  # rádiofarmaká, pacient ich v lekárni nekupuje


def fetch():
    for url in URLS:
        for k in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                    d = r.read()
                if d[:2] == b"PK":
                    return d
            except Exception as e:  # noqa: BLE001
                print(f"  pokus {k + 1}: {url}: {e}")
                time.sleep(5)
    return None


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def parse(blob):
    import openpyxl
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = next(n for n in z.namelist() if n.lower().endswith("zoznam_liekov.xlsx"))
    wb = openpyxl.load_workbook(io.BytesIO(z.read(name)), read_only=True, data_only=True)
    ws = wb["Export_lieky_R"] if "Export_lieky_R" in wb.sheetnames else wb.active
    rows = ws.iter_rows(values_only=True)
    head = [clean(h) for h in next(rows)]

    def col(prefix):
        return next(i for i, h in enumerate(head) if h.startswith(prefix))
    i_kod, i_n, i_atc, i_atcn, i_v = col("ŠÚKL kód"), col("Názov"), col("ATC kód"), col("atc_nazov"), col("Výdaj")
    our = set()
    full = DATA / "full.json"
    if full.exists():
        our = {x["kod"] for g in json.loads(full.read_text(encoding="utf-8"))["groups"] for x in g["i"]}
    vydaj, nazov, neh, seen_names, n = {}, {}, {}, set(), 0
    for r in rows:
        kod, nm = clean(r[i_kod]), clean(r[i_n])
        if not kod or not nm:
            continue
        n += 1
        v = clean(r[i_v])
        atc = clean(r[i_atc])
        if kod in our:
            if v in VYDAJ:
                vydaj[kod] = v
            nazov[kod] = nm
            seen_names.add(nm.lower())
            continue
        if atc.startswith(SKIP_ATC) or v not in VYDAJ:
            continue
        key = (nm.lower(), atc)
        cur = neh.get(key)
        # rovnaký názov s rôznym výdajom (napr. menšie balenie bez predpisu): F má prednosť
        if not cur or (v == "F" and cur[1] != "F"):
            neh[key] = [nm, v, clean(r[i_atcn]), atc]
    if n < 20000:
        raise RuntimeError(f"podozrivo málo liekov v registri: {n}")
    # názvy, ktoré sú v zozname kategorizovaných (iné balenie), nevynechávame: hľadanie ich nájde ako hradené
    items = sorted((x for k, x in neh.items() if k[0] not in seen_names), key=lambda x: x[0].lower())
    return {"datum": dt.date.today().isoformat(), "pocet": n, "vydaj": vydaj, "nazov": nazov, "neh": items}


def main():
    if "--raw" in sys.argv:
        blob = Path(sys.argv[sys.argv.index("--raw") + 1]).read_bytes()
    else:
        blob = fetch()
        if not blob:
            return print("Register ŠÚKL nedostupný, ponechávam uložené údaje")
    res = parse(blob)
    (DATA / "register.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    f = sum(1 for x in res["neh"] if x[1] == "F")
    print(f"register.json: {res['pocet']} balení v registri, výdaj pre {len(res['vydaj'])} našich liekov, "
          f"{len(res['neh'])} nehradených liekov ({f} bez predpisu)")


if __name__ == "__main__":
    main()
