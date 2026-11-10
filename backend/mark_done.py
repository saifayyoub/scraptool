import json
import sqlite3
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db"

manifests = []
for b in ["batch3", "batch4", "batch5"]:
    manifests += json.load(
        open(rf"C:\Users\pc\Documents\OpenCood\Content\{b}\manifest.json", encoding="utf-8")
    )

fr_titles = [r["title"] for r in manifests if r["lang"] == "fr"]

ALIASES = {
    "Master ESEF Agadir 2026-2027": "Master ESEF Agadir 206-2027",
    "Bachelor en Technologie EST Laâyoune 2026-2027": "Bachelor en Technologie EST Laayoune 2026-2027",
    "Bachelor EST Agadir Centre Tata 2026-2027": "Bachelor en Technologie EST Agadir Centre Tata 2026-2027",
}

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

ids = []
unmatched = []
for t in fr_titles:
    candidates = [t] + ([ALIASES[t]] if t in ALIASES else [])
    hit = None
    for cand in candidates:
        cur.execute("SELECT id FROM articles WHERE title = ?", (cand,))
        hit = cur.fetchone()
        if hit:
            break
    if hit:
        ids.append(hit["id"])
    else:
        unmatched.append(t)

ids = list(dict.fromkeys(ids))
print(f"Updating {len(ids)} rows")
if unmatched:
    print(f"UNMATCHED ({len(unmatched)}): {unmatched}")

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
cur.executemany(
    "UPDATE articles SET is_done = 1, is_posted = 1, is_read = 1, updated_at = ? WHERE id = ?",
    [(now, i) for i in ids],
)
conn.commit()

cur.execute("SELECT is_done, is_posted, is_read FROM articles WHERE id IN ({})".format(",".join("?" * len(ids))), ids)
for r in cur.fetchall():
    if r["is_done"] != 1 or r["is_posted"] != 1:
        print(f"  FAILED id={r['id']}: {dict(r)}")

cur.execute("SELECT COUNT(*) AS c, SUM(is_done) AS d, SUM(is_posted) AS p, SUM(is_whatsapped) AS w FROM articles")
tot = cur.fetchone()
print(f"\nDashboard totals: {tot['c']} articles, done={tot['d']}, posted={tot['p']}, whatsapped={tot['w']}")
conn.close()
