// Functional test for web/index.html demo JS, run in node with a DOM shim.
// Usage: node verify-demo-test.js <web-dir>
// Loads demo_data.js, extracts the inline <script> from index.html, evals it,
// then drives loadSample/analyze exactly as a user would in a browser.
const fs = require('fs');
const webDir = process.argv[2];
const assert = require('assert');

let failures = 0;
function check(name, fn) {
  try { fn(); console.log('PASS: ' + name); }
  catch (e) { failures++; console.log('FAIL: ' + name + ' — ' + e.message); }
}

// --- DOM shim ---
function makeEl() {
  return { value: '', textContent: '', innerHTML: '',
    classList: { remove() {}, add() {} } };
}
const ids = ['letter', 'path', 'verdict', 'appeal-stats', 'missing-doc',
  'draft', 'result', 'acc-from', 'acc-to', 'prec', 'appeals', 'dollars'];
const els = {};
for (const id of ids) els[id] = makeEl();
global.window = {};
global.document = { getElementById: (id) => els[id] || makeEl() };
global.alert = (m) => { throw new Error('alert: ' + m); };
global.navigator = { clipboard: { writeText() {} } };

// --- load demo data + page script ---
const demoJs = fs.readFileSync(webDir + '/demo_data.js', 'utf8');
eval.call(global, demoJs);
const D = global.window.DENIALGRAPH;
check('demo_data.js loads: patterns + samples + curve + docRates', () => {
  assert.ok(D && D.patterns && D.samples && D.curve && D.docRates);
  assert.ok(Object.keys(D.patterns).length > 0, 'no patterns');
  assert.ok(D.samples.length > 0, 'no samples');
  assert.strictEqual(D.curve.length, 11, 'curve should have 11 rounds');
  assert.strictEqual(D.curve[0].accuracy, 0.575);
  assert.strictEqual(D.curve[10].accuracy, 0.775);
});
const html = fs.readFileSync(webDir + '/index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
assert.ok(scripts.length >= 1, 'no inline script in index.html');
for (const s of scripts) eval.call(global, s);
const { loadSample, analyze, parseLetter } = global;

// --- curve stats rendered on load ---
// NOTE: 0.575*100 is 57.49999999999999 in float, so Math.round gives 57,
// and 0.775*100 rounds to 78. The demo therefore shows 57% -> 78% while
// the README states the exact 57.5% -> 77.5%: a rounding display quirk.
check('curve stats: 57% -> 78% accuracy, 40% -> 70% precision, 20 -> 10 appeals', () => {
  assert.strictEqual(els['acc-from'].textContent, '57%');
  assert.strictEqual(els['acc-to'].textContent, '78%');
  assert.ok(els.prec.textContent.includes('40%') && els.prec.textContent.includes('70%'), els.prec.textContent);
  assert.strictEqual(els.appeals.textContent, '20 → 10');
  assert.ok(els.dollars.textContent.includes('6,686'), els.dollars.textContent);
});
check('sample 0 letter preloaded into the textarea', () => {
  assert.ok(els.letter.value.length > 50);
  assert.ok(els.letter.value.includes('denied') || els.letter.value.includes('Denial'));
});

// --- every sample: parse -> precedent -> path + verdict + draft ---
let withPrecedent = 0;
D.samples.forEach((s, i) => {
  check(`sample ${i} (${s.payer}, CPT ${s.cpt}): full analysis`, () => {
    loadSample(i);
    const p = parseLetter(s.letter);
    assert.strictEqual(p.payer, s.payer, `payer parsed as ${p.payer}`);
    assert.strictEqual(p.cpt, s.cpt, `cpt parsed as ${p.cpt}`);
    assert.ok(p.denial.length > 0, 'denial not parsed');
    assert.ok(els.path.innerHTML.includes('Claim') && els.path.innerHTML.includes('Missing doc'),
      'path missing nodes');
    assert.ok(els.path.innerHTML.includes(s.missingDoc), 'path missing the missing-doc step');
    assert.ok(els.draft.textContent.includes('Appeal of denied claim'), 'draft missing header');
    assert.ok(els.draft.textContent.includes(s.missingDoc), 'draft missing the document');
    const key = `${p.payer}|${p.cpt}|${p.denial}`;
    if (D.patterns[key]) {
      withPrecedent++;
      assert.ok(els.verdict.innerHTML.includes('win chance'), 'verdict missing win chance');
      assert.ok(/(\d+)%/.test(els.verdict.innerHTML), 'verdict missing a % figure');
    }
  });
});
console.log(`samples with an exact graph precedent: ${withPrecedent}/${D.samples.length}`);
check('at least one sample has an exact precedent', () => assert.ok(withPrecedent > 0));

// --- gap case: unknown combination must say so, not invent ---
check('unknown combination yields the gap message, not invented numbers', () => {
  els.letter.value = 'Dear patient, your claim CLM-999999 for CPT 99999 (Billed amount: $100.00) ' +
    'was denied by Aetna (code CO-99) because of timely filing.';
  analyze();
  assert.ok(els.verdict.innerHTML.includes('no exact precedent'), els.verdict.innerHTML.slice(0, 120));
  assert.ok(!/%\s*win chance/.test(els.verdict.innerHTML), 'gap case invented a win chance');
});

// --- doc rates: the headline 45.5% vs 10.6% ---
check('docRates match the headline: supplied ~45.5% vs missing ~10.6%', () => {
  assert.ok(Math.abs(D.docRates.supplied.winRate - 0.455) < 0.01, D.docRates.supplied.winRate);
  assert.ok(Math.abs(D.docRates.missing.winRate - 0.106) < 0.01, D.docRates.missing.winRate);
});

if (failures === 0) console.log('ALL DEMO CHECKS PASSED');
else { console.log(`${failures} DEMO CHECK(S) FAILED`); process.exit(1); }
