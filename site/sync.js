/* Prepojenie zariadení (Moje lieky): údaje sa šifrujú v prehliadači (AES-GCM) a na server ide len zašifrovaný obsah.
   Kľúč je v QR kóde / odkaze za znakom #, server ho nikdy nedostane. Zlučuje sa po kľúčoch: novšia zmena vyhráva. */
(function () {
  'use strict';
  var card = document.getElementById('sync-card');
  if (!card || !window.crypto || !crypto.subtle) return;
  var CFG = 'sync.v1';
  var PREFIX = ['mojeLieky', 'limitTracker.v1', 'limitSettings.v1'];
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function cfg() { try { return JSON.parse(localStorage.getItem(CFG) || 'null'); } catch (e) { return null; } }
  function saveCfg(c) { try { if (c) localStorage.setItem(CFG, JSON.stringify(c)); else localStorage.removeItem(CFG); } catch (e) { /* nič */ } }
  function b64u(buf) { var s = '', a = new Uint8Array(buf); for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i]); return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); }
  function unb64u(s) { s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; var b = atob(s), a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; }
  function hex(a) { return Array.prototype.map.call(a, function (x) { return ('0' + x.toString(16)).slice(-2); }).join(''); }
  function keys() { var out = []; for (var i = 0; i < localStorage.length; i++) { var k = localStorage.key(i); if (PREFIX.some(function (p) { return k.indexOf(p) === 0; })) out.push(k); } return out; }
  function h(s) { var x = 0; for (var i = 0; i < s.length; i++) x = (x * 31 + s.charCodeAt(i)) | 0; return x; }
  function importKey(raw) { return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']); }
  function enc(key, obj) {
    var iv = crypto.getRandomValues(new Uint8Array(12));
    return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, new TextEncoder().encode(JSON.stringify(obj))).then(function (ct) {
      var all = new Uint8Array(12 + ct.byteLength); all.set(iv); all.set(new Uint8Array(ct), 12); return b64u(all);
    });
  }
  function dec(key, data) { var a = unb64u(data); return crypto.subtle.decrypt({ name: 'AES-GCM', iv: a.slice(0, 12) }, key, a.slice(12)).then(function (pt) { return JSON.parse(new TextDecoder().decode(pt)); }); }

  /* lokálne zmeny: porovnáme odtlačky hodnôt s poslednou synchronizáciou a zmeneným dáme aktuálny čas */
  function localDoc(c) {
    var now = Date.now(), doc = {}, mt = c.mt || {}, hs = c.hs || {};
    keys().forEach(function (k) { var v = localStorage.getItem(k), hv = h(v); if (hs[k] !== hv) { mt[k] = now; hs[k] = hv; } doc[k] = { v: v, t: mt[k] || now }; });
    Object.keys(hs).forEach(function (k) { if (localStorage.getItem(k) == null) { mt[k] = mt[k] && hs[k] === null ? mt[k] : now; hs[k] = null; doc[k] = { v: null, t: mt[k] }; } });
    c.mt = mt; c.hs = hs; return doc;
  }
  function merge(c, local, remote) {
    var out = {}, changed = false;
    Object.keys(local).concat(Object.keys(remote || {})).forEach(function (k) {
      if (out[k]) return;
      var a = local[k], b = remote && remote[k];
      var win = !a ? b : !b ? a : (b.t > a.t ? b : a);
      out[k] = win;
      if (b && win === b && (!a || a.v !== b.v)) {
        try { if (b.v == null) localStorage.removeItem(k); else localStorage.setItem(k, b.v); } catch (e) { /* nič */ }
        c.mt[k] = b.t; c.hs[k] = b.v == null ? null : h(b.v); changed = true;
      }
    });
    return { doc: out, changed: changed };
  }
  var busy = false;
  function sync(c, quiet) {
    if (busy || !c) return Promise.resolve();
    busy = true;
    var keyP = importKey(unb64u(c.k));
    return keyP.then(function (key) {
      return fetch('/api/sync?id=' + c.id, { cache: 'no-store' }).then(function (r) { return r.status === 404 ? null : r.json(); }).then(function (rec) {
        return (rec && rec.data ? dec(key, rec.data) : Promise.resolve(null)).then(function (remote) {
          var m = merge(c, localDoc(c), remote ? remote.d : null);
          var put = function (v) {
            return enc(key, { d: m.doc }).then(function (data) {
              return fetch('/api/sync', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: c.id, data: data, v: v }) });
            }).then(function (r) { if (r.status === 409) throw new Error('retry'); return r.json(); }).then(function (j) { c.v = j.v; c.at = Date.now(); saveCfg(c); });
          };
          var canon = function (d) { return JSON.stringify(Object.keys(d || {}).sort().map(function (k) { return [k, d[k].v, d[k].t]; })); };
          if (remote && canon(m.doc) === canon(remote.d)) { c.v = rec.v; c.at = Date.now(); saveCfg(c); if (m.changed && window.renderMoje) window.renderMoje(); return; }
          return put(rec ? rec.v : 0).then(function () {
            if (m.changed) { document.dispatchEvent(new Event('moje:refresh')); if (window.renderMoje) window.renderMoje(); }
          });
        });
      });
    }).catch(function (e) { if (!quiet) status('Synchronizácia sa nepodarila. Skúste to neskôr.', true); })
      .then(function () { busy = false; paint(); });
  }

  /* rozhranie */
  var body = card.querySelector('.sync-body');
  function status(t, err) { var p = card.querySelector('.form-msg'); p.textContent = t; p.className = 'form-msg ' + (err ? 'err' : 'ok'); }
  function link(c) { return location.origin + '/moje-lieky/#sync=' + c.id + '.' + c.k; }
  function paint() {
    var c = cfg(); body.replaceChildren();
    if (!c) {
      body.append(el('p', 'page-sub', 'Prepojte Moje lieky, členov rodiny, pripomienky a prehľad doplatkov medzi mobilom, tabletom a počítačom alebo s blízkym, ktorý vám pomáha s liekmi. Bez registrácie a hesla.'));
      var b = el('button', null, 'Prepojiť zariadenia'); b.type = 'button';
      b.addEventListener('click', function () {
        var id = hex(crypto.getRandomValues(new Uint8Array(16))), k = b64u(crypto.getRandomValues(new Uint8Array(32)));
        var nc = { id: id, k: k, v: 0, mt: {}, hs: {} }; saveCfg(nc); sync(nc).then(paint);
      });
      body.append(el('div', 'mine-tools'));
      body.lastChild.append(b);
      return;
    }
    var at = c.at ? new Date(c.at) : null;
    body.append(el('p', 'page-sub', 'Prepojenie je zapnuté' + (at ? ', naposledy zosynchronizované ' + at.toLocaleString('sk-SK', { day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit' }) : '') + '. Na druhom zariadení naskenujte QR kód fotoaparátom alebo otvorte odkaz.'));
    var wrap = el('div', 'sync-qr');
    if (window.qrcode) {
      var q = qrcode(0, 'M'); q.addData(link(c)); q.make();
      wrap.innerHTML = q.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
      var svg = wrap.querySelector('svg'); if (svg) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'QR kód na prepojenie zariadení'); }
    }
    body.append(wrap);
    var tools = el('div', 'mine-tools');
    var cp = el('button', null, 'Kopírovať odkaz'); cp.type = 'button';
    cp.addEventListener('click', function () { (navigator.clipboard ? navigator.clipboard.writeText(link(c)) : Promise.reject()).then(function () { status('Odkaz je skopírovaný. Pošlite ho len sebe alebo blízkemu – kto ho má, vidí vaše lieky.'); }, function () { prompt('Odkaz:', link(c)); }); });
    var now = el('button', null, 'Synchronizovať teraz'); now.type = 'button';
    now.addEventListener('click', function () { sync(cfg()).then(function () { status('Hotovo, údaje sú zosynchronizované.'); }); });
    var off = el('button', 'danger', 'Zrušiť prepojenie'); off.type = 'button';
    off.addEventListener('click', function () {
      if (!off.dataset.armed) { off.dataset.armed = '1'; off.classList.add('armed'); off.textContent = 'Naozaj zrušiť na tomto zariadení?'; return; }
      saveCfg(null); paint(); status('Prepojenie je na tomto zariadení zrušené. Údaje v tomto zariadení zostali.');
    });
    tools.append(cp, now, off); body.append(tools);
    body.append(el('p', 'hint', 'Údaje sa šifrujú priamo vo vašom zariadení. Kľúč je len v QR kóde a odkaze, my ho nemáme a zašifrované údaje nevieme prečítať.'));
  }

  /* otvorený odkaz s #sync=… */
  var m = /#sync=([a-f0-9]{32})\.([A-Za-z0-9_-]{43})/.exec(location.hash);
  if (m) {
    history.replaceState(null, '', location.pathname);
    var nc = { id: m[1], k: m[2], v: 0, mt: {}, hs: {} };
    // nové zariadenie: jeho prázdne/staršie údaje nemajú prepísať prepojené, preto im dáme najstarší čas
    keys().forEach(function (k) { nc.mt[k] = 1; nc.hs[k] = h(localStorage.getItem(k)); });
    saveCfg(nc);
    sync(nc).then(function () { status('Zariadenie je prepojené a údaje sú načítané.'); card.scrollIntoView({ block: 'center' }); });
  }
  paint();
  var c0 = cfg();
  if (c0 && !m) sync(c0, true);
  // zmeny: po úprave zoznamu a pri návrate do karty
  var t = null;
  document.addEventListener('moje:rendered', function () { if (!cfg()) return; clearTimeout(t); t = setTimeout(function () { sync(cfg(), true); }, 1500); });
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible' && cfg()) sync(cfg(), true); });
})();
