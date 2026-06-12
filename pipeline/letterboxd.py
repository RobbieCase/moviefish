from __future__ import annotations
"""Letterboxd average rating, with verbose per-attempt logging and
wrong-film protection.

Strategy, in priority order:
  1. PRIMARY: https://letterboxd.com/tmdb/{tmdb_id}/ — Letterboxd's exact-match
     redirect, with one cache-busted retry (stale CDN edges have been seen
     serving outdated redirects to duplicate entries).
  2. FALLBACK: slug guesses (title, title-YEAR, title-YEAR-1).

Validation on EVERY landing page (both paths):
  - runtime check: Letterboxd hosts duplicate entries for the same title
    (e.g. an 18-min short sharing a slug family with a 108-min feature, which
    is exactly what burned us on Obsession). If TMDB says the film is ~108
    mins and the landing page says 18 mins, it's the wrong film — rejected.
  - year check (slug path only): guesses can land on reused titles from
    other decades.

Every attempt prints one line so the resolution is visible in the terminal.
"""
import re
import time as _time

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RUNTIME_TOLERANCE = 20  # minutes


def rating(tmdb_id: int | None = None, title: str | None = None,
           year: str | None = None, runtime: int | None = None) -> float | None:
    """Return the Letterboxd average normalized to 0-100, or None."""
    tag = f"letterboxd[{title or tmdb_id}]"

    # --- 1. primary: exact tmdb-id redirect, with one cache-busted retry ---
    if tmdb_id:
        attempts = [
            (f"https://letterboxd.com/tmdb/{tmdb_id}/", f"tmdb/{tmdb_id}"),
            (f"https://letterboxd.com/tmdb/{tmdb_id}/?cb={int(_time.time())}",
             f"tmdb/{tmdb_id} cache-busted retry"),
        ]
        for url, label in attempts:
            html = _fetch(url, tag, label)
            if html is None:
                continue
            if not _runtime_ok(html, runtime, tag, label):
                continue  # wrong film served; retry, then fall through to slugs
            raw = _extract(html)
            if raw is not None:
                print(f"   {tag}: {label} -> rating {raw}, returning {round(raw*20,1)}")
                return round(raw * 20, 1)
            print(f"   {tag}: {label} -> right film but no published rating yet")
            return None  # correct film, genuinely unrated: slugs won't do better

    # --- 2. fallback: slug guesses with year + runtime validation ---
    if title:
        for slug in _slugs(title, year):
            path = f"/film/{slug}/"
            html = _fetch(f"https://letterboxd.com{path}", tag, path)
            if html is None:
                continue
            page_year = _page_year(html)
            if year and page_year and abs(page_year - int(year)) > 1:
                print(f"   {tag}: {path} -> found film (year {page_year}, "
                      f"too far from {year}), moving on")
                continue
            if not _runtime_ok(html, runtime, tag, path):
                continue
            raw = _extract(html)
            if raw is None:
                print(f"   {tag}: {path} -> right era (year {page_year or '?'}) "
                      f"but no published rating on page")
                continue
            print(f"   {tag}: {path} -> rating {raw} (year {page_year or '?'}), "
                  f"returning {round(raw*20,1)}")
            return round(raw * 20, 1)

    print(f"   {tag}: exhausted all attempts, no rating")
    return None


def _fetch(url: str, tag: str, label: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    except requests.RequestException as e:
        print(f"   {tag}: {label} -> request failed ({e}), moving on")
        return None
    if "Just a moment" in r.text[:600]:
        print(f"   {tag}: {label} -> blocked by Cloudflare challenge, moving on")
        return None
    if r.status_code != 200:
        print(f"   {tag}: {label} -> HTTP {r.status_code}, moving on")
        return None
    if r.history:
        final = r.url.split("letterboxd.com")[-1]
        print(f"   {tag}: {label} -> redirected to {final}")
    return r.text


def _runtime_ok(html: str, runtime: int | None, tag: str, label: str) -> bool:
    """Reject landing pages whose runtime is far from TMDB's expectation."""
    if not runtime:
        return True  # nothing to compare against
    page_rt = _page_runtime(html)
    if page_rt is None:
        return True  # can't verify -> don't block
    if abs(page_rt - runtime) > RUNTIME_TOLERANCE:
        print(f"   {tag}: {label} -> WRONG FILM (page says {page_rt} mins, "
              f"expected ~{runtime}), moving on")
        return False
    return True


def _page_runtime(html: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:&nbsp;)?\s*mins", html)
    try:
        return int(m.group(1)) if m else None
    except ValueError:
        return None


def _extract(html: str) -> float | None:
    m = re.search(r'twitter:data2"\s+content="([\d.]+) out of 5"', html)
    if not m:
        m = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)', html)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return val if 0 < val <= 5 else None


def _page_year(html: str) -> int | None:
    m = re.search(r"/films/year/(\d{4})/", html)
    try:
        return int(m.group(1)) if m else None
    except ValueError:
        return None


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
