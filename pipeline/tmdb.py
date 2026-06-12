from __future__ import annotations
from __future__ import annotations
"""Fetch movies currently in theaters from TMDB (free API key: themoviedb.org/settings/api)."""
import os
import requests

BASE = "https://api.themoviedb.org/3"


def now_playing(region: str = "US", max_pages: int = 2) -> list[dict]:
    """Return a list of movies currently in theaters."""
    key = os.environ["TMDB_API_KEY"]
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


def imdb_id_for(tmdb_id: int) -> str | None:
    """Get the IMDb id for a TMDB movie (needed for OMDb lookups)."""
    key = os.environ["TMDB_API_KEY"]
    r = requests.get(
        f"{BASE}/movie/{tmdb_id}/external_ids", params={"api_key": key}, timeout=15
    )
    r.raise_for_status()
    return r.json().get("imdb_id")
