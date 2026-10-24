"""Jednorazové stiahnutie príloh zoznamu kategorizovaných liekov na preskúmanie štruktúry."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_data import fetch  # noqa: E402

BASE = "https://www.health.gov.sk/Zdroje?/Sources/kategorizacia/zkl/"
OUT = Path(__file__).resolve().parent.parent / "raw"
log = []

def get(folder, name):
    url = BASE + f"{folder}/{name}"
    try:
        data = fetch(url, attempts=8)
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        (OUT / folder / name).write_bytes(data)
        log.append(f"OK   {len(data):>9} {folder}/{name}  head={data[:4]!r}")
    except Exception as e:  # noqa: BLE001
        log.append(f"FAIL {folder}/{name} {e}")

months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 12)]
for y, m in months:
    get(f"{y}{m:02d}", f"cast_A_zoznam_liekov_N_k_01_{m:02d}_{y}.xlsx")

for y, m in [(2026, 10), (2026, 11)]:
    f = f"{y}{m:02d}"
    s = f"k_01_{m:02d}_{y}"
    for name in [f"ind_obmedzenia_kody_{s}.xlsx", f"zoznam_IO_{s}.xlsx", f"zoznam_IO_po_produktoch_{s}.xlsx",
                 f"cast_B_ind_obmedzenia_{s}.docx", "cast_C_vysvetlivky_skratiek.xlsx", "cast_D_skr_liek_for.xlsx",
                 "cast_E_kody_ATC.xlsx", "cast_F_staty_vyrob.xlsx", "cast_G_skr_vyrob.xlsx", "cast_H_skr_lek.docx",
                 "cast_J_Zoznam-uhradovych-skupin.xlsx"]:
        get(f, name)

(OUT / "LOG.txt").write_text("\n".join(log) + "\n")
print("\n".join(log))
