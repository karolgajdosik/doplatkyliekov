// DOČASNÉ: overenie dostupnosti národného portálu čakacích listín z Cloudflare (zmazať po sonde)
export async function onRequestGet({ request }) {
  const u = new URL(request.url).searchParams.get('u') || 'https://ecakacielistiny.npz.sk/';
  if (!/^https:\/\/ecakacielistiny\.npz\.sk\//.test(u)) return new Response('no', { status: 400 });
  const t0 = Date.now();
  try {
    const r = await fetch(u, { headers: { 'user-agent': 'doplatkyliekov.sk (kontakt@doplatkyliekov.sk)' } });
    const b = await r.text();
    return new Response(JSON.stringify({ status: r.status, ms: Date.now() - t0, len: b.length, ct: r.headers.get('content-type'), body: b.slice(0, 20000) }), { headers: { 'content-type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e), ms: Date.now() - t0 }), { headers: { 'content-type': 'application/json' } });
  }
}
