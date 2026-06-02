"""
leap.py — Homer's 6-phase leapfrog.  while True: leap()

One token hops through six phases, one hop per scheduled run, carrying its
state in token.json (1-in / 1-out):

    A   AWARE     ready? clear the token, start a cycle
    O   OBSERVE   pick a random Wikipedia article
    C   CRAWL     read-only fetch: arXiv + Wikimedia Commons for that topic
    R   REACT     comparator — is arXiv newer & related?  NEW / OLD
    S1  WATCHDOG   self-heal + drop junk
    S2  COMMIT     if NEW, append to memory.json; spawn a fresh token

6 hops = one full cycle. Everything here is READ-ONLY against public APIs.
Homer never edits Wikipedia or anything else — it only reads, identifies
itself by User-Agent, and writes solely to its own repo (token + memory).
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

import requests
import wikipedia
import arxiv

import box  # 6-2-6 delivery box: build + schema-validate

ROOT = Path(__file__).parent
TOKEN = ROOT / "token.json"
MEM = ROOT / "memory.json"

UA = "homer-leapfrog/2.0 (+https://github.com/DavidWise01/homer; read-only research agent)"
wikipedia.set_user_agent(UA)
WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

PHASES = ["A", "O", "C", "R", "S1", "S2"]
NEXT = {"A": "O", "O": "C", "C": "R", "R": "S1", "S1": "S2", "S2": "A"}
REL_THRESHOLD = 0.2


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fresh(tick):
    return {"phase": "A", "data": {}, "tick": tick}


def load_token():
    if TOKEN.exists():
        try:
            t = json.loads(TOKEN.read_text(encoding="utf-8"))
            if t.get("phase") in PHASES and isinstance(t.get("data"), dict):
                return t
        except Exception:
            pass
    return fresh(0)


def save_token(t):
    TOKEN.write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")


def load_memory():
    if MEM.exists():
        try:
            return json.loads(MEM.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_memory(mem):
    MEM.write_text(json.dumps(mem, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ── senses (read-only, all defensive) ───────────────────────────────────────
def random_title():
    t = wikipedia.random(pages=1)
    return t if isinstance(t, str) else (t[0] if t else None)


def wiki_url(title):
    return "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")


def wiki_last_modified(title):
    r = requests.get(WIKI_API, headers={"User-Agent": UA}, timeout=20, params={
        "action": "query", "prop": "revisions", "titles": title,
        "rvprop": "timestamp", "rvlimit": 1, "format": "json"})
    r.raise_for_status()
    for _, p in r.json().get("query", {}).get("pages", {}).items():
        revs = p.get("revisions")
        if revs:
            return revs[0]["timestamp"]
    return None


def arxiv_recent(query, n=3):
    client = arxiv.Client(page_size=n, delay_seconds=3, num_retries=2)
    s = arxiv.Search(query=query, max_results=n,
                     sort_by=arxiv.SortCriterion.SubmittedDate)
    return [{"title": r.title.strip().replace("\n", " "),
             "url": r.entry_id,
             "published": r.published.isoformat()} for r in client.results(s)]


def commons_hits(query, n=3):
    r = requests.get(COMMONS_API, headers={"User-Agent": UA}, timeout=15, params={
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": n})
    r.raise_for_status()
    return [h["title"] for h in r.json().get("query", {}).get("search", [])[:n]]


# ── comparator ───────────────────────────────────────────────────────────────
def comparator(wiki, arxiv_list):
    """Is arXiv newer than the article's last edit, and topically related?
    Returns (verdict, relevance, match, newer)."""
    if not arxiv_list:
        return "OLD/DISREGARD", 0.0, None, False
    newest = max(arxiv_list, key=lambda p: parse_iso(p["published"]))
    wiki_mod = wiki.get("last_modified")
    wiki_dt = parse_iso(wiki_mod) if wiki_mod else datetime.now(timezone.utc)
    newer = parse_iso(newest["published"]) > wiki_dt
    if newer:
        wset = set(wiki["title"].lower().split())
        pset = set(newest["title"].lower().split())
        rel = len(wset & pset) / len(wset | pset) if (wset | pset) else 0.0
        verdict = "NEW" if rel > REL_THRESHOLD else "OLD/DISREGARD"
        return verdict, round(rel, 3), newest, True
    return "OLD/DISREGARD", 0.0, newest, False


# ── the leap ─────────────────────────────────────────────────────────────────
def leap():
    t = load_token()
    phase = t["phase"]
    d = t["data"]

    if phase == "A":                                   # AWARE
        t["data"] = {"status": "ready", "ts": now()}
        t["phase"] = "O"

    elif phase == "O":                                 # OBSERVE
        title = random_title()
        if not title:
            print("O: no title — reset")
            t = fresh(t["tick"]); save_token(t); return
        wiki = {"title": title, "url": wiki_url(title)}
        try:
            wiki["last_modified"] = wiki_last_modified(title)
        except Exception as e:
            wiki["last_modified"] = None
            print(f"O: last_modified failed: {e}")
        d["wiki"] = wiki
        t["phase"] = "C"
        print(f"O: target = {title}")

    elif phase == "C":                                 # CRAWL (read-only)
        title = d["wiki"]["title"]
        try:
            d["arxiv"] = arxiv_recent(title)
        except Exception as e:
            d["arxiv"] = []; print(f"C: arxiv failed: {e}")
        try:
            d["commons"] = commons_hits(title)
        except Exception as e:
            d["commons"] = []; print(f"C: commons failed: {e}")
        t["phase"] = "R"
        print(f"C: {len(d.get('arxiv', []))} arxiv, {len(d.get('commons', []))} commons")

    elif phase == "R":                                 # REACT (comparator)
        verdict, rel, match, newer = comparator(d.get("wiki", {}), d.get("arxiv", []))
        d["comparator"] = {"verdict": verdict, "relevance": rel,
                           "match": match, "newer": newer}
        t["phase"] = "S1"
        print(f"R: {verdict} (relevance {rel}, newer={newer})")

    elif phase == "S1":                                # WATCHDOG + self-heal
        complete = all(k in d for k in ("wiki", "arxiv", "comparator"))
        if not complete:
            print("S1: incomplete token — self-heal reset to A")
            t = fresh(t["tick"])
        else:
            if d["comparator"]["verdict"] != "NEW":
                d["drop"] = True
            t["phase"] = "S2"
            print(f"S1: {'drop' if d.get('drop') else 'pass'}")

    elif phase == "S2":                                # COMMIT
        cmp = d.get("comparator", {})
        if not d.get("drop") and "wiki" in d:
            key = d["wiki"]["title"]
            b = box.build_box(
                wiki=d["wiki"], arxiv_list=d.get("arxiv", []),
                commons=d.get("commons", []), aware_ts=d.get("ts") or now(),
                cycle=t["tick"], verdict="NEW",
                relevance=cmp.get("relevance", 0.0), match=cmp.get("match"),
                newer=cmp.get("newer", False), found=now(),
            )
            try:
                box.validate_box(b)                    # 6-2-6 gate
            except Exception as e:
                print(f"S2: box failed 6-2-6 validation — drop: {e}")
            else:
                mem = load_memory()
                mem[key] = b
                save_memory(mem)
                print(f"S2: committed {key} (box {b['out']['commit']}, {len(mem)} total)")
        else:
            print("S2: dropped — nothing committed")
        t = fresh(t["tick"] + 1)                       # spawn fresh token

    save_token(t)
    print(f"hop: {phase} -> {t['phase']}  (cycle {t['tick']})")


def prim(title):
    """The distilled primitive: crawl + compare -> one validated 6-2-6 box.
    The whole agent reduces to: while True: memory.update(prim(random_wiki()))."""
    wiki = {"title": title, "url": wiki_url(title)}
    try:
        wiki["last_modified"] = wiki_last_modified(title)
    except Exception:
        wiki["last_modified"] = None
    try:
        arxiv_list = arxiv_recent(title)
    except Exception as e:
        print(f"prim: arxiv unavailable ({e}) — treating as no results", file=sys.stderr)
        arxiv_list = []
    try:
        commons = commons_hits(title)
    except Exception:
        commons = []
    verdict, rel, match, newer = comparator(wiki, arxiv_list)
    b = box.build_box(
        wiki=wiki, arxiv_list=arxiv_list, commons=commons, aware_ts=now(),
        cycle=load_token()["tick"], verdict=verdict, relevance=rel,
        match=match, newer=newer, found=now(),
    )
    box.validate_box(b)
    return b


def verify():
    """Sentinel integrity check — token valid, and every memory entry a valid 6-2-6 box."""
    tok = json.loads(TOKEN.read_text(encoding="utf-8"))
    assert tok.get("phase") in PHASES, "token phase invalid"
    assert isinstance(tok.get("data"), dict), "token data invalid"
    n = 0
    if MEM.exists():
        mem = json.loads(MEM.read_text(encoding="utf-8"))
        assert isinstance(mem, dict), "memory.json not an object"
        errs = box.validate_memory(mem)
        if errs:
            for k, m in errs[:5]:
                print(f"  invalid box [{k}]: {m}")
            raise AssertionError(f"{len(errs)} memory entries fail the 6-2-6 schema")
        n = len(mem)
    print(f"integrity OK — phase={tok['phase']} cycle={tok['tick']} "
          f"memory={n} (all 6-2-6 valid)")


def status():
    t = load_token()
    print(f"phase={t['phase']}  cycle={t['tick']}  next={NEXT[t['phase']]}")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify()
    elif "--status" in sys.argv:
        status()
    elif "--prim" in sys.argv:
        i = sys.argv.index("--prim")
        title = sys.argv[i + 1] if len(sys.argv) > i + 1 else random_title()
        print(json.dumps(prim(title), indent=2))
    else:
        leap()
