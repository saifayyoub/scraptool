import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edufeed.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_id INTEGER,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published_date TEXT,
            description TEXT,
            is_read BOOLEAN DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # Migrations
    for col, default in [
        ("is_posted", "0"), ("is_whatsapped", "0"), ("is_done", "0"),
        ("edited_title", None), ("edited_description", None), ("edited_content", None),
        ("is_starred", "0"), ("fulltext_attempted", "0")
    ]:
        try:
            if default is None:
                cursor.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")
            else:
                cursor.execute(f"ALTER TABLE articles ADD COLUMN {col} BOOLEAN DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN updated_at TIMESTAMP")
        cursor.execute("UPDATE articles SET updated_at = COALESCE(added_at, datetime('now')) WHERE updated_at IS NULL")
    except sqlite3.OperationalError:
        pass

    for col in ["folder_id", "sort_order"]:
        try:
            if col == "folder_id":
                cursor.execute(f"ALTER TABLE feeds ADD COLUMN {col} INTEGER REFERENCES folders(id) ON DELETE SET NULL")
            else:
                cursor.execute(f"ALTER TABLE feeds ADD COLUMN {col} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    for col, default in [("max_entries", "20"), ("scan_interval", "0"), ("proxy", "''"), ("username", "''"), ("password", "''")]:
        try:
            cursor.execute(f"ALTER TABLE feeds ADD COLUMN {col} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    try:
        cursor.execute("ALTER TABLE feeds ADD COLUMN full_text INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
