/* Stránka lieku: skutočné doplatky v lekárňach, ktoré anonymne nahlásili používatelia z bločkov (/api/ceny). */
(function () {
  'use strict';
  var card = document.querySelector('[data-ceny]');
  if (!card) return;
  var kod = card.getAttribute('data-ceny'), max = parseFloat(card.getAttribute('data-max'));
  var out = card.querySelector('.ceny-out');
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function eur(n) { return n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function load() {
    fetch('/api/ceny?kod=' + encodeURIComponent(kod)).then(function (r) { return r.ok ? r.json() : { n: 0 }; }).then(function (j) {
      out.replaceChildren();
      if (!j.n) {
        out.append(el('p', null, 'Zatiaľ nikto nenahlásil, koľko za tento liek naozaj zaplatil. Lekárne môžu doplatok znížiť pod hodnotu zo zoznamu.'));
      } else {
        var sum = el('div', 'ceny-sum');
        var a = el('div', null, 'Najnižšie zaplatené'); a.append(el('b', null, eur(j.min)));
        var b = el('div', null, 'Bežne'); b.append(el('b', null, eur(j.median)));
        var c = el('div', null, 'Podľa zoznamu najviac'); c.append(el('b', null, isFinite(max) ? eur(max) : '–'));
        sum.append(a, b, c); out.append(sum);
        var ul = el('ul');
        (j.obce || []).forEach(function (o) {
          var li = el('li'), l = el('span', null, o.obec); if (o.lekaren) l.append(' ', el('small', null, o.lekaren));
          li.append(l, el('span', 'num', 'od ' + eur(o.min) + ' · ' + o.n + '×')); ul.append(li);
        });
        out.append(ul, el('p', 'hint', 'Nahlásené ' + j.n + '× za posledné 3 mesiace. Údaje zadávajú používatelia z bločkov, neoverujeme ich.'));
      }
      var cta = el('p', 'hint'); cta.append('Pomôžte ostatným: odfoťte bloček v ', el('a', null, 'prehľade doplatkov'), ' a zaškrtnite anonymný príspevok.');
      cta.querySelector('a').href = '/ochranny-limit/?akcia=blocek#tracker';
      out.append(cta);
      card.hidden = false;
    }).catch(function () {});
  }
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (e) { if (e[0].isIntersecting) { io.disconnect(); load(); } }, { rootMargin: '400px' });
    card.hidden = false; io.observe(card);
  } else load();
})();
