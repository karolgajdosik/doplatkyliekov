// POST /api/blocek – prečíta bloček z lekárne (Cloudflare Workers AI) a priradí položky k liekom zo zoznamu.
//   { img: 'data:image/jpeg;base64,…' } → { datum, items: [{ text, kusov, suma, liek: { kod, name, pack, pdop, dop } | null }] }
// Fotku neukladáme. Model má pokyn ignorovať osobné údaje.
import { vision, match } from './foto.js';

const PROMPT = `Na fotke je pokladničný doklad (bloček) z lekárne na Slovensku.
Vypíš dátum nákupu a všetky položky liekov. Pri každej položke uveď text názvu tak, ako je na bločku, obchodný názov lieku (napr. Concor), silu (napr. 10 mg), počet kusov/balení a sumu, ktorú zákazník zaplatil za položku (doplatok) v eurách.
Ignoruj meno, rodné číslo, číslo karty, adresu, DIČ a iné údaje. Nevymýšľaj položky, ktoré na bločku nie sú.
Odpovedz IBA platným JSON bez ďalšieho textu:
{"datum":"2026-10-21","polozky":[{"text":"CONCOR 10MG TBL FLM 30","nazov":"Concor","sila":"10 mg","kusov":1,"suma":4.12}]}
Ak to nie je bloček z lekárne, odpovedz {"datum":null,"polozky":[]}.`;

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
}
const hits = new Map();
function limited(ip) {
  const day = new Date().toISOString().slice(0, 10), h = hits.get(ip);
  if (!h || h.day !== day) { hits.set(ip, { day, n: 1 }); return false; }
  h.n += 1; if (hits.size > 5000) hits.clear();
  return h.n > 30;
}
function num(v) { const n = typeof v === 'number' ? v : parseFloat(String(v || '').replace(',', '.').replace(/[^0-9.]/g, '')); return Number.isFinite(n) && n >= 0 && n < 10000 ? Math.round(n * 100) / 100 : null; }

export async function onRequestPost({ request, env }) {
  if (!env.AI) return json({ error: 'Čítanie bločkov sa práve spúšťa. Skúste to prosím neskôr.' }, 503);
  if (+(request.headers.get('content-length') || 0) > 3_000_000) return json({ error: 'Fotka je príliš veľká.' }, 413);
  if (limited(request.headers.get('cf-connecting-ip') || 'x')) return json({ error: 'Dnes ste už poslali veľa fotiek. Skúste to prosím zajtra.' }, 429);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  const img = String(body.img || '');
  if (!/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(img) || img.length > 2_800_000) return json({ error: 'Neplatná fotka.' }, 400);
  try {
    const { text, model } = await vision(env, PROMPT, img, 900);
    const m = /\{[\s\S]*\}/.exec(text);
    let j = {};
    try { j = m ? JSON.parse(m[0]) : {}; } catch { j = {}; }
    const datum = /^\d{4}-\d{2}-\d{2}$/.test(String(j.datum || '')) ? j.datum : null;
    const pol = (Array.isArray(j.polozky) ? j.polozky : []).slice(0, 25);
    const items = [];
    for (const x of pol) {
      const nazov = String(x.nazov || x.text || '').replace(/[^\p{L}\p{N} .,+\-/]/gu, '').trim().slice(0, 60);
      if (nazov.length < 3) continue;
      const found = [{ nazov, sila: String(x.sila || '').slice(0, 30), kusov: null, kod: null }];
      const cands = await match(env, request, found);
      const best = cands[0] || null;
      items.push({ text: String(x.text || nazov).slice(0, 80), kusov: Math.max(1, Math.min(20, parseInt(x.kusov, 10) || 1)), suma: num(x.suma),
        liek: best ? { kod: best.kod, name: best.name, pack: best.pack, dop: best.dop } : null, ine: cands.slice(1, 4).map((c) => ({ kod: c.kod, name: c.name, pack: c.pack })) });
    }
    return json({ datum, items, model });
  } catch (e) {
    return json({ error: 'Bloček sa teraz nepodarilo prečítať. Skúste to prosím o chvíľu alebo pridajte lieky ručne.' }, 502);
  }
}
