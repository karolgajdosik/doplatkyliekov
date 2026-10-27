// Meranie rýchlosti a prístupnosti (Lighthouse, mobil). Výsledky do súhrnu GitHub Actions.
//   BASE=https://doplatkyliekov.sk node tests/lighthouse.mjs
// Zlyhá, ak prístupnosť klesne pod 95 alebo rýchlosť pod 70 (stredná hodnota z 3 meraní).
import fs from 'fs';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

const BASE = (process.env.BASE || 'https://doplatkyliekov.sk').replace(/\/$/, '');
const PAGES = ['/', '/liek/concor-10-mg-94163/', '/moje-lieky/', '/lekarne/', '/asistent/'];
const MIN = { performance: 70, accessibility: 95 };
const RUNS = 3;
const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
const rows = [], problems = [];
const median = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
for (const p of PAGES) {
  const sc = { performance: [], accessibility: [], 'best-practices': [], seo: [] }, lcp = [], bytes = [];
  let last;
  for (let i = 0; i < RUNS; i++) {
    const r = await lighthouse(BASE + p, { port: chrome.port, output: 'json', logLevel: 'error', onlyCategories: Object.keys(sc) });
    last = r.lhr;
    for (const k in sc) sc[k].push(Math.round(last.categories[k].score * 100));
    lcp.push(last.audits['largest-contentful-paint'].numericValue);
    bytes.push(last.audits['total-byte-weight'].numericValue);
  }
  const m = Object.fromEntries(Object.entries(sc).map(([k, v]) => [k, median(v)]));
  rows.push(`| ${p} | ${m.performance} | ${m.accessibility} | ${m['best-practices']} | ${m.seo} | ${(median(lcp) / 1000).toFixed(1)} s | ${Math.round(median(bytes) / 1024)} kB |`);
  for (const [k, min] of Object.entries(MIN)) if (m[k] < min) problems.push(`${p}: ${k} ${m[k]} < ${min}`);
  const failed = Object.values(last.audits).filter((a) => a.score !== null && a.score < 0.9 && ['binary', 'numeric'].includes(a.scoreDisplayMode) &&
    last.categories.accessibility.auditRefs.some((r) => r.id === a.id && r.weight > 0));
  for (const a of failed) problems.push(`${p}: prístupnosť – ${a.title}`);
  console.log(p, JSON.stringify(m), Math.round(median(lcp)), 'ms');
  console.log(`::notice title=Lighthouse ${p}::rýchlosť ${m.performance}, prístupnosť ${m.accessibility}, postupy ${m['best-practices']}, SEO ${m.seo}, LCP ${(median(lcp) / 1000).toFixed(1)} s, ${Math.round(median(bytes) / 1024)} kB` +
    ' || ' + Object.values(last.audits).filter((a) => a.score !== null && a.score < 0.9 && last.categories.performance.auditRefs.some((r) => r.id === a.id))
      .map((a) => `${a.id}${a.displayValue ? ' (' + a.displayValue + ')' : ''}${['render-blocking-insight', 'legacy-javascript-insight', 'cache-insight', 'third-parties-insight', 'long-tasks', 'unminified-css', 'unminified-javascript'].includes(a.id) ? ': ' + JSON.stringify((a.details?.items || []).slice(0, 4).map((x) => x.url || x.entity || x)).slice(0, 300) : ''}`).join('; ').slice(0, 1500));
  fs.mkdirSync('lh', { recursive: true });
  fs.writeFileSync(`lh/${p.replace(/\W+/g, '_') || 'home'}.json`, JSON.stringify(last));
}
await chrome.kill();
const md = ['### Rýchlosť a prístupnosť (mobil, medián z 3 meraní)', '', '| Stránka | Rýchlosť | Prístupnosť | Postupy | SEO | LCP | Veľkosť |', '|---|---|---|---|---|---|---|', ...rows, '',
  problems.length ? '**Na opravu:**\n' + problems.map((x) => '- ' + x).join('\n') : 'Všetko v poriadku.'].join('\n');
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + '\n');
console.log(md);
for (const x of problems.slice(0, 8)) console.log(`::warning title=Lighthouse::${x}`);
process.exit(problems.some((x) => / < /.test(x)) ? 1 : 0);
