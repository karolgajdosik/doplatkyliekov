"""Stiahne aktuálny Zoznam kategorizovaných liekov (časť A) z webu MZ SR
a prevedie ho na site/data.json pre web doplatkyliekov.sk.

Použitie:
  python scripts/build_data.py                 # stiahne najnovší zoznam
  python scripts/build_data.py cesta/k/suboru.xlsx   # použije lokálny súbor
"""
import datetime as dt
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "site" / "data.json"
URL = ("https://www.health.gov.sk/Zdroje?/Sources/kategorizacia/zkl/"
       "{y}{m:02d}/cast_A_zoznam_liekov_N_k_01_{m:02d}_{y}.xlsx")
MIN_ITEMS = 1000  # ochrana pred poškodeným súborom


def candidates(today):
    """Zoznam platný v aktuálnom mesiaci, pri jeho nedostupnosti predchádzajúce.
    Budúci mesiac neberieme: jeho doplatky ešte v lekárňach neplatia."""
    y, m = today.year, today.month
    months = []
    for delta in (0, -1, -2):
        mm = m + delta
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        months.append((yy, mm))
    return months


UA = {"User-Agent": "doplatkyliekov.sk data updater"}


def fetch(url, attempts=12):
    """Stiahne súbor. Server MZ SR často preruší spojenie uprostred prenosu,
    preto pri prerušení pokračujeme od prijatého bajtu (HTTP Range) a skúšame znova."""
    data = b""
    total = None
    for attempt in range(1, attempts + 1):
        headers = dict(UA)
        if data:
            headers["Range"] = f"bytes={len(data)}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                if data and r.status != 206:  # server ignoroval Range, začíname odznova
                    data = b""
                if total is None or r.status == 200:
                    cl = r.headers.get("Content-Length")
                    total = (len(data) + int(cl)) if cl else None
                try:
                    data += r.read()
                except http.client.IncompleteRead as e:
                    data += e.partial
                    print(f"  pokus {attempt}: prerušené pri {len(data)} B, pokračujem")
                    time.sleep(2)
                    continue
            if total is None or len(data) >= total:
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            print(f"  pokus {attempt}: HTTP {e.code}")
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {attempt}: {e}")
            time.sleep(3)
    raise RuntimeError(f"nepodarilo sa stiahnuť celý súbor ({len(data)} B z {total})")


def download():
    for y, m in candidates(dt.date.today()):
        url = URL.format(y=y, m=m)
        print(f"Sťahujem: {url}")
        try:
            data = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"Nedostupné: {url} ({e})")
            continue
        if data[:2] == b"PK":  # xlsx je zip
            print(f"Stiahnuté: {len(data)} B")
            return data, f"1. {m}. {y}", f"{y}-{m:02d}-01"
        print(f"Nie je xlsx: {url}")
    sys.exit("Nepodarilo sa stiahnuť žiadny zoznam.")


def num(x):
    if isinstance(x, (int, float)):
        return round(float(x), 2)
    if isinstance(x, str):
        try:
            return round(float(x.replace(",", ".").replace(" ", "")), 2)
        except ValueError:
            return None
    return None


def parse(xlsx_bytes):
    ws = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    h1, h2 = next(rows), next(rows)
    head = [(a or b or "") for a, b in zip(h1, h2)]
    col = {name: i for i, name in enumerate(head) if name}
    # pevné stĺpce overené na zozname 08/2026; overíme, že sedia
    need = {"Názov": 5, "Doplnok": 6, "Konečná c.": 10, "ÚZP": 11, "DOP": 13, "Typ lieku": 4}
    for name, idx in need.items():
        if col.get(name, idx) != idx:
            sys.exit(f"Zmenila sa štruktúra súboru: stĺpec {name} je na pozícii {col.get(name)}, čakal som {idx}.")

    groups, cur = [], None
    for r in rows:
        if not r or len(r) < 14:
            continue
        if r[0] and r[5] and r[10] is None and r[3] is None and r[4] is None:
            cur = {"a": r[0], "s": r[5], "f": r[6] or "", "i": []}
            groups.append(cur)
        elif cur is not None and r[5]:
            cur["i"].append([str(r[0]), r[5], r[6] or "", num(r[10]), num(r[11]), num(r[13]), r[4] or ""])
    groups = [g for g in groups if g["i"]]
    n = sum(len(g["i"]) for g in groups)
    if n < MIN_ITEMS:
        sys.exit(f"Príliš málo liekov ({n}), súbor je asi poškodený.")
    return groups, n


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        data = path.read_bytes()
        m = re.search(r"k_01_(\d{2})_(\d{4})", path.name)
        label, iso = (f"1. {int(m.group(1))}. {m.group(2)}", f"{m.group(2)}-{m.group(1)}-01") if m else ("", "")
    else:
        data, label, iso = download()
    groups, n = parse(data)
    OUT.write_text(json.dumps({"platnost": label, "platnostIso": iso, "groups": groups},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Uložené {OUT}: {len(groups)} skupín, {n} balení, platnosť od {label}")


if __name__ == "__main__":
    main()
