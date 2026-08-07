"""
Optional live web search via the Tavily API (https://tavily.com), used to
supplement the local ChromaDB knowledge base with fresh, citable web
results (cited by URL instead of a local filename).

Every result URL is also handed to rag/web_cache.py, which scrapes and
persists the full page (or reuses a previous scrape/failure) so the same
site isn't fetched over and over for similar questions -- see that module
for details.

Controlled entirely by env vars, so it's a no-op unless explicitly turned
on in .env:

    WEB_SEARCH_ENABLED=true
    TAVILY_API_KEY=your_key_here
    TAVILY_MONTHLY_LIMIT=1000   # optional, defaults to Tavily's free-tier quota

Each call to Tavily is metered against TAVILY_MONTHLY_LIMIT via
rag/web_usage.py, which resets automatically each calendar month. Once the
quota is used up, search_web() stops calling Tavily and the chatbot quietly
falls back to local-only retrieval until the next month -- app.py surfaces
the running usage count so this is visible in the UI, not just the logs.

Safe to import and call even when disabled or unconfigured.
"""

from __future__ import annotations

import os

from .web_cache import get_or_scrape
from .web_usage import quota_exceeded, record_search, usage_status

MAX_WEB_RESULTS = 3
MAX_CONTEXT_CHARS = 3000  # cap what a single scraped page contributes to one prompt


def _enabled() -> bool:
    return os.environ.get("WEB_SEARCH_ENABLED", "false").strip().lower() == "true"


def _api_key() -> str | None:
    return os.environ.get("TAVILY_API_KEY") or None


def web_search_available() -> bool:
    return _enabled() and bool(_api_key()) and not quota_exceeded()


def web_search_status() -> dict:
    """Status for display in the UI: usage numbers plus why search is/isn't active."""
    status = usage_status()
    status["enabled"] = _enabled()
    status["configured"] = bool(_api_key())
    status["active"] = web_search_available()
    return status


def search_web(query: str, max_results: int = MAX_WEB_RESULTS) -> list[dict]:
    """Returns [{"text": ..., "source": url}, ...], or [] if disabled/unconfigured/
    quota-exhausted/failed."""
    if not web_search_available():
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=_api_key())
        response = client.search(query, max_results=max_results, include_answer=False)
        record_search()  # the request above spent a credit regardless of what it returned

        results = []
        for r in response.get("results", []):
            url = r.get("url") or ""
            if not url:
                continue

            scraped = get_or_scrape(url, query)
            text = (scraped or r.get("content") or "").strip()
            if text:
                results.append({"text": text[:MAX_CONTEXT_CHARS], "source": url})
        return results
    except Exception as exc:
        print(f"[web_search] skipped due to error: {exc}")
        return []
