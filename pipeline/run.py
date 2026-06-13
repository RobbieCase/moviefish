from __future__ import annotations
"""Run the full pipeline: theaters -> review scores + fan buzz -> data/movies.json.

The composite GRADE is built from review sites only: IMDb, Rotten Tomatoes,
Metacritic, Letterboxd, TMDB. Fan buzz (YouTube trailer-comment sentiment)
is a separate display object and does NOT affect the grade.

Reddit is removed for now (API access pending approval); the module file
remains in the repo for if/when that changes.

Usage:
    python -m pipeline.run
    python dashboard/build.py    # -> output/index.html
"""
import json
import os
import pathlib
import sys
import time

from dotenv import load_dotenv

from . import tmdb, omdb, letterboxd, youtube, rottentomatoes, metacritic, cache
from .aggregate import aggregate

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "movies.json"


def cached(key: str, fn):
    """Memoize fn() in the TTL cache. Exceptions return None and are NOT
    cached, so a flaky source gets retried on the next run."""
    val = cache.get(key)
    if val is not cache.MISS:
        return val
    try:
        val = fn()
    except Exception as e:
        print(f"   {key} failed: {e}", file=sys.stderr)
        return None
    cache.put(key, val)
    return val


def main(limit: int = 20):
    load_dotenv()
    if not os.environ.get("YOUTUBE_API_KEY"):
        print("note: YOUTUBE_API_KEY not set — buzz section will be empty")

    print("Fetching now-playing movies from TMDB (re-releases filtered)...")
    movies = tmdb.now_playing()[:limit]
    print(f"  {len(movies)} movies")

    results = []
    for m in movies:
        print(f"-> {m['title']}")
        mid = m["tmdb_id"]
        year = m["release_date"][:4] if m.get("release_date") else None
        sources: dict[str, float | None] = {"tmdb": m["tmdb_score"] or None}

        det = cached(f"tmdbdet:{mid}", lambda: tmdb.movie_details(mid)) or {}

        if det.get("imdb_id"):
            sources.update(
                cached(f"omdb:{mid}", lambda: omdb.scores(det["imdb_id"])) or {}
            )

        rt = cached(f"rt:{mid}",
                    lambda: rottentomatoes.scores(m["title"], year)) or {}
        mc = cached(f"mc:{mid}",
                    lambda: metacritic.score(m["title"], year))
        if mc is not None:
            sources["metacritic"] = mc          # scrape beats OMDb's metacritic
        if rt.get("critic") is not None:
            sources["rotten_tomatoes"] = rt["critic"]   # scrape beats OMDb's RT
        if rt.get("audience") is not None:
            sources["rt_audience"] = rt["audience"]     # new: audience score

        sources["letterboxd"] = cached(
            f"lbxd:{mid}",
            lambda: letterboxd.rating(tmdb_id=mid, title=m["title"],
                                      year=year, runtime=det.get("runtime")),
        )

        buzz = cached(f"yt:{mid}", lambda: youtube.sentiment(m["title"]))

        # Require at least 3 *review* sources (critic/aggregate sites), else the
        # composite isn't meaningful. rt_audience is an audience signal, not a
        # review source, so it doesn't count toward the minimum.
        REVIEW_KEYS = ("imdb", "rotten_tomatoes", "metacritic", "letterboxd", "tmdb")
        n_review = sum(1 for k in REVIEW_KEYS if sources.get(k) is not None)
        if n_review < 3:
            print(f"   skipping {m['title']}: only {n_review} review sources")
            time.sleep(0.5)
            continue

        agg = aggregate(sources)
        results.append(
            {
                "title": m["title"],
                "release_date": m["release_date"],
                "poster": m["poster"],
                "buzz": buzz,
                **agg,
            }
        )
        time.sleep(0.5)

    results.sort(key=lambda r: (r["composite"] is None, -(r["composite"] or 0)))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "sample": False,
                "movies": results,
            },
            indent=2,
        )
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
