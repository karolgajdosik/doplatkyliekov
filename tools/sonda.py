import re, urllib.request, urllib.parse, pathlib, time, html, json
UA = {'User-Agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, binary=False):
    time.sleep(1.0)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120) as r:
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
ok = 0
for u in json.load(open('tools/spc_urls.json')):
    f, t = get(u)
    spc = re.findall(r'<a[^>]+href="(https://www\.sukl\.sk/document/download[^"]+)"[^>]*>(.*?)</a>', t or '', re.S)
    ok += bool(t)
    log.append(f'{"OK " if t else "ERR"} {u} docs={[re.sub(r"<[^>]+>|\s+", " ", x[1]).strip()[:40] for x in spc][:4]}')
log.append(f'SPC slug ok {ok}/60')
save('spot', 'https://www.nczisk.sk/Statisticke_vystupy/Tematicke_statisticke_vystupy/TOP-50-liekov/Spotreba_humannych_liekov_zdravotnickych_pomocok_dietetickych_potravin_SR/Pages/default.aspx', r'xls|csv|pdf|zip')
save('ucet', 'https://www.nczisk.sk/Statisticke_vystupy/Tematicke_statisticke_vystupy/TOP-50-liekov/Pages/Ucet-poistenca-humanne-lieky-hradene-z-verejneho-zdravotneho-poistenia-v-SR.aspx', r'xls|csv|pdf|zip')
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
