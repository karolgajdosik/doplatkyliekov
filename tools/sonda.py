import re, urllib.request, pathlib, time, html, json
UA = {'User-Agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, binary=False):
    time.sleep(1.0)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            d = r.read(); return r.geturl(), (d if binary else d.decode('utf-8', 'replace'))
    except Exception as e:
        log.append(f'ERR {u} {e}'); return '', ''
def save(name, u, kw):
    f, t = get(u)
    (R / f'{name}.html').write_text(t or '')
    links = sorted(set(re.findall(r'href="([^"]+)"', t or '')))
    hit = [l for l in links if re.search(kw, l, re.I)]
    log.append(f'== {name} {u} -> {f} len={len(t or "")}\n   ' + '\n   '.join(hit[:40]))
    return t
save('dov', 'https://www.dovera.sk/cakacie-listiny', r'cakac|xls|csv|pdf|api')
save('dov2', 'https://www.dovera.sk/poistenec/cakacie-listiny', r'cakac|xls|csv|pdf|api')
save('vszp', 'https://www.vszp.sk/poistenci/zdravotna-starostlivost/cakacie-listiny/', r'cakac|xls|csv|pdf')
save('union', 'https://www.union.sk/cakacie-listiny/', r'cakac|xls|csv|pdf')
save('union2', 'https://www.union.sk/zoznam-cakatelov/', r'cakac|xls|csv|pdf')
save('udzs', 'https://www.udzs-sk.sk/', r'cakac|zoznam-poist|xls')
save('nczi', 'https://www.nczisk.sk/Statisticke_vystupy/Tematicke_statisticke_vystupy/Lieky_a_zdravotnicke_pomocky/Pages/default.aspx', r'liek|xls|pdf')
save('nczi2', 'https://www.nczisk.sk/Statisticke_vystupy/Pages/default.aspx', r'liek|spotreb')
save('nczi3', 'https://data.nczisk.sk/', r'liek|spotreb|xls|csv')
save('mz', 'https://www.health.gov.sk/', r'kupel')
save('sukl', 'https://www.sukl.sk/hlavna-stranka/slovenska-verzia/pomocne-stranky/detail-lieku?page_id=386&lie_id=20126', r'spc|pil|verejne|\.pdf|\.doc')
f, t = get('https://www.sukl.sk/hlavna-stranka/slovenska-verzia/databazy-a-servis/vyhladavanie-liekov-zdravotnickych-pomocok-a-zmien-v-liekovej-databaze?page_id=242')
(R / 'sukl_search.html').write_text(t or ''); log.append('sukl search ' + f + ' ' + str(sorted(set(re.findall(r'href="([^"]*(?:detail|lie_id|spc)[^"]*)"', t or '')))[:20]))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
