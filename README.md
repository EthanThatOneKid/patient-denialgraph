# DenialGraph-lite — patient-first claim denial appeals

**HydraDB Hackathon, Track 1: the self-improving graph.**

A patient uploads a denial letter or EOB. The graph explains in plain English
why it was denied — Claim → CPT code → Payer → Policy → Denial Reason — finds
the appeal path that has worked for that same payer / code / policy combo,
and drafts the appeal. The graph gets better at this every time an appeal
outcome comes back: edge reweighting, path compression, and gap-driven
questions for the one missing document.

**Patient first, by design.** The buyer in most denial software is the
clinic. Here the user is the patient: the metric is the patient's appeal-win
rate and the patient's wasted effort, not the clinic's revenue. A clinic
benefits second (fewer angry calls, faster payment). See the numbers below —
the learned graph recovers about the same money as a static rule lookup while
filing *half* as many appeals.

> All data is synthetic (200 invented cases, no real PHI). Nothing here is
> medical or legal advice.

## Results (frozen 40-case eval set, never trained on)

| | Baseline: payer rule lookup | After 10 learning rounds |
|---|---|---|
| Appeal-win prediction accuracy | 57.5% | **77.5% (+20 pts)** |
| Precision of recommended appeals | 40% | **70%** |
| Appeals filed (eval set) | 20 | **10** |
| Patient net $ saved (eval set) | $6,707 | $6,686 |

The honest read: the graph doesn't invent money — the winnable dollars in the
eval set are fixed. What it does is stop patients wasting appeals on cases
that won't win. Same money recovered, half the wasted effort. Each losing
appeal costs a patient ~$35 of time/postage/phone calls (our model); at 40%
precision the rule lookup burns most of its recommendations.

![Learning curve](web/curve.png)

Full numbers: [`data/curve.csv`](data/curve.csv). Reproduce with
`python3 src/generate_data.py && python3 src/learn.py`.

## How the graph learns (the Track 1 bar)

1. **Edge reweighting.** The weight of the `(payer, CPT, denial)` edge is the
   Bayesian-smoothed appeal-win rate for that combo, re-estimated from every
   appeal outcome. The `Document` edge carries P(win | doc supplied) vs
   P(win | doc missing): 45.5% vs 10.6% in our data. That's the single most
   useful thing the graph knows.
2. **Path compression.** A `(CPT, payer, denial)` chain seen ≥ 5 times gets a
   shortcut edge `FREQUENTLY_DENIED_AS`, collapsing the explanation path
   from 3 hops to 1. 30 shortcuts by round 10.
3. **Gap-driven ingestion.** When the supporting document is missing, the
   system asks the patient for exactly one document — the one the graph
   learned wins appeals for that denial. In the simulation, asked patients
   supply it half the time, which is what lifts the win rate.

## Try it

Open `web/index.html` (static, no build step) and paste a denial letter,
or load a sample. It parses payer / CPT / denial code, walks the graph path,
shows your win chance with and without the missing document, and drafts the
appeal letter.

Deploy: see [`DEPLOY.md`](DEPLOY.md) — GitHub Pages for the static demo
first, live HydraDB 0.4.0 on Railway second.

## Stack

- **HydraDB** ([hydra-db/hydradb](https://github.com/hydra-db/hydradb)) —
  open-source graph DB, Rust + SlateDB, OpenCypher/Bolt + HTTP API.
  Cypher schema + HTTP client: [`src/cypher.py`](src/cypher.py).
- **SelfGraph** ([hydra-db/selfgraph](https://github.com/hydra-db/selfgraph),
  v0.2.1) — unstructured text in, versioned knowledge graph out. Ingest:
  [`src/ingest_selfgraph.py`](src/ingest_selfgraph.py).
- Learning loop (in-memory graph, same model as the Cypher schema):
  [`src/learn.py`](src/learn.py). Data: [`src/generate_data.py`](src/generate_data.py).

### Run the SelfGraph ingest (verified working, Kuzu embedded backend)

```bash
python3 -m venv .venv && .venv/bin/pip install "selfgraph[all]"
.venv/bin/python src/ingest_selfgraph.py --full   # 200 letters, ~80s
```

Verified 2026-11-15: 200 letters ingested, 385 entities, 291 relations,
201 sources; retrieval returns the source letter text; `check-answerable`
reports `partial` with missing terms for unanswerable questions; a policy
update (Aetna PA-101 retired → PA-102) supersedes the old rule and `as_of`
retrieval shows the pre-change graph. Full log: [`HYDRA_FINDINGS.md`](HYDRA_FINDINGS.md).

### Run against live HydraDB 0.4.0 (not yet executed — see findings)

```bash
# Start HydraDB 0.4.0: ghcr.io/hydra-db/hydradb:0.4.0 (Docker) or the Railway template
HYDRA_TOKEN=local-development-token-32-bytes python3 src/cypher.py
```

SelfGraph's `HydraDBStore` requires HydraDB ≥ 0.4.0; v0.4.0 shipped
Nov 14, 2026 and the image exists on GHCR. The sandbox used for this build
had no Docker/Rust and apt stalled, so no live HydraDB run happened here —
the Cypher is written to the docs and marked unexecuted.

## Who wants it (GTM)

- **Patients, direct:** anyone who gets a denial letter. Free tier for one
  appeal draft; paid when the appeal wins (success fee) or a flat $9/appeal.
  Distribution: employers' benefits help, patient-advocacy groups, Reddit
  r/healthinsurance, TikTok explainers.
- **Second:** small clinics that want fewer angry patient calls — white-label
  the appeal explainer.
- **Proof point:** Avelis Health started consumer-facing (helping patients
  fight inflated bills) before moving upstream to employers/plans. Same arc.

## Layout

```
data/                 synthetic cases (cases.json), eval curve, denial letters
src/generate_data.py  200 synthetic cases, 30 payer x CPT patterns
src/learn.py          baseline vs 10-round learning loop + curve.png
src/ingest_selfgraph.py  SelfGraph ingest + versioning + answerability demo
src/cypher.py         HydraDB Cypher schema + HTTP client (unexecuted, see findings)
src/build_demo_data.py  embeds learned weights into the demo page
web/index.html        one-page demo (paste a letter, get the path + appeal draft)
web/curve.png         learning curve
HYDRA_FINDINGS.md     what we actually verified about HydraDB + SelfGraph
```

## Limitations

- Synthetic data only; real denial letters vary more, and real win rates
  depend on state law (external review rights) and payer behavior.
- Light-level SelfGraph extraction is regex-based: it finds the letter text
  but doesn't reliably extract typed relations without an LLM (balanced/max
  need spaCy/LLM). The demo's pattern matching therefore uses the structured
  case fields, not the regex graph.
- No auth, no multi-user, no real payer API. Deliberately out of scope for a
  hackathon demo.
