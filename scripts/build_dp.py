#!/usr/bin/env python3
"""Zoznam kategorizovaných dietetických potravín MZ SR (štvrťročný) → data/dp.json.

Stránka: health.gov.sk/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-dietetickych-potravin/zkdpRRRRMM/
„Časť A“ = xlsx: Podskupina (riadky skupín), Kód vykazujúci, Kód párujúci, Názov, Doplnok, Výrobca, Štát, Maximálna cena
v lekárni, Úhrada ZP, Spôsob úhrady, Doplatok, % doplatku, LS, RD v balení, Preskripčné obmedzenie, Indikačné obmedzenia,
Množstvové limity (3 stĺpce), Energetická hodnota. Ak je zverejnený ďalší štvrťrok, uloží sa data/dp_next.json (kód → doplatok).

  python3 scripts/build_dp.py               (sťahuje)
  python3 scripts/build_dp.py --raw SUBOR   (lokálny xlsx, voliteľne od=RRRRMM)
"""
import datetime as dt
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
H = "https://www.health.gov.sk"
LIST = "/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-dietetickych-potravin/"
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
TOP = {"V06C": "Výživa pri metabolických ochoreniach", "V06D": "Dojčenská výživa", "V06E": "Enterálna výživa"}


def fetch(url, binary=False):
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                d = r.read()
                return d if binary else d.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
            time.sleep(4)
    return None


def num(v):
    try:
        return round(float(str(v).replace(",", ".")), 4) if v not in (None, "") else None
    except ValueError:
        return None


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def parse(blob, od):
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True).active
    heads, groups, cur = {}, {}, None
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        r = list(r) + [None] * (22 - len(r))
        if i < 2:
            continue
        if r[0] and not r[1]:
            code = clean(r[0])
            name = clean(r[3])
            if r[4] and len(code) >= 7:
                name += f" ({clean(r[4])})"
            heads[code] = name
            cur = code
            continue
        if not r[1] or not cur:
            continue
        lim = [clean(x) for x in r[16:19] if x]
        groups.setdefault(cur, []).append({
            "kod": clean(r[1]), "n": clean(r[3]), "d": clean(r[4]), "v": clean(r[5]), "st": clean(r[6]),
            "c": num(r[7]), "u": num(r[8]), "su": clean(r[9]), "dop": num(r[10]), "pr": clean(r[14]),
            "io": bool(r[15]), "lim": bool(lim), "kcal": num(r[19]),
        })
    n = sum(len(v) for v in groups.values())
    if n < 300:
        raise RuntimeError(f"podozrivo málo dietetických potravín: {n}")
    out = []
    for code in sorted(groups):
        chain = [[c, heads[c]] for c in sorted(heads, key=len) if code.startswith(c) and c != code and len(c) >= 4]
        items = sorted(groups[code], key=lambda x: (x["dop"] if x["dop"] is not None else 9e9, x["n"]))
        out.append({"k": code, "name": heads.get(code, code), "chain": chain, "lim": [], "i": items})
    y, m = int(od[:4]), int(od[4:6])
    em = m + 2
    end = dt.date(y + (em > 12), (em - 1) % 12 + 1, 1)
    end = dt.date(end.year + (end.month == 12), end.month % 12 + 1, 1) - dt.timedelta(days=1)
    return {"od": f"{y}-{m:02d}-01", "do": end.isoformat(), "skupiny": TOP, "groups": out, "pocet": n}


def main():
    if "--raw" in sys.argv:
        blob = Path(sys.argv[sys.argv.index("--raw") + 1]).read_bytes()
        od = next((a.split("=")[1] for a in sys.argv if a.startswith("od=")), "202610")
        res = parse(blob, od)
        (DATA / "dp.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"dp.json: {res['pocet']} potravín v {len(res['groups'])} skupinách")
        return
    page = fetch(H + LIST)
    if not page:
        return print("Zoznam dietetických potravín nedostupný, ponechávam uložené údaje")
    periods = sorted(set(re.findall(r"/zkdp-?(\d{6})/", page)))
    today = dt.date.today().strftime("%Y%m")
    cur = max((p for p in periods if p <= today), default=None)
    nxt = min((p for p in periods if p > today), default=None)
    old = json.loads((DATA / "dp.json").read_text(encoding="utf-8")) if (DATA / "dp.json").exists() else {}
    for period, target in ((cur, "dp.json"), (nxt, "dp_next.json")):
        if not period:
            if target == "dp_next.json" and (DATA / target).exists():
                (DATA / target).unlink()
            continue
        sub = fetch(f"{H}{LIST}zkdp{period}/") or fetch(f"{H}{LIST}zkdp-{period}/") or ""
        link = next((u for u, t in re.findall(r'href="(https://cloud\.health\.gov\.sk/s/[A-Za-z0-9]+/download)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)', sub)
                     if re.match(r"\s*Časť A", t)), None)
        if not link:
            print(f"zkdp{period}: nenašiel som časť A")
            continue
        if target == "dp.json" and old.get("zdroj") == link:
            print(f"zkdp{period}: bez zmeny")
            continue
        blob = fetch(link, binary=True)
        if not blob or blob[:2] != b"PK":
            print(f"zkdp{period}: časť A sa nepodarilo stiahnuť")
            continue
        try:
            res = parse(blob, period)
        except Exception as e:  # noqa: BLE001
            print(f"zkdp{period}: chyba {e}")
            continue
        res["zdroj"] = link
        if target == "dp.json":
            (DATA / target).write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            (DATA / target).write_text(json.dumps({"od": res["od"], "prices": {x["kod"]: x["dop"] for g in res["groups"] for x in g["i"]}},
                                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{target}: obdobie {period}, {res['pocet']} potravín")


if __name__ == "__main__":
    main()
