#!/usr/bin/env python3
"""Oznamy ŠÚKL: stiahnutia liekov z trhu a bezpečnostné oznamy držiteľov (DHPC) → data/sukl_oznamy.json.

Zoznamy sa sťahujú každý deň; detail oznamu o stiahnutí (kódy ŠÚKL, šarže, dôvod) len pri novom oznamu,
staré sa berú z uloženého súboru. Pri chybe siete zostane posledný uložený súbor.

Použitie:  python scripts/build_sukl.py            (sťahuje zo sukl.sk)
           python scripts/build_sukl.py --raw DIR  (lokálne HTML: sukl_list_0.html, sukl_list_1.html, detaily podľa slugu)
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sukl_oznamy.json"
S = "https://www.sukl.sk"
LISTS = {
    "stiahnutia": "/pre-odbornikov-a-firmy/dostupnost-a-kvalita-liekov/kvalita-liekov/oznamy-o-stiahnuti-liekov",
    "dhpc": "/pre-odbornikov-a-firmy/bezpecnost-liekov/oznamy-drzitelov-dhpc",
}
UA = {"User-Agent": "doplatkyliekov.sk data updater"}
RAW = None


def get(url):
    if RAW:
        name = url.rstrip("/").split("/")[-1]
        for cand in (RAW / f"{name}.html", RAW / name):
            if cand.exists():
                return cand.read_text(encoding="utf-8", errors="replace")
        return None
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
            time.sleep(3)
    return None


def text_of(h):
    i = h.find("<main")
    h = h[i:] if i > 0 else h
    for stop in ('Vytlačiť túto stránku', 'class="govuk-footer', "<footer"):
        j = h.find(stop)
        if j > 0:
            h = h[:j]
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    h = re.sub(r"<(br|/p|/li|/tr|/h\d|/div)[^>]*>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def parse_list(h, path):
    """Karty zo zoznamu: [{id, url, title, date}]."""
    out, seen = [], set()
    pat = re.compile(r'<a href="(' + re.escape(S + path) + r'/([^"#?/]+))"[^>]*>(.*?)</a>(.*?)(?=<a href="'
                     + re.escape(S + path) + r'/|$)', re.S)
    for m in pat.finditer(h):
        url, slug, title, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        if slug in seen:
            continue
        seen.add(slug)
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", title))).strip()
        d = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})"', rest[:4000])
        out.append({"id": slug, "url": url, "title": title, "date": d.group(1) if d else ""})
    return out


def parse_recall(h):
    t = text_of(h)
    d = re.search(r"Zverejnené:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    trieda = re.search(r"\b(I{1,3})\.\s*trieda urgentnosti", t)
    kody = []
    for k in re.findall(r"kód\s*ŠÚKL\s*:?\s*([0-9A-Z]{5})\b", t, re.I):
        if k not in kody:
            kody.append(k)
    sarze = []
    for s in re.findall(r"(?:č\.|číslo|čísla)\s*šarž[eí]\s*:?\s*([0-9A-Za-z][0-9A-Za-z/\-]*(?:\s*,\s*[0-9A-Za-z][0-9A-Za-z/\-]*)*)", t, re.I):
        for x in re.split(r"\s*,\s*", s):
            if x and x not in sarze and len(x) <= 20 and re.search(r"\d", x):
                sarze.append(x)
    vsetky = bool(re.search(r"všetk\w+ šarž", t, re.I))
    dovod = ""
    m = re.search(r"(Dôvod\w*[^.\n]{0,40}(?:je|sú|bol\w*)\s[^.\n]{5,260}\.)", t)
    if m:
        dovod = re.sub(r"\s+", " ", m.group(1)).strip()
    return {
        "date": f"{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}" if d else "",
        "trieda": trieda.group(1) if trieda else "",
        "kody": kody, "sarze": sarze[:30], "vsetky": vsetky, "dovod": dovod[:300],
    }


def main():
    global RAW
    if "--raw" in sys.argv:
        RAW = Path(sys.argv[sys.argv.index("--raw") + 1])
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    old_rec = {r["id"]: r for r in old.get("stiahnutia", [])}
    result = dict(old)
    ok = False
    for key, path in LISTS.items():
        h = get(S + path) if not RAW else (RAW / f"sukl_list_{0 if key == 'stiahnutia' else 1}.html").read_text(encoding="utf-8", errors="replace")
        if not h:
            print(f"{key}: zoznam nedostupný, ponechávam uložené údaje")
            continue
        items = parse_list(h, path)
        if len(items) < 5:
            print(f"{key}: podozrivo málo položiek ({len(items)}), ponechávam uložené údaje")
            continue
        if key == "stiahnutia":
            new = 0
            for it in items:
                prev = old_rec.get(it["id"])
                if prev and prev.get("detail"):
                    it.update({k: prev[k] for k in ("trieda", "kody", "sarze", "vsetky", "dovod") if k in prev})
                    it["detail"] = True
                    continue
                dh = get(it["url"])
                if dh:
                    det = parse_recall(dh)
                    it["date"] = it["date"] or det.pop("date")
                    det.pop("date", None)
                    it.update(det)
                    it["detail"] = True
                    new += 1
                    if not RAW:
                        time.sleep(0.7)
            print(f"stiahnutia: {len(items)} oznamov, {new} nových detailov, "
                  f"{sum(1 for i in items if i.get('kody'))} s kódom ŠÚKL")
        else:
            print(f"dhpc: {len(items)} oznamov")
        items.sort(key=lambda x: x.get("date", ""), reverse=True)
        result[key] = items
        ok = True
    if ok:
        result["stiahnute"] = time.strftime("%Y-%m-%d")
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"Uložené: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
