/* Kto je môj lekár: obvodný lekár podľa obce a ulice (/api/obvod, registre krajov e-VÚC). */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var form = $('ob-form'), q = $('ob-q'), sug = $('ob-sug'), out = $('ob-out'), msg = $('ob-msg'), ul = $('ob-ul'), ulBox = $('ob-ul-box');
  if (!form) return;
  var obec = null, data = null, timer = null, items = [], act = -1, seq = 0;
  function el(t, c, x) { var e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; }
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function odb() { var r = form.querySelector('input[name="o"]:checked'); return r ? r.value : '1'; }
  function cas(s) {
    return s.replace(/(\d{1,2}:\d{2}) - (\d{1,2}:\d{2})(?: - (\d{1,2}:\d{2}) - (\d{1,2}:\d{2}))?/g, function (m, a, b, c, d) {
      return a + '–' + b + (c ? ', ' + c + '–' + d : '');
    });
  }
  function close() { sug.hidden = true; q.setAttribute('aria-expanded', 'false'); act = -1; q.removeAttribute('aria-activedescendant'); }
  function pick(i) {
    var o = items[i]; if (!o) return;
    close(); obec = o; q.value = o.n; load();
  }
  q.addEventListener('input', function () {
    clearTimeout(timer); obec = null;
    var t = q.value.trim();
    if (t.length < 2) return close();
    timer = setTimeout(function () {
      var my = ++seq;
      fetch('/api/obvod?q=' + encodeURIComponent(t)).then(function (r) { return r.json(); }).then(function (j) {
        if (my !== seq) return;
        items = j.obce || [];
        sug.replaceChildren();
        items.forEach(function (o, i) {
          var li = el('li', null, o.label); li.id = 'ob-s' + i; li.setAttribute('role', 'option');
          li.addEventListener('mousedown', function (e) { e.preventDefault(); pick(i); });
          sug.append(li);
        });
        if (!items.length) sug.append(el('li', 'none', 'Obec sme nenašli. Košický kraj register nezverejňuje.'));
        sug.hidden = false; q.setAttribute('aria-expanded', 'true');
      }).catch(function () { msg.textContent = 'Návrhy obcí sa nepodarilo načítať.'; });
    }, 300);
  });
  q.addEventListener('keydown', function (e) {
    if (sug.hidden) { if (e.key === 'Enter') e.preventDefault(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      act = (act + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % Math.max(items.length, 1);
      sug.querySelectorAll('li').forEach(function (li, i) { li.classList.toggle('act', i === act); });
      q.setAttribute('aria-activedescendant', 'ob-s' + act);
    } else if (e.key === 'Enter') { e.preventDefault(); pick(act < 0 ? 0 : act); }
    else if (e.key === 'Escape') close();
  });
  q.addEventListener('blur', function () { setTimeout(close, 150); });
  form.addEventListener('submit', function (e) { e.preventDefault(); });
  form.querySelectorAll('input[name="o"]').forEach(function (r) { r.addEventListener('change', function () { if (obec) load(); }); });
  ul.addEventListener('input', render);

  function load() {
    data = null; out.replaceChildren(); ulBox.hidden = true;
    msg.textContent = 'Hľadám v registri kraja…';
    var my = ++seq;
    fetch('/api/obvod?k=' + obec.k + '&id=' + obec.id + '&n=' + encodeURIComponent(obec.n) + '&o=' + odb())
      .then(function (r) { return r.json(); }).then(function (j) {
        if (my !== seq) return;
        if (j.error) { msg.textContent = j.error; return; }
        data = j; ul.value = '';
        ulBox.hidden = j.ulice.length < 8;
        render();
      }).catch(function () { msg.textContent = 'Register kraja sa nepodarilo načítať. Skúste to o chvíľu.'; });
  }
  function render() {
    if (!data) return;
    out.replaceChildren();
    var t = norm(ul.value.trim()), groups = new Map();
    data.ulice.forEach(function (u) {
      if (t && norm(u[0]).indexOf(t) < 0) return;
      var g = groups.get(u[1]) || []; g.push(u[0]); groups.set(u[1], g);
    });
    if (!data.ulice.length) data.amb.forEach(function (a, i) { groups.set(i, []); });
    var n = groups.size;
    msg.textContent = n ? (n === 1 ? '1 ambulancia' : n + (n < 5 ? ' ambulancie' : ' ambulancií')) + ' v obci ' + obec.n + (t ? ', ulica „' + ul.value.trim() + '“' : '') + '.'
      : 'Pre túto ulicu sme nenašli pridelenú ambulanciu. Skúste kratší názov ulice.';
    groups.forEach(function (streets, i) {
      var a = data.amb[i], li = el('li', 'ob-item');
      li.append(el('strong', null, a[0]));
      var meta = el('p', 'ob-meta');
      meta.append(el('span', null, a[2]));
      if (a[3]) meta.append(el('span', 'ob-cas', 'Dnes: ' + cas(a[3])));
      li.append(meta);
      var free = streets.filter(function (s) { return /slobodnej vo/.test(s); }).length;
      var real = streets.filter(function (s) { return !/slobodnej vo/.test(s); });
      if (real.length) {
        var d = el('details', 'ob-ul'), s = el('summary', null, real.length === 1 ? 'Ulica: ' + real[0] : real.length + ' ulíc v obvode');
        d.append(s);
        if (real.length > 1) d.append(el('p', null, real.join(', ')));
        if (t) d.open = true;
        li.append(d);
      } else if (free) li.append(el('p', 'ob-meta', 'Bez pridelených ulíc: prijíma pacientov v rámci slobodnej voľby lekára.'));
      var acts = el('p', 'ob-acts');
      var nav = el('a', null, 'Navigovať'); nav.href = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(a[2]); nav.target = '_blank'; nav.rel = 'noopener';
      var det = el('a', null, 'Detail v registri kraja'); det.href = 'https://www.e-vuc.sk/index.php?page_id=' + a[4]; det.target = '_blank'; det.rel = 'noopener';
      acts.append(nav, det); li.append(acts);
      out.append(li);
    });
  }
})();
