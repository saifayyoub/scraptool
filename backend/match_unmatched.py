import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

manifests = []
for b in ["batch3", "batch4", "batch5"]:
    manifests += json.load(
        open(rf"C:\Users\pc\Documents\OpenCood\Content\{b}\manifest.json", encoding="utf-8")
    )
fr_titles = [r["title"] for r in manifests if r["lang"] == "fr"]

conn = sqlite3.connect(r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find which were NOT matched exactly
matched_ids = set()
for t in fr_titles:
    cur.execute("SELECT id FROM articles WHERE title = ?", (t,))
    for r in cur.fetchall():
        matched_ids.add(r["id"])

print("=== Exact unmatched published titles + fuzzy candidates ===")
for t in fr_titles:
    cur.execute("SELECT id FROM articles WHERE title = ?", (t,))
    if not cur.fetchall():
        print(f"NO EXACT: '{t}'")
        for kw in t.split()[0:3]:
            cur.execute("SELECT id, title, feed_id, is_done, is_posted FROM articles WHERE title LIKE ? LIMIT 5", (f"%{kw}%",))
            for r in cur.fetchall():
                print(f"    cand[{kw}]: id={r['id']} feed={r['feed_id']} done={r['is_done']} posted={r['is_posted']} :: {r['title']}")
conn.close()
