// GET /api/letak?kod=94163 – zrozumiteľné zhrnutie príbalového letáka (PIL zo ŠÚKL) pomocou Workers AI.
// Zhrnutie sa ukladá do KV (letak:<id>), aby sa ten istý leták nesumarizoval znova.
function json(obj, status = 200, cache = 'no-store') {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': cache } });
}
const MODELS = ['@cf/meta/llama-4-scout-17b-16e-instruct', '@cf/mistralai/mistral-small-3.1-24b-instruct'];
const NAMES = ['Na čo sa používa', 'Pred užitím (kedy neužívať, upozornenia)', 'Ako užívať', 'Možné vedľajšie účinky', 'Ako uchovávať'];
const cache = {};
async function asset(env, request, path) {
  if (cache[path]) return cache[path];
  const r = await env.ASSETS.fetch(new Request(new URL(path, request.url)));
  if (!r.ok) return null;
  cache[path] = await r.json();
  return cache[path];
}
export async function onRequestGet({ request, env }) {
  const kod = new URL(request.url).searchParams.get('kod') || '';
  if (!/^[0-9A-Z]{4,6}$/.test(kod)) return json({ error: 'Neplatný kód lieku.' }, 400);
  const map = await asset(env, request, '/pil/map.json');
  const id = map && map[kod];
  if (!id) return json({ error: 'K tomuto lieku nemáme príbalový leták.' }, 404);
  if (env.SUBS) {
    const hit = await env.SUBS.get(`letak:${id}`, 'json');
    if (hit) return json(hit, 200, 'public, max-age=86400');
  }
  const shard = await asset(env, request, `/pil/${Number(id) % 64}.json`);
  const doc = shard && shard[id];
  if (!doc) return json({ error: 'Leták sa nepodarilo načítať.' }, 404);
  if (!env.AI) return json({ error: 'Zhrnutie sa práve spúšťa. Skúste to prosím neskôr.' }, 503);
  const parts = doc.s.map((t, i) => t ? `### ${NAMES[i]}\n${t}` : '').filter(Boolean).join('\n\n');
  const sys = `Zhrni oficiálnu písomnú informáciu pre používateľa (príbalový leták) lieku pre bežného človeka po slovensky.
Použi presne tieto nadpisy v tvare "## Nadpis": ${NAMES.map((n) => '## ' + n).join(', ')}.
Pod každým nadpisom 2 – 5 krátkych odrážok jednoduchými slovami. Pri vedľajších účinkoch uveď najčastejšie a tie, pri ktorých treba ihneď k lekárovi.
Používaj VÝLUČNE informácie z letáka, nič nepridávaj ani neodporúčaj nad jeho rámec. Dávkovanie uveď len tak, ako je v letáku, a dodaj, že rozhoduje lekár.
Ak časť v letáku chýba, napíš pod nadpis "Pozrite celý leták."`;
  let text = '', model = '';
  for (const m of MODELS) {
    try {
      const res = await env.AI.run(m, { messages: [{ role: 'system', content: sys }, { role: 'user', content: `Liek: ${doc.t}\n\n${parts}` }], max_tokens: 1100, temperature: 0.1 });
      text = String((res && (res.response ?? res.choices?.[0]?.message?.content)) || '').trim();
      if (text) { model = m; break; }
    } catch (e) { /* ďalší model */ }
  }
  if (!text) return json({ error: 'Zhrnutie sa teraz nepodarilo. Skúste to prosím o chvíľu.' }, 502);
  const out = { title: doc.t, summary: text, model };
  if (env.SUBS) await env.SUBS.put(`letak:${id}`, JSON.stringify(out), { expirationTtl: 60 * 60 * 24 * 45 });
  return json(out, 200, 'public, max-age=86400');
}
