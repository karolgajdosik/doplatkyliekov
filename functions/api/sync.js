// /api/sync – úložisko pre prepojenie zariadení (Moje lieky). Server dostáva len zašifrované dáta:
// kľúč je v QR kóde / odkaze za znakom # a na server sa nikdy neposiela.
//   GET  /api/sync?id=<32 hex>          → { data, v } alebo 404
//   PUT  { id, data, v }                → { v } ; 409 { data, v } ak medzitým zapísalo iné zariadenie
//   DELETE { id }                       → { ok }
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
}
const ID = /^[a-f0-9]{32}$/;
const TTL = 60 * 60 * 24 * 400; // záznam bez použitia zmizne po ~13 mesiacoch
const hits = new Map();
function limited(ip) {
  const day = new Date().toISOString().slice(0, 10), h = hits.get(ip);
  if (!h || h.day !== day) { hits.set(ip, { day, n: 1 }); return false; }
  h.n += 1; if (hits.size > 5000) hits.clear();
  return h.n > 300;
}

export async function onRequest({ request, env }) {
  if (!env.SUBS) return json({ error: 'Prepojenie zariadení zatiaľ nie je spustené.' }, 503);
  if (limited(request.headers.get('cf-connecting-ip') || 'x')) return json({ error: 'Príliš veľa požiadaviek.' }, 429);
  const url = new URL(request.url);
  if (request.method === 'GET') {
    const id = url.searchParams.get('id') || '';
    if (!ID.test(id)) return json({ error: 'Neplatné prepojenie.' }, 400);
    const rec = await env.SUBS.get(`sync:${id}`, 'json');
    return rec ? json(rec) : json({ error: 'Prepojenie neexistuje.' }, 404);
  }
  let b;
  try { b = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  if (!ID.test(String(b.id || ''))) return json({ error: 'Neplatné prepojenie.' }, 400);
  const key = `sync:${b.id}`;
  if (request.method === 'DELETE') { await env.SUBS.delete(key); return json({ ok: true }); }
  if (request.method !== 'PUT') return json({ error: 'Nepodporovaná metóda.' }, 405);
  const data = String(b.data || '');
  if (!/^[A-Za-z0-9_-]+$/.test(data) || data.length > 90000) return json({ error: 'Neplatné alebo príliš veľké dáta.' }, 400);
  const cur = await env.SUBS.get(key, 'json');
  if (cur && Number(b.v) !== cur.v) return json(cur, 409);
  const v = (cur ? cur.v : 0) + 1;
  await env.SUBS.put(key, JSON.stringify({ data, v, t: new Date().toISOString() }), { expirationTtl: TTL });
  return json({ v });
}
