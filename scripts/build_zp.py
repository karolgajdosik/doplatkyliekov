#!/usr/bin/env python3
"""Zoznam kategorizovaných zdravotníckych pomôcok MZ SR (vychádza štvrťročne) → data/zp.json.

Stránka zoznamov: health.gov.sk/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-zdravotnickych-pomocok/
Každé obdobie má podstránku zkzp-RRRRMM s odkazmi na cloud.health.gov.sk:
  Časť 1 – xlsx so všetkými pomôckami (cena AKC, úhrada ÚZP, doplatok DOP, preskripčné obmedzenie),
  Časť 2 – docx s množstvovými limitmi a indikačnými obmedzeniami po podskupinách.
Ak už je zverejnený zoznam na budúci štvrťrok, uloží sa aj data/zp_next.json (kód → doplatok).

Použitie:  python scripts/build_zp.py
           python scripts/build_zp.py --raw DIR   (lokálne súbory zp1.xlsx/zp1, zp2.docx/zp2, voliteľne od=RRRRMM)
"""
import datetime as dt
import html
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
H = "https://www.health.gov.sk"
LIST = "/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-zdravotnickych-pomocok/"
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
MIN_ITEMS = 2000


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
    if v is None or v == "":
        return None
    try:
        return round(float(str(v).replace(",", ".")), 4)
    except ValueError:
        return None


def parse_xlsx(blob):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    ws = wb.active
    heads, groups = {}, {}
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i < 2 or len(r) < 16:
            continue
        r = list(r) + [None] * (20 - len(r))
        name = str(r[4]).strip() if r[4] is not None else ""
        if not r[3]:
            m = re.match(r"([A-Z]\d+(?:\.\d+)*)\s+(.*)", name)
            if m:
                hn = re.sub(r"\s+", " ", m.group(2)).strip()
                extra = re.sub(r"\s+", " ", str(r[5] or "")).strip()
                if extra and extra.lower() not in hn.lower():
                    hn += " " + extra
                if hn.isupper():
                    hn = hn[:1] + hn[1:].lower()
                heads[m.group(1)] = hn
            continue
        pod = str(r[1] or "").strip()
        if not pod:
            continue
        g = groups.setdefault(pod, [])
        g.append({
            "kod": str(r[3]).strip(), "n": re.sub(r"\s+", " ", name), "d": re.sub(r"\s+", " ", str(r[5] or "")).strip(),
            "v": str(r[6] or "").strip(), "st": str(r[7] or "").strip(), "mj": str(r[8] or "").strip(),
            "c": num(r[10]), "u": num(r[11]), "dop": num(r[12]), "su": str(r[15] or "").strip(),
            "pr": re.sub(r"\s+", " ", str(r[16] or "")).strip(), "z": bool(r[18]),
        })
    return heads, groups


def parse_limits(blob):
    """Časť 2 → ({podskupina: [riadky limitov]}, {písmeno: názov skupiny})."""
    x = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
    plain = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", x))).replace("\xa0", " ")
    letters = {}
    for m in re.finditer(r"Limit skupiny ([A-Z])\s*[–-]\s*([^\n]+)", plain):
        letters[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()

    def tx(s):
        paras = re.findall(r"<w:p[ >].*?</w:p>", s, re.S) or [s]
        return html.unescape(" ".join("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in paras)).replace("\xa0", " ").strip()

    limits, cur = {}, None
    code_re = re.compile(r"^([A-Z]\d+(?:\.\d+)*)\s")
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", x, re.S):
        cells = [re.sub(r"\s+", " ", tx(tc)).strip() for tc in re.findall(r"<w:tc[ >].*?</w:tc>", tr, re.S)]
        if not cells or re.search(r"podskupina|množstvový limit", " ".join(cells[:2]), re.I) and not code_re.match(cells[0] + " "):
            continue
        idx = None
        for j in (1, 0):
            if j < len(cells) and code_re.match(cells[j] + " "):
                idx = j
                break
        if idx is not None:
            cur = code_re.match(cells[idx] + " ").group(1)
            rest = cells[idx + 1:]
        else:
            rest = cells[1:] if len(cells) > 1 else cells
        if not cur:
            continue
        line = " – ".join(c for c in rest if c)
        if line:
            limits.setdefault(cur, [])
            if line not in limits[cur]:
                limits[cur].append(line[:400])
    return limits, letters


def build(blob1, blob2, od):
    heads, groups = parse_xlsx(blob1)
    limits, letters = parse_limits(blob2) if blob2 else ({}, {})
    n_items = sum(len(v) for v in groups.values())
    if n_items < MIN_ITEMS:
        raise RuntimeError(f"podozrivo málo pomôcok: {n_items}")
    out_groups = []
    for pod in sorted(groups, key=lambda c: [c[0]] + [int(x) for x in re.findall(r"\d+", c)]):
        chain, parts = [], pod.split(".")
        for k in range(1, len(parts) + 1):
            c = ".".join(parts[:k])
            if c in heads:
                chain.append([c, heads[c]])
        lim = None
        for k in range(len(parts), 0, -1):
            c = ".".join(parts[:k])
            if c in limits:
                lim = limits[c]
                break
        items = sorted(groups[pod], key=lambda x: (x["dop"] if x["dop"] is not None else 9e9, x["c"] or 0, x["n"]))
        out_groups.append({"k": pod, "name": heads.get(pod) or (chain[-1][1] if chain else pod), "chain": chain,
                           "lim": lim or [], "i": items})
    y, m = int(od[:4]), int(od[4:6])
    em = m + 2
    end = dt.date(y + (em > 12), (em - 1) % 12 + 1, 1)
    end = (dt.date(end.year + (end.month == 12), end.month % 12 + 1, 1) - dt.timedelta(days=1))
    return {"od": f"{y}-{m:02d}-01", "do": end.isoformat(), "skupiny": letters, "groups": out_groups,
            "pocet": n_items}


def find_periods(page):
    return sorted(set(re.findall(r"/zkzp-(\d{6})/", page)))


def part_links(page):
    """[(číslo časti, url)] z podstránky obdobia."""
    out = {}
    for m in re.finditer(r'href="(https://cloud\.health\.gov\.sk/s/[A-Za-z0-9]+/download)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*Časť\s*(\d)', page):
        out.setdefault(int(m.group(2)), m.group(1))
    if not out:  # záloha: odkazy v poradí, v akom sú na stránke
        for n, u in enumerate(dict.fromkeys(re.findall(r'href="(https://cloud\.health\.gov\.sk/s/[A-Za-z0-9]+/download)', page)), 1):
            out[n] = u
    return out


def main():
    if "--raw" in sys.argv:
        raw = Path(sys.argv[sys.argv.index("--raw") + 1])
        b1 = next((raw / n).read_bytes() for n in ("zp1.xlsx", "zp1", "Zoznam_ZP_202610.xlsx") if (raw / n).exists())
        b2 = next(((raw / n).read_bytes() for n in ("zp2.docx", "zp2") if (raw / n).exists()), None)
        od = next((a.split("=")[1] for a in sys.argv if a.startswith("od=")), "202610")
        res = build(b1, b2, od)
        (DATA / "zp.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"zp.json: {res['pocet']} pomôcok v {len(res['groups'])} podskupinách, limity pri "
              f"{sum(1 for g in res['groups'] if g['lim'])}")
        return
    page = fetch(H + LIST)
    if not page:
        print("Zoznam pomôcok nedostupný, ponechávam uložené údaje")
        return
    periods = find_periods(page)
    today = dt.date.today().strftime("%Y%m")
    cur = max((p for p in periods if p <= today), default=None)
    nxt = min((p for p in periods if p > today), default=None)
    if not cur:
        print("Nenašiel som aktuálne obdobie zoznamu pomôcok")
        return
    old = json.loads((DATA / "zp.json").read_text(encoding="utf-8")) if (DATA / "zp.json").exists() else {}
    for period, target in ((cur, "zp.json"), (nxt, "zp_next.json")):
        if not period:
            if target == "zp_next.json" and (DATA / target).exists():
                (DATA / target).unlink()
            continue
        sub = fetch(f"{H}{LIST}zkzp-{period}/")
        links = part_links(sub or "")
        if 1 not in links:
            print(f"zkzp-{period}: nenašiel som odkaz na časť 1")
            continue
        sig = links[1]
        if target == "zp.json" and old.get("zdroj") == sig and old.get("od", "").replace("-", "")[:6] == period:
            print(f"zkzp-{period}: bez zmeny")
            continue
        b1 = fetch(links[1], binary=True)
        b2 = fetch(links[2], binary=True) if 2 in links else None
        if not b1 or b1[:2] != b"PK":
            print(f"zkzp-{period}: časť 1 sa nepodarilo stiahnuť")
            continue
        if b2 and b2[:2] != b"PK":
            b2 = None
        try:
            res = build(b1, b2, period)
        except Exception as e:  # noqa: BLE001
            print(f"zkzp-{period}: chyba spracovania: {e}")
            continue
        res["zdroj"] = sig
        if target == "zp.json":
            (DATA / target).write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            prices = {x["kod"]: x["dop"] for g in res["groups"] for x in g["i"]}
            (DATA / target).write_text(json.dumps({"od": res["od"], "prices": prices}, ensure_ascii=False,
                                                  separators=(",", ":")), encoding="utf-8")
        print(f"{target}: obdobie {period}, {res['pocet']} pomôcok")


if __name__ == "__main__":
    main()
