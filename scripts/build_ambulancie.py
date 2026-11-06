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
import urllib.error
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
DELAY = float(ARG.get("--delay", 0.8))
ONLY = [k for k in ARG.get("--kraj", "").split(",") if k]
n_req = 0


def get(url, tries=4):
    global n_req
    for k in range(tries):
        try:
            n_req += 1
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = r.read().decode("utf-8", "replace")
            time.sleep(DELAY)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            wait = 60 * (k + 1) if e.code == 429 else 3 + 3 * k
            print(f"  pokus {k + 1}: {url}: {e}, čakám {wait} s")
            time.sleep(wait)
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


def okresy_url(url):
    h = get(url)
    return [(u, txt(t)) for u, t in re.findall(r"<tr onclick=\"window\.location = '([^']+)'\".*?<a [^>]*>(.*?)</a>", h, re.S)
            if "okres" in t.lower()], h


def menu(h, kraj):
    """Odkazy v ľavom menu zdravotníctva kraja: slug → URL."""
    return {m.group(1): html.unescape(m.group(0)[6:-1]) for m in
            re.finditer(r'href="https://www\.e-vuc\.sk/' + kraj + r'/zdravotnictvo/([a-z0-9-]+)\.html\?page_id=\d+"', h)}


def lekarne_pohotovost(url):
    """Rozpis lekárenskej pohotovostnej služby: okresy (?okres=…) → riadky [dátum, page_id lekárne, názov, adresa, čas]."""
    h = get(url)
    okr = list(dict.fromkeys(html.unescape(u) for u in re.findall(r'href="([^"]*[?&]okres=[^"]+)"', h)))
    out = []
    for u in okr or [url]:
        p = get(u) if okr else h
        for tbl in re.findall(r'<table class="list er">(.*?)</table>', p, re.S):
            day = None
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
                d = re.search(r"(\d{1,2})\.(\d{1,2})\.(20\d\d)", re.sub(r"<a .*?</a>", "", tr, flags=re.S))
                if d:
                    day = f"{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}"
                a = re.search(r'<a href="([^"]+)">(.*?)</a>', tr, re.S)
                if not a or not day:
                    continue
                tds = [txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
                addr = next((t for t in tds if re.search(r"\d{3}\s?\d{2}\s+\S", t)), "")
                cas = next((t for t in reversed(tds) if re.match(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", t)), "")
                out.append([day, pid(a.group(1)), txt(a.group(2)), addr, cas, a.group(1)])
    return out


def rows(url):
    """Všetky strany zoznamu zariadení v okrese (po 150, stránkovanie ?page=N)."""
    h = get(url)
    last = re.search(r'title="Posledná strana"[^>]*href="[^"]*[?&]page=(\d+)', h) or \
        re.search(r'href="[^"]*[?&]page=(\d+)[^"]*"[^>]*>&gt;&gt;', h)
    pages = [h]
    if last:
        sep = "&" if "?" in url else "?"
        for n in range(2, min(int(last.group(1)), 60) + 1):
            pages.append(get(f"{url}{sep}page={n}"))
    out = []
    for h in pages:
        out += rows_of(h)
    return out


def rows_of(h):
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
    amb, aps, nem, done, lp_all = [], [], [], [], []
    for kraj, (amb_id, aps_id) in KRAJE.items():
        if ONLY and kraj not in ONLY:
            continue
        ka, kp, kn = [], [], []
        for u, _ in okresy(kraj, "aps", aps_id):
            kp += rows(u)
        ok_amb, h_amb = okresy_url(f"{H}/{kraj}/zdravotnictvo/ambulantne-zdravotnicke-zariadenia.html?page_id={amb_id}")
        for u, _ in ok_amb:
            ka += rows(u)
        mn = menu(h_amb, kraj)
        u_uz = next((v for k, v in mn.items() if k.startswith("ustavne-zdravotnicke")), None)
        if u_uz:
            for u, _ in okresy_url(u_uz)[0]:
                kn += [x for x in rows(u) if "výskum" not in x["druh"]]
        u_lp = next((v for k, v in mn.items() if k.startswith("lekarenska-pohotovost")), None)
        klp = lekarne_pohotovost(u_lp) if u_lp else []
        for r in klp:
            r.append(kraj)
        lp_all.extend(klp)
        print(f"{kraj}: {len(ka)} ambulancií, {len(kp)} pohotovostí, {len(kn)} nemocníc, {len(klp)} služieb lekární")
        if len(ka) < 200:
            print(f"  {kraj}: podozrivo málo ambulancií, ponechávam uložené")
            continue
        for x in ka + kp + kn:
            x["k"] = kraj
        amb += ka
        aps += kp
        nem += kn
        done.append(kraj)
    # deduplikácia (to isté zariadenie býva vo viacerých okresoch)
    seen, A, P, N = set(), [], [], []
    for lst, dst in ((aps, P), (nem, N), (amb, A)):
        for x in lst:
            x["p"] = pid(x["u"])
            if x["p"] in seen:
                continue
            seen.add(x["p"])
            dst.append(x)
    # súradnice z detailov: najprv pohotovosti, potom ambulancie
    # pohotovostné lekárne: rozpis od dnes, súradnice z detailu lekárne
    lp_today = [r for r in lp_all if r[0] >= today]
    lekarne_lp = {}
    for r in lp_today:
        lekarne_lp.setdefault(r[1], {"u": r[5], "p": r[1], "n": r[2], "a": r[3], "k": r[6]})
    todo = [x for x in P + list(lekarne_lp.values()) + N + A if x["p"] not in gps]
    print(f"bez súradníc {len(todo)}, sťahujem najviac {MAX}")
    t0 = time.time()
    for k, x in enumerate(todo[:MAX]):
        gps[x["p"]] = detail(x["u"]) or 0
        if k % 500 == 499:
            GPS.write_text(json.dumps(gps, separators=(",", ":")), encoding="utf-8")
            print(f"  {k + 1} detailov, {time.time() - t0:.0f} s")
    if done and not ONLY:
        live = {x["p"] for x in P + N + A} | set(lekarne_lp)
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
    # riadok: [lat, lon, názov, adresa, druh, oddelenia, kraj, page_id]
    nemoc = [[*gps[x["p"]], x["n"], x["a"], x["druh"], x["o"][:400], x["k"], int(x["p"])] for x in N if gps.get(x["p"])]
    # pohotovostné lekárne: miesta {page_id: [lat, lon, názov, adresa, kraj]} a rozpis {dátum: [[page_id, čas], …]}
    lp_m = {p: [*gps[p], v["n"], v["a"], v["k"]] for p, v in lekarne_lp.items() if gps.get(p)}
    lp_d = {}
    for r in sorted(lp_today):
        if r[1] in lp_m and [r[1], r[4]] not in lp_d.get(r[0], []):
            lp_d.setdefault(r[0], []).append([r[1], r[4]])
    # kraje, ktoré sa tentoraz nepodarilo stiahnuť, ponecháme z minula
    lekari += [r for r in old.get("lekari", []) if r[6] not in done and (not ONLY or r[6] not in ONLY)]
    pohot += [r for r in old.get("pohotovosti", []) if r[6] not in done and (not ONLY or r[6] not in ONLY)]
    nemoc += [r for r in old.get("nemocnice", []) if r[6] not in done and (not ONLY or r[6] not in ONLY)]
    for p, v in (old.get("lp_miesta") or {}).items():
        if v[4] not in done and p not in lp_m:
            lp_m[p] = v
    for d, lst in (old.get("lp_rozpis") or {}).items():
        if d >= today:
            for e in lst:
                if lp_m.get(e[0], [0] * 5)[4] not in done and e not in lp_d.get(d, []):
                    lp_d.setdefault(d, []).append(e)
    if old.get("odbory") and odbory != old["odbory"]:
        remap = {i: oi.get(o, -1) for i, o in enumerate(old["odbory"])}
        for r in lekari:
            if r[6] not in done:
                r[4] = remap.get(r[4], -1)
    cnt = dict(old.get("pocet", {}))
    for k in done:
        cnt[k] = [sum(1 for x in A if x["k"] == k), sum(1 for x in P if x["k"] == k)]
    res = {"datum": today, "zdroj": "registre zdravotníckych zariadení samosprávnych krajov (e-VÚC)",
           "chyba": "Košický kraj", "odbory": odbory, "pocet": cnt, "lekari": lekari, "pohotovosti": pohot,
           "nemocnice": nemoc, "lp_miesta": lp_m, "lp_rozpis": dict(sorted(lp_d.items()))}
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"nemocnice {len(nemoc)}/{len(N)}, pohotovostné lekárne {len(lp_m)}/{len(lekarne_lp)}, rozpis {len(lp_d)} dní")
    print(f"lekari.json: {len(lekari)} ambulancií a {len(pohot)} pohotovostí so súradnicami "
          f"(v registroch {sum(v[0] for v in cnt.values())} a {sum(v[1] for v in cnt.values())}), "
          f"{len(odbory)} odborností, {n_req} požiadaviek")


if __name__ == "__main__":
    main()
