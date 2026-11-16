# HYDRA_FINDINGS.md — what we actually verified about HydraDB + SelfGraph

Date: 2026-11-15. Sandbox: Linux VM, Python 3.12, Node 24, no Docker, no
Rust toolchain, root access. Everything below was run or fetched on that day;
claims say how they were checked.

## HydraDB engine

- **v0.4.0 exists and is current.** GitHub API, 2026-11-15:
  releases `v0.4.0` (published 2026-11-14T02:32:46Z), `v0.3.0` (2026-10-25),
  `v0.2.0` (2026-09-30). No release binaries attached to v0.4.0.
- **Docker image 0.4.0 exists.** GHCR tags list (authenticated token fetch):
  `0.4.0, 0.4, 0.3.0, 0.3, 0.2.0, latest, sha-9166374, …` for
  `ghcr.io/hydra-db/hydradb`. This matters because SelfGraph's HydraDBStore
  requires HydraDB **≥ 0.4.0** — the requirement is satisfiable, and the
  0.3.0 image must NOT be used.
- **No live HydraDB run in this sandbox (BLOCKED, not failed).** No `docker`,
  no `cargo`/`rustc`, no `just`. `apt-get update` hung for 8+ minutes
  (killed by hand) while installing `docker.io`. Building from source was
  out of scope for the timebox and is not recommended for the demo path
  anyway. **Next step for a live run:** pull `ghcr.io/hydra-db/hydradb:0.4.0`
  on a machine with Docker, or use the Railway template with a Railway
  Bucket as the S3-compatible store.
- **Ports/endpoints (from USING-HYDRADB.md, main branch, read 2026-11-14 —
  doc claims, not live-verified):** Bolt `127.0.0.1:7687`, HTTP query API
  `127.0.0.1:8443` (`POST /v1/graphs/{graph_id}/query`, `GET /healthz`),
  Admin `127.0.0.1:9090` (`GET /readyz` returns 200 with empty body,
  `GET /metrics`). `/healthz` and `/readyz` are NOT interchangeable.
- **Quirks (doc claims, baked into `src/cypher.py`):**
  - Node `id` is the upsert key, not an ordinary property.
  - Relationships do NOT deduplicate on single-statement CREATE
    (3× CREATE = 3 parallel edges); MERGE and UNWIND batch CREATE are
    idempotent. All writes here use MERGE.
  - `count(DISTINCT …)` is rejected; `RETURN *` is rejected (name columns).
  - Reading a node `id` yields typed cell `vertex_id`, not `integer`;
    a null cell has no `value` key.
  - `cell_id` is mandatory on every HTTP request; a wrong one returns an
    opaque HTTP 500, not a helpful error.
  - Auth is a bearer token; local-dev default
    `local-development-token-32-bytes`, graph `default`, cell `cell-0`.

## SelfGraph

- **v0.2.1 on PyPI** (released 2026-11-14T18:18:08Z; also `ts-v0.2.1`).
  `pip install "selfgraph[all]"` works cleanly in a venv (install took
  ~4 min). `selfgraph 0.2.1`, `kuzu 0.11.3`, `neo4j 6.4.1` driver present.
- **Verified working end-to-end on the embedded Kuzu backend** (no server):
  - `selfgraph --store kuzu --uri data/selfgraph-kuzu --level light init` →
    `{"ok": true, "store": "kuzu"}`.
  - `insert text` of 200 denial letters via `src/ingest_selfgraph.py`
    (SyncSelfGraph API): **81s for 200 letters**, no LLM.
  - `readiness`: `{"ready": true, "entities": 385, "relations": 291,
    "sources": 201}`, lint flags 3 orphan entities
    (`thing:billed`, `thing:patient`, `thing:pt`).
  - `retrieve "Why was claim CLM-100000 denied?"` returns the source
    letter passages with provenance (context 9,402 chars).
  - `check_answerable` on an answerable question → verdict `partial`,
    missing `['denied']`; on "What is the staff size of Aetna by ad spend?"
    → `partial`, missing `['staff','size','ad','spend']` — i.e. it reports
    the gap instead of inventing an answer. Good.
  - **Versioning works:** inserting an Aetna policy update with
    `contradiction="supersede"` retires PA-101; `retrieve(..., as_of=
    "2026-06-01")` returns the pre-change context (8,164 chars vs 9,402).
- **API notes (0.2.1, found by reading the installed package):**
  - The sync facade is `SyncSelfGraph(store=..., level="light")` with
    `.insert.text(...)`, `.retrieve(...)`, `.check_answerable(...)`,
    `.readiness()`, `.initialize()`, `.close()`. The async `SelfGraph`
    class has no top-level `insert_text` method — ingestion lives on
    `sg.insert` (a proxy object). The CLI (`selfgraph insert text /
    retrieve / check-answerable / readiness`) is the documented path.
  - Levels: `light` = regex extraction (deterministic, no LLM, no spaCy);
    `balanced` (default) = spaCy else regex; `max` = LLM extraction.
    Light extraction finds entities but its typed relations are thin —
    the demo's pattern matching therefore uses the structured case fields,
    and the README says so.
  - **Port quirk to verify against a live server:** SelfGraph's docs use
    `HydraDBStore("bolt://127.0.0.1:17687", …)` — port **17687**, while
    HydraDB's own docs use Bolt **7687**. Unresolved which is right for
    0.4.0; treat 17687 as SelfGraph's expectation and check it first.
  - `HydraDBStore` connection attempt to `bolt://127.0.0.1:17687` with no
    server running fails cleanly with connection-refused (Errno 111) —
    i.e. the client code path works, there is just nothing listening.
    That is the expected failure, recorded here, not a bug.

## Learning loop (src/learn.py, synthetic data)

- 200 cases, 30 (payer × CPT) patterns, 160 train / 40 frozen eval.
- Baseline (payer rule lookup): 57.5% accuracy, 40% appeal precision.
- After 10 rounds × 16 appeal outcomes: **77.5% accuracy (+20 pts)**,
  70% precision, appeals filed 20 → 10, 30 path-compression shortcuts.
- Key learned fact: P(appeal wins | doc supplied) = 45.5% vs P(win |
  doc missing) = 10.6%. The missing document is the highest-leverage edge.
- Noise note: rounds 1–4 wobble (small eval set, n=40); the trend, not any
  single round, is the claim. Full numbers in `data/curve.csv`.

## What is NOT verified

- Nothing against a live HydraDB 0.4.0 server (see blocked note above).
- The Cypher in `src/cypher.py` is unexecuted; it follows
  USING-HYDRADB.md's rules but has not been run.
- Railway deploy has not been attempted (needs a Railway account).
- No LLM extraction tier was tested (no LLM key in this sandbox).
