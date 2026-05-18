import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "edufeed.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create feeds table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create articles table
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
            FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    
    # Run migrations for new columns if they don't exist
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN is_posted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN is_whatsapped BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN is_done BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN edited_title TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN edited_description TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN edited_content TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
