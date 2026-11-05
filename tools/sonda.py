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
L = H + '/odbornik/kategorizacia-a-cenotvorba/kategorizacia-liekov/zoznam-kategorizovanych-liekov/'
t = get(L)
A = anchors(t)
log.append(f'== ZKL {len(A)} odkazov')
for a, b in A[:80]:
    if 'ministerstvo/' in a or a in ('/', '/odbornik/'):
        continue
    log.append(f'  {a} | {b[:100]}')
subs = [a for a, b in A if re.search(r'2026|202611|202612', a + b) and 'cloud' not in a][:3]
for c in subs:
    u = c if c.startswith('http') else H + c
    log.append(f'== SUB {u}')
    for a, b in anchors(get(u)):
        if 'cloud.health' in a:
            log.append(f'  {a} | {b[:110]}')
pathlib.Path('raw').mkdir(exist_ok=True)
pathlib.Path('raw/log.txt').write_text('\n'.join(log), encoding='utf-8')
print('\n'.join(log))
