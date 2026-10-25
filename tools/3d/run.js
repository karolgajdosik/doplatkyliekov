const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 800, height: 600 } });
  p.on('console', m => console.log('C', m.text())); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('http://127.0.0.1:8833/scene.html'); await p.waitForFunction(() => window.ready, null, { timeout: 60000 });
  const jobs = JSON.parse(process.argv[2]);
  fs.mkdirSync('out', { recursive: true });
  for (const [name, form, color, accent] of jobs) {
    const t = Date.now();
    const d = await p.evaluate(([f, c, a]) => window.render3d(f, c, a), [form, color, accent]);
    fs.writeFileSync((process.env.OUT || 'out') + '/' + name + '.png', Buffer.from(d.split(',')[1], 'base64'));
    console.log(name, Date.now() - t, 'ms');
  }
  await b.close();
})();
