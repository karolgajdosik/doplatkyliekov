"""Jednorazové stiahnutie dát ŠÚKL na preskúmanie štruktúry."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_data import fetch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "raw" / "sukl"
OUT.mkdir(parents=True, exist_ok=True)
log = []
S = "https://www.sukl.sk/hlavna-stranka/slovenska-verzia/databazy-a-servis/vyhladavanie-liekov-zdravotnickych-pomocok-a-zmien-v-liekovej-databaze/vyhladavanie-v-databaze-registrovanych-liekov?page_id=242"
urls = {
    "prerusenia.csv": "https://portal.sukl.sk/PreruseniePublic/?act=PrerusenieOznList&export=csv",
    "prerusenia_list.html": "https://portal.sukl.sk/PreruseniePublic/?act=PrerusenieOznList&order=-1",
    "hladanie.html": S,
    "hladanie_kod.html": S + "&lie_kod=94586",
    "hladanie_nazov.html": S + "&lie_nazov=Concor",
    "datagov_search.json": "https://data.slovensko.sk/api/3/action/package_search?q=liekov%20registr%C3%A1ciou",
    "datagovsk_search.json": "https://data.gov.sk/api/3/action/package_search?q=sukl",
}
for name, url in urls.items():
    try:
        data = fetch(url, attempts=4)
        (OUT / name).write_bytes(data)
        log.append(f"OK   {len(data):>9} {name}")
    except Exception as e:  # noqa: BLE001
        log.append(f"FAIL {name} {e}")
(OUT / "LOG.txt").write_text("\n".join(log) + "\n")
print("\n".join(log))
