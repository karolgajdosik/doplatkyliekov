# Dočasné: zdroje pobočiek poisťovní a výdajní pomôcok
import re, urllib.request, urllib.parse, pathlib, json
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, data=None, t=120):
    for k in range(3):
        try:
            req = urllib.request.Request(u, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=t) as r:
                return r.read().decode('utf-8', 'replace'), r.geturl()
        except Exception as e:
            log.append(f'ERR {k} {u[:120]} {e}')
    return '', u
for name, home in [('vszp', 'https://www.vszp.sk/'), ('dovera', 'https://www.dovera.sk/'), ('union', 'https://www.union.sk/')]:
    t, final = get(home)
    (R / f'{name}_home.html').write_text(t, encoding='utf-8')
    links = sorted(set(re.findall(r'href="([^"]*(?:pobock|kontakt|pracovisk|klientsk)[^"]*)"', t, re.I)))
    log.append(f'{name} {final}: {links[:15]}')
    for i, l in enumerate(links[:4]):
        u = urllib.parse.urljoin(final, l)
        tt, f2 = get(u)
        (R / f'{name}_{i}.html').write_text(tt, encoding='utf-8')
        log.append(f'  {name}_{i} {f2} {len(tt)}')
Q = {
 'poistovne': 'node["office"="insurance"]["name"~"VšZP|Všeobecná zdravotná|Dôvera|Union|ZP ",i](area.a);way["office"="insurance"]["name"~"VšZP|Všeobecná zdravotná|Dôvera|Union|ZP ",i](area.a);',
 'medical_supply': 'node["shop"="medical_supply"](area.a);way["shop"="medical_supply"](area.a);',
 'hearing': 'node["shop"="hearing_aids"](area.a);way["shop"="hearing_aids"](area.a);',
 'optician': 'node["shop"="optician"](area.a);way["shop"="optician"](area.a);',
 'orthopedics': 'node["healthcare"="orthopedics"](area.a);node["shop"="orthopedics"](area.a);',
}
for k, q in Q.items():
    body = 'data=' + urllib.parse.quote(f'[out:json][timeout:120];area["ISO3166-1"="SK"][admin_level=2]->.a;({q});out center tags;')
    t, _ = get('https://overpass-api.de/api/interpreter', body.encode(), 180)
    try:
        el = json.loads(t)['elements']
    except Exception:
        el = []
    (R / f'osm_{k}.json').write_text(json.dumps(el, ensure_ascii=False), encoding='utf-8')
    log.append(f'OSM {k}: {len(el)} | ' + '; '.join((e.get('tags', {}).get('name', '?') + ' / ' + e.get('tags', {}).get('addr:city', '')) for e in el[:6]))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
