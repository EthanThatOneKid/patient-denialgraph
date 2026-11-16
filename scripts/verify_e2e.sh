#!/bin/bash
# End-to-end verification of patient-denialgraph, in a clean-room copy.
# Never mutates ~/workspace/hydradb-denialgraph. All output goes to $LOG.
SRC="$HOME/workspace/hydradb-denialgraph"
ROOM="/tmp/verify-room"
LOG="$ROOM/LOG.txt"
PASS=0; FAIL=0
rm -rf "$ROOM"; mkdir -p "$ROOM"
exec > "$LOG" 2>&1
echo "=== patient-denialgraph E2E verification ==="
echo "started: $(date -u +%FT%TZ)  src: $SRC"
check() { # check "name" command...
  local name="$1"; shift
  if "$@"; then echo "PASS: $name"; PASS=$((PASS+1));
  else echo "FAIL: $name"; FAIL=$((FAIL+1)); fi
}
note() { echo "NOTE: $*"; }

# --- 0. clean-room copy (exclude git, venv, existing Kuzu store, caches) ---
# NOTE: .venv is NOT copied (it is ~GBs and filled /tmp on the first run,
# leaving a truncated partial copy). It is symlinked instead.
mkdir -p "$ROOM/repo"
tar --exclude=.git --exclude=.venv --exclude=data/selfgraph-kuzu \
    --exclude=__pycache__ -cf - -C "$SRC" . | tar -xf - -C "$ROOM/repo"
ln -s "$SRC/.venv" "$ROOM/repo/.venv"
cd "$ROOM/repo" || exit 1
# Interpreters: the original build used system python3 (matplotlib 3.6.3)
# for generate/learn, and the repo .venv (selfgraph 0.2.1) for ingest.
# Invoke the venv python by its REAL path, not through the room symlink,
# or venv detection breaks and system pandas leaks in (binary-incompatible).
SYS_PY=python3
VENV_PY="$SRC/.venv/bin/python"
note "clean-room copy ready; venv symlinked, Kuzu store excluded (fresh ingest)"

# --- 1. data integrity: committed inputs ---
cat > /tmp/verify-data-check.py <<'EOF'
import json, csv, sys
cases = json.load(open('data/cases.json'))
assert len(cases) == 200, len(cases)
splits = {s: sum(1 for c in cases if c['split'] == s) for s in ('train','eval')}
assert splits == {'train': 160, 'eval': 40}, splits
rows = list(csv.DictReader(open('data/curve.csv')))
assert len(rows) == 11, len(rows)
r0, rN = rows[0], rows[-1]
assert (r0['accuracy'], r0['appeal_precision'], r0['recommended']) == ('0.575','0.400','20'), r0
assert (rN['accuracy'], rN['appeal_precision'], rN['recommended'], rN['shortcuts']) == ('0.775','0.700','10','30'), rN
assert abs(float(r0['dollars_saved_net']) - 6707.38) < 0.01 and abs(float(rN['dollars_saved_net']) - 6686.30) < 0.01
print("data OK: 200 cases (160 train / 40 eval), 11 curve rows, "
      "baseline 57.5%/40%/20 appeals/$6707.38 -> final 77.5%/70%/10 appeals/$6686.30, 30 shortcuts")
EOF
check "committed data matches README headline numbers" python3 /tmp/verify-data-check.py

# --- 2. reproducibility: regenerate from scratch (seeded) ---
cp data/curve.csv /tmp/verify-curve-orig.csv
cp data/curve.json /tmp/verify-curve-orig.json
md5sum data/curve.png web/curve.png > /tmp/verify-png-orig.md5
$SYS_PY src/generate_data.py > /tmp/verify-gen.log 2>&1
check "generate_data.py runs" grep -q "200" /tmp/verify-gen.log
$SYS_PY src/learn.py > /tmp/verify-learn.log 2>&1
check "learn.py runs (system python3, matplotlib 3.6.3 as in the original build)" grep -q "Baseline acc 0.575 -> final acc 0.775" /tmp/verify-learn.log
tail -4 /tmp/verify-learn.log
diff -q data/curve.csv /tmp/verify-curve-orig.csv && echo "PASS: regenerated curve.csv identical to committed" && PASS=$((PASS+1)) || { echo "FAIL: regenerated curve.csv differs"; FAIL=$((FAIL+1)); diff data/curve.csv /tmp/verify-curve-orig.csv | head; }
diff -q data/curve.json /tmp/verify-curve-orig.json && echo "PASS: regenerated curve.json identical to committed" && PASS=$((PASS+1)) || { echo "FAIL: regenerated curve.json differs"; FAIL=$((FAIL+1)); }
md5sum -c /tmp/verify-png-orig.md5 && echo "PASS: regenerated curve.png identical to committed local PNG" && PASS=$((PASS+1)) || { echo "FAIL: regenerated curve.png differs"; FAIL=$((FAIL+1)); }
if diff -q web/curve.svg "$SRC/web/curve.svg" > /dev/null 2>&1; then
  echo "PASS: curve.svg unchanged by learn.py rerun"; PASS=$((PASS+1))
else
  echo "FAIL: learn.py rerun OVERWROTE web/curve.svg (matplotlib SVG replaces the hand-built SVG)"
  FAIL=$((FAIL+1))
  ls -l web/curve.svg "$SRC/web/curve.svg"
  python3 -c "import xml.etree.ElementTree as ET; ET.parse('web/curve.svg'); print('regenerated curve.svg is still valid XML')" && note "overwritten SVG is valid XML" || note "overwritten SVG is NOT valid XML"
  grep -o "Appeal-win prediction accuracy" web/curve.svg | head -1
fi

# --- 3. SelfGraph ingest + retrieval + answerability + versioning (Kuzu, --full) ---
$VENV_PY src/ingest_selfgraph.py --full > /tmp/verify-ingest.log 2>&1
check "ingest --full runs (200 letters)" grep -q "inserted 200 letters" /tmp/verify-ingest.log
check "policy update inserted (PA-101 retired)" grep -q "policy update inserted" /tmp/verify-ingest.log
grep -E "inserted|policy update|context chars|check_answerable" /tmp/verify-ingest.log
cat > /tmp/verify-ingest-check.py <<'EOF'
import re
log = open('/tmp/verify-ingest.log').read()
cur = re.search(r"retrieve \(current\) ---\ncontext chars: (\d+)", log)
old = re.search(r"retrieve \(as_of 2026-06-01\) ---\ncontext chars: (\d+)", log)
assert cur and old, "retrieve context lines missing"
print(f"retrieve current context chars={cur.group(1)}, as_of 2026-06-01 chars={old.group(1)}")
assert int(cur.group(1)) > 0 and int(old.group(1)) > 0
assert cur.group(1) != old.group(1), "as-of retrieval identical to current: versioning not visible"
print("versioning OK: as-of retrieval differs from current")
ans = re.findall(r"check_answerable\('([^']+)'\) -> verdict=(\S+) missing=(\S+)", log)
print("answerability:", ans)
assert len(ans) == 2
assert ans[1][1] != 'answerable', f"off-topic question claimed answerable: {ans[1]}"
print("answerability OK: off-topic question flagged, not invented")
EOF
check "SelfGraph retrieve/versioning/answerability assertions" python3 /tmp/verify-ingest-check.py

# --- 4. demo data build ---
$SYS_PY src/build_demo_data.py > /tmp/verify-demodata.log 2>&1
check "build_demo_data.py runs" grep -q "curve: baseline 0.575 -> final 0.775" /tmp/verify-demodata.log
diff -q web/demo_data.js "$SRC/web/demo_data.js" && echo "PASS: regenerated demo_data.js identical to committed" && PASS=$((PASS+1)) || { echo "FAIL: regenerated demo_data.js differs"; FAIL=$((FAIL+1)); diff web/demo_data.js "$SRC/web/demo_data.js" | head -20; }

# --- 5. functional test of the demo page JS in node (DOM shim) ---
node "$(dirname "$0")/verify_demo_test.js" "$ROOM/repo/web" > /tmp/verify-demo.log 2>&1
check "node functional test of demo JS (all samples + gap case)" grep -q "^ALL DEMO CHECKS PASSED" /tmp/verify-demo.log
cat /tmp/verify-demo.log

# --- 6. serve the demo over HTTP and check assets ---
$SYS_PY -m http.server 8137 --directory web > /tmp/verify-http.log 2>&1 &
SRV=$!
sleep 1
for path in "/" "demo_data.js" "curve.svg"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8137/$path")
  [ "$code" = "200" ] && echo "PASS: HTTP 200 /$path" && PASS=$((PASS+1)) || { echo "FAIL: /$path -> HTTP $code"; FAIL=$((FAIL+1)); }
done
curl -s http://127.0.0.1:8137/ | grep -q 'src="curve.svg"' && echo "PASS: index.html references curve.svg" && PASS=$((PASS+1)) || { echo "FAIL: index.html does not reference curve.svg"; FAIL=$((FAIL+1)); }
curl -s http://127.0.0.1:8137/curve.svg | head -c 1000 | grep -q "<svg" && echo "PASS: served curve.svg is SVG" && PASS=$((PASS+1)) || { echo "FAIL: served curve.svg is not SVG"; FAIL=$((FAIL+1)); }
kill $SRV 2>/dev/null

# --- 7. remote GitHub state ---
# Expected head = the last confirmed push in the sync record (the script
# runs before the next push, so a hardcoded SHA goes stale after any push).
EXPECTED_HEAD=$(python3 -c "import json; print(json.load(open('$HOME/workspace/hydradb-denialgraph.muse-github-snapshot-sync.json'))[-1]['commit_sha'])")
/opt/hatch/bin/github call-read-tool --name list_commits --arguments-json '{"owner":"EthanThatOneKid","repo":"patient-denialgraph","branch":"main","perPage":1}' > /tmp/verify-gh.json 2>&1
grep -q "$EXPECTED_HEAD" /tmp/verify-gh.json && echo "PASS: GitHub main head matches last confirmed push ($EXPECTED_HEAD)" && PASS=$((PASS+1)) || { echo "FAIL: GitHub head is not $EXPECTED_HEAD (last confirmed push)"; FAIL=$((FAIL+1)); grep -o '"sha":"[0-9a-f]*"' /tmp/verify-gh.json | head -1; }
for p in web/curve.svg web/index.html README.md data/curve.csv DEPLOY.md DEMO_SCRIPT.md; do
  /opt/hatch/bin/github call-read-tool --name get_file_contents --arguments-json "{\"owner\":\"EthanThatOneKid\",\"repo\":\"patient-denialgraph\",\"path\":\"$p\",\"branch\":\"main\"}" > /tmp/verify-gh-file.json 2>&1
  grep -q "successfully downloaded" /tmp/verify-gh-file.json && echo "PASS: $p present on GitHub main" && PASS=$((PASS+1)) || { echo "FAIL: $p missing on GitHub main"; FAIL=$((FAIL+1)); }
done
PAGES_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://ethanthatonekid.github.io/patient-denialgraph/)
echo "NOTE: GitHub Pages URL https://ethanthatonekid.github.io/patient-denialgraph/ -> HTTP $PAGES_CODE (expected 404: Pages workflow not yet added/enabled by Ethan — NOT a failure of the app, but the live link does not exist yet)"

# --- 8. known limits (not verified live) ---
note "NO live HydraDB server was run in this verification (no Docker/Rust in sandbox); src/cypher.py remains unexecuted — see HYDRA_FINDINGS.md. SelfGraph ran on embedded Kuzu."
note "Walkthrough video not recorded yet (Ethan-only); submission not filed (needs live link + video + Ethan go-ahead)."

echo "=== RESULT: $PASS passed, $FAIL failed ==="
echo "finished: $(date -u +%FT%TZ)"
