import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

manifests = []
for b in ["batch3", "batch4", "batch5"]:
    manifests += json.load(
        open(rf"C:\Users\pc\Documents\OpenCood\Content\{b}\manifest.json", encoding="utf-8")
    )

# Distinct FR titles published
fr_titles = [r["title"] for r in manifests if r["lang"] == "fr"]

conn = sqlite3.connect(r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== edufeed.db: search published FR titles ===")
matched = []
for t in fr_titles:
    cur.execute("SELECT id, title, feed_id, is_done, is_posted FROM articles WHERE title LIKE ?", (t,))
    rows = cur.fetchall()
    if rows:
        matched.append((t, rows))
for t, rows in matched:
    for r in rows:
        print(f"  '{t}' -> db id={r['id']} feed_id={r['feed_id']} done={r['is_done']} posted={r['is_posted']}")

print("\nTotal published FR titles:", len(fr_titles), "| matched in edufeed.db:", len(matched))

print("\n=== edufeed.db feeds ===")
for r in cur.execute("SELECT id, title, url FROM feeds"):
    print(" ", dict(r))

conn.close()
