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
for n, u in [('zp1', 'https://cloud.health.gov.sk/s/ByFb8Gf6AsdB4DE/download'),
             ('zp2', 'https://cloud.health.gov.sk/s/xgdX3fwjiALdmb2/download'),
             ('zp3', 'https://cloud.health.gov.sk/s/XgrG5MG6Y9BjZHw/download')]:
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=300) as r:
                d = r.read(); cd = r.headers.get('Content-Disposition', '')
            (R / n).write_bytes(d); log.append(f'OK {n} {len(d)} {cd} {d[:4]!r}'); break
        except Exception as e:
            log.append(f'ERR {k} {n} {e}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
