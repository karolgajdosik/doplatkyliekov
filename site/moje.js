/* Moje lieky: zoznam liekov uložený len v prehliadači používateľa (localStorage),
   kalkulačka ročného doplatku, tlač a zdieľanie zoznamu, e-mailové upozornenia a inštalácia aplikácie.
   Používa ho každá stránka webu. */
(function () {
  'use strict';
  var KEY = 'mojeLieky.v1';

  function read() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  }
  function write(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* súkromné okno, plné úložisko */ }
    refresh();
  }
  var Moje = {
    list: read,
    has: function (kod) { return read().some(function (x) { return x.kod === kod; }); },
    add: function (item) { var l = read().filter(function (x) { return x.kod !== item.kod; }); l.push(item); write(l); },
    remove: function (kod) { write(read().filter(function (x) { return x.kod !== kod; })); },
    update: function (kod, patch) {
      write(read().map(function (x) { if (x.kod === kod) { for (var k in patch) x[k] = patch[k]; } return x; }));
    },
    toggle: function (item) { if (Moje.has(item.kod)) Moje.remove(item.kod); else Moje.add(item); }
  };
  window.Moje = Moje;

  function eur(n) {
    return n == null ? '–' : n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  }
  function num(n, d) { return n.toLocaleString('sk-SK', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function skDate(iso) { var p = iso.split('-'); return (+p[2]) + '. ' + (+p[1]) + '. ' + p[0]; }
  function dose(v) { var d = parseFloat(String(v == null ? '' : v).replace(',', '.')); return d > 0 && d <= 20 ? d : 1; }

  /* tlačidlá „Pridať do Mojich liekov“ */
  function paintButton(b) {
    var on = Moje.has(b.getAttribute('data-kod'));
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    var t = b.querySelector('.mine-label');
    if (t) t.textContent = on ? 'Uložené v Mojich liekoch' : 'Pridať do Mojich liekov';
  }
  function refresh() {
    var n = read().length;
    document.querySelectorAll('[data-mine-count]').forEach(function (e) { e.textContent = n ? String(n) : ''; e.hidden = !n; });
    document.querySelectorAll('.mine-btn[data-kod]').forEach(paintButton);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.mine-btn[data-kod]');
    if (!b) return;
    ev.preventDefault();
    var item = { kod: b.getAttribute('data-kod'), name: b.getAttribute('data-name') || '', slug: b.getAttribute('data-slug') || '' };
    var yc = document.querySelector('.year-calc input');
    if (yc && !Moje.has(item.kod)) item.d = dose(yc.value);
    Moje.toggle(item);
    if (window.renderMoje) window.renderMoje();
  });

  /* kalkulačka ročného doplatku na stránke lieku */
  function bindYearCalc(box) {
    var ks = +box.getAttribute('data-ks'), dop = +box.getAttribute('data-dop');
    var best = box.hasAttribute('data-best') ? +box.getAttribute('data-best') : null;
    var inp = box.querySelector('input');
    var kod = (document.querySelector('.mine-btn[data-kod]') || { getAttribute: function () { return null; } }).getAttribute('data-kod');
    var saved = read().filter(function (x) { return x.kod === kod; })[0];
    if (saved && saved.d) inp.value = saved.d;
    function set(k, t) { var e = box.querySelector('[data-yc="' + k + '"]'); if (e) e.textContent = t; }
    function calc() {
      var d = dose(inp.value), packs = 365 * d / ks;
      var days = ks / d;
      set('days', (days >= 10 ? num(days) : num(days, 1)) + ' ' + (days === 1 ? 'deň' : days < 5 && days % 1 === 0 ? 'dni' : 'dní'));
      set('packs', num(packs, 1));
      set('year', eur(packs * dop));
      if (best != null) { set('best', eur(packs * best)); set('save', eur(packs * (dop - best))); }
      if (kod && Moje.has(kod)) Moje.update(kod, { d: d });
    }
    box.querySelectorAll('button[data-step]').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = Math.max(0.25, Math.min(20, dose(inp.value) + parseFloat(b.getAttribute('data-step'))));
        inp.value = v; calc();
      });
    });
    inp.addEventListener('input', calc);
    calc();
  }

  /* formulár e-mailových upozornení */
  function bindForm(form) {
    if (form.dataset.bound) return;
    form.dataset.bound = '1';
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var out = form.querySelector('.form-msg');
      var email = (form.querySelector('[name=email]').value || '').trim();
      var consent = form.querySelector('[name=consent]').checked;
      var hp = (form.querySelector('[name=web]') || {}).value || '';
      var kody = read().map(function (x) { return x.kod; });
      var own = form.getAttribute('data-kod');
      if (own && kody.indexOf(own) < 0) kody.push(own);
      function say(t, ok) { out.textContent = t; out.className = 'form-msg ' + (ok ? 'ok' : 'err'); }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return say('Zadajte platnú e-mailovú adresu.');
      if (!consent) return say('Na zasielanie upozornení potrebujeme váš súhlas.');
      if (!kody.length) return say('Najprv si uložte aspoň jeden liek do Mojich liekov.');
      var btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      fetch('/api/subscribe', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, kody: kody, consent: true, web: hp })
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, j: j }; });
      }).then(function (res) {
        if (res.status === 200) say('Hotovo. Poslali sme vám e-mail, potvrďte v ňom prihlásenie.', true);
        else if ([404, 405, 501, 503].indexOf(res.status) >= 0) say('E-mailové upozornenia zatiaľ spúšťame. Skúste to prosím o pár dní.');
        else say(res.j.error || 'Prihlásenie sa nepodarilo. Skúste to znova.');
      }).catch(function () { say('Nepodarilo sa spojiť so serverom. Skúste to znova.'); })
        .then(function () { btn.disabled = false; });
    });
  }

  /* zdieľaný zoznam: /moje-lieky/?l=KOD,KOD*2,... (číslo za * = dávok denne) */
  function sharedList() {
    var q = new URLSearchParams(location.search).get('l');
    if (!q) return null;
    var out = [];
    q.split(',').forEach(function (part) {
      var m = /^([0-9A-Z]{4,6})(?:\*([0-9.]+))?$/.exec(part.trim().toUpperCase());
      if (m && out.length < 60) out.push({ kod: m[1], d: m[2] ? dose(m[2]) : undefined });
    });
    return out.length ? out : null;
  }
  function shareUrl(list) {
    return location.origin + '/moje-lieky/?l=' + list.map(function (m) {
      return m.kod + (m.d && m.d !== 1 ? '*' + m.d : '');
    }).join(',');
  }

  /* stránka /moje-lieky/ */
  var cache = null, slugCache = null;
  function loadData() {
    if (cache) return cache;
    cache = Promise.all([
      fetch('/data.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }),
      fetch('/alerts.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : { items: {} }; }).catch(function () { return { items: {} }; })
    ]);
    return cache;
  }
  function loadSlugs() {
    if (!slugCache) slugCache = fetch('/slugs.json').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return slugCache;
  }

  window.renderMoje = function () {
    var root = document.getElementById('moje-root');
    if (!root) return;
    var shared = sharedList();
    var list = shared || read();
    var tools = document.getElementById('mine-tools');
    if (!list.length) {
      if (tools) tools.hidden = true;
      root.replaceChildren();
      var empty = el('div', 'card empty-state');
      empty.append(el('h2', null, 'Zatiaľ nemáte uložený žiadny liek'));
      var p = el('p', 'page-sub');
      p.append('Vyhľadajte liek, ktorý užívate, a na jeho stránke kliknite na ', el('strong', null, 'Pridať do Mojich liekov'), '. Zoznam sa uloží len vo vašom prehliadači.');
      var a = el('a', 'cta', 'Vyhľadať liek →'); a.href = '/';
      empty.append(p, a);
      root.append(empty);
      return;
    }
    Promise.all([loadData(), shared ? loadSlugs() : Promise.resolve({})]).then(function (all) {
      var data = all[0][0], alerts = all[0][1] || { items: {} }, slugs = all[1];
      var byKod = {};
      data.groups.forEach(function (g) { g.i.forEach(function (it) { byKod[it[0]] = { g: g, it: it }; }); });
      root.replaceChildren();
      var totalPack = 0, yearNow = 0, yearBest = 0, yearKnown = 0;
      var ul = el('ul', 'glist mine-list');
      var prows = [];
      list.forEach(function (m) {
        var hit = byKod[m.kod];
        var name = m.name || (hit ? hit.it[1] : m.kod);
        var slug = m.slug || slugs[m.kod];
        var li = el('li');
        var line = el('div', 'gline');
        var a = el('a', null, name); a.href = slug ? '/liek/' + slug + '/' : '#';
        line.append(a);
        var prow = { name: name, kod: m.kod, pack: '', dose: '', dop: '–', alt: '' };
        if (!hit) {
          line.append(el('span', 'mono', '–'));
          line.append(el('small', null, 'Liek už nie je v zozname hradených liekov.'));
        } else {
          var it = hit.it, g = hit.g, ks = it[8], d = dose(m.d);
          prow.pack = it[2]; prow.dop = eur(it[5]);
          line.append(el('span', 'mono', eur(it[5])));
          line.append(el('small', null, it[2]));
          var cheapest = g.i.filter(function (x) { return x[5] != null; }).sort(function (a, b) { return a[5] - b[5]; })[0];
          var diff = (cheapest && it[5] != null) ? it[5] - cheapest[5] : 0;
          if (diff > 0.005) {
            totalPack += diff;
            var s = el('small', 'mine-save');
            s.append('Lacnejšia alternatíva: ' + cheapest[1] + ' za ' + eur(cheapest[5]) + ' (ušetríte ' + eur(diff) + ' na balení)');
            line.append(s);
            prow.alt = cheapest[1] + ' (' + eur(cheapest[5]) + ')';
          }
          if (ks && it[5] != null) {
            var packs = 365 * d / ks;
            yearNow += packs * it[5]; yearBest += packs * (it[5] - Math.max(diff, 0)); yearKnown++;
            var yr = el('div', 'mine-dose');
            var lab = el('label', null, 'Denne ');
            var inp = el('input'); inp.type = 'number'; inp.min = '0.25'; inp.max = '20'; inp.step = '0.25'; inp.value = d; inp.inputMode = 'decimal';
            inp.setAttribute('aria-label', 'Počet denne: ' + name);
            if (shared) inp.disabled = true;
            inp.addEventListener('change', function () { Moje.update(m.kod, { d: dose(inp.value) }); window.renderMoje(); });
            lab.append(inp, ' ks');
            yr.append(lab, el('span', null, 'ročne ' + eur(packs * it[5]) + (diff > 0.005 ? ', s alternatívou ' + eur(packs * (it[5] - diff)) : '')));
            line.append(yr);
            prow.dose = d.toLocaleString('sk-SK', { maximumFractionDigits: 2 }) + ' denne';
          }
          var al = alerts.items && alerts.items[m.kod];
          if (al && al.n !== undefined && alerts.next) {
            line.append(el('small', 'mine-warn', al.n === null
              ? 'Od ' + skDate(alerts.next) + ' liek vypadne zo zoznamu hradených liekov.'
              : 'Od ' + skDate(alerts.next) + ' doplatok ' + (al.n > it[5] ? 'stúpne' : 'klesne') + ' na ' + eur(al.n) + '.'));
          }
          if (al && al.v) {
            var txt = { R: 'Prerušené dodávky od ', Z: 'Ukončené dodávky od ', PR: 'Ohlásené prerušenie dodávok od ', PZ: 'Ohlásené ukončenie dodávok od ' }[al.v[0]];
            if (txt) line.append(el('small', 'mine-warn', txt + skDate(al.v[1]) + '.'));
          }
        }
        li.append(line);
        if (!shared) {
          var rm = el('button', 'mine-remove', 'Odobrať'); rm.type = 'button';
          rm.addEventListener('click', function () { Moje.remove(m.kod); window.renderMoje(); });
          li.append(rm);
        }
        ul.append(li);
        prows.push(prow);
      });

      var head = el('div', 'mine-summary');
      if (shared) {
        var banner = el('div', 'card shared-banner');
        banner.append(el('h2', null, 'Zdieľaný zoznam liekov'));
        banner.append(el('p', 'page-sub', 'Niekto vám poslal tento zoznam. Môžete si ho vytlačiť alebo uložiť do svojich Mojich liekov.'));
        var save = el('button', null, 'Uložiť do mojich liekov'); save.type = 'button';
        save.addEventListener('click', function () {
          list.forEach(function (m) {
            var hit = byKod[m.kod];
            if (!Moje.has(m.kod)) Moje.add({ kod: m.kod, name: hit ? hit.it[1] : m.kod, slug: slugs[m.kod] || '', d: m.d });
          });
          location.href = '/moje-lieky/';
        });
        var mine = el('a', 'linkish', 'Zobraziť moje vlastné lieky'); mine.href = '/moje-lieky/';
        banner.append(save, ' ', mine);
        root.append(banner);
      }
      head.append(el('p', 'eyebrow', (shared ? 'Liekov v zozname: ' : 'Uložené lieky: ') + list.length));
      if (totalPack > 0.005) {
        var t = el('p', 'mine-total');
        t.append('Pri prechode na lacnejšie alternatívy ušetríte ', el('b', null, eur(totalPack)), ' na jednom nákupe');
        if (yearKnown && yearNow - yearBest > 0.005) t.append(' a približne ', el('b', null, eur(yearNow - yearBest)), ' za rok');
        t.append('.');
        head.append(t);
      }
      if (yearKnown) {
        head.append(el('p', 'mine-year', 'Ročne doplatíte približne ' + eur(yearNow) +
          (yearKnown < list.length ? ' (za ' + yearKnown + ' z ' + list.length + ' liekov, pri ostatných nevieme spotrebu vypočítať)' : '') + '.'));
      }
      root.append(head, ul);

      /* tabuľka len pre tlač */
      var tbl = el('table', 'print-only print-table');
      var thead = el('thead'); var hr = el('tr');
      ['Liek', 'Balenie', 'Kód ŠÚKL', 'Dávkovanie', 'Doplatok', 'Lacnejšia alternatíva'].forEach(function (h) { hr.append(el('th', null, h)); });
      thead.append(hr); tbl.append(thead);
      var tb = el('tbody');
      prows.forEach(function (r) {
        var tr = el('tr');
        [r.name, r.pack, r.kod, r.dose, r.dop, r.alt].forEach(function (c) { tr.append(el('td', null, c)); });
        tb.append(tr);
      });
      tbl.append(tb);
      var note = el('p', 'print-only print-note', 'Pán doktor / pani doktorka, prosím o posúdenie, či je možné predpísať liek s nižším doplatkom alebo predpisovať názvom účinnej látky. Alternatívy majú rovnakú účinnú látku, silu a veľkosť balenia.');
      root.append(tbl, note);

      if (tools) {
        tools.hidden = false;
        var shareBtn = document.getElementById('mine-share');
        if (shareBtn) shareBtn.hidden = !!shared;
      }
    }).catch(function () {
      root.replaceChildren(el('p', 'page-sub', 'Údaje o liekoch sa nepodarilo načítať. Obnovte stránku.'));
    });
  };

  function bindTools() {
    var pr = document.getElementById('mine-print'), sh = document.getElementById('mine-share'), msg = document.getElementById('mine-tools-msg');
    var pd = document.getElementById('print-date');
    if (pd) pd.textContent = new Date().toLocaleDateString('sk-SK');
    if (pr) pr.addEventListener('click', function () { window.print(); });
    if (sh) sh.addEventListener('click', function () {
      var url = shareUrl(read());
      function say(t) { if (msg) { msg.textContent = t; msg.className = 'form-msg ok'; } }
      if (navigator.share) {
        navigator.share({ title: 'Moje lieky', text: 'Zoznam liekov, ktoré užívam', url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () { say('Odkaz je skopírovaný. Pošlite ho rodine alebo lekárovi.'); },
          function () { prompt('Skopírujte odkaz:', url); });
      } else { prompt('Skopírujte odkaz:', url); }
    });
  }

  /* aplikácia: service worker a inštalácia */
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); deferred = e; showInstall();
  });
  function standalone() { return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone; }
  function showInstall() {
    var card = document.getElementById('install-card');
    if (!card || standalone()) return;
    var btn = document.getElementById('install-btn'), txt = document.getElementById('install-text');
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (deferred) {
      card.hidden = false; btn.hidden = false;
      btn.onclick = function () { deferred.prompt(); deferred.userChoice.then(function () { deferred = null; card.hidden = true; }); };
    } else if (ios) {
      card.hidden = false;
      txt.textContent = 'Pridajte si web na plochu iPhonu: v Safari ťuknite na tlačidlo Zdieľať (štvorec so šípkou) a vyberte „Pridať na plochu“. Otvorí sa ako aplikácia a Moje lieky budete mať vždy po ruke.';
    }
  }
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(function () {}); });
  }

  document.addEventListener('moje:refresh', refresh);

  function init() {
    refresh();
    document.querySelectorAll('form.alert-form:not(#manage-link-form)').forEach(bindForm);
    document.querySelectorAll('.year-calc').forEach(bindYearCalc);
    bindTools();
    showInstall();
    window.renderMoje();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
