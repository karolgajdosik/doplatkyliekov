# Dočasné: overenie zdrojov (lekári, register liekov ŠÚKL, dietetické potraviny, výhody poisťovní)
import re, urllib.request, urllib.parse, pathlib, json, html
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, data=None, t=120):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=UA), timeout=t) as r:
                return r.read().decode('utf-8', 'replace'), r.geturl()
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return '', u
def links(t, pat):
    out = []
    for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', b))).strip()
        if re.search(pat, a + ' ' + b, re.I):
            out.append((a, b[:80]))
    return list(dict.fromkeys(out))
# 1) katalóg otvorených dát (CKAN)
for qq in ['poskytovatel zdravotnej starostlivosti', 'ambulancie', 'lekari', 'registrovane lieky', 'sukl', 'nczi']:
    for base in ['https://data.slovensko.sk/api/3/action/package_search?rows=8&q=', 'https://data.gov.sk/api/action/package_search?rows=8&q=']:
        t, _ = get(base + urllib.parse.quote(qq))
        try:
            res = json.loads(t)['result']['results']
            log.append(f'CKAN {base[8:30]} "{qq}": ' + ' | '.join(f"{p.get('title')} [{', '.join((r.get('format') or '') + ':' + (r.get('url') or '')[:90] for r in p.get('resources', [])[:3])}]" for p in res))
        except Exception as e:
            log.append(f'CKAN {base[8:30]} "{qq}": {len(t)} {e}')
# 2) ŠÚKL – register liekov
t, f = get('https://www.sukl.sk/')
log.append('SUKL links: ' + str(links(t, r'datab|registr|lieky|vyhlad|export|otvoren|open')[:25]))
for p in ['https://www.sukl.sk/pre-odbornikov-a-firmy/registracia-liekov', 'https://www.sukl.sk/hlavna-stranka/slovenska-verzia/databazy-a-servis/databazy']:
    t2, f2 = get(p); log.append(f'SUKL {p}: {len(t2)} ' + str(links(t2, r'datab|export|xls|csv|xml|zip|stiahn|open')[:25]))
# 3) MZ – dietetické potraviny
H = 'https://www.health.gov.sk'
t, _ = get(H + '/odbornik/kategorizacia-a-cenotvorba/')
log.append('MZ kat: ' + str(links(t, r'dietet|potravin|zkdp')))
for a, b in links(t, r'dietet|zkdp')[:2]:
    t2, f2 = get(urllib.parse.urljoin(H, a)); (R / 'mz_dp.html').write_text(t2, encoding='utf-8')
    subs = links(t2, r'zkdp|dp-?\d{6}|20\d{4}')
    log.append(f'MZ dp {f2}: subs {subs[:8]} cloud {links(t2, "cloud.health")[:6]}')
    if subs:
        t3, f3 = get(urllib.parse.urljoin(H, subs[0][0])); (R / 'mz_dp_sub.html').write_text(t3, encoding='utf-8')
        log.append(f'MZ dp sub {f3}: ' + str(links(t3, 'cloud.health')[:8]))
# 4) výhody poisťovní
for n, u, pat in [('dovera', 'https://www.dovera.sk/poistenec/benefity/vsetky', r'/benefity/'), ('union', 'https://www.union.sk/', r'benefit|výhod|vyhod'),
                  ('vszp', 'https://www.vszp.sk/', r'benefit|výhod|vyhod|program|penazenk')]:
    t, f = get(u); (R / f'ben_{n}.html').write_text(t, encoding='utf-8')
    log.append(f'BEN {n} {f} {len(t)}: ' + str(links(t, pat)[:30]))
# 5) OSM lekári
for k, q in {'doctors': 'nwr["amenity"="doctors"](area.a);', 'dentist': 'nwr["amenity"="dentist"](area.a);', 'clinic': 'nwr["amenity"="clinic"](area.a);nwr["amenity"="hospital"](area.a);'}.items():
    body = 'data=' + urllib.parse.quote(f'[out:json][timeout:120];area["ISO3166-1"="SK"][admin_level=2]->.a;({q});out center tags;')
    t, _ = get('https://overpass-api.de/api/interpreter', body.encode(), 180)
    try:
        el = json.loads(t)['elements']
        sp = {}
        for e in el:
            s = e.get('tags', {}).get('healthcare:speciality', '-')
            sp[s] = sp.get(s, 0) + 1
        log.append(f'OSM {k}: {len(el)}, s adresou {sum(1 for e in el if e.get("tags", {}).get("addr:street") or e.get("tags", {}).get("addr:place"))}, hodiny {sum(1 for e in el if e.get("tags", {}).get("opening_hours"))}, odbornosti {sorted(sp.items(), key=lambda x: -x[1])[:12]}')
    except Exception as e:
        log.append(f'OSM {k}: chyba {e}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
