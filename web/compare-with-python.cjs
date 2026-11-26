const { chromium } = require('playwright');
const ref = require('/home/user/webexport/reference.json');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
  await p.goto('http://127.0.0.1:8765/index.html');
  let agree = 0, n = 0;
  for (const [name, r] of Object.entries(ref)) {
    const t0 = Date.now();
    const js = await p.evaluate(u => window.__cropDoctorPredict(u), 'imgs/' + name);
    n++; const same = js.status === r.status && js.class_id === r.class_id;
    agree += same;
    console.log(`${same ? 'SAME' : 'DIFF'} ${name}: py=${r.status}/${r.class_id}/${r.confidence}/${r.ood_distance}  js=${js.status}/${js.class_id}/${js.confidence.toFixed(4)}/${js.ood_distance.toFixed(2)} (${Date.now()-t0}ms)`);
  }
  console.log(`${agree}/${n} identical decisions`); console.log('errors:', errs);
  await b.close();
})();
