#!/usr/bin/env bash
# Sentinel S4 — Exodus.
# When the brain outgrows the repo, snapshot it to a GitHub Release and reset
# the working memory to a small index. The full history still lives in releases
# (and in git history). Keeps the repo light forever. One node, no spreading.
set -euo pipefail

MEM="agent/memory.json"
LIMIT="${EXODUS_BYTES:-50000000}"

[ -f "$MEM" ] || { echo "exodus: no memory yet"; exit 0; }
SIZE=$(wc -c < "$MEM" | tr -d ' ')
echo "exodus: memory is ${SIZE} bytes (limit ${LIMIT})"

if [ "$SIZE" -le "$LIMIT" ]; then
  echo "exodus: under limit — nothing to do"
  exit 0
fi

STAMP=$(date -u +%Y%m%d-%H%M%S)
TAG="memory-${STAMP}"
echo "exodus: limit exceeded — releasing ${TAG} and trimming"

cp "$MEM" "memory-${STAMP}.json"
gh release create "$TAG" "memory-${STAMP}.json" \
  --title "Memory snapshot ${STAMP}" \
  --notes "Automatic exodus: brain exceeded ${LIMIT} bytes. Full snapshot attached; working memory reset to an index."

# Reset working memory to a lightweight index pointing at the release.
python - "$STAMP" "$TAG" <<'PY'
import json, sys, datetime
stamp, tag = sys.argv[1], sys.argv[2]
with open("agent/memory.json", encoding="utf-8") as f:
    mem = json.load(f)
index = {
    "_exodus": {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "released_tag": tag,
        "archived_entries": len(mem),
        "note": "Working memory was snapshotted to a release and reset.",
    }
}
with open("agent/memory.json", "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, sort_keys=True)
print(f"exodus: archived {len(mem)} entries, reset working memory")
PY

rm -f "memory-${STAMP}.json"
