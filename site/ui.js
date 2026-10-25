/* Rozhranie: vysúvacie menu, panel Zobrazenie (farebný režim, veľkosť písma, režim pre slabozrakých).
   Voľba sa ukladá len v prehliadači (localStorage „zobrazenie.v1“). */
(function () {
  'use strict';
  var KEY = 'zobrazenie.v1';
  var FS = [90, 100, 115, 130, 150];
  var root = document.documentElement;

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; } }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* bez úložiska */ } }
  var prefs = load();
  function cur() {
    return { t: prefs.t || 'dark', f: prefs.f != null ? +prefs.f : 1, c: !!prefs.c };
  }
  function apply() {
    var p = cur();
    root.dataset.theme = p.t;
    root.dataset.eff = (p.t === 'light' || (p.t === 'auto' && window.matchMedia('(prefers-color-scheme: light)').matches)) ? 'light' : 'dark';
    root.dataset.fs = String(p.f);
    if (p.c) root.dataset.contrast = 'high'; else delete root.dataset.contrast;
    var light = root.dataset.eff === 'light';
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', p.c ? (light ? '#ffffff' : '#000000') : (light ? '#f3f7f5' : '#05090b'));
    paint();
  }
  function paint() {
    var p = cur();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) { b.setAttribute('aria-label', root.dataset.eff === 'light' ? 'Prepnúť na tmavý režim' : 'Prepnúť na svetlý režim'); b.setAttribute('aria-pressed', root.dataset.eff === 'light' ? 'true' : 'false'); });
    document.querySelectorAll('input[name="theme"]').forEach(function (r) { r.checked = r.value === p.t; });
    var out = document.getElementById('fs-out');
    if (out) out.textContent = FS[p.f] + ' %';
    document.querySelectorAll('[data-fs]').forEach(function (b) {
      if (b.tagName !== 'BUTTON') return;
      var d = +b.getAttribute('data-fs');
      b.disabled = (d < 0 && p.f <= 0) || (d > 0 && p.f >= FS.length - 1);
    });
    var c = document.getElementById('set-contrast');
    if (c) c.checked = p.c;
  }
  function set(k, v) {
    prefs[k] = v;
    if (k === 't' && v === 'dark') delete prefs.t;
    if (k === 'f' && v === 1) delete prefs.f;
    if (k === 'c' && !v) delete prefs.c;
    save(prefs); apply();
  }

  /* vysúvacie panely */
  var openEl = null, lastFocus = null;
  var backdrop = document.querySelector('.sheet-backdrop');
  function focusables(el) {
    return Array.prototype.filter.call(el.querySelectorAll('a[href], button:not([disabled]), input, select, [tabindex]:not([tabindex="-1"])'),
      function (x) { return x.offsetParent !== null; });
  }
  function open(id, from) {
    var el = document.getElementById(id);
    if (!el) return;
    if (openEl && openEl !== el) openEl.hidden = true; else lastFocus = from || document.activeElement;
    openEl = el; el.hidden = false; if (backdrop) backdrop.hidden = false;
    document.body.classList.add('sheet-open');
    document.querySelectorAll('[data-open="' + id + '"]').forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    paint();
    var f = el.querySelector('input:checked') || focusables(el)[0];
    if (f) f.focus();
  }
  function close() {
    if (!openEl) return;
    var id = openEl.id;
    openEl.hidden = true; openEl = null;
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove('sheet-open');
    document.querySelectorAll('[data-open="' + id + '"]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target : null;
    if (!t) return;
    var o = t.closest('[data-open]');
    if (o) { e.preventDefault(); open(o.getAttribute('data-open'), o); return; }
    if (t.closest('[data-close]')) { e.preventDefault(); close(); return; }
    var fs = t.closest('button[data-fs]');
    if (fs) { var p = cur(); set('f', Math.max(0, Math.min(FS.length - 1, p.f + +fs.getAttribute('data-fs')))); return; }
    if (t.closest('#set-reset')) { prefs = {}; save(prefs); apply(); }
    if (t.closest('[data-theme-toggle]')) {
      var next = root.dataset.eff === 'light' ? 'dark' : 'light';
      set('t', next);
      var b = t.closest('[data-theme-toggle]');
      b.setAttribute('aria-label', next === 'light' ? 'Prepnúť na tmavý režim' : 'Prepnúť na svetlý režim');
    }
  });
  document.addEventListener('change', function (e) {
    if (e.target.name === 'theme') set('t', e.target.value);
    if (e.target.id === 'set-contrast') set('c', e.target.checked);
  });
  document.addEventListener('keydown', function (e) {
    if (!openEl) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Tab') {
      var f = focusables(openEl);
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  try {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function () { if (cur().t === 'auto') apply(); });
  } catch (e) { /* staršie prehliadače */ }
  document.querySelectorAll('[data-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  apply();
})();
