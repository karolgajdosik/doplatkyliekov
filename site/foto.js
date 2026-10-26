/* Rozpoznanie lieku z fotky balenia alebo receptu (úvodná stránka). Fotka sa zmenší v prehliadači
   a pošle na /api/foto; server ju neukladá. */
(function () {
  'use strict';
  var inp = document.getElementById('foto-in'), out = document.getElementById('foto-out');
  if (!inp || !out) return;
  var lang = document.documentElement.lang;
  var L = {
    sk: { busy: 'Rozpoznávam liek na fotke…', none: 'Na fotke sme nenašli názov lieku. Skúste ostrejšiu fotku zblízka, na ktorej je dobre čitateľný názov, alebo názov napíšte.',
      nomatch: 'Na fotke je pravdepodobne: ', nomatch2: '. V zozname hradených liekov sme ho nenašli – voľnopredajné lieky v ňom nie sú.', seen: 'Na fotke: ',
      cheaper: 'lacnejšia alternatíva ', err: 'Fotku sa nepodarilo spracovať. Skúste to znova alebo napíšte názov lieku.', drug: '/liek/', search: 'Hľadať ' },
    hu: { busy: 'Felismerem a gyógyszert a fotón…', none: 'A fotón nem találtunk gyógyszernevet. Próbáljon élesebb közeli fotót, vagy írja be a nevet.',
      nomatch: 'A fotón valószínűleg: ', nomatch2: '. A támogatott gyógyszerek listájában nem találtuk.', seen: 'A fotón: ',
      cheaper: 'olcsóbb alternatíva: ', err: 'A fotót nem sikerült feldolgozni. Próbálja újra, vagy írja be a gyógyszer nevét.', drug: '/hu/gyogyszer/', search: 'Keresés: ' },
    uk: { busy: 'Розпізнаю ліки на фото…', none: 'На фото не знайдено назви ліків. Спробуйте чіткіше фото зблизька або введіть назву.',
      nomatch: 'На фото, ймовірно: ', nomatch2: '. У переліку ліків, які компенсує страхова, його не знайдено.', seen: 'На фото: ',
      cheaper: 'дешевша альтернатива: ', err: 'Не вдалося обробити фото. Спробуйте ще раз або введіть назву ліків.', drug: '/uk/liky/', search: 'Шукати ' }
  }[lang] || null;
  if (!L) return;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function eur(n) { return n == null ? '–' : n.toLocaleString(lang === 'hu' ? 'hu-HU' : lang === 'uk' ? 'uk-UA' : 'sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function say(t, cls) { out.hidden = false; out.replaceChildren(el('p', cls || null, t)); }

  function shrink(file) {
    return new Promise(function (res, rej) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        var max = 1280, w = img.naturalWidth, h = img.naturalHeight, k = Math.min(1, max / Math.max(w, h));
        var c = document.createElement('canvas'); c.width = Math.round(w * k); c.height = Math.round(h * k);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        res(c.toDataURL('image/jpeg', 0.82));
      };
      img.onerror = function () { URL.revokeObjectURL(url); rej(new Error('img')); };
      img.src = url;
    });
  }

  function show(j) {
    out.hidden = false; out.replaceChildren();
    var found = j.found || [], items = j.items || [];
    if (!found.length) return say(L.none, 'form-msg err');
    var desc = found.map(function (f) { return f.nazov + (f.sila ? ' ' + f.sila : '') + (f.kusov ? ' (' + f.kusov + ' ks)' : ''); }).join(', ');
    if (!items.length) {
      out.append(el('p', 'form-msg err', L.nomatch + desc + L.nomatch2));
      var q = document.getElementById('q');
      if (q) { var b = el('button', 'linkish', L.search + '„' + found[0].nazov + '“'); b.type = 'button'; b.onclick = function () { q.value = found[0].nazov; q.dispatchEvent(new Event('input', { bubbles: true })); q.focus(); }; out.append(b); }
      return;
    }
    out.append(el('p', 'eyebrow', L.seen + desc));
    var ul = el('ul', 'foto-list');
    items.forEach(function (it) {
      var li = el('li'), a = el('a'); a.href = L.drug + it.slug + '/';
      a.append(el('strong', null, it.name), el('span', 'mono', eur(it.dop)), el('small', null, it.pack));
      if (it.best) a.append(el('small', 'foto-best', L.cheaper + it.best.name + ' ' + eur(it.best.dop)));
      li.append(a); ul.append(li);
    });
    out.append(ul);
  }

  function run(f) {
    say(L.busy, 'foto-busy');
    out.scrollIntoView({ block: 'center' });
    shrink(f).then(function (img) {
      return fetch('/api/foto', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ img: img }) });
    }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ''); return j; }); })
      .then(show)
      .catch(function (e) { say(e.message && e.message.length > 3 && e.message !== 'img' ? e.message : L.err, 'form-msg err'); })
      .then(function () { inp.value = ''; });
  }
  inp.addEventListener('change', function () { var f = inp.files && inp.files[0]; if (f) run(f); });
  // rýchle akcie aplikácie a zdieľanie fotky z galérie
  var akcia = new URLSearchParams(location.search).get('akcia');
  if (akcia) history.replaceState(null, '', location.pathname);
  if (akcia === 'foto') { var fb = document.querySelector('.foto-btn'); fb.scrollIntoView({ block: 'center' }); fb.classList.add('pulse'); inp.focus(); }
  if (akcia === 'hladat') { var q = document.getElementById('q'); if (q) setTimeout(function () { q.focus(); }, 200); }
  if (akcia === 'zdielane' && 'caches' in window) {
    caches.open('share').then(function (c) { return c.match('/zdielane/foto').then(function (r) { if (!r) return; c.delete('/zdielane/foto'); return r.blob().then(function (b) { run(b); }); }); }).catch(function () {});
  }
})();
