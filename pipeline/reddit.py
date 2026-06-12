from __future__ import annotations
"""Reddit buzz + sentiment, now via Reddit's free OAuth API.

Reddit blocks most unauthenticated .json requests these days, so this module
authenticates as a "script" app (free, takes 2 minutes to register):

  1. reddit.com/prefs/apps -> "create another app"
  2. type: script, name: MovieFish, redirect uri: http://localhost:8080
  3. The string under the app name is your CLIENT_ID; "secret" is the SECRET.
  4. Add to .env:
       REDDIT_CLIENT_ID=...
       REDDIT_CLIENT_SECRET=...

If no credentials are set, it falls back to the public endpoint (which may
403) — and either way it now prints loudly instead of failing silently.

Sentiment is VADER over recent r/movies + r/boxoffice post titles/bodies.
"""
import os
import time

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

UA = {"User-Agent": "MovieFish/0.2 (personal score aggregator; low volume)"}
SUBREDDITS = ["movies", "boxoffice"]
_an = SentimentIntensityAnalyzer()
_token: dict = {"v": None, "exp": 0.0}


def _auth() -> str | None:
    """App-only OAuth token via client_credentials. Cached until expiry."""
    cid = os.environ.get("REDDIT_CLIENT_ID")
    sec = os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not sec:
        return None
    if _token["v"] and time.time() < _token["exp"] - 60:
        return _token["v"]
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(cid, sec),
        data={"grant_type": "client_credentials"},
        headers=UA,
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    _token["v"] = j["access_token"]
    _token["exp"] = time.time() + j.get("expires_in", 3600)
    return _token["v"]


def sentiment(title: str, max_posts: int = 25) -> dict | None:
    """Return {'score': 0-100, 'n_posts': int, 'raw_compound': -1..1} or None."""
    try:
        token = _auth()
    except Exception as e:
        print(f"   reddit: auth failed ({e}); falling back to public endpoint")
        token = None

    base = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"bearer {token}"

    texts: list[str] = []
    for sub in SUBREDDITS:
        try:
            r = requests.get(
                f"{base}/r/{sub}/search.json",
                params={
                    "q": f'"{title}"',
                    "restrict_sr": "on",
                    "sort": "new",
                    "t": "month",
                    "limit": max_posts,
                },
                headers=headers,
                timeout=15,
            )
            if r.status_code != 200:
                hint = "" if token else " — Reddit blocks anonymous requests; add REDDIT_CLIENT_ID/SECRET to .env (see pipeline/reddit.py)"
                print(f"   reddit: HTTP {r.status_code} on r/{sub}{hint}")
                continue
            for child in r.json().get("data", {}).get("children", []):
                d = child.get("data", {})
                txt = " ".join(filter(None, [d.get("title"), d.get("selftext")]))
                if txt.strip():
                    texts.append(txt[:1500])
            time.sleep(0.6)  # stay well inside rate limits
        except requests.RequestException as e:
            print(f"   reddit: request failed on r/{sub}: {e}")
            continue

    if not texts:
        return None

    compounds = [_an.polarity_scores(t)["compound"] for t in texts]
    avg = sum(compounds) / len(compounds)
    return {
        "score": round((avg + 1) * 50, 1),  # -1..1 -> 0..100
        "n_posts": len(texts),
        "raw_compound": round(avg, 3),
    }
