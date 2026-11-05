import urllib.request, pathlib
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
for n, u in [('dov_det', 'https://www.dovera.sk/pobocky/38-banovce-nad-bebravou'), ('dov_p2', 'https://www.dovera.sk/pobocky?page=2'),
             ('union_k', 'https://www.union.sk/union-kontakty/'), ('vszp_det', 'https://www.vszp.sk/kontaktne-miesta/trenciansky-kraj/banovce-nad-bebravou.html')]:
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
                (R / (n + '.html')).write_bytes(r.read()); break
        except Exception as e:
            print(n, e)
