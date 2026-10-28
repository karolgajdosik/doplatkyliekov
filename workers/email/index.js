// Cloudflare Email Worker: e-mail na lieky@doplatkyliekov.sk s názvami liekov → odpoveď s doplatkami a lacnejšími alternatívami.
// Pri nasadení sa pred tento súbor pripojí site/hladaj.js (vyhľadávanie s preklepmi, window = globalThis).
// E-mail neukladáme; v KV (väzba SUBS) je len denné počítadlo podľa odtlačku adresy (proti zneužitiu).
import { EmailMessage } from 'cloudflare:email';

const SITE = 'https://doplatkyliekov.sk';
const FROM = 'lieky@doplatkyliekov.sk';
const DAILY = 20;
let data = null, dataAt = 0;
const shards = {};

async function loadData() {
  if (data && Date.now() - dataAt < 6 * 3600e3) return data;
  const j = await (await fetch(SITE + '/ai/search.json', { cf: { cacheTtl: 3600 } })).json();
  data = { platnost: j.platnost, items: j.items.map((it) => ({ kod: it[0], name: it[1], gi: it[2], subst: j.groups[it[2]][0], f: j.groups[it[2]][1] })) };
  dataAt = Date.now();
  return data;
}
async function group(gi) {
  const n = Math.floor(gi / 100);
  if (!shards[n]) shards[n] = fetch(`${SITE}/ai/g/${n}.json`, { cf: { cacheTtl: 3600 } }).then((r) => r.json());
  return (await shards[n])[String(gi)];
}
const eur = (n) => (n == null ? '–' : n.toFixed(2).replace('.', ',') + ' €');

// --- čítanie e-mailu (predmet + text bez citácie a podpisu) ---
function decodeWords(s) {
  return s.replace(/=\?([^?]+)\?([BQ])\?([^?]*)\?=/gi, (_, cs, enc, txt) => {
    try {
      const bytes = enc.toUpperCase() === 'B' ? Uint8Array.from(atob(txt), (c) => c.charCodeAt(0))
        : Uint8Array.from(txt.replace(/_/g, ' ').replace(/=([0-9A-F]{2})/gi, (m, h) => String.fromCharCode(parseInt(h, 16))), (c) => c.charCodeAt(0));
      return new TextDecoder(cs).decode(bytes);
    } catch { return txt; }
  });
}
function decodeBody(body, enc, charset) {
  let bytes;
  if (/base64/i.test(enc)) { try { bytes = Uint8Array.from(atob(body.replace(/\s+/g, '')), (c) => c.charCodeAt(0)); } catch { bytes = new TextEncoder().encode(body); } }
  else if (/quoted-printable/i.test(enc)) {
    const s = body.replace(/=\r?\n/g, '');
    const arr = []; for (let i = 0; i < s.length; i++) { if (s[i] === '=' && /^[0-9A-F]{2}$/i.test(s.substr(i + 1, 2))) { arr.push(parseInt(s.substr(i + 1, 2), 16)); i += 2; } else arr.push(s.charCodeAt(i) & 255); }
    bytes = Uint8Array.from(arr);
  } else bytes = Uint8Array.from(body, (c) => c.charCodeAt(0) & 255);
  try { return new TextDecoder(charset || 'utf-8').decode(bytes); } catch { return new TextDecoder().decode(bytes); }
}
function headersOf(part) {
  const h = {}; const head = part.split(/\r?\n\r?\n/)[0].replace(/\r?\n[ \t]+/g, ' ');
  for (const line of head.split(/\r?\n/)) { const m = /^([\w-]+):\s*(.*)$/.exec(line); if (m) h[m[1].toLowerCase()] = m[2]; }
  return h;
}
export function plainText(raw) {
  const h = headersOf(raw), ct = h['content-type'] || 'text/plain';
  const bodyOf = (p) => p.split(/\r?\n\r?\n/).slice(1).join('\n\n');
  const bnd = /boundary="?([^";]+)"?/i.exec(ct);
  if (bnd) {
    const parts = raw.split('--' + bnd[1]).slice(1, -1);
    let html = '';
    for (const p of parts) {
      const ph = headersOf(p.replace(/^\r?\n/, '')), pct = ph['content-type'] || '';
      if (/multipart\//i.test(pct)) { const t = plainText(p.replace(/^\r?\n/, '')); if (t) return t; }
      const cs = (/charset="?([^";]+)"?/i.exec(pct) || [])[1];
      if (/text\/plain/i.test(pct)) return decodeBody(bodyOf(p.replace(/^\r?\n/, '')), ph['content-transfer-encoding'], cs);
      if (/text\/html/i.test(pct) && !html) html = decodeBody(bodyOf(p.replace(/^\r?\n/, '')), ph['content-transfer-encoding'], cs);
    }
    return html.replace(/<br\s*\/?>|<\/p>|<\/div>/gi, '\n').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ');
  }
  return decodeBody(bodyOf(raw), h['content-transfer-encoding'], (/charset="?([^";]+)"?/i.exec(ct) || [])[1]);
}
export function queriesOf(subject, text) {
  const lines = [];
  for (const line of String(text || '').split(/\r?\n/)) {
    const t = line.trim();
    if (/^(--|__|>|On .* wrote:|Dňa .* napísal|Od:|From:|Odoslané z|Sent from|S pozdravom|S úctou|Pekný deň|Ďakujem|Dakujem|Vďaka|Díky)/i.test(t)) break;
    if (t) lines.push(t);
  }
  const subj = String(subject || '').replace(/^(re|fw|fwd|aw):\s*/i, '').trim();
  const cand = [subj, ...lines].join('\n').split(/[\n,;+]+|\s+(?:a|aj|alebo|and)\s+/i).map((s) => s.replace(/^(dobr[ýy] de[ňn]|ahoj|zdrav[ií]m|pros[ií]m|ďakujem|dakujem)[\s,!.]*/i, '').trim())
    .filter((s) => s.length >= 3 && s.length <= 60 && /\p{L}{3}/u.test(s) && !/^(s pozdravom|pozdrav|dakujem|ďakujem)/i.test(s));
  return [...new Set(cand)].slice(0, 5);
}

// --- odpoveď ---
export async function answer(qs) {
  const d = await loadData();
  const out = [];
  for (const q of qs) {
    const hits = globalThis.Hladaj.find(d.items, q, { limit: 12 });
    if (!hits.length) { if (qs.length === 1 || !out.length) out.push(`„${q}“: tento liek sme nenašli. Skúste názov z krabičky, napríklad „Concor 10 mg“.`); continue; }
    const shown = [], seenG = new Set();
    for (const h of hits) { if (seenG.has(h.gi)) continue; seenG.add(h.gi); shown.push(h); if (shown.length >= 3) break; }
    out.push(`Hľadali ste „${q}“:`);
    for (const h of shown) {
      const g = await group(h.gi); if (!g) continue;
      const me = g.i.find((r) => r[0] === h.kod); if (!me) continue;
      const cheaper = g.i.filter((r) => r[3] != null && r[0] !== me[0] && r[3] < me[3] - 0.005).slice(0, 2);
      out.push(`• ${me[1]} (${me[2]}): doplatok ${eur(me[3])}`);
      if (cheaper.length) cheaper.forEach((r) => out.push(`    lacnejšie: ${r[1]} – ${eur(r[3])} (o ${eur(me[3] - r[3])} menej)`));
      else out.push(me[3] < 0.005 ? '    tento liek je bez doplatku' : '    patrí medzi najlacnejšie vo svojej skupine');
      out.push(`    ${SITE}/liek/${me[8]}/`);
    }
    out.push('');
  }
  return { text: out.join('\n').trim(), platnost: d.platnost };
}
function b64(str) { const bytes = new TextEncoder().encode(str); let s = ''; for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s); }
function wrap76(s) { return s.replace(/.{1,76}/g, '$&\r\n'); }
export function mime({ to, subject, text, inReplyTo }) {
  const id = `<${crypto.randomUUID()}@doplatkyliekov.sk>`;
  return [
    `From: doplatkyliekov.sk <${FROM}>`, `To: ${to}`, `Subject: =?UTF-8?B?${b64(subject)}?=`, `Message-ID: ${id}`,
    inReplyTo ? `In-Reply-To: ${inReplyTo}` : '', inReplyTo ? `References: ${inReplyTo}` : '',
    `Date: ${new Date().toUTCString()}`, 'MIME-Version: 1.0', 'Auto-Submitted: auto-replied',
    'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: base64', '', wrap76(b64(text)),
  ].filter((l, i) => l !== '' || i > 8).join('\r\n');
}
async function fingerprint(addr) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(addr.toLowerCase()));
  return [...new Uint8Array(d)].slice(0, 8).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export default {
  async email(message, env) {
    const from = message.from || '';
    const auto = message.headers.get('auto-submitted'), prec = message.headers.get('precedence') || '';
    if (!from || /doplatkyliekov\.sk$/i.test(from) || /mailer-daemon|postmaster|no-?reply/i.test(from) || (auto && auto !== 'no') || /bulk|list|junk/i.test(prec)) return;
    if (env.SUBS) {
      const key = `mail:${await fingerprint(from)}:${new Date().toISOString().slice(0, 10)}`;
      const n = +((await env.SUBS.get(key)) || 0);
      if (n >= DAILY) return;
      await env.SUBS.put(key, String(n + 1), { expirationTtl: 2 * 86400 });
    }
    const raw = await new Response(message.raw).text();
    const subject = decodeWords(message.headers.get('subject') || '');
    const qs = queriesOf(subject, plainText(raw));
    let body;
    if (!qs.length) {
      body = 'Dobrý deň,\n\nv e-maile sme nenašli názov lieku. Napíšte do predmetu alebo do textu názov lieku z krabičky, napríklad „Concor 10 mg“. Viac liekov oddeľte čiarkou alebo každý napíšte na nový riadok.';
    } else {
      const a = await answer(qs);
      body = `Dobrý deň,\n\ntu sú doplatky podľa zoznamu Ministerstva zdravotníctva SR platného od ${a.platnost}:\n\n${a.text}\n\nUvedený doplatok je najvyšší možný; lekáreň ho môže znížiť. Lekárnik vám lacnejší liek s rovnakou látkou môže vydať, ak lekár na recepte nevyznačil, že sa nesmie zamieňať. O zmene lieku sa poraďte s lekárom alebo lekárnikom.`;
    }
    body += `\n\nS pozdravom\ndoplatkyliekov.sk – porovnanie doplatkov za lieky\n${SITE}\n\nTúto odpoveď poslal automat. Váš e-mail neukladáme.`;
    const subj = 'Doplatky: ' + (qs.length ? qs.join(', ').slice(0, 80) : 'ako sa opýtať');
    await message.reply(new EmailMessage(FROM, from, mime({ to: from, subject: subj, text: body, inReplyTo: message.headers.get('message-id') })));
  },
};
