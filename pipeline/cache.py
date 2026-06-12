from __future__ import annotations
from __future__ import annotations
"""Tiny JSON file cache with a TTL, so repeated runs within the same day
don't re-hammer OMDb, Letterboxd, and Reddit for movies already fetched.

Usage:
    from . import cache
    val = cache.get("omdb:tt1234567")
    if val is _MISS: ...
"""
import json
import pathlib
import time

PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "cache.json"
TTL = 20 * 3600  # 20 hours: a daily cron always refetches

_MISS = object()


def _load() -> dict:
    if PATH.exists():
        try:
            return json.loads(PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def get(key: str):
    """Return cached value (may be None!) or the sentinel cache.MISS."""
    entry = _load().get(key)
    if entry and time.time() - entry["t"] < TTL:
        return entry["v"]
    return _MISS


def put(key: str, value) -> None:
    data = _load()
    data[key] = {"t": time.time(), "v": value}
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps(data))


MISS = _MISS
