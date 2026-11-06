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
t = save('skd', 'https://www.sukl.sk/concor-10-mg-94163', r'\.pdf|\.doc|spc|pil|verejne|download|subor|dokument')
for u in ['https://www.sukl.sk/x-94163', 'https://www.sukl.sk/94163', 'https://www.sukl.sk/liek-94163']:
    f, t2 = get(u); log.append(f'{u} -> {f} len={len(t2 or "")} concor={"Concor" in (t2 or "")}')
import random
for q in ['zentiva', 'ratiopharm', 'Ženy', 'Paralen', 'Apo-', 'Lipanthyl']:
    f, t2 = get('https://www.sukl.sk/rozsirene-vyhladavanie?search_type=drugs&drug_fulltext=' + urllib.parse.quote(q))
    rows = re.findall(r'<a href="https://www\.sukl\.sk/([^"]+)">[^<]*</a>\s*</td>\s*<td>\s*<label>Kód</label>\s*(\w+)\s*</td>\s*<td>\s*<label>Liek / Účinná látka</label>\s*([^<]+?)\s*</td>', t2 or '')
    log.append(f'{q}: ' + ' | '.join(f'{a} <= {c.strip()} [{b}]' for a, b, c in rows[:8]))
f, t = get('https://ecakacielistiny.npz.sk/')
log.append(f'npz retry len={len(t or "")}')
save('nczit', 'https://www.nczisk.sk/Statisticke_vystupy/Tematicke_statisticke_vystupy/Pages/default.aspx', r'liek|spotreb|xls')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
