/* Service worker doplatkyliekov.sk: stránky a dáta najprv zo siete (aby boli aktuálne),
   bez internetu z vyrovnávacej pamäte. Štýly, skripty a písma (/fonts) z pamäte s obnovou na pozadí. */
'use strict';
var V = 'v9';
var SHELL = 'shell-' + V, PAGES = 'pages-' + V;
var PRECACHE = ['/', '/moje-lieky/', '/ochranny-limit/',
  '/data.json', '/alerts.json', '/manifest.webmanifest', '/icons/icon-192.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(SHELL).then(function (c) { return c.addAll(PRECACHE); }).catch(function () {}).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.slice(-V.length - 1) !== '-' + V; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(cacheName, max) {
  caches.open(cacheName).then(function (c) {
    c.keys().then(function (keys) { if (keys.length > max) c.delete(keys[0]).then(function () { trim(cacheName, max); }); });
  });
}
function networkFirst(req, cacheName) {
  return fetch(req).then(function (res) {
    if (res.ok) { var copy = res.clone(); caches.open(cacheName).then(function (c) { c.put(req, copy); trim(PAGES, 80); }); }
    return res;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: req.mode === 'navigate' }).then(function (hit) {
      if (hit) return hit;
      if (req.mode === 'navigate') {
        return caches.match('/moje-lieky/').then(function (m) {
          return m || new Response('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><body style="background:#fff;color:#0d1726;font-family:sans-serif;font-size:20px;padding:24px"><h1>Ste offline</h1><p>Táto stránka nie je uložená. Pripojte sa na internet a skúste to znova.</p>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
        });
      }
      return Response.error();
    });
  });
}
function staleWhileRevalidate(req) {
  return caches.open(SHELL).then(function (c) {
    return c.match(req).then(function (hit) {
      var net = fetch(req).then(function (res) { if (res.ok || res.type === 'opaque') c.put(req, res.clone()); return res; }).catch(function () { return hit; });
      return hit || net;
    });
  });
}

// zdieľanie fotky do aplikácie (Web Share Target): uložiť a otvoriť úvod, kde ju foto.js rozpozná
self.addEventListener('fetch', function (e) {
  var u = new URL(e.request.url);
  if (e.request.method !== 'POST' || u.origin !== location.origin || u.pathname !== '/zdielane/') return;
  e.respondWith(e.request.formData().then(function (fd) {
    var f = fd.get('foto');
    return caches.open('share').then(function (c) {
      return f && f.size ? c.put('/zdielane/foto', new Response(f, { headers: { 'Content-Type': f.type || 'image/jpeg' } })) : null;
    }).then(function () { return Response.redirect(f && f.size ? '/?akcia=zdielane' : '/', 303); });
  }).catch(function () { return Response.redirect('/', 303); }));
});
self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin === location.origin) {
    if (url.pathname.indexOf('/api/') === 0) return;
    if (req.mode === 'navigate' || /\.json$/.test(url.pathname)) {
      e.respondWith(networkFirst(req, req.mode === 'navigate' ? PAGES : SHELL));
      return;
    }
    // štýly a skripty najprv zo siete (inak by k novej stránke prišiel starý vzhľad), bez internetu z pamäte
    if (/\.(css|js)$/.test(url.pathname)) { e.respondWith(networkFirst(req, SHELL)); return; }
    if (/\.(png|svg|webmanifest|woff2?)$/.test(url.pathname)) { e.respondWith(staleWhileRevalidate(req)); return; }
    return;
  }
});

/* notifikácie */
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'doplatkyliekov.sk', {
    body: d.body || '', icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', tag: d.tag || 'doplatky', lang: 'sk',
    data: { url: d.url || '/moje-lieky/' }, renotify: !!d.dose, requireInteraction: !!d.dose,
    actions: d.dose ? [{ action: 'done', title: 'Užité' }] : []
  }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  if (e.action === 'done') return;
  var url = (e.notification.data && e.notification.data.url) || '/moje-lieky/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) { if ('focus' in list[i]) { list[i].navigate(url); return list[i].focus(); } }
    return self.clients.openWindow(url);
  }));
});
