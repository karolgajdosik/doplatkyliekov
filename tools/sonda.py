import re, urllib.request, urllib.parse, pathlib, html
UA = {'User-Agent': 'Mozilla/5.0 (doplatkyliekov.sk data updater)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u):
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return ''
def rows(t):
    j = t.find('<table class="list">'); k = t.find('</table>', j)
    return re.findall(r"window.location = '([^']+)'.*?<td>(.*?)</td>", t[j:k], re.S), t[j:k]
u = 'https://www.e-vuc.sk/bsk/zdravotnictvo/ambulantne-zdravotnicke-zariadenia/malacky.html?page_id=60165'
for lvl in range(4):
    t = get(u); (R / f'lvl{lvl}.html').write_text(t, encoding='utf-8')
    rr, tab = rows(t)
    log.append(f'LVL{lvl} {u} rows {len(rr)} first {[(a[-60:], re.sub("<[^>]+>|\\s+", " ", b)[:80]) for a, b in rr[:4]]} pag {sorted(set(re.findall(r"[?&](?:page|strana|p|offset)=\\d+", t)))[:6]}')
    if not rr:
        break
    u = html.unescape(rr[0][0])
t = get('https://www.e-vuc.sk/bsk/zdravotnictvo/ambulantna-pohotovostna-sluzba-v-bsk.html?page_id=127099'); (R / 'aps.html').write_text(t, encoding='utf-8')
rr, _ = rows(t); log.append(f'APS rows {len(rr)} {[(a[-50:], re.sub("<[^>]+>|\\s+", " ", b)[:80]) for a, b in rr[:3]]}')
if rr:
    t2 = get(html.unescape(rr[0][0])); (R / 'aps_det.html').write_text(t2, encoding='utf-8')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
