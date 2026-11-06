import re, urllib.request, urllib.parse, pathlib, json, html
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, data=None, t=120, hdr=None):
    for k in range(2):
        try:
            h = dict(UA); h.update(hdr or {})
            with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=t) as r:
                return r.read().decode('utf-8', 'replace'), r.geturl()
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return '', u
def links(t, pat):
    out = []
    for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', b))).strip()
        if re.search(pat, a + ' ' + b, re.I):
            out.append((a, b[:70]))
    return list(dict.fromkeys(out))
t, f = get('https://www.sukl.sk/o-nas/databazy-a-servis'); (R / 'sukl_db.html').write_text(t, encoding='utf-8')
i = t.find('<main'); log.append('SUKL db: ' + str(links(t[i:] if i > 0 else t, r'.')[:40]))
for n, u in [('dovera', 'https://www.dovera.sk/'), ('vszp', 'https://www.vszp.sk/'), ('union', 'https://www.union.sk/')]:
    t, f = get(u)
    log.append(f'{n} lekari: ' + str(links(t, r'lekár|lekar|poskytovat|ambulanc|vyhľadať|benefit|výhod')[:20]))
t, f = get('https://www.union.sk/vyhody-pre-poistencov/'); (R / 'union_ben.html').write_text(t, encoding='utf-8'); log.append(f'union ben {len(t)}')
for ep in ['https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']:
    body = 'data=' + urllib.parse.quote('[out:json][timeout:150];area["ISO3166-1"="SK"][admin_level=2]->.a;(nwr["amenity"~"doctors|dentist|clinic"](area.a);nwr["healthcare"~"doctor|dentist"](area.a););out center tags;')
    t, _ = get(ep, body.encode(), 200)
    try:
        el = json.loads(t)['elements']
    except Exception:
        continue
    sp = {}
    for e in el:
        tg = e.get('tags', {}); s = tg.get('healthcare:speciality') or tg.get('amenity') or '-'
        sp[s] = sp.get(s, 0) + 1
    log.append(f'OSM {ep[8:30]}: {len(el)}, s adresou {sum(1 for e in el if e.get("tags", {}).get("addr:street") or e.get("tags", {}).get("addr:place"))}, s menom {sum(1 for e in el if e.get("tags", {}).get("name"))}, hodiny {sum(1 for e in el if e.get("tags", {}).get("opening_hours"))}, odbornosti {sorted(sp.items(), key=lambda x: -x[1])[:15]}')
    (R / 'osm_doc.json').write_text(json.dumps(el[:3000], ensure_ascii=False), encoding='utf-8')
    break
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
