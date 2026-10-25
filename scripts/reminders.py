"""Pripomienky užívania liekov (Web Push) v čase, ktorý si používateľ nastavil v Moje lieky.

Beží každých 10 minút (GitHub Actions, .github/workflows/reminders.yml). Číta index časov `doses:index`
a pošle notifikáciu pre časy za posledných 35 minút, ktoré ešte neboli odoslané (GitHub občas spúšťa s oneskorením).
  python3 scripts/reminders.py [--dry-run] [--now 2026-10-26T08:05]
"""
import datetime as dt
import json
import sys
import urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify  # noqa: E402

WINDOW = 35  # minút


def dose_txt(d):
    return {0.25: "¼", 0.5: "½", 0.75: "¾", 1.5: "1½"}.get(d, f"{d:g}".replace(".", ","))


def main():
    if not notify.VAPID_KEY or not notify.ENV.get("CF_API_TOKEN"):
        print("Pripomienky nie sú nastavené (chýba VAPID_PRIVATE_KEY alebo prístup ku KV).")
        return
    try:
        idx = notify.get_value("doses:index") or {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("Žiadne pripomienky.")
            return
        raise
    arg_now = sys.argv[sys.argv.index("--now") + 1] if "--now" in sys.argv else None
    names = {}
    full = json.loads((notify.ROOT / "data" / "full.json").read_text(encoding="utf-8")) if hasattr(notify, "ROOT") else \
        json.loads((Path(__file__).resolve().parent.parent / "data" / "full.json").read_text(encoding="utf-8"))
    for g in full["groups"]:
        for it in g["i"]:
            names[it["kod"]] = it["name"]
    sent = 0
    for pid, times in idx.items():
        rec_key = f"push:{pid}"
        try:
            rec = notify.get_value(rec_key)
        except urllib.error.HTTPError:
            continue
        tz = ZoneInfo(rec.get("tz") or "Europe/Bratislava")
        now = dt.datetime.fromisoformat(arg_now).replace(tzinfo=tz) if arg_now else dt.datetime.now(tz)
        done = rec.setdefault("notified", {}).setdefault("dose", {})
        due = {}
        for x in rec.get("doses") or []:
            h, m = map(int, x["t"].split(":"))
            at = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if at > now:
                at -= dt.timedelta(days=1)  # napr. 23:55 tesne po polnoci
            age = (now - at).total_seconds() / 60
            key = f"{at.date().isoformat()} {x['t']} {x['k']} {x.get('w', '')}"
            if 0 <= age < WINDOW and key not in done:
                due.setdefault(x["t"], []).append((key, x))
        if not due:
            continue
        changed = False
        for t, lst in sorted(due.items()):
            lines = [f"{names.get(x['k'], x['k'])}: {dose_txt(x['d'])} ks" + (f" ({x['w']})" if x.get("w") else "") for _, x in lst]
            payload = {"title": f"Čas na liek · {t}", "body": "; ".join(lines)[:220], "url": "/moje-lieky/",
                       "tag": f"dose-{t}", "dose": True}
            if notify.DRY:
                print(f"[skúška] {rec_key[:13]}… {payload['title']}: {payload['body']}")
                continue
            res = notify.send_push(rec, payload, ttl=WINDOW * 60)
            if res == "gone":
                notify.delete_value(rec_key)
                idx2 = notify.get_value("doses:index") or {}
                idx2.pop(pid, None)
                notify.put_value("doses:index", idx2)
                break
            if res == "ok":
                sent += 1
                for key, _ in lst:
                    done[key] = 1
                changed = True
            else:
                print("Pripomienka neodoslaná:", res)
        if changed:
            cutoff = (now.date() - dt.timedelta(days=2)).isoformat()
            rec["notified"]["dose"] = {k: v for k, v in done.items() if k[:10] >= cutoff}
            notify.put_value(rec_key, rec)
    print(f"Odoslané pripomienky: {sent}")


if __name__ == "__main__":
    main()
