import sqlite3

for db in [
    r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\edufeed.db",
    r"C:\Users\pc\Documents\OpenCood\FeedEdu\backend\gravity.db",
]:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    print("===", db)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("tables:", [r[0] for r in cur.fetchall()])
    for t in ("articles", "feeds", "folders"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t}:", cur.fetchone()[0])
        except Exception as e:
            print(f"{t} err:", e)
    try:
        cur.execute("SELECT COUNT(*) FROM articles WHERE is_done=1")
        print("is_done=1:", cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM articles WHERE is_posted=1")
        print("is_posted=1:", cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped=1")
        print("is_whatsapped=1:", cur.fetchone()[0])
    except Exception as e:
        print("status err:", e)
    conn.close()
