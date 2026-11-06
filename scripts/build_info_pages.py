"""Stránky /kupele/ (z data/kupele.json, build_kupele.py) a /cakacie-lehoty/ (čakanie na plánované operácie).

Čakacie lehoty: národný portál čakacích listín (ecakacielistiny.npz.sk) nie je dostupný mimo Slovenska, preto
stránka uvádza súhrnné údaje Úradu pre dohľad (ÚDZS) s dátumom a zdrojom a práva pacienta. Čísla aktualizovať ručne
podľa novej tlačovej správy ÚDZS (spravidla dvakrát ročne).
"""
import json
from urllib.parse import quote

CAKANIE = {
    "overene": "6. 11. 2026",
    "k_datum": "1. 9. 2026",
    "navrhy": "96\u00a0549",
    "pacienti": "takmer 87\u00a0500",
    "nad_lehotu": "11\u00a0848",
    "priemer": "123",
    "deti": "163",
    "zdroj_2026": ("https://www.noviny.sk/slovensko/1275942-na-operacie-caka-takmer-88-tisic-slovakov-najdlhsie-cakaju-deti",
                   "Analýza ÚDZS k 1. 9. 2026 (SITA, 21. 10. 2026)"),
    "mediany_datum": "31. 8. 2025",
    "mediany": [("Totálna endoprotéza kolenného kĺbu", 349), ("Totálna endoprotéza bedrového kĺbu", 266),
                ("Operácia sivého zákalu (výmena šošovky)", 101), ("Podanie lieku do oka", 61)],
    "zdroj_2025": ("https://www.udzs-sk.sk/wp-content/uploads/2025/11/TS_V-cakackach-na-operacie-nastal-pozitivny-vyvoj.pdf",
                   "Tlačová správa ÚDZS z 21. 11. 2025"),
}


def build_info_pages(c):
    esc, page, write, crumbs, breadcrumb_ld, urls, DATA = c["esc"], c["page"], c["write"], c["crumbs"], c["breadcrumb_ld"], c["urls"], c["DATA"]
    n = 0
    # --- kúpele ---
    src = DATA / "kupele.json"
    if src.exists():
        kp = json.loads(src.read_text(encoding="utf-8"))
        K = {k["id"]: k for k in kp["kupele"]}

        def grp(g):
            items = sorted(g["k"], key=lambda e: K[e[0]]["m"])
            lis = "".join(
                f'<li><strong>{esc(K[i]["m"] or K[i]["n"])}</strong> <small>{esc(K[i]["n"])}'
                f'{" · kúpeľná liečebňa" if K[i]["t"] == "KL" else ""}</small>'
                f'{f"<small class=kp-note>{esc(note)}</small>" if note else ""}</li>' for i, note in items)
            return (f'<details class="card kp-g" id="sk-{esc(g["c"].lower())}"><summary><span>{esc(g["n"])}</span>'
                    f'<small>{len(items)} {"kúpele" if 2 <= len(items) <= 4 else "kúpeľ" if len(items) == 1 else "kúpeľov"}</small></summary>'
                    f'<ul class="plain kp-list">{lis}</ul></details>')
        dospeli = "".join(grp(g) for g in kp["skupiny"] if not g["deti"])
        deti = "".join(grp(g) for g in kp["skupiny"] if g["deti"])
        miesta = sorted({k["m"] for k in kp["kupele"] if k["m"]})
        crumb_items = [("Domov", "/"), ("Kúpele", None)]
        body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Kúpeľná starostlivosť</p>
    <h1 class="page-h1">Kúpele, ktoré platí poisťovňa</h1>
    <p class="page-sub">Ktoré kúpele liečia vaše ochorenie a čo pri kúpeľnej liečbe zaplatíte. {len(kp["kupele"])} kúpeľov a kúpeľných liečební v {len(miesta)} obciach podľa povolení ministerstva zdravotníctva.</p>
  </section>
  <section class="card">
    <h2>Ako to funguje</h2>
    <ul class="kp-how">
      <li><strong>Návrh vystaví lekár.</strong> Kúpeľnú liečbu navrhne všeobecný lekár alebo špecialista, ak vaše ochorenie patrí do indikačného zoznamu. Návrh schvaľuje zdravotná poisťovňa.</li>
      <li><strong>Skupina A:</strong> kúpele sú nevyhnutnou súčasťou liečby, napríklad po operácii. Poisťovňa platí liečbu aj ubytovanie a stravu.</li>
      <li><strong>Skupina B:</strong> kúpele sú vhodné na zlepšenie stavu. Poisťovňa platí liečbu (procedúry), <strong>ubytovanie a stravu platíte vy</strong> podľa cenníka kúpeľov.</li>
      <li><strong>Vždy platíte</strong> poplatok za deň pobytu a daň z ubytovania (VšZP uvádza 1,70 € za deň) a dopravu do kúpeľov.</li>
      <li><strong>Kúpele si vyberáte sami</strong> z tých, ktoré liečia vaše ochorenie a majú zmluvu s vašou poisťovňou. Termín nástupu určia kúpele, dôležité je stihnúť posledný možný termín uvedený v návrhu.</li>
    </ul>
    <p class="hint">Niektoré poisťovne prispievajú aj na pobyt v skupine B, pozrite <a href="/vyhody-poistovni/">výhody poisťovní</a>. Zdroj podmienok: <a href="https://www.vszp.sk/files/poistenci/zdravotna-starostlivost/kupelna-starostlivost/formular-najcastejsich-otazok-odpovedi-skupine-b.pdf" rel="nofollow">VšZP, otázky a odpovede ku skupine B</a>.</p>
  </section>
  <h2 class="kp-h">Dospelí: podľa ochorenia</h2>
  {dospeli}
  <h2 class="kp-h">Deti a dorast: podľa ochorenia</h2>
  {deti}
  <p class="hint">Poznámky „okrem indikácie…“ znamenajú, že kúpele nelečia všetky diagnózy zo skupiny; presnú indikáciu uvádza lekár v návrhu. Zdroj: <a href="{esc(kp["zdroj"])}" rel="nofollow">Ministerstvo zdravotníctva SR, Inšpektorát kúpeľov a žriediel</a>, stav k {esc(kp["datum"][8:10].lstrip("0"))}. {esc(kp["datum"][5:7].lstrip("0"))}. {esc(kp["datum"][:4])}.</p>
  <style>
  .kp-how{{padding-left:1.1em;display:grid;gap:8px}}
  .kp-h{{margin:28px 4px 10px;font-size:22px}}
  details.kp-g.card{{display:block;padding:0;margin:0 0 10px}}
  details.kp-g.card+details.kp-g.card{{margin-top:0}}
  .kp-g summary{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 18px;cursor:pointer;font-weight:600;list-style:none}}
  .kp-g summary::-webkit-details-marker{{display:none}}
  .kp-g summary::after{{content:"+";font-size:24px;line-height:1;color:var(--accent)}}
  .kp-g[open] summary::after{{content:"–"}}
  .kp-g summary small{{margin-left:auto;color:var(--muted);font-weight:400;white-space:nowrap}}
  .kp-g ul.kp-list{{padding:0 18px 12px;margin:0}}
  .kp-list li{{padding:8px 0;border-top:1px solid var(--line)}}
  .kp-list small{{display:block;color:var(--muted)}}
  .kp-note{{font-style:italic}}
  </style>"""
        write("/kupele/", page("Kúpele, ktoré platí poisťovňa – podľa ochorenia",
                               f"Ktoré z {len(kp['kupele'])} slovenských kúpeľov liečia vaše ochorenie, čo platí poisťovňa v skupine A a B a čo doplácate.",
                               "/kupele/", body, breadcrumb_ld(crumb_items)))
        urls.append(("/kupele/", "0.6"))
        n += 1

    # --- čakacie lehoty ---
    C = CAKANIE
    rows = "".join(f'<tr><th scope="row">{esc(a)}</th><td class="mono">{b} dní</td></tr>' for a, b in C["mediany"])
    crumb_items = [("Domov", "/"), ("Čakanie na operáciu", None)]
    body = f"""{crumbs(crumb_items)}
  <section class="intro">
    <p class="eyebrow">Plánované operácie</p>
    <h1 class="page-h1">Čakanie na operáciu: lehoty a vaše práva</h1>
    <p class="page-sub">Koľko sa na Slovensku čaká na plánované operácie, čo je lehota časovej dostupnosti a čo robiť, keď ju nemocnica nedodrží.</p>
  </section>
  <section class="card">
    <h2>Koľko sa čaká</h2>
    <p>K {C["k_datum"]} evidovali poisťovne <strong>{C["navrhy"]}</strong> návrhov na plánovanú operáciu ({C["pacienti"]} pacientov). Priemerne sa čakalo <strong>{C["priemer"]} dní</strong>, deti a mladiství do 17 rokov {C["deti"]} dní. Lehotu prekročilo {C["nad_lehotu"]} návrhov, zhruba každý ôsmy.</p>
    <table class="kp-t"><caption>Medián čakania na najčastejšie operácie (k {C["mediany_datum"]})</caption>
      <thead><tr><th scope="col">Výkon</th><th scope="col">Polovica pacientov čakala najviac</th></tr></thead><tbody>{rows}</tbody></table>
    <p class="hint">Zdroje: <a href="{C["zdroj_2026"][0]}" rel="nofollow">{C["zdroj_2026"][1]}</a>; <a href="{C["zdroj_2025"][0]}" rel="nofollow">{C["zdroj_2025"][1]}</a>. Čakanie v konkrétnej nemocnici sa môže výrazne líšiť.</p>
  </section>
  <section class="card">
    <h2>Lehota časovej dostupnosti</h2>
    <p>Pri plánovanej operácii vás lekár zaradí do zoznamu čakajúcich vo vašej poisťovni. Pri mnohých výkonoch (podľa ÚDZS asi pri 6 z 10 návrhov) platí <strong>lehota časovej dostupnosti</strong>: najdlhší čas, do ktorého má byť operácia urobená. Termín vám oznámi nemocnica.</p>
    <ul>
      <li><strong>Ak nemocnica lehotu nestíha</strong>, požiadajte poisťovňu o náhradného zmluvného poskytovateľa, ktorý vás operuje skôr.</li>
      <li><strong>Operácia u nezmluvného poskytovateľa alebo v inom štáte EÚ</strong>: po prekročení lehoty môžete požiadať poisťovňu o úhradu. Postup a tlačivá majú poisťovne na svojich stránkach.</li>
      <li><strong>Neskorší termín môžete aj prijať</strong>, napríklad kvôli konkrétnemu lekárovi alebo nemocnici. Podľa ÚDZS tak urobilo vyše 90 % pacientov, ktorým termín vychádzal po lehote.</li>
    </ul>
  </section>
  <section class="card">
    <h2>Kde zistiť viac</h2>
    <ul class="plain kp-links">
      <li><a href="https://ecakacielistiny.npz.sk/" rel="nofollow">Národný portál čakacích listín</a> <small>Národný portál zdravia</small></li>
      <li><a href="https://www.dovera.sk/cakacie-listiny" rel="nofollow">Dôvera: čakacie listiny</a></li>
      <li><a href="https://www.union.sk/cakacie-listiny/" rel="nofollow">Union: čakacie listiny</a></li>
      <li><a href="https://www.vszp.sk/" rel="nofollow">VšZP</a> <small>čakacie listiny v časti pre poistencov</small></li>
      <li><a href="/lekarne/?typ=nemocnice">Nemocnice na mape</a> <small>s oddeleniami</small></li>
    </ul>
    <p class="hint">Ak poisťovňa lehotu nedodrží ani nepomôže, môžete podať podnet na Úrad pre dohľad nad zdravotnou starostlivosťou (ÚDZS). Údaje overené {C["overene"]}.</p>
  </section>
  <style>
  .kp-t{{width:100%;border-collapse:collapse;margin:14px 0}}
  .kp-t caption{{text-align:left;font-weight:600;padding-bottom:8px}}
  .kp-t th,.kp-t td{{text-align:left;padding:10px 6px;border-top:1px solid var(--line)}}
  .kp-t td{{text-align:right;white-space:nowrap}}
  .kp-t thead th{{font-size:16px;color:var(--muted);font-weight:500}}
  .kp-t thead th:last-child{{text-align:right}}
  .kp-links li{{padding:6px 0}} .kp-links small{{color:var(--muted);margin-left:6px}}
  </style>"""
    write("/cakacie-lehoty/", page("Čakanie na operáciu – lehoty a práva pacienta",
                                   f"Na plánovanú operáciu sa na Slovensku čaká priemerne {C['priemer']} dní, na náhradu kolena polovica pacientov až {C['mediany'][0][1]} dní. Čo je lehota časovej dostupnosti a čo robiť, keď ju nemocnica nedodrží.",
                                   "/cakacie-lehoty/", body, breadcrumb_ld(crumb_items)))
    urls.append(("/cakacie-lehoty/", "0.5"))
    return n + 1
