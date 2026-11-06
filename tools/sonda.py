import re, urllib.request, urllib.parse, pathlib, time, json
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
H = 'https://www.e-vuc.sk'
for name, u in [('lp_ba1', H + '/bsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-bsk.html?page_id=51147&okres=Okres+Bratislava+I'),
                ('lp_za', H + '/zsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-zsk.html?page_id=40490&okres=Okres+%C5%BDilina'),
                ('lp_bb', H + '/bbsk/zdravotnictvo/lekarenska-pohotovostna-sluzba-v-bbsk.html?page_id=92808')]:
    t = get(u); (R / f'{name}.html').write_text(t); log.append(f'{name} len={len(t)} rows={t.count("window.location")}')
for term in ['Malacky', 'Žilina']:
    for pid in ['64903', '55563']:
        t = get(H + '/e-vuc/ajax-zdravotne-obvody-mesto.html?page_id=122990&' + urllib.parse.urlencode({'term': term, 'current_page_id': pid}))
        log.append(f'ajax {term} {pid}: {t[:600]}')
        try:
            j = json.loads(t)
            if j:
                mid = j[0].get('mesto_id')
                base = H + ('/bsk/zdravotnictvo/kto-je-moj-lekar-zdravotne-obvody.html' if pid == '64903' else '/zsk/zdravotnictvo/kto-je-moj-lekar-zdravotne-obvody.html')
                q = urllib.parse.urlencode({'page_id': pid, 'odbornost': 1, 'mesto': j[0].get('value') or j[0].get('label'), 'mesto_id': mid, 'current_page_id': pid, 'mesto_search_url': '', 'https': '', 'iframe': ''})
                r = get(base + '?' + q); (R / f'ob_{pid}_{mid}.html').write_text(r); log.append(f'  vysledok len={len(r)} rows={r.count("data-row")} url={base}?{q}')
        except Exception as e:
            log.append(f'  json err {e}')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
