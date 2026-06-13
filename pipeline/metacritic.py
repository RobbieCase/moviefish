from __future__ import annotations
"""Metacritic Metascore (critic) via the film page's JSON-LD aggregateRating.

Metacritic serves full pages to plain requests (unlike IMDb, which soft-blocks),
with the Metascore in a schema.org aggregateRating block: ratingValue 0-100 on a
bestRating of 100. Used as the primary Metacritic source; OMDb stays as fallback
when the scrape misses (which fills gaps for films OMDb hasn't ingested yet).

Slug: metacritic.com/movie/{title-kebab-case}. Many films resolve directly; a
miss falls through to OMDb rather than guessing aggressively.
"""
import json
import re

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def score(title: str, year: str | None = None) -> int | None:
    """Return the Metascore (0-100) or None. Logs each attempt."""
    tag = f"metacritic[{title}]"
    for slug in _slugs(title, year):
        url = f"https://www.metacritic.com/movie/{slug}/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            print(f"   {tag}: {slug} -> request failed ({e})")
            continue
        if "Just a moment" in r.text[:600] or "Access Denied" in r.text[:600]:
            print(f"   {tag}: {slug} -> blocked")
            continue
        if r.status_code == 404:
            continue
        if r.status_code != 200:
            print(f"   {tag}: {slug} -> HTTP {r.status_code}")
            continue
        val = _extract(r.text)
        if val is not None:
            print(f"   {tag}: {slug} -> metascore {val}")
            return val
        print(f"   {tag}: {slug} -> page loaded, no metascore yet")
    print(f"   {tag}: no metascore found")
    return None


def _extract(html: str) -> int | None:
    """Pull Metascore from the JSON-LD aggregateRating (ratingValue / 100)."""
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                            html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        agg = data.get("aggregateRating") if isinstance(data, dict) else None
        if not agg:
            continue
        # Metascore is the rating on a 100-point scale
        best = agg.get("bestRating")
        val = agg.get("ratingValue")
        try:
            val = int(float(val))
        except (TypeError, ValueError):
            continue
        if best in (100, "100") or val > 10:  # guard against a /10 user-score block
            if 0 <= val <= 100:
                return val
    return None


def _slugs(title: str, year: str | None) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    out = [base]
    if year:
        try:
            y = int(year)
            out += [f"{base}-{y}", f"{base}-{y - 1}"]
        except ValueError:
            out.append(f"{base}-{year}")
    return out
