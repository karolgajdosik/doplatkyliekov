/* Vkladaná kalkulačka doplatkov (/vlozit/okno/): hľadanie v /ai/search.json, detail skupiny z /ai/g/<n>.json.
   Výšku okna posiela rodičovskej stránke (embed.js) cez postMessage. Bez cookies a bez sledovania. */
(function () {
  'use strict';
  var q = document.getElementById('q'), res = document.getElementById('res'), out = document.getElementById('out');
  var params = new URLSearchParams(location.search), id = params.get('id') || '';
  var items = null, shards = {};
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function eur(n) { return n == null ? '–' : n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function size() { if (parent !== window) parent.postMessage({ doplatkyH: document.documentElement.scrollHeight, id: id }, '*'); }
  if (window.ResizeObserver) new ResizeObserver(size).observe(document.body); else setInterval(size, 500);
  function load() {
    if (!items) items = fetch('/ai/search.json').then(function (r) { return r.json(); }).then(function (j) {
      return j.items.map(function (it) { return { kod: it[0], name: it[1], gi: it[2], subst: j.groups[it[2]][0], f: j.groups[it[2]][1] }; });
    });
    return items;
  }
  function shard(gi) {
    var n = Math.floor(gi / 100);
    if (!shards[n]) shards[n] = fetch('/ai/g/' + n + '.json').then(function (r) { return r.json(); });
    return shards[n].then(function (s) { return s[String(gi)]; });
  }
  var tmr;
  q.addEventListener('focus', load, { once: true });
  q.addEventListener('input', function () {
    clearTimeout(tmr);
    tmr = setTimeout(function () {
      var t = q.value.trim();
      if (t.length < 2) { res.replaceChildren(); return; }
      load().then(function (list) {
        var hits = window.Hladaj ? window.Hladaj.find(list, t, { limit: 8 }) : [];
        res.replaceChildren();
        if (!hits.length) { res.append(el('li', 'msg', 'Liek sme nenašli. Skúste názov účinnej látky.')); return; }
        hits.forEach(function (x) {
          var li = el('li'), b = el('button'); b.type = 'button';
          var l = el('span', null, x.name); l.append(el('small', null, x.subst + ' · ' + x.f.replace(/^p\.o\.\s*/, '')));
          b.append(l); b.addEventListener('click', function () { pick(x); });
          li.append(b); res.append(li);
        });
      });
    }, 150);
  });
  function pick(x) {
    res.replaceChildren(); q.value = x.name;
    out.replaceChildren(el('p', 'msg', 'Načítavam…'));
    shard(x.gi).then(function (g) {
      var rows = g.i.filter(function (r) { return r[3] != null; }), me = g.i.filter(function (r) { return r[0] === x.kod; })[0];
      if (!me) { out.replaceChildren(el('p', 'msg', 'Údaje o lieku sa nepodarilo načítať.')); return; }
      var c = el('div', 'card');
      c.append(el('h2', null, me[1]), el('p', 'pack', me[2]));
      var d = el('p', null, 'Doplatok: '); d.append(el('span', 'big num', eur(me[3]))); c.append(d);
      var cheaper = rows.filter(function (r) { return r[0] !== me[0] && r[3] < me[3] - 0.005; }).slice(0, 3);
      if (cheaper.length) {
        c.append(el('p', null, 'Lacnejšie s rovnakou látkou, silou a balením:'));
        var ul = el('ul', 'alt');
        cheaper.forEach(function (r) {
          var li = el('li'), a = el('a', null, r[1]); a.href = 'https://doplatkyliekov.sk/liek/' + r[8] + '/?zdroj=vlozene'; a.target = '_blank'; a.rel = 'noopener';
          var p = el('span', 'num', eur(r[3])); p.append(el('span', 'save', 'o ' + eur(me[3] - r[3]) + ' menej'));
          li.append(a, p); ul.append(li);
        });
        c.append(ul);
        c.append(el('p', 'msg', 'Lekárnik vám lacnejší liek môže vydať, ak lekár na recepte nevyznačil, že sa nesmie zamieňať. O zmene sa poraďte s lekárom alebo lekárnikom.'));
      } else c.append(el('p', 'ok', me[3] < 0.005 ? 'Tento liek je bez doplatku.' : 'Tento liek patrí medzi najlacnejšie vo svojej skupine.'));
      var more = el('a', 'more', 'Podrobnosti o lieku →'); more.href = 'https://doplatkyliekov.sk/liek/' + me[8] + '/?zdroj=vlozene'; more.target = '_blank'; more.rel = 'noopener';
      c.append(more);
      out.replaceChildren(c);
    }).catch(function () { out.replaceChildren(el('p', 'msg', 'Údaje sa nepodarilo načítať. Skúste to o chvíľu.')); });
  }
  size();
  // človek mohol začať písať skôr, ako sa tento skript načítal
  if (q.value.trim().length >= 2) q.dispatchEvent(new Event('input'));
})();
