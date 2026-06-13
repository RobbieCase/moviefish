from __future__ import annotations
"""Fetch movies currently in theaters from TMDB (free API key: themoviedb.org/settings/api)."""
import os
from datetime import date, timedelta

import requests

BASE = "https://api.themoviedb.org/3"

# Tuning for the "big releases people care about" filter:
MIN_POPULARITY = 15   # TMDB popularity floor (festival/limited tail sits below)
MIN_RESULTS = 6       # safety floor so a quiet week is never near-empty


def now_playing(region: str = "US", max_pages: int = 2) -> list[dict]:
    """Return movies currently in theaters, excluding re-releases.

    TMDB's now_playing feed includes anniversary/re-release screenings of old
    films (Shrek, Top Gun: Maverick, etc.). Anything whose original release
    date is older than ~6 months is dropped, and non-English-language releases
    are excluded, so the board stays focused on new US/English films.
    """
    key = os.environ["TMDB_API_KEY"]
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    raw = []  # collect with popularity so we can gate by it below
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
            if m.get("original_language") != "en":
                continue  # non-English release (keeps the board US-focused)
            raw.append(
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
                    "popularity": m.get("popularity", 0),
                }
            )
        if page >= data.get("total_pages", 1):
            break
    # Dedupe by id, keep order
    seen, deduped = set(), []
    for m in raw:
        if m["tmdb_id"] not in seen:
            seen.add(m["tmdb_id"])
            deduped.append(m)

    # Popularity gate: drop the festival/limited tail, keep solid mid-size films.
    # TMDB 'popularity' is a daily-decaying engagement score; wide/major current
    # releases sit well above the long tail. We favor a quality floor over filling
    # slots, so a quiet week legitimately shows fewer (but "real") releases.
    gated = [m for m in deduped if m.get("popularity", 0) >= MIN_POPULARITY]

    # Safety floor: if the gate is so strict that a slow week leaves almost
    # nothing, fall back to the top titles by popularity so it's never empty.
    if len(gated) < MIN_RESULTS:
        gated = sorted(deduped, key=lambda m: m.get("popularity", 0),
                       reverse=True)[:MIN_RESULTS]

    return gated


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
        "vote_average": j.get("vote_average") or None,
        "vote_count": j.get("vote_count") or 0,
    }


def imdb_id_for(tmdb_id: int) -> str | None:
    """Get the IMDb id for a TMDB movie (needed for OMDb lookups)."""
    key = os.environ["TMDB_API_KEY"]
    r = requests.get(
        f"{BASE}/movie/{tmdb_id}/external_ids", params={"api_key": key}, timeout=15
    )
    r.raise_for_status()
    return r.json().get("imdb_id")
