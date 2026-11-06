// Kto je môj lekár: zdravotné obvody z registrov samosprávnych krajov (e-VÚC), na požiadanie a s vyrovnávacou pamäťou.
//   GET /api/obvod?q=Mala            → { obce: [{ n, label, id, k }] }  (návrhy obcí zo všetkých krajov okrem Košického)
//   GET /api/obvod?k=bsk&id=…&n=Malacky&o=1  → { ulice: [[ulica, i]], amb: [[názov, odbornosť, adresa, čas, page_id, identifikátor]] }
//   o: 1 všeobecný lekár pre dospelých, 2 pre deti a dorast, 3 gynekológ, 4 zubár
// Nič o používateľovi neukladáme; e-VÚC dostane len názov obce.

const KRAJE = { bsk: 64903, ttsk: 87132, tsk: 194, nsk: 91937, zsk: 55563, bbsk: 129813, psk: 132603 };
const H = 'https://www.e-vuc.sk';
const UA = { 'user-agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)' };

function json(obj, status = 200, maxAge = 0) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': maxAge ? `public, max-age=${maxAge}` : 'no-store' }
  });
}
const ent = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
function txt(s) {
  return String(s || '').replace(/<[^>]+>/g, ' ')
    .replace(/&(#\d+|#x[0-9a-f]+|\w+);/gi, (m, e) => e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : +e.slice(1)) : (ent[e] ?? m))
    .replace(/\s+/g, ' ').trim().replace(/^[ ,.]+|[ ,.]+$/g, '');
}
async function cached(ctx, key, ttl, fn) {
  const cache = caches.default, req = new Request(key);
  const hit = await cache.match(req);
  if (hit) return hit.json();
  const val = await fn();
  if (val) ctx.waitUntil(cache.put(req, new Response(JSON.stringify(val), { headers: { 'cache-control': `public, max-age=${ttl}`, 'content-type': 'application/json' } })));
  return val;
}
async function up(url) {
  const r = await fetch(url, { headers: UA, cf: { cacheTtl: 0 } });
  if (!r.ok) throw new Error('e-VÚC ' + r.status);
  return r.text();
}

function parse(h) {
  const tbl = (h.match(/<table class="list"[\s\S]*?<\/table>/) || [''])[0];
  const ulice = [], amb = [], idx = new Map();
  let street = null;
  const re = /<tr class="data-row">([\s\S]*?)<\/tr>|<tr\s+onclick="window\.location = '([^']+)'"([\s\S]*?)<\/tr>/g;
  let m;
  while ((m = re.exec(tbl))) {
    if (m[1] != null) { street = txt((m[1].match(/<h2[^>]*>([\s\S]*?)<\/h2>/) || [])[1]); continue; }
    const body = m[3], pid = +((m[2].match(/page_id=(\d+)/) || [])[1] || 0);
    if (!idx.has(pid)) {
      const name = txt((body.match(/<a\s[^>]*>([\s\S]*?)<\/a>/) || [])[1]);
      const odb = txt((body.match(/<span class="specializacny_odbor">\(([^)]*)\)<\/span>/) || [])[1]);
      const ident = txt((body.match(/<span style="font-size:12px">([^<]*)<\/span>/) || [])[1]);
      const tds = [...body.matchAll(/<td(?:\s[^>]*)?>([\s\S]*?)<\/td>/g)].map((x) => x[1]);
      const addr = tds.map(txt).find((t) => /\d{3}\s?\d{2}\s+\S/.test(t)) || '';
      const hh = body.match(/<td style="white-space:nowrap;">([\s\S]*?)<\/td>/);
      const cas = hh ? hh[1].split(/<br\s*\/?>/).map(txt).filter(Boolean).join(', ') : '';
      idx.set(pid, amb.length);
      amb.push([name, odb, addr, cas, pid, ident]);
    }
    if (street) ulice.push([street, idx.get(pid)]);
  }
  return { ulice, amb };
}

export async function onRequestGet({ request, waitUntil }) {
  const ctx = { waitUntil };
  const u = new URL(request.url), q = (u.searchParams.get('q') || '').trim().slice(0, 40);
  try {
    if (q) {
      if (q.length < 2) return json({ obce: [] });
      const key = `https://cache.doplatkyliekov.sk/obvod-q/${encodeURIComponent(q.toLowerCase())}`;
      const obce = await cached(ctx, key, 86400 * 30, async () => {
        const res = await Promise.all(Object.entries(KRAJE).map(async ([k, pid]) => {
          try {
            const t = await up(`${H}/e-vuc/ajax-zdravotne-obvody-mesto.html?page_id=122990&term=${encodeURIComponent(q)}&current_page_id=${pid}`);
            const j = JSON.parse(t || 'null') || [];
            return j.map((x) => ({ n: x.value, label: x.label, id: String(x.mesto_id), k }));
          } catch { return []; }
        }));
        return res.flat().slice(0, 15);
      });
      return json({ obce }, 200, 3600);
    }
    const k = u.searchParams.get('k'), id = (u.searchParams.get('id') || '').replace(/\D/g, ''), n = (u.searchParams.get('n') || '').slice(0, 60);
    const o = Math.max(1, Math.min(4, +u.searchParams.get('o') || 1));
    if (!KRAJE[k] || !id || !n) return json({ error: 'Chýba obec' }, 400);
    const key = `https://cache.doplatkyliekov.sk/obvod/${k}/${id}/${o}`;
    const data = await cached(ctx, key, 86400 * 7, async () => {
      const pid = KRAJE[k];
      const qs = new URLSearchParams({ page_id: pid, odbornost: o, mesto: n, mesto_id: id, current_page_id: pid });
      const src = `${H}/${k}/zdravotnictvo/kto-je-moj-lekar-zdravotne-obvody.html?${qs}`;
      const r = parse(await up(src));
      r.zdroj = src;
      return r;
    });
    return json(data, 200, 3600);
  } catch (e) {
    return json({ error: 'Register kraja je práve nedostupný. Skúste to o chvíľu.' }, 502);
  }
}
