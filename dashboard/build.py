"""Inject data/movies.json (or sample data if absent) into the dashboard template."""
import json, pathlib

root = pathlib.Path(__file__).resolve().parents[1]
data_file = root / "data" / "movies.json"
if not data_file.exists():
    data_file = root / "data" / "sample_movies.json"
    print("No live data found - building with sample data.")

template = (root / "dashboard" / "template.html").read_text()
html = template.replace("/*__DATA__*/", json.dumps(json.loads(data_file.read_text())))
out = root / "output" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html)
print(f"Wrote {out}")
