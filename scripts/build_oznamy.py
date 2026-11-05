"""Oznamy ŠÚKL na webe: priradenie stiahnutí z trhu a bezpečnostných oznamov (DHPC) k liekom,
upozornenia na stránke lieku, prehľadová stránka /upozornenia-sukl/ a site/oznamy.json pre Moje lieky.

Stiahnutia sa priraďujú podľa kódu ŠÚKL z oznamu; ak ho oznam neuvádza, podľa názvu lieku z nadpisu.
DHPC sa priraďujú podľa značky (prvé slovo názvu lieku) alebo účinnej látky v nadpise.
"""
import datetime as dt
import json
import re

RECALL_DAYS = 730     # stiahnutia na stránke lieku a v Moje lieky
DHPC_DAYS = 1095      # bezpečnostné oznamy na stránke lieku
NOTIFY_DAYS = 30      # o novom stiahnutí upozorníme e-mailom/notifikáciou, ak nie je staršie
STOP = {"liek", "lieky", "liekov", "lieku", "vakcina", "vakciny", "vakcín", "obsahujuce", "obsahujuci", "infuzny", "injekcny",
        "roztok", "tablety", "tableta", "kapsuly", "sirup", "masť", "krem", "gel", "prasok", "humanny", "humanne", "nove", "nova",
        "aktualizacia", "aktualizovane", "informacia", "informacie", "riziko", "dolezite", "upozornenie", "pouzitie", "lieku"}


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _cut(iso, days):
    return (dt.date.today() - dt.timedelta(days=days)).isoformat() if iso is None else iso


def title_names(title):
    t = re.sub(r"^(Stiahnutie|Sťahovanie)\s+(hromadne pripravovan\w+\s+humánn\w+\s+)?(lieč\w+|liek\w*)\s+", "", title, flags=re.I)
    t = re.sub(r"\s+(z\s+trhu|zo?\s+slovenského\s+trhu|až\s+z\s+úrovne|z\s+úrovne).*$", "", t, flags=re.I)
    out = []
    for part in re.split(r",\s*|\s+a\s+", t):
        words = []
        for w in _norm(part).split():
            if re.search(r"\d", w):
                break
            words.append(w)
        pref = " ".join(words[:3])
        if len(pref) >= 4 and pref not in STOP:
            out.append(pref)
    return out


def dhpc_keys(title):
    head = title.split(":")[0]
    brands, substs = set(), set()
    for m in re.finditer(r"\(([^)]*)\)", head):
        for s in re.split(r",|\s+a\s+|/|;", m.group(1)):
            s = _norm(s)
            if len(s) >= 5:
                substs.add(s)
    m = re.search(r"obsahujúc\w*\s+(.+)$", re.sub(r"\([^)]*\)", "", head), re.I)
    if m:
        for s in re.split(r",|\s+a\s+|/|;", m.group(1)):
            s = _norm(s)
            if len(s) >= 5:
                substs.add(s)
    else:
        for b in re.split(r",|\s+a\s+|/|;", re.sub(r"\([^)]*\)", "", head)):
            w = _norm(b.replace("®", " ").replace("™", " ")).split()
            if w and len(w[0]) >= 4 and w[0] not in STOP:
                brands.add(w[0])
    return brands, substs


def match(sukl, products):
    """→ (recalls {kod: [oznam]}, dhpc {kod: [oznam]}); products = [(g, p)] s p['slug']."""
    rec_cut = (dt.date.today() - dt.timedelta(days=RECALL_DAYS)).isoformat()
    dh_cut = (dt.date.today() - dt.timedelta(days=DHPC_DAYS)).isoformat()
    by_kod = {p["kod"]: (g, p) for g, p in products}
    pnorm = [(_norm(p["name"]), g, p) for g, p in products]
    recalls, dhpc = {}, {}
    for r in sukl.get("stiahnutia", []):
        if (r.get("date") or "") < rec_cut:
            continue
        hits = [k for k in r.get("kody", []) if k in by_kod]
        how = "kod"
        if not hits:
            how = "nazov"
            for pref in title_names(r["title"]):
                hits += [p["kod"] for n, g, p in pnorm if n == pref or n.startswith(pref + " ")]
        for k in dict.fromkeys(hits):
            recalls.setdefault(k, []).append(dict(r, how=how))
    subst_first = {(_norm(g["s"]).split(" ") or [""])[0] for g, p in products}
    for d in sukl.get("dhpc", []):
        if (d.get("date") or "") < dh_cut:
            continue
        brands, substs = dhpc_keys(d["title"])
        # oznam o konkrétnej značke (napr. „Keppra … (levetiracetam)“) platí len pre ňu, nie pre všetky lieky s látkou;
        # podľa látky priraďujeme len oznamy, ktoré začínajú látkou („Finasterid, dutasterid: …“, „Lieky obsahujúce …“)
        lead_subst = {b for b in brands if b in subst_first}
        if brands - lead_subst:
            substs = set()
            brands = brands - lead_subst
        else:
            substs = (substs if not brands else set()) | lead_subst
            brands = set()
        for n, g, p in pnorm:
            first = n.split(" ")[0] if n else ""
            sn = _norm(g["s"])
            if first in brands or any(sn == s or sn.startswith(s + " ") for s in substs):
                dhpc.setdefault(p["kod"], []).append(d)
    return recalls, dhpc


def sk(iso):
    return f"{int(iso[8:10])}. {int(iso[5:7])}. {iso[:4]}" if iso and len(iso) >= 10 else ""


def recall_alert(r, esc):
    if r.get("vsetky"):
        scope = "Týka sa všetkých šarží tohto lieku."
    elif r.get("sarze"):
        scope = (f"Týka sa len šarží č. {esc(', '.join(r['sarze'][:8]))}. Číslo šarže nájdete na krabičke "
                 f"(označené „Lot“ alebo „č. š.“).")
    else:
        scope = "Týka sa len niektorých šarží, čísla nájdete v oznamu ŠÚKL."
    how = "" if r.get("how") == "kod" else " Priradené podľa názvu lieku v oznamu, skontrolujte silu a balenie."
    dov = f" {esc(r['dovod'])}" if r.get("dovod") else ""
    return (f'<div class="alert warn"><strong>ŠÚKL sťahuje liek z trhu ({sk(r.get("date"))})</strong>'
            f'<p>{scope}{dov} Liečbu neprerušujte bez porady s lekárom alebo lekárnikom.{how} '
            f'<a href="{esc(r["url"])}" rel="nofollow">Oznam ŠÚKL</a></p></div>')


def dhpc_alert(d, esc):
    return (f'<div class="alert"><strong>Bezpečnostný oznam výrobcu ({sk(d.get("date"))})</strong>'
            f'<p>{esc(d["title"])}. Oznam je určený najmä lekárom a lekárnikom. Ak máte otázky, poraďte sa s nimi; '
            f'liečbu sami neprerušujte. <a href="{esc(d["url"])}" rel="nofollow">Oznam na stránke ŠÚKL</a></p></div>')


def build_page(c, sukl, recalls, dhpc, by_kod):
    """Stránka /upozornenia-sukl/ a site/oznamy.json."""
    esc, page, write, crumbs, breadcrumb_ld, urls, SITE = (c["esc"], c["page"], c["write"], c["crumbs"],
                                                          c["breadcrumb_ld"], c["urls"], c["SITE"])
    rec_cut = (dt.date.today() - dt.timedelta(days=RECALL_DAYS)).isoformat()
    inv = {}
    for k, lst in recalls.items():
        for r in lst:
            inv.setdefault(r["id"], []).append(k)
    inv_d = {}
    for k, lst in dhpc.items():
        for d in lst:
            inv_d.setdefault(d["id"], []).append(k)

    def links(kods):
        ps = [by_kod[k][1] for k in kods if k in by_kod][:6]
        more = len(kods) - len(ps)
        s = ", ".join(f'<a href="/liek/{esc(p["slug"])}/">{esc(p["name"])}</a>' for p in ps)
        return (s + (f" a ďalšie ({more})" if more > 0 else "")) if s else ""

    rows = []
    for r in sukl.get("stiahnutia", [])[:60]:
        if (r.get("date") or "") < rec_cut:
            break
        l = links(inv.get(r["id"], []))
        scope = "všetky šarže" if r.get("vsetky") else ("šarže " + ", ".join(r["sarze"][:5])) if r.get("sarze") else "vybrané šarže"
        rows.append(f'<li><div class="gline"><a href="{esc(r["url"])}" rel="nofollow">{esc(r["title"])}</a>'
                    f'<span class="mono">{sk(r.get("date"))}</span><small>{esc(scope)}'
                    f'{" · " + esc(r["dovod"]) if r.get("dovod") else ""}</small>'
                    f'{"<small>V našom zozname: " + l + "</small>" if l else ""}</div></li>')
    rows_d = []
    for d in sukl.get("dhpc", [])[:40]:
        l = links(inv_d.get(d["id"], []))
        rows_d.append(f'<li><div class="gline"><a href="{esc(d["url"])}" rel="nofollow">{esc(d["title"])}</a>'
                      f'<span class="mono">{sk(d.get("date"))}</span>'
                      f'{"<small>Lieky v našom zozname: " + l + "</small>" if l else ""}</div></li>')
    crumb_items = [("Domov", "/"), ("Stiahnuté lieky a bezpečnostné oznamy", None)]
    datum = sukl.get("stiahnute")
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Podľa ŠÚKL{(' k ' + sk(datum)) if datum else ''}</p>
    <h1 class="page-h1">Stiahnuté lieky a bezpečnostné oznamy</h1>
    <p class="page-sub">Keď Štátny ústav pre kontrolu liečiv stiahne liek alebo jeho šaržu z trhu, nájdete to tu aj na stránke lieku. Ak máte liek uložený v Moje lieky so zapnutými upozorneniami, dáme vám vedieť.</p>
  </section>
  <div class="alert"><strong>Máte doma liek zo zoznamu?</strong><p>Pozrite číslo šarže na krabičke (označené „Lot“ alebo „č. š.“). Liečbu neprerušujte bez porady s lekárom alebo lekárnikom; v lekárni vám liek vymenia.</p></div>
  <section class="card"><h2>Stiahnutia z trhu za posledné dva roky ({len(rows)})</h2><ul class="glist">{''.join(rows) or '<li>Žiadne.</li>'}</ul></section>
  <section class="card"><h2>Bezpečnostné oznamy výrobcov (DHPC)</h2><p class="hint">Dôležité informácie o rizikách liekov, ktoré výrobcovia posielajú lekárom a lekárnikom so súhlasom ŠÚKL.</p><ul class="glist">{''.join(rows_d) or '<li>Žiadne.</li>'}</ul></section>
  <p class="hint">Zdroj: <a href="https://www.sukl.sk/pre-odbornikov-a-firmy/dostupnost-a-kvalita-liekov/kvalita-liekov/oznamy-o-stiahnuti-liekov" rel="nofollow">Oznamy o stiahnutí liekov</a> a <a href="https://www.sukl.sk/pre-odbornikov-a-firmy/bezpecnost-liekov/oznamy-drzitelov-dhpc" rel="nofollow">oznamy držiteľov (DHPC)</a>, ŠÚKL. Priradenie k liekom robíme automaticky podľa kódu ŠÚKL alebo názvu; pri rozpore platí oznam ŠÚKL.</p>"""
    write("/upozornenia-sukl/", page("Stiahnuté lieky z trhu a bezpečnostné oznamy ŠÚKL",
                                     f"Lieky a šarže, ktoré ŠÚKL stiahol z trhu za posledné dva roky ({len(rows)}), a bezpečnostné oznamy výrobcov. Aktualizované denne.",
                                     "/upozornenia-sukl/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/upozornenia-sukl/", "0.6"))
    small = {}
    for k, lst in recalls.items():
        small[k] = [{"t": "s", "d": r.get("date", ""), "n": r["title"], "u": r["url"],
                     "v": bool(r.get("vsetky")), "s": r.get("sarze", [])[:8]} for r in lst]
    (SITE / "oznamy.json").write_text(json.dumps(small, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(rows)
