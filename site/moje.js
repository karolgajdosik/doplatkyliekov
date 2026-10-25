/* Moje lieky: zoznam liekov uložený len v prehliadači používateľa (localStorage)
   + formulár na e-mailové upozornenia. Používa ho hlavná stránka, stránky liekov a /moje-lieky/. */
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
    toggle: function (item) { if (Moje.has(item.kod)) Moje.remove(item.kod); else Moje.add(item); }
  };
  window.Moje = Moje;

  function eur(n) {
    return n == null ? '–' : n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function skDate(iso) { var p = iso.split('-'); return (+p[2]) + '. ' + (+p[1]) + '. ' + p[0]; }

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
    Moje.toggle({ kod: b.getAttribute('data-kod'), name: b.getAttribute('data-name') || '', slug: b.getAttribute('data-slug') || '' });
    if (window.renderMoje) window.renderMoje();
  });

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

  /* stránka /moje-lieky/ */
  var cache = null;
  function loadData() {
    if (cache) return cache;
    cache = Promise.all([
      fetch('/data.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }),
      fetch('/alerts.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : { items: {} }; }).catch(function () { return { items: {} }; })
    ]);
    return cache;
  }
  window.renderMoje = function () {
    var root = document.getElementById('moje-root');
    if (!root) return;
    var list = read();
    if (!list.length) {
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
    loadData().then(function (res) {
      var data = res[0], alerts = res[1] || { items: {} };
      var byKod = {};
      data.groups.forEach(function (g) {
        g.i.forEach(function (it) { byKod[it[0]] = { g: g, it: it }; });
      });
      root.replaceChildren();
      var total = 0;
      var ul = el('ul', 'glist mine-list');
      list.forEach(function (m) {
        var hit = byKod[m.kod];
        var li = el('li');
        var line = el('div', 'gline');
        var a = el('a', null, m.name || m.kod); a.href = m.slug ? '/liek/' + m.slug + '/' : '#';
        line.append(a);
        if (!hit) {
          line.append(el('span', 'mono', '–'));
          line.append(el('small', null, 'Liek už nie je v zozname hradených liekov.'));
        } else {
          var it = hit.it, g = hit.g;
          line.append(el('span', 'mono', eur(it[5])));
          line.append(el('small', null, it[2]));
          var cheapest = g.i.filter(function (x) { return x[5] != null; }).sort(function (a, b) { return a[5] - b[5]; })[0];
          if (cheapest && it[5] != null && it[5] - cheapest[5] > 0.005) {
            total += it[5] - cheapest[5];
            var s = el('small', 'mine-save');
            s.append('Lacnejšia alternatíva: ' + cheapest[1] + ' za ' + eur(cheapest[5]) + ' (ušetríte ' + eur(it[5] - cheapest[5]) + ')');
            line.append(s);
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
        var rm = el('button', 'mine-remove', 'Odobrať'); rm.type = 'button';
        rm.addEventListener('click', function () { Moje.remove(m.kod); window.renderMoje(); });
        li.append(line, rm);
        ul.append(li);
      });
      var head = el('div', 'mine-summary');
      head.append(el('p', 'eyebrow', 'Uložené lieky: ' + list.length));
      if (total > 0.005) {
        var t = el('p', 'mine-total');
        t.append('Pri prechode na lacnejšie alternatívy ušetríte až ', el('b', null, eur(total)), ' na jednom nákupe.');
        head.append(t);
      }
      root.append(head, ul);
    }).catch(function () {
      root.replaceChildren(el('p', 'page-sub', 'Údaje o liekoch sa nepodarilo načítať. Obnovte stránku.'));
    });
  };

  document.addEventListener('moje:refresh', refresh);

  function init() {
    refresh();
    document.querySelectorAll('form.alert-form').forEach(bindForm);
    window.renderMoje();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
