# Dočasné: zoznam kategorizovaných zdravotníckych pomôcok MZ SR
import re, urllib.request, pathlib
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
log = []
def get(u, t=180):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
                return r.read()
        except Exception as e:
            log.append(f'ERR {k} {u} {e}')
    return None
H = 'https://www.health.gov.sk'
p = '/odbornik/kategorizacia-a-cenotvorba/zoznam-kategorizovanych-zdravotnickych-pomocok/'
h = get(H + p)
if h:
    (R / 'mz_zp.html').write_bytes(h)
    t = h.decode('utf-8', 'replace')
    files = re.findall(r'href="([^"]+\.(?:xlsx|xls|docx|pdf|zip))"', t, re.I)
    log.append('SUBORY:\n' + '\n'.join(files[:60]))
    pick = [f for f in files if re.search(r'2026|202611|202612', f)][:10]
    for f in pick:
        u = f if f.startswith('http') else H + ('' if f.startswith('/') else '/') + f
        d = get(u)
        if d:
            n = 'zp_' + re.sub(r'[^\w.-]+', '_', u.split('/')[-2] + '_' + u.split('/')[-1])[-90:]
            (R / n).write_bytes(d); log.append(f'OK {n} {len(d)}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
