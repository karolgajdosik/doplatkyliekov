/* AI asistent: konverzácia (len v tejto karte prehliadača, sessionStorage), bezpečné zobrazenie odpovede. */
(function () {
  'use strict';
  var KEY = 'asistent.v1';
  var log = document.getElementById('ai-log'), form = document.getElementById('ai-form'), inp = document.getElementById('ai-q');
  var sendBtn = document.getElementById('ai-send'), sugg = document.getElementById('ai-sugg'), ctxEl = document.getElementById('ai-ctx');
  if (!log || !form) return;
  var params = new URLSearchParams(location.search);
  var kod = /^[0-9A-Z]{4,6}$/.test(params.get('kod') || '') ? params.get('kod') : null;
  var conv = [];
  try { var s = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (s && Array.isArray(s.m)) { conv = s.m; if (!kod && s.kod) kod = s.kod; } } catch (e) { /* nič */ }
  function store() { try { sessionStorage.setItem(KEY, JSON.stringify({ m: conv.slice(-20), kod: kod })); } catch (e) { /* nič */ } }

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  /* jednoduchý a bezpečný markdown: odkazy len na tento web, tučné písmo, zoznamy, odseky */
  function inline(text, parent) {
    var re = /\[([^\]]{1,200})\]\(([^)\s]{1,300})\)|\*\*([^*]{1,300})\*\*/g, last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) parent.append(text.slice(last, m.index));
      if (m[1]) {
        var href = m[2].replace(/^https?:\/\/(www\.)?doplatkyliekov\.sk/, '');
        if (/^\/[a-z0-9\-/#?=&.]*$/i.test(href)) { var a = el('a', null, m[1]); a.href = href; parent.append(a); }
        else parent.append(m[1]);
      } else { parent.append(el('strong', null, m[3])); }
      last = re.lastIndex;
    }
    if (last < text.length) parent.append(text.slice(last));
  }
  function render(md) {
    var box = el('div', 'ai-md'), list = null;
    md.replace(/\r/g, '').split('\n').forEach(function (line) {
      var t = line.trim();
      var li = /^([-*•]|\d+[.)])\s+(.*)$/.exec(t);
      if (li) {
        if (!list) { list = el(/^\d/.test(li[1]) ? 'ol' : 'ul'); box.append(list); }
        var item = el('li'); inline(li[2], item); list.append(item);
        return;
      }
      list = null;
      if (!t) return;
      var h = /^#{1,4}\s+(.*)$/.exec(t);
      var p = el(h ? 'h3' : 'p'); inline(h ? h[1] : t, p); box.append(p);
    });
    return box;
  }
  function bubble(role, text) {
    var wrap = el('div', 'ai-msg ' + (role === 'user' ? 'me' : 'bot'));
    wrap.append(el('span', 'ai-who', role === 'user' ? 'Vy' : 'Asistent'));
    if (role === 'user') wrap.append(el('p', null, text)); else wrap.append(render(text));
    log.append(wrap);
    return wrap;
  }
  function paint() {
    log.replaceChildren();
    conv.forEach(function (m) { bubble(m.role, m.text); });
    sugg.hidden = conv.length > 0;
    document.getElementById('ai-new').hidden = conv.length === 0;
  }
  function scrollEnd(node) { (node || log.lastElementChild || log).scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }

  function ask(q) {
    q = (q || '').trim();
    if (q.length < 2 || sendBtn.disabled) return;
    var history = conv.slice(-8);
    conv.push({ role: 'user', text: q }); store();
    sugg.hidden = true; document.getElementById('ai-new').hidden = false;
    var mine = bubble('user', q);
    var wait = el('div', 'ai-msg bot wait'); wait.append(el('span', 'ai-who', 'Asistent'), el('p', 'ai-typing', 'Hľadám v údajoch o liekoch…'));
    log.append(wait); scrollEnd(mine);
    inp.value = ''; autosize(); sendBtn.disabled = true; inp.setAttribute('aria-busy', 'true');
    fetch('/api/asistent', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q: q, kod: kod, history: history }) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j }; }); })
      .then(function (res) {
        wait.remove();
        if (res.s === 200 && res.j.answer) {
          conv.push({ role: 'assistant', text: res.j.answer }); store();
          scrollEnd(bubble('assistant', res.j.answer));
        } else {
          conv.pop(); store();
          var err = el('div', 'ai-msg bot err');
          err.append(el('span', 'ai-who', 'Asistent'), el('p', null, res.j.error || (res.s === 404 || res.s === 405 ? 'Asistent sa práve spúšťa. Skúste to prosím neskôr.' : 'Asistent teraz neodpovedá. Skúste to prosím o chvíľu.')));
          log.append(err); inp.value = q;
        }
      })
      .catch(function () { wait.remove(); conv.pop(); store(); log.append(el('p', 'form-msg err', 'Nepodarilo sa spojiť so serverom. Skontrolujte pripojenie.')); inp.value = q; })
      .then(function () { sendBtn.disabled = false; inp.removeAttribute('aria-busy'); inp.focus(); });
  }
  function autosize() { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 180) + 'px'; }

  form.addEventListener('submit', function (e) { e.preventDefault(); ask(inp.value); });
  inp.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(inp.value); } });
  inp.addEventListener('input', autosize);
  sugg.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) ask(b.textContent); });
  document.getElementById('ai-new').addEventListener('click', function () {
    conv = []; kod = null; store(); paint(); if (ctxEl) ctxEl.hidden = true;
    history.replaceState(null, '', location.pathname); inp.focus();
  });

  if (kod && ctxEl) {
    ctxEl.hidden = false;
    fetch('/data.json').then(function (r) { return r.json(); }).then(function (d) {
      d.groups.forEach(function (g) { g.i.forEach(function (it) { if (it[0] === kod) ctxEl.querySelector('b').textContent = it[1] + ' (' + it[2] + ')'; }); });
    }).catch(function () {});
  }
  paint();
  var q0 = params.get('q');
  if (q0) { history.replaceState(null, '', location.pathname + (kod ? '?kod=' + kod : '')); ask(q0); }
})();
