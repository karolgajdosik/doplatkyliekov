import re, urllib.request, urllib.parse, pathlib, json, html
UA = {'User-Agent': 'Mozilla/5.0 (doplatkyliekov.sk data updater)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, t=150, binary=False):
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
                d = r.read(); return (d if binary else d.decode('utf-8', 'replace')), r.geturl()
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return (b'' if binary else ''), u
def links(t, pat):
    out = []
    for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', b))).strip()
        if re.search(pat, a + ' ' + b, re.I):
            out.append((a, b[:100]))
    return list(dict.fromkeys(out))
t, f = get('https://www.sukl.sk/verejne/Zoznam_liekov/')
log.append('ZL: ' + str([a for a, b in links(t, r'.')][5:60]))
files = [a for a, b in links(t, r'aktual|\.xlsx|\.zip|\.csv|\.xml') if not a.startswith('?')]
pick = [x for x in files if 'aktual' in x.lower()][:1] or files[-1:]
for x in pick:
    d, _ = get(urllib.parse.urljoin(f, x), binary=True, t=300)
    (R / ('zl_' + x.split('/')[-1])).write_bytes(d); log.append(f'ZL file {x} {len(d)} {d[:4]!r}')
E = 'https://www.e-vuc.sk/bsk/zdravotnictvo/ambulantne-zdravotnicke-zariadenia.html?page_id=60142'
t, f = get(E); (R / 'evuc_amb.html').write_text(t, encoding='utf-8')
log.append(f'EVUC amb {len(t)} pag {sorted(set(re.findall(r"[?&](?:page|p|strana|offset|start)=\d+", t)))[:10]} det {links(t, r"detail|zariadenie")[:6]} export {links(t, r"xls|csv|export|stiahn|tlač")[:6]}')
dets = [a for a, b in links(t, r'detail')][:1]
for d0 in dets:
    t2, f2 = get(urllib.parse.urljoin(E, html.unescape(d0))); (R / 'evuc_det.html').write_text(t2, encoding='utf-8'); log.append(f'EVUC det {f2} {len(t2)}')
t, f = get('https://www.e-vuc.sk/'); log.append('EVUC kraje: ' + str(sorted(set(re.findall(r'e-vuc\.sk/([a-z]{3,5})/', t)))))
t, f = get('https://www.e-vuc.sk/bsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-bsk.html?page_id=51147'); (R / 'evuc_lps.html').write_text(t, encoding='utf-8'); log.append(f'EVUC LPS {len(t)} pdf {links(t, r"pdf")[:5]}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
