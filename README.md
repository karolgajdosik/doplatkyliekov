# doplatkyliekov.sk

Vyhľadávač lacnejších liekov s rovnakou účinnou látkou, silou a balením. Zobrazuje doplatok pacienta podľa úradného Zoznamu kategorizovaných liekov Ministerstva zdravotníctva SR.

## Štruktúra

- `site/index.html` – hlavná stránka s vyhľadávačom
- `site/data.json` – ľahké dáta pre vyhľadávač
- `data/` – všetky spracované dáta: `full.json` (aktuálny zoznam so všetkými údajmi), `ref.json` (číselníky ATC, výrobcov, štátov, odborností a indikačných obmedzení), `next.json` (zoznam na budúci mesiac), `history/` (ceny po mesiacoch), `vypadky.json` (stav dodávok podľa ŠÚKL)
- `scripts/build_data.py` – stiahne zoznam MZ SR s prílohami a hlásenia ŠÚKL a vytvorí `data/` a `site/data.json`
- `scripts/build_pages.py` – z `data/` vygeneruje podstránky `/liek/…`, `/latka/…`, `/skupina/…`, `/skupiny/`, `/lieky/`, `/zmeny/`, `/vypadky/`, `/ochranny-limit/`, `404.html` a `sitemap.xml` (iba štandardná knižnica Pythonu)
- `.github/workflows/update-data.yml` – automatická aktualizácia dát každý mesiac

## Nasadenie na Cloudflare Pages

1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → vyber tento repozitár.
2. Nastavenia buildu:
   - Framework preset: **None**
   - Build command: `python3 scripts/build_pages.py`
   - Build output directory: `site`
3. **Save and Deploy**.
4. V projekte → **Custom domains** → pridaj `doplatkyliekov.sk` (a prípadne `www.doplatkyliekov.sk`).

Každý push do vetvy `main` web automaticky nasadí znova.

## Aktualizácia dát

GitHub Action beží každý deň. Stiahne zoznam ministerstva (aj ten na budúci mesiac, keď je zverejnený), doplní históriu a aktualizuje výpadky zo ŠÚKL. Ak sa niečo zmenilo, uloží dáta a Cloudflare web nasadí sám.

Ručne: GitHub → **Actions** → *Aktualizácia zoznamu liekov* → **Run workflow**.

Lokálne:

```bash
pip install openpyxl
python scripts/build_data.py                    # stiahne najnovší zoznam
python scripts/build_data.py --raw cesta/k/raw    # použije lokálne stiahnuté súbory (priečinky RRRRMM)
python scripts/build_pages.py                    # vygeneruje stránky do site/
```

## Upozornenie

Doplatok v zozname je maximálny. Lekáreň môže dať zľavu. Web slúži na informáciu a nenahrádza radu lekára ani lekárnika.
