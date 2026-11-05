# Dočasné: nové umiestnenie zoznamu kategorizovaných liekov na webe MZ SR
import re, urllib.request, pathlib
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
H = 'https://www.health.gov.sk'
log = []
def get(u):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            log.append(f'ERR {k} {u} {e}')
    return ''
def anchors(t):
    i = t.find('<main'); t = t[i:] if i > 0 else t
    return [(a, re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', b)).strip()) for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S)]
for p in ['/odbornik/kategorizacia-a-cenotvorba/kategorizacia-liekov/', '/odbornik/kategorizacia-a-cenotvorba/']:
    t = get(H + p)
    log.append(f'== {p}')
    for a, b in anchors(t):
        if re.search(r'zkl|zoznam|liek', a + b, re.I) and 'ministerstvo' not in a:
            log.append(f'  {a} | {b[:90]}')
cands = sorted(set(a for p in ['/odbornik/kategorizacia-a-cenotvorba/kategorizacia-liekov/'] for a, b in anchors(get(H + p)) if re.search(r'zkl-?\d{6}|zoznam-kategorizovanych-liekov', a)))
log.append(f'KANDIDATI {cands[:20]}')
for c in cands[:3] + [x for x in cands if '202611' in x or '202612' in x][:2]:
    u = c if c.startswith('http') else H + c
    t = get(u)
    log.append(f'== {u}')
    for a, b in anchors(t):
        if 'cloud.health' in a or re.search(r'zkl-?\d{6}', a):
            log.append(f'  {a} | {b[:110]}')
pathlib.Path('raw').mkdir(exist_ok=True)
pathlib.Path('raw/log.txt').write_text('\n'.join(log), encoding='utf-8')
for l in log: print(f'::notice::{l[:900]}') if False else None
print('\n'.join(log))
