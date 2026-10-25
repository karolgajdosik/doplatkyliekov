// GET /api/confirm?t=… – potvrdenie prihlásenia alebo zmeny zoznamu liekov.
import { ready, redirect } from '../../lib/mail.js';

export async function onRequestGet({ request, env }) {
  if (!ready(env)) return redirect('/upozornenia/chyba/');
  const t = new URL(request.url).searchParams.get('t') || '';
  if (!/^[a-f0-9]{32}$/.test(t)) return redirect('/upozornenia/chyba/');
  const email = await env.SUBS.get(`tok:${t}`);
  if (!email) return redirect('/upozornenia/chyba/');
  const rec = await env.SUBS.get(`sub:${email}`, 'json');
  if (!rec) return redirect('/upozornenia/chyba/');

  if (rec.pendingKody) {
    rec.kody = [...new Set([...(rec.kody || []), ...rec.pendingKody])].slice(0, 80);
    delete rec.pendingKody;
  }
  if ('pendingDigest' in rec) { rec.digest = rec.digest || rec.pendingDigest; delete rec.pendingDigest; }
  rec.confirmed = true;
  rec.confirmedAt = rec.confirmedAt || new Date().toISOString();
  await env.SUBS.put(`sub:${email}`, JSON.stringify(rec));   // bez expirácie
  await env.SUBS.put(`tok:${t}`, email);
  return redirect(`/upozornenia/potvrdene/?t=${t}`);
}
