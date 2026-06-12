"""Inject data/movies.json into the dashboard template. No sample fallback:
if the pipeline hasn't produced real data, the build fails loudly instead of
shipping placeholder movies."""
import json, pathlib, sys

root = pathlib.Path(__file__).resolve().parents[1]
data_file = root / "data" / "movies.json"
if not data_file.exists():
    sys.exit("No data/movies.json found - run `python -m pipeline.run` first. "
             "Refusing to build with no data.")

data = json.loads(data_file.read_text())
if not data.get("movies"):
    sys.exit("data/movies.json contains no movies - refusing to build an empty board.")

template = (root / "dashboard" / "template.html").read_text()
html = template.replace("/*__DATA__*/", json.dumps(data))
out = root / "output" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html)
print(f"Wrote {out} ({len(data['movies'])} movies)")
