// Cloudflare Worker: pripomienky užívania liekov (Web Push) presne v nastavený čas.
// Plánovač Cloudflare ho spúšťa každú minútu (cron "* * * * *"). Číta rovnaké KV ako stránka (väzba SUBS):
//   doses:index → { id: { t: ['08:00', …], z: 'Europe/Bratislava' } }   (staršie záznamy: { id: ['08:00', …] })
//   push:<id>   → { sub, doses: [{ k, t, d, w }], tz, notified: { dose: { '<dátum> <čas> <kód> <meno>': 1 } } }
// Pripomienku pošle v danú minútu; ak by nejaké spustenie vypadlo, dobehne ju o 3 – 15 minút neskôr
// (dovtedy sa zápis o odoslaní v KV už rozšíri, takže sa nepošle dvakrát).
// Šifrovanie podľa RFC 8291 (aes128gcm) a podpis VAPID (RFC 8292) cez WebCrypto, bez knižníc.
// Nasadzuje .github/workflows/worker.yml.

const VAPID_PUBLIC = 'BIMBi6qoRml0DsWvgoUVItYTsgvdaAaOOjiFtsdlcd04L4qFCw7frmMeUYVVzuk3iirtULNrZH-STHGsN0RUCSw';
const VAPID_SUB = 'mailto:kontakt@doplatkyliekov.sk';
const SITE = 'https://doplatkyliekov.sk';
const CATCH_UP = [3, 15]; // minúty: dobehnutie vynechaných
const TTL = 3600;

const te = new TextEncoder();
export function b64uDecode(s) {
  s = String(s).trim().replace(/-/g, '+').replace(/_/g, '/').replace(/=+$/, '');
  const bin = atob(s + '='.repeat((4 - (s.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
export function b64uEncode(buf) {
  const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

// ---------- VAPID ----------
let signKey = null;
async function vapidKey(priv) {
  if (signKey) return signKey;
  const pub = b64uDecode(VAPID_PUBLIC);
  const d = b64uDecode(priv);
  if (d.length !== 32) throw new Error('VAPID_PRIVATE_KEY nemá 32 bajtov');
  signKey = await crypto.subtle.importKey('jwk', {
    kty: 'EC', crv: 'P-256', d: b64uEncode(d), x: b64uEncode(pub.slice(1, 33)), y: b64uEncode(pub.slice(33, 65)), ext: true,
  }, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  return signKey;
}
export async function vapidHeader(endpoint, priv, now = Date.now()) {
  const aud = new URL(endpoint).origin;
  const enc = (o) => b64uEncode(te.encode(JSON.stringify(o)));
  const unsigned = enc({ typ: 'JWT', alg: 'ES256' }) + '.' + enc({ aud, exp: Math.floor(now / 1000) + 12 * 3600, sub: VAPID_SUB });
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, await vapidKey(priv), te.encode(unsigned));
  return `vapid t=${unsigned}.${b64uEncode(sig)}, k=${VAPID_PUBLIC}`;
}

// ---------- šifrovanie aes128gcm ----------
async function hkdf(salt, ikm, info, len) {
  const k = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, k, len * 8));
}
export async function encrypt(p256dh, auth, plaintext) {
  const uaPub = b64uDecode(p256dh), authSecret = b64uDecode(auth);
  const eph = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', eph.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', uaPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, eph.privateKey, 256));
  const ikm = await hkdf(authSecret, shared, concat(te.encode('WebPush: info\0'), uaPub, asPub), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, te.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, te.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, concat(plaintext, new Uint8Array([2]))));
  const head = new Uint8Array(21);
  head.set(salt, 0);
  new DataView(head.buffer).setUint32(16, 4096);
  head[20] = asPub.length;
  return concat(head, asPub, ct);
}

// vráti 'ok' | 'gone' | 'chyba <kód>'
export async function sendPush(sub, payload, priv, ttl = TTL) {
  const body = await encrypt(sub.keys.p256dh, sub.keys.auth, te.encode(JSON.stringify(payload)));
  const r = await fetch(sub.endpoint, {
    method: 'POST',
    headers: {
      Authorization: await vapidHeader(sub.endpoint, priv), TTL: String(ttl), Urgency: 'high',
      'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream',
    },
    body,
  });
  if (r.status === 404 || r.status === 410) return 'gone';
  return r.ok ? 'ok' : `chyba ${r.status} ${(await r.text()).slice(0, 120)}`;
}

// ---------- čas ----------
const fmtCache = {};
function local(date, tz) {
  const f = fmtCache[tz] || (fmtCache[tz] = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }));
  const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, min: +p.hour * 60 + +p.minute };
}
function safeTz(tz) {
  try { local(new Date(), tz); return tz; } catch { return 'Europe/Bratislava'; }
}
// vek pripomienky v minútach (0 = práve teraz) a dátum, ku ktorému patrí
export function ageOf(t, now, tz) {
  const [h, m] = t.split(':').map(Number);
  const cur = local(now, tz);
  const age = (cur.min - (h * 60 + m) + 1440) % 1440;
  return { age, date: local(new Date(now.getTime() - age * 60000), tz).date };
}
function isDue(age) { return age === 0 || (age >= CATCH_UP[0] && age < CATCH_UP[1]); }
function doseTxt(d) { return { 0.25: '¼', 0.5: '½', 0.75: '¾', 1.5: '1½' }[d] || String(d).replace('.', ','); }

// ---------- názvy liekov ----------
let names = null, namesAt = 0;
async function nameMap() {
  if (names && Date.now() - namesAt < 6 * 3600e3) return names;
  try {
    const r = await fetch(SITE + '/ai/search.json', { cf: { cacheTtl: 3600 } });
    const j = await r.json();
    names = new Map(j.items.map((it) => [it[0], it[1]]));
    namesAt = Date.now();
  } catch { names = names || new Map(); }
  return names;
}

export function buildPayloads(rec, now, map) {
  const tz = safeTz(rec.tz || 'Europe/Bratislava');
  const done = (rec.notified && rec.notified.dose) || {};
  const due = {};
  for (const x of rec.doses || []) {
    const { age, date } = ageOf(x.t, now, tz);
    const key = `${date} ${x.t} ${x.k} ${x.w || ''}`;
    if (isDue(age) && !done[key]) (due[x.t] = due[x.t] || []).push({ key, x });
  }
  return Object.keys(due).sort().map((t) => ({
    keys: due[t].map((d) => d.key),
    payload: {
      title: `Čas na liek · ${t}`,
      body: due[t].map(({ x }) => `${map.get(x.k) || x.k}: ${doseTxt(x.d)} ks` + (x.w ? ` (${x.w})` : '')).join('; ').slice(0, 220),
      url: '/moje-lieky/', tag: `dose-${t}`, dose: true,
    },
  }));
}

// rýchly predvýber podľa indexu: môže niektorá pripomienka byť práve teraz na rade?
function maybeDue(entry, now) {
  if (!entry || typeof entry !== 'object') return false;
  if (Array.isArray(entry)) return true; // starý formát bez časového pásma
  const tz = safeTz(entry.z || 'Europe/Bratislava');
  return (entry.t || []).some((t) => isDue(ageOf(t, now, tz).age));
}

export async function run(env, now = new Date()) {
  const idx = (await env.SUBS.get('doses:index', 'json')) || {};
  const ids = Object.keys(idx).filter((id) => /^[a-z0-9]{32}$/.test(id) && maybeDue(idx[id], now));
  let sent = 0, gone = 0, err = 0;
  if (!ids.length) return { sent, gone, err };
  const map = await nameMap();
  for (const id of ids) {
    try { ({ sent, gone, err } = await one(env, id, now, map, { sent, gone, err })); } catch (e) { err++; console.log('Chyba pri', id.slice(0, 6), e.message); }
  }
  return { sent, gone, err };
}

async function one(env, id, now, map, c) {
  let { sent, gone, err } = c;
  {
    const rec = await env.SUBS.get(`push:${id}`, 'json');
    if (!rec || !rec.sub) return c;
    const jobs = buildPayloads(rec, now, map);
    if (!jobs.length) return c;
    rec.notified = rec.notified || {};
    const done = rec.notified.dose = rec.notified.dose || {};
    let changed = false, isGone = false;
    for (const j of jobs) {
      const res = await sendPush(rec.sub, j.payload, env.VAPID_PRIVATE_KEY).catch((e) => 'chyba ' + e.message);
      if (res === 'gone') { isGone = true; break; }
      if (res === 'ok') { sent++; changed = true; for (const k of j.keys) done[k] = 1; } else { err++; console.log('Pripomienka neodoslaná:', res); }
    }
    if (isGone) {
      gone++;
      await env.SUBS.delete(`push:${id}`);
      const idx2 = (await env.SUBS.get('doses:index', 'json')) || {};
      delete idx2[id];
      await env.SUBS.put('doses:index', JSON.stringify(idx2));
    } else if (changed) {
      const cutoff = local(new Date(now.getTime() - 2 * 86400e3), 'UTC').date;
      rec.notified.dose = Object.fromEntries(Object.entries(done).filter(([k]) => k.slice(0, 10) >= cutoff));
      await env.SUBS.put(`push:${id}`, JSON.stringify(rec));
    }
  }
  return { sent, gone, err };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env, new Date(event.scheduledTime)).then((r) => { if (r.sent || r.err || r.gone) console.log(JSON.stringify(r)); }));
  },
  async fetch() {
    return new Response('doplatkyliekov.sk – pripomienky', { status: 404 });
  },
};
