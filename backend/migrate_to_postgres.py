"""Copy the local SQLite database into the PostgreSQL database in DATABASE_URL.

Deployed containers have no persistent disk, so EduFeed uses a PostgreSQL
database there (`DATABASE_URL`). This one-time script uploads the feeds,
folders and articles you already have locally so the deployed copy starts with
your current data.

Usage, from the `backend` folder:

    set DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require   (Windows)
    export DATABASE_URL="postgresql://..."                                    (macOS/Linux)
    python migrate_to_postgres.py

Optional: SQLITE_SOURCE=/path/to/other.db to copy a different SQLite file.
Re-running is safe: rows that already exist are skipped.
"""
import os
import sqlite3
import sys

from database import DB_PATH, IS_POSTGRES, get_db, init_db

TABLES = ("feeds", "folders", "articles")


def main():
    if not IS_POSTGRES:
        print("DATABASE_URL is not set (or is not a postgresql:// URL).")
        print("Set it to your hosted PostgreSQL connection string and run again.")
        return 1

    source = os.environ.get("SQLITE_SOURCE") or DB_PATH
    if not os.path.exists(source):
        print(f"SQLite source not found: {source}")
        return 1

    src = sqlite3.connect(source)
    src.row_factory = sqlite3.Row

    print("Preparing the PostgreSQL schema...")
    init_db()

    conn = get_db()
    cur = conn.cursor()
    try:
        for table in TABLES:
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"{table}: nothing to copy")
                continue
            columns = rows[0].keys()
            placeholders = ", ".join(["?"] * len(columns))
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            )
            cur.executemany(sql, [tuple(r) for r in rows])
            conn.commit()
            print(f"{table}: {len(rows)} rows copied")

        # Keep auto-increment counters ahead of the copied ids.
        for table in TABLES:
            try:
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"{table}: could not reset id counter ({e})")

        print("\nDone. The deployed app now shows your local data.")
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table} in PostgreSQL: {cur.fetchone()[0]}")
    finally:
        conn.close()
        src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
