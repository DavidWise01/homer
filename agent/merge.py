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


def write_if_changed(path, obj):
    """Canonical JSON, with a trailing newline. Only touch the file if the
    serialized content actually differs — so idle ticks stay byte-for-byte
    silent and never produce a phantom commit."""
    canonical = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == canonical:
        return False
    path.write_text(canonical, encoding="utf-8")
    return True


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

    m_changed = write_if_changed(MEMORY, memory)
    c_changed = write_if_changed(COVERAGE, coverage)

    print(f"merge: +{added} new, -{pruned} pruned, {covered} coverage hits")
    print(f"merge: memory={len(memory)} entries ({MEMORY.stat().st_size} bytes), "
          f"coverage={len(coverage)} entries")
    print(f"merge: files changed -> memory={m_changed} coverage={c_changed}"
          + ("" if (m_changed or c_changed) else "  (silent tick)"))


if __name__ == "__main__":
    main()
