#!/usr/bin/env python3
"""Regenerate the learning-curve chart as SVG from data/curve.csv.

Same data and same two series as the PNG that src/learn.py writes
(accuracy on the left axis, appeal precision on the right axis).
SVG is text, so it can be pushed through the GitHub connector, which
only accepts UTF-8 text files — the PNG could not go that route.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")

with open(os.path.join(DATA, "curve.csv")) as f:
    rows = list(csv.DictReader(f))
rounds = [int(r["round"]) for r in rows]
acc = [float(r["accuracy"]) for r in rows]
prec = [float(r["appeal_precision"]) for r in rows]

W, H = 1200, 675
L, R, T, B = 90, 90, 70, 80
PW, PH = W - L - R, H - T - B


def x(i):
    return L + PW * i / max(rounds)


def y_acc(v):
    return T + PH * (1 - (v - 0.4) / (1.0 - 0.4))


def y_prec(v):
    return T + PH * (1 - v / 1.05)


def pts(xs, ys):
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys))


def circles(xs, ys, color):
    return "".join(
        f'<circle cx="{a:.1f}" cy="{b:.1f}" r="6" fill="{color}" stroke="#fff" stroke-width="2"/>'
        for a, b in zip(xs, ys)
    )


xs = [x(i) for i in rounds]
acc_y = [y_acc(v) for v in acc]
prec_y = [y_prec(v) for v in prec]
base_acc_y = y_acc(acc[0])
base_prec_y = y_prec(prec[0])

# Gridlines + y labels, left (accuracy 0.4-1.0) and right (precision 0-1.0)
grid = []
for v in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    yy = y_acc(v)
    grid.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{W - R}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
    grid.append(f'<text x="{L - 10}" y="{yy + 5:.1f}" text-anchor="end" font-size="16" fill="#374151">{v:.0%}</text>')
for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
    yy = y_prec(v)
    grid.append(f'<text x="{W - R + 10}" y="{yy + 5:.1f}" font-size="16" fill="#166534">{v:.0%}</text>')

xticks = "".join(
    f'<text x="{x(i):.1f}" y="{H - B + 30}" text-anchor="middle" font-size="16" fill="#374151">{i}</text>'
    for i in rounds
)

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="system-ui, -apple-system, sans-serif">
<rect width="{W}" height="{H}" fill="#fff"/>
<text x="{W // 2}" y="38" text-anchor="middle" font-size="24" font-weight="600" fill="#111827">DenialGraph-lite: accuracy rises as the graph learns from appeals</text>
{''.join(grid)}
<line x1="{L}" y1="{T}" x2="{L}" y2="{H - B}" stroke="#9ca3af"/>
<line x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke="#9ca3af"/>
<line x1="{W - R}" y1="{T}" x2="{W - R}" y2="{H - B}" stroke="#9ca3af"/>
{xticks}
<text x="{W // 2}" y="{H - 18}" text-anchor="middle" font-size="17" fill="#374151">Learning round (16 appeal outcomes per round)</text>
<text x="22" y="{H // 2}" text-anchor="middle" font-size="17" fill="#1d4ed8" transform="rotate(-90 22 {H // 2})">Accuracy on frozen 40-case eval set</text>
<text x="{W - 22}" y="{H // 2}" text-anchor="middle" font-size="17" fill="#166534" transform="rotate(90 {W - 22} {H // 2})">Precision (share of recommended appeals that won)</text>
<line x1="{L}" y1="{base_acc_y:.1f}" x2="{W - R}" y2="{base_acc_y:.1f}" stroke="#9ca3af" stroke-dasharray="8 6" stroke-width="1.5"/>
<line x1="{L}" y1="{base_prec_y:.1f}" x2="{W - R}" y2="{base_prec_y:.1f}" stroke="#16a34a" stroke-dasharray="8 6" stroke-width="1.5"/>
<polyline points="{pts(xs, prec_y)}" fill="none" stroke="#16a34a" stroke-width="2.5"/>
{circles(xs, prec_y, "#16a34a")}
<polyline points="{pts(xs, acc_y)}" fill="none" stroke="#2563eb" stroke-width="3"/>
{circles(xs, acc_y, "#2563eb")}
<rect x="{L + 14}" y="{T + 14}" width="330" height="58" fill="#fff" fill-opacity="0.85" stroke="#e5e7eb"/>
<line x1="{L + 28}" y1="{T + 34}" x2="{L + 58}" y2="{T + 34}" stroke="#16a34a" stroke-width="2.5"/>
<circle cx="{L + 43}" cy="{T + 34}" r="5" fill="#16a34a"/>
<text x="{L + 68}" y="{T + 40}" font-size="16" fill="#111827">Precision of recommended appeals</text>
<text x="{L + 68}" y="{T + 62}" font-size="15" fill="#6b7280">Baseline precision: {prec[0]:.0%}</text>
<rect x="{W - R - 360}" y="{H - B - 58}" width="346" height="58" fill="#fff" fill-opacity="0.85" stroke="#e5e7eb"/>
<line x1="{W - R - 346}" y1="{H - B - 38}" x2="{W - R - 316}" y2="{H - B - 38}" stroke="#2563eb" stroke-width="3"/>
<circle cx="{W - R - 331}" cy="{H - B - 38}" r="5" fill="#2563eb"/>
<text x="{W - R - 306}" y="{H - B - 32}" font-size="16" fill="#111827">Appeal-win prediction accuracy</text>
<text x="{W - R - 306}" y="{H - B - 10}" font-size="15" fill="#6b7280">Baseline (rule lookup): {acc[0]:.0%}</text>
<text x="{L}" y="{H - B + 58}" font-size="15" fill="#6b7280">Baseline 57.5% accuracy, 40% precision -&gt; after 10 rounds 77.5% accuracy, 70% precision. Synthetic data, n=40 eval.</text>
</svg>
"""

for out in (os.path.join(DATA, "curve.svg"), os.path.join(WEB, "curve.svg")):
    with open(out, "w") as f:
        f.write(svg)
    print(f"wrote {out} ({os.path.getsize(out)} bytes)")
