# End-to-end verification — patient-denialgraph

**Verdict: the app works as intended, end to end, on the verified scope below.
24 of 25 checks passed on first run; the 1 failure was a real defect, fixed
and re-verified (see §4).**

- Verified: Sun Nov 15, 2026, ~5:00–5:05pm PT (01:01–01:02 UTC Nov 16)
- Verified against: GitHub `main` at `97df2cb0` (the SVG-switch commit)
- Method: clean-room copy of the repo (no `.git`, no `.venv`, no existing
  Kuzu store), rebuilt from scratch and re-run. Scripts:
  [`scripts/verify_e2e.sh`](scripts/verify_e2e.sh) (bash driver, writes
  `LOG.txt`) and [`scripts/verify_demo_test.js`](scripts/verify_demo_test.js)
  (node functional test of the demo page JS with a DOM shim).
- Interpreters: system `python3` (matplotlib 3.6.3) for
  `generate_data.py` / `learn.py` / `build_demo_data.py`, exactly as in the
  original build; repo `.venv` (SelfGraph 0.2.1) for the ingest.
  This matters: the `.venv` ships matplotlib 3.11.2, which renders a
  byte-different PNG, and running the venv python through a symlinked path
  leaks the system pandas in (binary-incompatible with the venv numpy) and
  crashes the ingest. Both are verification-harness gotchas, not app bugs —
  the scripts encode the working invocation.
- Raw log: re-run `scripts/verify_e2e.sh` to reproduce it.

## 1. Results

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Committed data matches the README headline numbers | PASS | 200 cases (160 train / 40 eval), 11 curve rows; baseline 57.5% acc / 40% precision / 20 appeals / $6,707.38 net → final 77.5% / 70% / 10 appeals / $6,686.30 net, 30 shortcuts |
| 2 | `generate_data.py` runs | PASS | seeded (`random.seed(20261115)`) |
| 3 | `learn.py` runs, same curve | PASS | "Baseline acc 0.575 -> final acc 0.775 (+20.0 pts)"; net $6,707.38 → $6,686.30; 30 shortcuts |
| 4 | Regenerated `curve.csv` identical to committed | PASS | byte-identical diff |
| 5 | Regenerated `curve.json` identical to committed | PASS | byte-identical diff |
| 6 | Regenerated `curve.png` identical to committed local PNG | PASS | md5 match, both files (system python3 / matplotlib 3.6.3 only — see §3) |
| 7 | `learn.py` rerun leaves `curve.svg` untouched | **FAIL → fixed, re-verified** | see §4 |
| 8 | SelfGraph ingest `--full` (200 letters, Kuzu) | PASS | "inserted 200 letters in 18.7s" |
| 9 | Policy update inserted (PA-101 retired → PA-102) | PASS | "policy update inserted (PA-101 retired, PA-102 supersedes)" |
| 10 | Retrieval returns sourced context | PASS | current context 9,402 chars |
| 11 | Versioning: `as_of` retrieval differs from current | PASS | as-of 2026-06-01 context 8,164 chars ≠ current 9,402 |
| 12 | Answerability: off-topic question flagged, not invented | PASS | "What is the staff size of Aetna by ad spend?" → `partial`, missing `['staff', 'size', 'ad', 'spend']` |
| 13 | `build_demo_data.py` runs, same curve | PASS | "curve: baseline 0.575 -> final 0.775" |
| 14 | Regenerated `demo_data.js` identical to committed | PASS | byte-identical diff |
| 15 | Demo JS loads (patterns, samples, curve, docRates) | PASS | node + DOM shim; curve 11 rounds, 0.575 → 0.775 |
| 16 | Curve stats render | PASS | 57% → 78% acc, 40% → 70% precision, 20 → 10 appeals, $6,686 (see §3 on rounding) |
| 17 | Sample 0 letter preloaded | PASS | textarea populated on load |
| 18 | All 3 samples: parse → precedent → path + verdict + appeal draft | PASS | 3/3 with an exact graph precedent; path shows Claim → CPT → Payer → Policy → Denial → Missing doc; draft contains the missing document |
| 19 | Unknown combination yields the gap message, invents nothing | PASS | "no exact precedent in the graph"; no win-chance % invented |
| 20 | Doc rates match the headline | PASS | supplied ≈45.5% vs missing ≈10.6% |
| 21 | Demo serves over HTTP: `/`, `/demo_data.js`, `/curve.svg` | PASS | HTTP 200 for all three |
| 22 | `index.html` references `curve.svg`; served file is SVG | PASS | `src="curve.svg"`, valid SVG |
| 23 | GitHub `main` head is `97df2cb0` | PASS | `list_commits`, head SHA match |
| 24 | Key files present on GitHub `main` | PASS | `web/curve.svg`, `web/index.html`, `README.md`, `data/curve.csv`, `DEPLOY.md`, `DEMO_SCRIPT.md` — all read back |
| 25 | GitHub Pages live URL | NOT LIVE (expected) | `https://ethanthatonekid.github.io/patient-denialgraph/` → HTTP 404. Pages workflow not yet added/enabled — Ethan-only item, not an app failure |

## 2. What "working" means here, precisely

- The learning loop is real computation on synthetic data, and it
  reproduces exactly: same seed, same code → byte-identical `curve.csv`,
  `curve.json`, and (with the original interpreter) `curve.png`.
  The graph does not invent money: it recovers about the same dollars
  ($6,707 → $6,686 net) while filing half as many appeals (20 → 10) at
  much higher precision (40% → 70%). The headline gain is accuracy
  57.5% → 77.5%.
- SelfGraph on embedded Kuzu ingests all 200 letters, keeps sources,
  versions a policy change (PA-101 → PA-102) so the past graph is still
  readable `as_of` 2026-06-01, and refuses to invent answers for
  off-graph questions.
- The demo page is functional, not a screenshot: pasting (or loading) a
  denial letter parses payer / CPT / denial, walks the
  Claim → CPT → Payer → Policy → Denial → Missing-doc path against the
  learned patterns, quotes a win chance with and without the missing
  document, and drafts a copyable appeal. An unmatched combination says
  so instead of inventing a precedent.

## 3. Honest notes (not failures)

- **Demo rounding.** The page shows 57% → 78% accuracy while the README
  states the exact 57.5% → 77.5%. Cause: `Math.round(0.575 * 100)` is 57
  in floating point (57.4999…), and `Math.round(77.5)` is 78. Cosmetic;
  the underlying data is exact.
- **Answerability is conservative.** `check_answerable` returns `partial`
  even for the on-topic question ("Why was claim CLM-100000 denied?" →
  missing `['denied']`). Light-level SelfGraph does not claim full
  answerability; it reports what is missing instead of inventing.
- **PNG reproducibility is interpreter-pinned.** Byte-identical PNGs
  require system python3 / matplotlib 3.6.3. The `.venv` matplotlib
  3.11.2 renders the same chart with different bytes (and different
  pixels, from font rendering). The data (`curve.csv`/`curve.json`) is
  identical either way.
- **Synthetic data only.** 200 synthetic cases, 30 payer×CPT patterns,
  40-case frozen eval. Rounds 1–4 wobble (small eval set). Real denial
  letters and win rates will vary.

## 4. Defect found and fixed

**`learn.py` silently overwrote the hand-built `curve.svg` on every rerun.**
The two `fig.savefig(..., "curve.svg")` lines added in the PNG→SVG switch
made matplotlib replace `web/curve.svg` (6.6 KB, hand-built) with a 56 KB
matplotlib rendering. The replacement was valid SVG of the same chart, so
the demo still worked — but the committed file was not the file being
regenerated, and a rerun would silently swap it.

Fix (commit `ba5e3be`): the `savefig` SVG lines are removed from
`learn.py`; the SVG's source of truth is `src/build_curve_svg.py`.
Re-verified in a fresh clean room: a `learn.py` rerun now leaves
`web/curve.svg` and `data/curve.svg` byte-identical, and `curve.csv` /
`curve.json` / `curve.png` identical too.

## 5. Explicitly NOT verified (out of scope for this run)

- **No live HydraDB server.** The sandbox has no Docker and no Rust
  toolchain, so no HydraDB 0.4.0 server was run here; `src/cypher.py`
  remains unexecuted (see `HYDRA_FINDINGS.md`). What was verified is
  SelfGraph on embedded Kuzu plus the confirmed existence of HydraDB
  0.4.0 (released 2026-11-14, `ghcr.io/hydra-db/hydradb:0.4.0`).
  Do not claim a live HydraDB run in the submission.
- **No live Pages link.** See check 25 — Ethan-only steps remain
  (workflow file, Pages source, manual run).
- **No walkthrough video, no submission.** Ethan-only; not filed.

## 6. Reproduce

```bash
bash scripts/verify_e2e.sh   # clean-room rebuild + full check suite, log to /tmp/verify-room/LOG.txt
node scripts/verify_demo_test.js web   # demo-page functional test only (needs web/demo_data.js + web/index.html)
```
