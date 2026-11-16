# Deploy — patient-denialgraph

Status: 2026-11-15, ~4:15pm PT. Deadline 7:30pm PT, target 6:30pm PT.
Nothing here is deployed yet. Nothing was pushed, posted, or submitted.

## Recommended path (do this first)

**Static demo via GitHub Pages.** It is the only path that gives a
submittable live link without a second account, a second service, or a
server. The demo is static (`web/index.html` + `web/demo_data.js` +
`web/curve.png`, no build step, all paths relative), and it was verified
locally on 2026-11-15: HTTP 200 for all three assets when served from
`web/` as root.

Expected live URL (after the steps below):

```
https://ethanthatonekid.github.io/patient-denialgraph/
```

### Step 0 — push (Ethan, your auth)

```bash
cd ~/workspace/hydradb-denialgraph
git push -u origin main
```

The repo is `EthanThatOneKid/patient-denialgraph` (public, empty on
GitHub as of 2026-11-15). The local repo is clean, 4 commits, remote
`origin` already set. Do not push workflow files from the Muse GitHub
App — it has no Workflows permission and the push fails with 403.
That is why the Pages workflow below lives in `deploy/`, not in
`.github/workflows/`.

### Step 1 — add the Pages workflow (Ethan, one file move)

```bash
mkdir -p .github/workflows
cp deploy/pages.yml .github/workflows/pages.yml
git add .github/workflows/pages.yml
git commit -m "Add GitHub Pages deploy for the static demo"
git push
```

`deploy/pages.yml` uploads `web/` as the Pages artifact and deploys
it. It runs on push to `main` and on manual dispatch.

### Step 2 — enable Pages (Ethan, one click, first time only)

Repo → Settings → Pages → **Build and deployment → Source:
GitHub Actions**. (Classic "Deploy from a branch" cannot publish a
`web/` subfolder — that is why the workflow is needed.)

### Step 3 — run it manually (Ethan, do not trust the push trigger)

Repo → Actions → "Deploy demo to GitHub Pages" → **Run workflow**.

Why manual: on 2026-11-15, push-triggered GitHub Pages deploys on
`etok.me` failed (deploy step found 0 artifacts despite a successful
upload — GitHub artifact eventual consistency; a re-run failed with
2 duplicates), while manual dispatch runs worked. After the push,
run it by hand and watch it go green. If a run fails with 0 artifacts,
re-run it manually once; do not push an empty commit to retry.

### Step 4 — verify

```bash
curl -s -o /dev/null -w "index: %{http_code}\n" https://ethanthatonekid.github.io/patient-denialgraph/
curl -s -o /dev/null -w "demo_data.js: %{http_code}\n" https://ethanthatonekid.github.io/patient-denialgraph/demo_data.js
curl -s -o /dev/null -w "curve.png: %{http_code}\n" https://ethanthatonekid.github.io/patient-denialgraph/curve.png
```

All three must be 200. Then open the page in a browser, click
"Sample: MRI denied, no prior auth", and check the graph path,
the win-chance numbers, and the appeal draft all render. If the page
loads but the curve image is missing, the artifact root is wrong —
the workflow must upload `web/`, not the repo root.

## Alternatives for the static demo (if Pages stalls)

Both need Ethan's account login — neither can be done unattended.

**Vercel** (CLI exists in this sandbox, but no login):

```bash
cd web
vercel login        # Ethan, in his own terminal
vercel --prod       # serves web/ as root; URL will be *.vercel.app
```

**Netlify Drop** (browser only): drag the `web/` folder onto
https://app.netlify.com/drop — URL will be `*.netlify.app`. Or,
after `netlify login`:

```bash
cd web
npx netlify deploy --dir=. --prod
```

Either is a fine fallback live link for the submission. The demo
does not need a backend to be submittable — see "What the live link
proves" below.

## Step 2 — live HydraDB 0.4.0 server (Railway; needs Ethan's account)

Do this after the Pages link is live. It is **not** required for a
submittable entry — the demo page is — but it is what makes the
"runs on HydraDB" claim real instead of "Cypher written to the docs,
unexecuted". Full steps in
[`deploy/railway-hydradb-0.4.0.md`](deploy/railway-hydradb-0.4.0.md).

Short version:

1. Open the Railway template
   https://railway.com/deploy/hydradb-v03-graph-database-on-object-storage--hydradb-v03-graph-database-on-object-sto
   and deploy it into a new project.
2. **Do NOT leave it on 0.3.0.** The template pins
   `ghcr.io/hydra-db/hydradb:0.3.0` for both `graph-node` and
   `graph-indexer`. SelfGraph's `HydraDBStore` requires HydraDB
   **≥ 0.4.0**. Change the image tag to `0.4.0` in both services
   (the template doc says the version is pinned by tag and digest in
   `services/hydradb/Dockerfile` — update both, back up the
   `hydradb/` bucket prefix first if any data exists; here it will be
   empty, so a fresh deploy at 0.4.0 is cleanest).
3. Wait until both services are healthy. HydraDB reports healthy only
   after its startup check of the Bucket's conditional writes passes.
4. Copy `HYDRADB_AUTH_TOKEN` and the public domain from the HydraDB
   service, then run the smoke test in
   `deploy/railway-hydradb-0.4.0.md` (write/read/delete a test edge).
   Expected cost per the template doc: ~0.4 GB RAM at idle, roughly
   $5.50/month; ~1.2 GB for a small app graph, roughly $22/month.
   A Railway trial is enough for an evaluation.
5. Seed it with `src/cypher.py` (set `HYDRA_HTTP` to the public URL,
   `HYDRA_TOKEN` to the copied token), then update the demo/README
   to point at the live endpoint.

**Blockers, stated plainly:** Railway needs Ethan's Railway account
and a click in his browser. The template's 0.3.0 pin must be changed
by hand — there is no official 0.4.0 Railway template as of
2026-11-15. The template's S3/Bucket wiring is auto-provisioned by
Railway; the exact bucket env-var names are the template's, not
hand-set, so they are not listed here as copy-paste values. Do not
submit a HydraDB URL you have not smoke-tested.

## What the live link proves (and what it does not)

- The Pages link proves the demo, the curve, and the appeal draft.
  That is the submittable live app.
- It does **not** prove a live HydraDB server. The honest status,
  stated in the README and on the demo page itself: SelfGraph 0.2.1
  is verified end-to-end on embedded Kuzu; HydraDB 0.4.0 exists and
  its image exists; no live HydraDB server was run in the build
  sandbox (no Docker/Rust), and `src/cypher.py` is unexecuted.
- Do not claim otherwise in the submission or the Loom/demo script.

## No public preview link

A self-contained single-file preview of the demo was built locally
(`web/index.html` + inlined `demo_data.js` + base64 `curve.png`,
165,816 bytes, served locally with HTTP 200) and offered for upload
to Hatch storage for a public preview link. The upload was **declined
by Ethan** (approval denied, 2026-11-15 ~4:10pm PT). It was not
retried and the local copy was deleted. There is no public preview
URL. The first public link will be the Pages URL above, after Ethan
pushes and runs the workflow.
