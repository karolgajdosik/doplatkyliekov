#!/usr/bin/env python3
"""Týždenný e-mail so štatistikami návštevnosti doplatkyliekov.sk (Cloudflare Web Analytics) pre prevádzkovateľa.

Každý pondelok: návštevy za posledných 7 dní oproti predchádzajúcemu týždňu, návštevy po dňoch, najčítanejšie
stránky (pri liekoch s názvom), odkiaľ ľudia prišli, zariadenia, krajiny, počet prihlásených na upozornenia
a stav automatických úloh. Web Analytics nepoužíva cookies a neukladá IP adresy – sú to súhrnné počty.
Podľa skriptu z mestovcislach.sk.

Premenné: CF_API_TOKEN (Account Analytics: Read), CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, BREVO_API_KEY,
STATISTIKY_EMAIL (nepovinné, predvolene kontakt@doplatkyliekov.sk), GH_TOKEN + GITHUB_REPOSITORY (stav úloh).

  python3 scripts/statistiky_tyzden.py [--nahlad]
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

CF = "https://api.cloudflare.com/client/v4"
HOSTY = ["doplatkyliekov.sk", "www.doplatkyliekov.sk"]
ODOSIELATEL = {"name": "doplatkyliekov.sk", "email": "upozornenia@doplatkyliekov.sk"}
DATA = Path(__file__).resolve().parent.parent / "data"
ULOHY = {"update-data.yml": "Denná aktualizácia dát", "monitor.yml": "Strážca webu", "testy.yml": "Nočné testy",
         "lekari.yml": "Lekári a pohotovosti", "mesacne.yml": "Mesačné dáta"}

DOTAZ = """query($a: String!, $f: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!, $p: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!) {
  viewer { accounts(filter: {accountTag: $a}) {
    spolu: rumPageloadEventsAdaptiveGroups(limit: 1, filter: $f) { count sum { visits } }
    pred: rumPageloadEventsAdaptiveGroups(limit: 1, filter: $p) { count sum { visits } }
    dni: rumPageloadEventsAdaptiveGroups(limit: 14, filter: $f, orderBy: [date_ASC]) { count sum { visits } dimensions { date } }
    stranky: rumPageloadEventsAdaptiveGroups(limit: 15, filter: $f, orderBy: [sum_visits_DESC]) { count sum { visits } dimensions { requestPath } }
    zdroje: rumPageloadEventsAdaptiveGroups(limit: 10, filter: $f, orderBy: [sum_visits_DESC]) { sum { visits } dimensions { refererHost } }
    zariadenia: rumPageloadEventsAdaptiveGroups(limit: 5, filter: $f, orderBy: [sum_visits_DESC]) { sum { visits } dimensions { deviceType } }
    krajiny: rumPageloadEventsAdaptiveGroups(limit: 6, filter: $f, orderBy: [sum_visits_DESC]) { sum { visits } dimensions { countryName } }
  } }
}"""


def req(method, url, headers=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url.split('?')[0]}: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}") from None


def cf(token, method, path, body=None):
    return req(method, CF + path, {"Authorization": f"Bearer {token}"}, body)


def statistiky(token, a, od, do):
    """Skúsi filter bez robotov a len pre hlavnú doménu; ak ho API nepozná, postupne ho zjednoduší."""
    pod = od - timedelta(days=7)
    chyba = None
    for z in ({"bot": 0, "requestHost_in": HOSTY}, {"requestHost_in": HOSTY}, {}):
        f = {"date_geq": od.isoformat(), "date_leq": do.isoformat(), **z}
        p = {"date_geq": pod.isoformat(), "date_leq": (od - timedelta(days=1)).isoformat(), **z}
        d = cf(token, "POST", "/graphql", {"query": DOTAZ, "variables": {"a": a, "f": f, "p": p}})
        if d.get("errors"):
            chyba = "; ".join(e.get("message", "") for e in d["errors"])
            continue
        return d["data"]["viewer"]["accounts"][0]
    raise RuntimeError(f"Cloudflare GraphQL: {chyba}")


def v(x):
    return int((x.get("sum") or {}).get("visits") or 0)


_NAZVY = None


def citatelne(cesta):
    """/liek/concor-10-mg-94163/ → „Concor 10 mg (liek)“; /latka/x/ → „látka: X“; ostatné bez zmeny."""
    global _NAZVY
    m = re.match(r"^/liek/[^/]*-([0-9a-z]{4,6})/?$", cesta)
    if m:
        if _NAZVY is None:
            try:
                full = json.loads((DATA / "full.json").read_text(encoding="utf-8"))
                _NAZVY = {x["kod"].lower(): x["name"] for g in full["groups"] for x in g["i"]}
            except (OSError, ValueError, KeyError):
                _NAZVY = {}
        n = _NAZVY.get(m.group(1))
        return f"{n} (liek)" if n else cesta
    m = re.match(r"^/latka/([^/]+)/?$", cesta)
    if m:
        return f"látka: {m.group(1).replace('-', ' ')}"
    return cesta


def tabulka(nadpis, riadky, spolu):
    if not riadky:
        return ""
    r = "".join(f'<tr><td style="padding:4px 8px;border-bottom:1px solid #eee">{html.escape(n)}</td>'
                f'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right">{c}</td>'
                f'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right;color:#666">{round(100 * c / spolu) if spolu else 0} %</td></tr>'
                for n, c in riadky)
    return f'<h3 style="margin:20px 0 6px">{nadpis}</h3><table style="border-collapse:collapse;width:100%;font-size:14px">{r}</table>'


def odbery():
    """Počet prihlásených na e-mailové upozornenia, push a pripomienky (KV), bez akýchkoľvek údajov o ľuďoch."""
    tok, acc, ns = os.environ.get("CF_KV_TOKEN") or os.environ.get("CF_API_TOKEN", ""), os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_KV_NAMESPACE_ID", "")
    if not (tok and acc and ns):
        return ""
    out = []
    for pref, nazov in (("sub:", "e-mailové upozornenia"), ("push:", "upozornenia v prehliadači"), ("rem:", "pripomienky receptu")):
        n, cur = 0, ""
        try:
            while True:
                q = f"/accounts/{acc}/storage/kv/namespaces/{ns}/keys?prefix={urllib.parse.quote(pref)}&limit=1000" + (f"&cursor={urllib.parse.quote(cur)}" if cur else "")
                d = cf(tok, "GET", q)
                n += len(d.get("result") or [])
                cur = (d.get("result_info") or {}).get("cursor") or ""
                if not cur:
                    break
        except RuntimeError:
            return ""
        out.append(f"{nazov}: <b>{n}</b>")
    return '<h3 style="margin:20px 0 6px">Prihlásení</h3><p style="margin:0">' + " · ".join(out) + "</p>"


def stav_webu(od):
    """Úspešnosť automatických úloh za týždeň (GitHub API)."""
    tok, repo = os.environ.get("GH_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "karolgajdosik/doplatkyliekov")
    if not tok:
        return ""
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    riadky = []
    for subor, nazov in ULOHY.items():
        try:
            d = req("GET", f"https://api.github.com/repos/{repo}/actions/workflows/{subor}/runs?created=%3E%3D{od.isoformat()}&per_page=100&status=completed", h)
        except RuntimeError:
            continue
        behy = [b for b in d.get("workflow_runs", []) if b.get("conclusion") not in ("cancelled", "skipped")]
        if behy:
            zle = sum(1 for b in behy if b["conclusion"] != "success")
            riadky.append((nazov, len(behy), zle, behy[0]["conclusion"] == "success"))
    if not riadky:
        return ""
    ok = all(z == 0 for _, _, z, _ in riadky)
    t_ = "".join(f'<tr><td style="padding:4px 8px;border-bottom:1px solid #eee">{html.escape(n)}</td><td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right">{b}</td>'
                 f'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right;color:{"#b34700" if z else "#087a5f"}">{z or "–"}</td>'
                 f'<td style="padding:4px 8px;border-bottom:1px solid #eee">{"✓" if posl else "✗ chyba"}</td></tr>' for n, b, z, posl in riadky)
    return (f'<h3 style="margin:24px 0 6px">Stav webu {"– všetko v poriadku" if ok else "– pozor"}</h3>'
            '<table style="border-collapse:collapse;width:100%;font-size:14px"><tr><th style="text-align:left;padding:4px 8px">Automatická úloha</th>'
            '<th style="text-align:right;padding:4px 8px">behov</th><th style="text-align:right;padding:4px 8px">chýb</th><th style="text-align:left;padding:4px 8px">teraz</th></tr>'
            + t_ + "</table>")


def main():
    token = os.environ.get("CF_ANALYTICS_TOKEN") or os.environ.get("CF_API_TOKEN", "")
    token, brevo, acc = token.strip(), os.environ.get("BREVO_API_KEY", "").strip(), os.environ.get("CF_ACCOUNT_ID", "").strip()
    if not token or not acc:
        print("Chýba CF token alebo CF_ACCOUNT_ID – týždenný e-mail je vypnutý.")
        return 0
    do = date.today() - timedelta(days=1)
    od = do - timedelta(days=6)
    s = statistiky(token, acc, od, do)
    spolu, pred = v((s["spolu"] or [{}])[0]), v((s["pred"] or [{}])[0])
    zobrazenia = int(((s["spolu"] or [{}])[0]).get("count") or 0)
    zmena = f"{'+' if spolu >= pred else '−'}{abs(round(100 * (spolu - pred) / pred))} % oproti predchádzajúcemu týždňu" if pred else "prvý týždeň merania"
    dn = {"Mon": "po", "Tue": "ut", "Wed": "st", "Thu": "št", "Fri": "pi", "Sat": "so", "Sun": "ne"}
    dni = []
    for x in s["dni"]:
        d = date.fromisoformat(x["dimensions"]["date"])
        dni.append((f"{dn[d.strftime('%a')]} {d.day:02d}. {d.month:02d}.", v(x)))
    naj = max(dni, key=lambda x: x[1]) if dni else None
    stranky = [(citatelne(x["dimensions"]["requestPath"] or "/"), v(x)) for x in s["stranky"]]
    zdroje = [((x["dimensions"]["refererHost"] or "priamo / správy").replace("www.", ""), v(x)) for x in s["zdroje"]]
    zariadenia = [({"desktop": "počítač", "mobile": "mobil", "tablet": "tablet"}.get(x["dimensions"]["deviceType"], x["dimensions"]["deviceType"] or "iné"), v(x)) for x in s["zariadenia"]]
    krajiny = [(x["dimensions"]["countryName"] or "neznáma", v(x)) for x in s["krajiny"]]
    maxd = max([c for _, c in dni] or [1]) or 1
    graf = "".join(f'<tr><td style="padding:2px 8px;font-size:13px;white-space:nowrap">{d}</td><td style="padding:2px 0;width:100%">'
                   f'<div style="background:#087a5f;height:12px;border-radius:6px;width:{max(2, round(100 * c / maxd))}%"></div></td>'
                   f'<td style="padding:2px 8px;font-size:13px;text-align:right">{c}</td></tr>' for d, c in dni)
    obdobie = f"{od.day}. {od.month}. – {do.day}. {do.month}. {do.year}"
    telo = f"""<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:0 auto;color:#12211d">
<h2 style="margin:0 0 4px">Návštevnosť <a href="https://doplatkyliekov.sk" style="color:#087a5f">doplatkyliekov.sk</a></h2><p style="margin:0 0 16px;color:#666">{obdobie}</p>
<p style="font-size:28px;font-weight:700;margin:0">{spolu} návštev</p>
<p style="margin:4px 0 16px;color:#444">{zmena} · {zobrazenia} zobrazení stránok{f' · najviac v deň {naj[0]} ({naj[1]})' if naj and naj[1] else ''}</p>
<table style="border-collapse:collapse;width:100%">{graf}</table>
{tabulka('Najčítanejšie stránky (vstupné)', stranky, spolu)}
{tabulka('Odkiaľ prišli', zdroje, spolu)}
{tabulka('Zariadenia', zariadenia, spolu)}
{tabulka('Krajiny', krajiny, spolu)}
{odbery()}
{stav_webu(od)}
<p style="margin-top:24px;font-size:12px;color:#888">Cloudflare Web Analytics (bez cookies, bez robotov; naše automatické testy sa nepočítajú). „Priamo / správy“ sú aj odkazy poslané cez WhatsApp, Messenger či e-mail.</p></div>"""
    print(f"{obdobie}: {spolu} návštev ({zmena}); stránky {len(stranky)}, zdroje {len(zdroje)}")
    if "--nahlad" in sys.argv or not brevo:
        Path("statistiky_nahlad.html").write_text(telo, encoding="utf-8")
        print("Náhľad bez odoslania (statistiky_nahlad.html).")
        return 0
    prijemca = os.environ.get("STATISTIKY_EMAIL", "").strip() or "kontakt@doplatkyliekov.sk"
    req("POST", "https://api.brevo.com/v3/smtp/email", {"api-key": brevo, "accept": "application/json"}, {
        "sender": ODOSIELATEL, "to": [{"email": prijemca}], "subject": f"Návštevnosť {obdobie}: {spolu} návštev ({zmena.split(' oproti')[0]})",
        "htmlContent": telo, "tags": ["statistiky"]})
    print("E-mail odoslaný.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"::error title=Štatistiky::{type(e).__name__}: {str(e)[:500]}".replace("\n", " "))
        sys.exit(1)
