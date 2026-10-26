// Dočasný test: skutočné prihlásenie v prehliadači (Chrome/Firefox) → odoslanie cez workers/pripomienky → prijatie v service workeri.
import fs from 'fs'; import http from 'http'; import crypto from 'crypto';
import { chromium, firefox } from '/tmp/pw/node_modules/playwright/index.mjs';
const v = crypto.createECDH('prime256v1'); v.generateKeys();
const pub = v.getPublicKey('base64url'), priv = v.getPrivateKey().toString('base64');
const src = fs.readFileSync('workers/pripomienky/index.js', 'utf8').replace(/const VAPID_PUBLIC = '[^']+'/, `const VAPID_PUBLIC = '${pub}'`);
fs.writeFileSync('tools/pushtest/w.mjs', src);
const W = await import('./w.mjs');
const page = `<!doctype html><script>
window.go = async () => { const reg = await navigator.serviceWorker.register('/sw.js'); await navigator.serviceWorker.ready;
  const s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: '${pub}' }); return JSON.parse(JSON.stringify(s)); };
window.got = new Promise((res) => navigator.serviceWorker.addEventListener('message', (e) => res(e.data)));
</script>`;
const sw = `self.addEventListener('push', (e) => e.waitUntil((async () => { const d = e.data.text();
  await self.registration.showNotification('t', { body: d }); for (const c of await clients.matchAll({ includeUncontrolled: true })) c.postMessage(d); })()));
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));`;
http.createServer((q, r) => { r.writeHead(200, { 'content-type': q.url === '/sw.js' ? 'text/javascript' : 'text/html' }); r.end(q.url === '/sw.js' ? sw : page); }).listen(8123);
async function attempt(name, launch) {
  let b;
  try {
    b = await launch();
    const ctx = await b.newContext({ permissions: name === 'chrome' ? ['notifications'] : [] });
    const p = await ctx.newPage(); await p.goto('http://localhost:8123/');
    const sub = await p.evaluate(() => window.go());
    const res = await W.sendPush(sub, { title: 'Čas na liek · 08:00', body: 'Concor 10 mg: ½ ks' }, priv, 60);
    const data = await Promise.race([p.evaluate(() => window.got), new Promise((r) => setTimeout(() => r('NEPRIŠLO'), 30000))]);
    console.log(`::notice::${name}: služba ${new URL(sub.endpoint).host} odpoveď ${res}, prijaté: ${data}`);
  } catch (e) { console.log(`::warning::${name}: ${String(e.message).slice(0, 200)}`); }
  finally { if (b) await b.close(); }
}
await attempt('chrome', () => chromium.launch({ channel: 'chrome', headless: false }));
await attempt('firefox', () => firefox.launch({ headless: true, firefoxUserPrefs: { 'dom.push.enabled': true, 'dom.push.connection.enabled': true,
  'dom.push.serverURL': 'wss://push.services.mozilla.com/', 'permissions.default.desktop-notification': 1, 'dom.push.testing.ignorePermission': true } }));
process.exit(0);
