#!/usr/bin/env python3
"""Ingest denial letters into SelfGraph (Kuzu embedded backend).

Proves, end to end and without an LLM:
  * unstructured text in -> entities/relations out (light level = regex)
  * every fact keeps its source (denial letter id)
  * versioning: a payer policy update retires the old rule; as-of retrieval
    shows the graph as it was known before the update
  * answerability: the graph knows when it cannot answer a question

Usage: .venv/bin/python src/ingest_selfgraph.py [--full]
Default ingests 10 letters (fast smoke test); --full ingests all 200.
"""
import json, os, sys, time

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")

from selfgraph import SyncSelfGraph, KuzuStore  # noqa: E402


def main():
    full = "--full" in sys.argv
    cases = json.load(open(os.path.join(ROOT, "data", "cases.json")))
    sample = cases if full else cases[:10]
    sg = SyncSelfGraph(store=KuzuStore(os.path.join(ROOT, "data", "selfgraph-kuzu")),
                       level="light")
    sg.initialize()
    t0 = time.time()
    for c in sample:
        sg.insert.text(c["denial_letter"], source_id=c["case_id"],
                       event_time=c["service_date"] + "T00:00:00Z")
    print(f"inserted {len(sample)} letters in {time.time()-t0:.1f}s")

    # Versioning demo: Aetna retires PA-101 (prior auth for MRI) on 2026-11-01
    sg.insert.text(
        "Aetna policy update, effective 2026-11-01: Policy PA-101, prior "
        "authorization required for advanced imaging, is retired and replaced "
        "by policy PA-102, prior authorization required only for MRI with "
        "contrast. MRI brain without contrast (CPT 70553) no longer requires "
        "prior authorization.",
        source_id="AETNA-POLICY-2026-11-01", event_time="2026-11-01T00:00:00Z",
        contradiction="supersede")
    print("policy update inserted (PA-101 retired, PA-102 supersedes)")

    q = "Why was claim CLM-100000 denied by Aetna?"
    now = sg.retrieve(q, depth=3)
    print("\n--- retrieve (current) ---")
    print("context chars:", len(now.context or ""))
    print((now.context or "")[:600])
    then = sg.retrieve(q, depth=3, as_of="2026-06-01T00:00:00Z")
    print("\n--- retrieve (as_of 2026-06-01) ---")
    print("context chars:", len(then.context or ""))

    for question in ["Why was claim CLM-100000 denied?",
                     "What is the staff size of Aetna by ad spend?"]:
        rep = sg.check_answerable(question)
        print(f"\ncheck_answerable({question!r}) -> verdict={rep.verdict} "
              f"missing={getattr(rep, 'missing', None)}")

    ready = sg.readiness()
    print("\n--- readiness ---")
    print(json.dumps(ready if isinstance(ready, dict) else ready.__dict__,
                     indent=2, default=str)[:900])
    sg.close()


if __name__ == "__main__":
    main()
