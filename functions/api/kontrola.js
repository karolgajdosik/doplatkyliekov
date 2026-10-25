// POST /api/kontrola – AI prehľad zoznamu Moje lieky: kde ušetriť, zmeny, výpadky, otázky pre lekára.
//   { items: [{ kod, d }] } → { answer, total: { pack, year } }
// Zoznam liekov neukladáme. Výpočty úspor robí server, model ich len zrozumiteľne zhrnie.
import { index, group, itemLine, eur } from './asistent.js';

const MODELS = ['@cf/meta/llama-4-scout-17b-16e-instruct', '@cf/mistralai/mistral-small-3.1-24b-instruct'];
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
}
function packCount(p) { const m = /^(tbl|cps|drg|tob|lyo)[a-z .]*?\s(\d+)/i.exec(p || ''); return m ? +m[2] : null; }
const hits = new Map();
function limited(ip) {
  const day = new Date().toISOString().slice(0, 10), h = hits.get(ip);
  if (!h || h.day !== day) { hits.set(ip, { day, n: 1 }); return false; }
  h.n += 1; if (hits.size > 5000) hits.clear();
  return h.n > 20;
}

export async function onRequestPost({ request, env }) {
  if (!env.AI) return json({ error: 'Kontrola sa práve spúšťa. Skúste to prosím neskôr.' }, 503);
  if (limited(request.headers.get('cf-connecting-ip') || 'x')) return json({ error: 'Dnes ste už spustili veľa kontrol. Skúste to prosím zajtra.' }, 429);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  const items = (Array.isArray(body.items) ? body.items : []).filter((x) => x && /^[0-9A-Z]{4,6}$/.test(String(x.kod))).slice(0, 30);
  if (!items.length) return json({ error: 'Zoznam je prázdny.' }, 400);
  const idx = await index(env, request);
  const next = /^\d{4}-\d{2}-\d{2}$/.test(idx.next || '') ? idx.next.slice(8, 10).replace(/^0/, '') + '. ' + idx.next.slice(5, 7).replace(/^0/, '') + '. ' + idx.next.slice(0, 4) : (idx.next || 'budúceho mesiaca');
  const lines = [];
  let pack = 0, year = 0, yearNow = 0;
  for (const x of items) {
    const it = idx.items.find((r) => r[0] === String(x.kod));
    if (!it) { lines.push(`- Liek s kódom ${x.kod}: už nie je v zozname liekov hradených poisťovňou.`); continue; }
    const g = await group(env, request, it[2]);
    const row = g.i.find((r) => r[0] === it[0]);
    const best = g.i[0];
    const d = +x.d > 0 && +x.d <= 20 ? +x.d : 1, ks = packCount(row[2]);
    const diff = row[3] - best[3];
    let note = '';
    if (diff > 0.005) {
      pack += diff;
      note = `NAJLACNEJŠIA ALTERNATÍVA: ${best[1]} (${best[2]}) doplatok ${eur(best[3])}, odkaz /liek/${best[8]}/; úspora ${eur(diff)} na balení`;
      if (ks) { const y = 365 * d / ks * diff; year += y; note += `, pri ${d} ks denne približne ${eur(y)} ročne`; }
    } else note = 'už patrí medzi najlacnejšie vo svojej skupine';
    if (ks && row[3] != null) yearNow += 365 * d / ks * row[3];
    lines.push(`- ${itemLine(row, next, false)}; užíva ${d} ks denne; ${note}. Skupina: ${g.s}, ${g.f}.`);
  }
  const sys = `Si asistent webu doplatkyliekov.sk. Používateľ si dal skontrolovať svoj zoznam liekov. Napíš mu po slovensky krátky prehľad (do 250 slov) presne v týchto sekciách:
## Kde môžete ušetriť
## Zmeny od ${next}
## Výpadky dodávok
## Na čo sa opýtať lekára alebo lekárnika
Pravidlá: používaj VÝLUČNE údaje z podkladov, čísla neprepočítavaj a nevymýšľaj. Celková úspora je už vypočítaná. Pri každom lieku s lacnejšou alternatívou uveď jej názov ako odkaz [Názov](/liek/...), doplatok a úsporu. Ak sekcia nemá obsah, napíš jednou vetou, že tu nie je nič. V poslednej sekcii navrhni 2 – 4 konkrétne otázky (napríklad či môže lekár predpísať liek názvom účinnej látky alebo či je vhodná lacnejšia verzia). Nehodnoť interakcie, dávkovanie ani vhodnosť liečby, nestanovuj diagnózu. Nepoužívaj propagačné výrazy. Pri liekoch na epilepsiu, štítnu žľazu a riedenie krvi pripomeň, že zmenu výrobcu treba vždy prebrať s lekárom.`;
  const ctx = `PODKLADY:\nCelková možná úspora: ${eur(pack)} na jednom nákupe všetkých liekov${year > 0 ? `, približne ${eur(year)} ročne` : ''}. Ročný doplatok teraz približne ${eur(yearNow)}.\n${lines.join('\n')}`;
  let lastErr;
  for (const model of MODELS) {
    try {
      const res = await env.AI.run(model, { messages: [{ role: 'system', content: sys }, { role: 'user', content: ctx }], max_tokens: 900, temperature: 0.2 });
      const text = String((res && (res.response ?? res.choices?.[0]?.message?.content)) || '').trim();
      if (text) return json({ answer: text, total: { pack: Math.round(pack * 100) / 100, year: Math.round(year * 100) / 100, yearNow: Math.round(yearNow * 100) / 100 }, model });
    } catch (e) { lastErr = e; }
  }
  return json({ error: 'Kontrola sa teraz nepodarila. Skúste to prosím o chvíľu.' }, 502);
}
