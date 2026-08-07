"""
Optional live web search via the Tavily API (https://tavily.com), used to
supplement the local ChromaDB knowledge base with fresh, citable web
results (cited by URL instead of a local filename).

Controlled entirely by env vars, so it's a no-op unless explicitly turned
on in .env:

    WEB_SEARCH_ENABLED=true
    TAVILY_API_KEY=your_key_here

Safe to import and call even when disabled or unconfigured.
"""

from __future__ import annotations

import os

MAX_WEB_RESULTS = 3


def _enabled() -> bool:
    return os.environ.get("WEB_SEARCH_ENABLED", "false").strip().lower() == "true"


def _api_key() -> str | None:
    return os.environ.get("TAVILY_API_KEY") or None


def web_search_available() -> bool:
    return _enabled() and bool(_api_key())


def search_web(query: str, max_results: int = MAX_WEB_RESULTS) -> list[dict]:
    """Returns [{"text": ..., "source": url}, ...], or [] if disabled/unconfigured/failed."""
    if not web_search_available():
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=_api_key())
        response = client.search(query, max_results=max_results, include_answer=False)

        results = []
        for r in response.get("results", []):
            content = (r.get("content") or "").strip()
            url = r.get("url") or ""
            if content and url:
                results.append({"text": content, "source": url})
        return results
    except Exception as exc:
        print(f"[web_search] skipped due to error: {exc}")
        return []
