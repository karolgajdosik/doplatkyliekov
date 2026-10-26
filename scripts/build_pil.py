"""Príbalové letáky (PIL) z úložiska ŠÚKL → data/pil/*.json.gz a data/pil_map.json.

Beží v GitHub Actions (mesačne): stiahne spc_pil_aktualny.zip (~3,6 GB), vyberie písomné informácie pre používateľa,
vytiahne text (pdftotext, catdoc, docx), priradí ich k liekom zo zoznamu podľa názvu a sily
a uloží hlavné časti letáka (na čo sa používa, pred užitím, ako užívať, vedľajšie účinky, uchovávanie).
  python3 scripts/build_pil.py PIL.zip
"""
import gzip
import json
import re
import subprocess
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTDIR = DATA / "pil"
SHARDS = 64
LIMITS = [1500, 2600, 2200, 2600, 700]
HEAD_RE = [
    r"1\.\s*Čo je .{0,200}?(?:a )?na čo sa (?:používa|používajú)",
    r"2\.\s*Čo potrebujete vedieť",
    r"3\.\s*Ako (?:užívať|používať|užiť|použiť|sa podáva|vám bude|aplikovať|inhalovať)",
    r"4\.\s*Možné vedľajšie účinky",
    r"5\.\s*Ako uchovávať",
    r"6\.\s*Obsah balenia",
]


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def text_of(name, raw, tmp):
    low = name.lower()
    try:
        if low.endswith(".pdf"):
            tmp.write_bytes(raw)
            return subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(tmp), "-"], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
        if low.endswith(".docx"):
            import io
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml)
        if low.endswith(".doc"):
            tmp.write_bytes(raw)
            return subprocess.run(["catdoc", "-d", "utf-8", str(tmp)], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    return ""


def clean(t):
    t = t.replace("\r", "").replace("\f", "\n")
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()


def title_of(t):
    m = re.search(r"Písomná informácia pre (?:používateľa|použ[ií]vateľa|pacienta)\s*(.{3,300}?)(?:\n\s*\n|Pozorne si prečítajte)", t, re.S | re.I)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:250]


def sections(t):
    pos = []
    for i, h in enumerate(HEAD_RE):
        # nadpis v obsahu na začiatku letáka preskočíme: hľadáme posledný výskyt pred ďalším nadpisom
        ms = list(re.finditer(h, t, re.I | re.S))
        pos.append(ms[1].start() if len(ms) > 1 else (ms[0].start() if ms else -1))
    out = []
    for i in range(5):
        a = pos[i]
        if a < 0:
            out.append("")
            continue
        nxt = [p for p in pos[i + 1:] if p > a]
        b = min(nxt) if nxt else a + LIMITS[i]
        s = re.sub(r"\s+", " ", t[a:b]).strip()
        out.append(s[:LIMITS[i]])
    return out


def products():
    full = json.loads((DATA / "full.json").read_text(encoding="utf-8"))
    by_brand = defaultdict(list)
    for g in full["groups"]:
        for it in g["i"]:
            words = re.findall(r"[a-z0-9]+", norm(it["name"]))
            if not words:
                continue
            nums = set(re.findall(r"\d+(?:[.,]\d+)?", it["name"]))
            by_brand[words[0]].append((it["kod"], norm(it["name"]), {n.replace(",", ".") for n in nums}))
    return by_brand


def main():
    src = Path(sys.argv[1])
    by_brand = products()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/pil_one")
    shards = defaultdict(dict)
    best = {}  # kód → (skóre, pil_id)
    n_all = n_title = 0
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            name = info.filename
            base = name.rsplit("/", 1)[-1]
            m = re.match(r"PIL(\d+)\.(pdf|docx?|PDF|DOCX?)$", base)
            if not m or info.file_size > 25_000_000:
                continue
            n_all += 1
            t = clean(text_of(base, z.read(info), tmp))
            title = title_of(t)
            if not title:
                continue
            n_title += 1
            nt = norm(title)
            words = re.findall(r"[a-z0-9]+", nt)
            if not words:
                continue
            cands = by_brand.get(words[0], [])
            if not cands:
                continue
            tnums = {x.replace(",", ".") for x in re.findall(r"\d+(?:[.,]\d+)?", title)}
            pid = m.group(1)
            matched = False
            for kod, pname, nums in cands:
                pw = re.findall(r"[a-z0-9]+", pname)
                brand2 = " ".join(w for w in pw[:2] if not w[0].isdigit())
                if brand2 and brand2 not in nt:
                    continue
                if nums and not nums <= tnums:
                    continue
                score = len(nums & tnums) * 2 + (1 if brand2 in nt else 0)
                if kod not in best or score > best[kod][0]:
                    best[kod] = (score, pid)
                matched = True
            if matched:
                shards[int(pid) % SHARDS][pid] = {"t": title, "s": sections(t)}
    used = {pid for _, pid in best.values()}
    for n in range(SHARDS):
        docs = {k: v for k, v in shards.get(n, {}).items() if k in used}
        (OUTDIR / f"{n}.json.gz").write_bytes(gzip.compress(json.dumps(docs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))
    (DATA / "pil_map.json").write_text(json.dumps({k: v[1] for k, v in sorted(best.items())}, separators=(",", ":")), encoding="utf-8")
    print(f"Letáky: {n_all} súborov, s názvom {n_title}, priradené k {len(best)} liekom ({len(used)} letákov)")


if __name__ == "__main__":
    main()
