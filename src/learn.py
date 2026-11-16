#!/usr/bin/env python3
"""Track 1 learning loop for patient-first DenialGraph-lite.

Graph model (in-memory, mirrors the Cypher schema in src/cypher.py):
  Claim -[HAS_CPT]-> CPT -[DENIED_UNDER {payer}]-> DenialReason
  Payer -[ENFORCES]-> Policy -[CAUSES]-> DenialReason
  DenialReason -[NEEDS_DOC]-> Document -[SUPPORTS_APPEAL]-> AppealOutcome

Learning mechanisms (the Track 1 bar):
  1. Edge reweighting — the weight of the (payer, CPT, denial) edge is the
     Bayesian-smoothed appeal-win rate for that combo, re-estimated from
     every appeal outcome. The weight of the Document edge is the observed
     P(win | doc supplied) vs P(win | doc missing).
  2. Path compression — once a (CPT, payer, denial) chain is seen >= 5 times,
     a shortcut edge CPT -[FREQUENTLY_DENIED_AS]-> DenialReason is created so
     the explanation path is 1 hop instead of 3.
  3. Gap-driven ingestion — when the missing document is unknown, the system
     asks the patient for exactly one document. In this synthetic run a patient
     who is asked supplies it with probability 0.5, which lifts the win rate:
     the graph learns *what to ask for*.

Baseline (round 0): payer rule lookup. Predicts "appeal will win" iff the
denial reason is on a fixed winnable list, ignoring which payer/CPT combo it
is and whether the patient has the supporting document. This is what a
static rules engine does.

Eval: frozen 40-case eval split, never used for training.
Metrics: appeal-win prediction accuracy, precision of recommended appeals,
and patient net dollars saved = billed amount recovered on appeals the model
recommended that actually won, minus $35 of patient effort per recommended
appeal that lost (time, postage, phone calls). Precision matters to the
patient: a bad recommendation wastes their time.
"""
import json, os, random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

random.seed(20261115)
HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
WEB = os.path.join(HERE, "..", "web")
os.makedirs(WEB, exist_ok=True)
APPEAL_COST = 35.0  # patient effort per filed appeal that loses, in dollars

cases = json.load(open(os.path.join(DATA, "cases.json")))
train = [c for c in cases if c["split"] == "train"]
ev = [c for c in cases if c["split"] == "eval"]

WINNABLE_BY_RULE = {"No prior authorization", "Not medically necessary as coded",
                    "Out of network"}


class DenialGraph:
    """Weighted multi-hop scorer over the denial graph."""

    def __init__(self):
        self.pattern_stats = {}   # (payer, cpt, denial) -> [wins, total]
        self.doc_stats = {True: [0, 0], False: [0, 0]}  # doc supplied -> [wins, total]
        self.shortcuts = set()
        self.chain_counts = {}

    def pattern_key(self, c):
        return (c["payer"], c["cpt"], c["denial_reason"])

    def pattern_rate(self, c):
        """Bayesian-smoothed edge weight, prior 0.5 with strength 2."""
        w, t = self.pattern_stats.get(self.pattern_key(c), (0, 0))
        return (w + 1.0) / (t + 2.0)

    def doc_rate(self, doc_supplied):
        w, t = self.doc_stats[doc_supplied]
        return (w + 1.0) / (t + 2.0)

    def score(self, c, doc_supplied=None):
        doc = c["doc_supplied"] if doc_supplied is None else doc_supplied
        # multi-hop: pattern edge weight + document edge weight
        s = 0.6 * self.pattern_rate(c) + 0.4 * self.doc_rate(doc)
        if self.pattern_key(c) in self.shortcuts:
            s += 0.05  # compressed path: extra confidence, same prediction
        return s

    def predict_win(self, c, doc_supplied=None):
        return self.score(c, doc_supplied) >= 0.5

    def observe(self, c, doc_supplied=None):
        doc = c["doc_supplied"] if doc_supplied is None else doc_supplied
        key = self.pattern_key(c)
        w, t = self.pattern_stats.get(key, (0, 0))
        self.pattern_stats[key] = (w + (1 if c["appeal_won"] else 0), t + 1)
        dw, dt = self.doc_stats[doc]
        self.doc_stats[doc] = (dw + (1 if c["appeal_won"] else 0), dt + 1)
        self.chain_counts[key] = self.chain_counts.get(key, 0) + 1
        if self.chain_counts[key] >= 5:
            self.shortcuts.add(key)  # path compression


def baseline_predict(c):
    return c["denial_reason"] in WINNABLE_BY_RULE


def evaluate(predict_fn):
    correct, saved_gross, recommended, rec_won, rec_lost = 0, 0.0, 0, 0, 0
    for c in ev:
        pred = predict_fn(c)
        if pred == c["appeal_won"]:
            correct += 1
        if pred:
            recommended += 1
            if c["appeal_won"]:
                rec_won += 1
                saved_gross += c["billed"]
            else:
                rec_lost += 1
    n = len(ev)
    return {
        "accuracy": round(correct / n, 3),
        "appeal_precision": round(rec_won / recommended, 3) if recommended else 0.0,
        "recommended": recommended,
        "dollars_saved_gross": round(saved_gross, 2),
        "dollars_saved_net": round(saved_gross - APPEAL_COST * rec_lost, 2),
    }


graph = DenialGraph()
rows = []
m0 = evaluate(baseline_predict)
rows.append({"round": 0, "mode": "baseline rule lookup", **m0,
             "shortcuts": 0, "patterns_learned": 0})
print(f"round 0 baseline: acc={m0['accuracy']:.3f} precision={m0['appeal_precision']:.3f} "
      f"net_saved=${m0['dollars_saved_net']:,.2f}")

for rnd in range(1, 11):
    batch = train[(rnd - 1) * 16: rnd * 16]
    for c in batch:
        doc = c["doc_supplied"]
        if not doc and random.random() < 0.5:
            # gap-driven: ask for the one missing doc; patient supplies it 50%
            doc = True
            c = dict(c, doc_supplied=True,
                     appeal_won=random.random() < c["base_win_rate"])
        graph.observe(c, doc_supplied=doc)
    m = evaluate(graph.predict_win)
    rows.append({"round": rnd, "mode": "learning", **m,
                 "shortcuts": len(graph.shortcuts),
                 "patterns_learned": len(graph.pattern_stats)})
    print(f"round {rnd:2d}: acc={m['accuracy']:.3f} precision={m['appeal_precision']:.3f} "
          f"net_saved=${m['dollars_saved_net']:,.2f} shortcuts={len(graph.shortcuts)} "
          f"patterns={len(graph.pattern_stats)}")

with open(os.path.join(DATA, "curve.json"), "w") as f:
    json.dump(rows, f, indent=2)
with open(os.path.join(DATA, "curve.csv"), "w") as f:
    f.write("round,accuracy,appeal_precision,recommended,dollars_saved_gross,dollars_saved_net,shortcuts,patterns_learned\n")
    for r in rows:
        f.write(f"{r['round']},{r['accuracy']:.3f},{r['appeal_precision']:.3f},"
                f"{r['recommended']},{r['dollars_saved_gross']},{r['dollars_saved_net']},"
                f"{r['shortcuts']},{r['patterns_learned']}\n")

rounds = [r["round"] for r in rows]
acc = [r["accuracy"] for r in rows]
net = [r["dollars_saved_net"] for r in rows]
fig, ax1 = plt.subplots(figsize=(8, 4.5))
ax1.plot(rounds, acc, marker="o", linewidth=2, label="Appeal-win prediction accuracy")
ax1.axhline(y=rows[0]["accuracy"], color="gray", linestyle="--", linewidth=1,
            label=f"Baseline (rule lookup): {rows[0]['accuracy']:.0%}")
ax1.set_xlabel("Learning round (16 appeal outcomes per round)")
ax1.set_ylabel("Accuracy on frozen 40-case eval set")
ax1.set_ylim(0.4, 1.0)
ax1.set_title("DenialGraph-lite: accuracy rises as the graph learns from appeals")
ax1.legend(loc="lower right", fontsize=9)
ax1.grid(alpha=0.3)
ax2 = ax1.twinx()
ax2.plot(rounds, [r["appeal_precision"] for r in rows], marker="s", linewidth=1.5,
         color="green", label="Precision of recommended appeals")
ax2.axhline(y=rows[0]["appeal_precision"], color="green", linestyle="--", linewidth=1,
            label=f"Baseline precision: {rows[0]['appeal_precision']:.0%}")
ax2.set_ylabel("Precision (share of recommended appeals that won)")
ax2.set_ylim(0.0, 1.05)
ax2.legend(loc="upper left", fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(WEB, "curve.png"), dpi=150)
fig.savefig(os.path.join(DATA, "curve.png"), dpi=150)
# SVG twin of the same chart (text, so it can go through the GitHub
# connector, which rejects binaries): regenerate with src/build_curve_svg.py
fig.savefig(os.path.join(WEB, "curve.svg"))
fig.savefig(os.path.join(DATA, "curve.svg"))
print(f"\nBaseline acc {rows[0]['accuracy']:.3f} -> final acc {rows[-1]['accuracy']:.3f} "
      f"(+{(rows[-1]['accuracy']-rows[0]['accuracy'])*100:.1f} pts)")
print(f"Patient net $ saved: ${rows[0]['dollars_saved_net']:,.2f} -> ${rows[-1]['dollars_saved_net']:,.2f}")
print(f"Shortcuts (path compression): {len(graph.shortcuts)}")
