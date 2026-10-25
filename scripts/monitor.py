"""Strážca webu: overí, že doplatkyliekov.sk beží, dáta sú čerstvé a asistent odpovedá.
Pri chybe pošle e-mail na kontakt@doplatkyliekov.sk (cez Brevo) a skončí s chybou (GitHub pošle aj vlastné upozornenie).

Spúšťa .github/workflows/monitor.yml každých 6 hodín. Premenné: BREVO_API_KEY (voliteľné), GITHUB_TOKEN, GITHUB_REPOSITORY.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request

SITE = "https://doplatkyliekov.sk"
TO = os.environ.get("MONITOR_TO", "kontakt@doplatkyliekov.sk")
UA = {"User-Agent": "doplatkyliekov-monitor/1.0"}


def get(url, data=None, timeout=60, headers=None):
    h = dict(UA, **(headers or {}))
    if data is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=h)
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), time.time() - t


def check(name, fn, problems, notes):
    try:
        msg = fn()
        notes.append(f"OK  {name}{': ' + msg if msg else ''}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"{name}: {e}")
        notes.append(f"CHYBA {name}: {e}")


def main():
    problems, notes = [], []
    today = dt.date.today()

    def home():
        s, body, sec = get(SITE + "/")
        assert s == 200 and b'id="q"' in body and b"doplatkyliekov" in body, "úvodná stránka nemá očakávaný obsah"
        return f"{s}, {sec:.1f} s"

    def data():
        s, body, _ = get(SITE + "/data.json")
        j = json.loads(body)
        iso = j.get("platnostIso") or ""
        n = sum(len(g["i"]) for g in j["groups"])
        assert n > 3000, f"v zozname je len {n} liekov"
        age = (today - dt.date.fromisoformat(iso)).days if iso else 999
        assert age <= 40, f"zoznam platný od {iso} je starý {age} dní"
        return f"{n} liekov, zoznam od {iso}"

    def drug():
        s, body, _ = get(SITE + "/ai/search.json")
        j = json.loads(body)
        kod, name, gi = j["items"][len(j["items"]) // 2]
        s2, b2, _ = get(SITE + "/sitemap.xml")
        assert s2 == 200 and b2.count(b"<url>") > 5000, "mapa stránok je neúplná"
        return f"register asistenta {len(j['items'])} liekov, mapa stránok OK"

    def pages():
        for path in ("/moje-lieky/", "/zmeny/", "/vypadky/", "/ochranny-limit/", "/asistent/", "/choroby/", "/og/default.jpg"):
            s, _, _ = get(SITE + path)
            assert s == 200, f"{path} vrátil {s}"
        return "7 adries vrátane náhľadového obrázka"

    def assistant():
        s, body, sec = get(SITE + "/api/asistent", {"q": "Koľko doplatím za Concor 10 mg?"}, timeout=90)
        j = json.loads(body)
        ans = j.get("answer") or ""
        assert s == 200 and "Concor" in ans and "€" in ans, f"odpoveď je podozrivá: {ans[:120] or j}"
        return f"{sec:.1f} s, model {j.get('model', '?')}"

    def updater():
        repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
        if not repo or not tok:
            return "preskočené"
        s, body, _ = get(f"https://api.github.com/repos/{repo}/actions/workflows/update-data.yml/runs?per_page=5&status=completed",
                         headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
        runs = json.loads(body).get("workflow_runs", [])
        ok = [r for r in runs if r.get("conclusion") == "success"]
        assert ok, "posledné behy aktualizácie dát zlyhali"
        last = dt.datetime.fromisoformat(ok[0]["created_at"].replace("Z", "+00:00"))
        hours = (dt.datetime.now(dt.timezone.utc) - last).total_seconds() / 3600
        assert hours < 30, f"posledná úspešná aktualizácia pred {hours:.0f} h"
        return f"posledná úspešná pred {hours:.0f} h"

    for name, fn in [("Úvodná stránka", home), ("Údaje o liekoch", data), ("Register a mapa stránok", drug),
                     ("Podstránky", pages), ("AI asistent", assistant), ("Denná aktualizácia", updater)]:
        check(name, fn, problems, notes)
    print("\n".join(notes))
    for n in notes:
        print(("::error title=Strážca::" if n.startswith("CHYBA") else "::notice title=Strážca::") + n)
    if problems:
        key = os.environ.get("BREVO_API_KEY")
        if key:
            html = ("<p>Strážca webu doplatkyliekov.sk našiel problém:</p><ul>" + "".join(f"<li>{p}</li>" for p in problems)
                    + "</ul><p>Celý výsledok:</p><pre>" + "\n".join(notes) + "</pre>")
            payload = {"sender": {"name": "Strážca doplatkyliekov.sk", "email": "upozornenia@doplatkyliekov.sk"},
                       "to": [{"email": TO}], "subject": f"⚠ doplatkyliekov.sk: {problems[0][:80]}", "htmlContent": html}
            try:
                req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
                                             headers={"api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
                urllib.request.urlopen(req, timeout=30)
                print("E-mail o chybe odoslaný.")
            except Exception as e:  # noqa: BLE001
                print("E-mail sa nepodarilo odoslať:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
