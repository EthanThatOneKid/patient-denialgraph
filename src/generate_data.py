#!/usr/bin/env python3
"""Generate synthetic patient denial cases (NO real PHI — fully invented).

Patient-first DenialGraph-lite: each case is a patient-facing denial.
30 patterns = 5 payers x 6 procedure types. Each (payer, CPT) combo has its
own true appeal-win rate (drawn around a per-procedure mean), so the graph
has something real to learn over rounds: a coarse payer-rule baseline cannot
see per-combo rates, but the graph's edge weights converge to them.
"""
import json, random, os

random.seed(20261115)
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "denial_letters"), exist_ok=True)

PAYERS = ["Aetna", "UnitedHealthcare", "Blue Cross Blue Shield", "Cigna",
          "Kaiser Permanente"]

# cpt, name, icd, icd_name, policy, policy_text, denial, code, missing_doc,
# mean_win_rate_when_doc_supplied, billed
CPT_TYPES = [
    ("70553", "MRI brain w/o contrast", "G44.1", "Vascular headache",
     "PA-101", "Prior authorization required for advanced imaging",
     "No prior authorization", "CO-197", "prior-authorization letter", 0.80, 1450),
    ("64490", "Facet joint injection", "M47.816", "Lumbar spondylosis",
     "EXP-44", "Facet injections considered experimental without failed conservative care",
     "Experimental / investigational", "CO-50", "peer-reviewed evidence + PT records", 0.60, 890),
    ("99214", "Office visit, established patient", "M54.5", "Low back pain",
     "MEDNEC-22", "Visit must document medical necessity for level-4 coding",
     "Not medically necessary as coded", "CO-50", "clinical notes supporting level 4", 0.73, 210),
    ("80053", "Comprehensive metabolic panel", "E11.9", "Type 2 diabetes",
     "DUP-07", "Same lab on same date already paid",
     "Duplicate claim", "CO-18", "proof this was a distinct repeat test", 0.18, 95),
    ("93000", "Electrocardiogram", "I25.10", "Atherosclerotic heart disease",
     "OON-12", "Service outside network without referral",
     "Out of network", "CO-109", "in-network exception / continuity-of-care letter", 0.65, 180),
    ("36415", "Venipuncture / blood draw", "Z00.00", "Routine general exam",
     "TIMELY-03", "Claim filed after timely-filing deadline",
     "Timely filing exceeded", "CO-29", "proof of timely filing / clearinghouse receipt", 0.22, 45),
]

# 30 (payer, CPT) combos, each with its own true win rate
PATTERNS = []
for payer in PAYERS:
    for t in CPT_TYPES:
        mean = t[9]
        base = min(0.90, max(0.10, random.gauss(mean, 0.12)))
        PATTERNS.append((payer,) + t + (round(base, 2),))

FIRST = ["Alex", "Maria", "James", "Priya", "Chen", "Fatima", "Jordan", "Sofia",
         "Marcus", "Elena", "David", "Aisha", "Tom", "Nadia", "Sam", "Grace"]
LAST_INIT = ["R.", "G.", "K.", "M.", "T.", "S.", "L.", "P.", "W.", "H."]


def make_letter(c):
    return (
        f"Dear {c['patient']},\n\n"
        f"We have reviewed your claim {c['claim_id']} for services on {c['service_date']}.\n"
        f"Your {c['cpt_name']} (CPT {c['cpt']}) for {c['icd_name']} (ICD {c['icd']}) "
        f"has been denied by {c['payer']}.\n\n"
        f"Reason: {c['denial_reason']} (code {c['denial_code']}).\n"
        f"Policy: {c['policy_id']} — {c['policy_text']}.\n"
        f"Billed amount: ${c['billed']:.2f}. Patient responsibility if unpaid: ${c['billed']:.2f}.\n\n"
        f"You have the right to appeal within 180 days. An appeal is most likely to succeed "
        f"if you include: {c['missing_doc']}.\n"
        f"Appeal address: {c['payer']} Appeals Department, PO Box 1000.\n\n"
        f"Sincerely,\n{c['payer']} Claims Review\n"
    )


def make_eob(c):
    return (
        f"EOB {c['claim_id']} | {c['payer']} | {c['service_date']} | "
        f"CPT {c['cpt']} {c['cpt_name']} | ICD {c['icd']} | "
        f"Billed ${c['billed']:.2f} | Allowed $0.00 | Denied: {c['denial_reason']} ({c['denial_code']})"
    )


cases = []
for i in range(200):
    p = PATTERNS[i % len(PATTERNS)]
    (payer, cpt, cpt_name, icd, icd_name, pol, pol_text,
     reason, code, doc, _mean, billed, base_rate) = p
    doc_supplied = random.random() < 0.55
    if doc_supplied:
        won = random.random() < base_rate
    else:
        won = random.random() < 0.08
    billed_amt = round(billed * random.uniform(0.9, 1.15), 2)
    c = {
        "case_id": f"DG-{i+1:03d}",
        "claim_id": f"CLM-{100000+i}",
        "patient": f"{random.choice(FIRST)} {random.choice(LAST_INIT)}",
        "payer": payer, "cpt": cpt, "cpt_name": cpt_name,
        "icd": icd, "icd_name": icd_name,
        "policy_id": pol, "policy_text": pol_text,
        "denial_reason": reason, "denial_code": code,
        "missing_doc": doc, "doc_supplied": doc_supplied,
        "appeal_won": won, "billed": billed_amt,
        "base_win_rate": base_rate,
        "service_date": f"2026-{random.randint(1,10):02d}-{random.randint(1,28):02d}",
        "split": "eval" if i >= 160 else "train",
    }
    c["denial_letter"] = make_letter(c)
    c["eob"] = make_eob(c)
    cases.append(c)
    with open(os.path.join(OUT, "denial_letters", f"{c['case_id']}.txt"), "w") as f:
        f.write(c["denial_letter"])

with open(os.path.join(OUT, "cases.json"), "w") as f:
    json.dump(cases, f, indent=2)

train = [c for c in cases if c["split"] == "train"]
ev = [c for c in cases if c["split"] == "eval"]
print(f"cases: {len(cases)} (train {len(train)}, eval {len(ev)}), patterns: {len(PATTERNS)}")
print(f"train appeal-win rate: {sum(c['appeal_won'] for c in train)/len(train):.3f}")
print(f"eval  appeal-win rate: {sum(c['appeal_won'] for c in ev)/len(ev):.3f}")
print(f"doc-supplied win rate: "
      f"{sum(c['appeal_won'] for c in cases if c['doc_supplied'])/sum(1 for c in cases if c['doc_supplied']):.3f}")
print(f"doc-missing  win rate: "
      f"{sum(c['appeal_won'] for c in cases if not c['doc_supplied'])/sum(1 for c in cases if not c['doc_supplied']):.3f}")
print(f"total billed in eval set: ${sum(c['billed'] for c in ev):,.2f}")
