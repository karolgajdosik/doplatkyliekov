"""Rozošle e-mailové upozornenia prihláseným používateľom.

Beží denne v GitHub Actions po aktualizácii dát. Pre každého potvrdeného odberateľa nájde jeho lieky, pri ktorých
- sa od budúceho mesiaca zmení doplatok alebo liek vypadne zo zoznamu,
- výrobca nahlásil ŠÚKL prerušenie alebo ukončenie dodávok,
- v novom mesačnom zozname pribudol liek s rovnakou látkou, silou a balením s nižším doplatkom (generikum),
a o ktorých ešte nedostal e-mail. Pošle jeden súhrnný e-mail a zapamätá si, čo už oznámil.

Potrebné premenné prostredia (GitHub → Settings → Secrets and variables → Actions):
  CF_ACCOUNT_ID, CF_API_TOKEN (oprávnenie Workers KV Storage: Edit), CF_KV_NAMESPACE_ID,
  BREVO_API_KEY (alebo RESEND_API_KEY)
  voliteľne MAIL_FROM
Bez nich skript nič neurobí.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_pages import product_slug, eur, sk_date_long, sk_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://doplatkyliekov.sk"
ENV = {k: os.environ.get(k, "") for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN", "CF_KV_NAMESPACE_ID")}
BREVO_KEY = os.environ.get("BREVO_API_KEY", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
VAPID_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
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


def list_subs(prefix="sub:"):
    keys, cursor = [], ""
    while True:
        q = f"keys?prefix={prefix}&limit=1000" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        res = cf(q)
        keys += [k["name"] for k in res.get("result", [])]
        cursor = (res.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            return keys


def get_value(key):
    return json.loads(cf("values/" + urllib.parse.quote(key, safe=""), raw=True))


def put_value(key, obj):
    cf("values/" + urllib.parse.quote(key, safe=""), method="PUT", data=json.dumps(obj).encode("utf-8"))


def parse_from(sender):
    m = re.match(r"^\s*(.*?)\s*<([^>]+)>\s*$", sender)
    return {"name": m.group(1), "email": m.group(2)} if m else {"email": sender.strip()}


def send(to, subject, body_html, unsub):
    headers = {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    if BREVO_KEY:
        url = "https://api.brevo.com/v3/smtp/email"
        payload = {"sender": parse_from(MAIL_FROM), "to": [{"email": to}], "subject": subject,
                   "htmlContent": body_html, "headers": headers}
        hdrs = {"api-key": BREVO_KEY, "Content-Type": "application/json", "Accept": "application/json"}
    else:
        url = "https://api.resend.com/emails"
        payload = {"from": MAIL_FROM, "to": [to], "subject": subject, "html": body_html, "headers": headers}
        hdrs = {"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode(), headers=hdrs)
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


def delete_value(key):
    cf("values/" + urllib.parse.quote(key, safe=""), method="DELETE")


class Ctx:
    """Spoločné údaje pre e-maily, notifikácie a mesačný prehľad."""
    def __init__(self):
        self.full = json.loads((DATA / "full.json").read_text(encoding="utf-8"))
        self.nxt = json.loads((DATA / "next.json").read_text(encoding="utf-8")) if (DATA / "next.json").exists() else None
        vyp_all = json.loads((DATA / "vypadky.json").read_text(encoding="utf-8")) if (DATA / "vypadky.json").exists() else {}
        cutoff = (dt.date.today() - dt.timedelta(days=730)).isoformat()
        self.vyp = {k: v for k, v in vyp_all.get("lieky", {}).items() if v.get("od", "") >= cutoff and v.get("stav") in ("R", "Z", "PR", "PZ")}
        # všetky aktuálne hlásenia bez časového obmedzenia (na zistenie, že sa výpadok skončil)
        self.vyp_raw = {k for k, v in vyp_all.get("lieky", {}).items() if v.get("stav") in ("R", "Z", "PR", "PZ")}
        self.vyp_ok = bool(vyp_all.get("lieky"))
        self.cur_iso = self.full.get("platnostIso") or ""
        self.prev_keys = None
        if self.cur_iso:
            y, m = int(self.cur_iso[:4]), int(self.cur_iso[5:7])
            py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
            pf = DATA / "history" / f"{py}-{pm:02d}.json"
            if pf.exists():
                self.prev_keys = set(json.loads(pf.read_text(encoding="utf-8")))
        self.products = {}
        for g in self.full["groups"]:
            cheapest = min((x for x in g["i"] if x["dop"] is not None), key=lambda x: x["dop"], default=None)
            for p in g["i"]:
                self.products[p["kod"]] = (g, p, cheapest)


def changes_for(ctx, kody, notified, since):
    """Zoznam (url, názov lieku, text) nových zmien pre dané lieky; zapíše, čo už bolo oznámené."""
    n_next = notified.setdefault("next", {})
    n_vyp = notified.setdefault("vyp", {})
    n_gen = notified.setdefault("gen", {})
    nxt, vyp, items = ctx.nxt, ctx.vyp, []
    for kod in kody:
        hit = ctx.products.get(kod)
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
        if ctx.prev_keys is not None and ctx.cur_iso > since and p["dop"] is not None:
            seen = set(n_gen.get(kod, []))
            fresh = [x for x in g["i"] if x["kod"] != kod and x["kod"] not in ctx.prev_keys and x["kod"] not in seen
                     and x["dop"] is not None and p["dop"] - x["dop"] >= 0.5]
            if fresh:
                best = min(fresh, key=lambda x: x["dop"])
                items.append((url, p["name"],
                              f"Pribudla lacnejšia alternatíva s rovnakou látkou, silou a balením: {best['name']} "
                              f"s doplatkom {eur(best['dop'])} (teraz doplácate {eur(p['dop'])}). Opýtajte sa lekára alebo lekárnika."))
                n_gen[kod] = sorted(seen | {x["kod"] for x in fresh})
        st = vyp.get(kod)
        if st and n_vyp.get(kod) != st["od"]:
            txt = {"R": "Výrobca prerušil dodávky", "Z": "Výrobca ukončil dodávky",
                   "PR": "Výrobca ohlásil prerušenie dodávok", "PZ": "Výrobca ohlásil ukončenie dodávok"}[st["stav"]]
            alt = ""
            if cheapest and cheapest["kod"] != kod and cheapest["kod"] not in vyp:
                alt = f" Alternatíva s rovnakou látkou: {cheapest['name']} (doplatok {eur(cheapest['dop'])})."
            items.append((url, p["name"], f"{txt} od {sk_date(st['od'])}.{alt}"))
            n_vyp[kod] = st["od"]
        elif not st and kod in n_vyp and ctx.vyp_ok and kod not in ctx.vyp_raw:
            # predtým sme hlásili výpadok a teraz už v hláseniach ŠÚKL nie je → liek je opäť dostupný
            items.append((url, p["name"], f"Liek je opäť dostupný: výrobca už nehlási prerušenie dodávok. Doplatok je {eur(p['dop'])}."))
            n_vyp.pop(kod, None)
    return items


def digest_html(ctx):
    """Mesačný prehľad zmien z nového zoznamu ministerstva."""
    nxt = ctx.nxt
    nd = sk_date_long(nxt["platnostIso"])
    ups, downs, gone = [], [], []
    for kod, (g, p, _) in ctx.products.items():
        np_ = nxt["prices"].get(kod)
        if np_ is None:
            gone.append(p)
        elif np_[2] is not None and p["dop"] is not None and abs(np_[2] - p["dop"]) >= 0.01:
            (ups if np_[2] > p["dop"] else downs).append((np_[2] - p["dop"], p, np_[2]))
    common = [x for x in ups + downs if (x[1].get("konc") or 0) <= 150]
    ups_c = sorted([x for x in common if x[0] > 0], key=lambda x: -x[0])[:5]
    downs_c = sorted([x for x in common if x[0] < 0], key=lambda x: x[0])[:5]

    def li(d, p, new):
        u = f"{SITE}/liek/{product_slug(p['name'], p['kod'])}/"
        return (f'<li style="margin:0 0 8px"><a href="{esc(u)}" style="color:#00866a">{esc(p["name"])}</a>: '
                f'{eur(p["dop"])} → {eur(new)}</li>')
    n_vyp = sum(1 for k, v in ctx.vyp.items() if v["stav"] in ("R", "Z") and k in ctx.products)
    inner = (f'<p style="line-height:1.6;margin:0 0 14px">Od {nd} platí nový zoznam hradených liekov. Doplatok klesne pri '
             f'<strong>{len(downs)}</strong> liekoch, stúpne pri <strong>{len(ups)}</strong> a <strong>{len(gone)}</strong> liekov vypadne zo zoznamu. '
             f'Prerušené dodávky má teraz {n_vyp} liekov.</p>')
    if downs_c:
        inner += '<p style="margin:14px 0 6px;font-weight:bold">Najviac zlacnie</p><ul style="padding-left:18px;margin:0">' + "".join(li(*x) for x in downs_c) + "</ul>"
    if ups_c:
        inner += '<p style="margin:14px 0 6px;font-weight:bold">Najviac zdražie</p><ul style="padding-left:18px;margin:0">' + "".join(li(*x) for x in ups_c) + "</ul>"
    inner += (f'<p style="margin:18px 0"><a href="{SITE}/zmeny/" style="display:inline-block;background:#00866a;color:#fff;text-decoration:none;'
              f'font-weight:bold;padding:12px 20px;border-radius:999px">Všetky zmeny</a></p>')
    return f"Prehľad doplatkov od {nd}", inner


def send_push(rec, payload, ttl=86400):
    from pywebpush import webpush, WebPushException  # noqa: PLC0415
    try:
        webpush(subscription_info=rec["sub"], data=json.dumps(payload, ensure_ascii=False), vapid_private_key=VAPID_KEY,
                vapid_claims={"sub": "mailto:kontakt@doplatkyliekov.sk"}, ttl=ttl)
        return "ok"
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return "gone" if code in (404, 410) else f"chyba {code}"


def run_push(ctx):
    today = dt.date.today()
    sent = 0
    for key in list_subs("push:"):
        rec = get_value(key)
        notified = rec.setdefault("notified", {})
        items = changes_for(ctx, rec.get("kody", []), notified, (rec.get("consentAt") or rec.get("created") or "")[:10])
        n_ref = notified.setdefault("refill", {})
        for kod, iso in (rec.get("refills") or {}).items():
            try:
                left = (dt.date.fromisoformat(iso) - today).days
            except ValueError:
                continue
            hit = ctx.products.get(kod)
            if hit and 0 <= left <= 3 and n_ref.get(kod) != iso:
                when = "dnes" if left == 0 else "zajtra" if left == 1 else f"o {left} dni"
                items.append((f"{SITE}/moje-lieky/", hit[1]["name"], f"Balenie vám dôjde {when} ({sk_date(iso)}). Nezabudnite na recept."))
                n_ref[kod] = iso
        if not items:
            continue
        if len(items) == 1:
            u, n, t = items[0]
            payload = {"title": n, "body": t, "url": u.replace(SITE, ""), "tag": "doplatky"}
        else:
            payload = {"title": f"Vaše lieky: {len(items)} upozornenia" if len(items) < 5 else f"Vaše lieky: {len(items)} upozornení",
                       "body": " · ".join(f"{n}: {t}" for _, n, t in items[:2])[:220], "url": "/moje-lieky/", "tag": "doplatky"}
        if DRY:
            print(f"[skúška] push {key[:13]}…: {payload['title']}")
            continue
        res = send_push(rec, payload)
        if res == "ok":
            put_value(key, rec)
            sent += 1
        elif res == "gone":
            delete_value(key)
        else:
            print("Notifikácia neodoslaná:", res)
    print(f"Odoslané notifikácie: {sent}")


def main():
    if not all(ENV.values()):
        print("Upozornenia nie sú nastavené (chýbajú tajné premenné), preskakujem.")
        return
    ctx = Ctx()
    if VAPID_KEY:
        try:
            run_push(ctx)
        except Exception as e:  # noqa: BLE001
            print("Notifikácie zlyhali:", e)
    else:
        print("Notifikácie nie sú nastavené (chýba VAPID_PRIVATE_KEY).")
    if not (BREVO_KEY or RESEND_KEY):
        print("E-maily nie sú nastavené, preskakujem.")
        return
    run_email(ctx)


def run_email(ctx):
    nxt = ctx.nxt
    digest = digest_html(ctx) if nxt else None
    sent = 0
    for key in list_subs():
        rec = get_value(key)
        if not rec.get("confirmed"):
            continue
        notified = rec.setdefault("notified", {})
        since = (rec.get("confirmedAt") or rec.get("created") or "")[:10]
        unsub = f"{SITE}/api/unsubscribe?t={rec['token']}"
        manage = f"{SITE}/upozornenia/sprava/?t={rec['token']}"
        foot = (f'<p style="font-size:13px;color:#5d716b;line-height:1.5;margin:18px 0 0">Tento e-mail dostávate, lebo ste sa prihlásili na upozornenia na doplatkyliekov.sk. '
                f'<a href="{esc(manage)}" style="color:#5d716b">Upraviť upozornenia</a> · <a href="{esc(unsub)}" style="color:#5d716b">Odhlásiť sa</a></p>')
        if digest and rec.get("digest") and notified.get("digest") != nxt["platnostIso"]:
            title_d, inner_d = digest
            if DRY:
                print(f"[skúška] prehľad {rec['email']}")
            else:
                try:
                    if send(rec["email"], title_d, layout(title_d, inner_d + foot), unsub):
                        notified["digest"] = nxt["platnostIso"]
                        put_value(key, rec)
                except Exception as e:  # noqa: BLE001
                    print(f"Chyba pri prehľade pre {rec['email'][:3]}…: {e}")
        items = changes_for(ctx, rec.get("kody", []), notified, since)
        if not items:
            continue
        lis = "".join(
            f'<li style="margin:0 0 14px;line-height:1.5"><a href="{esc(u)}" style="color:#00866a;font-weight:bold">{esc(n)}</a><br>{esc(t)}</li>'
            for u, n, t in items)
        title = "Zmena pri vašich liekoch" if len(items) == 1 else f"Zmeny pri vašich liekoch ({len(items)})"
        body = layout(title, f'<ul style="padding-left:18px;margin:0">{lis}</ul>' + foot)
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
