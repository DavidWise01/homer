"""
state.py — the 3x3x3 torus.

The full Hamiltonian is {-1,0,1} x {-1,0,1} x {1,2,3} = 27 states.

We split it the natural way:
  - PHASE_3 (1,2,3) is the PLANE dimension — the REACT mode.
    Each plane is a separate parallel job, so p3 is fixed per job.
  - (PHASE_1, PHASE_2) is a 9-state sub-torus each plane walks.

  3 planes x 9 sub-states = 27. The whole torus is covered every tick,
  in parallel, with no edges (it wraps).

The tick is DERIVED FROM THE CLOCK, not a committed counter. Each 6-hour
slot since EPOCH is one tick. This keeps the agent stateless between runs
(no race, no commit-just-to-advance) — it only ever commits real findings.
"""
import sys
import json
import itertools
import datetime
from pathlib import Path

ROOT = Path(__file__).parent

# ── the three axes ─────────────────────────────────────────────────────────
PHASE_1 = [-1, 0, 1]   # AWARE:   backoff / idle / ready
PHASE_2 = [-1, 0, 1]   # OBSERVE: skip / neutral / good
PHASE_3 = [1, 2, 3]    # REACT:   accumulate / learn / shadow   (= the plane)

SUB = list(itertools.product(PHASE_1, PHASE_2))          # 9 states per plane
HAMILTONIAN = list(itertools.product(PHASE_1, PHASE_2, PHASE_3))  # 27 total

# one tick per 6-hour slot since this instant
EPOCH = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
TICK_SECONDS = 6 * 3600


def current_tick(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return int((now - EPOCH).total_seconds() // TICK_SECONDS)


def phases(plane, now=None):
    """Return (p1, p2, p3, tick) for a given plane (1/2/3)."""
    plane = int(plane)
    if plane not in (1, 2, 3):
        raise ValueError(f"plane must be 1, 2 or 3 (got {plane})")
    tick = current_tick(now)
    p1, p2 = SUB[tick % 9]
    p3 = plane
    return p1, p2, p3, tick


# ── Sentinel S3: memory integrity ────────────────────────────────────────────
def verify(name):
    f = ROOT / name
    if not f.exists():
        print(f"{name}: absent (ok — first run)")
        return
    data = json.loads(f.read_text(encoding="utf-8"))   # raises on corruption
    if not isinstance(data, dict):
        raise ValueError(f"{name} is not a JSON object")
    print(f"{name}: integrity OK ({len(data)} entries)")


if __name__ == "__main__":
    if "--verify-memory" in sys.argv:
        verify("memory.json")
        verify("coverage.json")
    elif "--phases" in sys.argv:
        for pl in (1, 2, 3):
            print(pl, phases(pl))
    else:
        print("usage: state.py [--verify-memory | --phases]")
