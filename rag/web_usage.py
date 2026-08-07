"""
Tracks Tavily search API usage against the configured monthly quota, so the
chatbot stops calling Tavily (and can tell the user why) once the quota is
used up, rather than erroring out or silently failing per-call.

Resets automatically at the start of each calendar month. The limit is
configurable via TAVILY_MONTHLY_LIMIT in .env (default: 1000, Tavily's
free-tier monthly search quota).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

USAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "tavily_usage.json")

DEFAULT_MONTHLY_LIMIT = 1000


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _monthly_limit() -> int:
    try:
        return int(os.environ.get("TAVILY_MONTHLY_LIMIT", DEFAULT_MONTHLY_LIMIT))
    except ValueError:
        return DEFAULT_MONTHLY_LIMIT


def _load() -> dict:
    if not os.path.exists(USAGE_PATH):
        return {"month": _current_month(), "count": 0}
    with open(USAGE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("month") != _current_month():
        return {"month": _current_month(), "count": 0}
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(USAGE_PATH), exist_ok=True)
    with open(USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_search() -> None:
    """Call once per actual Tavily API request — it spends a credit whether
    or not the results end up being useful."""
    data = _load()
    data["count"] += 1
    _save(data)


def quota_exceeded() -> bool:
    data = _load()
    return data["count"] >= _monthly_limit()


def usage_status() -> dict:
    data = _load()
    limit = _monthly_limit()
    return {
        "month": data["month"],
        "used": data["count"],
        "limit": limit,
        "remaining": max(limit - data["count"], 0),
        "exceeded": data["count"] >= limit,
    }
