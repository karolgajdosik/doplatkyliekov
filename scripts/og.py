"""Náhľadové obrázky (Open Graph, 1200 × 630) pre zdieľanie na sociálnych sieťach a v aplikáciách na správy."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "assets-src" / "fonts"
W, H = 1200, 630
BG = (5, 9, 11)
ACC = (69, 240, 192)
INK = (236, 248, 244)
MUTED = (163, 184, 178)
SAVE = (255, 178, 107)

_cache = {}


def font(name, size):
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONTS / name), size)
    return _cache[key]


def _background():
    if "bg" in _cache:
        return _cache["bg"]
    im = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(glow)
    g.ellipse([-260, -320, 620, 420], fill=(16, 92, 72))
    g.ellipse([760, -300, 1500, 300], fill=(18, 52, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    im = Image.blend(im, glow, 0.85)
    d = ImageDraw.Draw(im)
    for x in range(30, W, 30):          # jemná bodová mriežka
        for y in range(30, H, 30):
            d.point((x, y), fill=(28, 46, 44))
    # logo: kapsula + názov
    x0, y0 = 64, 58
    d.rounded_rectangle([x0, y0, x0 + 64, y0 + 34], radius=17, outline=ACC, width=3)
    d.rounded_rectangle([x0, y0, x0 + 34, y0 + 34], radius=17, fill=ACC)
    d.rectangle([x0 + 17, y0, x0 + 31, y0 + 34], fill=ACC)
    f = font("Unbounded-Bold.ttf", 30)
    d.text((x0 + 84, y0 + 1), "doplatky", font=f, fill=INK)
    wx = x0 + 84 + d.textlength("doplatky", font=f)
    d.text((wx, y0 + 1), "liekov", font=f, fill=ACC)
    d.text((wx + d.textlength("liekov", font=f), y0 + 1), ".sk", font=f, fill=INK)
    d.line([64, H - 92, W - 64, H - 92], fill=(30, 52, 48), width=2)
    d.text((64, H - 70), "Porovnanie doplatkov za lieky hradené poisťovňou · údaje MZ SR", font=font("Onest-Medium.ttf", 26), fill=MUTED)
    _cache["bg"] = im
    return im


def _wrap(d, text, f, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while d.textlength(lines[-1] + "…", font=f) > width and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def render(out, eyebrow, title, sub="", big="", big_label="", big_color=SAVE):
    im = _background().copy()
    d = ImageDraw.Draw(im)
    right = 760 if big else W - 64
    d.text((64, 150), eyebrow.upper(), font=font("Onest-Bold.ttf", 24), fill=ACC)
    size = 64
    while True:
        f = font("Unbounded-Bold.ttf", size)
        lines = _wrap(d, title, f, right - 64, 3)
        if size <= 40 or (len(lines) <= 2 and all(d.textlength(x, font=f) <= right - 64 for x in lines)):
            break
        size -= 6
    y = 196
    for ln in lines:
        d.text((64, y), ln, font=f, fill=INK)
        y += int(size * 1.18)
    if sub:
        for ln in _wrap(d, sub, font("Onest-Medium.ttf", 30), right - 64, 2):
            d.text((64, y + 14), ln, font=font("Onest-Medium.ttf", 30), fill=MUTED)
            y += 42
    if big:
        bx = 800
        d.rounded_rectangle([bx, 170, W - 64, 450], radius=28, fill=(13, 24, 27), outline=(40, 70, 64), width=2)
        fb = font("Unbounded-Bold.ttf", 58)
        while d.textlength(big, font=fb) > W - 64 - bx - 48 and fb.size > 30:
            fb = font("Unbounded-Bold.ttf", fb.size - 4)
        d.text((bx + 32, 250), big, font=fb, fill=big_color)
        if big_label:
            for i, ln in enumerate(_wrap(d, big_label, font("Onest-Medium.ttf", 26), W - 64 - bx - 64, 2)):
                d.text((bx + 32, 350 + i * 34), ln, font=font("Onest-Medium.ttf", 26), fill=MUTED)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out.with_suffix(".jpg"), quality=86, optimize=True, progressive=True)
