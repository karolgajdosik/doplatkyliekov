// POST /api/subscribe – prihlásenie na e-mailové upozornenia (s potvrdením e-mailom).
import { json, ready, sendMail, mailLayout, button, esc, SITE } from '../../lib/mail.js';

const WEEK = 7 * 24 * 3600;

export async function onRequestPost({ request, env }) {
  if (!ready(env)) return json({ error: 'Upozornenia e-mailom zatiaľ nie sú spustené.' }, 503);

  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  if (body.web) return json({ ok: true }); // pasca na roboty

  const email = String(body.email || '').trim().toLowerCase();
  if (email.length > 200 || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
    return json({ error: 'Zadajte platnú e-mailovú adresu.' }, 400);
  }
  if (body.consent !== true) return json({ error: 'Na zasielanie upozornení potrebujeme váš súhlas.' }, 400);
  const kody = [...new Set((Array.isArray(body.kody) ? body.kody : []).map(String)
    .filter((k) => /^[0-9A-Z]{4,6}$/.test(k)))].slice(0, 50);
  if (!kody.length) return json({ error: 'Vyberte aspoň jeden liek.' }, 400);

  const key = `sub:${email}`;
  const prev = await env.SUBS.get(key, 'json');
  const now = new Date().toISOString();
  const recent = (prev?.mails || []).filter((t) => Date.now() - Date.parse(t) < 864e5);
  if (recent.length >= 3) return json({ error: 'Príliš veľa pokusov. Skúste to prosím zajtra.' }, 429);

  const token = prev?.token || crypto.randomUUID().replace(/-/g, '');
  const rec = prev?.confirmed
    ? { ...prev, pendingKody: kody, mails: [...recent, now] }                 // úpravu zoznamu treba potvrdiť
    : { email, kody, token, confirmed: false, created: now, notified: {}, mails: [...recent, now] };
  rec.consentAt = now;

  const ttl = rec.confirmed ? undefined : { expirationTtl: WEEK };
  await env.SUBS.put(key, JSON.stringify(rec), ttl);
  await env.SUBS.put(`tok:${token}`, email, ttl);

  const confirmUrl = `${SITE}/api/confirm?t=${token}`;
  const ok = await sendMail(env, email,
    rec.confirmed ? 'Potvrďte zmenu zoznamu liekov' : 'Potvrďte prihlásenie na upozornenia',
    mailLayout(rec.confirmed ? 'Potvrďte zmenu zoznamu liekov' : 'Potvrďte prihlásenie na upozornenia',
      `<p style="line-height:1.6;margin:0">Dostali sme žiadosť o zasielanie upozornení na zmeny doplatkov a výpadky
      ${kody.length === 1 ? 'jedného lieku' : `${kody.length} liekov`} na adresu <strong>${esc(email)}</strong>.
      Ak ste ju poslali vy, potvrďte ju kliknutím na tlačidlo.</p>
      ${button(confirmUrl, 'Potvrdiť')}
      <p style="font-size:13px;color:#5d716b;line-height:1.5;margin:0">Ak ste o nič nežiadali, e-mail ignorujte. Bez potvrdenia vám nič posielať nebudeme a údaje do 7 dní vymažeme.</p>`));
  if (!ok) return json({ error: 'E-mail sa nepodarilo odoslať. Skúste to znova.' }, 502);
  return json({ ok: true });
}
