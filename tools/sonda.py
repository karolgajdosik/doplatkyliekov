import urllib.request, pathlib, re
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
        return r.read().decode('utf-8', 'replace')
h = get('https://www.union.sk/union-kontakty/pobocky/'); (R / 'u_list.html').write_text(h, encoding='utf-8')
links = list(dict.fromkeys(re.findall(r'href="((?:https://www\.union\.sk)?/union-kontakty/pobocky/[a-z0-9-]+/?)"', h)))
for i, l in enumerate(links[:2]):
    (R / f'u_det{i}.html').write_text(get(l if l.startswith('http') else 'https://www.union.sk' + l), encoding='utf-8')
