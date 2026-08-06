"""
Pulls current Liverpool FC fixtures, results, and Premier League standings
from football-data.org (free tier: https://www.football-data.org/client/register)
and saves them as readable text documents in data/raw/football_api/.

Requires the environment variable FOOTBALL_API_KEY to be set.
"""

from __future__ import annotations

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "football_api")
BASE_URL = "https://api.football-data.org/v4"
LIVERPOOL_TEAM_ID = 64  # football-data.org's fixed ID for Liverpool FC
PREMIER_LEAGUE_ID = "PL"

API_KEY = os.environ.get("FOOTBALL_API_KEY")


def api_get(path: str, params: dict | None = None) -> dict:
    headers = {"X-Auth-Token": API_KEY}
    resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def save_fixtures() -> None:
    data = api_get(f"/teams/{LIVERPOOL_TEAM_ID}/matches", params={"limit": 20})
    lines = ["LIVERPOOL FC — RECENT & UPCOMING MATCHES\n"]

    for match in data.get("matches", []):
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        date = match["utcDate"][:10]
        status = match["status"]
        score = match.get("score", {}).get("fullTime", {})
        score_str = (
            f"{score.get('home')}-{score.get('away')}"
            if status == "FINISHED"
            else "not played yet"
        )
        competition = match["competition"]["name"]
        lines.append(f"- [{date}] {home} vs {away} ({competition}): {score_str} [{status}]")

    _write("fixtures.txt", "\n".join(lines))


def save_standings() -> None:
    data = api_get(f"/competitions/{PREMIER_LEAGUE_ID}/standings")
    lines = ["PREMIER LEAGUE STANDINGS\n"]

    for table in data.get("standings", []):
        if table["type"] != "TOTAL":
            continue
        for row in table["table"]:
            lines.append(
                f"{row['position']}. {row['team']['name']} — "
                f"P{row['playedGames']} W{row['won']} D{row['draw']} L{row['lost']} "
                f"GD{row['goalDifference']} Pts{row['points']}"
            )

    _write("standings.txt", "\n".join(lines))


def _write(filename: str, content: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [ok] saved {filename}")


def main() -> None:
    if not API_KEY:
        raise SystemExit(
            "FOOTBALL_API_KEY is not set. Get a free key at "
            "https://www.football-data.org/client/register and export it."
        )

    print("Fetching Liverpool FC fixtures/results...")
    save_fixtures()

    print("Fetching Premier League standings...")
    save_standings()

    print(f"\nDone. Files saved to: {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
