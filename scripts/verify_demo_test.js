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
global.alert = (m) => { global.__alerted = m; }; // record, don't throw: copyDraft alerts on success
// NOTE: Node 24 ships a getter-only global `navigator` (no clipboard), so a
// plain `global.navigator = ...` assignment silently no-ops. Replace it.
Object.defineProperty(globalThis, 'navigator', {
  value: { clipboard: { writeText(t) { global.__copied = t; } } },
  configurable: true, writable: true });

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
const { loadSample, analyze, parseLetter,
  reviseShorter, reviseFirmer, reviseEmphasizeDoc, resetDraft, copyDraft } = global;

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
    assert.ok(els.draft.value.includes('Appeal of denied claim'), 'draft missing header');
    assert.ok(els.draft.value.includes(s.missingDoc), 'draft missing the document');
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

// --- draft iteration: editable draft + revise actions ---
check('draft is an editable textarea in the page (not read-only text)', () => {
  assert.ok(html.includes('<textarea id="draft"'), 'no <textarea id="draft"> in index.html');
  assert.ok(!html.includes('<pre id="draft"'), 'draft is still a read-only <pre>');
  assert.ok(html.includes('reviseShorter()') && html.includes('reviseFirmer()') &&
    html.includes('reviseEmphasizeDoc()') && html.includes('resetDraft()'),
    'revise buttons missing from index.html');
});

check('draft iteration: edit, Shorter, Firmer, Emphasize, stack, Reset, Copy', () => {
  loadSample(0);
  const original = els.draft.value;
  assert.ok(original.includes('Appeal of denied claim'), 'original draft missing header');
  const sample0 = D.samples[0];
  assert.ok(original.includes(sample0.missingDoc), 'original draft missing the missing doc');

  // The patient can edit the draft directly, and revises keep their edit.
  els.draft.value += '\nMy doctor says this MRI was urgent.';
  reviseShorter();
  assert.ok(els.draft.value.includes('My doctor says this MRI was urgent.'),
    'Shorter dropped the patient edit');
  assert.ok(!els.draft.value.includes('Similar appeals for this payer'),
    'Shorter did not remove the similar-appeals paragraph');
  assert.ok(!els.draft.value.includes('Thank you for your review.'),
    'Shorter did not remove the thank-you line');
  assert.ok(els.draft.value.length < original.length, 'Shorter did not shorten the draft');
  assert.ok(els.draft.value.includes(sample0.missingDoc), 'Shorter dropped the missing doc');
  assert.ok(els.draft.value.includes('Appeal of denied claim'), 'Shorter dropped the claim');

  // Firmer: stronger ask + deadline + external-review step; idempotent.
  resetDraft();
  assert.strictEqual(els.draft.value, original, 'Reset did not restore the original draft');
  reviseFirmer();
  assert.ok(els.draft.value.includes('full review and reversal of this denial'),
    'Firmer did not strengthen the ask');
  assert.ok(els.draft.value.includes('within 30 days'), 'Firmer did not add a deadline');
  assert.ok(els.draft.value.includes('external review'), 'Firmer did not add the external-review step');
  const firmerOnce = els.draft.value;
  reviseFirmer();
  assert.strictEqual(els.draft.value, firmerOnce, 'Firmer is not idempotent');
  assert.strictEqual((els.draft.value.match(/external review/g) || []).length, 1,
    'external-review line duplicated');

  // Emphasize the document: adds the paragraph; idempotent.
  resetDraft();
  reviseEmphasizeDoc();
  assert.ok(els.draft.value.includes('is the document the denial turns on'),
    'Emphasize did not add the paragraph');
  assert.ok(els.draft.value.includes(sample0.missingDoc), 'Emphasize lost the document name');
  const emphOnce = els.draft.value;
  reviseEmphasizeDoc();
  assert.strictEqual(els.draft.value, emphOnce, 'Emphasize is not idempotent');

  // Revisions stack: Shorter then Firmer keeps both effects.
  resetDraft();
  reviseShorter();
  reviseFirmer();
  assert.ok(!els.draft.value.includes('Similar appeals for this payer'), 'stacked Shorter lost');
  assert.ok(els.draft.value.includes('full review and reversal'), 'stacked Firmer lost');
  assert.ok(els.draft.value.includes('Appeal of denied claim'), 'stacked revises dropped the claim');

  // Copy copies the CURRENT draft, including patient edits.
  resetDraft();
  els.draft.value += '\nMy doctor says this MRI was urgent.';
  copyDraft();
  assert.strictEqual(global.__copied, els.draft.value, 'Copy did not copy the edited draft');
  assert.ok(global.__copied.includes('My doctor says this MRI was urgent.'),
    'Copy missed the patient edit');

  // Re-analyzing regenerates the draft (documented: edits are discarded).
  analyze();
  assert.strictEqual(els.draft.value, original, 're-analyze did not regenerate the original draft');
});

if (failures === 0) console.log('ALL DEMO CHECKS PASSED');
else { console.log(`${failures} DEMO CHECK(S) FAILED`); process.exit(1); }
