"""
main.py — one tick, for one plane.  aware -> observe -> react.

Run with PLANE_ID in {1,2,3}. Emits findings-<PLANE>.json describing what (if
anything) this plane wants merged into the shared brain. The merge job applies it.

  plane 1  REACT=accumulate : log the topic seen           -> coverage.json
  plane 2  REACT=learn      : arXiv newer than wiki -> NEW  -> memory.json
  plane 3  REACT=shadow     : re-check a remembered entry; dead link -> prune

The torus throttles itself: a plane only acts when AWARE=ready (p1==1) and
OBSERVE!=skip (p2!=-1). The other states are deliberate idle/backoff.
"""
import os
import json
import datetime
from pathlib import Path

import state as st
import observe as ob

ROOT = Path(__file__).parent
PLANE = int(os.getenv("PLANE_ID", "1"))


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def aware(p1):
    return {-1: (False, "backoff"), 0: (False, "idle"), 1: (True, "ready")}[p1]


def write(findings):
    out = ROOT / f"findings-{PLANE}.json"
    out.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"wrote {out.name}: {json.dumps(findings)[:200]}")


def main():
    p1, p2, p3, tick = st.phases(PLANE)
    print(f"plane={PLANE}  tick={tick}  phases=({p1},{p2},{p3})  react={['','accumulate','learn','shadow'][p3]}")

    findings = {"coverage": {}, "memory": {}, "prune": []}

    ready, why = aware(p1)
    if not ready:
        print(f"aware: {why} — standing down")
        return write(findings)
    if p2 == -1:
        print("observe: skip")
        return write(findings)

    # ── PLANE 3 · SHADOW · maintenance (reads existing memory, no new page) ──
    if p3 == 3:
        mem_path = ROOT / "memory.json"
        mem = json.loads(mem_path.read_text(encoding="utf-8")) if mem_path.exists() else {}
        if not mem:
            print("shadow: memory empty — nothing to re-check")
            return write(findings)
        # deterministic pick so parallel runs don't all hit the same entry
        title = sorted(mem.keys())[tick % len(mem)]
        entry = mem[title]
        url = entry.get("arxiv_url")
        if url and not ob.arxiv_reachable(url):
            findings["prune"].append(title)
            print(f"shadow: arXiv link dead for {title!r} -> prune")
        else:
            print(f"shadow: {title!r} still valid")
        return write(findings)

    # ── PLANES 1 & 2 observe a fresh page ────────────────────────────────────
    title = ob.random_title()
    if not title:
        return write(findings)
    page = ob.resolve_page(title)
    if not page:
        return write(findings)
    print(f"observe: {page.title}")

    if p3 == 1:  # ACCUMULATE — coverage map of what we've sampled
        findings["coverage"][page.title] = {"wiki_url": page.url, "last_seen": now_iso()}
        print(f"accumulate: logged {page.title}")
        return write(findings)

    if p3 == 2:  # LEARN — does arXiv have something newer than the article's last edit?
        paper = ob.newest_arxiv(page.title)
        last_mod = ob.page_last_modified(page.title)
        if paper and last_mod and paper.published > last_mod:
            findings["memory"][page.title] = {
                "entity": page.title,
                "wiki_url": page.url,
                "wiki_last_modified": last_mod.isoformat(),
                "arxiv_url": paper.entry_id,
                "arxiv_title": paper.title.strip().replace("\n", " "),
                "arxiv_published": paper.published.isoformat(),
                "verdict": "NEW",
                "found": now_iso(),
            }
            print(f"learn: NEW — arXiv newer than wiki for {page.title}")
        else:
            print("learn: old / disregard")
        return write(findings)


if __name__ == "__main__":
    main()
