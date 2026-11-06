#!/usr/bin/env python3
"""Ambulancie lekárov a ambulantné pohotovosti z registrov samosprávnych krajov (e-VÚC) → data/lekari.json.

Zdroj: www.e-vuc.sk (registre zdravotníckych zariadení VÚC). Košický kraj e-VÚC nepoužíva, preto chýba.
Postup: kraj → zoznam okresov → zoznam zariadení v okrese (názov, odbornosť, identifikátor, adresa, neprítomnosti,
pri pohotovostiach ordinačný čas). Súradnice sú len v detaile zariadenia, preto sa detaily sťahujú postupne
(najviac --max za beh, pohotovosti prednostne) a ukladajú do data/lekari_gps.json podľa identifikátora.

  python3 scripts/build_ambulancie.py [--max 4000] [--kraj bsk,ttsk] [--delay 0.15]
"""
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT, GPS = DATA / "lekari.json", DATA / "lekari_gps.json"
H = "https://www.e-vuc.sk"
UA = {"User-Agent": "doplatkyliekov.sk (kontakt@doplatkyliekov.sk)"}
KRAJE = {"bsk": (60142, 127099), "ttsk": (84363, 127104), "tsk": (195, 127103), "nsk": (87161, 127101),
         "zsk": (52318, 127105), "bbsk": (93172, 127098), "psk": (97068, 127102)}
ROW = re.compile(r"<tr\s+onclick=\"window\.location = '([^']+)'\"(.*?)</tr>", re.S)
ARG = {a.split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if "=" in a}
for i, a in enumerate(sys.argv[1:-1], 1):
    if a.startswith("--") and "=" not in a:
        ARG[a] = sys.argv[i + 1]
MAX = int(ARG.get("--max", 4000))
DELAY = float(ARG.get("--delay", 0.15))
ONLY = [k for k in ARG.get("--kraj", "").split(",") if k]
n_req = 0


def get(url, tries=3):
    global n_req
    for k in range(tries):
        try:
            n_req += 1
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = r.read().decode("utf-8", "replace")
            time.sleep(DELAY)
            return d
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
            time.sleep(3 + 3 * k)
    return ""


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip(" ,.")


def okresy(kraj, kind, page_id):
    slug = "ambulantne-zdravotnicke-zariadenia" if kind == "amb" else f"ambulantna-pohotovostna-sluzba-v-{kraj}"
    h = get(f"{H}/{kraj}/zdravotnictvo/{slug}.html?page_id={page_id}")
    if not h:
        root = get(f"{H}/{kraj}/")
        m = re.search(r'href="([^"]*/zdravotnictvo/' + re.escape(slug) + r'\.html\?page_id=\d+)"', root)
        h = get(m.group(1) if m.group(1).startswith("http") else H + m.group(1)) if m else ""
    return [(u, txt(t)) for u, t in re.findall(r"<tr onclick=\"window\.location = '([^']+)'\".*?<a [^>]*>(.*?)</a>", h, re.S)
            if "okres" in t.lower() or "Okres" in t]


def rows(url):
    h = get(url)
    out = []
    for u, body in ROW.findall(h):
        a = re.search(r"<a\s[^>]*>(.*?)</a>", body, re.S)
        ident = re.search(r'<span style="font-size:12px">\s*([^<]+?)\s*</span>', body)
        if not a or not ident:
            continue
        odb = re.search(r'<span class="specializacny_odbor">\(([^)]*)\)</span>', body)
        tds = re.findall(r"<td(?:\s[^>]*)?>(.*?)</td>", body, re.S)
        addr = ""
        for td in tds[2:]:
            t = txt(td)
            if re.search(r"\d{3}\s?\d{2}\s+\S", t):
                addr = t
                break
        hours = ""
        hh = re.search(r'<td style="white-space:nowrap;">(.*?)</td>', body, re.S)
        if hh:
            hours = ", ".join(x for x in (txt(p) for p in re.split(r"<br\s*/?>", hh.group(1))) if x)
        absn = re.findall(r"<strong>od (\d{2}\.\d{2}\.\d{4})</strong>\s*<strong>do (\d{2}\.\d{2}\.\d{4})</strong>", body)
        icon = re.search(r'<img class="icon"[^>]*alt="([^"]*)"', body)
        out.append({"u": u.strip(), "n": txt(a.group(1)), "id": ident.group(1).strip(), "o": txt(odb.group(1)) if odb else "",
                    "a": addr, "h": hours, "abs": absn, "druh": icon.group(1) if icon else ""})
    return out


def detail(url):
    h = get(url)
    m = re.search(r"maps\.google\.com/\?q=(4[789]\.\d+),(1[6-9]\.\d+|2[0-2]\.\d+)", h)
    return [round(float(m.group(1)), 5), round(float(m.group(2)), 5)] if m else None


def iso(d):
    return f"{d[6:10]}-{d[3:5]}-{d[0:2]}"


def city_of(addr):
    m = re.search(r"\d{3}\s?\d{2}\s+(.+)$", addr)
    return m.group(1).strip() if m else ""


def pid(u):
    m = re.search(r"page_id=(\d+)", u)
    return m.group(1) if m else u


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    gps = json.loads(GPS.read_text(encoding="utf-8")) if GPS.exists() else {}
    today = dt.date.today().isoformat()
    amb, aps, done = [], [], []
    for kraj, (amb_id, aps_id) in KRAJE.items():
        if ONLY and kraj not in ONLY:
            continue
        ka, kp = [], []
        for u, _ in okresy(kraj, "aps", aps_id):
            kp += rows(u)
        for u, _ in okresy(kraj, "amb", amb_id):
            ka += rows(u)
        print(f"{kraj}: {len(ka)} ambulancií, {len(kp)} pohotovostí")
        if len(ka) < 200:
            print(f"  {kraj}: podozrivo málo ambulancií, ponechávam uložené")
            continue
        for x in ka + kp:
            x["k"] = kraj
        amb += ka
        aps += kp
        done.append(kraj)
    # deduplikácia (to isté zariadenie býva vo viacerých okresoch)
    seen, A, P = set(), [], []
    for lst, dst in ((aps, P), (amb, A)):
        for x in lst:
            x["p"] = pid(x["u"])
            if x["p"] in seen:
                continue
            seen.add(x["p"])
            dst.append(x)
    # súradnice z detailov: najprv pohotovosti, potom ambulancie
    todo = [x for x in P + A if x["p"] not in gps]
    print(f"bez súradníc {len(todo)}, sťahujem najviac {MAX}")
    t0 = time.time()
    for k, x in enumerate(todo[:MAX]):
        gps[x["p"]] = detail(x["u"]) or 0
        if k % 500 == 499:
            GPS.write_text(json.dumps(gps, separators=(",", ":")), encoding="utf-8")
            print(f"  {k + 1} detailov, {time.time() - t0:.0f} s")
    if done and not ONLY:
        live = {x["p"] for x in P + A}
        gps = {k: v for k, v in gps.items() if k in live}
    GPS.write_text(json.dumps(gps, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    odbory = sorted({x["o"] for x in A if x["o"]} | set(old.get("odbory", [])), key=lambda s: s.lower())
    oi = {o: i for i, o in enumerate(odbory)}

    def absence(x):
        for od, do in x["abs"]:
            if iso(do) >= today:
                return [iso(od), iso(do)]
        return 0
    # riadok: [lat, lon, názov, adresa, index odbornosti, neprítomnosť [od, do] alebo 0, kraj, page_id]
    lekari = [[*gps[x["p"]], x["n"], x["a"], oi.get(x["o"], -1), absence(x), x["k"], int(x["p"])] for x in A if gps.get(x["p"])]
    # riadok: [lat, lon, názov, adresa, ordinačný čas, druh, kraj, page_id]
    pohot = [[*gps[x["p"]], x["n"], x["a"], x["h"], x["druh"], x["k"], int(x["p"])] for x in P if gps.get(x["p"])]
    # kraje, ktoré sa tentoraz nepodarilo stiahnuť, ponecháme z minula
    lekari += [r for r in old.get("lekari", []) if r[6] not in done and (not ONLY or r[6] not in ONLY)]
    pohot += [r for r in old.get("pohotovosti", []) if r[6] not in done and (not ONLY or r[6] not in ONLY)]
    if old.get("odbory") and odbory != old["odbory"]:
        remap = {i: oi.get(o, -1) for i, o in enumerate(old["odbory"])}
        for r in lekari:
            if r[6] not in done:
                r[4] = remap.get(r[4], -1)
    cnt = dict(old.get("pocet", {}))
    for k in done:
        cnt[k] = [sum(1 for x in A if x["k"] == k), sum(1 for x in P if x["k"] == k)]
    res = {"datum": today, "zdroj": "registre zdravotníckych zariadení samosprávnych krajov (e-VÚC)",
           "chyba": "Košický kraj", "odbory": odbory, "pocet": cnt, "lekari": lekari, "pohotovosti": pohot}
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"lekari.json: {len(lekari)} ambulancií a {len(pohot)} pohotovostí so súradnicami "
          f"(v registroch {sum(v[0] for v in cnt.values())} a {sum(v[1] for v in cnt.values())}), "
          f"{len(odbory)} odborností, {n_req} požiadaviek")


if __name__ == "__main__":
    main()
