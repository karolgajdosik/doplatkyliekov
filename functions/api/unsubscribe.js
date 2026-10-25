// /api/unsubscribe?t=… – odhlásenie a vymazanie údajov (GET z odkazu v e-maile, POST pre one-click odhlásenie).
import { ready, redirect } from '../../lib/mail.js';

async function remove(request, env) {
  if (!ready(env)) return false;
  const t = new URL(request.url).searchParams.get('t') || '';
  if (!/^[a-f0-9]{32}$/.test(t)) return false;
  const email = await env.SUBS.get(`tok:${t}`);
  if (email) await env.SUBS.delete(`sub:${email}`);
  await env.SUBS.delete(`tok:${t}`);
  return true;
}

export async function onRequestGet({ request, env }) {
  return redirect((await remove(request, env)) ? '/upozornenia/odhlasene/' : '/upozornenia/chyba/');
}

export async function onRequestPost({ request, env }) {
  await remove(request, env);
  return new Response('OK', { status: 200 });
}
