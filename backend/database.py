"""Database access layer.

Local use keeps the bundled SQLite file (`edufeed.db`), so `run.bat` works with
no setup. Container platforms wipe the filesystem on every restart/redeploy, so
on a server you set the `DATABASE_URL` environment variable to a PostgreSQL
database (for example a free Neon project) and the exact same queries run
against it instead.

Only the small compatibility layer below is engine specific: it accepts the
SQLite style `?` placeholders used by the app, maps a few SQLite functions to
PostgreSQL equivalents, and makes rows readable both by position and by name.
"""
import os
import queue
import re
import sqlite3
import time
from urllib.parse import parse_qs, unquote, urlparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edufeed.db")

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


# ── SQLite (local) ───────────────────────────────────────────────────────────

def _sqlite_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── PostgreSQL (deployed) ────────────────────────────────────────────────────

_TS_NOW = "to_char((now() at time zone 'utc'), 'YYYY-MM-DD HH24:MI:SS')"

_DATETIME_INTERVAL = re.compile(r"datetime\(\s*'now'\s*,\s*'(-?\d+)\s+days?'\s*\)", re.I)
_DATETIME_NOW = re.compile(r"datetime\(\s*'now'\s*\)", re.I)
_DATE_OF_ADDED = re.compile(r"\bdate\(\s*added_at\s*\)", re.I)
_CURRENT_TIMESTAMP = re.compile(r"\bCURRENT_TIMESTAMP\b", re.I)


def _shift_now(days):
    days = int(days)
    sign = "+" if days >= 0 else "-"
    return f"to_char((now() at time zone 'utc') {sign} interval '{abs(days)} days', 'YYYY-MM-DD HH24:MI:SS')"


def _qmark_to_format(sql):
    """Turn SQLite `?` placeholders into pg8000 `%s` placeholders."""
    out = []
    quote = None
    for ch in sql:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "?":
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def _translate(sql):
    """Rewrite the handful of SQLite only bits into PostgreSQL SQL."""
    out = _DATETIME_INTERVAL.sub(lambda m: _shift_now(m.group(1)), sql)
    out = _DATETIME_NOW.sub(_TS_NOW, out)
    out = _DATE_OF_ADDED.sub("substr(added_at, 1, 10)", out)
    out = _CURRENT_TIMESTAMP.sub(_TS_NOW, out)
    out = out.replace("%", "%%")  # literal percents, pg8000 uses %s placeholders
    return _qmark_to_format(out)


class Row:
    """Row that can be read by position (row[0]) or by column name (row['id'])."""

    __slots__ = ("_values", "_keys", "_index")

    def __init__(self, values, keys):
        self._values = tuple(values)
        self._keys = tuple(keys)
        self._index = {k: i for i, k in enumerate(self._keys)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._keys)

    def __repr__(self):
        return repr(self._values)


class PgCursor:
    def __init__(self, conn):
        self._cur = conn.cursor()
        self._keys = []

    def execute(self, sql, params=None):
        if params:
            self._cur.execute(_translate(sql), list(params))
        else:
            self._cur.execute(_translate(sql))
        desc = self._cur.description
        self._keys = [d[0] for d in desc] if desc else []
        return self

    def executemany(self, sql, seq_params):
        self._cur.executemany(_translate(sql), [list(p) for p in seq_params])
        return self

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        raise NotImplementedError("Use INSERT ... RETURNING or SELECT after INSERT")

    def _wrap(self, row):
        return None if row is None else Row(row, self._keys)

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        return [self._wrap(r) for r in rows]

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


try:
    _POOL_MAX = max(1, int(os.environ.get("DB_POOL_SIZE", "4")))
except ValueError:
    _POOL_MAX = 4
_pool = queue.LifoQueue(maxsize=_POOL_MAX)


def _new_pg_connection():
    import pg8000.dbapi  # imported lazily: local SQLite use needs no driver

    parsed = urlparse(DATABASE_URL)
    query = parse_qs(parsed.query)
    sslmode = (query.get("sslmode") or ["prefer"])[0].lower()
    kwargs = {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/").lstrip("/") or "postgres",
        "timeout": 20,
    }
    if sslmode == "disable":
        kwargs["ssl_context"] = False
    else:
        kwargs["ssl_context"] = True
    return pg8000.dbapi.connect(**kwargs)


def _acquire_pg_connection():
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            return _new_pg_connection()
        # Hosted databases drop idle connections; check only ones left a while.
        if time.time() - getattr(conn, "_edufeed_checked", 0) < 60:
            return conn
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn._edufeed_checked = time.time()
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def _release_pg_connection(conn):
    conn._edufeed_checked = time.time()
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        try:
            conn.close()
        except Exception:
            pass


class PgConnection:
    def __init__(self):
        self._conn = _acquire_pg_connection()
        self._closed = False

    def cursor(self):
        return PgCursor(self._conn)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    @property
    def connection(self):
        return self

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.rollback()  # clears any uncommitted statement before reuse
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            return
        _release_pg_connection(self._conn)


# ── Public API ───────────────────────────────────────────────────────────────

def get_db():
    if IS_POSTGRES:
        return PgConnection()
    return _sqlite_connect()


# Column layout the app expects. Tables are created with it and older databases
# get the missing columns added, on both engines.
_FEED_COLUMNS = [
    ("folder_id", "INTEGER"),
    ("sort_order", "INTEGER DEFAULT 0"),
    ("max_entries", "INTEGER DEFAULT 20"),
    ("scan_interval", "INTEGER DEFAULT 0"),
    ("proxy", "TEXT DEFAULT ''"),
    ("username", "TEXT DEFAULT ''"),
    ("password", "TEXT DEFAULT ''"),
    ("full_text", "INTEGER DEFAULT 1"),
]

_ARTICLE_COLUMNS = [
    ("is_posted", "INTEGER DEFAULT 0"),
    ("is_whatsapped", "INTEGER DEFAULT 0"),
    ("is_done", "INTEGER DEFAULT 0"),
    ("edited_title", "TEXT"),
    ("edited_description", "TEXT"),
    ("edited_content", "TEXT"),
    ("is_starred", "INTEGER DEFAULT 0"),
    ("fulltext_attempted", "INTEGER DEFAULT 0"),
    ("updated_at", "TEXT"),
]

def _existing_columns(conn, table):
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ?",
            (table,),
        )
    else:
        cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    cur.close()
    if IS_POSTGRES:
        return {r[0] for r in rows}
    return {r[1] for r in rows}


def _create_tables(conn):
    cur = conn.cursor()
    if IS_POSTGRES:
        id_column = "SERIAL PRIMARY KEY"
        ts_default = f"DEFAULT {_TS_NOW}"
    else:
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_default = "DEFAULT CURRENT_TIMESTAMP"

    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS feeds (
            id {id_column},
            title TEXT,
            url TEXT UNIQUE NOT NULL,
            added_at TEXT {ts_default},
            folder_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            max_entries INTEGER DEFAULT 20,
            scan_interval INTEGER DEFAULT 0,
            proxy TEXT DEFAULT '',
            username TEXT DEFAULT '',
            password TEXT DEFAULT '',
            full_text INTEGER DEFAULT 1
        )
    ''')
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS articles (
            id {id_column},
            feed_id INTEGER,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published_date TEXT,
            description TEXT,
            is_read INTEGER DEFAULT 0,
            added_at TEXT {ts_default},
            updated_at TEXT,
            is_posted INTEGER DEFAULT 0,
            is_whatsapped INTEGER DEFAULT 0,
            is_done INTEGER DEFAULT 0,
            edited_title TEXT,
            edited_description TEXT,
            edited_content TEXT,
            is_starred INTEGER DEFAULT 0,
            fulltext_attempted INTEGER DEFAULT 0,
            FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
        )
    ''')
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS folders (
            id {id_column},
            name TEXT NOT NULL,
            created_at TEXT {ts_default}
        )
    ''')
    cur.close()
    conn.commit()


def _add_missing_columns(conn, table, columns):
    present = _existing_columns(conn, table)
    for name, decl in columns:
        if name in present:
            continue
        cur = conn.cursor()
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
            conn.commit()
            print(f"Database migration: added {table}.{name}")
        except Exception as e:  # column already there on some engines
            conn.rollback()
            print(f"Database migration skipped {table}.{name}: {e}")
        finally:
            cur.close()


def init_db():
    if IS_POSTGRES:
        last_error = None
        for attempt in range(3):
            try:
                conn = get_db()
                break
            except Exception as e:  # database waking up / cold start
                last_error = e
                print(f"Database connection attempt {attempt + 1} failed: {e}")
        else:
            raise last_error
    else:
        conn = get_db()

    try:
        for attempt in range(2):
            try:
                _create_tables(conn)
                break
            except Exception as e:
                conn.rollback()
                if attempt:
                    raise
                print(f"Schema creation retry ({e})")
                time.sleep(1)
        _add_missing_columns(conn, "feeds", _FEED_COLUMNS)
        _add_missing_columns(conn, "articles", _ARTICLE_COLUMNS)
        cur = conn.cursor()
        cur.execute(
            "UPDATE articles SET updated_at = COALESCE(added_at, datetime('now')) "
            "WHERE updated_at IS NULL"
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized:", "PostgreSQL" if IS_POSTGRES else DB_PATH)
