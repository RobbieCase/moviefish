from __future__ import annotations
from __future__ import annotations
"""Fetch IMDb, Rotten Tomatoes, and Metacritic scores via OMDb (free key: omdbapi.com/apikey.aspx)."""
import os
import requests


def scores(imdb_id: str) -> dict:
    """Return normalized 0-100 scores: {'imdb': .., 'rotten_tomatoes': .., 'metacritic': ..}.

    Missing sources are simply absent from the dict.
    """
    key = os.environ["OMDB_API_KEY"]
    r = requests.get(
        "https://www.omdbapi.com/",
        params={"apikey": key, "i": imdb_id, "tomatoes": "true"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    out: dict[str, int] = {}

    for rating in data.get("Ratings", []):
        src, val = rating.get("Source"), rating.get("Value", "")
        try:
            if src == "Internet Movie Database":  # "7.8/10"
                out["imdb"] = round(float(val.split("/")[0]) * 10)
            elif src == "Rotten Tomatoes":  # "84%"
                out["rotten_tomatoes"] = int(val.rstrip("%"))
            elif src == "Metacritic":  # "67/100"
                out["metacritic"] = int(val.split("/")[0])
        except (ValueError, IndexError):
            continue
    return out
