"""
merge.py — fold the three planes' findings into the shared brain, once.

Reads findings-1.json / findings-2.json / findings-3.json (whichever exist),
merges into memory.json (the curated NEW-research map) and coverage.json (the
sampling log), applies shadow prunes, and reports sizes.

Run by the single commit job — never in parallel — so there are no races.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY = ROOT / "memory.json"
COVERAGE = ROOT / "coverage.json"


def load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            print(f"merge: {path.name} unreadable — starting fresh")
    return default


def main():
    memory = load(MEMORY, {})
    coverage = load(COVERAGE, {})
    added, pruned, covered = 0, 0, 0

    for plane in (1, 2, 3):
        f = ROOT / f"findings-{plane}.json"
        if not f.exists():
            continue
        find = load(f, {})

        for title, rec in find.get("memory", {}).items():
            if title not in memory:
                added += 1
            memory[title] = rec

        for title, rec in find.get("coverage", {}).items():
            existing = coverage.get(title, {"count": 0})
            coverage[title] = {
                "wiki_url": rec.get("wiki_url"),
                "last_seen": rec.get("last_seen"),
                "count": existing.get("count", 0) + 1,
            }
            covered += 1

        for title in find.get("prune", []):
            if title in memory:
                del memory[title]
                pruned += 1

    MEMORY.write_text(json.dumps(memory, indent=2, sort_keys=True), encoding="utf-8")
    COVERAGE.write_text(json.dumps(coverage, indent=2, sort_keys=True), encoding="utf-8")

    print(f"merge: +{added} new, -{pruned} pruned, {covered} coverage hits")
    print(f"merge: memory={len(memory)} entries ({MEMORY.stat().st_size} bytes), "
          f"coverage={len(coverage)} entries")


if __name__ == "__main__":
    main()
