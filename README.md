<div align="center">

```
 ╔═══════════════════════════════════════════════╗
 ║   H O M E R   ·   L E A P F R O G   A G E N T   ║
 ║        A → O → C → R → S1 → S2 → A ...           ║
 ╚═══════════════════════════════════════════════╝
```

# Homer

[![Leapfrog Hop](https://github.com/DavidWise01/homer/actions/workflows/torus.yml/badge.svg)](https://github.com/DavidWise01/homer/actions/workflows/torus.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![read-only](https://img.shields.io/badge/wikipedia-READ--ONLY-2ecc40?style=flat-square)](#read-only--not-a-bot-that-edits-anything)
[![one node](https://img.shields.io/badge/nodes-1-0a84ff?style=flat-square)](#design)

**→ Live dashboard: [davidwise01.github.io/homer](https://davidwise01.github.io/homer/)**

*A single-node research agent that leapfrogs a six-phase loop on GitHub's cron, reading Wikipedia and arXiv to map where the literature has moved ahead of the encyclopedia.*

</div>

---

## Read-only — not a bot that edits anything

This is the important part, so it's first:

- **Homer never edits Wikipedia.** There is no write path. It only *reads* public
  article pages and uses the public read APIs (`action=query`).
- It identifies itself with a descriptive **`User-Agent`** and respects timeouts and
  rate limits — `AWARE` literally checks readiness before each cycle.
- The only thing Homer ever *writes* is its own two files in this repo:
  `agent/token.json` (its position in the loop) and `agent/memory.json` (its findings).
- It does not replicate, call out to anything but Wikipedia / arXiv / Wikimedia Commons,
  or run untrusted code. **One node. One token. One loop.**

If you're a Wikipedia editor who found this from a User-Agent in the logs: Homer is a
courteous read-only reader building a research index. It changes nothing.

---

## What it produces

After it's been hopping a while, `agent/memory.json` is the payload — a curated list of
Wikipedia topics where **arXiv has newer, topically-related research than the article's
last edit**:

```json
{
  "Topological insulator": {
    "entity": "Topological insulator",
    "wiki_url": "https://en.wikipedia.org/wiki/Topological_insulator",
    "wiki_last_modified": "2026-02-14T09:12:00+00:00",
    "arxiv": { "title": "New bulk-boundary correspondence ...",
               "url": "http://arxiv.org/abs/2605.01234v1",
               "published": "2026-05-29T18:00:00+00:00" },
    "relevance": 0.33,
    "verdict": "NEW",
    "found": "2026-06-01T00:00:00+00:00"
  }
}
```

A standing answer to *"where might the encyclopedia be behind the research?"* — useful
to editors, librarians, and researchers.

---

## Design

GitHub's `schedule:` cron is the `while True`. **Each run is one hop.** A single token
carries its state in `token.json` and leapfrogs six phases — one-in, one-out:

| Hop | Phase | Does |
|-----|-------|------|
| **A** | `AWARE` | clear the token, confirm readiness, start a cycle |
| **O** | `OBSERVE` | pick a random Wikipedia article + its last-edit time |
| **C** | `CRAWL` | read-only fetch: recent arXiv papers + Wikimedia Commons hits |
| **R** | `REACT` | **comparator** — is arXiv newer than the article, and related? |
| **S1** | `WATCHDOG` | self-heal a broken token; drop anything `OLD/DISREGARD` |
| **S2** | `COMMIT` | if `NEW`, append to `memory.json`; spawn a fresh token |

**6 hops = one full cycle.** At 4 hops/day that's a complete cycle roughly every day and
a half — deliberately slow, gentle on the APIs, and comfortably inside the Actions free tier.

### The comparator

```
NEW  ⟺  newest_arxiv.published > wiki.last_modified
        AND  jaccard(wiki.title_words, arxiv.title_words) > 0.2
```

Newer *and* topically related. Everything else is `OLD/DISREGARD`.

### Delivery format: the 6-2-6 box

Every `memory.json` entry is a **6-2-6 box** — 6 inputs, 2 engines, 6 outputs.
Nothing hidden. It makes Homer auditable: you can see exactly what went in, the
two transforms, and what came out.

```
+-------------------------------------------------------------+
|                 HOMER  ·  6-2-6  DELIVERY  BOX              |
+--------------------+----------------+-----------------------+
|      6  INTAKE     |   2  ENGINE    |      6  DELIVERY      |
|--------------------|----------------|-----------------------|
| 1. Wikipedia title |    [ CRAWL ]   | 1. Verdict            |
| 2. arXiv query     |       ||       | 2. Relevance score    |
| 3. Commons hits    |       \/       | 3. Timestamp          |
| 4. Aware status    |   [ COMPARE ]  | 4. Wiki URL           |
| 5. Token state     |                | 5. arXiv URL          |
| 6. Rate status     |                | 6. Commit fingerprint |
+--------------------+----------------+-----------------------+
|  Flow: A→O→C→R→S1→S2→A  |  1-in / 1-out  |  read-only / public |
+-------------------------------------------------------------+
```

The box is defined by a JSON Schema — [`schema/box-6-2-6.json`](schema/box-6-2-6.json) —
with `additionalProperties: false` everywhere, so **no hidden state** can sneak in.
`S2` builds the box, validates it against the schema, and *only then* commits;
`leap.py --verify` re-validates every entry on each run. An invalid box is dropped,
not stored.

```bash
python agent/leap.py --prim "Topological insulator"   # run the primitive, print one box
```

#### The distillation lens

It's a distillation pattern, honestly framed:

| Distillation | Homer |
|--------------|-------|
| Teacher | the open web — Wikipedia + arXiv + Commons |
| Student | `memory.json` |
| One primitive | `prim = compare(crawl(page))` — *"is there newer research?"* |
| The loop | `while True: memory.update(prim(random_wiki()))` |
| Product | small, specialized, auditable 6-2-6 boxes |

Everything else — `A`, `O`, `S1`, `S2` — is bookkeeping so the one primitive can run
forever on the free tier without exploding. One prim. One token. One public repo.

### Self-healing token

If a run is killed mid-cycle (timeout, runner eviction), the next hop reaches `S1`,
sees the token is missing the data earlier phases should have deposited, and resets
cleanly to `A`. No corrupt state, no stuck loops.

---

## Sentinels

| | Guard | Mechanism |
|---|-------|-----------|
| **Watchdog (S1)** | corrupt / partial token | self-heal reset to `A` |
| **Watchdog (job)** | crash visibility | opens a GitHub issue on any failed hop |
| **Timeout** | free-tier ceiling | 10-minute `timeout-minutes` |
| **Integrity** | bad JSON | `leap.py --verify` fails the run if token/memory are invalid |

---

## Files

```
agent/
  leap.py          the six-phase leapfrog + comparator + self-heal + prim + --verify
  box.py           builds, fingerprints, and schema-validates the 6-2-6 box
  token.json       the token — its phase, carried data, and cycle count
  memory.json      the findings — curated NEW-research map (each entry a 6-2-6 box)
schema/
  box-6-2-6.json   JSON Schema for the delivery box (no hidden state)
.github/workflows/
  torus.yml        cron: one hop per run, commit only on change
index.html         live 8-bit dashboard (GitHub Pages)
requirements.txt   wikipedia, arxiv, requests, jsonschema
```

---

## Run it

```bash
python agent/leap.py            # one hop
python agent/leap.py --status   # show current phase / cycle
python agent/leap.py --verify   # integrity check
```

On GitHub: enable Actions, set **Settings → Actions → Workflow permissions → Read and
write**, and the schedule starts once `torus.yml` is on the default branch. Or hit
**Run workflow** to fire a hop by hand.

> GitHub may delay scheduled runs under load and disables schedules after 60 days of
> repo inactivity (any push re-arms them). Commits by the built-in token don't
> re-trigger the workflow — no loops.

---

```
ROOT0-ATTRIBUTION-v1.0 · Homer — Leapfrog Agent · David Lee Wise / ROOT0 / TriPod LLC · MIT
```
