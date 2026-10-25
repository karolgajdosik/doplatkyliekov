// Spoločné funkcie pre Cloudflare Pages Functions (prihlásenie na upozornenia).
// Potrebné nastavenia v Cloudflare Pages → Settings:
//   KV binding  SUBS            (úložisko prihlásení)
//   premenná    BREVO_API_KEY   (odosielanie e-mailov cez brevo.com) – alebo RESEND_API_KEY (resend.com)
//   premenná    MAIL_FROM       (voliteľné, napr. "doplatkyliekov.sk <upozornenia@doplatkyliekov.sk>")

export const SITE = 'https://doplatkyliekov.sk';

export function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

export function redirect(path) {
  return new Response(null, { status: 302, headers: { location: path, 'cache-control': 'no-store' } });
}

export function ready(env) {
  return Boolean(env.SUBS && (env.BREVO_API_KEY || env.RESEND_API_KEY));
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const DEFAULT_FROM = 'doplatkyliekov.sk <upozornenia@doplatkyliekov.sk>';

function parseFrom(from) {
  const m = /^\s*(.*?)\s*<([^>]+)>\s*$/.exec(from);
  return m ? { name: m[1], email: m[2] } : { email: from.trim() };
}

export async function sendMail(env, to, subject, html, unsubscribeUrl) {
  const headers = {};
  if (unsubscribeUrl) {
    headers['List-Unsubscribe'] = `<${unsubscribeUrl}>`;
    headers['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click';
  }
  const from = env.MAIL_FROM || DEFAULT_FROM;
  let r;
  if (env.BREVO_API_KEY) {
    r = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': env.BREVO_API_KEY, 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        sender: parseFrom(from), to: [{ email: to }], subject, htmlContent: html,
        ...(unsubscribeUrl ? { headers } : {}),
      }),
    });
  } else {
    r = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to: [to], subject, html, headers }),
    });
  }
  return r.ok;
}

export function mailLayout(title, inner) {
  return `<!doctype html><html lang="sk"><body style="margin:0;background:#f1f5f4;font-family:Arial,Helvetica,sans-serif;color:#0a1a16">
<div style="max-width:560px;margin:0 auto;padding:28px 20px">
<p style="font-weight:bold;font-size:16px;margin:0 0 20px">doplatky<span style="color:#00866a">liekov</span>.sk</p>
<div style="background:#ffffff;border-radius:14px;padding:24px;border:1px solid #dce6e3">
<h1 style="font-size:20px;line-height:1.3;margin:0 0 14px">${esc(title)}</h1>
${inner}
</div>
<p style="font-size:12px;color:#5d716b;line-height:1.5;margin:18px 4px 0">Údaje pochádzajú zo Zoznamu kategorizovaných liekov MZ SR a z hlásení ŠÚKL. Majú informačný charakter a nenahrádzajú radu lekára ani lekárnika.</p>
</div></body></html>`;
}

export function button(href, label) {
  return `<p style="margin:22px 0"><a href="${esc(href)}" style="display:inline-block;background:#00866a;color:#ffffff;text-decoration:none;font-weight:bold;padding:12px 20px;border-radius:999px">${esc(label)}</a></p>`;
}
