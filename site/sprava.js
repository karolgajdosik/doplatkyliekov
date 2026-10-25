/* Správa e-mailových upozornení: zoznam liekov, odobratie, pridanie z Mojich liekov, zrušenie.
   Tajný odkaz (token) z e-mailu sa uloží v tomto prehliadači, aby sa sem dalo vrátiť aj bez e-mailu. */
(function () {
  'use strict';
  var KEY = 'upozornenia.t';
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function put(t) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch (e) { /* bez úložiska */ } }

  var url = new URL(location.href);
  var fromUrl = url.searchParams.get('t');
  if (fromUrl && /^[a-f0-9]{32}$/.test(fromUrl)) {
    put(fromUrl);
    url.searchParams.delete('t');
    history.replaceState(null, '', url.pathname + (url.search || '') + url.hash);
  }
  var root = document.getElementById('sprava-root');
  if (!root) return;   // stránka potvrdenia: len uložíme odkaz
  var token = get();

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function msg(t, ok) { var p = el('p', 'form-msg ' + (ok ? 'ok' : 'err'), t); return p; }

  /* formulár „pošlite mi odkaz“ */
  var lf = document.getElementById('manage-link-form');
  if (lf) lf.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var out = lf.querySelector('.form-msg');
    var email = (lf.querySelector('[name=email]').value || '').trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { out.textContent = 'Zadajte platnú e-mailovú adresu.'; out.className = 'form-msg err'; return; }
    var btn = lf.querySelector('button'); btn.disabled = true;
    fetch('/api/manage-link', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, web: lf.querySelector('[name=web]').value }) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j }; }); })
      .then(function (res) {
        if (res.s === 200) { out.textContent = 'Ak sú na tejto adrese zapnuté upozornenia, poslali sme na ňu odkaz na ich správu. Pozrite aj priečinok spam.'; out.className = 'form-msg ok'; }
        else { out.textContent = res.j.error || 'Nepodarilo sa to. Skúste to znova.'; out.className = 'form-msg err'; }
      })
      .catch(function () { out.textContent = 'Nepodarilo sa spojiť so serverom.'; out.className = 'form-msg err'; })
      .then(function () { btn.disabled = false; });
  });

  if (!token) {
    root.replaceChildren(el('h2', null, 'Odkaz na správu nemáme'),
      el('p', 'page-sub', 'Upozornenia upravíte cez odkaz „Upraviť zoznam liekov“ v e-maile s upozornením alebo si ho necháte poslať formulárom nižšie. Úplne sa odhlásite aj odkazom „Odhlásiť sa“ v každom e-maile.'));
    return;
  }

  var names = {};
  function loadNames() {
    return fetch('/data.json').then(function (r) { return r.json(); }).then(function (d) {
      d.groups.forEach(function (g) { g.i.forEach(function (it) { names[it[0]] = it[1] + ' – ' + it[2]; }); });
    }).catch(function () {});
  }
  function call(body) {
    body.t = token;
    return fetch('/api/manage', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j }; }); });
  }
  function gone(text) {
    put(null);
    root.replaceChildren(el('h2', null, 'Upozornenia sú zrušené'), el('p', 'page-sub', text));
    var a = el('a', 'cta', 'Moje lieky →'); a.href = '/moje-lieky/'; root.append(a);
    var link = document.getElementById('sprava-link'); if (link) link.hidden = true;
  }

  function render(data) {
    root.replaceChildren();
    root.append(el('h2', null, 'Vaše upozornenia'));
    var who = el('p', 'page-sub'); who.append('Upozornenia chodia na ', el('strong', null, data.email), '.');
    root.append(who);
    if (!data.confirmed) root.append(el('p', 'hint', 'Prihlásenie zatiaľ nie je potvrdené. Kliknite na odkaz v e-maile, ktorý sme vám poslali.'));
    var ul = el('ul', 'glist mine-list');
    data.kody.forEach(function (k) {
      var li = el('li'); var line = el('div', 'gline');
      line.append(el('span', 'tr-name', names[k] || ('Liek s kódom ŠÚKL ' + k)));
      var rm = el('button', 'mine-remove', 'Odobrať'); rm.type = 'button';
      rm.addEventListener('click', function () {
        rm.disabled = true;
        call({ remove: [k] }).then(function (res) {
          if (res.j.deleted) return gone('Odobrali ste posledný liek, preto sme upozornenia zrušili a vaše údaje vymazali.');
          if (res.s === 200) { data.kody = res.j.kody; render(data); } else { rm.disabled = false; root.append(msg(res.j.error || 'Nepodarilo sa to.')); }
        });
      });
      li.append(line, rm); ul.append(li);
    });
    if (!data.kody.length) ul.append(el('li', 'tr-empty', 'Nesledujete žiadny liek.'));
    root.append(ul);

    var mine = window.Moje ? window.Moje.list().map(function (m) { return m.kod; }) : [];
    var missing = mine.filter(function (k) { return data.kody.indexOf(k) < 0; });
    var tools = el('div', 'mine-tools');
    if (missing.length && data.confirmed) {
      var add = el('button', null, 'Pridať lieky z Mojich liekov (' + missing.length + ')'); add.type = 'button';
      add.addEventListener('click', function () {
        add.disabled = true;
        call({ add: missing }).then(function (res) { if (res.s === 200) { data.kody = res.j.kody; render(data); } else { add.disabled = false; } });
      });
      tools.append(add);
    }
    var del = el('button', 'danger', 'Zrušiť všetky upozornenia'); del.type = 'button';
    var armed = false;
    del.addEventListener('click', function () {
      if (!armed) { armed = true; del.textContent = 'Naozaj zrušiť a vymazať údaje?'; del.classList.add('armed'); return; }
      del.disabled = true;
      call({ deleteAll: true }).then(function (res) {
        if (res.s === 200) gone('Už vám nebudeme posielať žiadne e-maily a váš e-mail aj zoznam liekov sme vymazali. Zoznam Moje lieky v tomto prehliadači zostáva.');
        else { del.disabled = false; root.append(msg(res.j.error || 'Nepodarilo sa to.')); }
      });
    });
    tools.append(del);
    root.append(tools);
    root.append(el('p', 'hint', 'Zmeny platia hneď. Liek odobratý z Mojich liekov sa z upozornení neodoberie automaticky, urobte to tu.'));
  }

  Promise.all([
    fetch('/api/manage?t=' + encodeURIComponent(token)).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j }; }); }),
    loadNames()
  ]).then(function (res) {
    var r = res[0];
    if (r.s === 200) render(r.j);
    else if (r.s === 404) gone('Upozornenia na tomto odkaze už nie sú aktívne. Ak ich chcete znova, prihláste sa na stránke Moje lieky.');
    else root.replaceChildren(msg(r.j.error || 'Upozornenia sa nepodarilo načítať. Skúste to neskôr.'));
  }).catch(function () { root.replaceChildren(msg('Nepodarilo sa spojiť so serverom. Skúste to neskôr.')); });
})();
