"""
observe.py — the senses. Real Wikipedia + arXiv + MediaWiki calls.

Everything here is best-effort and defensive: any network hiccup returns
None/[] rather than raising, so a flaky API never crashes a tick (and never
trips Sentinel S1 for something that isn't actually broken).
"""
import datetime
import requests
import wikipedia
import arxiv

UA = "homer-torus-agent/1.0 (+https://github.com/DavidWise01/homer)"
wikipedia.set_user_agent(UA)
WIKI_API = "https://en.wikipedia.org/w/api.php"


def random_title():
    """wikipedia.random(pages=1) returns a TITLE STRING, not a page."""
    try:
        t = wikipedia.random(pages=1)
        return t if isinstance(t, str) else (t[0] if t else None)
    except Exception as e:
        print(f"observe: random_title failed: {e}")
        return None


def resolve_page(title):
    """Turn a title into a real page object (url, title)."""
    try:
        return wikipedia.page(title, auto_suggest=False, redirect=True)
    except Exception as e:
        print(f"observe: resolve_page({title!r}) failed: {e}")
        return None


def page_last_modified(title):
    """Last revision timestamp of an article, via the MediaWiki API."""
    try:
        r = requests.get(WIKI_API, headers={"User-Agent": UA}, timeout=20, params={
            "action": "query", "prop": "revisions", "titles": title,
            "rvprop": "timestamp", "rvlimit": 1, "format": "json",
        })
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for _, p in pages.items():
            revs = p.get("revisions")
            if revs:
                ts = revs[0]["timestamp"].replace("Z", "+00:00")
                return datetime.datetime.fromisoformat(ts)
    except Exception as e:
        print(f"observe: page_last_modified({title!r}) failed: {e}")
    return None


def newest_arxiv(query):
    """Most recently submitted arXiv paper matching the query (arxiv 2.x API)."""
    try:
        client = arxiv.Client(page_size=1, delay_seconds=3, num_retries=2)
        search = arxiv.Search(
            query=query, max_results=1,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        for result in client.results(search):
            return result
    except Exception as e:
        print(f"observe: newest_arxiv({query!r}) failed: {e}")
    return None


def arxiv_reachable(entry_id):
    """Sentinel/shadow helper: is an arXiv abstract URL still live?"""
    try:
        r = requests.head(entry_id, headers={"User-Agent": UA},
                          timeout=15, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False
