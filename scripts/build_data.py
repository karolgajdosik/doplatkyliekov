"""Stiahne Zoznam kategorizovaných liekov MZ SR s prílohami a dáta ŠÚKL o výpadkoch
a pripraví z nich dáta pre web doplatkyliekov.sk.

Výstupy:
  site/data.json            ľahké dáta pre vyhľadávač na hlavnej stránke
  data/full.json            všetky údaje o liekoch platných v aktuálnom mesiaci
  data/ref.json             číselníky: ATC skupiny, výrobcovia, štáty, odbornosti lekárov, indikačné obmedzenia
  data/next.json            ceny zo zoznamu na budúci mesiac (ak už je zverejnený)
  data/history/RRRR-MM.json ceny za jednotlivé mesiace (spätne doplní chýbajúce)
  data/vypadky.json         stav dodávok podľa hlásení ŠÚKL

Použitie:
  python scripts/build_data.py                     # stiahne všetko z internetu
  python scripts/build_data.py --raw cesta/k/raw   # použije lokálne stiahnuté súbory (priečinky RRRRMM)
"""
import csv
import datetime as dt
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data.json"
DATA = ROOT / "data"
HISTORY = DATA / "history"
BASE = "https://www.health.gov.sk/Zdroje?/Sources/kategorizacia/zkl/"
SUKL_CSV = "https://portal.sukl.sk/PreruseniePublic/?act=PrerusenieOznList&export=csv"
MIN_ITEMS = 1000      # ochrana pred poškodeným súborom
HISTORY_MONTHS = 24   # koľko mesiacov histórie udržiavať

UA = {"User-Agent": "doplatkyliekov.sk data updater"}
RAW_DIR = None


# ---------- sťahovanie ----------

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


def get_file(y, m, name):
    """Vráti obsah prílohy zoznamu za daný mesiac alebo None, ak neexistuje."""
    folder = f"{y}{m:02d}"
    if RAW_DIR:
        p = RAW_DIR / folder / name
        return p.read_bytes() if p.exists() else None
    url = BASE + f"{folder}/{name}"
    try:
        data = fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"  nedostupné: {folder}/{name} ({e})")
        return None
    if data[:2] != b"PK":  # xlsx aj docx sú zip
        print(f"  nie je xlsx/docx: {folder}/{name}")
        return None
    return data


def part_a(y, m):
    return get_file(y, m, f"cast_A_zoznam_liekov_N_k_01_{m:02d}_{y}.xlsx")


def shift(y, m, delta):
    mm = m + delta
    return y + (mm - 1) // 12, (mm - 1) % 12 + 1


def label(y, m):
    return f"1. {m}. {y}"


# ---------- spracovanie ----------

def num(x):
    if isinstance(x, (int, float)):
        return round(float(x), 2)
    if isinstance(x, str):
        try:
            return round(float(x.replace(",", ".").replace(" ", "").replace("%", "")), 2)
        except ValueError:
            return None
    return None


def txt(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x).replace("\xa0", " ")).strip()


def rows_of(xlsx_bytes, sheet=0):
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True)
    ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
    return ws.iter_rows(values_only=True)


class BadFile(Exception):
    pass


def parse_part_a(xlsx_bytes, full=True):
    rows = rows_of(xlsx_bytes)
    h1, h2 = next(rows), next(rows)
    head = [(a or b or "") for a, b in zip(h1, h2)]
    need = {"Názov": 5, "Doplnok": 6, "Konečná c.": 10, "ÚZP": 11, "DOP": 13, "Typ lieku": 4,
            "PDOP Limit": 16, "PO": 17, "Kód IO": 22}
    for name, idx in need.items():
        if idx >= len(head) or head[idx] != name:
            sys.exit(f"Zmenila sa štruktúra súboru: na pozícii {idx} čakám stĺpec {name}, je tam {head[idx:idx+1]}.")

    groups, cur = [], None
    for r in rows:
        if not r or len(r) < 27:
            continue
        # riadok skupiny: ATC kód, bez ceny a typu lieku (stĺpec OL/PL môže byť vyplnený, napr. "§" pri morfíne)
        if r[0] and r[5] and r[10] is None and r[4] is None and re.fullmatch(r"[A-Z]\d\d[A-Z0-9]*", txt(r[0])):
            cur = {"a": txt(r[0]), "s": txt(r[5]), "f": txt(r[6]), "i": []}
            groups.append(cur)
        elif cur is not None and r[5]:
            item = {"kod": txt(r[0]), "name": txt(r[5]), "pack": txt(r[6]),
                    "konc": num(r[10]), "uzp": num(r[11]), "dop": num(r[13]), "typ": txt(r[4])}
            if full:
                item.update({
                    "gp": txt(r[1]) == "X",           # predpisuje sa názvom liečiva
                    "zwy": txt(r[2]),                 # Z = zmluva MEA, W, Y = NOAK
                    "olpl": txt(r[3]),                # omamná/psychotropná látka (modrý pruh)
                    "drz": txt(r[7]),                 # skratka držiteľa registrácie
                    "stat": txt(r[8]),
                    "sdl": num(r[9]),                 # počet štandardných dávok v balení
                    "su": txt(r[12]),                 # spôsob úhrady
                    "pdop": num(r[16]),               # doplatok za najlacnejší náhradný liek (ochranný limit)
                    "po": [p.strip() for p in txt(r[17]).split(",") if p.strip()],
                    "io": txt(r[18]),                 # "ind.obm." / "ind.obm.,ZP"
                    "podm": txt(r[19]), "docas": txt(r[20]),
                })
            cur["i"].append(item)
    groups = [g for g in groups if g["i"]]
    n = sum(len(g["i"]) for g in groups)
    if n < MIN_ITEMS:
        raise BadFile(f"Príliš málo liekov ({n}), súbor je asi poškodený.")
    return groups, n


def prices_map(groups):
    return {it["kod"]: [it["konc"], it["uzp"], it["dop"]] for g in groups for it in g["i"]}


def parse_atc(xlsx_bytes):
    out = {}
    for r in rows_of(xlsx_bytes):
        code, name = txt(r[0]) if r else "", txt(r[1]) if r and len(r) > 1 else ""
        if re.fullmatch(r"[A-Z](\d\d)?([A-Z]{1,2})?(\d\d)?", code) and name:
            out[code] = name
    return out


def parse_pairs(xlsx_bytes):
    out = {}
    for r in rows_of(xlsx_bytes):
        if not r or len(r) < 2:
            continue
        k, v = txt(r[0]), txt(r[1])
        if k and v and k.lower() not in ("skratka",) and not k.startswith("Časť"):
            out[k] = v
    return out


def parse_docx_table(docx_bytes):
    """Vytiahne riadky tabuliek z .docx bez ďalších knižníc."""
    xml = zipfile.ZipFile(io.BytesIO(docx_bytes)).read("word/document.xml").decode("utf-8")
    rows = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", xml, re.S):
        cells = []
        for tc in re.findall(r"<w:tc[ >].*?</w:tc>", tr, re.S):
            paras = re.findall(r"<w:p[ >].*?</w:p>", tc, re.S) or [tc]
            text = " ".join("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in paras)
            cells.append(txt(text))
        rows.append(cells)
    return rows


def parse_odbornosti(docx_bytes):
    out = {}
    for cells in parse_docx_table(docx_bytes):
        if len(cells) >= 2 and re.fullmatch(r"[A-Z]{2,4}", cells[0] or ""):
            name = cells[1]
            name = re.sub(r"^lekár,? ktorý poskytuje zdravotnú starostlivosť\s*(v|vo)\s*", "", name)
            name = re.sub(r"^(sub)?špecializačnom odbore\s*", "", name)
            name = name.replace(" alebo v subšpecializačnom odbore ", " / ").replace(" alebo v špecializačnom odbore ", " / ")
            out[cells[0]] = name
    return out


def parse_io(xlsx_bytes):
    """Indikačné obmedzenia po produktoch: {kód IO: text} a {kód ŠÚKL: [kódy IO]}."""
    texts, by_kod = {}, {}
    rows = rows_of(xlsx_bytes, "Sumár_IO")
    head = [txt(c) for c in next(rows)]
    ci = {h: i for i, h in enumerate(head)}
    for r in rows:
        if not r:
            continue
        code, kod, text = txt(r[ci["Kód IO"]]), txt(r[ci["ŠÚKL"]]), str(r[ci["Znenie IO"]] or "").strip()
        if not code or not kod:
            continue
        texts.setdefault(code, re.sub(r"[ \t\xa0]+", " ", text))
        by_kod.setdefault(kod, [])
        if code not in by_kod[kod]:
            by_kod[kod].append(code)
    return texts, by_kod


def parse_vypadky(csv_bytes, today):
    """Posledný platný stav dodávok pre každý kód ŠÚKL podľa hlásení držiteľov."""
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    notices = {}
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        kod = (row.get("Kód") or "").strip()
        eff = (row.get("Účinnosť") or "").strip()[:10]
        typ = (row.get("Predmet") or "").strip()
        sub = (row.get("Podanie") or "").strip()
        if kod and eff and typ:
            notices.setdefault(kod, []).append((eff, sub, typ))
    out = {}
    iso = today.isoformat()
    for kod, ns in notices.items():
        ns.sort()
        past = [n for n in ns if n[0] <= iso]
        future = [n for n in ns if n[0] > iso]
        cur = past[-1] if past else None
        state = {}
        if cur and cur[2] in ("R", "Z"):
            state = {"stav": cur[2], "od": cur[0]}
        nxt = next((n for n in future if n[2] in ("R", "Z")), None)
        if nxt and not state:
            state = {"stav": "P" + nxt[2], "od": nxt[0]}   # ohlásené do budúcna
        if state:
            out[kod] = state
    return out


# ---------- hlavný beh ----------

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    global RAW_DIR
    args = sys.argv[1:]
    today = dt.date.today()
    if "--raw" in args:
        RAW_DIR = Path(args[args.index("--raw") + 1])
    if "--today" in args:
        today = dt.date.fromisoformat(args[args.index("--today") + 1])

    # aktuálny zoznam (platný v tomto mesiaci, inak posledný dostupný)
    cur = None
    for delta in (0, -1, -2):
        y, m = shift(today.year, today.month, delta)
        print(f"Zoznam {m}/{y}")
        data = part_a(y, m)
        if data:
            cur = (y, m, data)
            break
    if not cur:
        sys.exit("Nepodarilo sa stiahnuť žiadny zoznam.")
    y, m, data = cur
    groups, n = parse_part_a(data)
    iso = f"{y}-{m:02d}-01"
    print(f"Aktuálny zoznam od {label(y, m)}: {len(groups)} skupín, {n} balení")

    # číselníky
    ref = {"atc": {}, "drz": {}, "staty": {}, "odbornosti": {}, "io": {}, "io_kod": {}}
    for name, key, fn in [("cast_E_kody_ATC.xlsx", "atc", parse_atc),
                          ("cast_G_skr_vyrob.xlsx", "drz", parse_pairs),
                          ("cast_F_staty_vyrob.xlsx", "staty", parse_pairs),
                          ("cast_H_skr_lek.docx", "odbornosti", parse_odbornosti)]:
        b = get_file(y, m, name)
        if b:
            try:
                ref[key] = fn(b)
            except Exception as e:  # noqa: BLE001
                print(f"  chyba pri spracovaní {name}: {e}")
        print(f"  {name}: {len(ref[key])} položiek")
    b = get_file(y, m, f"zoznam_IO_po_produktoch_k_01_{m:02d}_{y}.xlsx")
    if b:
        ref["io"], ref["io_kod"] = parse_io(b)
    print(f"  indikačné obmedzenia: {len(ref['io'])} textov, {len(ref['io_kod'])} liekov")

    # výstupy pre aktuálny mesiac
    lean = [{"a": g["a"], "s": g["s"], "f": g["f"],
             "i": [[it["kod"], it["name"], it["pack"], it["konc"], it["uzp"], it["dop"], it["typ"]] for it in g["i"]]}
            for g in groups]
    write_json(SITE_DATA, {"platnost": label(y, m), "platnostIso": iso, "groups": lean})
    write_json(DATA / "full.json", {"platnost": label(y, m), "platnostIso": iso, "groups": groups})
    write_json(DATA / "ref.json", ref)
    write_json(HISTORY / f"{y}-{m:02d}.json", prices_map(groups))

    # budúci mesiac
    ny, nm = shift(y, m, 1)
    nb = part_a(ny, nm)
    try:
        ng = parse_part_a(nb, full=False)[0] if nb else None
    except BadFile as e:
        print(f"Budúci zoznam {nm}/{ny} sa nedá spracovať ({e}), ponechávam predošlý")
        nb = ng = None
        if (DATA / "next.json").exists():
            nb = True
    if ng:
        write_json(DATA / "next.json", {"platnost": label(ny, nm), "platnostIso": f"{ny}-{nm:02d}-01",
                                        "prices": prices_map(ng)})
        print(f"Budúci zoznam od {label(ny, nm)} spracovaný")
    elif not nb:
        (DATA / "next.json").unlink(missing_ok=True)
        print("Budúci zoznam ešte nie je zverejnený")

    # história: doplní chýbajúce mesiace, staršie odstráni
    # mesiace, ktorých súbor na webe MZ SR je poškodený, sa zapíšu do history_skip.json a viac sa nesťahujú
    skip_path = DATA / "history_skip.json"
    skip = set(json.loads(skip_path.read_text(encoding="utf-8"))) if skip_path.exists() else set()
    keep = set()
    for d in range(0, HISTORY_MONTHS):
        hy, hm = shift(y, m, -d)
        key = f"{hy}-{hm:02d}"
        keep.add(f"{key}.json")
        p = HISTORY / f"{key}.json"
        if p.exists() or key in skip:
            continue
        try:
            hb = part_a(hy, hm)
            if hb:
                hg, _ = parse_part_a(hb, full=False)
                write_json(p, prices_map(hg))
                print(f"  história {hm}/{hy} doplnená")
        except Exception as e:  # noqa: BLE001 – história nie je kritická
            print(f"  história {hm}/{hy} preskočená: {e}")
            skip.add(key)
    oldest = "{}-{:02d}".format(*shift(y, m, -(HISTORY_MONTHS - 1)))
    skip = sorted(k for k in skip if k >= oldest)
    if skip:
        write_json(skip_path, skip)
    else:
        skip_path.unlink(missing_ok=True)
    for p in HISTORY.glob("*.json"):
        if p.name not in keep:
            p.unlink()

    # výpadky ŠÚKL
    try:
        if RAW_DIR and (RAW_DIR / "sukl" / "prerusenia.csv").exists():
            vb = (RAW_DIR / "sukl" / "prerusenia.csv").read_bytes()
        else:
            vb = fetch(SUKL_CSV, attempts=6)
        vyp = parse_vypadky(vb, today)
        prev = json.loads((DATA / "vypadky.json").read_text(encoding="utf-8")) if (DATA / "vypadky.json").exists() else {}
        if prev.get("lieky") != vyp:  # dátum meníme len pri zmene, aby nevznikali zbytočné commity
            write_json(DATA / "vypadky.json", {"datum": today.isoformat(), "lieky": vyp})
        print(f"Výpadky ŠÚKL: {len(vyp)} liekov s hláseným prerušením alebo ukončením")
    except Exception as e:  # noqa: BLE001
        print(f"Výpadky ŠÚKL sa nepodarilo načítať ({e}), ponechávam predchádzajúce")


if __name__ == "__main__":
    main()
