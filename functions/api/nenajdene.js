// POST /api/nenajdene {q, kde} – anonymné počítadlo vyhľadávaní bez výsledku (čo ľudia hľadajú a na webe chýba).
// Ukladá len upravený hľadaný výraz a počet za mesiac (KV `nf:RRRR-MM:<výraz>`, počet aj v metadátach kvôli výpisu).
// Žiadna IP adresa, čas ani iný údaj o človeku. Výrazy, ktoré by mohli byť osobným údajom (e-mail, dlhé číslo), sa zahodia.
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

export function clean(q) {
  let t = String(q || '').toLowerCase().normalize('NFC').replace(/\s+/g, ' ').trim();
  if (t.length < 3 || t.length > 40) return '';
  if (/[@\/\\:]|\d{6,}|https?|www\./.test(t)) return '';
  if (!/^[a-záäčďéíĺľňóôŕšťúýžőöüű0-9 .,+%-]+$/i.test(t)) return '';
  return t;
}

export async function onRequestPost({ request, env }) {
  if (!env.SUBS) return json({ ok: false }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ ok: false }, 400); }
  const t = clean(body.q);
  const kde = ['uvod', 'pomocky', 'dp', 'mapa'].includes(body.kde) ? body.kde : 'uvod';
  if (!t) return json({ ok: true });
  const key = `nf:${new Date().toISOString().slice(0, 7)}:${kde}:${t}`;
  const n = (+(await env.SUBS.get(key)) || 0) + 1;
  if (n <= 10000) await env.SUBS.put(key, String(n), { metadata: { n }, expirationTtl: 86400 * 400 });
  return json({ ok: true });
}
