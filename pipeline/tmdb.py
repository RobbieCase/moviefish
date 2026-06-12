from __future__ import annotations
"""Fetch movies currently in theaters from TMDB (free API key: themoviedb.org/settings/api)."""
import os
from datetime import date, timedelta

import requests

BASE = "https://api.themoviedb.org/3"


def now_playing(region: str = "US", max_pages: int = 2) -> list[dict]:
    """Return movies currently in theaters, excluding re-releases.

    TMDB's now_playing feed includes anniversary/re-release screenings of old
    films (Shrek, Top Gun: Maverick, etc.). Anything whose original release
    date is older than ~6 months is dropped so the board stays "new this week".
    """
    key = os.environ["TMDB_API_KEY"]
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    movies = []
    for page in range(1, max_pages + 1):
        r = requests.get(
            f"{BASE}/movie/now_playing",
            params={"api_key": key, "region": region, "page": page},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        for m in data.get("results", []):
            rd = m.get("release_date", "")
            if rd and rd < cutoff:
                continue  # re-release of an older film
            movies.append(
                {
                    "tmdb_id": m["id"],
                    "title": m["title"],
                    "release_date": m.get("release_date", ""),
                    "poster": (
                        f"https://image.tmdb.org/t/p/w342{m['poster_path']}"
                        if m.get("poster_path")
                        else None
                    ),
                    "tmdb_score": round(m.get("vote_average", 0) * 10),  # 0-100
                    "tmdb_votes": m.get("vote_count", 0),
                }
            )
        if page >= data.get("total_pages", 1):
            break
    # Dedupe by id, keep order
    seen, out = set(), []
    for m in movies:
        if m["tmdb_id"] not in seen:
            seen.add(m["tmdb_id"])
            out.append(m)
    return out


def movie_details(tmdb_id: int) -> dict:
    """One call for the fields other modules need: imdb_id + runtime (mins)."""
    key = os.environ["TMDB_API_KEY"]
    r = requests.get(
        f"{BASE}/movie/{tmdb_id}",
        params={"api_key": key, "append_to_response": "external_ids"},
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    return {
        "imdb_id": (j.get("external_ids") or {}).get("imdb_id"),
        "runtime": j.get("runtime") or None,
    }


def imdb_id_for(tmdb_id: int) -> str | None:
    """Get the IMDb id for a TMDB movie (needed for OMDb lookups)."""
    key = os.environ["TMDB_API_KEY"]
    r = requests.get(
        f"{BASE}/movie/{tmdb_id}/external_ids", params={"api_key": key}, timeout=15
    )
    r.raise_for_status()
    return r.json().get("imdb_id")
