from __future__ import annotations
"""Rotten Tomatoes critic (Tomatometer) + audience (Popcornmeter) scores.

RT has no public API, but each film page embeds a JSON blob with both scores
fully structured. We read criticsScore and audienceScore from it. This gives
us something OMDb never could: the AUDIENCE score, so the board can show the
critics-vs-audience split — the juiciest "where do they disagree" signal.

Slug resolution: RT slugs are usually m/{title_snake_case}; when that misses
we fall back to RT's own search-suggestion endpoint, which maps a title to its
canonical URL. One daily fetch per film; results cached upstream.

Returns: {"critic": 96, "audience": 99, "critic_sentiment": "POSITIVE",
          "audience_sentiment": "POSITIVE", "slug": "..."}  (keys absent if
not found). Scores are already 0-100 percentages.
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


def scores(title: str, year: str | None = None) -> dict | None:
    """Return {'critic','audience',...} or None. Logs each attempt."""
    tag = f"rt[{title}]"
    for slug in _slug_candidates(title, year):
        url = f"https://www.rottentomatoes.com/m/{slug}"
        html = _fetch(url, tag, slug)
        if html is None:
            continue
        out = _parse(html)
        if out:
            out["slug"] = slug
            bits = []
            if "critic" in out:   bits.append(f"critic {out['critic']}")
            if "audience" in out: bits.append(f"audience {out['audience']}")
            print(f"   {tag}: m/{slug} -> {', '.join(bits)}")
            return out
        print(f"   {tag}: m/{slug} -> page loaded, no scores yet")

    # fallback: RT search suggestion endpoint resolves the real slug
    slug = _search_slug(title, tag)
    if slug:
        html = _fetch(f"https://www.rottentomatoes.com/m/{slug}", tag, f"search:{slug}")
        if html:
            out = _parse(html)
            if out:
                out["slug"] = slug
                print(f"   {tag}: m/{slug} (via search) -> "
                      f"critic {out.get('critic','-')}, audience {out.get('audience','-')}")
                return out

    print(f"   {tag}: no RT scores found")
    return None


def _fetch(url: str, tag: str, label: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"   {tag}: {label} -> request failed ({e})")
        return None
    if "Just a moment" in r.text[:600]:
        print(f"   {tag}: {label} -> blocked by Cloudflare")
        return None
    if r.status_code == 404:
        return None  # wrong slug; quietly try next
    if r.status_code != 200:
        print(f"   {tag}: {label} -> HTTP {r.status_code}")
        return None
    return r.text


def _parse(html: str) -> dict | None:
    out: dict = {}
    cm = re.search(r'"criticsScore":\s*(\{[^}]*\})', html)
    am = re.search(r'"audienceScore":\s*(\{[^}]*\})', html)
    for key, m in (("critic", cm), ("audience", am)):
        if not m:
            continue
        try:
            blob = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        score = blob.get("score")
        if score and str(score).isdigit():
            out[key] = int(score)
            if blob.get("sentiment"):
                out[f"{key}_sentiment"] = blob["sentiment"]
    return out or None


def _search_slug(title: str, tag: str) -> str | None:
    try:
        r = requests.get(
            "https://www.rottentomatoes.com/napi/search/",
            params={"query": title, "type": "movie", "limit": 3},
            headers=HEADERS, timeout=15,
        )
        if r.status_code != 200:
            return None
        for item in r.json().get("movies", []):
            url = item.get("url", "")
            m = re.search(r"/m/([^/]+)", url)
            if m:
                return m.group(1)
    except (requests.RequestException, ValueError):
        return None
    return None


def _slug_candidates(title: str, year: str | None) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    out = [base]
    if year:
        try:
            y = int(year)
            # RT slugs by release year, but festival-circuit films are often
            # slugged a year earlier than their wide-release date (e.g. The
            # Furious is the_furious_2025 despite a 2026 theatrical date).
            out += [f"{base}_{y}", f"{base}_{y - 1}"]
        except ValueError:
            out.append(f"{base}_{year}")
    return out
