/* Vyhľadávanie liekov s toleranciou preklepov (úvodná stránka a vkladaná kalkulačka).
   window.Hladaj.find(items, term, opts) → zoradené položky.
   items: [{ kod, name, subst, ... }]; najprv presná zhoda podľa podreťazca (aj kód ŠÚKL),
   ak je výsledkov málo, doplní podobné názvy: „konkor“ → Concor, „glukofag“ → Glucophage, „kontroloc“ → Controloc. */
(function () {
  'use strict';
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  // zjednodušená výslovnosť: ph→f, c→k (okrem ch), y→i, w→v, x→ks, qu→kv, th→t, zdvojené písmená, koncové e
  function phon(word) {
    var w = norm(word).replace(/[^a-z0-9]/g, '');
    if (!w || /^\d+$/.test(w)) return w;
    w = w.replace(/ph/g, 'f').replace(/th/g, 't').replace(/qu/g, 'kv').replace(/ch/g, '#').replace(/[cq]/g, 'k').replace(/#/g, 'ch')
      .replace(/x/g, 'ks').replace(/w/g, 'v').replace(/y/g, 'i').replace(/(.)\1+/g, '$1');
    if (w.length > 4) w = w.replace(/e$/, '');
    return w;
  }
  // Damerau-Levenshtein (s výmenou susedných písmen), s predčasným ukončením nad limit
  function dist(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev2 = null, prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i]; var rowMin = i;
      for (j = 1; j <= b.length; j++) {
        var c = a[i - 1] === b[j - 1] ? 0 : 1;
        var v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, prev2[j - 2] + 1);
        cur[j] = v; if (v < rowMin) rowMin = v;
      }
      if (rowMin > max) return max + 1;
      prev2 = prev; prev = cur;
    }
    return prev[b.length];
  }
  function allowed(len) { return len <= 3 ? 0 : len <= 7 ? 1 : 2; }
  // najlepšia zhoda slova so začiatkom niektorého slova názvu (prípadne celým slovom)
  function wordScore(w, tokens) {
    var best = 99, lim = allowed(w.length);
    for (var t = 0; t < tokens.length; t++) {
      var tok = tokens[t];
      if (tok.indexOf(w) === 0) return 0;
      if (lim) {
        var d = Math.min(dist(w, tok.slice(0, w.length), lim), dist(w, tok, lim));
        if (d < best) best = d;
      }
    }
    return best <= lim ? best : 99;
  }
  function split(s) { return norm(s).split(/[^a-z0-9]+/).filter(Boolean).map(phon); }
  function tokens(x) {
    if (!x._ph) x._ph = [split(x.name), split(x.subst || '')];
    return x._ph;
  }
  function find(items, term, opts) {
    opts = opts || {};
    var limit = opts.limit || 30, t = norm(String(term || '').trim());
    if (t.length < 2) return [];
    var words = t.split(/\s+/).filter(Boolean), code = /^[0-9a-z]{5}$/.test(t) ? t.toUpperCase() : null;
    var exact = [], seen = {};
    items.forEach(function (x) {
      if (!x._key) x._key = norm(x.name + ' ' + (x.subst || '')) + ' ' + String(x.kod).toLowerCase();
      if ((code && x.kod === code) || words.every(function (w) { return x._key.indexOf(w) >= 0; })) { x._fuzzy = false; exact.push(x); seen[x.kod] = 1; }
    });
    var first = words[0];
    exact.sort(function (a, b) {
      return (code ? (b.kod === code) - (a.kod === code) : 0) ||
        ((norm(a.name).indexOf(first) === 0 ? 0 : 1) - (norm(b.name).indexOf(first) === 0 ? 0 : 1)) || a.name.localeCompare(b.name, 'sk');
    });
    if (exact.length >= 3 || opts.exactOnly) return exact.slice(0, limit);
    var pw = words.map(phon).filter(Boolean), fuzzy = [];
    if (!pw.length || pw.every(function (w) { return w.length < 3; })) return exact.slice(0, limit);
    items.forEach(function (x) {
      if (seen[x.kod]) return;
      var tk = tokens(x), sc = 0;
      for (var i = 0; i < pw.length; i++) {
        var s = wordScore(pw[i], tk[0]);
        if (s === 99) { s = wordScore(pw[i], tk[1]); if (s === 99) return; s += 0.5; } // zhoda len v účinnej látke až za zhodou v názve
        sc += s;
      }
      fuzzy.push([sc, x]);
    });
    fuzzy.sort(function (a, b) { return a[0] - b[0] || a[1].name.localeCompare(b[1].name, 'sk'); });
    return exact.concat(fuzzy.map(function (f) { f[1]._fuzzy = true; return f[1]; })).slice(0, limit);
  }
  window.Hladaj = { find: find, norm: norm, phon: phon, dist: dist };
})();
