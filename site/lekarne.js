/* Lekárne v okolí: zoznam z OpenStreetMap (/lekarne.json), vzdialenosť podľa polohy alebo hľadania obce.
   Poloha sa nikam neposiela; mapa (dlaždice OpenStreetMap) sa načíta až po kliknutí. */
(function () {
  'use strict';
  var root = document.getElementById('lek-root');
  if (!root) return;
  var listEl = document.getElementById('lek-list'), msg = document.getElementById('lek-msg'), q = document.getElementById('lek-q');
  var mapBtn = document.getElementById('lek-map-btn'), mapEl = document.getElementById('lek-map');
  var all = null, here = null, shown = [], map = null, layer = null;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function norm(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function say(t, err) { msg.textContent = t; msg.className = 'form-msg ' + (err ? 'err' : 'ok'); }
  function load() { if (!all) all = fetch('/lekarne.json').then(function (r) { return r.json(); }).then(function (j) { return j.lekarne; }); return all; }
  function dist(a, b) {
    var R = 6371, dLat = (b[0] - a[0]) * Math.PI / 180, dLon = (b[1] - a[1]) * Math.PI / 180;
    var x = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * Math.PI / 180) * Math.cos(b[0] * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function km(d) { return d < 1 ? Math.round(d * 1000 / 10) * 10 + ' m' : d.toFixed(d < 10 ? 1 : 0).replace('.', ',') + ' km'; }

  /* jednoduché čítanie otváracích hodín z OSM (napr. „Mo-Fr 08:00-17:00; Sa 08:00-12:00“) */
  var DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'], SKD = { Mo: 'Po', Tu: 'Ut', We: 'St', Th: 'Št', Fr: 'Pi', Sa: 'So', Su: 'Ne', PH: 'sviatky' };
  function openNow(oh) {
    if (!oh) return null;
    if (/24\/7/.test(oh)) return true;
    var now = new Date(), d = DAYS[now.getDay()], mins = now.getHours() * 60 + now.getMinutes(), known = false, open = false;
    oh.split(';').forEach(function (rule) {
      var m = /^\s*([A-Za-z,\- ]+?)\s+([\d:,\- ]+|off|closed)\s*$/.exec(rule.trim());
      if (!m) return;
      var daysOk = m[1].split(',').some(function (part) {
        var r = part.trim().split('-');
        if (r.length === 1) return r[0] === d;
        var a = DAYS.indexOf(r[0]), b = DAYS.indexOf(r[1]), x = DAYS.indexOf(d);
        if (a < 0 || b < 0) return false;
        a = (a + 6) % 7; b = (b + 6) % 7; x = (x + 6) % 7;
        return a <= b ? x >= a && x <= b : x >= a || x <= b;
      });
      if (!daysOk) return;
      known = true;
      if (/off|closed/.test(m[2])) { open = false; return; }
      m[2].split(',').forEach(function (span) {
        var t = /(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/.exec(span);
        if (t && mins >= +t[1] * 60 + +t[2] && mins < +t[3] * 60 + +t[4]) open = true;
      });
    });
    return known ? open : null;
  }
  function skHours(oh) { return oh.replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b/g, function (x) { return SKD[x]; }).replace(/\boff\b/g, 'zatvorené'); }

  function render(items, center) {
    shown = items;
    listEl.replaceChildren();
    if (!items.length) { listEl.append(el('li', 'tr-empty', 'Nenašli sme žiadnu lekáreň.')); return; }
    items.forEach(function (x) {
      var li = el('li'), g = el('div', 'gline');
      var name = el('strong', null, x[2]);
      var o = openNow(x[5]);
      if (o !== null) name.append(el('span', 'tag ' + (o ? 'zero' : ''), o ? 'Otvorené' : 'Zatvorené'));
      g.append(name, el('span', 'mono', center ? km(x.d) : ''));
      g.append(el('small', null, [x[3], x[4]].filter(Boolean).join(', ') || 'Adresa neuvedená'));
      if (x[5]) g.append(el('small', 'lek-oh', skHours(x[5])));
      var acts = el('small', 'lek-acts');
      var nav = el('a', null, 'Navigovať'); nav.href = 'https://www.google.com/maps/dir/?api=1&destination=' + x[0] + ',' + x[1]; nav.target = '_blank'; nav.rel = 'noopener';
      acts.append(nav);
      if (x[6]) { var tel = el('a', null, x[6]); tel.href = 'tel:' + x[6].replace(/[^\d+]/g, ''); acts.append(' · ', tel); }
      g.append(acts); li.append(g); listEl.append(li);
    });
    if (map) drawMap();
  }
  function nearest(center) {
    return load().then(function (l) {
      l.forEach(function (x) { x.d = dist(center, x); });
      return l.slice().sort(function (a, b) { return a.d - b.d; }).slice(0, 25);
    });
  }
  document.getElementById('lek-geo').addEventListener('click', function () {
    if (!navigator.geolocation) return say('Tento prehliadač nevie zistiť polohu. Napíšte názov obce.', true);
    say('Zisťujem polohu…');
    navigator.geolocation.getCurrentPosition(function (p) {
      here = [p.coords.latitude, p.coords.longitude];
      nearest(here).then(function (l) { render(l, here); say('Najbližšie lekárne k vašej polohe. Poloha zostáva len vo vašom zariadení.'); });
    }, function () { say('Polohu sa nepodarilo zistiť alebo ste ju nepovolili. Napíšte názov obce alebo ulice.', true); }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
  });
  var tmr = null;
  q.addEventListener('input', function () {
    clearTimeout(tmr);
    tmr = setTimeout(function () {
      var t = norm(q.value.trim()); if (t.length < 2) return;
      load().then(function (l) {
        var hits = l.filter(function (x) { return norm(x[4] + ' ' + x[3] + ' ' + x[2]).indexOf(t) >= 0; });
        if (!hits.length) { render([], null); return say('Nič sme nenašli. Skúste názov obce bez skratiek.', true); }
        // stred nájdených, potom zoradiť podľa vzdialenosti od neho
        var c = [hits.reduce(function (s, x) { return s + x[0]; }, 0) / hits.length, hits.reduce(function (s, x) { return s + x[1]; }, 0) / hits.length];
        hits.forEach(function (x) { x.d = dist(c, x); });
        render(hits.sort(function (a, b) { return a.d - b.d; }).slice(0, 40), null);
        say('Lekárne: ' + hits.length + (hits.length > 40 ? ' (zobrazených 40)' : ''));
      });
    }, 250);
  });
  function drawMap() {
    if (!window.L) return;
    if (!map) {
      map = L.map(mapEl, { scrollWheelZoom: false });
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">prispievatelia OpenStreetMap</a>' }).addTo(map);
      layer = L.layerGroup().addTo(map);
    }
    layer.clearLayers();
    var pts = [];
    shown.forEach(function (x) {
      var mk = L.circleMarker([x[0], x[1]], { radius: 8, color: '#05090b', weight: 2, fillColor: '#45f0c0', fillOpacity: 1 });
      var box = document.createElement('div'); box.append(el('b', null, x[2]), document.createElement('br'), [x[3], x[4]].filter(Boolean).join(', '));
      mk.bindPopup(box); layer.addLayer(mk); pts.push([x[0], x[1]]);
    });
    if (here) { layer.addLayer(L.circleMarker(here, { radius: 9, color: '#fff', weight: 3, fillColor: '#ffb26b', fillOpacity: 1 }).bindPopup('Vy')); pts.push(here); }
    if (pts.length) map.fitBounds(pts, { padding: [24, 24], maxZoom: 15 }); else map.setView([48.7, 19.5], 7);
  }
  mapBtn.addEventListener('click', function () {
    mapEl.hidden = false; mapBtn.hidden = true;
    var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/vendor/leaflet/leaflet.css'; document.head.append(css);
    var s = document.createElement('script'); s.src = '/vendor/leaflet/leaflet.js'; s.onload = drawMap; document.body.append(s);
  });
  load().then(function (l) { say('V zozname je ' + l.length + ' lekární. Nájdite najbližšie podľa polohy alebo obce.'); }).catch(function () { say('Zoznam lekární sa nepodarilo načítať.', true); });
})();
