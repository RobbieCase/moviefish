from __future__ import annotations
from __future__ import annotations
"""Letterboxd average rating — now matched by TMDB id, not slug guessing.

Letterboxd exposes a stable redirect: https://letterboxd.com/tmdb/{tmdb_id}/
lands on the exact film page for that TMDB entry. This kills the wrong-film
problem that title-slug guessing had (remakes, reused titles).

Two safety layers remain:
  1. A release-year sanity check against TMDB's year (tolerates ±1 for
     festival/wide-release gaps). A mismatch drops the score rather than
     poisoning the composite.
  2. Slug guessing is kept only as a fallback if the tmdb redirect 404s.
"""
import re
import requests

UA = {"User-Agent": "MoviePulse/0.2 (personal score aggregator; low volume)"}


def rating(tmdb_id: int | None = None, title: str | None = None,
           year: str | None = None) -> float | None:
    """Return the Letterboxd average normalized to 0-100, or None."""
    urls: list[str] = []
    if tmdb_id:
        urls.append(f"https://letterboxd.com/tmdb/{tmdb_id}/")
    if title:
        urls += [f"https://letterboxd.com/film/{s}/" for s in _slugs(title, year)]

    for url in urls:
        try:
            r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
            if r.status_code != 200:
                continue
            if year and not _year_ok(r.text, year):
                print(f"   letterboxd: year mismatch at {r.url}, dropping score")
                continue
            m = re.search(r'twitter:data2"\s+content="([\d.]+) out of 5"', r.text)
            if m:
                return round(float(m.group(1)) * 20, 1)  # /5 -> /100
        except requests.RequestException:
            continue
    return None


def _year_ok(html: str, year: str) -> bool:
    m = re.search(r"/films/year/(\d{4})/", html)
    if not m:
        return True  # can't verify -> don't block
    try:
        return abs(int(m.group(1)) - int(year)) <= 1
    except ValueError:
        return True


def _slugs(title: str, year: str | None) -> list[str]:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    out = [slug]
    if year:
        try:
            y = int(year)
            out += [f"{slug}-{y}", f"{slug}-{y - 1}"]
        except ValueError:
            out.append(f"{slug}-{year}")
    return out
