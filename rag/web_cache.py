"""
Persistent cache for pages discovered via live web search (rag/web_search.py).

Every URL a web search turns up gets scraped once and saved as a local .txt
file under data/raw/web_cache/, with the outcome recorded in
web_cache_index.json so the same URL is never fetched twice:

  - already scraped        -> reuse the saved text, no network call at all
  - scraping failed before -> don't retry every turn; the caller falls back
    to the search API's own snippet for that turn instead

Because the cached files live under data/raw/, the next `make build-db` run
picks them up like any other source -- so a site that answered one question
becomes part of the local knowledge base for future similar questions,
instead of needing another live web search.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
CACHE_DIR = os.path.join(BASE_DIR, "data", "raw", "web_cache")
INDEX_PATH = os.path.join(BASE_DIR, "data", "processed", "web_cache_index.json")

USER_AGENT = "LiverpoolFCChatbot/1.0 (portfolio project; local RAG cache)"
REQUEST_TIMEOUT = 10
MIN_TEXT_LENGTH = 200


def _slug_for(url: str) -> str:
    domain = urlparse(url).netloc.replace("www.", "")
    safe_domain = re.sub(r"[^A-Za-z0-9]+", "_", domain).strip("_") or "site"
    short_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    return f"{safe_domain}_{short_hash}.txt"


def _load_index() -> dict:
    if not os.path.exists(INDEX_PATH):
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: dict) -> None:
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def _scrape(url: str) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if "html" not in resp.headers.get("Content-Type", ""):
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{2,}", "\n\n", text)
        return text if len(text) >= MIN_TEXT_LENGTH else None
    except Exception as exc:
        print(f"[web_cache] scrape failed for {url}: {exc}")
        return None


def get_or_scrape(url: str, query: str) -> str | None:
    """Returns cached/freshly-scraped page text, or None if unavailable
    (this attempt failed, or a past attempt already failed and we're not
    retrying)."""
    index = _load_index()
    entry = index.get(url)

    if entry and entry.get("status") == "scraped":
        path = os.path.join(BASE_DIR, entry["local_path"])
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        # cached file went missing on disk -- fall through and re-scrape

    elif entry and entry.get("status") == "failed":
        return None  # known-bad URL, don't hammer it again this session

    text = _scrape(url)
    now = datetime.now(timezone.utc).isoformat()

    if text:
        os.makedirs(CACHE_DIR, exist_ok=True)
        rel_path = os.path.join("data", "raw", "web_cache", _slug_for(url))
        with open(os.path.join(BASE_DIR, rel_path), "w", encoding="utf-8") as f:
            f.write(f"SOURCE: {url}\nQUERY: {query}\n\n{text}")

        index[url] = {
            "status": "scraped",
            "local_path": rel_path,
            "query": query,
            "scraped_at": now,
        }
        _save_index(index)
        return text

    index[url] = {"status": "failed", "query": query, "scraped_at": now}
    _save_index(index)
    return None
