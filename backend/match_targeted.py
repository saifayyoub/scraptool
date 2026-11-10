import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

queries = [
    ("Master ESEF Agadir 2026-2027", 14),
    ("Bachelor en Technologie EST Laâyoune 2026-2027", 9),
    ("Bachelor EST Agadir Centre Tata 2026-2027", 9),
]

for title, feed in queries:
    print("===", title, "(feed", feed, ")")
    kws = title.replace("-", " ").split()
    for kw in kws:
        if len(kw) < 4:
            continue
        cur.execute(
            "SELECT id, title, feed_id, is_done, is_posted FROM articles WHERE feed_id=? AND title LIKE ?",
            (feed, f"%{kw}%"),
        )
        for r in cur.fetchall():
            print(f"  [{kw}] id={r['id']} feed={r['feed_id']} done={r['is_done']} posted={r['is_posted']} :: {r['title'][:100]}")
conn.close()
