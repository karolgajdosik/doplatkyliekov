import urllib.request, pathlib
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
B = 'https://www.sukl.sk/pre-odbornikov-a-firmy/dostupnost-a-kvalita-liekov/kvalita-liekov/oznamy-o-stiahnuti-liekov/'
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
for s in ['stiahnutie-lieku-fingolimod-zentiva-ztrhu', 'stiahnutie-liekov-plenvu-a-moviprep-ztrhu', 'stiahnutie-lieku-tyverb-250-mg-ztrhu']:
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + s, headers=UA), timeout=60) as r:
                (R / (s + '.html')).write_bytes(r.read()); break
        except Exception as e:
            print(e)
