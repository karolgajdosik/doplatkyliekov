import re, urllib.request, urllib.parse, pathlib, time, html, json
UA = {'User-Agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, binary=False):
    time.sleep(1.0)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120) as r:
            d = r.read(); return r.geturl(), (d if binary else d.decode('utf-8', 'replace'))
    except Exception as e:
        log.append(f'ERR {u} {e}'); return '', ''
def save(name, u, kw):
    f, t = get(u)
    (R / f'{name}.html').write_text(t or '')
    links = sorted(set(re.findall(r'href="([^"]+)"', t or '')))
    hit = [l for l in links if re.search(kw, l, re.I)]
    log.append(f'== {name} {u} -> {f} len={len(t or "")}\n   ' + '\n   '.join(hit[:40]))
    return t
for q in ['Lopridam', 'Actelsar HCT', 'Benoxi', 'Aboxoma', 'Acnatac', 'Norditropin FlexPro', 'Accofil', 'Abiraterone G.L.', 'Carzap HCT']:
    f, t2 = get('https://www.sukl.sk/rozsirene-vyhladavanie?search_type=drugs&drug_fulltext=' + urllib.parse.quote(q))
    rows = re.findall(r'<a href="https://www\.sukl\.sk/([^"]+)">[^<]*</a>\s*</td>\s*<td>\s*<label>Kód</label>\s*(\w+)\s*</td>\s*<td>\s*<label>Liek / Účinná látka</label>\s*([^<]+?)\s*</td>', t2 or '')
    log.append(f'{q}: ' + ' | '.join(f'{a} <= {c.strip()} [{b}]' for a, b, c in rows[:4]))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
