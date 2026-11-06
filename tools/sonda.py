import re, urllib.request, pathlib, time, html
UA = {'User-Agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u):
    time.sleep(2.5)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            return r.read().decode('utf-8', 'replace')
    except Exception as e:
        log.append(f'ERR {u} {e}'); return ''
def links(t):
    return [(u, re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', n))).strip()) for u, n in
            re.findall(r"<tr\s+onclick=\"window\.location = '([^']+)'\".*?<a [^>]*>(.*?)</a>", t, re.S)]
H = 'https://www.e-vuc.sk'
jobs = [('lp_bsk', '/bsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-bsk.html?page_id=51147', 2),
        ('lp_zsk', '/zsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-zsk.html?page_id=40490', 2),
        ('uz_bsk', '/bsk/zdravotnictvo/ustavne-zdravotnicke-zariadenia.html?page_id=60143', 2),
        ('ob_bsk', '/bsk/zdravotnictvo/kto-je-moj-lekar-zdravotne-obvody.html?page_id=64903', 3),
        ('mo_bsk', '/bsk/zdravotnictvo/mobilne-odberove-miesta.html?page_id=135367', 2)]
for name, path, depth in jobs:
    t = get(H + path); (R / f'{name}_0.html').write_text(t)
    L = links(t); log.append(f'{name}_0 len={len(t)} rows={len(L)} {L[:4]}')
    pdf = re.findall(r'href="([^"]+\.pdf)"', t); log.append(f'  pdf {pdf[:5]}')
    for d in range(1, depth + 1):
        if not L: break
        t = get(L[0][0]); (R / f'{name}_{d}.html').write_text(t)
        L2 = links(t); log.append(f'{name}_{d} {L[0][1][:60]} len={len(t)} rows={len(L2)} {L2[:3]} gps={bool(re.search(r"maps.google.com/.q=4", t))}')
        L = L2
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
