/* Prehľad doplatkov pre ochranný limit: nákupy sa ukladajú len v prehliadači (localStorage). */
(function () {
  'use strict';
  var KEY = 'limitTracker.v1', SET = 'limitSettings.v1';
  var box = document.getElementById('tracker');
  if (!box) return;

  function load(k, def) { try { var v = JSON.parse(localStorage.getItem(k) || 'null'); return v == null ? def : v; } catch (e) { return def; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* bez úložiska */ } }
  function eur(n) { return n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function norm(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function quarterOf(isoDate) { var y = +isoDate.slice(0, 4), m = +isoDate.slice(5, 7); return y * 4 + Math.floor((m - 1) / 3); }
  function qLabel(q) { return (q % 4 + 1) + '. štvrťrok ' + Math.floor(q / 4); }
  function skDate(s) { var p = s.split('-'); return (+p[2]) + '. ' + (+p[1]) + '.'; }

  var entries = load(KEY, []);
  if (!Array.isArray(entries)) entries = [];
  var curQ = quarterOf(iso(new Date()));
  var picked = null, items = null;

  var q = document.getElementById('tr-q'), res = document.getElementById('tr-results'), n = document.getElementById('tr-n');
  var d = document.getElementById('tr-d'), submit = document.getElementById('tr-submit'), pickedEl = document.getElementById('tr-picked');
  var list = document.getElementById('tr-list'), sum = document.getElementById('tr-sum');
  d.value = iso(new Date());

  /* nastavenia kalkulačky (kto som) si pamätáme */
  var sk = document.getElementById('skupina'), pr = document.getElementById('prijem');
  var st = load(SET, null);
  if (st && sk && pr) {
    if (st.g) sk.value = st.g; if (st.p) pr.value = st.p;
    sk.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function limit() {
    if (!sk) return 30;
    var g = sk.value, low = pr && pr.value === 'nizky';
    if (g === 'iny') return null;
    return g === 'dieta' ? 0 : low ? 0 : (g === 'ztp' ? 12 : 30);
  }
  [sk, pr].forEach(function (s) {
    if (s) s.addEventListener('change', function () { save(SET, { g: sk.value, p: pr && pr.value }); render(); });
  });

  function data() {
    if (items) return Promise.resolve(items);
    return fetch('/data.json').then(function (r) { return r.json(); }).then(function (j) {
      items = [];
      j.groups.forEach(function (g) {
        g.i.forEach(function (it) {
          items.push({ kod: it[0], name: it[1], pack: it[2], dop: it[5], pdop: it[7] != null ? it[7] : it[5], key: norm(it[1] + ' ' + g.s) });
        });
      });
      return items;
    });
  }

  function choose(it) {
    picked = it;
    q.value = it.name;
    res.hidden = true;
    submit.disabled = false;
    pickedEl.textContent = it.pack + ' · do limitu sa započíta ' + eur(it.pdop || 0) + ' za balenie (doplatok ' + eur(it.dop || 0) + ')';
  }
  q.addEventListener('input', function () {
    picked = null; submit.disabled = true; pickedEl.textContent = '';
    var t = norm(q.value.trim());
    if (t.length < 2) { res.hidden = true; return; }
    var token = q.value;
    data().then(function (all) {
      if (q.value !== token || picked) return;  // medzitým sa text zmenil alebo je liek vybraný
      var words = t.split(/\s+/);
      var hits = all.filter(function (x) { return words.every(function (w) { return x.key.indexOf(w) >= 0; }); }).slice(0, 8);
      res.replaceChildren();
      hits.forEach(function (it) {
        var li = el('li'); var b = el('button'); b.type = 'button';
        b.append(el('span', null, it.name), el('small', null, it.pack + ' · ' + eur(it.pdop || 0)));
        b.addEventListener('click', function () { choose(it); });
        li.append(b); res.append(li);
      });
      if (!hits.length) res.append(el('li', 'tr-none', 'Nič sme nenašli.'));
      res.hidden = false;
    });
  });

  document.getElementById('tr-add').addEventListener('submit', function (ev) {
    ev.preventDefault();
    if (!picked) return;
    var cnt = Math.max(1, Math.min(99, parseInt(n.value, 10) || 1));
    entries.push({ id: Date.now().toString(36), d: d.value || iso(new Date()), kod: picked.kod, name: picked.name, n: cnt, amt: picked.pdop || 0 });
    save(KEY, entries);
    curQ = quarterOf(d.value || iso(new Date()));
    picked = null; q.value = ''; n.value = 1; submit.disabled = true; pickedEl.textContent = ''; res.hidden = true;
    render();
  });

  document.getElementById('tr-manual').addEventListener('click', function () {
    var v = prompt('Suma, ktorá sa započíta do limitu (€):', '');
    if (v == null) return;
    var a = parseFloat(String(v).replace(',', '.'));
    if (!(a > 0)) return;
    var name = prompt('Popis (napríklad názov lieku):', 'Ručne zadaná suma') || 'Ručne zadaná suma';
    entries.push({ id: Date.now().toString(36), d: d.value || iso(new Date()), name: name, n: 1, amt: Math.round(a * 100) / 100 });
    save(KEY, entries); curQ = quarterOf(d.value || iso(new Date())); render();
  });

  document.getElementById('tr-mine').addEventListener('click', function () {
    var mine = window.Moje ? window.Moje.list() : [];
    if (!mine.length) { alertMsg('V Mojich liekoch nemáte uložený žiadny liek.'); return; }
    data().then(function (all) {
      var by = {}; all.forEach(function (x) { by[x.kod] = x; });
      var day = d.value || iso(new Date()), added = 0;
      mine.forEach(function (m) {
        var it = by[m.kod]; if (!it) return;
        entries.push({ id: Date.now().toString(36) + added, d: day, kod: it.kod, name: it.name, n: 1, amt: it.pdop || 0 });
        added++;
      });
      save(KEY, entries); curQ = quarterOf(day); render();
    });
  });
  function alertMsg(t) { pickedEl.textContent = t; }

  box.querySelectorAll('[data-q]').forEach(function (b) {
    b.addEventListener('click', function () { curQ += +b.getAttribute('data-q'); render(); });
  });

  function render() {
    document.getElementById('tr-qlabel').textContent = qLabel(curQ);
    var mine = entries.filter(function (e) { return quarterOf(e.d) === curQ; }).sort(function (a, b) { return a.d < b.d ? -1 : 1; });
    list.replaceChildren();
    var total = 0;
    mine.forEach(function (e) {
      var line = e.amt * e.n; total += line;
      var li = el('li'); var g = el('div', 'gline');
      g.append(el('span', 'tr-name', e.name), el('span', 'mono', eur(line)));
      g.append(el('small', null, skDate(e.d) + ' · ' + e.n + ' × ' + eur(e.amt)));
      var rm = el('button', 'mine-remove', 'Odobrať'); rm.type = 'button';
      rm.addEventListener('click', function () { entries = entries.filter(function (x) { return x.id !== e.id; }); save(KEY, entries); render(); });
      li.append(g, rm); list.append(li);
    });
    if (!mine.length) list.append(el('li', 'tr-empty', 'V tomto štvrťroku zatiaľ nemáte zapísaný žiadny nákup.'));
    sum.replaceChildren();
    var L = limit();
    var p1 = el('p'); p1.append('Započítané doplatky: ', el('b', null, eur(total)));
    sum.append(p1);
    var p2 = el('p');
    if (L == null) p2.textContent = 'Podľa kalkulačky vyššie sa na vás zákonný ochranný limit nevzťahuje.';
    else {
      var back = Math.max(0, total - L);
      p2.append('Váš limit: ' + eur(L) + '. ');
      if (back >= 3) p2.append('Poisťovňa vám približne vráti ', el('b', 'save', eur(back)), ' do 90 dní po skončení štvrťroka.');
      else if (back > 0) p2.append('Preplatok ' + eur(back) + ' je nižší ako 3 €, prenesie sa do ďalšieho štvrťroka.');
      else if (L === 0) p2.append('Pri nulovom limite by ste doplatok za najlacnejší náhradný liek nemali platiť už v lekárni.');
      else p2.append('Do limitu vám chýba ' + eur(L - total) + '.');
    }
    sum.append(p2);
  }
  render();
})();
