import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\gravity.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM feeds")
for r in cur.fetchall():
    print("FEED:", dict(r))
cur.execute("SELECT * FROM articles ORDER BY id")
for r in cur.fetchall():
    d = dict(r)
    print(d["id"], "|", d["title"][:80], "|", d["link"])
conn.close()
