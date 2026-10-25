// /api/manage – správa upozornení cez tajný odkaz z e-mailu (token).
//   GET  ?t=…                         → { email (skrátený), kody, pending }
//   POST { t, remove: [kódy] }        → odoberie lieky (ak nezostane žiadny, vymaže odber)
//   POST { t, add: [kódy] }           → pridá lieky (vlastník tokenu už e-mail potvrdil)
//   POST { t, deleteAll: true }       → zruší upozornenia a vymaže údaje
import { json, ready } from '../../lib/mail.js';

const KOD = /^[0-9A-Z]{4,6}$/;

function mask(email) {
  const [u, d] = email.split('@');
  return (u.length <= 2 ? u[0] + '*' : u.slice(0, 2) + '***') + '@' + d;
}

async function load(env, t) {
  if (!/^[a-f0-9]{32}$/.test(t || '')) return null;
  const email = await env.SUBS.get(`tok:${t}`);
  if (!email) return null;
  const rec = await env.SUBS.get(`sub:${email}`, 'json');
  return rec ? { email, rec } : null;
}

async function wipe(env, email, t) {
  await env.SUBS.delete(`sub:${email}`);
  await env.SUBS.delete(`tok:${t}`);
}

export async function onRequestGet({ request, env }) {
  if (!ready(env)) return json({ error: 'Upozornenia e-mailom zatiaľ nie sú spustené.' }, 503);
  const t = new URL(request.url).searchParams.get('t');
  const hit = await load(env, t);
  if (!hit) return json({ error: 'Odkaz je neplatný alebo upozornenia už boli zrušené.' }, 404);
  return json({ email: mask(hit.email), confirmed: !!hit.rec.confirmed, kody: hit.rec.kody || [], pending: hit.rec.pendingKody || [], digest: !!hit.rec.digest });
}

export async function onRequestPost({ request, env }) {
  if (!ready(env)) return json({ error: 'Upozornenia e-mailom zatiaľ nie sú spustené.' }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  const hit = await load(env, body.t);
  if (!hit) return json({ error: 'Odkaz je neplatný alebo upozornenia už boli zrušené.' }, 404);
  const { email, rec } = hit;
  if (body.deleteAll === true) {
    await wipe(env, email, body.t);
    return json({ deleted: true });
  }
  if (typeof body.digest === 'boolean') {
    rec.digest = body.digest;
    await env.SUBS.put(`sub:${email}`, JSON.stringify(rec));
    return json({ kody: rec.kody || [], digest: rec.digest });
  }
  const clean = (a) => (Array.isArray(a) ? a : []).map(String).filter((k) => KOD.test(k));
  let kody = rec.kody || [];
  const remove = new Set(clean(body.remove));
  if (remove.size) kody = kody.filter((k) => !remove.has(k));
  const add = clean(body.add);
  if (add.length) kody = [...new Set([...kody, ...add])].slice(0, 50);
  if (!kody.length && rec.confirmed) {
    await wipe(env, email, body.t);
    return json({ deleted: true });
  }
  rec.kody = kody;
  if (rec.pendingKody) rec.pendingKody = rec.pendingKody.filter((k) => !remove.has(k));
  await env.SUBS.put(`sub:${email}`, JSON.stringify(rec));
  return json({ kody });
}
