#!/usr/bin/env python3
"""Kúpele a indikácie, ktoré liečia (MZ SR, Inšpektorát kúpeľov a žriediel) → data/kupele.json.

Zdroj: health.gov.sk/ministerstvo/kupele-a-zriedla/povolenie-na-prevadzkovanie-prirodnych-liecebnych-kupelov-a-kupelnych-liecebni/
súbor „Indikácie prírodných liečebných kúpeľov a kúpeľných liečební v SR“ (RTF, tabuľka č. 2: skupina indikácií →
prevádzkovatelia, s poznámkou o obmedzení). Skupiny I.–XII. sú pre dospelých, XXI.–XXX. pre deti a dorast.
Spúšťa sa mesačne (mesacne.yml); potrebuje balík striprtf.

  python3 scripts/build_kupele.py               (sťahuje)
  python3 scripts/build_kupele.py --raw SUBOR   (lokálny RTF)
"""
import datetime as dt
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "kupele.json"
PAGE = "https://www.health.gov.sk/ministerstvo/kupele-a-zriedla/povolenie-na-prevadzkovanie-prirodnych-liecebnych-kupelov-a-kupelnych-liecebni/"
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
ROMAN = re.compile(r"^(X{0,3}(?:IX|IV|V?I{0,3}))\.$")


def get(url, binary=False):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                d = r.read()
                return d if binary else d.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
            time.sleep(5)
    return None


def key(name):
    s = unicodedata.normalize("NFD", name.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\b(a\.? ?s|s\.? ?r\.? ?o|n\.? ?o|s\.? ?p|spol)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def place_of(name):
    parts = [p.strip() for p in name.split(",") if p.strip()]
    last = parts[-1] if len(parts) > 1 else ""
    if not last or re.fullmatch(r"(a\.\s?s|s\.\s?r\.\s?o|n\.\s?o|š\.\s?p)\.?", last):
        m = re.search(r"(?:s\.r\.o\.|a\.s\.|n\. ?o\.)\s*-?\s*(.+)$", name)
        last = m.group(1) if m else ""
    return re.sub(r"^(?:s\.r\.o\.|a\.s\.|-|klimatické kúpele)\s*", "", last).strip()


def parse(rtf_text):
    from striprtf.striprtf import rtf_to_text
    t = rtf_to_text(rtf_text, errors="ignore")
    lines, buf = [], ""
    for raw in t.splitlines():
        line = raw.strip()
        if not line:
            continue
        if buf and not line.startswith("|") and not re.match(r"^[IVX]+\.\|", line):
            buf += " " + line
        else:
            if buf:
                lines.append(buf)
            buf = line
    if buf:
        lines.append(buf)
    groups, kupele, cur = [], {}, None
    for line in lines:
        cells = [re.sub(r"\s+", " ", c).strip() for c in line.split("|")]
        if len(cells) > 1 and ROMAN.match(cells[0] or "-") and cells[1]:
            num = cells[0][:-1]
            deti = len(num) >= 3 and num.startswith("XX")
            cur = {"c": num, "n": cells[1][0].upper() + cells[1][1:].lower(), "deti": deti, "k": []}
            groups.append(cur)
            continue
        if not cur or len(cells) < 4 or not re.match(r"^\d+\.$", cells[2] or ""):
            continue
        note = cells[1]
        plk, kl = cells[3], (cells[4] if len(cells) > 4 else "")
        name, typ = (plk, "PLK") if plk else (kl, "KL")
        if not name:
            continue
        m = re.search(r"\s*\(([^)]*)\)\s*$", name)
        if m:
            name = name[:m.start()].strip()
            note = (note + "; " if note else "") + m.group(1)
        k = key(name)
        # ten istý prevádzkovateľ býva zapísaný s obcou aj bez nej: kratší kľúč je predponou dlhšieho
        hit = next((kk for kk in kupele if kk.startswith(k + " ") or k.startswith(kk + " ") or kk == k), None)
        if hit is None:
            kupele[k] = {"id": len(kupele), "n": name, "m": place_of(name), "t": typ}
            hit = k
        elif len(name) > len(kupele[hit]["n"]) and place_of(name):
            kupele[hit].update(n=name, m=place_of(name))
        prev = next((e for e in cur["k"] if e[0] == kupele[hit]["id"]), None)
        if prev is None:
            cur["k"].append([kupele[hit]["id"], note])
        elif note and note not in prev[1]:
            prev[1] = (prev[1] + "; " if prev[1] else "") + note
    n_rows = sum(len(g["k"]) for g in groups)
    if len(groups) < 15 or n_rows < 100:
        raise RuntimeError(f"podozrivo málo údajov: {len(groups)} skupín, {n_rows} riadkov")
    return {"datum": dt.date.today().isoformat(), "zdroj": PAGE, "skupiny": groups,
            "kupele": sorted(kupele.values(), key=lambda x: x["id"])}


def main():
    if "--raw" in sys.argv:
        rtf = Path(sys.argv[sys.argv.index("--raw") + 1]).read_bytes().decode("latin-1")
    else:
        page = get(PAGE) or ""
        m = re.search(r'href="(https://cloud\.health\.gov\.sk/s/[A-Za-z0-9]+/download)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*Indikácie prírodných', page)
        if not m:
            return print("Zoznam kúpeľov nedostupný, ponechávam uložené údaje")
        blob = get(m.group(1), binary=True)
        if not blob or not blob.startswith(b"{\\rtf"):
            return print("Súbor s indikáciami kúpeľov sa nepodarilo stiahnuť")
        rtf = blob.decode("latin-1")
    res = parse(rtf)
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"kupele.json: {len(res['kupele'])} kúpeľov, {len(res['skupiny'])} skupín indikácií")


if __name__ == "__main__":
    main()
