import re, urllib.request, pathlib
UA = {'User-Agent': 'Mozilla/5.0 (doplatkyliekov.sk data updater)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, binary=False, t=150):
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
                d = r.read(); return d if binary else d.decode('utf-8', 'replace')
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return b'' if binary else ''
for n, u in [('dp_A', 'https://cloud.health.gov.sk/s/WTj7b7fCXoms9H8/download'), ('dp_C', 'https://cloud.health.gov.sk/s/QP9g8d4acKCX6pZ/download')]:
    d = get(u, True, 200); (R / n).write_bytes(d); log.append(f'{n} {len(d)}')
for n, u in [('union_ben', 'https://www.union.sk/vyhody-pre-poistencov/'), ('dov_home', 'https://www.dovera.sk/'), ('vszp_ben', 'https://www.vszp.sk/poistenci/benefity-celu-rodinu/'),
             ('vszp_pen', 'https://www.vszp.sk/poistenci/penazenka-zdravia/')]:
    t = get(u); (R / f'{n}.html').write_text(t, encoding='utf-8'); log.append(f'{n} {len(t)}')
for k in ['bsk', 'ttsk', 'tsk', 'nsk', 'zsk', 'bbsk', 'psk', 'ksk']:
    t = get(f'https://www.e-vuc.sk/{k}/')
    z = sorted(set(re.findall(r'href="(https://www\.e-vuc\.sk/' + k + r'/zdravotnictvo[^"]*)"', t)))
    log.append(f'{k}: {len(t)} zdrav {z[:3]}')
    if z:
        t2 = get(z[0].replace('&amp;', '&'))
        menu = sorted(set(re.findall(r'href="(https://www\.e-vuc\.sk/' + k + r'/zdravotnictvo/[a-z0-9-]+\.html\?page_id=\d+)"', t2)))
        log.append(f'  menu {menu[:12]}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
