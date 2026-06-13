from __future__ import annotations
"""Combine per-source scores into a composite, and measure disagreement.

All sources are normalized to 0-100 upstream:
  IMDb        /10  -> x10
  RT          %    -> as-is
  Metacritic  /100 -> as-is
  Letterboxd  /5   -> x20
  TMDB        /10  -> x10
  Reddit      VADER compound -1..1 -> (x+1)*50

The composite is a weighted mean of whatever sources are present.
Spread (max - min across sources) is the interesting signal: a movie with
an 85 composite and a 40-point spread is a very different object than one
with an 85 and a 6-point spread.
"""

WEIGHTS = {
    "imdb": 1.0,
    "rotten_tomatoes": 1.0,
    "metacritic": 1.0,
    "letterboxd": 1.0,
    "tmdb": 0.6,    # overlaps heavily with IMDb's audience
    "rt_audience": 0.8,  # RT Popcornmeter — real audience signal
}

CONTESTED_SPREAD = 25  # points


def aggregate(sources: dict[str, float]) -> dict:
    """sources: {'imdb': 78, 'rotten_tomatoes': 91, ...} -> summary dict."""
    present = {k: v for k, v in sources.items() if v is not None}
    if not present:
        return {"composite": None, "spread": None, "contested": False, "sources": {}}

    wsum = sum(WEIGHTS.get(k, 0.5) for k in present)
    composite = sum(v * WEIGHTS.get(k, 0.5) for k, v in present.items()) / wsum
    spread = max(present.values()) - min(present.values())

    return {
        "composite": round(composite, 1),
        "spread": round(spread, 1),
        "contested": spread >= CONTESTED_SPREAD,
        "sources": present,
    }
