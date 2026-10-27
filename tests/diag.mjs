import { chromium, devices } from 'playwright';
const B = 'https://doplatkyliekov.sk';
const b = await chromium.launch(); const ctx = await b.newContext({ ...devices['Pixel 7'], serviceWorkers: 'block' }); const p = await ctx.newPage();
const log = []; p.on('pageerror', (e) => log.push('ERR ' + e.message)); p.on('console', (m) => { if (m.type() === 'error') log.push('CON ' + m.text()); });
p.on('response', (r) => { if (r.status() >= 400) log.push('HTTP ' + r.status() + ' ' + r.url()); });
await p.goto(B + '/liek/concor-10-mg-94163/'); await p.click('.mine-btn[data-kod]');
await p.goto(B + '/moje-lieky/'); await p.waitForTimeout(8000);
const st = await p.evaluate(() => { const c = document.getElementById('mine-chart'); return { exists: !!c, hidden: c && c.hidden, extrasHidden: document.getElementById('mine-extras')?.hidden, text: c && c.innerText.slice(0, 200), yr: !!document.querySelector('.yr-table'), m2: [...document.scripts].map((s) => s.src).filter((s) => s.includes('moje')) }; });
console.log('::notice title=moje::' + JSON.stringify(st).slice(0, 900));
await p.goto(B + '/vlozit/'); await p.waitForTimeout(3000);
const fr = p.frames().find((f) => f.url().includes('/vlozit/okno/'));
console.log('::notice title=okno::' + (fr ? fr.url() : 'žiadny frame') );
if (fr) {
  await fr.fill('#q', 'glukofag'); await p.waitForTimeout(3000);
  const s = await fr.evaluate(async () => ({ hl: typeof window.Hladaj, res: document.getElementById('res').innerText.slice(0, 200), scripts: [...document.scripts].map((s) => s.src), sj: (await fetch('/ai/search.json')).status }));
  console.log('::notice title=okno2::' + JSON.stringify(s).slice(0, 900));
}
console.log('::notice title=log::' + JSON.stringify(log).slice(0, 1500));
await b.close();
