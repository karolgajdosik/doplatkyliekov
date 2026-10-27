"""3D ilustrácie liekov: výber obrázka podľa liekovej formy a skupiny ATC, HTML pre stránky.

Obrázky sú v site/img3d/<forma>-<písmeno ATC>.webp (vyrenderované nástrojom v tools/3d).
  python3 scripts/illus3d.py --jobs        # vypíše chýbajúce kombinácie pre tools/3d/run.js
  python3 scripts/illus3d.py --webp DIR    # PNG z DIR → site/img3d/*.webp
"""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from illus import form_of, label_of, FORM_NAMES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "site" / "img3d"
try:
    PAL = json.loads((ROOT / "tools" / "3d" / "pal.json").read_text(encoding="utf-8"))
except OSError:
    PAL = {"V": ["#94a3b8", "#45f0c0"]}
_have = None


def have():
    global _have
    if _have is None:
        _have = {p.stem for p in IMG.glob("*.webp")}
    return _have


def image_of(pack, atc):
    form, letter = form_of(pack), (atc or "V")[:1]
    for name in (f"{form}-{letter}", f"other-{letter}", f"{form}-V", "other-V"):
        if name in have():
            return f"/img3d/{name}.webp", form
    return None, form


def color_of(atc):
    return PAL.get((atc or "V")[:1], PAL["V"])[0]


def figure(pack, atc, cls="drug3d", label=None, alt_name="", eager=False, note="Ilustračný obrázok", alt=None):
    src, form = image_of(pack, atc)
    if not src:
        return ""
    lab = label if label is not None else label_of(pack)
    if alt is None:
        alt = f"Ilustračný obrázok: {FORM_NAMES.get(form, 'liek')}" + (f" – {alt_name}" if alt_name else "")
    return (f'<figure class="{cls}" style="--dc:{color_of(atc)}"><img src="{src}" alt="{html.escape(alt)}" width="640" height="480"'
            f'{" fetchpriority=\"high\"" if eager else " loading=\"lazy\" decoding=\"async\""}>'
            + (f'<span class="d3-lab">{html.escape(lab)}</span>' if lab else "")
            + f'<span class="d3-note">{html.escape(note)}</span></figure>')


if __name__ == "__main__":
    if "--jobs" in sys.argv:
        d = json.loads((ROOT / "data" / "full.json").read_text(encoding="utf-8"))
        combos = {(form_of(it["pack"]), g["a"][:1]) for g in d["groups"] for it in g["i"]}
        jobs = [[f"{f}-{l}", f, *PAL.get(l, PAL["V"])] for f, l in sorted(combos) if f"{f}-{l}" not in have()]
        print(json.dumps(jobs))
    elif "--webp" in sys.argv:
        from PIL import Image
        src = Path(sys.argv[sys.argv.index("--webp") + 1])
        for f in src.glob("*.png"):
            Image.open(f).resize((640, 480), Image.LANCZOS).save(IMG / (f.stem + ".webp"), "WEBP", quality=82, method=4)
