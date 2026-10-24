# doplatkyliekov.sk

Vyhľadávač lacnejších liekov s rovnakou účinnou látkou, silou a balením. Zobrazuje doplatok pacienta podľa úradného Zoznamu kategorizovaných liekov Ministerstva zdravotníctva SR.

## Štruktúra

- `site/index.html` – hlavná stránka s vyhľadávačom
- `site/data.json` – spracované dáta o liekoch
- `scripts/build_data.py` – stiahne aktuálny zoznam z health.gov.sk a vytvorí `data.json`
- `scripts/build_pages.py` – z `data.json` vygeneruje podstránky `/liek/…`, `/latka/…`, `/lieky/`, `404.html` a `sitemap.xml` (iba štandardná knižnica Pythonu)
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

GitHub Action beží každý deň koncom a začiatkom mesiaca. Keď nájde nový zoznam, uloží nový `data.json` a Cloudflare web nasadí sám.

Ručne: GitHub → **Actions** → *Aktualizácia zoznamu liekov* → **Run workflow**.

Lokálne:

```bash
pip install openpyxl
python scripts/build_data.py                    # stiahne najnovší zoznam
python scripts/build_data.py cesta/k/suboru.xlsx  # použije stiahnutý súbor
```

## Upozornenie

Doplatok v zozname je maximálny. Lekáreň môže dať zľavu. Web slúži na informáciu a nenahrádza radu lekára ani lekárnika.
