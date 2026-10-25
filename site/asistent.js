/* AI asistent: konverzácia (len v tejto karte prehliadača, sessionStorage), bezpečné zobrazenie odpovede. */
(function () {
  'use strict';
  var KEY = 'asistent.v1';
  var log = document.getElementById('ai-log'), form = document.getElementById('ai-form'), inp = document.getElementById('ai-q');
  var sendBtn = document.getElementById('ai-send'), sugg = document.getElementById('ai-sugg'), ctxEl = document.getElementById('ai-ctx');
  if (!log || !form) return;
  var HU = document.documentElement.lang === 'hu';
  function T(sk, hu) { return HU ? hu : sk; }
  var params = new URLSearchParams(location.search);
  var kod = /^[0-9A-Z]{4,6}$/.test(params.get('kod') || '') ? params.get('kod') : null;
  var conv = [];
  try { var s = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (s && Array.isArray(s.m)) { conv = s.m; if (!kod && s.kod) kod = s.kod; } } catch (e) { /* nič */ }
  function store() { try { sessionStorage.setItem(KEY, JSON.stringify({ m: conv.slice(-12), kod: kod })); } catch (e) { /* nič */ } }

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
  /* odkazy na lieky a stránky z podkladov odpovede */
  function nrm(t) { return (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  function shortName(n) {
    var m = /^(.*?\d+(?:[.,]\d+)?(?:\s*(?:mg|µg|mcg|g|ml|%|IU|m\.j\.))?)(?=\s|$|,)/i.exec(n);
    return (m ? m[1] : n.split(/\s+/).slice(0, 2).join(' ')).trim();
  }
  function escRe(t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function prelink(md, refs) {
    // „Názov (/liek/…/)“ → [Názov](/liek/…/) ; holá cesta → odkaz s názvom stránky
    refs.forEach(function (r) {
      var url = r[0], esc = escRe(url);
      md = md.replace(new RegExp('\\]\\(' + esc + '\\)', 'g'), '](\u0000' + url.slice(1) + ')');
      md = md.replace(new RegExp('([^\\n\\[\\]()]{0,90}?)\\s*\\(\\s*' + esc + '\\s*\\)', 'g'), function (all, before) {
        var b = before.replace(/\s+$/, ''), name = r[1];
        var nb = nrm(b), nn = nrm(name), sn = nrm(shortName(name));
        var at = nb.lastIndexOf(nn); if (at < 0) { at = nb.lastIndexOf(sn); nn = sn; }
        if (at >= 0 && at + nn.length >= nb.length - 2) return b.slice(0, at) + '[' + b.slice(at, at + nn.length) + '](' + url + ')' + b.slice(at + nn.length);
        return b + ' [' + name + '](' + url + ')';
      });
      md = md.replace(new RegExp('(^|[\\s:])' + esc + '(?=$|[\\s.,;])', 'g'), function (all, pre) { return pre + '[' + r[1] + '](' + url + ')'; });
    });
    return md.replace(/\u0000/g, '/');
  }
  function linkNames(box, refs) {
    var linked = {};
    box.querySelectorAll('a').forEach(function (a) { linked[a.getAttribute('href')] = 1; });
    // názov → lieky s týmto názvom (rôzne balenia); vyberie sa podľa „(30 ks)“ za názvom
    var byName = {};
    refs.forEach(function (r) {
      if (r[3] !== 'liek' && r[3] !== 'latka') return;
      [r[1], r[3] === 'liek' ? shortName(r[1]) : null].forEach(function (nm) {
        if (!nm || nm.length < 4) return;
        var k = nrm(nm); (byName[k] = byName[k] || { name: nm, refs: [] }).refs.push(r);
      });
    });
    var names = Object.keys(byName).sort(function (a, b) { return b.length - a.length; });
    var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT, { acceptNode: function (n) { return n.parentNode.closest('a') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; } });
    var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i], txt = nrm(node.nodeValue), best = null;
      names.forEach(function (k) {
        var at = txt.indexOf(k);
        if (at < 0) return;
        var after = node.nodeValue.charAt(at + k.length);
        if (after && /[0-9A-Za-zÀ-ž]/.test(after)) return;
        if (!best || at < best.at || (at === best.at && k.length > best.k.length)) best = { at: at, k: k };
      });
      if (!best) continue;
      var group = byName[best.k].refs, pick = null;
      var m = /^\s*\(?\s*(\d+)\s*ks/.exec(node.nodeValue.slice(best.at + best.k.length, best.at + best.k.length + 20));
      if (m) pick = group.filter(function (r) { return r[2] === m[1] + ' ks'; })[0];
      if (!pick) pick = group.filter(function (r) { return r[4]; })[0] || group[0];
      var rest = node.splitText(best.at), tail = rest.splitText(best.k.length);
      if (!linked[pick[0]]) { var a = el('a', null, rest.nodeValue); a.href = pick[0]; rest.replaceWith(a); linked[pick[0]] = 1; }
      nodes.splice(i + 1, 0, tail);
    }
  }
  function chips(box, text, refs) {
    var inText = {};
    box.querySelectorAll('a[href^="/liek/"]').forEach(function (a) { inText[a.getAttribute('href')] = 1; });
    var out = refs.filter(function (r) { return r[3] === 'liek' && (inText[r[0]] || (r[4] && nrm(text).indexOf(nrm(shortName(r[1]))) >= 0)); });
    var seen = {};
    out = out.filter(function (r) { if (seen[r[0]]) return false; seen[r[0]] = 1; return true; });
    out.sort(function (a, b) { return b[4] - a[4]; });
    if (!out.length) return;
    var wrap = el('div', 'ai-refs'); wrap.append(el('p', 'eyebrow', T(out.length === 1 ? 'Liek v odpovedi' : 'Lieky v odpovedi', 'Gyógyszerek a válaszban')));
    out.slice(0, 8).forEach(function (r) {
      var a = el('a', 'ai-ref'); a.href = r[0];
      a.append(el('span', null, r[1]), el('small', null, (r[2] ? r[2] + ' · ' : '') + T('otvoriť stránku lieku', 'gyógyszer oldala')));
      wrap.append(a);
    });
    box.append(wrap);
  }
  function bubble(role, text, refs) {
    var wrap = el('div', 'ai-msg ' + (role === 'user' ? 'me' : 'bot'));
    wrap.append(el('span', 'ai-who', role === 'user' ? T('Vy', 'Ön') : T('Asistent', 'Asszisztens')));
    if (role === 'user') wrap.append(el('p', null, text));
    else {
      refs = Array.isArray(refs) ? refs : [];
      var box = render(refs.length ? prelink(text, refs) : text);
      if (refs.length) { linkNames(box, refs); chips(box, text, refs); }
      wrap.append(box);
    }
    log.append(wrap);
    return wrap;
  }
  function paint() {
    log.replaceChildren();
    conv.forEach(function (m) { bubble(m.role, m.text, m.refs); });
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
    var wait = el('div', 'ai-msg bot wait'); wait.append(el('span', 'ai-who', T('Asistent', 'Asszisztens')), el('p', 'ai-typing', T('Hľadám v údajoch o liekoch…', 'Keresek a gyógyszeradatokban…')));
    log.append(wait); scrollEnd(mine);
    inp.value = ''; autosize(); sendBtn.disabled = true; inp.setAttribute('aria-busy', 'true');
    fetch('/api/asistent', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lang: HU ? 'hu' : 'sk', q: q, kod: kod, history: history.map(function (m) { return { role: m.role, text: m.text }; }) }) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j }; }); })
      .then(function (res) {
        wait.remove();
        if (res.s === 200 && res.j.answer) {
          conv.push({ role: 'assistant', text: res.j.answer, refs: (res.j.refs || []).slice(0, 120) }); store();
          scrollEnd(bubble('assistant', res.j.answer, res.j.refs));
        } else {
          conv.pop(); store();
          var err = el('div', 'ai-msg bot err');
          err.append(el('span', 'ai-who', T('Asistent', 'Asszisztens')), el('p', null, res.j.error || (res.s === 404 || res.s === 405 ? T('Asistent sa práve spúšťa. Skúste to prosím neskôr.', 'Az asszisztens most indul. Próbálja később.') : T('Asistent teraz neodpovedá. Skúste to prosím o chvíľu.', 'Az asszisztens most nem válaszol. Próbálja kicsit később.'))));
          log.append(err); inp.value = q;
        }
      })
      .catch(function () { wait.remove(); conv.pop(); store(); log.append(el('p', 'form-msg err', T('Nepodarilo sa spojiť so serverom. Skontrolujte pripojenie.', 'Nem sikerült kapcsolódni a szerverhez. Ellenőrizze a kapcsolatot.'))); inp.value = q; })
      .then(function () { sendBtn.disabled = false; inp.removeAttribute('aria-busy'); inp.focus(); });
  }
  function autosize() { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 180) + 'px'; }

  form.addEventListener('submit', function (e) { e.preventDefault(); ask(inp.value); });

  /* hlasové otázky (rozpoznávanie reči priamo v prehliadači) */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, mic = document.getElementById('ai-mic');
  if (SR && mic) {
    mic.hidden = false;
    form.classList.add('has-mic');
    var rec = null, listening = false;
    mic.addEventListener('click', function () {
      if (listening && rec) { rec.stop(); return; }
      rec = new SR();
      rec.lang = document.documentElement.lang === 'hu' ? 'hu-HU' : 'sk-SK';
      rec.interimResults = true; rec.maxAlternatives = 1; rec.continuous = false;
      var finalText = '';
      rec.onstart = function () { listening = true; mic.classList.add('on'); mic.setAttribute('aria-label', T('Zastaviť nahrávanie', 'Felvétel leállítása')); inp.placeholder = T('Počúvam… hovorte', 'Figyelek… beszéljen'); };
      rec.onresult = function (ev) {
        var interim = '';
        for (var i = ev.resultIndex; i < ev.results.length; i++) {
          if (ev.results[i].isFinal) finalText += ev.results[i][0].transcript; else interim += ev.results[i][0].transcript;
        }
        inp.value = (finalText + interim).trim(); autosize();
      };
      rec.onerror = function (ev) {
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') inp.placeholder = T('Mikrofón nie je povolený. Povoľte ho v nastaveniach prehliadača.', 'A mikrofon nincs engedélyezve. Engedélyezze a böngésző beállításaiban.');
      };
      rec.onend = function () {
        listening = false; mic.classList.remove('on'); mic.setAttribute('aria-label', T('Položiť otázku hlasom', 'Kérdés hanggal'));
        inp.placeholder = T('Napíšte otázku…', 'Írja be kérdését…');
        if (finalText.trim().length > 2) ask(finalText.trim());
      };
      try { rec.start(); } catch (e) { /* už beží */ }
    });
  }
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
