"""Rozošle e-mailové upozornenia prihláseným používateľom.

Beží denne v GitHub Actions po aktualizácii dát. Pre každého potvrdeného odberateľa nájde jeho lieky, pri ktorých
- sa od budúceho mesiaca zmení doplatok alebo liek vypadne zo zoznamu,
- výrobca nahlásil ŠÚKL prerušenie alebo ukončenie dodávok,
a o ktorých ešte nedostal e-mail. Pošle jeden súhrnný e-mail a zapamätá si, čo už oznámil.

Potrebné premenné prostredia (GitHub → Settings → Secrets and variables → Actions):
  CF_ACCOUNT_ID, CF_API_TOKEN (oprávnenie Workers KV Storage: Edit), CF_KV_NAMESPACE_ID, RESEND_API_KEY
  voliteľne MAIL_FROM
Bez nich skript nič neurobí.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_pages import product_slug, eur, sk_date_long, sk_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://doplatkyliekov.sk"
ENV = {k: os.environ.get(k, "") for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN", "CF_KV_NAMESPACE_ID", "RESEND_API_KEY")}
MAIL_FROM = os.environ.get("MAIL_FROM") or "doplatkyliekov.sk <upozornenia@doplatkyliekov.sk>"
DRY = "--dry-run" in sys.argv


def kv_url(path):
    return (f"https://api.cloudflare.com/client/v4/accounts/{ENV['CF_ACCOUNT_ID']}/storage/kv/namespaces/"
            f"{ENV['CF_KV_NAMESPACE_ID']}/{path}")


def cf(path, method="GET", data=None, raw=False):
    req = urllib.request.Request(kv_url(path), method=method, data=data,
                                 headers={"Authorization": f"Bearer {ENV['CF_API_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body if raw else json.loads(body)


def list_subs():
    keys, cursor = [], ""
    while True:
        q = "keys?prefix=sub:&limit=1000" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        res = cf(q)
        keys += [k["name"] for k in res.get("result", [])]
        cursor = (res.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            return keys


def get_value(key):
    return json.loads(cf("values/" + urllib.parse.quote(key, safe=""), raw=True))


def put_value(key, obj):
    cf("values/" + urllib.parse.quote(key, safe=""), method="PUT", data=json.dumps(obj).encode("utf-8"))


def send(to, subject, body_html, unsub):
    payload = {"from": MAIL_FROM, "to": [to], "subject": subject, "html": body_html,
               "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}}
    req = urllib.request.Request("https://api.resend.com/emails", method="POST", data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {ENV['RESEND_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return 200 <= r.status < 300


def esc(s):
    return html.escape(str(s), quote=True)


def layout(title, inner):
    return f"""<!doctype html><html lang="sk"><body style="margin:0;background:#f1f5f4;font-family:Arial,Helvetica,sans-serif;color:#0a1a16">
<div style="max-width:560px;margin:0 auto;padding:28px 20px">
<p style="font-weight:bold;font-size:16px;margin:0 0 20px">doplatky<span style="color:#00866a">liekov</span>.sk</p>
<div style="background:#ffffff;border-radius:14px;padding:24px;border:1px solid #dce6e3">
<h1 style="font-size:20px;line-height:1.3;margin:0 0 14px">{esc(title)}</h1>
{inner}
</div>
<p style="font-size:12px;color:#5d716b;line-height:1.5;margin:18px 4px 0">Údaje pochádzajú zo Zoznamu kategorizovaných liekov MZ SR a z hlásení ŠÚKL.
Majú informačný charakter a nenahrádzajú radu lekára ani lekárnika.</p>
</div></body></html>"""


def main():
    if not all(ENV.values()):
        print("Upozornenia nie sú nastavené (chýbajú tajné premenné), preskakujem.")
        return
    full = json.loads((DATA / "full.json").read_text(encoding="utf-8"))
    nxt = json.loads((DATA / "next.json").read_text(encoding="utf-8")) if (DATA / "next.json").exists() else None
    vyp_all = json.loads((DATA / "vypadky.json").read_text(encoding="utf-8")) if (DATA / "vypadky.json").exists() else {}
    cutoff = (dt.date.today() - dt.timedelta(days=730)).isoformat()
    vyp = {k: v for k, v in vyp_all.get("lieky", {}).items() if v.get("od", "") >= cutoff and v.get("stav") in ("R", "Z", "PR", "PZ")}
    products = {}
    for g in full["groups"]:
        cheapest = min((x for x in g["i"] if x["dop"] is not None), key=lambda x: x["dop"], default=None)
        for p in g["i"]:
            products[p["kod"]] = (g, p, cheapest)

    sent = 0
    for key in list_subs():
        rec = get_value(key)
        if not rec.get("confirmed"):
            continue
        notified = rec.setdefault("notified", {})
        n_next = notified.setdefault("next", {})
        n_vyp = notified.setdefault("vyp", {})
        items = []
        for kod in rec.get("kody", []):
            hit = products.get(kod)
            if not hit:
                continue
            g, p, cheapest = hit
            url = f"{SITE}/liek/{product_slug(p['name'], p['kod'])}/"
            if nxt and n_next.get(kod) != nxt["platnostIso"]:
                np_ = nxt["prices"].get(kod)
                nd = sk_date_long(nxt["platnostIso"])
                if np_ is None:
                    items.append((url, p["name"], f"Od {nd} liek vypadne zo zoznamu hradených liekov. Poraďte sa s lekárom o náhrade."))
                    n_next[kod] = nxt["platnostIso"]
                elif np_[2] is not None and p["dop"] is not None and abs(np_[2] - p["dop"]) >= 0.01:
                    word = "stúpne" if np_[2] > p["dop"] else "klesne"
                    items.append((url, p["name"], f"Od {nd} doplatok {word} z {eur(p['dop'])} na {eur(np_[2])}."))
                    n_next[kod] = nxt["platnostIso"]
            st = vyp.get(kod)
            if st and n_vyp.get(kod) != st["od"]:
                txt = {"R": "Výrobca prerušil dodávky", "Z": "Výrobca ukončil dodávky",
                       "PR": "Výrobca ohlásil prerušenie dodávok", "PZ": "Výrobca ohlásil ukončenie dodávok"}[st["stav"]]
                alt = ""
                if cheapest and cheapest["kod"] != kod and cheapest["kod"] not in vyp:
                    alt = f" Alternatíva s rovnakou látkou: {cheapest['name']} (doplatok {eur(cheapest['dop'])})."
                items.append((url, p["name"], f"{txt} od {sk_date(st['od'])}.{alt}"))
                n_vyp[kod] = st["od"]
        if not items:
            continue
        unsub = f"{SITE}/api/unsubscribe?t={rec['token']}"
        lis = "".join(
            f'<li style="margin:0 0 14px;line-height:1.5"><a href="{esc(u)}" style="color:#00866a;font-weight:bold">{esc(n)}</a><br>{esc(t)}</li>'
            for u, n, t in items)
        title = "Zmena pri vašich liekoch" if len(items) == 1 else f"Zmeny pri vašich liekoch ({len(items)})"
        body = layout(title, f'<ul style="padding-left:18px;margin:0">{lis}</ul>'
                             f'<p style="font-size:13px;color:#5d716b;line-height:1.5;margin:18px 0 0">Tento e-mail dostávate, lebo ste sa prihlásili na upozornenia na doplatkyliekov.sk. '
                             f'<a href="{esc(unsub)}" style="color:#5d716b">Odhlásiť sa</a></p>')
        if DRY:
            print(f"[skúška] {rec['email']}: {len(items)} položiek")
            continue
        try:
            if send(rec["email"], title, body, unsub):
                put_value(key, rec)
                sent += 1
        except Exception as e:  # noqa: BLE001
            print(f"Chyba pri odoslaní na {rec['email'][:3]}…: {e}")
    print(f"Odoslané upozornenia: {sent}")


if __name__ == "__main__":
    main()
