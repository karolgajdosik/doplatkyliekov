#!/usr/bin/env python3
"""Pobočky zdravotných poisťovní (VšZP, Dôvera, Union) → data/pobocky.json.

Riadok: [lat, lon, názov, adresa, obec, otváracie hodiny vo formáte OSM, telefón, poisťovňa, odkaz na detail].
Zdroje sú zoznamy pobočiek na weboch poisťovní; hodiny z detailu pobočky. Ak niektorá poisťovňa zlyhá,
ponechajú sa jej uložené pobočky. Spúšťa sa mesačne (mesacne.yml).

  python3 scripts/build_pobocky.py
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "pobocky.json"
UA = {"User-Agent": "doplatkyliekov.sk (kontakt@doplatkyliekov.sk)"}
DAYS = [("pondelok", "Mo"), ("utorok", "Tu"), ("streda", "We"), ("štvrtok", "Th"), ("piatok", "Fr"), ("sobota", "Sa"), ("nedeľa", "Su")]
NAMES = {"vszp": "VšZP", "dovera": "Dôvera", "union": "Union"}


def get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  pokus {k + 1}: {url}: {e}")
            time.sleep(2 + 2 * k)
    return ""


def text_of(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", h, flags=re.S)
    h = re.sub(r"<(br|/p|/li|/tr|/h\d|/div|/dt|/dd|/span)[^>]*>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def hours_osm(segment):
    """Text s dňami a časmi („Pondelok 8.00 – 12.00 12.30 – 17.00 …“) → „Mo 08:00-12:00,12:30-17:00; …“."""
    low = segment.lower()
    pos = []
    for sk, en in DAYS:
        m = re.search(r"\b" + sk + r"\b", low)
        if m:
            pos.append((m.start(), en))
    if len(pos) < 3:
        return ""
    pos.sort()
    rules, seen = [], set()
    for i, (p, en) in enumerate(pos):
        if en in seen:
            continue
        seen.add(en)
        chunk = low[p:pos[i + 1][0] if i + 1 < len(pos) else p + 200]
        spans = re.findall(r"(\d{1,2})[.:](\d{2})\s*(?:[–-]|do)\s*(\d{1,2})[.:](\d{2})", chunk)
        if spans:
            rules.append(en + " " + ",".join(f"{int(a):02d}:{b}-{int(c):02d}:{d}" for a, b, c, d in spans[:3]))
        elif "zatvor" in chunk or "nestránkov" in chunk:
            rules.append(en + " off")
    order = [en for _, en in DAYS]
    have = {r.split(" ")[0] for r in rules}
    rules += [f"{en} off" for en in ("Sa", "Su") if en not in have]
    rules.sort(key=lambda r: order.index(r.split(" ")[0]))
    return "; ".join(rules)


def split_addr(a):
    a = re.sub(r"\s+", " ", a).strip(" ,")
    m = re.match(r"(.*?),?\s*(\d{3}\s?\d{2})\s*(.*)$", a)
    if m:
        return m.group(1).strip(" ,"), m.group(3).strip(" ,")
    return a, ""


def geocode(q):
    u = "https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=sk&q=" + urllib.parse.quote(q)
    t = get(u, 2)
    time.sleep(1.1)
    try:
        j = json.loads(t)
        return (round(float(j[0]["lat"]), 5), round(float(j[0]["lon"]), 5)) if j else None
    except Exception:  # noqa: BLE001
        return None


def vszp():
    base = "https://www.vszp.sk"
    h = get(base + "/kontaktne-miesta/")
    out, seen = [], set()
    for m in re.finditer(r"position:\s*\{\s*lat:\s*([\d.]+),\s*lng:\s*([\d.]+)\s*\},\s*title:\s*'([^']*)',\s*address:\s*'([^']*)'(.*?)detailLink:\s*'([^']*)'", h, re.S):
        lat, lon, title, addr, _, link = m.groups()
        if link in seen:
            continue
        seen.add(link)
        street, city = split_addr(html.unescape(addr))
        d = get(base + link)
        t = text_of(d)
        i = t.find("Otváracie hodiny")
        oh = hours_osm(t[i:i + 900].split("Nevyhovujú")[0]) if i >= 0 else ""
        tel = re.search(r"(?:Tel\.?|Telefón)[^\d+]{0,12}(\+?\d[\d /]{7,16}\d)", t)
        out.append([round(float(lat), 5), round(float(lon), 5), f"VšZP {html.unescape(title)}", street, city or html.unescape(title),
                    oh, tel.group(1).strip() if tel else "", "vszp", base + link])
        time.sleep(0.4)
    return out


def dovera():
    base = "https://www.dovera.sk"
    links = []
    for page in range(1, 12):
        h = get(f"{base}/pobocky" + (f"?page={page}" if page > 1 else ""))
        new = [l for l in dict.fromkeys(re.findall(r'href="(/pobocky/\d+-[a-z0-9-]+)"', h)) if l not in links]
        if not new:
            break
        links += new
    out = []
    for link in links:
        d = get(base + link)
        if not d:
            continue
        c = re.search(r"center=(4[789]\.\d+),(1[6-9]\.\d+|2[0-3]\.\d+)", d)
        t = text_of(d)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", d, re.S)
        name = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", title.group(1)))).strip() if title else link.split("-", 1)[1]
        i = t.find("Otváracie hodiny")
        oh = hours_osm(t[i:i + 700]) if i >= 0 else ""
        a = re.search(r"Adresa\s*\n\s*([^\n]+?),?\s*\n\s*([^\n]+)", t[i:] if i >= 0 else t)
        street, city = (a.group(1), re.sub(r"^\d{3}\s?\d{2}\s*", "", a.group(2))) if a else ("", "")
        lat_lon = (round(float(c.group(1)), 5), round(float(c.group(2)), 5)) if c else geocode(f"{street}, {city}")
        if not lat_lon:
            continue
        tel = re.search(r"(\+?421[\d /]{8,14}\d|0\d{2,3}[ /]?\d{3}[ /]?\d{3,4})", t)
        short = re.sub(r"^Pobočka\s+", "", name)
        out.append([lat_lon[0], lat_lon[1], f"Dôvera {short}", street.strip(), city.strip() or name,
                    oh, tel.group(1).strip() if tel else "", "dovera", base + link])
        time.sleep(0.4)
    return out


def union():
    """Zoznam pobočiek Union: riadky „Mesto, ulica“ v časti „Najbližšie pobočky“; súradnice z OpenStreetMap (Nominatim).
    Union uvádza len dnešné hodiny, preto ich neukladáme (odkaz vedie na stránku pobočiek)."""
    url = "https://www.union.sk/union-kontakty/pobocky/"
    t = text_of(get(url))
    i = t.find("Najbližšie pobočky")
    if i < 0:
        return []
    lines = [l.strip() for l in t[i:].split("\n")[1:] if l.strip()]
    zrusene = {(c.strip(), a.strip()) for c, a in re.findall(r"Pobočka ([^,\n]+), ([^,\n]+?), je od [\d.]+ zrušená", t)}
    out, seen = [], set(zrusene)
    for k, l in enumerate(lines):
        nxt = " ".join(lines[k + 1:k + 3])
        m = re.match(r"^([A-ZÁ-Ž][^,\d]{1,40}),\s*(.{3,90})$", l)
        if not m or not re.search(r"•|Teraz|zatvoren|otvoren", nxt):
            continue
        city, street = m.group(1).strip(), m.group(2).strip()
        street = re.sub(r"^ul\.\s*", "", street)
        if (city, street) in seen:
            continue
        seen.add((city, street))
        q = re.sub(r",\s*[^,]*(?:Center|centrum|OC|Shopping)[^,]*$", "", street, flags=re.I)
        ll = geocode(f"{q}, {city}") or geocode(city)
        if not ll:
            continue
        out.append([ll[0], ll[1], f"Union {city}" + (f" – {street.split(',')[-1].strip()}" if "," in street else ""), street, city, "", "", "union", url])
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8"))["pobocky"] if OUT.exists() else []
    result = []
    for key, fn in (("vszp", vszp), ("dovera", dovera), ("union", union)):
        try:
            rows = fn()
        except Exception as e:  # noqa: BLE001
            print(f"{key}: chyba {e}")
            rows = []
        prev = [r for r in old if r[7] == key]
        if len(rows) < max(5, len(prev) // 2):
            print(f"{NAMES[key]}: len {len(rows)} pobočiek, ponechávam uložených {len(prev)}")
            rows = prev
        else:
            print(f"{NAMES[key]}: {len(rows)} pobočiek, s hodinami {sum(1 for r in rows if r[5])}")
        result += rows
    if not result:
        sys.exit("Žiadne pobočky")
    OUT.write_text(json.dumps({"zdroj": "weby poisťovní VšZP, Dôvera a Union", "pobocky": result}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
