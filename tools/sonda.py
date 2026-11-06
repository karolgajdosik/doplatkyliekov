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
ok = 0; urls = json.load(open('tools/spc_urls.json'))
for u in urls:
    f, t = get(u); ok += bool(t)
    if not t: log.append(f'ERR {u}')
log.append(f'SPC slug ok {ok}/{len(urls)}')
for y in (2025, 2024, 2023):
    u = f'https://data.nczisk.sk/statisticke_vystupy/top_100_liekov/spotreba_liekov/Spotreba_liekov_a_zdravotnickych_pomocok_v_SR_{y}.xlsx'
    f, b = get(u, binary=True); log.append(f'spotreba {y}: {len(b or b"")}')
    if b: (R / f'spotreba_{y}.xlsx').write_bytes(b)
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
