# Dočasné: stiahne vzorky zdrojov do raw/ (ŠÚKL stiahnutia, DHPC, MZ SR pomôcky)
import re, urllib.request, pathlib, time, json
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
log = []
def get(u, t=60):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
            return r.read()
    except Exception as e:
        log.append(f'ERR {u} {e}'); return None
def save(name, data):
    if data is not None:
        (R / name).write_bytes(data); log.append(f'OK {name} {len(data)}')
S = 'https://www.sukl.sk'
for i, path in enumerate(['/pre-odbornikov-a-firmy/dostupnost-a-kvalita-liekov/kvalita-liekov/oznamy-o-stiahnuti-liekov',
                          '/pre-odbornikov-a-firmy/bezpecnost-liekov/oznamy-drzitelov-dhpc']):
    h = get(S + path); save(f'sukl_list_{i}.html', h)
    if h:
        links = sorted(set(re.findall(r'href="(' + re.escape(S + path) + r'/[^"#?]+)"', h.decode('utf-8', 'replace'))))
        log.append(f'{path}: {len(links)} detailov')
        for j, l in enumerate(links[:6]):
            save(f'sukl_det_{i}_{j}.html', get(l)); time.sleep(1)
        # stránkovanie
        pg = sorted(set(re.findall(r'href="([^"]*(?:page|strana|stranka)=\d+[^"]*)"', h.decode('utf-8', 'replace'))))
        log.append(f'strankovanie {i}: {pg[:5]}')
        if pg:
            u = pg[0] if pg[0].startswith('http') else S + pg[0].replace('&amp;', '&')
            save(f'sukl_list_{i}_p2.html', get(u))
H = 'https://www.health.gov.sk'
h = get(H + '/?zoznam-kategorizovanych-liekov'); save('mz_zkl.html', h)
cand = set()
if h:
    t = h.decode('utf-8', 'replace')
    cand |= set(re.findall(r'href="(\?[^"]*(?:pomoc|zdravotnick|dietet|zp)[^"]*)"', t, re.I))
log.append(f'kandidati stranok: {sorted(cand)}')
for c in sorted(cand)[:6]:
    hh = get(H + '/' + c); save('mz_' + re.sub(r'\W+', '_', c)[:60] + '.html', hh)
    if hh:
        files = sorted(set(re.findall(r'href="([^"]*(?:zkzp|zkdp)[^"]*\.(?:xlsx|xls|docx|pdf|zip))"', hh.decode('utf-8', 'replace'), re.I)))
        log.append(f'subory {c}: {files[:40]}')
        for f in [f for f in files if '2026' in f or '2611' in f][:8]:
            u = f if f.startswith('http') else H + ('' if f.startswith('/') else '/') + f
            save('zp_' + f.split('/')[-1], get(u, 120))
for d in ('zkzp', 'zkdp'):
    save(f'mz_dir_{d}.html', get(f'{H}/Zdroje?/Sources/kategorizacia/{d}/202611/'))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8')
print('\n'.join(log))
