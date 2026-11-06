import re, urllib.request, urllib.parse, pathlib, json, html
UA = {'User-Agent': 'Mozilla/5.0 (doplatkyliekov.sk data updater)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, data=None, t=120, hdr=None):
    for k in range(2):
        try:
            h = dict(UA); h.update(hdr or {})
            with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=t) as r:
                return r.read().decode('utf-8', 'replace'), r.geturl(), r.headers.get('Content-Type', '')
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return '', u, ''
def links(t, pat):
    out = []
    for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', b))).strip()
        if re.search(pat, a + ' ' + b, re.I):
            out.append((a, b[:90]))
    return list(dict.fromkeys(out))
t, f, ct = get('https://www.sukl.sk/verejne/'); (R / 'sukl_verejne.html').write_text(t, encoding='utf-8')
log.append(f'SUKL verejne {f} {ct} {len(t)}: ' + str(links(t, r'.')[:60]))
for sub in [a for a, b in links(t, r'lieky|registr|databaz|zoznam|lieč|liec|export')][:3]:
    t2, f2, _ = get(urllib.parse.urljoin(f, sub)); log.append(f'  SUB {f2}: ' + str(links(t2, r'.')[:40]))
t, f, ct = get('https://portal.unionzp.sk/pub/zmluvni-lekari-pzs'); (R / 'union_pzs.html').write_text(t, encoding='utf-8')
log.append(f'UNION pzs {f} {ct} {len(t)} forms {re.findall(r"<form[^>]*>", t)[:3]} selects {[s[:80] for s in re.findall(r"<select[^>]*>", t)][:6]} links {links(t, r"xls|csv|export|stiahn")[:8]} scripts {re.findall(r"src=\"([^\"]+)\"", t)[:8]}')
t, f, ct = get('https://www.e-vuc.sk/bsk/zdravotnictvo/kto-je-moj-lekar-zdravotne-obvody.html?page_id=64903'); (R / 'evuc.html').write_text(t, encoding='utf-8')
log.append(f'EVUC {f} {len(t)} ' + str(links(t, r'lekár|lekar|obvod|xls|csv|zoznam|ambul')[:15]))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
