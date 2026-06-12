from __future__ import annotations
from __future__ import annotations
"""Run the full pipeline: theaters -> scores -> sentiment -> data/movies.json.

Usage:
    cp config.example.env .env   # add your keys
    pip install -r requirements.txt
    python -m pipeline.run
    python dashboard/build.py    # -> output/index.html

Lookups are cached for ~20h (data/cache.json), so re-running after a crash
or a template tweak is cheap and polite.
"""
import json
import pathlib
import sys
import time

from dotenv import load_dotenv

from . import tmdb, omdb, letterboxd, reddit, cache
from .aggregate import aggregate

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "movies.json"


def cached(key: str, fn):
    """Memoize fn() in the TTL cache. Failures return None and are NOT cached,
    so a flaky source gets retried on the next run."""
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
    print("Fetching now-playing movies from TMDB...")
    movies = tmdb.now_playing()[:limit]
    print(f"  {len(movies)} movies")

    results = []
    for m in movies:
        print(f"-> {m['title']}")
        mid = m["tmdb_id"]
        year = m["release_date"][:4] if m.get("release_date") else None
        sources: dict[str, float | None] = {"tmdb": m["tmdb_score"] or None}

        omdb_scores = cached(f"omdb:{mid}", lambda: _omdb_for(mid)) or {}
        sources.update(omdb_scores)

        sources["letterboxd"] = cached(
            f"lbxd:{mid}",
            lambda: letterboxd.rating(tmdb_id=mid, title=m["title"], year=year),
        )

        red = cached(f"reddit:{mid}", lambda: reddit.sentiment(m["title"]))
        if red:
            sources["reddit"] = red["score"]

        agg = aggregate(sources)
        results.append(
            {
                "title": m["title"],
                "release_date": m["release_date"],
                "poster": m["poster"],
                "reddit_posts": red["n_posts"] if red else 0,
                **agg,
            }
        )
        time.sleep(0.5)  # global politeness delay

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


def _omdb_for(tmdb_id: int) -> dict:
    imdb_id = tmdb.imdb_id_for(tmdb_id)
    return omdb.scores(imdb_id) if imdb_id else {}


if __name__ == "__main__":
    main()
