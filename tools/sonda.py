import re, urllib.request, pathlib, time
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u):
    time.sleep(1.5)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            return r.read().decode('utf-8', 'replace')
    except Exception as e:
        log.append(f'ERR {u} {e}'); return ''
t = get('https://www.e-vuc.sk/bsk/zdravotnictvo/ambulantne-zdravotnicke-zariadenia.html?page_id=60142'); (R / 'amb_kraj.html').write_text(t)
ok = re.findall(r"<tr onclick=\"window\.location = '([^']+)'\".*?<a [^>]*>(.*?)</a>", t, re.S)
log.append(str([(u[-60:], re.sub(r'\s+', ' ', n)) for u, n in ok]))
if ok:
    t2 = get(ok[0][0]); (R / 'amb_okres1.html').write_text(t2)
    log.append(f'okres1 rows={t2.count("window.location")} pag={re.findall(r"[?&](?:page|strana|p|offset|start)[a-z_]*=\d+", t2)[:20]}')
t = get('https://www.e-vuc.sk/bsk/zdravotnictvo/ambulantna-pohotovostna-sluzba-v-bsk/bratislava-ii.html?page_id=127626'); (R / 'aps_ba2.html').write_text(t)
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
