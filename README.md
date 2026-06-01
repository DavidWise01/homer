# Homer

[![Torus Agent](https://github.com/DavidWise01/homer/actions/workflows/torus.yml/badge.svg)](https://github.com/DavidWise01/homer/actions/workflows/torus.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![One node](https://img.shields.io/badge/nodes-1-blue?style=flat-square)](#design)

> A single-node research agent that walks a 3×3×3 torus on GitHub's cron, sampling
> Wikipedia and cross-referencing arXiv, slowly building a curated map of topics
> where **arXiv has newer research than the Wikipedia article's last edit**.

The cron schedule is the `while True`. Each run is one **tick**. The agent never
spawns other agents, never leaves its own repo, and idles in most states. It looks
like a quiet bot tidying a file every six hours — because that's what it is.

---

## What it produces

After it's been running a while, `agent/memory.json` is the payload: a curated list
of Wikipedia topics that have **more recent arXiv activity than their article's last
edit** — a low-effort "where might the encyclopedia be behind the literature?" map.

```json
{
  "Topological insulator": {
    "entity": "Topological insulator",
    "wiki_url": "https://en.wikipedia.org/wiki/Topological_insulator",
    "wiki_last_modified": "2026-02-14T09:12:00+00:00",
    "arxiv_url": "http://arxiv.org/abs/2605.01234v1",
    "arxiv_title": "New bulk-boundary correspondence in ...",
    "arxiv_published": "2026-05-29T18:00:00+00:00",
    "verdict": "NEW",
    "found": "2026-06-01T00:00:00+00:00"
  }
}
```

`agent/coverage.json` is the sampling log (what's been seen, how often).

---

## Design

The full Hamiltonian is `{-1,0,1} × {-1,0,1} × {1,2,3}` = **27 states**, walked with
no edges (it wraps).

| Axis | Values | Meaning |
|------|--------|---------|
| `p1` AWARE | −1 / 0 / 1 | backoff / idle / **ready** |
| `p2` OBSERVE | −1 / 0 / 1 | skip / neutral / good |
| `p3` REACT | 1 / 2 / 3 | accumulate / learn / shadow — **this is the plane** |

`p3` is the **plane dimension**: three parallel jobs, one per REACT mode. Each plane
walks its own 3×3 = 9-state sub-torus. **3 planes × 9 = 27** — the whole torus is
covered every tick, in parallel.

| Plane | REACT | Does |
|-------|-------|------|
| 1 | accumulate | logs the sampled topic → `coverage.json` |
| 2 | learn | arXiv newer than the article's last edit → `memory.json` (`verdict: NEW`) |
| 3 | shadow | re-checks a remembered entry; dead arXiv link → prune |

A plane only acts when `AWARE=ready` **and** `OBSERVE≠skip` — so most ticks are
deliberate idle. Gentle on the APIs, comfortably inside the Actions free tier.

The **tick is derived from the clock** (one per 6-hour slot since an epoch), not a
committed counter — so the agent is stateless between runs, never races, and only
ever commits when it actually found something.

### How the planes stay race-free

The three planes run as a parallel matrix and each uploads its findings as an
**artifact**. A single downstream `commit` job downloads all three, merges once, and
makes one commit. No two jobs ever push to `main` — there is nothing to race.

---

## Sentinels

| | Guard | Mechanism |
|---|-------|-----------|
| **S1** | Crash visibility | opens a GitHub issue on any failed tick |
| **S2** | Free-tier ceiling | 10-minute `timeout-minutes` per job |
| **S3** | Memory integrity | `state.py --verify-memory` (fails the run if `memory.json` is corrupt) |
| **S4** | Exodus | if `memory.json` exceeds `EXODUS_BYTES` (default 50 MB), snapshot it to a GitHub **Release** and reset working memory to an index |

---

## Files

```
agent/
  state.py        the 3x3x3 torus: clock -> (p1,p2,p3,tick); integrity check (S3)
  observe.py      senses: wikipedia.random -> page, MediaWiki last-edit, newest arXiv
  main.py         one plane, one tick: aware -> observe -> react -> findings-N.json
  merge.py        folds the 3 planes' findings into memory.json + coverage.json
  memory.json     the brain — curated NEW-research map
  coverage.json   sampling log
.github/
  workflows/torus.yml   cron loop: 3 planes (parallel) -> single merge+commit
  exodus.sh             Sentinel S4
requirements.txt   wikipedia, arxiv, requests
```

---

## Run it

1. Fork / create the repo (public), **Settings → Actions → General → Workflow
   permissions → Read and write**.
2. Enable Actions. The schedule starts automatically once `torus.yml` is on the
   default branch.
3. Or hit **Run workflow** (`workflow_dispatch`) to fire a tick by hand.

Locally, to walk the torus without the network side:

```bash
python agent/state.py --phases          # show each plane's current phase
PLANE_ID=2 python agent/main.py          # run plane 2 once (needs deps + network)
python agent/merge.py                    # fold findings into the brain
```

> **Notes.** GitHub may delay scheduled runs under load, and disables schedules
> after 60 days of repo inactivity (any push re-arms them). Commits made by the
> built-in `GITHUB_TOKEN` intentionally don't re-trigger the workflow — no loops.

---

## What it is not

It does not replicate, call out to anything but Wikipedia and arXiv, run untrusted
code, or persist anything outside its own repo. One node. One loop. It accumulates,
learns, and shadows — forever, quietly, in place.

---

```
ROOT0-ATTRIBUTION-v1.0 · Homer — Torus Agent
David Lee Wise / ROOT0 / TriPod LLC · MIT
```
