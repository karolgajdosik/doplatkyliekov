import re, urllib.request, pathlib, subprocess, shutil
UA = {'User-Agent': 'doplatkyliekov.sk data updater'}
R = pathlib.Path('raw'); R.mkdir(exist_ok=True)
log = []
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            return r.geturl(), r.read().decode('utf-8', 'replace')
    except Exception as e:
        return 'ERR ' + str(e), ''
for u in ['https://www.e-vuc.sk/bsk/x.html?page_id=156278', 'https://www.e-vuc.sk/bsk/?page_id=156278',
          'https://www.e-vuc.sk/index.php?page_id=156278', 'https://www.e-vuc.sk/?page_id=156278']:
    f, t = get(u)
    log.append(f'{u} -> {f[:160]} len={len(t)} gps={bool(re.search(r"maps.google.com/.q=48.50", t))} title={re.findall(r"<title>(.*?)</title>", t, re.S)[:1]}')
def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3000)
    log.append('$ ' + cmd + '\n' + (p.stdout + p.stderr)[-2500:])
run('pip install -q openpyxl==3.1.5')
run('python3 scripts/build_ambulancie.py --kraj bsk --max 40 --delay 0.1')
run('python3 scripts/build_vyhody.py')
run('python3 scripts/build_dp.py')
run('python3 scripts/build_register.py')
for f in ['data/lekari.json', 'data/lekari_gps.json', 'data/vyhody.json', 'data/dp.json', 'data/register.json', 'vyhody_zmena.md']:
    p = pathlib.Path(f)
    if p.exists(): shutil.copy(p, R / p.name)
(R / 'log.txt').write_text('\n'.join(log), encoding='utf-8'); print('\n'.join(log))
