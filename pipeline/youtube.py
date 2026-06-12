from __future__ import annotations
"""Fan buzz from YouTube trailer comments — sentiment breakdown, not just a score.

Returns a structured analysis:
  {
    "pos": 62,            # % of analyzed comments that read excited/positive
    "neu": 24,            # % neutral / unclear
    "neg": 14,            # % negative ("looks bad")
    "score": 74.0,        # avg VADER compound mapped to 0-100 (sorting only;
                          #  NOT part of the review composite)
    "analyzed": 400,      # comments actually scored (up to ~400, paginated)
    "total": 18432,       # the video's real total comment count (videos.list)
    "video_id": "..."
  }

Buckets: VADER compound >= +0.25 -> positive, <= -0.25 -> negative, else neutral.

Quota: search 100u + statistics 1u + up to 4 comment pages at 1u each
per film -> ~105u x 20 films ≈ 2,100 of the 10,000 free daily units.
"""
import os

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

BASE = "https://www.googleapis.com/youtube/v3"
_an = SentimentIntensityAnalyzer()

POS_T, NEG_T = 0.25, -0.25
MAX_ANALYZED = 400  # 4 pages of 100


def sentiment(title: str) -> dict | None:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return None

    videos = _find_trailers(title, key)
    for vid in videos:
        texts = _comments(vid, key)
        if not texts:
            continue

        compounds = [_an.polarity_scores(t)["compound"] for t in texts]
        n = len(compounds)
        pos = sum(1 for c in compounds if c >= POS_T)
        neg = sum(1 for c in compounds if c <= NEG_T)
        neu = n - pos - neg
        avg = sum(compounds) / n

        return {
            "pos": round(100 * pos / n),
            "neu": round(100 * neu / n),
            "neg": round(100 * neg / n),
            "score": round((avg + 1) * 50, 1),
            "analyzed": n,
            "total": _comment_total(vid, key) or n,
            "video_id": vid,
        }
    return None


def _find_trailers(title: str, key: str) -> list[str]:
    r = requests.get(
        f"{BASE}/search",
        params={"key": key, "q": f"{title} official trailer",
                "part": "snippet", "type": "video", "maxResults": 3},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"   youtube: search HTTP {r.status_code}: {r.text[:120]}")
        return []
    return [it["id"]["videoId"] for it in r.json().get("items", [])]


def _comment_total(vid: str, key: str) -> int | None:
    """Real total comment count from the video's statistics."""
    r = requests.get(
        f"{BASE}/videos",
        params={"key": key, "id": vid, "part": "statistics"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    items = r.json().get("items", [])
    try:
        return int(items[0]["statistics"]["commentCount"])
    except (IndexError, KeyError, ValueError):
        return None


def _comments(vid: str, key: str) -> list[str]:
    """Up to MAX_ANALYZED relevance-ranked comments, paginated."""
    texts: list[str] = []
    token = None
    while len(texts) < MAX_ANALYZED:
        params = {"key": key, "videoId": vid, "part": "snippet",
                  "maxResults": 100, "order": "relevance",
                  "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{BASE}/commentThreads", params=params, timeout=15)
        if r.status_code == 403:  # comments disabled on this video
            return []
        if r.status_code != 200:
            print(f"   youtube: comments HTTP {r.status_code} on {vid}")
            break
        data = r.json()
        for it in data.get("items", []):
            texts.append(
                it["snippet"]["topLevelComment"]["snippet"]["textDisplay"][:1500]
            )
        token = data.get("nextPageToken")
        if not token:
            break
    return texts
