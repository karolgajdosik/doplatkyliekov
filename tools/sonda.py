import re, urllib.request, urllib.parse, pathlib, json, html
UA = {'User-Agent': 'Mozilla/5.0 (doplatkyliekov.sk data updater)'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u, data=None, t=120, binary=False):
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=UA), timeout=t) as r:
                d = r.read(); return (d if binary else d.decode('utf-8', 'replace')), r.geturl()
        except Exception as e:
            log.append(f'ERR {k} {u[:140]} {e}')
    return (b'' if binary else ''), u
def links(t, pat):
    out = []
    for a, b in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', b))).strip()
        if re.search(pat, a + ' ' + b, re.I):
            out.append((a, b[:90]))
    return list(dict.fromkeys(out))
# ŠÚKL verejné úložisko
t, f = get('https://www.sukl.sk/o-nas/databazy-a-servis/datove-archivy-a-zoznamy'); (R / 'sukl_arch.html').write_text(t, encoding='utf-8')
i = t.find('<main'); m = t[i:] if i > 0 else t
log.append('SUKL arch: ' + str(links(m, r'.')[:45]))
# Dôvera vyhľadávanie lekárov
t, f = get('https://poskytovatelia.dovera.sk/vyhladavanie'); (R / 'dov_lek.html').write_text(t, encoding='utf-8')
js = re.findall(r'src="([^"]+\.js[^"]*)"', t)
log.append(f'DOV lek {f} {len(t)} js {js[:6]} api {sorted(set(re.findall(r"[\"\x27](/?api/[A-Za-z0-9/_-]+)", t)))[:20]}')
for s in js[:4]:
    tj, _ = get(urllib.parse.urljoin(f, s))
    log.append(f'  js {s[:60]} {len(tj)} api: {sorted(set(re.findall(r"[\"\x27`](https?://[A-Za-z0-9./_-]*api[A-Za-z0-9./_-]*|/api/[A-Za-z0-9/_{}$.-]+)", tj)))[:25]}')
# VšZP zoznam zmluvných lekárov
t, f = get('https://www.vszp.sk/zoznam-zmluvnych-lekarov/'); (R / 'vszp_lek.html').write_text(t, encoding='utf-8')
log.append(f'VSZP lek {f} {len(t)} forms {re.findall(r"<form[^>]*>", t)[:3]} xls {links(t, r"xls|csv|stiahn|export")[:10]} api {sorted(set(re.findall(r"[\"\x27](/[A-Za-z0-9/_-]*(?:api|ajax|json|search)[A-Za-z0-9/_.-]*)", t)))[:15]}')
# Union vyhľadávanie lekára
t, f = get('https://www.union.sk/pomahame-vam-najst-lekara'); log.append(f'UNION lek {f} {len(t)} ' + str(links(t, r'lekár|lekar|vyhľad|xls|zoznam')[:12]))
# Dietetické potraviny – časti A a C
for n, u in [('dp_A', 'https://cloud.health.gov.sk/s/WTj7b7fCXoms9H8/download'), ('dp_C', 'https://cloud.health.gov.sk/s/QP9g8d4acKCX6pZ/download')]:
    d, _ = get(u, binary=True, t=200)
    (R / n).write_bytes(d); log.append(f'{n} {len(d)} {d[:4]!r}')
# Dôvera benefity
t, f = get('https://www.dovera.sk/poistenec/benefity'); (R / 'dov_ben.html').write_text(t, encoding='utf-8')
log.append(f'DOV ben {f} {len(t)} ' + str(len(links(t, r'/poistenec/benefity/vsetky/'))))
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
