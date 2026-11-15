// POST /api/hodnotenie {kod, v: "ano"|"nie"} – anonymné „Pomohla vám táto stránka?“ na stránke lieku.
// KV `fb:RRRR-MM:<kód lieku>:<ano|nie>` = počet (aj v metadátach). Nič o človeku sa neukladá.
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

export async function onRequestPost({ request, env }) {
  if (!env.SUBS) return json({ ok: false }, 503);
  let b;
  try { b = await request.json(); } catch { return json({ ok: false }, 400); }
  const kod = String(b.kod || '').toUpperCase();
  const v = b.v === 'ano' ? 'ano' : b.v === 'nie' ? 'nie' : '';
  if (!/^[0-9A-Z]{4,6}$/.test(kod) || !v) return json({ ok: true });
  const key = `fb:${new Date().toISOString().slice(0, 7)}:${kod}:${v}`;
  const n = (+(await env.SUBS.get(key)) || 0) + 1;
  if (n <= 10000) await env.SUBS.put(key, String(n), { metadata: { n }, expirationTtl: 86400 * 400 });
  return json({ ok: true });
}
