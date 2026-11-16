#!/usr/bin/env python3
"""Build web/demo_data.js: learned pattern weights + samples, embedded in the demo.

Pattern win rates use the same Bayesian smoothing as src/learn.py
(prior 0.5, strength 2) over all 200 synthetic cases, so the demo's
numbers match the learning loop's final state.
"""
import json, os

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
cases = json.load(open(os.path.join(ROOT, "data", "cases.json")))
curve = json.load(open(os.path.join(ROOT, "data", "curve.json")))

patterns = {}
doc_stats = {True: [0, 0], False: [0, 0]}
for c in cases:
    k = f"{c['payer']}|{c['cpt']}|{c['denial_reason']}"
    w, t = patterns.get(k, (0, 0))
    patterns[k] = (w + (1 if c["appeal_won"] else 0), t + 1)
    dw, dt = doc_stats[c["doc_supplied"]]
    doc_stats[c["doc_supplied"]] = (dw + (1 if c["appeal_won"] else 0), dt + 1)

out = {"patterns": {}, "docRates": {}, "curve": curve,
       "samples": []}
for k, (w, t) in sorted(patterns.items()):
    payer, cpt, denial = k.split("|")
    out["patterns"][k] = {
        "payer": payer, "cpt": cpt, "denial": denial,
        "winRate": round((w + 1) / (t + 2), 3), "wins": w, "total": t,
    }
for doc, (w, t) in doc_stats.items():
    out["docRates"]["supplied" if doc else "missing"] = {
        "winRate": round((w + 1) / (t + 2), 3), "wins": w, "total": t}

for c in cases[:3]:
    out["samples"].append({
        "caseId": c["case_id"], "letter": c["denial_letter"],
        "payer": c["payer"], "cpt": c["cpt"], "cptName": c["cpt_name"],
        "icd": c["icd"], "icdName": c["icd_name"],
        "policyId": c["policy_id"], "policyText": c["policy_text"],
        "denialReason": c["denial_reason"], "denialCode": c["denial_code"],
        "missingDoc": c["missing_doc"], "billed": c["billed"],
        "appealWon": c["appeal_won"],
    })

with open(os.path.join(ROOT, "web", "demo_data.js"), "w") as f:
    f.write("window.DENIALGRAPH = ")
    json.dump(out, f, indent=1)
    f.write(";\n")
print(f"patterns: {len(out['patterns'])}, samples: {len(out['samples'])}")
print("doc rates:", out["docRates"])
print(f"curve: baseline {curve[0]['accuracy']} -> final {curve[-1]['accuracy']}")
