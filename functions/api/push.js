// POST /api/push – prihlásenie zariadenia na notifikácie (Web Push).
//   { action: 'subscribe', sub, kody, refills, consent: true } → { id }
//   { action: 'update', id, endpoint, kody, refills }          → { ok }
//   { action: 'delete', id, endpoint }                          → { ok }
// Notifikácie posiela denný skript scripts/notify.py (GitHub Actions) s privátnym kľúčom VAPID.
import { json } from '../../lib/mail.js';

const HOSTS = /^(fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com|web\.push\.apple\.com|[a-z0-9.-]+\.notify\.windows\.com|[a-z0-9.-]+\.push\.apple\.com)$/;
const KOD = /^[0-9A-Z]{4,6}$/;

async function idOf(endpoint) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint));
  return [...new Uint8Array(d)].slice(0, 16).map((b) => b.toString(16).padStart(2, '0')).join('');
}
function cleanKody(a) { return [...new Set((Array.isArray(a) ? a : []).map(String).filter((k) => KOD.test(k)))].slice(0, 50); }
function cleanRefills(o, kody) {
  const out = {};
  if (o && typeof o === 'object') for (const k of kody) if (/^\d{4}-\d{2}-\d{2}$/.test(o[k] || '')) out[k] = o[k];
  return out;
}

export async function onRequestPost({ request, env }) {
  if (!env.SUBS) return json({ error: 'Notifikácie zatiaľ nie sú spustené.' }, 503);
  let b;
  try { b = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }

  if (b.action === 'subscribe') {
    const sub = b.sub || {};
    let host = '';
    try { host = new URL(sub.endpoint).hostname; } catch { /* nič */ }
    if (!HOSTS.test(host) || !sub.keys || !sub.keys.p256dh || !sub.keys.auth) return json({ error: 'Neplatné prihlásenie zariadenia.' }, 400);
    if (b.consent !== true) return json({ error: 'Na notifikácie potrebujeme váš súhlas.' }, 400);
    const kody = cleanKody(b.kody);
    const id = await idOf(sub.endpoint);
    const prev = await env.SUBS.get(`push:${id}`, 'json');
    const rec = { sub: { endpoint: sub.endpoint, keys: { p256dh: String(sub.keys.p256dh), auth: String(sub.keys.auth) } },
      kody, refills: cleanRefills(b.refills, kody), created: prev?.created || new Date().toISOString(),
      consentAt: new Date().toISOString(), notified: prev?.notified || {} };
    await env.SUBS.put(`push:${id}`, JSON.stringify(rec));
    return json({ id });
  }

  if (!/^[a-f0-9]{32}$/.test(String(b.id || ''))) return json({ error: 'Neplatné zariadenie.' }, 400);
  const rec = await env.SUBS.get(`push:${b.id}`, 'json');
  if (!rec || rec.sub.endpoint !== b.endpoint) return json({ error: 'Zariadenie nie je prihlásené.' }, 404);

  if (b.action === 'delete') {
    await env.SUBS.delete(`push:${b.id}`);
    return json({ ok: true });
  }
  if (b.action === 'update') {
    const kody = cleanKody(b.kody);
    const refills = cleanRefills(b.refills, kody);
    if (JSON.stringify(kody) === JSON.stringify(rec.kody) && JSON.stringify(refills) === JSON.stringify(rec.refills)) return json({ ok: true, same: true });
    rec.kody = kody; rec.refills = refills;
    await env.SUBS.put(`push:${b.id}`, JSON.stringify(rec));
    return json({ ok: true });
  }
  return json({ error: 'Neznáma akcia.' }, 400);
}
