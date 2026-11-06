/* Vyhľadávanie zdravotníckych pomôcok na /pomocky/ – dáta /pomocky.json sa načítajú až pri písaní. */
(function () {
  'use strict';
  var q = document.getElementById('zp-q'), out = document.getElementById('zp-out');
  if (!q || !out) return;
  var SRC = q.getAttribute('data-src') || '/pomocky.json', BASE = q.getAttribute('data-base') || '/pomocky/';
  var data = null, loading = null, timer = null;
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function load() {
    if (data) return Promise.resolve(data);
    if (!loading) loading = fetch(SRC).then(function (r) { return r.json(); }).then(function (d) {
      d.i.forEach(function (x) { x.k = norm(x[0] + ' ' + d.g[x[1]][1] + ' ' + x[3]); });
      data = d; return d;
    });
    return loading;
  }
  function eur(n) { return n == null ? '–' : n.toFixed(2).replace('.', ',') + ' €'; }
  function li(href, text, sub) {
    var l = document.createElement('li'), a = document.createElement('a');
    a.href = href; a.textContent = text; l.appendChild(a);
    if (sub) { var s = document.createElement('small'); s.textContent = ' ' + sub; l.appendChild(s); }
    return l;
  }
  function run() {
    var t = norm(q.value.trim());
    out.replaceChildren();
    if (t.length < 2) return;
    load().then(function (d) {
      var words = t.split(/\s+/);
      var groups = d.g.map(function (g, i) { return [i, norm(g[1])]; }).filter(function (g) {
        return words.every(function (w) { return g[1].indexOf(w) >= 0; });
      }).slice(0, 6);
      var items = d.i.filter(function (x) { return words.every(function (w) { return x.k.indexOf(w) >= 0; }); })
        .sort(function (a, b) { return (a[2] == null ? 9e9 : a[2]) - (b[2] == null ? 9e9 : b[2]); }).slice(0, 25);
      out.replaceChildren();
      groups.forEach(function (g) { out.appendChild(li(BASE + d.g[g[0]][0] + '/', d.g[g[0]][1], '– celá skupina')); });
      items.forEach(function (x) {
        out.appendChild(li(BASE + d.g[x[1]][0] + '/#' + encodeURIComponent(x[3]), x[0], '· doplatok ' + eur(x[2]) + ' · ' + d.g[x[1]][1]));
      });
      if (!groups.length && !items.length) out.appendChild(li(BASE, 'Nič sme nenašli. Skúste iné slovo alebo prejdite skupiny nižšie.'));
    }).catch(function () { out.appendChild(li(BASE, 'Vyhľadávanie sa nepodarilo načítať. Skúste obnoviť stránku.')); });
  }
  q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 180); });
  q.addEventListener('focus', load, { once: true });
})();
