"""Ilustračné obrázky liekov (SVG) podľa liekovej formy, skupiny ATC, sily a balenia.

Nie sú to fotky balení: tvar určuje lieková forma zo zoznamu MZ SR, farbu skupina ATC.
  svg = illustration(pack, atc, label)   # reťazec <svg …> (viewBox 400×300)
"""
import html
import re

# farby podľa hlavnej skupiny ATC: (hlavná, svetlá)
ATC_COLORS = {
    "A": ("#f5a524", "#ffe2a8"),  # tráviaci trakt a metabolizmus
    "B": ("#e5484d", "#ffc9c9"),  # krv
    "C": ("#ef5d8f", "#ffd0e1"),  # srdce a cievy
    "D": ("#e8a87c", "#fde3d0"),  # koža
    "G": ("#c084fc", "#ecd9ff"),  # urogenitálny systém
    "H": ("#a78bfa", "#e2d9ff"),  # hormóny
    "J": ("#2dd4bf", "#c5f5ec"),  # infekcie
    "L": ("#8b5cf6", "#ddd0ff"),  # onkológia, imunita
    "M": ("#60a5fa", "#d3e6ff"),  # svaly a kosti
    "N": ("#6366f1", "#d9daff"),  # nervový systém
    "P": ("#84cc16", "#e3f7c3"),  # parazity
    "R": ("#38bdf8", "#cdeefe"),  # dýchanie
    "S": ("#22d3ee", "#c8f4fb"),  # zmysly
    "V": ("#94a3b8", "#e2e8f0"),  # rôzne
}
ATC_NAMES = {"A": "tráviaci trakt a metabolizmus", "B": "krv", "C": "srdce a cievy", "D": "koža", "G": "močové a pohlavné orgány",
             "H": "hormóny", "J": "infekcie", "L": "onkológia a imunita", "M": "svaly a kosti", "N": "nervový systém",
             "P": "parazity", "R": "dýchanie", "S": "oči a uši", "V": "rôzne"}

FORM_NAMES = {"tablet": "tablety", "capsule": "kapsuly", "bottle": "roztok alebo sirup", "drops": "kvapky", "eye": "očné kvapky",
              "vial": "injekcia", "pen": "injekčné pero", "inhaler": "inhalátor", "nasal": "nosový sprej", "tube": "masť, krém alebo gél",
              "patch": "náplasť", "sachet": "prášok alebo granulát vo vrecku", "supp": "čapíky", "other": "liek"}


def form_of(pack):
    p = (pack or "").lower()
    w = p.split()
    a, b = (w + ["", ""])[:2]
    if a in ("tbl", "tablety") or (a == "lyo" and b in ("por", "slg")):
        return "tablet"
    if a == "cps":
        return "capsule"
    if a in ("emp",):
        return "patch"
    if a == "sup":
        return "supp"
    if a in ("crm", "ung", "gel", "pst") and b != "ist":
        return "tube"
    if a == "int" or b in ("opo", "opu", "ope", "osd", "ots", "oph"):
        return "eye"
    if b in ("nas", "nao", "nau"):
        return "nasal"
    if b in ("ihl", "inh", "ido", "icd") or (a == "aer" and b == "ora"):
        return "inhaler"
    if "pero" in p or " pen" in p or "napl.pero" in p:
        return "pen"
    if a in ("gtt", "gto", "gte"):
        return "drops"
    if a in ("gra", "gro", "gru") or (a in ("plv", "plo") and ("vre" in p or b in ("sps", "por") and "fľ" not in p)):
        return "sachet"
    if a == "imp" or b.startswith("i") or a in ("con", "dis", "plc", "pci", "lyo", "kit") or b in ("sif", "suf", "sul"):
        return "vial"
    if a in ("sir", "sol", "sus", "liq", "plu", "plv", "emu", "add", "shp", "lum", "plq", "aer"):
        return "bottle"
    return "other"


def _tablet(c, l):
    cells = "".join(f'<circle cx="{150 + (i % 4) * 40}" cy="{98 + (i // 4) * 44}" r="14" fill="#fff" stroke="{c}" stroke-opacity=".35" stroke-width="2"/>'
                    for i in range(8))
    return (f'<g transform="rotate(-8 200 130)"><rect x="118" y="70" width="164" height="118" rx="16" fill="{l}" stroke="{c}" stroke-width="3"/>{cells}</g>'
            f'<g transform="translate(262 186) rotate(18)"><ellipse rx="34" ry="22" fill="#fff" stroke="{c}" stroke-width="3"/>'
            f'<path d="M0 -20 V20" stroke="{c}" stroke-width="3" stroke-linecap="round"/></g>')


def _capsule(c, l):
    def cap(x, y, r):
        return (f'<g transform="translate({x} {y}) rotate({r})"><rect x="-60" y="-22" width="120" height="44" rx="22" fill="#fff" stroke="{c}" stroke-width="3"/>'
                f'<path d="M0 -22 H38 A22 22 0 0 1 38 22 H0 Z" fill="{c}"/></g>')
    return cap(170, 120, -28) + cap(236, 176, 14)


def _bottle(c, l):
    return (f'<rect x="168" y="66" width="44" height="26" rx="6" fill="{c}"/><path d="M160 96 h60 l14 28 v92 a14 14 0 0 1 -14 14 h-60 a14 14 0 0 1 -14 -14 v-92 z" fill="{l}" stroke="{c}" stroke-width="3"/>'
            f'<rect x="156" y="146" width="68" height="46" rx="6" fill="#fff"/><path d="M168 162 h44 M168 176 h30" stroke="{c}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M244 180 h44 l-6 46 h-32 z" fill="#fff" stroke="{c}" stroke-width="3"/><path d="M250 196 h32" stroke="{c}" stroke-width="2"/>')


def _drops(c, l):
    return (f'<path d="M188 52 q12 -22 24 0 v34 h-24 z" fill="{c}"/><rect x="178" y="86" width="44" height="22" rx="5" fill="{c}"/>'
            f'<rect x="166" y="108" width="68" height="112" rx="16" fill="{l}" stroke="{c}" stroke-width="3"/><rect x="174" y="140" width="52" height="40" rx="6" fill="#fff"/>'
            f'<path d="M270 150 q14 22 0 30 q-14 -8 0 -30z" fill="{c}"/><path d="M290 190 q10 16 0 22 q-10 -6 0 -22z" fill="{c}" opacity=".6"/>')


def _eye(c, l):
    return (f'<path d="M190 60 l10 -18 l10 18 v26 h-20 z" fill="#fff" stroke="{c}" stroke-width="3"/><rect x="178" y="86" width="44" height="18" rx="5" fill="{c}"/>'
            f'<rect x="170" y="104" width="60" height="100" rx="14" fill="{l}" stroke="{c}" stroke-width="3"/>'
            f'<path d="M246 170 q32 -30 64 0 q-32 30 -64 0z" fill="#fff" stroke="{c}" stroke-width="3"/><circle cx="278" cy="170" r="10" fill="{c}"/>')


def _vial(c, l):
    return (f'<rect x="132" y="80" width="56" height="20" rx="4" fill="{c}"/><rect x="138" y="100" width="44" height="12" fill="#cfd8dc"/>'
            f'<path d="M134 112 h52 v96 a12 12 0 0 1 -12 12 h-28 a12 12 0 0 1 -12 -12 z" fill="{l}" stroke="{c}" stroke-width="3"/><rect x="140" y="150" width="40" height="34" rx="4" fill="#fff"/>'
            f'<g transform="translate(262 150) rotate(-35)"><rect x="-14" y="-70" width="28" height="110" rx="5" fill="#fff" stroke="{c}" stroke-width="3"/>'
            f'<rect x="-10" y="-20" width="20" height="56" fill="{l}"/><path d="M0 40 v34" stroke="#9aa5ad" stroke-width="3"/><rect x="-22" y="-82" width="44" height="12" rx="3" fill="{c}"/>'
            f'<path d="M-8 -50 h8 M-8 -30 h8 M-8 -10 h8" stroke="{c}" stroke-width="2"/></g>')


def _pen(c, l):
    return (f'<g transform="translate(200 150) rotate(-24)"><rect x="-120" y="-20" width="190" height="40" rx="20" fill="#fff" stroke="{c}" stroke-width="3"/>'
            f'<rect x="70" y="-16" width="44" height="32" rx="10" fill="{c}"/><rect x="-60" y="-12" width="60" height="24" rx="6" fill="{l}"/>'
            f'<rect x="-140" y="-10" width="24" height="20" rx="4" fill="{c}"/><path d="M-152 0 h-16" stroke="#9aa5ad" stroke-width="3"/></g>')


def _inhaler(c, l):
    return (f'<rect x="176" y="54" width="56" height="120" rx="14" fill="{l}" stroke="{c}" stroke-width="3"/>'
            f'<path d="M150 150 h96 a10 10 0 0 1 10 10 v40 a10 10 0 0 1 -10 10 h-70 a26 26 0 0 1 -26 -26 z" fill="#fff" stroke="{c}" stroke-width="3"/>'
            f'<rect x="138" y="168" width="22" height="34" rx="6" fill="{c}"/><path d="M110 176 q-14 9 0 18 M96 170 q-22 15 0 30" stroke="{c}" stroke-width="3" fill="none" stroke-linecap="round" opacity=".6"/>')


def _nasal(c, l):
    return (f'<path d="M192 48 q8 -14 16 0 v40 h-16 z" fill="#fff" stroke="{c}" stroke-width="3"/><rect x="172" y="88" width="56" height="16" rx="4" fill="{c}"/>'
            f'<rect x="164" y="104" width="72" height="116" rx="18" fill="{l}" stroke="{c}" stroke-width="3"/><rect x="174" y="140" width="52" height="40" rx="6" fill="#fff"/>'
            f'<circle cx="240" cy="40" r="4" fill="{c}" opacity=".6"/><circle cx="252" cy="54" r="3" fill="{c}" opacity=".5"/><circle cx="232" cy="28" r="3" fill="{c}" opacity=".4"/>')


def _tube(c, l):
    return (f'<g transform="translate(200 150) rotate(-18)"><path d="M-110 -30 h170 l30 14 v32 l-30 14 h-170 z" fill="{l}" stroke="{c}" stroke-width="3"/>'
            f'<path d="M-110 -30 v60" stroke="{c}" stroke-width="8"/><rect x="90" y="-14" width="34" height="28" rx="5" fill="{c}"/>'
            f'<rect x="-60" y="-16" width="90" height="32" rx="6" fill="#fff"/><path d="M-50 -4 h60 M-50 6 h40" stroke="{c}" stroke-width="3" stroke-linecap="round"/></g>')


def _patch(c, l):
    return (f'<g transform="rotate(-10 200 140)"><rect x="120" y="70" width="160" height="140" rx="26" fill="#fff" stroke="{c}" stroke-width="3"/>'
            f'<rect x="146" y="96" width="108" height="88" rx="14" fill="{l}" stroke="{c}" stroke-dasharray="6 6" stroke-width="2"/></g>'
            f'<path d="M262 202 l26 26" stroke="{c}" stroke-width="3"/><path d="M262 202 q20 -4 30 10" stroke="{c}" stroke-width="3" fill="none"/>')


def _sachet(c, l):
    zig = "".join(f"l7 -8 l7 8" for _ in range(9))
    return (f'<path d="M140 70 {zig} v150 h-126 z" fill="{l}" stroke="{c}" stroke-width="3" transform="rotate(-6 200 150)"/>'
            f'<rect x="160" y="120" width="80" height="50" rx="8" fill="#fff" transform="rotate(-6 200 150)"/>'
            f'<g fill="{c}"><circle cx="276" cy="206" r="4"/><circle cx="288" cy="214" r="3"/><circle cx="268" cy="218" r="3"/><circle cx="282" cy="226" r="4"/></g>')


def _supp(c, l):
    def s(x, y, r):
        return (f'<g transform="translate({x} {y}) rotate({r})"><path d="M-18 40 v-40 q0 -40 18 -52 q18 12 18 52 v40 z" fill="#fff" stroke="{c}" stroke-width="3"/>'
                f'<path d="M-18 24 h36" stroke="{l}" stroke-width="10"/></g>')
    return s(170, 150, -16) + s(228, 160, 12)


def _other(c, l):
    return f'<rect x="150" y="80" width="100" height="130" rx="18" fill="{l}" stroke="{c}" stroke-width="3"/><path d="M200 120 v50 M175 145 h50" stroke="{c}" stroke-width="12" stroke-linecap="round"/>'


DRAW = {"tablet": _tablet, "capsule": _capsule, "bottle": _bottle, "drops": _drops, "eye": _eye, "vial": _vial, "pen": _pen,
        "inhaler": _inhaler, "nasal": _nasal, "tube": _tube, "patch": _patch, "sachet": _sachet, "supp": _supp, "other": _other}


def label_of(pack):
    """Krátky popis „10 mg · 30 ks“ z textu balenia."""
    p = (pack or "")
    m = re.search(r"(\d+)\s*(dávok|vstrekov|inhalácií)", p)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m = re.search(r"(\d+)\s*x\s*([\d,.]+\s*(?:mg|µg|g|ml|IU|U|mmol)(?:/[\d,.]+\s*(?:mg|µg|g|ml))?)", p)
    if m:
        return f"{m.group(2)} · {m.group(1)} ks"
    m = re.search(r"\b1x([\d,.]+\s*(?:ml|g))", p)
    if m:
        return m.group(1)
    return ""


def illustration(pack, atc, label=None, uid="i"):
    form = form_of(pack)
    c, l = ATC_COLORS.get((atc or "V")[:1], ATC_COLORS["V"])
    lab = html.escape(label if label is not None else label_of(pack))
    art = DRAW[form](c, l)
    title = f"Ilustračný obrázok: {FORM_NAMES[form]}"
    chip = (f'<g transform="translate(200 262)"><rect x="{-max(60, len(lab) * 5.4 + 18)}" y="-17" width="{2 * max(60, len(lab) * 5.4 + 18)}" height="34" rx="17" fill="#05090b" fill-opacity=".75" stroke="{c}" stroke-opacity=".6" stroke-width="1.5"/>'
            f'<text text-anchor="middle" y="6" font-family="JetBrains Mono, monospace" font-size="16" font-weight="600" fill="#fff">{lab}</text></g>') if lab else ""
    return (f'<svg class="illus" viewBox="0 0 400 300" role="img" aria-label="{html.escape(title)}" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><radialGradient id="g{uid}" cx="50%" cy="46%" r="62%"><stop offset="0" stop-color="{c}" stop-opacity=".55"/><stop offset=".6" stop-color="{c}" stop-opacity=".12"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
            f'<pattern id="d{uid}" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.2" fill="#fff" opacity=".10"/></pattern></defs>'
            f'<rect width="400" height="300" rx="24" fill="#0d1619"/><rect width="400" height="300" rx="24" fill="url(#d{uid})"/>'
            f'<rect width="400" height="300" rx="24" fill="url(#g{uid})"/><rect x="1" y="1" width="398" height="298" rx="23" fill="none" stroke="{c}" stroke-opacity=".35" stroke-width="2"/>'
            f'{art}{chip}</svg>')
