/* Moje lieky: zoznam liekov uložený len v prehliadači používateľa (localStorage),
   kalkulačka ročného doplatku, tlač a zdieľanie zoznamu, e-mailové upozornenia a inštalácia aplikácie.
   Používa ho každá stránka webu. */
(function () {
  'use strict';
  var BASE_KEY = 'mojeLieky.v1', PROF_KEY = 'mojeLieky.profily.v1';

  /* rodinné profily: každý člen rodiny má vlastný zoznam; prvý profil používa pôvodný kľúč (spätná kompatibilita) */
  function profiles() {
    try { var v = JSON.parse(localStorage.getItem(PROF_KEY) || 'null'); if (v && Array.isArray(v.list) && v.list.length) return v; } catch (e) { /* nič */ }
    return { cur: 'p0', list: [{ id: 'p0', name: 'Ja' }] };
  }
  function saveProfiles(v) { try { localStorage.setItem(PROF_KEY, JSON.stringify(v)); } catch (e) { /* nič */ } }
  function keyFor(id) { return id === 'p0' ? BASE_KEY : BASE_KEY + '.' + id; }
  function curProfile() { var P = profiles(); return P.list.filter(function (x) { return x.id === P.cur; })[0] || P.list[0]; }
  function readKey(k) {
    try { var v = JSON.parse(localStorage.getItem(k) || '[]'); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  }
  function read() { return readKey(keyFor(curProfile().id)); }
  function allItems() {
    var out = [];
    profiles().list.forEach(function (p) { readKey(keyFor(p.id)).forEach(function (x) { out.push(x); }); });
    return out;
  }
  function rawWrite(list) { try { localStorage.setItem(keyFor(curProfile().id), JSON.stringify(list)); } catch (e) { /* súkromné okno, plné úložisko */ } }
  function write(list) { rawWrite(list); refresh(); }
  var Profiles = {
    all: function () { return profiles(); },
    current: curProfile,
    select: function (id) { var P = profiles(); P.cur = id; saveProfiles(P); refresh(); },
    add: function (name) {
      var P = profiles(); if (P.list.length >= 8) return null;
      var id = 'p' + Date.now().toString(36);
      P.list.push({ id: id, name: String(name).slice(0, 30) }); P.cur = id; saveProfiles(P); refresh(); return id;
    },
    rename: function (id, name) { var P = profiles(); P.list.forEach(function (x) { if (x.id === id) x.name = String(name).slice(0, 30); }); saveProfiles(P); refresh(); },
    remove: function (id) {
      var P = profiles(); if (P.list.length < 2) return;
      try { localStorage.removeItem(keyFor(id)); } catch (e) { /* nič */ }
      if (id === 'p0') { // prvý profil má pôvodný kľúč: presunieme naň druhý profil
        var second = P.list[1];
        try { localStorage.setItem(BASE_KEY, localStorage.getItem(keyFor(second.id)) || '[]'); localStorage.removeItem(keyFor(second.id)); } catch (e) { /* nič */ }
        P.list.splice(1, 1); P.list[0] = { id: 'p0', name: second.name }; P.cur = 'p0';
      } else { P.list = P.list.filter(function (x) { return x.id !== id; }); if (P.cur === id) P.cur = 'p0'; }
      saveProfiles(P); refresh();
    }
  };
  window.MojeProfily = Profiles;

  /* 3D ilustrácia lieku podľa liekovej formy a skupiny ATC (rovnaká logika ako scripts/illus.py → form_of) */
  function formOf(pack) {
    var p = (pack || '').toLowerCase(), w = p.split(/\s+/), a = w[0] || '', b = w[1] || '';
    if (a === 'tbl' || a === 'tablety' || (a === 'lyo' && (b === 'por' || b === 'slg'))) return 'tablet';
    if (a === 'cps') return 'capsule';
    if (a === 'emp') return 'patch';
    if (a === 'sup') return 'supp';
    if (['crm', 'ung', 'gel', 'pst'].indexOf(a) >= 0 && b !== 'ist') return 'tube';
    if (a === 'int' || ['opo', 'opu', 'ope', 'osd', 'ots', 'oph'].indexOf(b) >= 0) return 'eye';
    if (['nas', 'nao', 'nau'].indexOf(b) >= 0) return 'nasal';
    if (['ihl', 'inh', 'ido', 'icd'].indexOf(b) >= 0 || (a === 'aer' && b === 'ora')) return 'inhaler';
    if (p.indexOf('pero') >= 0 || p.indexOf(' pen') >= 0) return 'pen';
    if (['gtt', 'gto', 'gte'].indexOf(a) >= 0) return 'drops';
    if (['gra', 'gro', 'gru'].indexOf(a) >= 0 || ((a === 'plv' || a === 'plo') && (p.indexOf('vre') >= 0 || ((b === 'sps' || b === 'por') && p.indexOf('fľ') < 0)))) return 'sachet';
    if (a === 'imp' || b.charAt(0) === 'i' || ['con', 'dis', 'plc', 'pci', 'lyo', 'kit'].indexOf(a) >= 0 || ['sif', 'suf', 'sul'].indexOf(b) >= 0) return 'vial';
    if (['sir', 'sol', 'sus', 'liq', 'plu', 'plv', 'emu', 'add', 'shp', 'lum', 'plq', 'aer'].indexOf(a) >= 0) return 'bottle';
    return 'other';
  }
  window.img3d = function (pack, atc, cls) {
    var img = document.createElement('img');
    img.src = '/img3d/' + formOf(pack) + '-' + ((atc || 'V').charAt(0)) + '.webp';
    img.alt = ''; img.loading = 'lazy'; img.decoding = 'async'; img.width = 640; img.height = 480;
    if (cls) img.className = cls;
    img.onerror = function () { img.onerror = null; img.src = '/img3d/other-V.webp'; };
    return img;
  };
  var Moje = {
    list: read,
    has: function (kod) { return read().some(function (x) { return x.kod === kod; }); },
    add: function (item) { var l = read().filter(function (x) { return x.kod !== item.kod; }); l.push(item); write(l); },
    remove: function (kod) { write(read().filter(function (x) { return x.kod !== kod; })); },
    update: function (kod, patch) {
      write(read().map(function (x) { if (x.kod === kod) { for (var k in patch) x[k] = patch[k]; } return x; }));
    },
    toggle: function (item) { if (Moje.has(item.kod)) Moje.remove(item.kod); else Moje.add(item); }
  };
  window.Moje = Moje;

  function eur(n) {
    return n == null ? '–' : n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  }
  function num(n, d) { return n.toLocaleString('sk-SK', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); }
  // rovnaký slug ako v scripts/build_pages.py (product_slug)
  function slugify(t, n) { return String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, n || 60).replace(/-+$/, ''); }
  function slugOf(name, kod) { return slugify(name) + '-' + slugify(kod); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function skDate(iso) { var p = iso.split('-'); return (+p[2]) + '. ' + (+p[1]) + '. ' + p[0]; }
  function dose(v) { var d = parseFloat(String(v == null ? '' : v).replace(',', '.')); return d > 0 && d <= 20 ? d : 1; }

  /* tlačidlá „Pridať do Mojich liekov“ */
  function paintButton(b) {
    var on = Moje.has(b.getAttribute('data-kod'));
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    var t = b.querySelector('.mine-label');
    var lg = document.documentElement.lang;
    var lbl = { hu: ['Elmentve a Gyógyszereim közé', 'Mentés a Gyógyszereim közé'], uk: ['Збережено в Моїх ліках', 'Зберегти в Мої ліки'] }[lg] || ['Uložené v Mojich liekoch', 'Pridať do Mojich liekov'];
    var who = profiles().list.length > 1 ? ' (' + curProfile().name + ')' : '';
    if (t) t.textContent = (on ? lbl[0] : lbl[1]) + who;
  }
  function refresh() {
    var n = read().length;
    document.querySelectorAll('[data-mine-count]').forEach(function (e) { e.textContent = n ? String(n) : ''; e.hidden = !n; });
    document.querySelectorAll('.mine-btn[data-kod]').forEach(paintButton);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.mine-btn[data-kod]');
    if (!b) return;
    ev.preventDefault();
    var item = { kod: b.getAttribute('data-kod'), name: b.getAttribute('data-name') || '', slug: b.getAttribute('data-slug') || '' };
    var yc = document.querySelector('.year-calc input');
    if (yc && !Moje.has(item.kod)) item.d = dose(yc.value);
    Moje.toggle(item);
    if (window.renderMoje) window.renderMoje();
  });

  /* „Ukázať v lekárni“: lacnejšia náhrada na celej obrazovke, vždy po slovensky (pre lekárnika) */
  var wake = null;
  function showPharm(d) {
    var ov = el('div', 'pharm-ov'); ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true'); ov.setAttribute('aria-label', 'Liek pre lekárnika');
    ov.lang = 'sk';
    var card = el('div', 'pharm-card');
    card.append(el('p', 'pc-ask', 'Prosím o liek s nižším doplatkom:'), el('p', 'pc-name', d.name), el('p', 'pc-pack', d.pack));
    var code = el('p', 'pc-code'); code.append(el('span', null, 'Kód ŠÚKL'), el('b', null, d.kod)); card.append(code);
    var dp = el('p', 'pc-dop'); dp.append('Doplatok ', el('b', null, d.dop)); card.append(dp);
    if (d.orig) card.append(el('p', 'pc-orig', 'namiesto: ' + d.orig + (d.origdop ? ' (' + d.origdop + ')' : '')));
    card.append(el('p', 'pc-note', 'Rovnaká účinná látka, sila a veľkosť balenia. Ak lekár na recepte nevyznačil, že liek sa nesmie zamieňať.'));
    var close = el('button', 'pc-close', 'Zavrieť'); close.type = 'button';
    card.append(close, el('p', 'pc-src', 'doplatkyliekov.sk · údaje zo zoznamu MZ SR'));
    ov.append(card); document.body.append(ov); document.documentElement.classList.add('pharm-open');
    function done() { ov.remove(); document.documentElement.classList.remove('pharm-open'); if (wake) { wake.release().catch(function () {}); wake = null; } document.removeEventListener('keydown', esc); }
    function esc(e) { if (e.key === 'Escape') done(); }
    close.addEventListener('click', done); document.addEventListener('keydown', esc); close.focus();
    try { if (navigator.wakeLock) navigator.wakeLock.request('screen').then(function (w) { wake = w; }).catch(function () {}); } catch (e) { /* nič */ }
    try { if (screen.orientation && screen.orientation.lock) screen.orientation.lock('portrait').catch(function () {}); } catch (e) { /* nič */ }
  }
  window.showPharm = showPharm;
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-pharm]');
    if (!b) return;
    ev.preventDefault();
    showPharm({ name: b.dataset.name, kod: b.dataset.kod, pack: b.dataset.pack, dop: b.dataset.dop, orig: b.dataset.orig, origdop: b.dataset.origdop });
  });

  /* kalkulačka ročného doplatku na stránke lieku */
  function bindYearCalc(box) {
    var ks = +box.getAttribute('data-ks'), dop = +box.getAttribute('data-dop');
    var best = box.hasAttribute('data-best') ? +box.getAttribute('data-best') : null;
    var inp = box.querySelector('input');
    var kod = (document.querySelector('.mine-btn[data-kod]') || { getAttribute: function () { return null; } }).getAttribute('data-kod');
    var saved = read().filter(function (x) { return x.kod === kod; })[0];
    if (saved && saved.d) inp.value = saved.d;
    function set(k, t) { var e = box.querySelector('[data-yc="' + k + '"]'); if (e) e.textContent = t; }
    function calc() {
      var d = dose(inp.value), packs = 365 * d / ks;
      var days = ks / d;
      set('days', (days >= 10 ? num(days) : num(days, 1)) + ' ' + (days === 1 ? 'deň' : days < 5 && days % 1 === 0 ? 'dni' : 'dní'));
      set('packs', num(packs, 1));
      set('year', eur(packs * dop));
      if (best != null) { set('best', eur(packs * best)); set('save', eur(packs * (dop - best))); }
      if (kod && Moje.has(kod)) Moje.update(kod, { d: d });
    }
    box.querySelectorAll('button[data-step]').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = Math.max(0.25, Math.min(20, dose(inp.value) + parseFloat(b.getAttribute('data-step'))));
        inp.value = v; calc();
      });
    });
    inp.addEventListener('input', calc);
    calc();
  }

  /* formulár e-mailových upozornení */
  function bindForm(form) {
    if (form.dataset.bound) return;
    form.dataset.bound = '1';
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var out = form.querySelector('.form-msg');
      var email = (form.querySelector('[name=email]').value || '').trim();
      var consent = form.querySelector('[name=consent]').checked;
      var hp = (form.querySelector('[name=web]') || {}).value || '';
      var kody = allItems().map(function (x) { return x.kod; }).filter(function (k, i, a) { return a.indexOf(k) === i; });
      var own = form.getAttribute('data-kod');
      if (own && kody.indexOf(own) < 0) kody.push(own);
      function say(t, ok) { out.textContent = t; out.className = 'form-msg ' + (ok ? 'ok' : 'err'); }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return say('Zadajte platnú e-mailovú adresu.');
      if (!consent) return say('Na zasielanie upozornení potrebujeme váš súhlas.');
      if (!kody.length) return say('Najprv si uložte aspoň jeden liek do Mojich liekov.');
      var btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      fetch('/api/subscribe', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, kody: kody, consent: true, web: hp, digest: !!(form.querySelector('[name=digest]') || {}).checked })
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, j: j }; });
      }).then(function (res) {
        if (res.status === 200) say('Hotovo. Poslali sme vám e-mail, potvrďte v ňom prihlásenie.', true);
        else if ([404, 405, 501, 503].indexOf(res.status) >= 0) say('E-mailové upozornenia zatiaľ spúšťame. Skúste to prosím o pár dní.');
        else say(res.j.error || 'Prihlásenie sa nepodarilo. Skúste to znova.');
      }).catch(function () { say('Nepodarilo sa spojiť so serverom. Skúste to znova.'); })
        .then(function () { btn.disabled = false; });
    });
  }

  /* zdieľaný zoznam: /moje-lieky/?l=KOD,KOD*2,... (číslo za * = dávok denne) */
  function sharedList() {
    var q = new URLSearchParams(location.search).get('l');
    if (!q) return null;
    var out = [];
    q.split(',').forEach(function (part) {
      var m = /^([0-9A-Z]{4,6})(?:\*([0-9.]+))?$/.exec(part.trim().toUpperCase());
      if (m && out.length < 60) out.push({ kod: m[1], d: m[2] ? dose(m[2]) : undefined });
    });
    return out.length ? out : null;
  }
  function shareUrl(list) {
    return location.origin + '/moje-lieky/?l=' + list.map(function (m) {
      return m.kod + (m.d && m.d !== 1 ? '*' + m.d : '');
    }).join(',');
  }

  /* stránka /moje-lieky/ */
  var cache = null, slugCache = null;
  function loadData() {
    if (cache) return cache;
    cache = Promise.all([
      fetch('/data.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }),
      fetch('/alerts.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : { items: {} }; }).catch(function () { return { items: {} }; })
    ]);
    return cache;
  }
  function loadSlugs() {
    if (!slugCache) slugCache = fetch('/slugs.json').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return slugCache;
  }

  /* kedy mi dôjde liek */
  var RUNOUT = {};
  function todayIso() { var t = new Date(); return t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); }
  function addDays(iso, n) { var p = iso.split('-'); var t = new Date(+p[0], +p[1] - 1, +p[2] + n); return t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); }
  function daysTo(iso) { var p = iso.split('-'); var a = new Date(+p[0], +p[1] - 1, +p[2]); var b = new Date(); b.setHours(0, 0, 0, 0); return Math.round((a - b) / 864e5); }
  function refillBox(m, ks, d, name) {
    if (m.k !== ks) rawWrite(read().map(function (x) { if (x.kod === m.kod) x.k = ks; return x; }));
    var box = el('div', 'mine-refill');
    if (!m.s || !/^\d{4}-\d{2}-\d{2}$/.test(m.s)) {
      delete RUNOUT[m.kod];
      box.append(el('span', null, 'Kedy vám liek dôjde? '));
      var now = el('button', 'linkish', 'Začal som nové balenie dnes'); now.type = 'button';
      now.addEventListener('click', function () { Moje.update(m.kod, { s: todayIso() }); window.renderMoje(); });
      var lab = el('label', 'mine-start', 'alebo dňa ');
      var di = el('input'); di.type = 'date'; di.max = todayIso(); di.setAttribute('aria-label', 'Dátum začatia balenia: ' + name);
      di.addEventListener('change', function () { if (di.value) { Moje.update(m.kod, { s: di.value }); window.renderMoje(); } });
      lab.append(di); box.append(now, ' ', lab);
      return box;
    }
    var out = addDays(m.s, Math.floor(ks / d));
    RUNOUT[m.kod] = out;
    var left = daysTo(out);
    var txt = left < 0 ? 'Balenie už malo dôjsť ' + skDate(out) + '.' : left === 0 ? 'Balenie dôjde dnes.' : 'Balenie dôjde približne ' + skDate(out) + ' (o ' + left + (left === 1 ? ' deň' : left < 5 ? ' dni' : ' dní') + ').';
    var info = el('span', left <= 7 ? 'mine-warn' : null, txt);
    if (left <= 7) info.append(' Myslite na nový recept.');
    var again = el('button', 'linkish', 'Mám nové balenie'); again.type = 'button';
    again.addEventListener('click', function () { Moje.update(m.kod, { s: todayIso() }); window.renderMoje(); });
    box.append(info, ' ', again);
    return box;
  }
  /* pripomienky užívania: časy pri lieku (pole t), notifikácia a/alebo kalendár */
  function dosesBox(m, name) {
    var box = el('div', 'mine-doses');
    var times = Array.isArray(m.t) ? m.t : [];
    box.append(el('span', null, times.length ? 'Pripomenúť užitie o ' : 'Pripomínať užitie? '));
    times.forEach(function (t) {
      var chip = el('span', 'dose-chip', t);
      var x = el('button', null, '×'); x.type = 'button'; x.setAttribute('aria-label', 'Zrušiť pripomienku o ' + t + ': ' + name);
      x.addEventListener('click', function () { Moje.update(m.kod, { t: times.filter(function (y) { return y !== t; }) }); window.renderMoje(); });
      chip.append(x); box.append(chip);
    });
    if (times.length < 6) {
      var add = el('button', 'linkish', times.length ? '+ ďalší čas' : 'Nastaviť čas'); add.type = 'button';
      var ti = el('input'); ti.type = 'time'; ti.hidden = true; ti.setAttribute('aria-label', 'Čas užitia: ' + name); ti.step = 300;
      add.addEventListener('click', function () { ti.hidden = false; add.hidden = true; ti.value = times.length ? '20:00' : '08:00'; ti.focus(); });
      ti.addEventListener('change', function () {
        if (!/^\d{2}:\d{2}$/.test(ti.value)) return;
        var nt = times.concat([ti.value]).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort();
        Moje.update(m.kod, { t: nt }); window.renderMoje();
        var st = pushState(); var msg = document.getElementById('mine-tools-msg');
        if (!st && msg) { msg.textContent = 'Aby pripomienky prišli do telefónu, zapnite nižšie notifikácie. Alebo si ich pridajte do kalendára.'; msg.className = 'form-msg ok'; }
      });
      box.append(add, ti);
    }
    return box;
  }
  function icsFor(list) {
    var lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//doplatkyliekov.sk//Moje lieky//SK', 'CALSCALE:GREGORIAN'];
    var stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
    list.forEach(function (m) {
      var out = RUNOUT[m.kod]; if (!out) return;
      var remind = addDays(out, -3); if (daysTo(remind) < 0) remind = todayIso();
      var d = remind.replace(/-/g, ''), d2 = addDays(remind, 1).replace(/-/g, '');
      lines.push('BEGIN:VEVENT', 'UID:' + m.kod + '-' + out + '@doplatkyliekov.sk', 'DTSTAMP:' + stamp,
        'DTSTART;VALUE=DATE:' + d, 'DTEND;VALUE=DATE:' + d2,
        'SUMMARY:Kúpiť liek: ' + (m.name || m.kod).replace(/[,;\\]/g, ' '),
        'DESCRIPTION:Balenie dôjde približne ' + skDate(out) + '. Ak treba\\, vyžiadajte si recept. doplatkyliekov.sk/moje-lieky/',
        'BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:Kúpiť liek', 'TRIGGER:PT9H', 'END:VALARM', 'END:VEVENT');
    });
    var who = profiles().list.length > 1 ? ' (' + curProfile().name + ')' : '';
    list.forEach(function (m) {
      (Array.isArray(m.t) ? m.t : []).forEach(function (t) {
        var hm = t.replace(':', '') + '00', d0 = todayIso().replace(/-/g, '');
        var nm = (m.name || m.kod).replace(/[,;\\]/g, ' ');
        lines.push('BEGIN:VEVENT', 'UID:dose-' + m.kod + '-' + t.replace(':', '') + '-' + curProfile().id + '@doplatkyliekov.sk', 'DTSTAMP:' + stamp,
          'DTSTART:' + d0 + 'T' + hm, 'DURATION:PT5M', 'RRULE:FREQ=DAILY',
          'SUMMARY:Užiť liek: ' + nm + ' (' + String(dose(m.d)).replace('.', '\\,') + ' ks)' + who.replace(/[,;]/g, ' '),
          'BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:Užiť liek ' + nm, 'TRIGGER:PT0M', 'END:VALARM', 'END:VEVENT');
      });
    });
    lines.push('END:VCALENDAR');
    return lines.join('\r\n');
  }

  /* notifikácie v telefóne (Web Push) */
  var VAPID = 'BIMBi6qoRml0DsWvgoUVItYTsgvdaAaOOjiFtsdlcd04L4qFCw7frmMeUYVVzuk3iirtULNrZH-STHGsN0RUCSw';
  var PKEY = 'push.v1';
  function pushState() { try { return JSON.parse(localStorage.getItem(PKEY) || 'null'); } catch (e) { return null; } }
  function pushSave(v) { try { if (v) localStorage.setItem(PKEY, JSON.stringify(v)); else localStorage.removeItem(PKEY); } catch (e) { /* nič */ } }
  function b64u(s) { var p = '='.repeat((4 - s.length % 4) % 4); var b = atob((s + p).replace(/-/g, '+').replace(/_/g, '/')); var a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; }
  function pushPayload() {
    // všetky profily v tomto zariadení; dátum dôjdenia z dátumu otvorenia balenia, dávky a počtu kusov
    var kody = [], refills = {}, doses = [];
    var P = profiles();
    P.list.forEach(function (p) {
      readKey(keyFor(p.id)).forEach(function (x) {
        (Array.isArray(x.t) ? x.t : []).forEach(function (t) { doses.push({ k: x.kod, t: t, d: dose(x.d), w: P.list.length > 1 ? p.name : '' }); });
      });
    });
    allItems().forEach(function (x) {
      if (kody.indexOf(x.kod) < 0) kody.push(x.kod);
      if (x.s && x.k && /^\d{4}-\d{2}-\d{2}$/.test(x.s)) {
        var out = addDays(x.s, Math.floor(x.k / dose(x.d)));
        if (!refills[x.kod] || out < refills[x.kod]) refills[x.kod] = out;
      }
    });
    var tz = 'Europe/Bratislava'; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || tz; } catch (e) { /* nič */ }
    return { kody: kody, refills: refills, doses: doses, tz: tz };
  }
  function pushSync() {
    var st = pushState(); if (!st) return;
    var p = pushPayload(), sig = JSON.stringify(p);
    if (sig === st.sig) return;
    fetch('/api/push', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'update', id: st.id, endpoint: st.endpoint, kody: p.kody, refills: p.refills, doses: p.doses, tz: p.tz }) })
      .then(function (r) { if (r.ok) { st.sig = sig; pushSave(st); } else if (r.status === 404) pushSave(null); }).catch(function () {});
  }
  function pushUI() {
    var card = document.getElementById('push-card'); if (!card) return;
    var msg = card.querySelector('.form-msg'), on = document.getElementById('push-on'), off = document.getElementById('push-off'), cons = card.querySelector('.consent');
    var st = pushState();
    var supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
    card.hidden = false;
    function say(t, ok) { msg.textContent = t; msg.className = 'form-msg ' + (ok ? 'ok' : 'err'); }
    if (!supported) {
      on.hidden = true; off.hidden = true; cons.hidden = true;
      say(ios && !standalone() ? 'Na iPhone fungujú notifikácie len vtedy, keď si web pridáte na plochu (Safari → Zdieľať → Pridať na plochu) a otvoríte ho odtiaľ.' : 'Tento prehliadač notifikácie nepodporuje. Môžete si nastaviť upozornenia e-mailom alebo pripomienky do kalendára.');
      return;
    }
    on.hidden = !!st; cons.hidden = !!st; off.hidden = !st;
    if (st) say('Notifikácie sú zapnuté na tomto zariadení.', true);
    on.onclick = function () {
      if (!card.querySelector('#push-consent').checked) return say('Na zasielanie notifikácií potrebujeme váš súhlas.');
      if (!allItems().length) return say('Najprv si uložte aspoň jeden liek.');
      on.disabled = true;
      Notification.requestPermission().then(function (perm) {
        if (perm !== 'granted') throw new Error('perm');
        return navigator.serviceWorker.register('/sw.js').then(function () { return navigator.serviceWorker.ready; });
      }).then(function (reg) {
        return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(VAPID) });
      }).then(function (sub) {
        var p = pushPayload(), j = sub.toJSON();
        return fetch('/api/push', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'subscribe', sub: j, kody: p.kody, refills: p.refills, doses: p.doses, tz: p.tz, consent: true }) })
          .then(function (r) { return r.json().then(function (x) { if (!r.ok) throw new Error(x.error || 'server'); pushSave({ id: x.id, endpoint: j.endpoint, sig: JSON.stringify(p) }); }); });
      }).then(function () { pushUI(); say('Hotovo. Notifikácie sú zapnuté na tomto zariadení.', true); })
        .catch(function (e) { say(e.message === 'perm' ? 'Notifikácie ste v prehliadači nepovolili. Povoľte ich v nastaveniach.' : 'Notifikácie sa nepodarilo zapnúť. ' + (e.message && e.message.length < 80 ? e.message : '')); })
        .then(function () { on.disabled = false; });
    };
    off.onclick = function () {
      var s0 = pushState();
      navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) { if (sub) return sub.unsubscribe(); }).catch(function () {});
      if (s0) fetch('/api/push', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'delete', id: s0.id, endpoint: s0.endpoint }) }).catch(function () {});
      pushSave(null); pushUI(); say('Notifikácie sú vypnuté a údaje o zariadení sme vymazali.', true);
    };
  }

  function profileBar(root, shared) {
    var bar = document.getElementById('mine-profiles');
    if (!bar) { bar = el('section', 'mine-profiles'); bar.id = 'mine-profiles'; bar.setAttribute('aria-label', 'Členovia rodiny'); root.parentNode.insertBefore(bar, root); }
    bar.hidden = !!shared;
    if (shared) return;
    var P = profiles();
    bar.replaceChildren();
    var row = el('div', 'mp-row');
    P.list.forEach(function (p) {
      var b = el('button', 'mp-chip' + (p.id === P.cur ? ' on' : ''), p.name); b.type = 'button';
      b.setAttribute('aria-pressed', p.id === P.cur ? 'true' : 'false');
      var n = readKey(keyFor(p.id)).length; if (n) b.append(el('small', null, String(n)));
      b.addEventListener('click', function () { Profiles.select(p.id); window.renderMoje(); });
      row.append(b);
    });
    var addB = el('button', 'mp-add', '+ Pridať člena rodiny'); addB.type = 'button';
    if (P.list.length >= 8) addB.hidden = true;
    row.append(addB);
    bar.append(row);
    var form = el('form', 'mp-form'); form.hidden = true;
    var inp = el('input'); inp.maxLength = 30; inp.placeholder = 'Meno, napr. Mama'; inp.setAttribute('aria-label', 'Meno člena rodiny');
    var ok = el('button', null, 'Uložiť'); ok.type = 'submit';
    var cancel = el('button', 'linkish', 'Zrušiť'); cancel.type = 'button';
    form.append(inp, ok, cancel);
    bar.append(form);
    var mode = 'add';
    addB.addEventListener('click', function () { mode = 'add'; inp.value = ''; form.hidden = false; inp.focus(); });
    cancel.addEventListener('click', function () { form.hidden = true; });
    form.addEventListener('submit', function (e) {
      e.preventDefault(); var v = inp.value.trim(); if (!v) return inp.focus();
      if (mode === 'add') Profiles.add(v); else Profiles.rename(P.cur, v);
      window.renderMoje();
    });
    var cur = curProfile();
    var tools = el('p', 'mp-tools');
    tools.append(el('span', null, 'Zoznam: ' + cur.name + ' · '));
    var ren = el('button', 'linkish', 'Premenovať'); ren.type = 'button';
    ren.addEventListener('click', function () { mode = 'rename'; inp.value = cur.name; form.hidden = false; inp.focus(); });
    tools.append(ren);
    if (P.list.length > 1) {
      var del = el('button', 'linkish', 'Odstrániť zoznam'); del.type = 'button';
      del.addEventListener('click', function () {
        if (del.dataset.armed) { Profiles.remove(cur.id); window.renderMoje(); return; }
        del.dataset.armed = '1'; del.textContent = 'Naozaj odstrániť zoznam ' + cur.name + '?';
      });
      tools.append(' · ', del);
    }
    bar.append(tools);
    var hint = el('p', 'hint', 'Každý člen rodiny má vlastný zoznam liekov, dávkovanie aj pripomienky. Notifikácie a upozornenia e-mailom platia pre lieky zo všetkých zoznamov.');
    if (P.list.length < 2) bar.append(hint);
  }

  window.renderMoje = function () {
    var root = document.getElementById('moje-root');
    if (!root) return;
    var shared = sharedList();
    profileBar(root, shared);
    var list = shared || read();
    var tools = document.getElementById('mine-tools');
    if (!list.length) {
      if (tools) tools.hidden = true;
      root.replaceChildren();
      var empty = el('div', 'card empty-state');
      empty.append(el('h2', null, profiles().list.length > 1 && !shared ? 'Zoznam ' + curProfile().name + ' je zatiaľ prázdny' : 'Zatiaľ nemáte uložený žiadny liek'));
      var p = el('p', 'page-sub');
      p.append('Vyhľadajte liek, ktorý užívate, a na jeho stránke kliknite na ', el('strong', null, 'Pridať do Mojich liekov'), '. Zoznam sa uloží len vo vašom prehliadači.');
      var a = el('a', 'cta', 'Vyhľadať liek →'); a.href = '/';
      empty.append(p, a);
      root.append(empty);
      window.MojeStats = { packSave: 0, yearSave: 0, yearNow: 0, count: 0, known: 0, shared: !!shared };
      document.dispatchEvent(new CustomEvent('moje:rendered', { detail: { list: [], shared: !!shared } }));
      return;
    }
    Promise.all([loadData(), shared ? loadSlugs() : Promise.resolve({})]).then(function (all) {
      var data = all[0][0], alerts = all[0][1] || { items: {} }, slugs = all[1];
      var byKod = {};
      data.groups.forEach(function (g) { g.i.forEach(function (it) { byKod[it[0]] = { g: g, it: it }; }); });
      root.replaceChildren();
      var totalPack = 0, yearNow = 0, yearBest = 0, yearKnown = 0;
      var ul = el('ul', 'glist mine-list');
      var prows = [];
      list.forEach(function (m) {
        var hit = byKod[m.kod];
        var name = m.name || (hit ? hit.it[1] : m.kod);
        var slug = m.slug || slugs[m.kod];
        var li = el('li');
        var line = el('div', 'gline');
        var a = el('a', null, name); a.href = slug ? '/liek/' + slug + '/' : '#';
        line.append(a);
        var prow = { name: name, kod: m.kod, pack: '', dose: '', dop: '–', alt: '' };
        if (!hit) {
          line.append(el('span', 'mono', '–'));
          line.append(el('small', null, 'Liek už nie je v zozname hradených liekov.'));
        } else {
          var it = hit.it, g = hit.g, ks = it[8], d = dose(m.d);
          li.classList.add('has-thumb'); li.prepend(window.img3d(it[2], g.a, 'mine-thumb'));
          prow.pack = it[2]; prow.dop = eur(it[5]);
          line.append(el('span', 'mono', eur(it[5])));
          line.append(el('small', null, it[2]));
          var cheapest = g.i.filter(function (x) { return x[5] != null; }).sort(function (a, b) { return a[5] - b[5]; })[0];
          var diff = (cheapest && it[5] != null) ? it[5] - cheapest[5] : 0;
          if (diff > 0.005) {
            totalPack += diff;
            var s = el('small', 'mine-save');
            var alt = el('a', null, cheapest[1]); alt.href = '/liek/' + slugOf(cheapest[1], cheapest[0]) + '/';
            s.append('Lacnejšia alternatíva: ', alt, ' za ' + eur(cheapest[5]) + ' (ušetríte ' + eur(diff) + ' na balení) ');
            var pb = el('button', 'linkish pharm-mini', 'Ukázať v lekárni'); pb.type = 'button';
            pb.addEventListener('click', function () { showPharm({ name: cheapest[1], kod: cheapest[0], pack: cheapest[2], dop: eur(cheapest[5]), orig: it[1], origdop: eur(it[5]) }); });
            s.append(pb);
            line.append(s);
            prow.alt = cheapest[1] + ' (' + eur(cheapest[5]) + ')';
          }
          if (ks && it[5] != null) {
            var packs = 365 * d / ks;
            yearNow += packs * it[5]; yearBest += packs * (it[5] - Math.max(diff, 0)); yearKnown++;
            var yr = el('div', 'mine-dose');
            var lab = el('label', null, 'Denne ');
            var inp = el('input'); inp.type = 'number'; inp.min = '0.25'; inp.max = '20'; inp.step = '0.25'; inp.value = d; inp.inputMode = 'decimal';
            inp.setAttribute('aria-label', 'Počet denne: ' + name);
            if (shared) inp.disabled = true;
            inp.addEventListener('change', function () { Moje.update(m.kod, { d: dose(inp.value) }); window.renderMoje(); });
            lab.append(inp, ' ks');
            yr.append(lab, el('span', null, 'ročne ' + eur(packs * it[5]) + (diff > 0.005 ? ', s alternatívou ' + eur(packs * (it[5] - diff)) : '')));
            line.append(yr);
            prow.dose = d.toLocaleString('sk-SK', { maximumFractionDigits: 2 }) + ' denne';
            if (!shared) line.append(refillBox(m, ks, d, name));
          }
          if (!shared) line.append(dosesBox(m, name));
          var al = alerts.items && alerts.items[m.kod];
          if (al && al.n !== undefined && alerts.next) {
            line.append(el('small', 'mine-warn', al.n === null
              ? 'Od ' + skDate(alerts.next) + ' liek vypadne zo zoznamu hradených liekov.'
              : 'Od ' + skDate(alerts.next) + ' doplatok ' + (al.n > it[5] ? 'stúpne' : 'klesne') + ' na ' + eur(al.n) + '.'));
          }
          if (al && al.v) {
            var txt = { R: 'Prerušené dodávky od ', Z: 'Ukončené dodávky od ', PR: 'Ohlásené prerušenie dodávok od ', PZ: 'Ohlásené ukončenie dodávok od ' }[al.v[0]];
            if (txt) line.append(el('small', 'mine-warn', txt + skDate(al.v[1]) + '.'));
          }
        }
        li.append(line);
        if (!shared) {
          var rm = el('button', 'mine-remove', 'Odobrať'); rm.type = 'button';
          rm.addEventListener('click', function () { Moje.remove(m.kod); window.renderMoje(); });
          li.append(rm);
        }
        ul.append(li);
        prows.push(prow);
      });

      var head = el('div', 'mine-summary');
      if (shared) {
        var banner = el('div', 'card shared-banner');
        banner.append(el('h2', null, 'Zdieľaný zoznam liekov'));
        banner.append(el('p', 'page-sub', 'Niekto vám poslal tento zoznam. Môžete si ho vytlačiť alebo uložiť do svojich Mojich liekov.'));
        var save = el('button', null, 'Uložiť do mojich liekov'); save.type = 'button';
        save.addEventListener('click', function () {
          list.forEach(function (m) {
            var hit = byKod[m.kod];
            if (!Moje.has(m.kod)) Moje.add({ kod: m.kod, name: hit ? hit.it[1] : m.kod, slug: slugs[m.kod] || '', d: m.d });
          });
          location.href = '/moje-lieky/';
        });
        var mine = el('a', 'linkish', 'Zobraziť moje vlastné lieky'); mine.href = '/moje-lieky/';
        banner.append(save, ' ', mine);
        root.append(banner);
      }
      head.append(el('p', 'eyebrow', (shared ? 'Liekov v zozname: ' : 'Uložené lieky: ') + list.length));
      if (totalPack > 0.005) {
        var t = el('p', 'mine-total');
        t.append('Pri prechode na lacnejšie alternatívy ušetríte ', el('b', null, eur(totalPack)), ' na jednom nákupe');
        if (yearKnown && yearNow - yearBest > 0.005) t.append(' a približne ', el('b', null, eur(yearNow - yearBest)), ' za rok');
        t.append('.');
        head.append(t);
      }
      if (yearKnown) {
        head.append(el('p', 'mine-year', 'Ročne doplatíte približne ' + eur(yearNow) +
          (yearKnown < list.length ? ' (za ' + yearKnown + ' z ' + list.length + ' liekov, pri ostatných nevieme spotrebu vypočítať)' : '') + '.'));
      }
      root.append(head, ul);

      /* tabuľka len pre tlač */
      var tbl = el('table', 'print-only print-table');
      var thead = el('thead'); var hr = el('tr');
      ['Liek', 'Balenie', 'Kód ŠÚKL', 'Dávkovanie', 'Doplatok', 'Lacnejšia alternatíva'].forEach(function (h) { hr.append(el('th', null, h)); });
      thead.append(hr); tbl.append(thead);
      var tb = el('tbody');
      prows.forEach(function (r) {
        var tr = el('tr');
        [r.name, r.pack, r.kod, r.dose, r.dop, r.alt].forEach(function (c) { tr.append(el('td', null, c)); });
        tb.append(tr);
      });
      tbl.append(tb);
      if (!shared && profiles().list.length > 1) root.append(el('p', 'print-only print-note', 'Pacient: ' + curProfile().name));
      var note = el('p', 'print-only print-note', 'Pán doktor / pani doktorka, prosím o posúdenie, či je možné predpísať liek s nižším doplatkom alebo predpisovať názvom účinnej látky. Alternatívy majú rovnakú účinnú látku, silu a veľkosť balenia.');
      root.append(tbl, note);

      if (!shared) pushSync();
      window.MojeStats = { packSave: totalPack, yearSave: yearKnown ? yearNow - yearBest : 0, yearNow: yearNow, count: list.length, known: yearKnown, shared: !!shared };
      document.dispatchEvent(new CustomEvent('moje:rendered', { detail: { list: list, shared: !!shared } }));
      var cal = document.getElementById('mine-ics');
      if (cal) {
        cal.hidden = shared || (!Object.keys(RUNOUT).length && !list.some(function (m) { return Array.isArray(m.t) && m.t.length; }));
        cal.onclick = function () {
          var blob = new Blob([icsFor(list)], { type: 'text/calendar;charset=utf-8' });
          var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'pripomienky-lieky.ics';
          document.body.append(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        };
      }
      if (tools) {
        tools.hidden = false;
        var shareBtn = document.getElementById('mine-share');
        if (shareBtn) shareBtn.hidden = !!shared;
      }
    }).catch(function () {
      root.replaceChildren(el('p', 'page-sub', 'Údaje o liekoch sa nepodarilo načítať. Obnovte stránku.'));
    });
  };

  function bindTools() {
    var pr = document.getElementById('mine-print'), sh = document.getElementById('mine-share'), msg = document.getElementById('mine-tools-msg');
    var pd = document.getElementById('print-date');
    if (pd) pd.textContent = new Date().toLocaleDateString('sk-SK');
    if (pr) pr.addEventListener('click', function () { window.print(); });
    if (sh) sh.addEventListener('click', function () {
      var url = shareUrl(read());
      function say(t) { if (msg) { msg.textContent = t; msg.className = 'form-msg ok'; } }
      if (navigator.share) {
        navigator.share({ title: 'Moje lieky', text: 'Zoznam liekov, ktoré užívam', url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () { say('Odkaz je skopírovaný. Pošlite ho rodine alebo lekárovi.'); },
          function () { prompt('Skopírujte odkaz:', url); });
      } else { prompt('Skopírujte odkaz:', url); }
    });
  }

  /* aplikácia: service worker a inštalácia */
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); deferred = e; showInstall();
  });
  function standalone() { return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone; }
  function showInstall() {
    var card = document.getElementById('install-card');
    if (!card || standalone()) return;
    var btn = document.getElementById('install-btn'), txt = document.getElementById('install-text');
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (deferred) {
      card.hidden = false; btn.hidden = false;
      btn.onclick = function () { deferred.prompt(); deferred.userChoice.then(function () { deferred = null; card.hidden = true; }); };
    } else if (ios) {
      card.hidden = false;
      txt.textContent = 'Pridajte si web na plochu iPhonu: v Safari ťuknite na tlačidlo Zdieľať (štvorec so šípkou) a vyberte „Pridať na plochu“. Otvorí sa ako aplikácia a Moje lieky budete mať vždy po ruke.';
    }
  }
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(function () {}); });
  }

  document.addEventListener('moje:refresh', refresh);
  // zmena v inom okne (napr. pridanie lieku na inej karte)
  window.addEventListener('storage', function (e) { if (e.key && e.key.indexOf(BASE_KEY) === 0 || e.key === PROF_KEY) { refresh(); if (window.renderMoje) window.renderMoje(); } });

  function init() {
    refresh();
    document.querySelectorAll('form.alert-form:not(#manage-link-form)').forEach(bindForm);
    document.querySelectorAll('.year-calc').forEach(bindYearCalc);
    bindTools();
    showInstall();
    pushUI();
    window.renderMoje();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
