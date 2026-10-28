/* Moje lieky – doplnky: graf doplatkov v čase, AI kontrola zoznamu, karta liekov pre núdzu a obrázok s úsporou.
   Všetko okrem AI kontroly sa počíta a kreslí len v prehliadači. */
(function () {
  'use strict';
  var box = document.getElementById('mine-extras');
  if (!box || !window.Moje) return;
  var MESIACE = ['jan', 'feb', 'mar', 'apr', 'máj', 'jún', 'júl', 'aug', 'sep', 'okt', 'nov', 'dec'];
  var last = { list: [], shared: false };
  var dataP = null;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function eur(n) { return (n == null ? 0 : n).toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'; }
  function eur0(n) { return Math.round(n).toLocaleString('sk-SK') + ' €'; }
  function dose(v) { var d = parseFloat(String(v == null ? '' : v).replace(',', '.')); return d > 0 && d <= 20 ? d : 1; }
  function data() {
    if (!dataP) dataP = fetch('/data.json').then(function (r) { return r.json(); }).then(function (d) {
      var by = {}; d.groups.forEach(function (g) { g.i.forEach(function (it) { by[it[0]] = { g: g, it: it }; }); }); d.by = by; return d;
    });
    return dataP;
  }
  function profileName() { var P = window.MojeProfily; return P && P.all().list.length > 1 ? P.current().name : ''; }
  function todaySk() { var t = new Date(); return t.getDate() + '. ' + (t.getMonth() + 1) + '. ' + t.getFullYear(); }

  /* ---------- graf doplatkov v čase ---------- */
  var histCache = {};
  function shardOf(kod) { var s = 0; for (var i = 0; i < kod.length; i++) s += kod.charCodeAt(i); return s % 32; }
  function hist(n) { if (!histCache[n]) histCache[n] = fetch('/hist/' + n + '.json').then(function (r) { return r.ok ? r.json() : { m: [], k: {} }; }).catch(function () { return { m: [], k: {} }; }); return histCache[n]; }
  function chart() {
    var card = document.getElementById('mine-chart'); if (!card) return;
    var out = card.querySelector('.mc-body');
    var list = last.list;
    if (!list.length) { card.hidden = true; return; }
    card.hidden = false;
    var shards = {}; list.forEach(function (m) { shards[shardOf(m.kod)] = 1; });
    Promise.all([data()].concat(Object.keys(shards).map(function (n) { return hist(+n).then(function (h) { return [n, h]; }); }))).then(function (res) {
      var d = res[0], H = {}, months = [];
      res.slice(1).forEach(function (x) { H[x[0]] = x[1]; if (x[1].m.length > months.length) months = x[1].m; });
      if (months.length < 2) { out.replaceChildren(el('p', 'hint', 'História doplatkov zatiaľ nie je k dispozícii.')); return; }
      var now = months.map(function () { return 0; }), best = months.map(function () { return 0; }), used = 0;
      list.forEach(function (m) {
        var h = H[shardOf(m.kod)].k[m.kod]; if (!h) return;
        var hit = d.by[m.kod], ks = hit ? hit.it[8] : null, f = ks ? 30.4 * dose(m.d) / ks : 1;
        used++;
        months.forEach(function (_, i) {
          var o = h[0][i], c = h[1][i];
          if (o == null) return;
          now[i] += o * f; best[i] += (c == null ? o : Math.min(c, o)) * f;
        });
      });
      if (!used) { out.replaceChildren(el('p', 'hint', 'Pre vaše lieky nemáme históriu doplatkov.')); return; }
      out.replaceChildren(svgChart(months, now, best));
      var n = Math.min(12, months.length), s1 = 0, s2 = 0;
      for (var i = months.length - n; i < months.length; i++) { s1 += now[i]; s2 += best[i]; }
      var p = el('p', 'mc-sum');
      p.append('Za posledných ' + n + ' mesiacov ste za tieto lieky doplatili približne ', el('b', null, eur0(s1)));
      if (s1 - s2 > 1) p.append('. S najlacnejšími verziami by to bolo ', el('b', 'mc-best', eur0(s2)), ', teda o ', el('b', null, eur0(s1 - s2)), ' menej.');
      else p.append('. Vaše lieky patrili celý čas medzi najlacnejšie.');
      out.append(p, el('p', 'hint', 'Mesačný doplatok podľa dávkovania (pri liekoch bez tabliet 1 balenie mesačne) a doplatkov platných v danom mesiaci. Orientačný výpočet.'));
      yearly(out, months, now, best, H, d, list, n, s1, s2);
    });
  }

  /* ---------- ročný prehľad: rozpis podľa liekov a mesiacov, tlač a obrázok ---------- */
  function yearly(out, months, now, best, H, d, list, n, s1, s2) {
    var from = months.length - n, per = [];
    list.forEach(function (m) {
      var h = H[shardOf(m.kod)].k[m.kod]; if (!h) return;
      var hit = d.by[m.kod], ks = hit ? hit.it[8] : null, f = ks ? 30.4 * dose(m.d) / ks : 1, a = 0, b = 0;
      for (var i = from; i < months.length; i++) { var o = h[0][i], c = h[1][i]; if (o == null) continue; a += o * f; b += (c == null ? o : Math.min(c, o)) * f; }
      per.push({ name: hit ? hit.it[1] : m.kod, kod: m.kod, a: a, b: b });
    });
    per.sort(function (x, y) { return y.a - x.a; });
    var box = el('div', 'yr');
    box.append(el('h3', null, 'Ročný prehľad podľa liekov'));
    var tw = el('div', 'scroll'), t = el('table', 'ltable yr-table'), th = el('tr');
    ['Liek', 'Doplatili ste', 'Najlacnejšie', 'Rozdiel'].forEach(function (x, i) { th.append(el('th', i ? 'num' : null, x)); });
    var thead = el('thead'); thead.append(th); t.append(thead);
    var tb = el('tbody');
    per.forEach(function (r) {
      var tr = el('tr'); tr.append(el('td', null, r.name), el('td', 'num', eur(r.a)), el('td', 'num', eur(r.b)), el('td', 'num' + (r.a - r.b > 0.5 ? ' yr-save' : ''), r.a - r.b > 0.5 ? eur(r.a - r.b) : '–'));
      tb.append(tr);
    });
    var tf = el('tr', 'yr-total'); tf.append(el('td', null, 'Spolu'), el('td', 'num', eur(s1)), el('td', 'num', eur(s2)), el('td', 'num' + (s1 - s2 > 0.5 ? ' yr-save' : ''), s1 - s2 > 0.5 ? eur(s1 - s2) : '–'));
    tb.append(tf); t.append(tb); tw.append(t); box.append(tw);
    var det = el('details', 'yr-months'), sum = el('summary', null, 'Po mesiacoch');
    var t2 = el('table', 'ltable'), h2 = el('tr');
    ['Mesiac', 'Vaše lieky', 'S najlacnejšími'].forEach(function (x, i) { h2.append(el('th', i ? 'num' : null, x)); });
    var th2 = el('thead'); th2.append(h2); t2.append(th2);
    var tb2 = el('tbody');
    for (var i = months.length - 1; i >= from; i--) {
      var tr = el('tr'); tr.append(el('td', null, MESIACE[+months[i].slice(5, 7) - 1] + ' ' + months[i].slice(0, 4)), el('td', 'num', eur(now[i])), el('td', 'num', eur(best[i])));
      tb2.append(tr);
    }
    t2.append(tb2); det.append(sum, t2); box.append(det);
    var tools = el('div', 'mine-tools no-print'), bp = el('button', null, 'Vytlačiť prehľad'), bi = el('button', null, 'Uložiť ako obrázok'), msg = el('p', 'form-msg');
    bp.type = bi.type = 'button';
    bp.addEventListener('click', function () {
      det.open = true; document.body.classList.add('print-yr');
      var done = function () { document.body.classList.remove('print-yr'); window.removeEventListener('afterprint', done); };
      window.addEventListener('afterprint', done); window.print(); setTimeout(done, 3000);
    });
    bi.addEventListener('click', function () { deliver(yearImage(months.slice(from), now.slice(from), best.slice(from), per, s1, s2), 'moje-doplatky-za-rok.png', 'Moje doplatky za lieky', msg); });
    tools.append(bp, bi); box.append(tools, msg);
    out.append(box);
  }
  function yearImage(ms, a, b, per, s1, s2) {
    var W = 1080, H = 1350, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    var x = cv.getContext('2d'), F = getComputedStyle(document.body).fontFamily || 'sans-serif';
    x.fillStyle = '#05090b'; x.fillRect(0, 0, W, H);
    var g = x.createRadialGradient(W, 0, 0, W, 0, 700); g.addColorStop(0, 'rgba(69,240,192,.25)'); g.addColorStop(1, 'rgba(69,240,192,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
    x.fillStyle = '#45f0c0'; x.font = '600 28px ' + F; x.fillText('MOJE DOPLATKY ZA LIEKY', 72, 110);
    x.fillStyle = '#e8f3f0'; x.font = '600 56px ' + F; x.fillText('Za posledných ' + ms.length + ' mesiacov', 72, 185);
    x.font = '700 120px ' + F; x.fillText(eur0(s1), 72, 320);
    x.fillStyle = '#a9bdb8'; x.font = '400 34px ' + F;
    if (s1 - s2 > 1) { x.fillText('S najlacnejšími verziami by to bolo ' + eur0(s2) + '.', 72, 385); x.fillStyle = '#ffb26b'; x.font = '600 40px ' + F; x.fillText('Ušetriť sa dalo ' + eur0(s1 - s2) + '.', 72, 440); }
    else x.fillText('Vaše lieky patrili medzi najlacnejšie.', 72, 385);
    // stĺpce po mesiacoch
    var top = 520, bh = 300, bw = (W - 144) / ms.length, mx = Math.max.apply(null, a.concat([1]));
    for (var i = 0; i < ms.length; i++) {
      var h1 = bh * a[i] / mx, h2 = bh * b[i] / mx, x0 = 72 + i * bw;
      x.fillStyle = '#2a5450'; x.fillRect(x0 + 6, top + bh - h1, bw - 12, h1);
      x.fillStyle = '#45f0c0'; x.fillRect(x0 + 6, top + bh - h2, bw - 12, Math.max(h2, 2));
      x.fillStyle = '#8aa29c'; x.font = '400 22px ' + F; x.textAlign = 'center'; x.fillText(MESIACE[+ms[i].slice(5, 7) - 1], x0 + bw / 2, top + bh + 34); x.textAlign = 'left';
    }
    x.font = '400 24px ' + F; x.fillStyle = '#2a5450'; x.fillRect(72, top + bh + 60, 24, 24); x.fillStyle = '#c9d8d4'; x.fillText('vaše lieky', 106, top + bh + 80);
    x.fillStyle = '#45f0c0'; x.fillRect(300, top + bh + 60, 24, 24); x.fillStyle = '#c9d8d4'; x.fillText('s najlacnejšími verziami', 334, top + bh + 80);
    var y = top + bh + 150;
    per.slice(0, 4).forEach(function (r) {
      x.fillStyle = '#e8f3f0'; x.font = '400 30px ' + F; var nm = r.name.length > 34 ? r.name.slice(0, 33) + '…' : r.name; x.fillText(nm, 72, y);
      x.textAlign = 'right'; x.font = '600 30px ' + F; x.fillText(eur0(r.a), W - 72, y); x.textAlign = 'left'; y += 52;
    });
    x.fillStyle = '#e8f3f0'; x.font = '600 34px ' + F; x.fillText('doplatkyliekov.sk', 72, H - 110);
    x.fillStyle = '#8aa29c'; x.font = '400 22px ' + F; x.fillText('Orientačný výpočet podľa dávkovania a doplatkov MZ SR v danom mesiaci.', 72, H - 66);
    return cv;
  }
  function svgChart(months, a, b) {
    var W = 640, Hh = 260, L = 56, R = 14, T = 14, B = 34, n = months.length;
    var mx = Math.max.apply(null, a.concat(b)) || 1;
    var raw = mx * 1.1 / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var tick = [1, 2, 2.5, 5, 10].map(function (k) { return k * mag; }).filter(function (k) { return k >= raw; })[0], top = tick * 4;
    function x(i) { return L + (W - L - R) * i / (n - 1); }
    function y(v) { return T + (Hh - T - B) * (1 - v / top); }
    var NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + Hh); svg.setAttribute('class', 'mc-svg'); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Mesačný doplatok za vaše lieky: teraz ' + eur(a[n - 1]) + ', s najlacnejšími verziami ' + eur(b[n - 1]));
    function add(tag, attrs, text) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; svg.appendChild(e); return e; }
    for (var k = 0; k <= 4; k++) {
      var v = top * k / 4, yy = y(v);
      add('line', { x1: L, x2: W - R, y1: yy, y2: yy, class: 'g' });
      add('text', { x: L - 8, y: yy + 4, 'text-anchor': 'end' }, (v % 1 ? v.toFixed(1).replace('.', ',') : v) + ' €');
    }
    months.forEach(function (m, i) {
      var mo = +m.slice(5, 7);
      if (i === 0 || i === n - 1 || (mo === 1 && i > 2 && i < n - 3)) add('text', { x: x(i), y: Hh - 8, 'text-anchor': i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle' }, MESIACE[mo - 1] + ' ' + m.slice(0, 4));
    });
    function path(arr) { return arr.map(function (v, i) { return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); }).join(' '); }
    add('path', { d: path(b), class: 'lb' });
    add('path', { d: path(a), class: 'la' });
    add('circle', { cx: x(n - 1), cy: y(a[n - 1]), r: 5, class: 'da' });
    add('circle', { cx: x(n - 1), cy: y(b[n - 1]), r: 5, class: 'db' });
    var wrap = el('div', 'mc-wrap'); wrap.append(svg);
    var leg = el('p', 'mc-legend');
    leg.append(el('span', 'la', 'Vaše lieky'), el('span', 'lb', 'S najlacnejšími verziami'));
    wrap.append(leg);
    return wrap;
  }

  /* ---------- AI kontrola zoznamu ---------- */
  function mdInline(text, parent) {
    var re = /\[([^\]]{1,200})\]\((\/[a-z0-9\-/]*)\)|\*\*([^*]{1,300})\*\*/gi, lastI = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > lastI) parent.append(text.slice(lastI, m.index));
      if (m[1]) { var a = el('a', null, m[1]); a.href = m[2]; parent.append(a); } else parent.append(el('strong', null, m[3]));
      lastI = re.lastIndex;
    }
    if (lastI < text.length) parent.append(text.slice(lastI));
  }
  function md(text) {
    var root = el('div', 'ai-md'), ul = null;
    text.replace(/\r/g, '').split('\n').forEach(function (line) {
      var t = line.trim(), li = /^([-*•]|\d+[.)])\s+(.*)$/.exec(t);
      if (li) { if (!ul) { ul = el('ul'); root.append(ul); } var item = el('li'); mdInline(li[2], item); ul.append(item); return; }
      ul = null; if (!t) return;
      var h = /^#{1,4}\s+(.*)$/.exec(t); var p = el(h ? 'h3' : 'p'); mdInline(h ? h[1] : t, p); root.append(p);
    });
    return root;
  }
  function bindCheck() {
    var btn = document.getElementById('mine-check'), out = document.getElementById('mine-check-out'), pr = document.getElementById('mine-check-print');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var list = last.list; if (!list.length) return;
      btn.disabled = true; pr.hidden = true;
      out.hidden = false; out.replaceChildren(el('p', 'foto-busy', 'Kontrolujem vaše lieky…'));
      fetch('/api/kontrola', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items: list.map(function (m) { return { kod: m.kod, d: dose(m.d) }; }) }) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ''); return j; }); })
        .then(function (j) {
          out.replaceChildren();
          var head = el('div', 'print-only print-head');
          head.append(el('b', null, 'Prehľad liekov' + (profileName() ? ' – ' + profileName() : '')), el('span', null, todaySk() + ' · doplatkyliekov.sk'));
          out.append(head, md(j.answer), el('p', 'hint', 'Prehľad pripravila umelá inteligencia z údajov zoznamu MZ SR. Nenahrádza lekára ani lekárnika; o zmene lieku sa vždy poraďte s nimi.'));
          pr.hidden = false;
        })
        .catch(function (e) { out.replaceChildren(el('p', 'form-msg err', e.message && e.message.length > 3 ? e.message : 'Kontrola sa nepodarila. Skúste to znova.')); })
        .then(function () { btn.disabled = false; });
    });
    pr.addEventListener('click', function () { document.body.classList.add('print-check'); window.print(); setTimeout(function () { document.body.classList.remove('print-check'); }, 500); });
  }

  /* ---------- kreslenie obrázkov ---------- */
  function fontsReady() {
    var f = document.fonts; if (!f || !f.load) return Promise.resolve();
    return Promise.all(['700 40px Unbounded', '600 40px Onest', '400 40px Onest'].map(function (x) { return f.load(x).catch(function () {}); }));
  }
  function wrapText(ctx, text, maxW) {
    var words = String(text).split(/\s+/), lines = [], cur = '';
    words.forEach(function (w) { var t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; });
    if (cur) lines.push(cur);
    return lines;
  }
  function deliver(canvas, name, title, msgEl) {
    canvas.toBlob(function (blob) {
      var file = new File([blob], name, { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: title }).catch(function () {});
      } else {
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        if (msgEl) { msgEl.textContent = 'Obrázok sa stiahol. Nájdete ho v stiahnutých súboroch alebo v galérii.'; msgEl.className = 'form-msg ok'; }
      }
    }, 'image/png');
  }

  /* ---------- karta liekov pre núdzu (obrázok na uzamknutú obrazovku) ---------- */
  function cardKey() { var P = window.MojeProfily; return 'mojeLieky.karta.' + (P ? P.current().id : 'p0'); }
  function cardRead() { try { return JSON.parse(localStorage.getItem(cardKey()) || '{}') || {}; } catch (e) { return {}; } }
  function cardSave(v) { try { localStorage.setItem(cardKey(), JSON.stringify(v)); } catch (e) { /* nič */ } }
  function bindCard() {
    var form = document.getElementById('sos-form'); if (!form) return;
    var msg = document.getElementById('sos-msg'), prev = document.getElementById('sos-preview');
    function fill() { var v = cardRead(); ['meno', 'nar', 'krv', 'alergie', 'diag', 'kontakt'].forEach(function (k) { form.elements[k].value = v[k] || ''; }); }
    document.addEventListener('moje:rendered', fill); fill();
    form.addEventListener('input', function () {
      var v = {}; ['meno', 'nar', 'krv', 'alergie', 'diag', 'kontakt'].forEach(function (k) { v[k] = form.elements[k].value.slice(0, 200); }); cardSave(v);
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var list = last.list; if (!list.length) { msg.textContent = 'Najprv si uložte lieky.'; msg.className = 'form-msg err'; return; }
      fontsReady().then(function () { return data(); }).then(function (d) {
        var c = drawCard(list, cardRead(), d);
        prev.replaceChildren(); var img = new Image(); img.src = c.toDataURL('image/png'); img.alt = 'Náhľad karty liekov'; prev.append(img); prev.hidden = false;
        deliver(c, 'karta-liekov.png', 'Karta liekov', msg);
      });
    });
  }
  function drawCard(list, v, d) {
    var W = 1080, H = 2340, c = document.createElement('canvas'); c.width = W; c.height = H;
    var x = c.getContext('2d');
    x.fillStyle = '#0b1114'; x.fillRect(0, 0, W, H);
    var y = 760, P = 80, maxW = W - 2 * P; // horná časť obrazovky zakrýva hodiny
    x.fillStyle = '#e5484d'; roundRect(x, P, y, maxW, 120, 28); x.fill();
    drawCross(x, P + 60, y + 60);
    x.font = '700 40px Unbounded, sans-serif'; x.textBaseline = 'middle'; x.fillText('ZDRAVOTNÉ ÚDAJE', P + 120, y + 48);
    x.font = '500 30px Onest, sans-serif'; x.fillText('pre záchranárov a lekárov', P + 120, y + 88);
    y += 180;
    x.textBaseline = 'alphabetic';
    function row(label, val, color) {
      if (!val) return;
      x.fillStyle = '#9fb3b0'; x.font = '600 28px Onest, sans-serif'; x.fillText(label.toUpperCase(), P, y); y += 50;
      x.fillStyle = color || '#f1f7f6'; x.font = '600 44px Onest, sans-serif';
      wrapText(x, val, maxW).slice(0, 3).forEach(function (l) { x.fillText(l, P, y); y += 56; });
      y += 22;
    }
    row('Meno', [v.meno, v.nar ? '(nar. ' + v.nar + ')' : ''].filter(Boolean).join(' ') || profileName());
    row('Alergie', v.alergie, '#ffb26b');
    row('Krvná skupina', v.krv);
    row('Ochorenia', v.diag);
    x.fillStyle = '#9fb3b0'; x.font = '600 28px Onest, sans-serif'; x.fillText('UŽÍVANÉ LIEKY', P, y); y += 54;
    list.slice(0, 12).forEach(function (m) {
      var hit = d.by[m.kod], name = m.name || (hit ? hit.it[1] : m.kod);
      x.fillStyle = '#f1f7f6'; x.font = '600 40px Onest, sans-serif';
      wrapText(x, name, maxW).slice(0, 2).forEach(function (l) { x.fillText(l, P, y); y += 48; });
      var times = Array.isArray(m.t) && m.t.length ? ' · ' + m.t.join(', ') : '';
      x.fillStyle = '#45f0c0'; x.font = '400 32px Onest, sans-serif';
      x.fillText(String(dose(m.d)).replace('.', ',') + ' ks denne' + times, P, y); y += 58;
    });
    if (list.length > 12) { x.fillStyle = '#9fb3b0'; x.font = '400 30px Onest, sans-serif'; x.fillText('+ ďalšie lieky: ' + (list.length - 12), P, y); y += 50; }
    y += 10;
    row('Kontakt v núdzi', v.kontakt);
    x.fillStyle = '#6f8582'; x.font = '400 26px Onest, sans-serif';
    x.fillText('Aktualizované ' + todaySk() + ' · doplatkyliekov.sk', P, Math.min(H - 70, Math.max(y + 20, H - 120)));
    return c;
  }
  function drawCross(x, cx, cy) { x.fillStyle = '#e5484d'; x.fillRect(cx - 40, cy - 40, 80, 80); x.fillStyle = '#fff'; x.fillRect(cx - 9, cy - 28, 18, 56); x.fillRect(cx - 28, cy - 9, 56, 18); }
  function roundRect(x, a, b, w, h, r) { x.beginPath(); x.moveTo(a + r, b); x.arcTo(a + w, b, a + w, b + h, r); x.arcTo(a + w, b + h, a, b + h, r); x.arcTo(a, b + h, a, b, r); x.arcTo(a, b, a + w, b, r); x.closePath(); }

  /* ---------- obrázok s úsporou na zdieľanie (bez názvov liekov) ---------- */
  function bindShare() {
    var btn = document.getElementById('mine-brag'), msg = document.getElementById('mine-tools-msg');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var st = window.MojeStats || {};
      fontsReady().then(function () { deliver(drawBrag(st), 'moja-uspora-na-liekoch.png', 'Ušetrite na liekoch – doplatkyliekov.sk', msg); });
    });
  }
  function drawBrag(st) {
    var S = 1080, c = document.createElement('canvas'); c.width = S; c.height = S;
    var x = c.getContext('2d');
    var g = x.createLinearGradient(0, 0, S, S); g.addColorStop(0, '#05090b'); g.addColorStop(1, '#0c2a24'); x.fillStyle = g; x.fillRect(0, 0, S, S);
    x.strokeStyle = 'rgba(69,240,192,.18)'; x.lineWidth = 2;
    for (var i = 0; i < S; i += 54) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i, S); x.stroke(); }
    var P = 90;
    x.fillStyle = '#45f0c0'; roundRect(x, P, 100, 120, 64, 32); x.fill(); x.fillStyle = '#05090b'; roundRect(x, P + 60, 106, 54, 52, 26); x.fill();
    x.fillStyle = '#f1f7f6'; x.font = '600 40px Onest, sans-serif'; x.fillText('doplatkyliekov.sk', P + 150, 146);
    var year = st.yearSave || 0, pack = st.packSave || 0, big, top, sub;
    if (year >= 1) { top = 'Na liekoch môžem ušetriť'; big = eur0(year); sub = 'ročne'; }
    else if (pack >= 0.5) { top = 'Na liekoch môžem ušetriť'; big = eur(pack); sub = 'na jednom nákupe'; }
    else { top = 'Moje lieky už mám'; big = 'najlacnejšie'; sub = 'a vy?'; }
    x.font = '600 58px Onest, sans-serif'; x.fillStyle = '#c9d6d4'; x.fillText(top, P, 400);
    x.font = '700 ' + (big.length > 8 ? 130 : 190) + 'px Unbounded, sans-serif'; x.fillStyle = '#ffb26b'; x.fillText(big, P, 600);
    x.font = '600 64px Onest, sans-serif'; x.fillStyle = '#ffb26b'; x.fillText(sub, P, 690);
    x.font = '400 42px Onest, sans-serif'; x.fillStyle = '#c9d6d4';
    wrapText(x, 'Rovnaká účinná látka, nižší doplatok. Porovnajte si svoje lieky zadarmo.', S - 2 * P).forEach(function (l, i) { x.fillText(l, P, 820 + i * 56); });
    x.font = '700 44px Unbounded, sans-serif'; x.fillStyle = '#45f0c0'; x.fillText('doplatkyliekov.sk', P, 990);
    return c;
  }

  // moje.js mohol zoznam vykresliť skôr, ako sa tento súbor načítal (pomalé pripojenie) – posledný stav je vo window.MojeLast
  function onRendered(e) {
    last = e.detail || last;
    box.hidden = last.shared || !last.list.length;
    var brag = document.getElementById('mine-brag'); if (brag) brag.hidden = last.shared || !last.list.length;
    var wal = document.getElementById('mine-wallet'); if (wal) wal.hidden = !last.list.length;
    if (!box.hidden) chart();
    var out = document.getElementById('mine-check-out'); if (out && e.detail) { out.hidden = true; document.getElementById('mine-check-print').hidden = true; }
  }
  document.addEventListener('moje:rendered', onRendered);
  if (window.MojeLast) onRendered({ detail: window.MojeLast });
  /* ---------- kartička do peňaženky (85,6 × 54 mm, predná a zadná strana) ---------- */
  function bindWallet() {
    var btn = document.getElementById('mine-wallet'), box = document.getElementById('wallet-print');
    if (!btn || !box) return;
    btn.addEventListener('click', function () {
      var list = last.list; if (!list.length) return;
      btn.disabled = true;
      data().then(function (d) {
        box.replaceChildren();
        var rows = list.map(function (m) {
          var hit = d.by[m.kod]; if (!hit) return null;
          var it = hit.it, best = hit.g.i.filter(function (x) { return x[5] != null; }).sort(function (a, b) { return a[5] - b[5]; })[0];
          return { name: it[1], dop: it[5], alt: best && best[0] !== it[0] && it[5] - best[5] >= 0.5 ? { name: best[1], dop: best[5] } : null, kod: it[0] };
        }).filter(Boolean);
        var per = 5;
        for (var i = 0; i < rows.length; i += per) {
          var front = el('div', 'wl-card wl-front');
          var h = el('div', 'wl-h'); h.append(el('b', null, 'Moje lieky' + (profileName() ? ' · ' + profileName() : '')), el('span', null, todaySk()));
          front.append(h);
          rows.slice(i, i + per).forEach(function (r) {
            var li = el('div', 'wl-row'), top = el('div', 'wl-top');
            top.append(el('span', 'wl-n', r.name), el('span', 'wl-p', eur(r.dop)));
            li.append(top);
            if (r.alt) li.append(el('div', 'wl-alt', 'lacnejšie: ' + r.alt.name + ' ' + eur(r.alt.dop)));
            front.append(li);
          });
          box.append(front);
        }
        var back = el('div', 'wl-card wl-back'), url = location.origin + '/moje-lieky/?l=' + list.map(function (m) { return m.kod + (m.d && dose(m.d) !== 1 ? '*' + dose(m.d) : ''); }).join(',');
        var q = el('div', 'wl-qr');
        if (window.qrcode) { var qr = window.qrcode(0, 'M'); qr.addData(url); qr.make(); q.innerHTML = qr.createSvgTag({ cellSize: 2, margin: 0, scalable: true }); }
        var t = el('div', 'wl-t');
        t.append(el('b', null, 'Pre lekárnika'), el('p', null, 'Ak je to možné, vydajte mi prosím liek s rovnakou látkou a nižším doplatkom.'),
          el('p', 'wl-small', 'Kódy ŠÚKL: ' + rows.map(function (r) { return r.kod; }).join(', ')), el('p', 'wl-brand', 'doplatkyliekov.sk'));
        back.append(q, t); box.append(back);
        box.append(el('p', 'wl-note', 'Vystrihnite po prerušovanej čiare, prednú a zadnú stranu prelepte alebo zalaminujte. Doplatky podľa zoznamu MZ SR k ' + todaySk() + '.'));
        document.body.classList.add('print-wallet');
        var done = function () { document.body.classList.remove('print-wallet'); window.removeEventListener('afterprint', done); btn.disabled = false; };
        window.addEventListener('afterprint', done); setTimeout(function () { window.print(); }, 50); setTimeout(done, 4000);
      });
    });
  }
  bindCheck(); bindCard(); bindShare(); bindWallet();
})();
