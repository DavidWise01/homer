"""
box.py — the 6-2-6 delivery box: build it, fingerprint it, validate it.

6 IN  (sources + state)  ->  2 ENGINE (crawl, compare)  ->  6 OUT (delivery)

Every memory.json entry is one box, validated against schema/box-6-2-6.json
before it is ever committed. Invalid box -> watchdog drop. No hidden state.
"""
import json
import hashlib
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT.parent / "schema" / "box-6-2-6.json"

_validator = None


def _get_validator():
    global _validator
    if _validator is None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        _validator = Draft202012Validator(schema)
    return _validator


def fingerprint(box):
    """sha256[:12] over in + engine + out(without commit) — an auditable id."""
    core = {
        "in": box["in"],
        "engine": box["engine"],
        "out": {k: v for k, v in box["out"].items() if k != "commit"},
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def build_box(*, wiki, arxiv_list, commons, aware_ts, cycle,
              verdict, relevance, match, newer, found, rate="ok"):
    """Assemble a canonical 6-2-6 box. commit fingerprint is filled last."""
    commons = commons or []
    arxiv_list = arxiv_list or []
    box = {
        "box": "6-2-6",
        "in": {
            "wikipedia": wiki["title"],
            "arxiv": f"query:{wiki['title']}",
            "commons": commons,
            "aware": f"{aware_ts}:ready",
            "token": f"cycle:{cycle}",
            "rate": rate,
        },
        "engine": {
            "crawl": {
                "arxiv_found": len(arxiv_list),
                "commons_found": len(commons),
            },
            "compare": {
                "method": "arxiv.published > wiki.last_modified & jaccard(titles) > 0.2",
                "newer": bool(newer),
                "relevance": float(relevance),
            },
        },
        "out": {
            "verdict": verdict,
            "relevance": float(relevance),
            "timestamp": found,
            "wiki_url": wiki["url"],
            "arxiv_url": (match or {}).get("url"),
            "commit": "",
        },
    }
    box["out"]["commit"] = fingerprint(box)
    return box


def validate_box(box):
    """Raise jsonschema.ValidationError if the box is not a valid 6-2-6."""
    _get_validator().validate(box)
    return True


def validate_memory(memory):
    """Validate every entry in a memory dict. Returns list of (key, error)."""
    errors = []
    for key, entry in memory.items():
        for err in _get_validator().iter_errors(entry):
            errors.append((key, err.message))
    return errors


if __name__ == "__main__":
    # self-test: a synthetic NEW box must validate
    demo = build_box(
        wiki={"title": "Topological insulator",
              "url": "https://en.wikipedia.org/wiki/Topological_insulator",
              "last_modified": "2026-02-14T09:12:00+00:00"},
        arxiv_list=[{"title": "New bulk-boundary correspondence",
                     "url": "http://arxiv.org/abs/2605.01234v1",
                     "published": "2026-05-29T18:00:00+00:00"}],
        commons=["File:TI band structure.svg"],
        aware_ts="2026-06-01T00:00:00+00:00", cycle=7,
        verdict="NEW", relevance=0.33,
        match={"url": "http://arxiv.org/abs/2605.01234v1"},
        newer=True, found="2026-06-01T00:05:00+00:00",
    )
    validate_box(demo)
    print("self-test OK — synthetic NEW box is valid 6-2-6")
    print(json.dumps(demo, indent=2))
