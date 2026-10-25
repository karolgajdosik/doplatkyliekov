// POST /api/foto – rozpozná liek z fotky balenia alebo receptu (Cloudflare Workers AI, väzba AI).
//   { img: 'data:image/jpeg;base64,…' } → { found: [{ nazov, sila, kusov }], items: [{ kod, name, pack, dop, slug, best }] }
// Fotku neukladáme; po rozpoznaní sa zahodí. Model dostane pokyn ignorovať osobné údaje.

// test 25. 10. 2026: Mistral Small 3.1 a Llama 3.2 Vision fotku prečítali správne, Llama 4 Scout a Gemma 3 vrátili chybu
const MODELS = ['@cf/mistralai/mistral-small-3.1-24b-instruct', '@cf/meta/llama-3.2-11b-vision-instruct', '@cf/meta/llama-4-scout-17b-16e-instruct'];
const TIMEOUT = 30000;
function withTimeout(p, ms) { return Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms))]); }
const PROMPT = `Na fotke je balenie lieku, príbalový leták alebo lekársky recept zo Slovenska.
Nájdi na nej názvy liekov. Pre každý liek vypíš obchodný názov (napr. Concor, Controloc, Xarelto), silu (napr. 10 mg) a počet kusov v balení, ak je uvedený.
Ignoruj meno pacienta, rodné číslo, adresu, lekára, poisťovňu a iné osobné údaje – nikdy ich nevypisuj.
Odpovedz IBA platným JSON bez ďalšieho textu v tvare:
{"lieky":[{"nazov":"Concor","sila":"10 mg","kusov":30}]}
Ak na fotke nie je žiadny liek, odpovedz {"lieky":[]}.`;

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
}
function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }

const cache = {};
async function asset(env, request, path) {
  if (cache[path]) return cache[path];
  const r = await env.ASSETS.fetch(new Request(new URL(path, request.url)));
  if (!r.ok) throw new Error('chýba ' + path);
  cache[path] = await r.json();
  return cache[path];
}

const hits = new Map();
function limited(ip) {
  const day = new Date().toISOString().slice(0, 10);
  const h = hits.get(ip);
  if (!h || h.day !== day) { hits.set(ip, { day, n: 1 }); return false; }
  h.n += 1;
  if (hits.size > 5000) hits.clear();
  return h.n > 30;
}

function parseJson(text) {
  const m = /\{[\s\S]*\}/.exec(String(text || ''));
  if (!m) return [];
  try {
    const j = JSON.parse(m[0]);
    return (Array.isArray(j.lieky) ? j.lieky : []).slice(0, 6).map((x) => ({
      nazov: String(x.nazov || '').replace(/[^\p{L}\p{N} .,+\-/]/gu, '').trim().slice(0, 60),
      sila: String(x.sila || '').replace(/[^\p{L}\p{N} .,/%]/gu, '').trim().slice(0, 30),
      kusov: Number.isFinite(+x.kusov) && +x.kusov > 0 && +x.kusov < 1000 ? Math.round(+x.kusov) : null,
    })).filter((x) => x.nazov.length >= 3);
  } catch { return []; }
}

async function recognize(env, img, only) {
  let lastErr;
  for (const model of (only ? [only] : MODELS.slice(0, 2))) {
    try {
      if (model.includes('llama-3.2-11b-vision')) { try { await env.AI.run(model, { prompt: 'agree' }); } catch { /* licencia už prijatá */ } }
      const res = await withTimeout(env.AI.run(model, {
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }, { type: 'image_url', image_url: { url: img } }] }],
        max_tokens: 300, temperature: 0,
      }), TIMEOUT);
      const text = res && (res.response ?? res.result?.response ?? res.choices?.[0]?.message?.content);
      const out = parseJson(typeof text === 'string' ? text : JSON.stringify(text));
      if (out.length || text) return { found: out, model };
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('bez odpovede');
}

async function match(env, request, found) {
  const idx = await asset(env, request, '/ai/search.json');
  const items = [];
  const seen = new Set();
  for (const f of found) {
    const words = norm(f.nazov).split(/[^a-z0-9]+/).filter((w) => w.length >= 3);
    if (!words.length) continue;
    const num = (norm(f.sila).match(/\d+(?:[.,]\d+)?/) || [''])[0].replace(',', '.');
    const scored = [];
    idx.items.forEach((it, i) => {
      const n = norm(it[1]);
      const subst = norm(idx.groups[it[2]][0]);
      let sc = 0;
      for (const w of words) if (n.includes(w)) sc += n.startsWith(w) ? 3 : 2; else if (subst.includes(w)) sc += 1;
      if (!sc) return;
      if (num && new RegExp('(^|[^0-9.])' + num.replace('.', '\\.') + '([^0-9]|$)').test(n + ' ' + norm(idx.groups[it[2]][1]))) sc += 2;
      scored.push([sc, i]);
    });
    scored.sort((a, b) => b[0] - a[0] || idx.items[a[1]][1].length - idx.items[b[1]][1].length);
    const best = scored.length ? scored[0][0] : 0;
    for (const [sc, i] of scored) {
      if (sc < best || items.length >= 8) break;
      const it = idx.items[i];
      if (seen.has(it[0])) continue;
      seen.add(it[0]);
      const shard = await asset(env, request, `/ai/g/${Math.floor(it[2] / 100)}.json`);
      const g = shard[String(it[2])];
      const row = g.i.find((r) => r[0] === it[0]);
      if (!row) continue;
      const cheapest = g.i[0];
      const packOk = f.kusov ? new RegExp('(^|[^0-9])' + f.kusov + '\\s*x|' + '\\b' + f.kusov + '\\s*\\(').test(row[2]) : false;
      items.push({ kod: row[0], name: row[1], pack: row[2], dop: row[3], slug: row[8], pack_ok: packOk,
        best: cheapest && cheapest[0] !== row[0] && row[3] - cheapest[3] > 0.005 ? { name: cheapest[1], dop: cheapest[3], slug: cheapest[8] } : null });
    }
  }
  items.sort((a, b) => (b.pack_ok ? 1 : 0) - (a.pack_ok ? 1 : 0));
  return items.slice(0, 6);
}

export async function onRequestPost({ request, env }) {
  if (!env.AI) return json({ error: 'Rozpoznávanie fotiek sa práve spúšťa. Skúste to prosím neskôr.' }, 503);
  const len = +(request.headers.get('content-length') || 0);
  if (len > 3_000_000) return json({ error: 'Fotka je príliš veľká.' }, 413);
  if (limited(request.headers.get('cf-connecting-ip') || 'x')) return json({ error: 'Dnes ste už poslali veľa fotiek. Skúste to prosím zajtra.' }, 429);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  const img = String(body.img || '');
  if (!/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(img) || img.length > 2_800_000) return json({ error: 'Neplatná fotka.' }, 400);
  try {
    const t0 = Date.now();
    const only = MODELS.includes(body.m) ? body.m : null;
    const { found, model } = await recognize(env, img, only);
    const items = found.length ? await match(env, request, found) : [];
    return json({ found, items, model, ms: Date.now() - t0 });
  } catch (e) {
    return json({ error: 'Fotku sa teraz nepodarilo spracovať. Skúste to prosím o chvíľu alebo napíšte názov lieku.', detail: body.m ? String(e && e.message || e).slice(0, 300) : undefined }, 502);
  }
}
