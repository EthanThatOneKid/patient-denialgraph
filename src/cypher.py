#!/usr/bin/env python3
"""HydraDB Cypher schema + HTTP client for patient-first DenialGraph-lite.

STATUS (2026-11-15, verified in this repo — see HYDRA_FINDINGS.md):
  * HydraDB v0.4.0 exists (released 2026-11-14) and its Docker image
    ghcr.io/hydra-db/hydradb:0.4.0 exists. SelfGraph's HydraDBStore
    requires >= 0.4.0, so the version requirement is satisfiable.
  * This sandbox has no Docker and no Rust toolchain, and `apt-get update`
    hung, so no HydraDB server could be started HERE. These statements were
    therefore NOT executed against a live HydraDB in this run.
  * They were written against USING-HYDRADB.md (main branch) and follow its
    rules exactly: MERGE (never bare CREATE) for idempotency, named return
    columns (RETURN * is rejected), no count(DISTINCT ...) (rejected),
    `cell_id` on every HTTP request, node `id` is the upsert key.
  * The learning loop in src/learn.py and the SelfGraph ingest in
    src/ingest_selfgraph.py (Kuzu backend, verified working) use the same
    node/relationship model as below, so swapping the store is mechanical:
    run `bootstrap()` once, then the MERGE statements per case.

Run against a live node:
  1. Start HydraDB 0.4.0 (Docker: ghcr.io/hydra-db/hydradb:0.4.0, or the
     Railway template) with the local-dev defaults from USING-HYDRADB.md.
  2. HYDRA_TOKEN=local-development-token-32-bytes python3 src/cypher.py
"""
import json, os, urllib.request

BASE = os.environ.get("HYDRA_HTTP", "http://127.0.0.1:8443")
GRAPH = os.environ.get("HYDRA_GRAPH", "default")
CELL = os.environ.get("HYDRA_CELL", "cell-0")
TOKEN = os.environ.get("HYDRA_TOKEN", "local-development-token-32-bytes")

# --- Schema: one MERGE per node type, one per relationship type. ---
# Node `id` is the upsert key (a property named `id` on the node itself).
NODE_STATEMENTS = [
    # Patient (synthetic id only — never real PHI)
    "MERGE (p:Patient {id: $patient_id}) "
    "SET p.display_name = $display_name",
    # Claim
    "MERGE (c:Claim {id: $claim_id}) "
    "SET c.billed = $billed, c.service_date = $service_date, c.appeal_won = $appeal_won",
    # Procedure / diagnosis codes
    "MERGE (cpt:CPT {id: $cpt}) SET cpt.name = $cpt_name",
    "MERGE (d:Diagnosis {id: $icd}) SET d.name = $icd_name",
    # Payer, policy, denial reason, document
    "MERGE (pay:Payer {id: $payer})",
    "MERGE (pol:Policy {id: $policy_id}) SET pol.text = $policy_text",
    "MERGE (dr:DenialReason {id: $denial_code}) SET dr.reason = $denial_reason",
    "MERGE (doc:Document {id: $missing_doc})",
]

REL_STATEMENTS = [
    # Claim -> CPT -> DenialReason is the core explanation path
    "MATCH (c:Claim {id: $claim_id}), (cpt:CPT {id: $cpt}) "
    "MERGE (c)-[:HAS_CPT]->(cpt)",
    "MATCH (c:Claim {id: $claim_id}), (d:Diagnosis {id: $icd}) "
    "MERGE (c)-[:HAS_DIAGNOSIS]->(d)",
    "MATCH (c:Claim {id: $claim_id}), (pay:Payer {id: $payer}) "
    "MERGE (c)-[:BILLED_TO]->(pay)",
    "MATCH (pay:Payer {id: $payer}), (pol:Policy {id: $policy_id}) "
    "MERGE (pay)-[:ENFORCES]->(pol)",
    "MATCH (pol:Policy {id: $policy_id}), (dr:DenialReason {id: $denial_code}) "
    "MERGE (pol)-[:CAUSES]->(dr)",
    "MATCH (c:Claim {id: $claim_id}), (dr:DenialReason {id: $denial_code}) "
    "MERGE (c)-[:DENIED_AS]->(dr)",
    "MATCH (dr:DenialReason {id: $denial_code}), (doc:Document {id: $missing_doc}) "
    "MERGE (dr)-[:NEEDS_DOC]->(doc)",
    # Learned edge: reweighted by appeal outcomes (see src/learn.py).
    # weight = Bayesian-smoothed P(appeal wins | payer, CPT, denial).
    "MATCH (cpt:CPT {id: $cpt}), (dr:DenialReason {id: $denial_code}) "
    "MERGE (cpt)-[r:DENIED_AS {payer: $payer}]->(dr) "
    "SET r.win_rate = $win_rate, r.observations = $observations",
    # Path compression: frequent chain collapsed to a 1-hop shortcut.
    "MATCH (cpt:CPT {id: $cpt}), (dr:DenialReason {id: $denial_code}) "
    "MERGE (cpt)-[:FREQUENTLY_DENIED_AS {payer: $payer}]->(dr)",
]

# --- Reads: the queries the demo actually runs. ---
# Explanation path for one claim (bounded, named columns only).
EXPLAIN_QUERY = """
MATCH (c:Claim {id: $claim_id})-[:HAS_CPT]->(cpt:CPT),
      (c)-[:BILLED_TO]->(pay:Payer)-[:ENFORCES]->(pol:Policy)-[:CAUSES]->(dr:DenialReason),
      (dr)-[:NEEDS_DOC]->(doc:Document)
RETURN c.id AS claim, cpt.id AS cpt, cpt.name AS procedure,
       pay.id AS payer, pol.id AS policy, pol.text AS policy_text,
       dr.reason AS denial_reason, doc.id AS missing_doc
"""

# Best appeal precedent: same payer + CPT + denial, appeals that won.
# (No count(DISTINCT ...) — HydraDB rejects it; count the rows instead.)
APPEAL_PRECEDENT_QUERY = """
MATCH (cpt:CPT {id: $cpt})-[r:DENIED_AS {payer: $payer}]->(dr:DenialReason {id: $denial_code})
RETURN r.win_rate AS win_rate, r.observations AS observations
"""

# Native path procedure: bounded paths from a claim to its denial reason.
# algo.SSpaths avoids client-side fan-out for multi-hop explanation paths.
PATH_QUERY = "CALL algo.SSpaths($claim_id, 3)"


def http_query(cypher, params=None):
    """POST one Cypher statement to the HydraDB HTTP query API."""
    body = json.dumps({
        "cell_id": CELL,
        "query": cypher,
        "parameters": params or {},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/graphs/{GRAPH}/query", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def health():
    with urllib.request.urlopen(f"{BASE}/healthz", timeout=10) as resp:
        return resp.status, json.load(resp)


def bootstrap(cases):
    """Create all nodes/relationships for the synthetic cases (idempotent)."""
    for c in cases:
        p = {
            "patient_id": c["claim_id"] + "-patient",
            "display_name": c["patient"],
            "claim_id": c["claim_id"], "billed": c["billed"],
            "service_date": c["service_date"], "appeal_won": c["appeal_won"],
            "cpt": c["cpt"], "cpt_name": c["cpt_name"],
            "icd": c["icd"], "icd_name": c["icd_name"],
            "payer": c["payer"], "policy_id": c["policy_id"],
            "policy_text": c["policy_text"],
            "denial_code": c["denial_code"], "denial_reason": c["denial_reason"],
            "missing_doc": c["missing_doc"],
            "win_rate": 0.5, "observations": 0,
        }
        for stmt in NODE_STATEMENTS + REL_STATEMENTS:
            http_query(stmt, p)
    print(f"bootstrapped {len(cases)} cases into HydraDB graph={GRAPH} cell={CELL}")


if __name__ == "__main__":
    print("health:", health())
    cases = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                        "data", "cases.json")))
    bootstrap(cases)
    print("explain sample:",
          http_query(EXPLAIN_QUERY, {"claim_id": cases[0]["claim_id"]}))
