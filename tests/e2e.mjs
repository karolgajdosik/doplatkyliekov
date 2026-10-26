// Nočný test webu: preklikanie hlavných funkcií v mobilnom prehliadači (Playwright, Chromium).
//   BASE=https://doplatkyliekov.sk node tests/e2e.mjs        (predvolene živý web)
//   BASE=http://localhost:8000 node tests/e2e.mjs           (lokálna kópia – bez AI a funkcií Cloudflare)
// Každá kontrola vypíše riadok OK/CHYBA; pri chybe skončí kódom 1 (GitHub potom pošle e-mail).
// AI funkcie (asistent, fotka) sa volajú najviac raz za noc, aby sa zbytočne nemíňali limity.
import { chromium, devices } from 'playwright';

const BASE = (process.env.BASE || 'https://doplatkyliekov.sk').replace(/\/$/, '');
const LIVE = !/localhost|127\.0\.0\.1/.test(BASE);
const GH = !!process.env.GITHUB_ACTIONS;
const results = [];

function log(ok, name, info = '') {
  results.push({ ok, name, info });
  const line = `${ok ? 'OK   ' : 'CHYBA'} ${name}${info ? ' – ' + info : ''}`;
  console.log(line);
  if (GH && !ok) console.log(`::error title=${name}::${String(info).replace(/\n/g, ' ').slice(0, 300)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ ...devices['Pixel 7'], locale: 'sk-SK', timezoneId: 'Europe/Bratislava', serviceWorkers: 'block' });
ctx.setDefaultTimeout(20000);
const jsErrors = [];
ctx.on('page', (p) => {
  p.on('pageerror', (e) => jsErrors.push(`${p.url().replace(BASE, '')}: ${e.message}`));
  p.on('response', (r) => {
    const u = r.url();
    if (u.startsWith(BASE) && r.status() >= 400 && !u.includes('/api/') && !u.includes('/cdn-cgi/')) jsErrors.push(`${u.replace(BASE, '')}: HTTP ${r.status()}`);
  });
});
const page = await ctx.newPage();

async function check(name, fn) {
  const t0 = Date.now();
  try {
    const info = await fn();
    log(true, name, (info ? info + ', ' : '') + (Date.now() - t0) + ' ms');
  } catch (e) {
    log(false, name, String(e && e.message || e).split('\n')[0]);
    try { await page.screenshot({ path: `test-chyba-${results.length}.png`, fullPage: false }); } catch { /* nič */ }
  }
}
function assert(c, msg) { if (!c) throw new Error(msg); }

let drugUrl = '';

await check('Úvodná stránka a vyhľadávanie', async () => {
  await page.goto(BASE + '/');
  await page.fill('#q', 'concor 10');
  await page.waitForSelector('#results button');
  const n = await page.locator('#results button').count();
  assert(n > 0, 'žiadne výsledky pre „concor 10“');
  await page.locator('#results button').first().dispatchEvent('mousedown');
  await page.waitForSelector('#slip:not([hidden])');
  const rows = await page.locator('#slip a[href^="/liek/"]').count();
  assert(rows > 1, 'porovnanie nemá odkazy na lieky');
  drugUrl = await page.locator('#slip a[href^="/liek/"]').first().getAttribute('href');
  return `${n} výsledkov, porovnanie ${rows} liekov`;
});

await check('Stránka lieku', async () => {
  await page.goto(BASE + (drugUrl || '/liek/'));
  const h1 = await page.locator('h1').first().textContent();
  assert(/\S/.test(h1 || ''), 'chýba nadpis');
  const img = page.locator('figure.drug3d img').first();
  if (await img.count()) {
    await img.scrollIntoViewIfNeeded();
    await page.waitForFunction((el) => el.complete && el.naturalWidth > 0, await img.elementHandle());
  }
  const price = await page.locator('text=/\\d+,\\d{2} €/').count();
  assert(price > 0, 'chýbajú ceny');
  const pharm = page.locator('.pharm-btn').first();
  if (await pharm.count()) {
    await pharm.click();
    await page.waitForSelector('.pharm-ov, .pharm-overlay, [class*="pharm"][role="dialog"]', { state: 'visible' });
    await page.keyboard.press('Escape');
  }
  return (h1 || '').trim().slice(0, 40);
});

await check('Moje lieky – pridanie a zobrazenie', async () => {
  const btn = page.locator('.mine-btn[data-kod]').first();
  assert(await btn.count(), 'chýba tlačidlo Pridať do Mojich liekov');
  const kod = await btn.getAttribute('data-kod');
  if ((await btn.getAttribute('aria-pressed')) !== 'true') await btn.click();
  await page.goto(BASE + '/moje-lieky/');
  await page.waitForFunction((k) => document.querySelector('#moje-root') && document.querySelector('#moje-root').textContent.length > 50 &&
    JSON.stringify(localStorage).includes(k), kod);
  const items = await page.locator('#moje-root li, #moje-root .mine-item').count();
  assert(items > 0, 'zoznam je prázdny');
  return `kód ${kod}, položiek ${items}`;
});

await check('Ochranný limit – kalkulačka', async () => {
  await page.goto(BASE + '/ochranny-limit/');
  await page.waitForSelector('#calc');
  const sel = page.locator('#skupina');
  if (await sel.count()) { const opts = await sel.locator('option').count(); assert(opts > 1, 'prázdny výber skupiny'); }
  await page.fill('#suma', '150');
  await page.locator('#suma').dispatchEvent('input');
  await page.waitForFunction(() => (document.querySelector('#vysledok') || {}).textContent?.trim().length > 10);
  return 'výsledok zobrazený';
});

await check('Lekárne v okolí – hľadanie obce', async () => {
  await page.goto(BASE + '/lekarne/');
  await page.waitForFunction(() => /V zozname je \d+/.test(document.querySelector('#lek-msg')?.textContent || ''));
  await page.fill('#lek-q', 'Žilina');
  await page.waitForFunction(() => document.querySelectorAll('#lek-list li .gline').length > 3);
  return (await page.locator('#lek-list li').count()) + ' lekární';
});

await check('Ďalšie jazyky a podstránky', async () => {
  const paths = ['/hu/', '/uk/', '/asistent/', '/bez-doplatku/', '/na-vytlacenie/', '/clanky/', '/statistiky/', '/pristupnost/',
    '/sitemap.xml', '/manifest.webmanifest', '/sw.js', '/ai/search.json', '/lekarne.json'];
  const bad = [];
  for (const p of paths) { const r = await page.request.get(BASE + p); if (r.status() !== 200) bad.push(`${p} ${r.status()}`); }
  assert(!bad.length, bad.join(', '));
  return `${paths.length} adries`;
});

await check('Odkazy z úvodnej stránky', async () => {
  await page.goto(BASE + '/');
  const links = [...new Set(await page.$$eval('a[href^="/"]', (as) => as.map((a) => a.getAttribute('href').split('#')[0])))].filter(Boolean).slice(0, 60);
  const bad = [];
  for (const l of links) { const r = await page.request.get(BASE + l, { maxRedirects: 3 }); if (r.status() >= 400) bad.push(`${l} ${r.status()}`); }
  assert(!bad.length, bad.join(', '));
  return `${links.length} odkazov`;
});

await check('Aktuálnosť údajov', async () => {
  const r = await page.request.get(BASE + '/data.json');
  const d = await r.json();
  assert(d.groups && d.groups.length > 1000, `málo skupín (${d.groups && d.groups.length})`);
  // platnosť zoznamu ŠÚKL nesmie byť staršia ako 40 dní
  const iso = d.platnostIso || '';
  const age = (Date.now() - Date.parse(iso.slice(0, 10))) / 86400e3;
  assert(!(age > 40), `údaje platné od ${iso}, ${Math.round(age)} dní`);
  return `${d.groups.length} skupín, platnosť ${d.platnost}`;
});

if (LIVE) {
  await check('AI asistent odpovedá', async () => {
    const r = await page.request.post(BASE + '/api/asistent', { data: { q: 'Aký je doplatok na Concor 10 mg a existuje lacnejšia náhrada?', history: [] }, timeout: 60000 });
    const t = await r.text();
    assert(r.ok(), `HTTP ${r.status()} ${t.slice(0, 120)}`);
    assert(/concor|bisoprolol/i.test(t), 'odpoveď nespomína Concor ani bisoprolol');
    return `${t.length} znakov`;
  });

  await check('Rozpoznanie lieku z fotky', async () => {
    // vyrobí obrázok „balenia“ s textom a pošle ho na /api/foto
    const img = await page.evaluate(() => {
      const c = document.createElement('canvas'); c.width = 800; c.height = 500;
      const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 800, 500);
      g.fillStyle = '#c00'; g.fillRect(0, 0, 800, 60); g.fillStyle = '#000';
      g.font = 'bold 90px Arial'; g.fillText('Concor 10', 60, 220);
      g.font = '44px Arial'; g.fillText('10 mg filmom obalené tablety', 60, 300); g.fillText('30 tabliet', 60, 370);
      return c.toDataURL('image/jpeg', 0.9);
    });
    const r = await page.request.post(BASE + '/api/foto', { data: { img }, timeout: 90000 });
    const j = await r.json().catch(() => ({}));
    assert(r.ok(), `HTTP ${r.status()} ${j.error || ''}`);
    assert((j.items || []).some((x) => /concor/i.test(x.name)), `nerozpoznal Concor (${JSON.stringify(j.found || []).slice(0, 100)})`);
    return `${j.model?.split('/').pop()}, ${j.ms} ms`;
  });

  await check('Zdieľanie medzi zariadeniami (šifrovaná synchronizácia)', async () => {
    const r = await page.request.get(BASE + '/api/sync?id=' + 'x'.repeat(4));
    assert(r.status() < 500, `HTTP ${r.status()}`);
    return `HTTP ${r.status()}`;
  });
}

await check('Bez chýb JavaScriptu a chýbajúcich súborov', async () => {
  const uniq = [...new Set(jsErrors)];
  assert(!uniq.length, uniq.slice(0, 5).join(' | '));
});

await browser.close();
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length - bad.length}/${results.length} kontrol v poriadku`);
if (GH) console.log(`::notice title=Nočný test::${results.length - bad.length}/${results.length} kontrol v poriadku${bad.length ? ' – chyby: ' + bad.map((b) => b.name).join(', ') : ''}`);
process.exit(bad.length ? 1 : 0);
