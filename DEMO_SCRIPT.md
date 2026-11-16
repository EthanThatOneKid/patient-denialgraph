# Demo script — patient-denialgraph walkthrough

Target: 3 minutes. Read it word for word. Plain short sentences.
All data is synthetic. No real PHI. No medical or legal advice.

## 0:00-0:20 — The problem, first

[On screen: a denial letter, full screen.]

Hi, I am Ethan Davidson. This is DenialGraph.

You get a letter like this. Your claim was denied. The letter is hard to read. You do not know why. You do not know what to do next.

Most people give up here.

## 0:20-0:45 — Why this happens

[On screen: the same letter, with the denial code highlighted.]

Most denials are not fraud. They are small errors. The wrong code. A missing document. A rule the patient never saw.

Industry reports say about 65 percent of denied claims are never resubmitted. About 90 percent are considered preventable. The patient loses. The clinic loses time too.

## 0:45-1:30 — The demo

[On screen: web/index.html. Paste a sample denial letter.]

Here is what I built. Paste the letter in. The graph reads it.

It shows the path. Claim to CPT code to payer to policy to denial reason. You can see why it denied. It also shows the one missing document.

With that document, the win chance in our test data is 45.5 percent. Without it, it is 10.6 percent. That is the whole point. The graph asks for the one thing that matters.

Then it drafts the appeal. You can edit it right in the page, hit Shorter or Firmer or Emphasize the document to revise it, then copy it and send it.

## 1:30-2:15 — It learns

[On screen: web/curve.png, the learning curve.]

This is Track 1. The graph learns from its own answers.

We tested it on 200 synthetic cases. 40 were held out and never trained on. The baseline is a simple payer rule lookup. It gets 57.5 percent right.

After 10 rounds of appeal outcomes, the graph gets 77.5 percent right. That is 20 points better.

Precision goes from 40 percent to 70 percent. Appeals filed go from 20 to 10. The dollars recovered are about the same, around 6,700 dollars. The graph does not invent money. It stops patients from wasting appeals that will not win.

It learns in three ways. Edge reweighting. Path compression. And gap-driven questions for the missing document.

## 2:15-2:45 — How it works

[On screen: README stack section, then HYDRA_FINDINGS.md.]

The stack is HydraDB and SelfGraph. SelfGraph turns the letters into a graph. Every fact keeps its source. When a policy changes, the old rule retires. You can ask the graph as it was on an earlier date.

HydraDB 0.4.0 came out on November 14. SelfGraph needs 0.4.0 or newer. That version exists. I verified SelfGraph end to end on embedded Kuzu. 200 letters in 81 seconds. Retrieval returns the source text. The answerability check reports gaps instead of inventing an answer.

One honest limit. No live HydraDB server ran in my sandbox. There was no Docker there. The Cypher is written to the docs and marked unexecuted. That is in the findings file.

## 2:45-3:00 — Who it helps

[On screen: README, patient-first section.]

This is patient first by design. The patient is the user. The clinic benefits second, with fewer angry calls and faster payment.

The plan is simple. Free for one appeal draft. Paid when the appeal wins, or a flat fee per appeal. Distribution is employers, patient advocacy groups, and people who already search for help with denials.

The repo is linked below. The demo is linked below. Thank you.

---

## Recording checklist

- Record in one take if you can. Do not worry about small pauses.
- Show the demo live. Do not show slides only.
- Say the numbers exactly as written. 57.5 to 77.5. 40 to 70. 20 to 10.
- Say synthetic data out loud at least once.
- End with the repo link on screen.
