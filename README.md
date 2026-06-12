# MoviePulse

Every movie currently in theaters, scored across all the major systems —
IMDb, Rotten Tomatoes, Metacritic, Letterboxd, TMDB, and Reddit sentiment —
normalized to one 0–100 axis so you can see not just *how good* a film is,
but *how much the sources disagree*.

## Quick start

```bash
pip install -r requirements.txt
python dashboard/build.py        # builds output/index.html with sample data
```

To run it live:

```bash
cp config.example.env .env       # add your TMDB + OMDb keys (both free)
python -m pipeline.run           # fetches everything -> data/movies.json
python dashboard/build.py        # rebuilds the dashboard with real data
```

Open `output/index.html`. Re-run the pipeline daily (cron / GitHub Action)
and the board stays current.

## How each source is fetched

| Source | Method | Notes |
|---|---|---|
| Now playing | TMDB `/movie/now_playing` | free key |
| IMDb, RT, Metacritic | OMDb API | one free key covers all three |
| Letterboxd | page scrape (meta tag) | no public API; most fragile module |
| Reddit | public JSON search + VADER | r/movies + r/boxoffice, last 30 days |
| Twitter/X | **not implemented** | X's read API has no free tier; Bluesky's free `searchPosts` is the drop-in alternative |

## Normalization & composite

IMDb ×10, Letterboxd ×20, RT/Metacritic as-is, TMDB ×10, Reddit VADER
compound mapped from −1..1 to 0..100. Composite is a weighted mean
(TMDB and Reddit down-weighted — see `pipeline/aggregate.py`).
A **spread** ≥ 25 points flags a film as *contested*, which is usually
where the interesting movies live (audience-pleasers critics hated, and
vice versa).

## Caveats worth knowing

- Reddit "sentiment" measures the tone of discussion, not quality. A
  beloved-but-divisive film can score low because people are arguing.
- Letterboxd slugs are guessed from titles; remakes with reused titles
  can mismatch. Check `data/movies.json` if a number looks wrong.
- Be a polite scraper: the pipeline sleeps between requests and is meant
  to run a few times a day, not continuously.

## Ideas for v2

- Cache + history: store daily snapshots, chart score drift after opening weekend
- Critic-vs-audience delta as its own sortable column
- Bluesky sentiment module
- Letterboxd via TMDB-id search instead of slug guessing
