/* Mapa v okolí: lekárne (/lekarne.json, OSM), výdajne pomôcok, optiky a pobočky poisťovní (/miesta.json),
   ambulancie lekárov a pohotovosti z registrov VÚC (/lekari.json, načíta sa až pri výbere kategórie).
   Mapa na celú plochu, vyhľadávanie s návrhmi obcí, kategórie, zoznam vo vysúvacom paneli, ktorý sleduje výrez mapy.
   Riadok miesta: [lat, lon, názov, adresa, obec, hodiny OSM, telefón, druh, odkaz]. Poloha sa nikam neposiela. */
(function () {
  'use strict';
  var root = document.getElementById('lek-root');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var mapEl = $('lek-map'), listEl = $('lek-list'), msg = $('lek-msg'), q = $('lek-q'), sug = $('lek-sug');
  var sheet = $('lek-sheet'), grip = $('lek-grip'), openBtn = $('lek-open'), insBox = $('lek-ins'), odbSel = $('lek-odb');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var desktop = window.matchMedia ? matchMedia('(min-width: 900px)') : { matches: false };

  var TYP = {
    lekarne: { color: '#087a5f', forms: ['lekáreň', 'lekárne', 'lekární'], none: 'žiadna lekáreň' },
    pohotovost: { color: '#c0262d', forms: ['pohotovosť', 'pohotovosti', 'pohotovostí'], none: 'žiadna pohotovosť', src: 'p' },
    lekari: { color: '#1d5fbf', forms: ['ambulancia', 'ambulancie', 'ambulancií'], none: 'žiadna ambulancia', src: 'l' },
    nemocnice: { color: '#8a2357', forms: ['nemocnica', 'nemocnice', 'nemocníc'], none: 'žiadna nemocnica', src: 'n' },
    pomocky: { color: '#0b6b8a', forms: ['výdajňa pomôcok', 'výdajne pomôcok', 'výdajní pomôcok'], none: 'žiadna výdajňa pomôcok', f: ['zp'] },
    optiky: { color: '#6a4bb3', forms: ['optika', 'optiky', 'optík'], none: 'žiadna optika', f: ['opt', 'sluch'] },
    poistovne: { color: '#b34700', forms: ['pobočka poisťovne', 'pobočky poisťovní', 'pobočiek poisťovní'], none: 'žiadna pobočka poisťovne', f: ['vszp', 'dovera', 'union'] }
  };
  var LABEL = { zp: 'Zdravotnícke potreby', opt: 'Optika', sluch: 'Načúvacie prístroje', vszp: 'VšZP', dovera: 'Dôvera', union: 'Union' };
  var ICON = {
    lekarne: '<path d="M10 4h4v6h6v4h-6v6h-4v-6H4v-4h6z"/>',
    pohotovost: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.6 4.8h3.2v3.6h3.6v3.2h-3.6v3.6h-3.2v-3.6H6.8v-3.2h3.6z"/>',
    nemocnice: '<path d="M4 21V5l8-3 8 3v16h-6v-5h-4v5zm6.5-14v2h-2v2.5h2v2h3v-2h2V9h-2V7z"/>',
    lekari: '<path d="M5 3h3v2H7v5a3 3 0 0 0 6 0V5h-1V3h3v7a5 5 0 0 1-4 4.9V16a3 3 0 0 0 6 0v-2.2a2.5 2.5 0 1 1 2 0V16a5 5 0 0 1-10 0v-1.1A5 5 0 0 1 5 10z"/>',
    pomocky: '<path d="M7 3h4v2H9v5.2l5.7 7.3H17v2h-3.3L9 13.4V21H7z"/><circle cx="16.5" cy="6.5" r="2.5"/>',
    optiky: '<path d="M2 12.5a4.5 4.5 0 0 0 9 0h2a4.5 4.5 0 0 0 9 0V11h-1.2L18.5 6H17l2 5h-5.1a2 2 0 0 0-3.8 0H5l2-5H5.5L3.2 11H2zm4.5 2.5A2.5 2.5 0 0 1 4 12.5h5A2.5 2.5 0 0 1 6.5 15zm11 0a2.5 2.5 0 0 1-2.5-2.5h5a2.5 2.5 0 0 1-2.5 2.5z"/>',
    poistovne: '<path d="M12 2 3 6v2h18V6zM5 10h2v7H5zm4 0h2v7H9zm4 0h2v7h-2zm4 0h2v7h-2zM3 19h18v2H3z"/>'
  };
  function svg(t, size) { return '<svg viewBox="0 0 24 24" width="' + (size || 16) + '" height="' + (size || 16) + '" fill="currentColor" aria-hidden="true">' + ICON[t] + '</svg>'; }

  var typ = (/[?&]typ=(\w+)/.exec(location.search) || [])[1];
  if (!TYP[typ]) typ = 'lekarne';
  var openOnly = false, ins = '', here = null, selected = null, map = null, layer = null, meMarker = null;
  var cache = {}, miesta = null, lek = null, places = null, lekari = null, odb = '', duty = /[?&]sluzba=1/.test(location.search);
  var dutyBtn = $('lek-duty');
  var today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function norm(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function plural(n, f) { return n === 1 ? f[0] : n >= 2 && n <= 4 ? f[1] : f[2]; }
  function say(t) { msg.textContent = t; }
  function getLek() { return lek || (lek = fetch('/lekarne.json').then(function (r) { return r.json(); }).then(function (j) { return j.lekarne; })); }
  function skd(iso) { return +iso.slice(8, 10) + '. ' + +iso.slice(5, 7) + '.'; }
  function splitAddr(a) {
    var m = /^(.*?),?\s*(\d{3}\s?\d{2})\s+(.+)$/.exec(a || '');
    return m ? [m[1], m[3]] : [a || '', ''];
  }
  function evuc(kraj, pid) { return 'https://www.e-vuc.sk/index.php?page_id=' + pid; }
  function apsKind(n) { n = norm(n); return /zubn/.test(n) ? 'Zubná pohotovosť' : /deti/.test(n) ? 'Pre deti a dorast' : 'Pre dospelých'; }
  /* ambulancie: [lat, lon, názov, adresa, odbornosť, neprítomnosť, kraj, page_id]; pohotovosti: [lat, lon, názov, adresa, čas, druh, kraj, page_id] */
  var sluzba = null;
  function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }
  /* /sluzba.json: pohotovosti p, nemocnice n [lat, lon, názov, adresa, druh, oddelenia, kraj, page_id],
     pohotovostné lekárne lm {page_id: [lat, lon, názov, adresa, kraj]} a rozpis lr {dátum: [[page_id, čas]]} */
  function getSluzba() {
    return sluzba || (sluzba = fetch('/sluzba.json').then(function (r) { return r.json(); }).then(function (j) {
      var out = { p: [], n: [], lp: [] };
      j.n.forEach(function (r) {
        var a = splitAddr(r[3]), x = [r[0], r[1], r[2], a[0], a[1], '', '', 'nem', evuc(r[6], r[7])];
        x.kind = cap(r[4]); x.odd = r[5]; out.n.push(x);
      });
      (j.lr[today] || []).forEach(function (e) {
        var m = j.lm[e[0]]; if (!m) return;
        var a = splitAddr(m[3]), x = [m[0], m[1], m[2], a[0], a[1], '', '', 'lp', evuc(m[4], e[0])];
        x.cas = e[1]; out.lp.push(x);
      });
      j.p.forEach(function (r) {
        var a = splitAddr(r[3]), x = [r[0], r[1], r[2], a[0], a[1], '', '', 'aps', evuc(r[6], r[7])];
        x.cas = r[4]; x.kind = apsKind(r[2]); out.p.push(x);
      });
      return out;
    }));
  }
  function getLekari() {
    return lekari || (lekari = fetch('/lekari.json').then(function (r) { return r.json(); }).then(function (j) {
      var out = { o: j.o, l: [] };
      j.l.forEach(function (r) {
        var a = splitAddr(r[3]), x = [r[0], r[1], r[2], a[0], a[1], '', '', 'amb', evuc(r[6], r[7])];
        x.odb = r[4]; x.abs = r[5] || null; out.l.push(x);
      });
      fillOdb(out);
      lekari._d = out;
      return out;
    }));
  }
  function fillOdb(d) {
    if (!odbSel || odbSel.options.length > 1) return;
    var cnt = {};
    d.l.forEach(function (x) { cnt[x.odb] = (cnt[x.odb] || 0) + 1; });
    var idx = Object.keys(cnt).filter(function (k) { return k >= 0 && d.o[k]; });
    var top = idx.slice().sort(function (a, b) { return cnt[b] - cnt[a]; }).slice(0, 8);
    function grp(label, keys) {
      var g = document.createElement('optgroup'); g.label = label;
      keys.forEach(function (k) { var o = document.createElement('option'); o.value = k; o.textContent = d.o[k] + ' (' + cnt[k] + ')'; g.append(o); });
      odbSel.append(g);
    }
    grp('Najčastejšie', top);
    grp('Všetky odbornosti', idx.sort(function (a, b) { return d.o[a].localeCompare(d.o[b], 'sk'); }));
  }
  function load(t) {
    t = t || typ;
    if (t === 'lekarne' && duty) {
      return cache.duty || (cache.duty = getSluzba().then(function (d) { d.lp.forEach(function (x, i) { x.id = 'lp' + i; x.t = 'lekarne'; }); return d.lp; }));
    }
    if (!cache[t]) {
      var T = TYP[t];
      cache[t] = (T.src ? (T.src === 'l' ? getLekari() : getSluzba()).then(function (d) { return d[T.src]; }) : T.f ? (miesta = miesta || fetch('/miesta.json').then(function (r) { return r.json(); })).then(function (j) {
        return j.m.filter(function (x) { return T.f.indexOf(x[7]) >= 0; });
      }) : getLek()).then(function (l) { l.forEach(function (x, i) { x.id = t + i; x.t = t; }); return l; });
    }
    return cache[t];
  }
  function dist(a, b) {
    var R = 6371, dLat = (b[0] - a[0]) * Math.PI / 180, dLon = (b[1] - a[1]) * Math.PI / 180;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a[0] * Math.PI / 180) * Math.cos(b[0] * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function km(d) { return d < 1 ? Math.round(d * 100) * 10 + ' m' : d.toFixed(d < 10 ? 1 : 0).replace('.', ',') + ' km'; }

  /* ---------- otváracie hodiny (OSM: „Mo-Fr 08:00-12:00,13:00-16:00; Sa off“) ---------- */
  var DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'], SKD = { Mo: 'Po', Tu: 'Ut', We: 'St', Th: 'Št', Fr: 'Pi', Sa: 'So', Su: 'Ne', PH: 'sviatky' };
  function spansFor(oh, day) {
    if (!oh) return null;
    if (/24\/7/.test(oh)) return [[0, 1440]];
    var known = false, spans = [];
    oh.split(';').forEach(function (rule) {
      var m = /^\s*([A-Za-z,\- ]+?)\s+([\d:,\- ]+|off|closed)\s*$/.exec(rule.trim());
      if (!m) return;
      var ok = m[1].split(',').some(function (part) {
        var r = part.trim().split('-');
        if (r.length === 1) return r[0] === day;
        var a = (DAYS.indexOf(r[0]) + 6) % 7, b = (DAYS.indexOf(r[1]) + 6) % 7, x = (DAYS.indexOf(day) + 6) % 7;
        if (DAYS.indexOf(r[0]) < 0 || DAYS.indexOf(r[1]) < 0) return false;
        return a <= b ? x >= a && x <= b : x >= a || x <= b;
      });
      if (!ok) return;
      known = true; spans = [];
      if (/off|closed/.test(m[2])) return;
      m[2].split(',').forEach(function (s) {
        var t = /(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/.exec(s);
        if (t) spans.push([+t[1] * 60 + +t[2], +t[3] * 60 + +t[4]]);
      });
    });
    return known ? spans : null;
  }
  function hm(m) { return Math.floor(m / 60) + ':' + ('0' + m % 60).slice(-2); }
  function status(oh) {
    var now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
    var sp = spansFor(oh, DAYS[now.getDay()]);
    if (sp === null) return null;
    for (var i = 0; i < sp.length; i++) {
      if (mins >= sp[i][0] && mins < sp[i][1]) return { open: true, text: sp[i][1] >= 1440 ? 'Otvorené nonstop' : 'Otvorené do ' + hm(sp[i][1]) };
    }
    for (i = 0; i < sp.length; i++) if (sp[i][0] > mins) return { open: false, text: 'Zatvorené · otvára o ' + hm(sp[i][0]) };
    return { open: false, text: 'Dnes už zatvorené' };
  }
  function skHours(oh) { return oh.replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b/g, function (x) { return SKD[x]; }).replace(/\boff\b/g, 'zatvorené').replace(/;\s*/g, '\n'); }

  /* ---------- kategórie a filtre ---------- */
  var cats = root.querySelectorAll('[data-typ]');
  function syncCats() {
    cats.forEach(function (b) {
      var on = b.getAttribute('data-typ') === typ;
      b.setAttribute('aria-checked', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    });
    insBox.hidden = typ !== 'poistovne';
    if (odbSel) odbSel.parentNode.hidden = typ !== 'lekari';
    openBtn.hidden = !!TYP[typ].src;
    if (dutyBtn) { dutyBtn.hidden = typ !== 'lekarne'; dutyBtn.setAttribute('aria-pressed', duty && typ === 'lekarne' ? 'true' : 'false'); }
    root.style.setProperty('--cat', TYP[typ].color);
    var on = root.querySelector('[data-typ="' + typ + '"]'), row = on && on.parentNode;
    if (row && row.scrollWidth > row.clientWidth) row.scrollLeft = Math.max(0, on.offsetLeft - row.offsetLeft - 12);
  }
  cats.forEach(function (b, i) {
    var t = b.getAttribute('data-typ');
    b.addEventListener('click', function () { setTyp(t); });
    b.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      var n = cats[(i + (e.key === 'ArrowRight' ? 1 : cats.length - 1)) % cats.length];
      n.focus(); n.click();
    });
  });
  function setTyp(t) {
    if (t === typ) return;
    typ = t; selected = null; ins = ''; if (TYP[t].src) openOnly = false;
    insBox.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-ins') === '' ? 'true' : 'false'); });
    try { history.replaceState(null, '', typ === 'lekarne' ? location.pathname : '?typ=' + typ); } catch (e) { /* bez histórie */ }
    syncCats(); refresh();
  }
  if (dutyBtn) dutyBtn.addEventListener('click', function () {
    duty = !duty; selected = null; if (duty) { openOnly = false; openBtn.setAttribute('aria-pressed', 'false'); }
    syncCats(); refresh();
  });
  openBtn.addEventListener('click', function () {
    openOnly = !openOnly; openBtn.setAttribute('aria-pressed', openOnly ? 'true' : 'false'); refresh();
  });
  insBox.querySelectorAll('button').forEach(function (b) {
    b.addEventListener('click', function () {
      ins = b.getAttribute('data-ins');
      insBox.querySelectorAll('button').forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
      refresh();
    });
  });
  if (odbSel) odbSel.addEventListener('change', function () { odb = odbSel.value; selected = null; refresh(); });
  function filtered(l) {
    return l.filter(function (x) {
      if (ins && x[7] !== ins) return false;
      if (typ === 'lekari' && odb !== '' && String(x.odb) !== odb) return false;
      if (openOnly) { var s = status(x[5]); if (!s || !s.open) return false; }
      return true;
    });
  }

  /* ---------- mapa ---------- */
  var SK = [[47.73, 16.83], [49.61, 22.57]];
  function leaflet() {
    if (window.L) return Promise.resolve();
    return new Promise(function (res, rej) {
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/vendor/leaflet/leaflet.css'; document.head.append(css);
      var s = document.createElement('script'); s.src = '/vendor/leaflet/leaflet.js'; s.onload = res; s.onerror = rej; document.body.append(s);
    });
  }
  function initMap() {
    map = L.map(mapEl, { zoomControl: false, attributionControl: true, zoomSnap: 0.5, tap: true });
    map.attributionControl.setPrefix(false);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map);
    L.control.zoom({ position: 'bottomright', zoomInTitle: 'Priblížiť', zoomOutTitle: 'Oddialiť' }).addTo(map);
    layer = L.layerGroup().addTo(map);
    map.fitBounds(SK, pad());
    var t = null;
    map.on('moveend', function () { clearTimeout(t); t = setTimeout(refresh, 80); });
    mapEl.classList.add('ready');
  }
  /* časť mapy zakrytá panelom: na počítači vľavo, na mobile hore lišta a dole panel */
  function pad() {
    return desktop.matches ? { paddingTopLeft: [440, 20], paddingBottomRight: [70, 20] } : { paddingTopLeft: [10, 130], paddingBottomRight: [10, 170] };
  }
  function focusOn(ll, z) {
    var dx = desktop.matches ? -220 : 0, dy = desktop.matches ? 0 : (sheetState === 'peek' ? 10 : mapEl.clientHeight * 0.24);
    var p = map.project(ll, z).add([-dx, dy]);
    map.setView(map.unproject(p, z), z, { animate: !reduce });
  }
  function pinIcon(x, sel) {
    var t = x.t, extra = t === 'poistovne' ? '<b>' + (x[7] === 'vszp' ? 'V' : x[7] === 'dovera' ? 'D' : 'U') + '</b>'
      : t === 'pohotovost' ? '<b>' + (x.kind === 'Zubná pohotovosť' ? 'Z' : x.kind === 'Pre deti a dorast' ? 'D' : 'A') + '</b>' : '';
    var s = status(x[5]);
    return L.divIcon({
      className: 'mapa-pin-wrap',
      html: '<span class="mapa-pin' + (sel ? ' sel' : '') + (s && s.open ? ' open' : '') + '" style="--c:' + TYP[t].color + '"><i>' + svg(t, 14) + '</i>' + (extra || '<em></em>') + '</span>',
      iconSize: [44, 26], iconAnchor: [22, 13]
    });
  }
  function draw(items) {
    if (!map) return;
    layer.clearLayers();
    var z = map.getZoom(), b = map.getBounds().pad(0.25), vis = items.filter(function (x) { return b.contains([x[0], x[1]]); });
    {
      // hladné zoskupovanie: stredy skupín sú od seba aspoň R px, takže sa značky (44 × 26 px) neprekrývajú
      var R = z >= 18 ? 0 : 54, hash = {}, groups = [], selX = null;
      vis.forEach(function (x) {
        if (x.id === selected) { selX = x; return; }  // vybrané miesto vždy samostatne
        var p = map.project([x[0], x[1]], z), hit = null;
        var cx = R ? Math.floor(p.x / R) : 0, cy = R ? Math.floor(p.y / R) : 0;
        if (R) {
          for (var i = -1; i <= 1 && !hit; i++) for (var j = -1; j <= 1 && !hit; j++) {
            (hash[(cx + i) + ':' + (cy + j)] || []).some(function (g) {
              if (Math.abs(g.p.x - p.x) < R && Math.abs(g.p.y - p.y) < R * 0.75) { hit = g; return true; }
              return false;
            });
          }
        }
        if (hit) hit.items.push(x);
        else { var g = { p: p, items: [x] }; groups.push(g); if (R) (hash[cx + ':' + cy] = hash[cx + ':' + cy] || []).push(g); }
      });
      var grid = {};
      groups.forEach(function (g, i) { grid[i] = g.items; grid[i].c = map.unproject(g.p, z); });
      Object.keys(grid).forEach(function (k) {
        var g = grid[k];
        if (g.length === 1) {
          var m1 = L.marker([g[0][0], g[0][1]], { icon: pinIcon(g[0], false), title: g[0][2], riseOnHover: true });
          m1.on('click', function () { select(g[0], true); });
          return layer.addLayer(m1);
        }
        var size = g.length < 10 ? 36 : g.length < 100 ? 42 : 48;
        var m = L.marker(g.c, {
          title: g.length + ' ' + plural(g.length, TYP[typ].forms) + ' – priblížiť',
          icon: L.divIcon({ className: 'mapa-pin-wrap', html: '<span class="mapa-cl" style="--c:' + TYP[typ].color + ';--s:' + size + 'px">' + g.length + '</span>', iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
        });
        m.on('click', function () {
          var bb = L.latLngBounds(g.map(function (x) { return [x[0], x[1]]; }));
          map.fitBounds(bb, { padding: [60, 60], maxZoom: 16, animate: !reduce });
        });
        layer.addLayer(m);
      });
      if (selX) {
        var ms = L.marker([selX[0], selX[1]], { icon: pinIcon(selX, true), title: selX[2], zIndexOffset: 1000 });
        ms.on('click', function () { select(selX, true); });
        layer.addLayer(ms);
      }
    }
    if (here) {
      if (!meMarker) meMarker = L.marker(here, { icon: L.divIcon({ className: 'mapa-pin-wrap', html: '<span class="mapa-me"></span>', iconSize: [22, 22], iconAnchor: [11, 11] }), title: 'Vaša poloha', keyboard: false, zIndexOffset: 2000 });
      meMarker.setLatLng(here); layer.addLayer(meMarker);
    }
  }

  /* ---------- zoznam ---------- */
  function refresh() {
    load().then(function (all) {
      var items = filtered(all);
      draw(items);
      var inView = map ? items.filter(function (x) { return map.getBounds().contains([x[0], x[1]]); }) : items;
      var ref = here && map && map.getBounds().contains(here) ? here : map ? [map.getCenter().lat, map.getCenter().lng] : [48.7, 19.5];
      inView.forEach(function (x) { x.d = dist(ref, x); });
      inView.sort(function (a, b) { return a.d - b.d; });
      var n = inView.length, T = TYP[typ];
      if (typ === 'lekarne' && duty) T = { forms: ['lekáreň s pohotovostnou službou dnes', 'lekárne s pohotovostnou službou dnes', 'lekární s pohotovostnou službou dnes'], none: 'žiadna lekáreň s pohotovostnou službou dnes (Košický kraj rozpis nezverejňuje)' };
      var whole = !map || map.getZoom() < 8.5;
      say(n ? (whole ? n + ' ' + plural(n, T.forms) + (openOnly ? ', ktoré sú teraz otvorené' : '') + ' na Slovensku'
        : n + ' ' + plural(n, T.forms) + (openOnly ? ' otvorených' : '') + ' v tejto oblasti')
        : (openOnly ? 'Teraz tu nie je otvorená ' + T.none.replace('žiadna ', '') + '.' : 'V tejto oblasti nie je ' + T.none + '.'));
      renderList(inView.slice(0, 40), whole && !here);
    }).catch(function () { say('Zoznam sa nepodarilo načítať. Skúste obnoviť stránku.'); });
  }
  function renderList(items, noDist) {
    listEl.replaceChildren();
    if (!items.length) {
      var e = el('li', 'mapa-empty');
      e.append(el('p', null, 'Oddiaľte mapu, hľadajte inú obec' + (openOnly ? ' alebo vypnite „Otvorené teraz“.' : '.')));
      listEl.append(e); return;
    }
    items.forEach(function (x) {
      var li = el('li', 'mapa-item' + (selected === x.id ? ' sel' : ''));
      li.id = 'pl-' + x.id; li.style.setProperty('--c', TYP[x.t].color);
      var main = el('button', 'mapa-main'); main.type = 'button';
      var ic = el('span', 'mapa-ic'); ic.innerHTML = svg(x.t, 18);
      var body = el('span', 'mapa-body');
      body.append(el('span', 'mapa-name', x[2]));
      var s = status(x[5]);
      var meta = el('span', 'mapa-meta');
      if (x.t === 'lekari') {
        if (lekariOdb(x)) meta.append(el('span', 'mapa-kind', lekariOdb(x)));
        if (x.abs && x.abs[1] >= today) meta.append(el('span', 'mapa-st off', x.abs[0] <= today ? 'Neprítomnosť do ' + skd(x.abs[1]) : 'Neprítomnosť ' + skd(x.abs[0]) + '–' + skd(x.abs[1])));
      } else if (x[7] === 'lp') {
        meta.append(el('span', 'mapa-kind', 'Pohotovostná služba'));
        meta.append(el('span', 'mapa-st on', 'Dnes ' + (/^0:00 - 24:00/.test(x.cas) ? 'nonstop' : x.cas.replace(/ - /g, '–'))));
      } else if (x.t === 'nemocnice') {
        meta.append(el('span', 'mapa-kind', x.kind));
      } else if (x.t === 'pohotovost') {
        meta.append(el('span', 'mapa-kind', x.kind));
        meta.append(el('span', 'mapa-st na', x.cas ? 'Ordinačný čas ' + x.cas.replace(/ - /g, '–') : 'Čas neuvedený'));
      } else {
        if (LABEL[x[7]] && x.t !== 'lekarne') meta.append(el('span', 'mapa-kind', LABEL[x[7]]));
        meta.append(el('span', 'mapa-st ' + (s ? (s.open ? 'on' : 'off') : 'na'), s ? s.text : 'Hodiny neuvedené'));
      }
      body.append(meta, el('span', 'mapa-addr', [x[3], x[4]].filter(Boolean).join(', ') || 'Adresa neuvedená'));
      main.append(ic, body);
      if (!noDist && x.d != null) main.append(el('span', 'mapa-dist', km(x.d)));
      main.addEventListener('click', function () { select(x, false); });
      li.append(main);
      var acts = el('div', 'mapa-acts');
      var nav = el('a', 'mapa-btn pri', 'Navigovať'); nav.href = 'https://www.google.com/maps/dir/?api=1&destination=' + x[0] + ',' + x[1]; nav.target = '_blank'; nav.rel = 'noopener';
      acts.append(nav);
      if (x[6]) { var tel = el('a', 'mapa-btn', 'Zavolať'); tel.href = 'tel:' + x[6].replace(/[^\d+]/g, ''); acts.append(tel); }
      if (x[8]) { var w = el('a', 'mapa-btn', x.t === 'lekari' || x.t === 'pohotovost' || x.t === 'nemocnice' || x[7] === 'lp' ? 'Detail v registri' : 'Web'); w.href = x[8]; w.target = '_blank'; w.rel = 'noopener'; acts.append(w); }
      if (x.odd) {
        var dd = el('details', 'mapa-hours'); dd.append(el('summary', null, 'Oddelenia'), el('p', null, x.odd)); acts.append(dd);
      }
      if (x[5]) {
        var d = el('details', 'mapa-hours'), su = el('summary', null, 'Otváracie hodiny');
        d.append(su, el('pre', null, skHours(x[5]))); acts.append(d);
      }
      li.append(acts);
      listEl.append(li);
    });
  }
  function lekariOdb(x) { var d = lekari && lekari._d; return d && x.odb >= 0 ? d.o[x.odb] : ''; }
  function select(x, fromMap) {
    selected = x.id;
    if (!desktop.matches && sheetState === 'peek') setSheet('half');
    if (!fromMap && map) {
      focusOn([x[0], x[1]], Math.max(map.getZoom(), 16));
    } else refresh();
    setTimeout(function () {
      var li = $('pl-' + x.id);
      if (li) { li.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' }); var b = li.querySelector('.mapa-main'); if (b && fromMap) b.focus({ preventScroll: true }); }
    }, 250);
  }

  /* ---------- poloha ---------- */
  $('lek-geo').addEventListener('click', function () {
    if (!navigator.geolocation) return say('Tento prehliadač nevie zistiť polohu. Napíšte názov obce.');
    say('Zisťujem vašu polohu…');
    navigator.geolocation.getCurrentPosition(function (p) {
      here = [p.coords.latitude, p.coords.longitude];
      if (!desktop.matches) setSheet('half');
      if (map) focusOn(here, 14); else refresh();
    }, function () { say('Polohu sa nepodarilo zistiť. Napíšte názov obce alebo ulice.'); }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
  });

  /* ---------- vyhľadávanie s návrhmi ---------- */
  function gazetteer() {
    return places || (places = getLek().then(function (l) {
      var m = {};
      l.forEach(function (x) {
        if (!x[4]) return;
        var k = x[4], o = m[k] || (m[k] = { n: k, k: norm(k), la: [], lo: [], c: 0 });
        o.la.push(x[0]); o.lo.push(x[1]); o.c++;
      });
      return Object.keys(m).map(function (k) { return m[k]; }).sort(function (a, b) { return b.c - a.c; });
    }));
  }
  var sugItems = [], active = -1, st = null;
  function closeSug() { sug.hidden = true; q.setAttribute('aria-expanded', 'false'); active = -1; q.removeAttribute('aria-activedescendant'); }
  function pick(i) {
    var s = sugItems[i]; if (!s) return;
    closeSug(); q.value = s.label;
    if (s.city) {
      var c = s.city, bb = L.latLngBounds(c.la.map(function (la, j) { return [la, c.lo[j]]; }));
      here = null;
      if (!desktop.matches) setSheet('half');
      var o = pad(); o.maxZoom = 14; o.animate = !reduce;
      if (!desktop.matches) o.paddingBottomRight = [10, mapEl.clientHeight * 0.5];
      map.fitBounds(bb, o);
    } else if (s.place) select(s.place, false);
  }
  q.addEventListener('input', function () {
    clearTimeout(st);
    st = setTimeout(function () {
      var t = norm(q.value.trim());
      if (t.length < 2) return closeSug();
      Promise.all([gazetteer(), load()]).then(function (r) {
        var cities = r[0].filter(function (c) { return c.k.indexOf(t) === 0; }).concat(r[0].filter(function (c) { return c.k.indexOf(t) > 0; })).slice(0, 5);
        var pl = r[1].filter(function (x) { return norm(x[2] + ' ' + x[3]).indexOf(t) >= 0; }).slice(0, 4);
        sugItems = cities.map(function (c) { return { label: c.n, sub: c.c + ' ' + plural(c.c, TYP.lekarne.forms), city: c }; })
          .concat(pl.map(function (x) { return { label: x[2], sub: [x[3], x[4]].filter(Boolean).join(', '), place: x }; }));
        sug.replaceChildren();
        sugItems.forEach(function (s, i) {
          var li = el('li', s.city ? 'is-city' : 'is-place'); li.id = 'sg-' + i; li.setAttribute('role', 'option');
          li.append(el('span', 'sg-l', s.label), el('span', 'sg-s', s.sub));
          li.addEventListener('mousedown', function (e) { e.preventDefault(); pick(i); });
          sug.append(li);
        });
        if (!sugItems.length) { var no = el('li', 'sg-none', 'Nič sme nenašli. Skúste názov obce.'); sug.append(no); }
        sug.hidden = false; q.setAttribute('aria-expanded', 'true'); active = -1;
      });
    }, 150);
  });
  q.addEventListener('keydown', function (e) {
    if (sug.hidden) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + sugItems.length) % Math.max(sugItems.length, 1);
      sug.querySelectorAll('li').forEach(function (li, i) { li.classList.toggle('act', i === active); });
      q.setAttribute('aria-activedescendant', 'sg-' + active);
    } else if (e.key === 'Enter') { e.preventDefault(); pick(active < 0 ? 0 : active); }
    else if (e.key === 'Escape') closeSug();
  });
  q.addEventListener('blur', function () { setTimeout(closeSug, 150); });
  $('lek-form').addEventListener('submit', function (e) { e.preventDefault(); });

  /* ---------- vysúvací panel (mobil) ---------- */
  var sheetState = 'peek';
  function setSheet(s) {
    sheetState = s; sheet.setAttribute('data-state', s); sheet.style.transform = '';
    grip.setAttribute('aria-expanded', s === 'peek' ? 'false' : 'true');
    grip.setAttribute('aria-label', s === 'full' ? 'Zbaliť zoznam' : 'Rozbaliť zoznam');
  }
  grip.addEventListener('click', function () { if (!moved) setSheet(sheetState === 'peek' ? 'half' : sheetState === 'half' ? 'full' : 'peek'); });
  var startY = 0, startT = 0, moved = false, dragging = false;
  function curT() { var tr = getComputedStyle(sheet).transform; return tr && tr !== 'none' ? new DOMMatrix(tr).m42 : 0; }
  $('lek-sheet-head').addEventListener('pointerdown', function (e) {
    if (desktop.matches || e.target.closest('button:not(#lek-grip), a')) return;
    dragging = true; moved = false; startY = e.clientY; startT = curT();
    sheet.classList.add('drag'); e.currentTarget.setPointerCapture(e.pointerId);
  });
  $('lek-sheet-head').addEventListener('pointermove', function (e) {
    if (!dragging) return;
    var dy = e.clientY - startY; if (Math.abs(dy) > 6) moved = true;
    sheet.style.transform = 'translateY(' + Math.max(0, startT + dy) + 'px)';
  });
  $('lek-sheet-head').addEventListener('pointerup', function (e) {
    if (!dragging) return;
    dragging = false; sheet.classList.remove('drag');
    if (!moved) { sheet.style.transform = ''; return; }
    var y = curT(), h = sheet.offsetHeight, peek = h - 150, half = h * 0.45;
    var best = [['full', 0], ['half', half], ['peek', peek]].sort(function (a, b) { return Math.abs(a[1] - y) - Math.abs(b[1] - y); })[0][0];
    setSheet(best);
    setTimeout(function () { moved = false; }, 50);
  });

  /* na počítači panel začína pod vyhľadávaním a kategóriami (tie sa môžu zalomiť do dvoch riadkov) */
  var topBox = root.querySelector('.mapa-top');
  function placeSheet() { sheet.style.top = desktop.matches ? (topBox.offsetTop + topBox.offsetHeight + 8) + 'px' : ''; }
  window.addEventListener('resize', placeSheet);
  /* ---------- štart ---------- */
  placeSheet();
  syncCats();
  setSheet('peek');
  refresh();
  var start = function () {
    leaflet().then(function () { initMap(); refresh(); })
      .catch(function () { mapEl.classList.add('fail'); say('Mapu sa nepodarilo načítať, zoznam funguje aj bez nej.'); });
  };
  start();
})();
