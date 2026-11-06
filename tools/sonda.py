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
save('top50', 'https://www.nczisk.sk/Statisticke_vystupy/Tematicke_statisticke_vystupy/TOP-50-liekov/Pages/default.aspx', r'xls|pdf|csv|TOP')
for n, u in [('kup_ind', 'https://cloud.health.gov.sk/s/jYKDxmKqn88kKwH/download'), ('kup_prev', 'https://cloud.health.gov.sk/s/7DYxCLnitm9ad6e/download')]:
    f, b = get(u, binary=True); (R / n).write_bytes(b or b''); log.append(f'{n} len={len(b or b"")} head={(b or b"")[:8]}')
import time as _t
_t.sleep(120)
for path in ['', 'api/', 'robots.txt']:
    f, t = get('https://doplatkyliekov.sk/api/docasna-sonda?u=' + urllib.parse.quote('https://ecakacielistiny.npz.sk/' + path))
    (R / f'npz_{path.replace("/", "_") or "root"}.json').write_text(t or ''); log.append(f'npz via CF {path}: {(t or "")[:400]}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
