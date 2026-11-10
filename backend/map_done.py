import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db"

manifests = []
for b in ["batch3", "batch4", "batch5"]:
    manifests += json.load(
        open(rf"C:\Users\pc\Documents\OpenCood\Content\{b}\manifest.json", encoding="utf-8")
    )

# Published FR titles are the ones that map to FeedEdu source articles.
fr_titles = [r["title"] for r in manifests if r["lang"] == "fr"]

# Aliases for DB titles that differ slightly from published titles.
ALIASES = {
    "Master ESEF Agadir 2026-2027": "Master ESEF Agadir 206-2027",
    "Bachelor en Technologie EST Laâyoune 2026-2027": "Bachelor en Technologie EST Laayoune 2026-2027",
    "Bachelor EST Agadir Centre Tata 2026-2027": "Bachelor en Technologie EST Agadir Centre Tata 2026-2027",
}

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = []
for t in fr_titles:
    candidates = [t] + ([ALIASES[t]] if t in ALIASES else [])
    hit = None
    for cand in candidates:
        cur.execute("SELECT id, title, is_done, is_posted, is_read FROM articles WHERE title = ?", (cand,))
        r = cur.fetchone()
        if r:
            hit = r
            break
    if hit:
        rows.append((t, hit["id"], hit["title"], hit["is_done"], hit["is_posted"]))
    else:
        print(f"UNMATCHED: {t}")

print(f"\nMatched {len(rows)} published FR articles -> edufeed.db rows")
for t, aid, dbt, done, posted in rows:
    print(f"  db id={aid:<5} done={done} posted={posted} | {dbt[:70]}")
conn.close()
