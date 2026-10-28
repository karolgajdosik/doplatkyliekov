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
      if (shCb.checked && obec.value.trim().length >= 2) {
        var sent = rows.filter(function (r) { return r.cb.checked && by[r.sel.value] && r.suma != null; }).map(function (r) {
          return { kod: r.sel.value, suma: Math.round(r.suma / Math.max(1, parseInt(r.cnt.value, 10) || 1) * 100) / 100 };
        });
        if (sent.length) fetch('/api/ceny', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ obec: obec.value, lekaren: lname.value, mesiac: day.slice(0, 7), items: sent }) }).catch(function () {});
      }
    });
  });
  function alertMsg(t) { pickedEl.textContent = t; }

  /* bloček z lekárne: fotka → /api/blocek → kontrola a pridanie položiek */
  var scanIn = document.getElementById('tr-foto'), scanOut = document.getElementById('tr-scan-out');
  function shrink(file) {
    return new Promise(function (res, rej) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        var max = 1600, w = img.naturalWidth, h = img.naturalHeight, k = Math.min(1, max / Math.max(w, h));
        var c = document.createElement('canvas'); c.width = Math.round(w * k); c.height = Math.round(h * k);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', 0.85));
      };
      img.onerror = function () { URL.revokeObjectURL(url); rej(new Error('img')); };
      img.src = url;
    });
  }
  function scanSay(t, cls) { scanOut.hidden = false; scanOut.replaceChildren(el('p', cls || null, t)); }
  function review(j, all) {
    var by = {}; all.forEach(function (x) { by[x.kod] = x; });
    scanOut.replaceChildren();
    var items = (j.items || []);
    if (!items.length) return scanSay('Na fotke sme nenašli lieky. Skúste ostrejšiu fotku celého bločku pri dobrom svetle.', 'form-msg err');
    var day = j.datum && j.datum <= iso(new Date()) ? j.datum : iso(new Date());
    scanOut.append(el('p', 'eyebrow', 'Z bločku' + (j.datum ? ' zo dňa ' + skDate(j.datum) + j.datum.slice(0, 4) : '') + ' – skontrolujte a pridajte'));
    var ul = el('ul', 'glist scan-list'), rows = [];
    items.forEach(function (x) {
      var li = el('li'), cb = el('input'); cb.type = 'checkbox'; cb.checked = !!x.liek;
      var sel = el('select'); sel.setAttribute('aria-label', 'Liek pre položku ' + x.text);
      [x.liek].concat(x.ine || []).filter(Boolean).forEach(function (c) { var o = el('option', null, c.name + ' · ' + c.pack); o.value = c.kod; sel.append(o); });
      var none = el('option', null, '— nie je liek na predpis —'); none.value = ''; sel.append(none);
      if (!x.liek) { sel.value = ''; }
      var cnt = el('input'); cnt.type = 'number'; cnt.min = 1; cnt.max = 20; cnt.value = x.kusov || 1; cnt.setAttribute('aria-label', 'Počet balení');
      var info = el('small');
      function upd() { var it = by[sel.value]; cb.disabled = !it; if (!it) cb.checked = false; info.textContent = (x.suma != null ? 'Na bločku ' + eur(x.suma) + ' · ' : '') + (it ? 'do limitu sa započíta ' + eur((it.pdop || 0) * (parseInt(cnt.value, 10) || 1)) : 'nezapočíta sa'); }
      sel.addEventListener('change', function () { cb.checked = !!sel.value; upd(); }); cnt.addEventListener('input', upd); upd();
      var lab = el('label', 'scan-row'); lab.append(cb, el('span', 'scan-text', x.text));
      var ctl = el('div', 'scan-ctl'); ctl.append(sel, cnt, el('span', null, 'bal.'));
      li.append(lab, ctl, info); ul.append(li);
      rows.push({ cb: cb, sel: sel, cnt: cnt, suma: x.suma });
    });
    // dobrovoľný anonymný príspevok do prehľadu skutočných doplatkov v lekárňach
    var lk = j.lekaren || {}, share = el('div', 'scan-share');
    var shCb = el('input'); shCb.type = 'checkbox'; shCb.id = 'scan-share-cb';
    var shLab = el('label'); shLab.htmlFor = 'scan-share-cb';
    shLab.append(shCb, ' Anonymne prispieť zaplatenými sumami do prehľadu ', el('a', null, 'skutočných doplatkov v lekárňach'));
    shLab.querySelector('a').href = '/ochrana-sukromia/#ceny';
    var obec = el('input'); obec.type = 'text'; obec.maxLength = 40; obec.value = lk.obec || ''; obec.placeholder = 'Obec lekárne'; obec.setAttribute('aria-label', 'Obec, kde je lekáreň');
    var lname = el('input'); lname.type = 'text'; lname.maxLength = 60; lname.value = lk.nazov || ''; lname.placeholder = 'Názov lekárne (nepovinné)'; lname.setAttribute('aria-label', 'Názov lekárne');
    var shFields = el('div', 'scan-share-f'); shFields.append(obec, lname); shFields.hidden = true;
    shCb.addEventListener('change', function () { shFields.hidden = !shCb.checked; });
    share.append(shLab, shFields, el('small', null, 'Pošle sa len liek, suma za balenie, obec, lekáreň a mesiac. Nič o vás.'));
    var add = el('button', null, 'Pridať označené do prehľadu'); add.type = 'button';
    add.addEventListener('click', function () {
      var n0 = 0;
      rows.forEach(function (r, i) {
        var it = by[r.sel.value]; if (!r.cb.checked || !it) return;
        entries.push({ id: Date.now().toString(36) + 's' + i, d: day, kod: it.kod, name: it.name, n: Math.max(1, Math.min(20, parseInt(r.cnt.value, 10) || 1)), amt: it.pdop || 0 });
        n0++;
      });
      save(KEY, entries); curQ = quarterOf(day); render();
      if (shCb.checked && obec.value.trim().length >= 2) {
        var sent = rows.filter(function (r) { return r.cb.checked && by[r.sel.value] && r.suma != null; }).map(function (r) {
          return { kod: r.sel.value, suma: Math.round(r.suma / Math.max(1, parseInt(r.cnt.value, 10) || 1) * 100) / 100 };
        });
        if (sent.length) fetch('/api/ceny', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ obec: obec.value, lekaren: lname.value, mesiac: day.slice(0, 7), items: sent }) }).catch(function () {});
      }
      scanSay(n0 ? 'Pridané: ' + n0 + (n0 === 1 ? ' položka.' : n0 < 5 ? ' položky.' : ' položiek.') : 'Nič nebolo označené.', 'form-msg ok');
      list.scrollIntoView({ block: 'center' });
    });
    scanOut.append(ul, share, add, el('p', 'hint', 'Do limitu počítame doplatok za najlacnejší náhradný liek podľa zoznamu ministerstva, nie celú sumu z bločku.'));
  }
  if (scanIn) scanIn.addEventListener('change', function () {
    var f = scanIn.files && scanIn.files[0]; if (!f) return;
    scanSay('Čítam bloček…', 'foto-busy');
    Promise.all([shrink(f).then(function (img) {
      return fetch('/api/blocek', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ img: img }) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ''); return j; }); });
    }), data()]).then(function (res) { review(res[0], res[1]); })
      .catch(function (e) { scanSay(e.message && e.message.length > 3 && e.message !== 'img' ? e.message : 'Bloček sa nepodarilo prečítať. Skúste to znova.', 'form-msg err'); })
      .then(function () { scanIn.value = ''; });
  });
  if (new URLSearchParams(location.search).get('akcia') === 'blocek') {
    history.replaceState(null, '', location.pathname + '#tracker');
    var fb = document.querySelector('.tr-scan .foto-btn'); if (fb) { fb.classList.add('pulse'); fb.scrollIntoView({ block: 'center' }); }
  }

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
