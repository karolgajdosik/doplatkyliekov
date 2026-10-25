// POST /api/manage-link { email } – pošle odkaz na správu upozornení.
// Odpoveď je vždy rovnaká, aby sa nedalo zistiť, či je adresa prihlásená.
import { json, ready, sendMail, mailLayout, button, SITE } from '../../lib/mail.js';

export async function onRequestPost({ request, env }) {
  if (!ready(env)) return json({ error: 'Upozornenia e-mailom zatiaľ nie sú spustené.' }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Neplatná požiadavka.' }, 400); }
  if (body.web) return json({ ok: true });
  const email = String(body.email || '').trim().toLowerCase();
  if (email.length > 200 || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return json({ error: 'Zadajte platnú e-mailovú adresu.' }, 400);

  const rec = await env.SUBS.get(`sub:${email}`, 'json');
  if (rec && rec.confirmed && rec.token) {
    const recent = (rec.mails || []).filter((t) => Date.now() - Date.parse(t) < 864e5);
    if (recent.length < 3) {
      rec.mails = [...recent, new Date().toISOString()];
      await env.SUBS.put(`sub:${email}`, JSON.stringify(rec));
      const url = `${SITE}/upozornenia/sprava/?t=${rec.token}`;
      await sendMail(env, email, 'Správa upozornení na doplatkyliekov.sk',
        mailLayout('Správa upozornení',
          `<p style="line-height:1.6;margin:0">Cez tlačidlo nižšie upravíte zoznam liekov, na ktoré vám posielame upozornenia, alebo upozornenia úplne zrušíte.</p>
          ${button(url, 'Spravovať upozornenia')}
          <p style="font-size:13px;color:#5d716b;line-height:1.5;margin:0">Ak ste o odkaz nežiadali, e-mail ignorujte. Nič sa nezmení.</p>`),
        `${SITE}/api/unsubscribe?t=${rec.token}`);
    }
  }
  return json({ ok: true });
}
