#!/usr/bin/env python3
"""Mesačný prehľad vyhľadávaní bez výsledku (KV `nf:RRRR-MM:<kde>:<výraz>`, zapisuje /api/nenajdene).

Pošle e-mail na kontakt@doplatkyliekov.sk (Brevo) s najčastejšími výrazmi za predchádzajúci mesiac (alebo
`--mesiac RRRR-MM`). Do logu GitHubu (verejného) vypíše len počty, nie samotné výrazy.
Premenné: CF_ACCOUNT_ID, CF_API_TOKEN, CF_KV_NAMESPACE_ID, BREVO_API_KEY.

  python3 scripts/nenajdene.py [--mesiac 2026-11]
"""
import collections
import datetime as dt
import html
import json
import os
import sys
import urllib.parse
import urllib.request

ENV = os.environ
TO = ENV.get("MONITOR_TO", "kontakt@doplatkyliekov.sk")
KDE = {"uvod": "vyhľadávanie liekov", "pomocky": "zdravotnícke pomôcky", "dp": "dietetické potraviny", "mapa": "mapa"}


def cf(path):
    url = (f"https://api.cloudflare.com/client/v4/accounts/{ENV['CF_ACCOUNT_ID']}/storage/kv/namespaces/"
           f"{ENV['CF_KV_NAMESPACE_ID']}/{path}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {ENV['CF_API_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    if "--mesiac" in sys.argv:
        month = sys.argv[sys.argv.index("--mesiac") + 1]
    else:
        first = dt.date.today().replace(day=1)
        month = (first - dt.timedelta(days=1)).strftime("%Y-%m")
    counts, cursor = collections.Counter(), ""
    while True:
        q = f"keys?prefix={urllib.parse.quote(f'nf:{month}:')}&limit=1000" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        res = cf(q)
        for k in res.get("result", []):
            _, _, kde, term = k["name"].split(":", 3)
            counts[(kde, term)] += int((k.get("metadata") or {}).get("n") or 1)
        cursor = (res.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            break
    # hodnotenia „Pomohla vám táto stránka?“ (fb:RRRR-MM:<kód>:<ano|nie>)
    fb, cursor = collections.Counter(), ""
    while True:
        q = f"keys?prefix={urllib.parse.quote(f'fb:{month}:')}&limit=1000" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        res = cf(q)
        for k in res.get("result", []):
            _, _, kod, v = k["name"].split(":", 3)
            fb[(kod, v)] += int((k.get("metadata") or {}).get("n") or 1)
        cursor = (res.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            break
    names = {}
    full = os.path.join(os.path.dirname(__file__), "..", "data", "full.json")
    if os.path.exists(full):
        names = {x["kod"]: x["name"] for g in json.load(open(full, encoding="utf-8"))["groups"] for x in g["i"]}
    ano, nie = sum(n for (k, v), n in fb.items() if v == "ano"), sum(n for (k, v), n in fb.items() if v == "nie")
    print(f"::notice title=hodnotenie::{month}: pomohlo {ano}×, nepomohlo {nie}×")
    total = sum(counts.values())
    print(f"Hľadania bez výsledku za {month}: {len(counts)} rôznych výrazov, spolu {total}")
    print(f"::notice title=nenajdene::{month}: {len(counts)} výrazov, {total} hľadaní (výrazy idú len e-mailom)")
    key = ENV.get("BREVO_API_KEY")
    if (not counts and not fb) or not key:
        return
    rows = []
    for kde in KDE:
        top = [(t, n) for (k, t), n in counts.most_common() if k == kde][:40]
        if top:
            rows.append(f"<h3>{KDE[kde]}</h3><table cellpadding='4'>" + "".join(
                f"<tr><td>{html.escape(t)}</td><td align='right'>{n}×</td></tr>" for t, n in top) + "</table>")
    body = (f"<p>Čo ľudia na doplatkyliekov.sk hľadali za {month} a nenašli ({len(counts)} rôznych výrazov, spolu {total}×). "
            "Výrazy sú anonymné, bez údajov o tom, kto hľadal. Pomôže doplniť preklepy, chýbajúce lieky alebo témy.</p>" + "".join(rows))
    if fb:
        bad = sorted({k for k, v in fb}, key=lambda k: -fb[(k, "nie")])[:20]
        body += (f"<h3>Pomohla vám táto stránka? (stránky liekov)</h3><p>Áno {ano}×, nie {nie}×.</p>"
                 + ("<table cellpadding='4'><tr><th align='left'>Liek</th><th>áno</th><th>nie</th></tr>" + "".join(
                     f"<tr><td>{html.escape(names.get(k, k))} ({k})</td><td align='right'>{fb[(k, 'ano')]}</td><td align='right'>{fb[(k, 'nie')]}</td></tr>"
                     for k in bad if fb[(k, "nie")]) + "</table>" if nie else ""))
    payload = {"sender": {"name": "doplatkyliekov.sk", "email": "upozornenia@doplatkyliekov.sk"}, "to": [{"email": TO}],
               "subject": f"doplatkyliekov.sk: čo ľudia hľadali a nenašli, hodnotenia stránok ({month})", "htmlContent": body}
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
                                 headers={"api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    urllib.request.urlopen(req, timeout=30)
    print("Prehľad odoslaný e-mailom.")


if __name__ == "__main__":
    main()
