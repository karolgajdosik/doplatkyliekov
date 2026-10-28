// Skutočné doplatky z lekární, ktoré dobrovoľne a anonymne nahlásili používatelia z bločkov.
//   POST /api/ceny { obec, lekaren, mesiac: 'YYYY-MM', items: [{ kod, suma }] } → { ok, ulozene }
//   GET  /api/ceny?kod=94163 → { kod, n, min, median, max, obce: [{ obec, min, n }], posledne: 'YYYY-MM' }
// Neukladáme IP adresu ani nič o človeku: len liek, sumu za balenie, obec, lekáreň a mesiac.
// KV: ceny:<kód> → [{ p, o, l, m }] (najviac 300 posledných záznamov)

function json(obj, status = 200, cache = 'no-store') {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': cache } });
}
const hits = new Map();
function limited(ip) {
  const day = new Date().toISOString().slice(0, 10), h = hits.get(ip);
  if (!h || h.day !== day) { hits.set(ip, { day, n: 1 }); return false; }
  h.n += 1; if (hits.size > 5000) hits.clear();
  return h.n > 8;
}
let idx = null;
async function prices(env, request) {
  if (!idx) {
    const r = await env.ASSETS.fetch(new Request(new URL('/ai/search.json', request.url)));
    const j = await r.json();
    idx = { items: new Map(j.items.map((it) => [it[0], it[2]])), shards: {} };
  }
  return idx;
}
async function maxDop(env, request, kod) {
  const ix = await prices(env, request);
  const gi = ix.items.get(kod);
  if (gi == null) return null;
  const n = Math.floor(gi / 100);
  if (!ix.shards[n]) {
    const r = await env.ASSETS.fetch(new Request(new URL(`/ai/g/${n}.json`, request.url)));
    ix.shards[n] = await r.json();
  }
  const row = ix.shards[n][String(gi)].i.find((r) => r[0] === kod);
  return row ? row[3] : null;
}
const clean = (v, n) => String(v || '').replace(/[^\p{L}\p{N} .,\-]/gu, '').replace(/\s+/g, ' ').trim().slice(0, n);
function titleCase(s) { return s.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase()); }

export async function onRequestPost({ request, env }) {
  if (!env.SUBS) return json({ error: 'Služba sa práve spúšťa.' }, 503);
  if (limited(request.headers.get('cf-connecting-ip') || 'x')) return json({ error: 'Dnes ste už poslali veľa príspevkov. Ďakujeme!' }, 429);
  let b;
  try { b = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  const obec = titleCase(clean(b.obec, 40)), lekaren = clean(b.lekaren, 60);
  const now = new Date(), cur = now.toISOString().slice(0, 7);
  const prev = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1)).toISOString().slice(0, 7);
  const mesiac = [cur, prev].includes(String(b.mesiac)) ? String(b.mesiac) : cur;
  if (obec.length < 2) return json({ error: 'Doplňte obec, kde je lekáreň.' }, 400);
  const items = (Array.isArray(b.items) ? b.items : []).slice(0, 15);
  let saved = 0;
  for (const it of items) {
    const kod = String(it.kod || '').toUpperCase();
    const p = Math.round(Number(it.suma) * 100) / 100;
    if (!/^[0-9A-Z]{4,6}$/.test(kod) || !Number.isFinite(p) || p < 0) continue;
    const mx = await maxDop(env, request, kod);
    if (mx == null || p > mx + 0.05) continue; // doplatok v lekárni nemôže byť vyšší ako maximálny podľa zoznamu
    const key = `ceny:${kod}`;
    const list = (await env.SUBS.get(key, 'json')) || [];
    list.push({ p, o: obec, l: lekaren, m: mesiac });
    await env.SUBS.put(key, JSON.stringify(list.slice(-300)));
    saved++;
  }
  return json({ ok: true, ulozene: saved });
}

export async function onRequestGet({ request, env }) {
  if (!env.SUBS) return json({ n: 0 }, 200);
  const kod = (new URL(request.url).searchParams.get('kod') || '').toUpperCase();
  if (!/^[0-9A-Z]{4,6}$/.test(kod)) return json({ error: 'Neplatný kód.' }, 400);
  const now = new Date();
  const from = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 2, 1)).toISOString().slice(0, 7); // posledné 3 mesiace
  const list = ((await env.SUBS.get(`ceny:${kod}`, 'json')) || []).filter((x) => x.m >= from);
  if (!list.length) return json({ kod, n: 0 }, 200, 'public, max-age=600');
  const ps = list.map((x) => x.p).sort((a, b) => a - b);
  const byObec = {};
  for (const x of list) { const o = byObec[x.o] || (byObec[x.o] = { obec: x.o, min: x.p, n: 0, lekaren: x.l }); o.n++; if (x.p < o.min) { o.min = x.p; o.lekaren = x.l; } }
  const obce = Object.values(byObec).sort((a, b) => b.n - a.n || a.min - b.min).slice(0, 8);
  return json({ kod, n: list.length, min: ps[0], max: ps[ps.length - 1], median: ps[Math.floor(ps.length / 2)], obce, posledne: list[list.length - 1].m }, 200, 'public, max-age=600');
}
