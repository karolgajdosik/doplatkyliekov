import re, urllib.request, pathlib, time, html, json
UA = {'User-Agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, binary=False):
    time.sleep(1.0)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
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
t = save('sk1', 'https://www.sukl.sk/rozsirene-vyhladavanie?search_type=drugs&drug_fulltext=concor+10', r'detail|liek/|lieky/|spc|pil|kod')
m = re.findall(r'href="(https://www\.sukl\.sk/[^"]*(?:detail|lieky?/)[^"]*)"', t or '')
if m:
    t2 = save('sk2', html.unescape(m[0]), r'\.pdf|\.doc|spc|pil|verejne|download|subor')
t = save('npz', 'https://ecakacielistiny.npz.sk/', r'.')
for s_ in re.findall(r'<script[^>]*src="([^"]+)"', t or '')[:4]:
    u = s_ if s_.startswith('http') else 'https://ecakacielistiny.npz.sk/' + s_.lstrip('/')
    f, js = get(u); (R / ('npz_' + re.sub(r'\W', '_', s_)[-40:] + '.js')).write_text(js or '')
    log.append(f'js {u} len={len(js or "")} api={sorted(set(re.findall(r"[\"\x27`](/?api/[A-Za-z0-9/_.-]+|https?://[a-z0-9.-]+npz[^\"\x27`]*)", js or "")))[:30]}')
save('nczi', 'https://www.nczisk.sk/Statisticke_vystupy/Zverejnovanie_podla_zakona_liekoch_zdravotnickych_pomockach/Pages/default.aspx', r'xls|csv|zip|pdf|Pages')
save('kup', 'https://www.health.gov.sk/ministerstvo/kupele-a-zriedla/povolenie-na-prevadzkovanie-prirodnych-liecebnych-kupelov-a-kupelnych-liecebni/', r'cloud|xls|pdf|kupel')
save('kup0', 'https://www.health.gov.sk/ministerstvo/kupele-a-zriedla/', r'cloud|xls|pdf|kupel')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
