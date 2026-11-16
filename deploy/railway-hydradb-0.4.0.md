# Live HydraDB 0.4.0 on Railway — step by step

Status: 2026-11-15. **Not attempted.** Needs Ethan's Railway account
and clicks in his browser. Do this after the GitHub Pages link is live
(see `../DEPLOY.md`).

## 0. The one thing that will go wrong if you skip it

The official Railway template pins **HydraDB 0.3.0**:

- Template: https://railway.com/deploy/hydradb-v03-graph-database-on-object-storage--hydradb-v03-graph-database-on-object-sto
- It runs `ghcr.io/hydra-db/hydradb:0.3.0` for `graph-node` and
  `graph-indexer`, with a Railway Bucket as the store.
- SelfGraph's `HydraDBStore` requires HydraDB **>= 0.4.0**.
- **Do not submit a 0.3.0 deployment.** Deploy the template, then
  change the image tag to `0.4.0` in both services before seeding
  anything. The template doc says the version is pinned by tag and
  digest in `services/hydradb/Dockerfile` — update both. There is no
  official 0.4.0 Railway template as of 2026-11-15. Since the graph
  will be empty at first deploy, a fresh deploy at 0.4.0 is cleanest;
  if data ever exists, back up the `hydradb/` bucket prefix first
  (HydraDB is pre-1.0).

Verified 2026-11-15: `v0.4.0` was released 2026-11-14T02:32:46Z and
`ghcr.io/hydra-db/hydradb:0.4.0` exists on GHCR (tags list includes
`0.4.0, 0.4, 0.3.0, 0.3, 0.2.0, latest`).

## 1. Deploy the template (Ethan, browser)

1. Open the template link above, sign in to Railway, deploy into a
   new project. No input is required: the token is generated and the
   Bucket is created and connected.
2. What you get (per the template doc):
   - `HydraDB` service — `graph-node`: Bolt 7687, HTTP query API
     8443, admin/metrics 9090 (all private except the HTTPS domain,
     which routes to 8443, bearer token required). Volume
     `/var/cache/slatedb` (cache only, disposable).
   - `HydraDB Indexer` service — `graph-indexer`: builds and
     publishes traversal indexes; admin/metrics on 9091 (private).
   - `Bucket` — Railway Bucket (S3-compatible) holding all graph
     data under the `hydradb/` prefix. This is the source of truth;
     the volume is only a cache.
3. Change both services' image tag from `0.3.0` to `0.4.0` and
   redeploy.
4. Wait until both services are healthy. HydraDB reports healthy
   only after its startup check of the Bucket's conditional writes
   has passed. If it never turns healthy, check the node logs for
   the bucket check and the token file — do not seed until healthy.

Cost per the template doc: ~0.4 GB RAM at idle, roughly $5.50/month
including volume and polling egress; ~1.2 GB for a small app graph,
roughly $22/month. A Railway trial is enough for an evaluation.

## 2. Connection values the template exposes

Copy these from the HydraDB service after deploy (do not guess them):

- `HYDRADB_AUTH_TOKEN` — generated token, at least 32 chars
  (letters, digits, `. _ ~ -`). The Indexer references the same
  token. Rotating it means redeploying HydraDB, the Indexer, and
  every service that references it.
- `HYDRADB_URL` / `HYDRADB_QUERY_URL` — e.g.
  `${{HydraDB.HYDRADB_PUBLIC_URL}}/v1/graphs/default/query`
  (HTTPS; Railway terminates TLS at the edge).
- Bolt (Neo4j drivers, private network only):
  `NEO4J_URI` = `bolt://hydradb.railway.internal:7687`,
  `NEO4J_USERNAME` = `neo4j` (by convention), `NEO4J_PASSWORD` =
  the token, `NEO4J_DATABASE` = `default`.
- `HYDRADB_HOST`, `HYDRADB_METRICS_URL` (Prometheus, private).

Known template variables (from the template doc — these are the
template's own, mostly `auto`):

| Variable | Default | Meaning |
|---|---|---|
| `HYDRADB_S3_ADDRESSING` | `virtual` | Railway Buckets use `https://{bucket}.{endpoint}`. Set `path` for older buckets, as their Credentials tab says. |
| `GRAPH_SLATE_DB_CACHE_BYTES` | `auto` | RAM cache: 5/16 of memory limit, 64 MiB–2 GiB. |
| `GRAPH_DATA_CACHE_BYTES` | `auto` | Disk cache on the volume: 75% of the volume, 64 MiB–8 GiB. |
| `GRAPH_MAX_GRAPHBLAS_BYTES` | `auto` | GraphBLAS traversal memory: 1/16 of memory limit, 32–512 MiB. |
| `HYDRADB_MEMORY_LIMIT_MB`, `HYDRADB_CPU_LIMIT` | `auto` | What the auto sizes are based on; 2 GiB assumed if Railway exposes no limit. |
| `GRAPH_INDEXER_BUILD_MODE` | `full` | On the Indexer; `incremental` reuses the previous index generation for large graphs. |
| `HYDRADB_CACHE_RESET` | `false` | Set `true` for one deploy if the Bucket was emptied, then back to `false`. |

The Bucket's S3 credentials are auto-provisioned by the template —
they are not hand-set env vars, so they are not listed here as
copy-paste values. If you deploy the image outside the template,
you will need the S3-mode env vars yourself; those are not in the
v0.4.0 `USING-HYDRADB.md` (it covers the client side only) — check
the template's service definitions or the `graph-node --help` output
before inventing any.

## 3. Smoke test (run from your laptop, after healthy)

```bash
TOKEN='<paste HYDRADB_AUTH_TOKEN>'
URL='https://{your-domain}/v1/graphs/default/query'

q() { curl -sS "$URL" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data "{\"cell_id\":\"cell-0\",\"query\":\"$1\"}"; echo; }

q 'MERGE (a {id: 1})-[:FOLLOWS]->(b {id: 2})'
q 'MATCH (a {id: 1})-[:FOLLOWS]->(b) RETURN b.id AS id'
q 'MATCH (a {id: 1}) DETACH DELETE a'
q 'MATCH (a {id: 2}) DETACH DELETE a'
```

The second call must return one row:
`{"type":"vertex_id","value":2}`. No token → `401 unauthenticated`.
`GET /healthz` on the public domain answers without a token.
Every HTTP request needs `cell_id` (`cell-0` here); a wrong one
returns an opaque HTTP 500, not a helpful error.

## 4. Seed it with this repo's graph

```bash
cd ~/workspace/hydradb-denialgraph   # after `git push`, this is the same code
HYDRA_HTTP='https://{your-domain}' \
HYDRA_TOKEN='<paste HYDRADB_AUTH_TOKEN>' \
python3 src/cypher.py
```

`src/cypher.py` uses `HYDRA_HTTP` (default `http://127.0.0.1:8443`),
`HYDRA_GRAPH` (default `default`), `HYDRA_CELL` (default `cell-0`),
`HYDRA_TOKEN`. It is MERGE-only, so re-running it is safe.
**It has never been executed against a live HydraDB** (no Docker/Rust
in the build sandbox) — the first live run is the test. If it fails,
read the error envelope: 400 = parse/unsupported construct, 401 =
token, 422 = malformed body (usually missing `cell_id`), 500 =
server-side (often a wrong `cell_id`).

## 5. Local Docker alternative (same image, no Railway)

Verified env vars, from `hydra-db/hydradb` v0.4.0 `README.md`,
"Run a local server" (local-directory store, plaintext dev only):

```bash
mkdir -p .hydradb/store .hydradb/cache
printf '%s\n' 'local-development-token-32-bytes' > .hydradb/auth-token

export CLOUD_PROVIDER=local
export LOCAL_PATH="$PWD/.hydradb/store"
export GRAPH_NAMESPACE=default
export GRAPH_ID=default
export GRAPH_CELL_ID=cell-0
export GRAPH_CELLS=cell-0
export GRAPH_NODE_ID=node-0
export GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687
export GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687
export GRAPH_DATA_CACHE_DIR="$PWD/.hydradb/cache"
export GRAPH_AUTH_TOKEN_FILE="$PWD/.hydradb/auth-token"
export GRAPH_ALLOW_PLAINTEXT=true
export RUST_MIN_STACK=33554432   # async query futures overflow the default stack
```

With Docker instead of `cargo run`, the same env vars go on the
`ghcr.io/hydra-db/hydradb:0.4.0` image with ports 7687/8443/9090
published and a volume for the store/cache. The image's entrypoint
runs `graph-node`; run a second container with the same env vars for
`graph-indexer`. This path was not executed here (no Docker in the
sandbox) — treat the first run as a test, same as Railway.

Ports: Bolt `127.0.0.1:7687`, HTTP `127.0.0.1:8443`
(`POST /v1/graphs/{graph_id}/query`, `GET /healthz`), Admin
`127.0.0.1:9090` (`GET /readyz` returns 200 with an empty body,
`GET /metrics`). `/healthz` and `/readyz` are on different ports and
are not interchangeable.

## 6. Open quirks (do not paper over these)

- **Bolt port:** SelfGraph's docs use
  `HydraDBStore("bolt://127.0.0.1:17687", …)` — port **17687** —
  while HydraDB's own docs use Bolt **7687**. Unresolved which is
  right for 0.4.0. Try 17687 first for SelfGraph (it is SelfGraph's
  expectation), fall back to 7687, and record which worked.
- **Bolt through a TCP proxy (optional):** add a TCP proxy on 7687
  and connect `bolt://{proxy-domain}:{proxy-port}` (not `neo4j://`).
  Without TLS the token crosses the internet in clear text.
  `HYDRADB_TLS=self-signed` encrypts it (`bolt+ssc://`), but then
  HTTP requires TLS too and the public HTTPS domain stops working.
- **Backups:** Railway Buckets have no versioning or automatic
  backups. Back up by copying the `hydradb/` prefix with an S3 tool
  such as rclone, ideally with HydraDB stopped.
- **Token rotation:** set a new `HYDRADB_AUTH_TOKEN` (≥32 chars,
  letters/digits/`. _ ~ -`), then redeploy HydraDB, the Indexer, and
  every service referencing it.
