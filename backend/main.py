from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
import uvicorn
import os
from database import init_db, get_db
from pydantic import BaseModel
from typing import List, Optional
import feedparser
import requests
from html.parser import HTMLParser
import urllib.parse
import linkedin
import blogger
import fulltext

init_db()

app = FastAPI(title="EduFeed API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(linkedin.router)

class FeedCreate(BaseModel):
    url: str
    title: Optional[str] = None
    max_entries: Optional[int] = None
    scan_interval: Optional[int] = None
    folder_id: Optional[int] = None
    proxy: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    full_text: Optional[int] = None

class ArticleEdit(BaseModel):
    title: str
    description: str
    content: str

class ArticleStatusUpdate(BaseModel):
    status_type: str
    value: bool

class FolderCreate(BaseModel):
    name: str

class FolderUpdate(BaseModel):
    name: str

class FeedFolderMove(BaseModel):
    folder_id: Optional[int] = None

class FeedReorder(BaseModel):
    feed_ids: List[int]

class FeedRename(BaseModel):
    title: str

class FeedUpdate(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    max_entries: Optional[int] = None
    scan_interval: Optional[int] = None
    folder_id: Optional[int] = None
    proxy: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    full_text: Optional[int] = None

@app.get("/")
def read_root():
    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "EduFeed Backend is running."}

# ── Feeds ────────────────────────────────────────────────────────────────────

def resolve_max_entries(feed, default=20):
    """Read the feed's 'Maximum entries to save' setting (falls back to default)."""
    try:
        val = feed["max_entries"]
    except (IndexError, KeyError):
        val = None
    if val is None:
        return default
    try:
        val = int(val)
    except (TypeError, ValueError):
        return default
    return val if val > 0 else default

@app.post("/feeds/preview")
def preview_feed(url: str):
    parsed = feedparser.parse(url)
    if not parsed.entries:
        raise HTTPException(status_code=400, detail="Invalid feed or no entries found.")
    title = parsed.feed.get('title', url)
    return {"url": url, "title": title, "entry_count": len(parsed.entries)}

@app.post("/feeds/")
def add_feed(feed: FeedCreate):
    parsed = feedparser.parse(feed.url)
    if not parsed.entries:
        raise HTTPException(status_code=400, detail="Invalid feed or no entries found.")
    title = feed.title or parsed.feed.get('title', feed.url)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO feeds (title, url, max_entries, scan_interval, folder_id, proxy, username, password, full_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title,
                feed.url,
                feed.max_entries if feed.max_entries is not None else 20,
                feed.scan_interval if feed.scan_interval is not None else 0,
                feed.folder_id if feed.folder_id is not None else None,
                feed.proxy or "",
                feed.username or "",
                feed.password or "",
                feed.full_text if feed.full_text is not None else 1,
            ),
        )
        cursor.execute("SELECT id FROM feeds WHERE url = ?", (feed.url,))
        feed_id = cursor.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.close()
        print(f"Add feed error: {e}")
        raise HTTPException(status_code=400, detail=f"Feed already exists or database error: {e}")
    max_vals = feed.max_entries if (feed.max_entries is not None and feed.max_entries > 0) else 20
    entries_found = len(parsed.entries)
    enable_fulltext = True if feed.full_text is None else bool(feed.full_text)
    for entry in parsed.entries[:max_vals]:
        link = (entry.get("link") or "").strip()
        if link:
            cursor.execute("DELETE FROM articles WHERE link = ? AND feed_id IS NULL", (link,))
    conn.commit()
    imported, updated = fulltext.process_feed_entries(cursor, feed_id, parsed.entries, max_vals, enable_fulltext)
    conn.commit()
    conn.close()
    print(f"Add feed result: {imported}/{max_vals} imported (feed had {entries_found} entries)")
    return {"status": "success", "id": feed_id, "title": title, "imported": imported, "updated": updated, "entries_found": entries_found}

@app.get("/feeds/")
def list_feeds():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*,
            (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0 AND a.is_done = 0) AS unread_count
        FROM feeds f
        ORDER BY f.sort_order ASC, f.title ASC
    """)
    feeds = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return feeds

@app.delete("/feeds/{feed_id}")
def delete_feed(feed_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM articles WHERE feed_id = ? AND is_done = 0", (feed_id,))
        cursor.execute("UPDATE articles SET feed_id = NULL WHERE feed_id = ? AND is_done = 1", (feed_id,))
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    return {"status": "success"}

@app.put("/feeds/{feed_id}/folder")
def move_feed_to_folder(feed_id: int, move: FeedFolderMove):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE feeds SET folder_id = ? WHERE id = ?", (move.folder_id, feed_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/feeds/reorder")
def reorder_feeds(reorder: FeedReorder):
    conn = get_db()
    cursor = conn.cursor()
    for i, fid in enumerate(reorder.feed_ids):
        cursor.execute("UPDATE feeds SET sort_order = ? WHERE id = ?", (i, fid))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/feeds/{feed_id}/rename")
def rename_feed(feed_id: int, rename: FeedRename):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE feeds SET title = ? WHERE id = ?", (rename.title.strip(), feed_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/feeds/{feed_id}/mark-read")
def mark_feed_read(feed_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE articles SET is_read = 1 WHERE feed_id = ? AND is_read = 0", (feed_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "success", "marked": affected}

@app.post("/feeds/{feed_id}/sync")
def sync_single_feed(feed_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, title, full_text, max_entries FROM feeds WHERE id = ?", (feed_id,))
    feed = cursor.fetchone()
    if not feed:
        conn.close()
        raise HTTPException(status_code=404, detail="Feed not found")
    new_articles = 0
    updated_articles = 0
    entries_processed = 0
    try:
        parsed = feedparser.parse(feed["url"])
        enable_fulltext = True if feed["full_text"] is None else bool(feed["full_text"])
        max_vals = resolve_max_entries(feed)
        entries_available = len(parsed.entries)
        new_articles, updated_articles = fulltext.process_feed_entries(cursor, feed_id, parsed.entries, max_vals, enable_fulltext)
        entries_processed = min(entries_available, max_vals)
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    return {"status": "success", "new_articles_count": new_articles, "updated_articles_count": updated_articles, "entries_processed": entries_processed, "entries_available": entries_available}

@app.put("/feeds/{feed_id}")
def update_feed(feed_id: int, upd: FeedUpdate):
    conn = get_db()
    cursor = conn.cursor()
    fields = []
    vals = []
    for key, col in [("url","url"),("title","title"),("max_entries","max_entries"),("scan_interval","scan_interval"),("folder_id","folder_id"),("proxy","proxy"),("username","username"),("password","password"),("full_text","full_text")]:
        val = getattr(upd, key, None)
        if val is not None:
            fields.append(f"{col} = ?")
            vals.append(val)
    if fields:
        vals.append(feed_id)
        cursor.execute(f"UPDATE feeds SET {', '.join(fields)} WHERE id = ?", vals)
        conn.commit()
    conn.close()
    return {"status": "success"}

class FeedLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.feeds = []
    def handle_starttag(self, tag, attrs):
        if tag == "link":
            attrs = dict(attrs)
            if attrs.get("type") in ("application/rss+xml", "application/atom+xml"):
                href = attrs.get("href")
                title = attrs.get("title", "")
                if href:
                    self.feeds.append({"url": href, "title": title})

@app.get("/discover-feeds")
def discover_feeds(url: str):
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        if "application/rss+xml" in resp.headers.get("Content-Type","") or "application/atom+xml" in resp.headers.get("Content-Type",""):
            parsed = feedparser.parse(resp.content)
            return [{"url": url, "title": parsed.feed.get("title", url)}]
        parser = FeedLinkParser()
        parser.feed(resp.text)
        base = resp.url.rstrip("/")
        results = []
        for f in parser.feeds:
            href = urllib.parse.urljoin(base, f["url"])
            title = f["title"] or href
            results.append({"url": href, "title": title})
        if not results:
            for guess in ["/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/feeds", "/feed/"]:
                test_url = urllib.parse.urljoin(base, guess)
                p = feedparser.parse(test_url)
                if p.entries:
                    results.append({"url": test_url, "title": p.feed.get("title", test_url)})
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ── Folders ──────────────────────────────────────────────────────────────────

@app.get("/folders/")
def list_folders():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM folders ORDER BY name ASC")
    folders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return folders

@app.post("/folders/")
def create_folder(folder: FolderCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO folders (name) VALUES (?)", (folder.name,))
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder.name,))
        fid = cursor.fetchone()[0]
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Folder name must be unique.")
    conn.close()
    return {"id": fid, "name": folder.name}

@app.put("/folders/{folder_id}")
def update_folder(folder_id: int, folder: FolderUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE folders SET name = ? WHERE id = ?", (folder.name, folder_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Folder not found")
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/folders/{folder_id}")
def delete_folder(folder_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE feeds SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
    cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ── Sync ─────────────────────────────────────────────────────────────────────

@app.post("/sync/")
def sync_feeds():
    print("Starting sync...")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, url, title, full_text, max_entries FROM feeds")
        feeds = cursor.fetchall()
        new_articles = 0
        updated_articles = 0
        entries_processed = 0
        for feed in feeds:
            try:
                safe_title = feed['title'].encode('ascii', 'ignore').decode()
                print(f"Syncing feed: {safe_title}")
                parsed = feedparser.parse(feed["url"])
                if hasattr(parsed, 'bozo_exception') and parsed.bozo_exception:
                    print(f"Warning: {str(parsed.bozo_exception).encode('ascii', 'ignore').decode()}")
                enable_fulltext = True if feed["full_text"] is None else bool(feed["full_text"])
                max_vals = resolve_max_entries(feed)
                n, u = fulltext.process_feed_entries(cursor, feed["id"], parsed.entries, max_vals, enable_fulltext)
                new_articles += n
                updated_articles += u
                entries_processed += min(len(parsed.entries), max_vals)
                conn.commit()
            except Exception as e:
                print(f"Error syncing feed: {str(e).encode('ascii', 'ignore').decode()}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue
        return {"status": "success", "new_articles_count": new_articles, "updated_articles_count": updated_articles, "entries_processed": entries_processed}
    except Exception as e:
        print(f"Critical sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        conn.close()

# ── Articles ─────────────────────────────────────────────────────────────────

@app.get("/articles/")
def list_articles(feed_id: Optional[str] = None, folder_id: Optional[int] = None, status_filter: Optional[str] = "undone", search: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM articles WHERE 1=1"
    params = []

    if feed_id == "starred":
        query += " AND is_starred = 1"
    elif feed_id == "linkedin":
        query += " AND feed_id IS NULL AND link LIKE '%linkedin.com%'"
    elif feed_id == "manual":
        query += " AND feed_id IS NULL AND NOT (link LIKE '%linkedin.com%')"
    elif feed_id and feed_id != "all":
        query += " AND feed_id = ?"
        params.append(int(feed_id))

    if folder_id:
        query += " AND feed_id IN (SELECT id FROM feeds WHERE folder_id = ?)"
        params.append(folder_id)

    if status_filter == "starred":
        query += " AND is_starred = 1"
    elif status_filter == "unread":
        query += " AND is_read = 0 AND is_done = 0"
    elif status_filter == "read":
        query += " AND is_read = 1 AND is_done = 0"
    elif status_filter == "posted":
        query += " AND is_posted = 1"
    elif status_filter == "whatsapped":
        query += " AND is_whatsapped = 1"
    elif status_filter == "done":
        query += " AND is_done = 1"
    elif status_filter == "undone":
        query += " AND is_done = 0"
    elif status_filter == "all":
        pass

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR edited_title LIKE ? OR edited_content LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term, search_term])

    query += " ORDER BY published_date DESC, id DESC"

    cursor.execute(query, params)
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

@app.post("/articles/{article_id}/star")
def star_article(article_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_starred FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Article not found")
    new_val = 0 if row["is_starred"] else 1
    cursor.execute("UPDATE articles SET is_starred = ? WHERE id = ?", (new_val, article_id))
    conn.commit()
    conn.close()
    return {"is_starred": bool(new_val)}

@app.post("/articles/{article_id}/status")
def update_status(article_id: int, status_update: ArticleStatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    col_map = {
        "read": "is_read", "unread": "is_read",
        "posted": "is_posted", "whatsapped": "is_whatsapped", "done": "is_done"
    }
    if status_update.status_type not in col_map:
        raise HTTPException(status_code=400, detail="Invalid status type")
    col = col_map[status_update.status_type]
    val = 1 if status_update.value else 0
    if status_update.status_type == "unread":
        val = 0
    cursor.execute(f"UPDATE articles SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (val, article_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/articles/{article_id}")
def edit_article(article_id: int, edit: ArticleEdit):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE articles
        SET edited_title = ?, edited_description = ?, edited_content = ?, is_done = 1, is_read = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (edit.title, edit.description, edit.content, article_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/articles/{article_id}/fulltext")
def fetch_article_fulltext(article_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, link, description FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Article not found")
    link = (row["link"] or "").strip()
    if not link or link.startswith("urn:"):
        conn.close()
        raise HTTPException(status_code=400, detail="Article has no source URL to fetch")
    extracted = fulltext.extract_full_text(link)
    if not extracted:
        cursor.execute("UPDATE articles SET fulltext_attempted = 1 WHERE id = ?", (article_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=502, detail="Could not extract full text from the source page.")
    old_desc = row["description"] or ""
    cursor.execute(
        "UPDATE articles SET description = ?, fulltext_attempted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (extracted, article_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "upgraded": extracted != old_desc, "length": len(extracted), "description": extracted}

@app.delete("/articles/{article_id}")
def delete_article(article_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ── Stats ────────────────────────────────────────────────────────────────────

@app.get("/stats/")
def get_stats(period: Optional[str] = "weekly"):
    conn = get_db()
    cursor = conn.cursor()
    import datetime

    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 1")
    total_read = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0 AND is_done = 0 AND is_posted = 0 AND is_whatsapped = 0")
    zero_engagement = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM feeds")
    total_feeds = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM feeds WHERE id IN (SELECT DISTINCT feed_id FROM articles WHERE feed_id IS NOT NULL)")
    active_feeds = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 0")
    undone_posts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1")
    done_posts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_posted = 1")
    posted = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped = 1")
    whatsapped = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_starred = 1")
    starred_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0 AND is_done = 0")
    total_unread = cursor.fetchone()[0]

    completion_rate = round((done_posts / total_articles * 100), 1) if total_articles > 0 else 0
    read_rate = round((total_read / total_articles * 100), 1) if total_articles > 0 else 0
    posted_rate = round((posted / total_articles * 100), 1) if total_articles > 0 else 0
    whatsapped_rate = round((whatsapped / total_articles * 100), 1) if total_articles > 0 else 0
    avg_per_feed = round((total_articles / active_feeds), 1) if active_feeds > 0 else 0

    cursor.execute("SELECT COUNT(*) FROM feeds WHERE added_at >= datetime('now', '-7 days')")
    feeds_this_week = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE added_at >= datetime('now', '-1 day')")
    new_articles_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE updated_at >= datetime('now', '-1 day')")
    updated_recently = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_posted = 1 AND updated_at >= datetime('now', '-1 day')")
    posted_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped = 1 AND updated_at >= datetime('now', '-1 day')")
    whatsapped_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1 AND updated_at >= datetime('now', '-7 days')")
    done_this_week = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1 AND updated_at >= datetime('now', '-14 days') AND updated_at < datetime('now', '-7 days')")
    done_last_week = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE added_at >= datetime('now', '-7 days')")
    new_this_week = cursor.fetchone()[0]
    social_share = posted + whatsapped
    social_share_rate = round((social_share / total_articles * 100), 1) if total_articles > 0 else 0
    cursor.execute("SELECT COUNT(*) FROM articles WHERE feed_id IS NULL AND link LIKE '%linkedin.com%'")
    linkedin_imports = cursor.fetchone()[0]

    cursor.execute("""
        SELECT f.id, f.title, f.url,
               COUNT(a.id) AS total,
               SUM(CASE WHEN a.is_done = 1 THEN 1 ELSE 0 END) AS done,
               SUM(CASE WHEN a.is_posted = 1 THEN 1 ELSE 0 END) AS posted,
               SUM(CASE WHEN a.is_whatsapped = 1 THEN 1 ELSE 0 END) AS whatsapped
        FROM feeds f LEFT JOIN articles a ON a.feed_id = f.id
        GROUP BY f.id ORDER BY total DESC
    """)
    feed_stats = [dict(r) for r in cursor.fetchall()]

    period_map = {"weekly": (7, "days", "%a"), "monthly": (30, "days", "%d %b"), "yearly": (12, "months", "%b"), "all": (0, "all", "%Y-%m")}
    if period not in period_map: period = "weekly"
    num, unit, fmt = period_map[period]
    labels, done_counts, undone_counts, whatsapped_counts, posted_counts = [], [], [], [], []

    if period == "all":
        cursor.execute("SELECT MIN(date(added_at)) FROM articles")
        first = cursor.fetchone()[0]
        if not first: first = datetime.datetime.now().strftime("%Y-%m-%d")
        start = datetime.datetime.strptime(first[:7] + "-01", "%Y-%m-%d")
        now = datetime.datetime.now()
        c = datetime.datetime(start.year, start.month, 1)
        while c <= now:
            ms = c.strftime("%Y-%m-%d")
            me = c.replace(year=c.year + (1 if c.month == 12 else 0), month=(1 if c.month == 12 else c.month + 1)).strftime("%Y-%m-%d")
            labels.append(c.strftime("%b %Y"))
            for col, target in [("is_done", done_counts), ("is_done=0", undone_counts), ("is_whatsapped", whatsapped_counts), ("is_posted", posted_counts)]:
                pieces = col.split("=")
                sql_col = pieces[0]
                sql_val = pieces[1] if len(pieces) > 1 else "1"
                cursor.execute(f"SELECT COUNT(*) FROM articles WHERE {sql_col} = ? AND added_at >= ? AND added_at < ?", (sql_val, ms, me))
                target.append(cursor.fetchone()[0])
            c = c.replace(year=c.year + (1 if c.month == 12 else 0), month=(1 if c.month == 12 else c.month + 1))
    else:
        now = datetime.datetime.now()
        for i in range(num - 1, -1, -1):
            day = now - datetime.timedelta(days=i) if unit == "days" else now - datetime.timedelta(days=30 * i)
            ds = day.strftime("%Y-%m-%d")
            labels.append(day.strftime(fmt))
            cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1 AND date(added_at) = ?", (ds,)); done_counts.append(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 0 AND date(added_at) = ?", (ds,)); undone_counts.append(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped = 1 AND date(added_at) = ?", (ds,)); whatsapped_counts.append(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM articles WHERE is_posted = 1 AND date(added_at) = ?", (ds,)); posted_counts.append(cursor.fetchone()[0])

    cursor.execute("SELECT title, is_done, is_posted, is_whatsapped FROM articles WHERE is_done = 1 OR is_posted = 1 OR is_whatsapped = 1 ORDER BY updated_at DESC LIMIT 10")
    recent = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {
        "total_feeds": total_feeds, "active_feeds": active_feeds, "feeds_this_week": feeds_this_week,
        "total_articles": total_articles, "total_read": total_read,
        "undone_posts": undone_posts, "done_posts": done_posts, "zero_engagement": zero_engagement,
        "new_articles_today": new_articles_today, "updated_recently": updated_recently,
        "completion_rate": completion_rate, "read_rate": read_rate, "posted_rate": posted_rate, "whatsapped_rate": whatsapped_rate,
        "avg_per_feed": avg_per_feed, "whatsapped": whatsapped, "posted": posted,
        "posted_today": posted_today, "whatsapped_today": whatsapped_today,
        "done_this_week": done_this_week, "done_last_week": done_last_week, "new_this_week": new_this_week,
        "social_share_rate": social_share_rate, "linkedin_imports": linkedin_imports,
        "starred_count": starred_count, "total_unread": total_unread,
        "feed_stats": feed_stats, "trend_data": {"labels": labels, "done": done_counts, "undone": undone_counts, "whatsapped": whatsapped_counts, "posted": posted_counts},
        "recent_activity": recent,
    }

# ── Blogger ──────────────────────────────────────────────────────────────────

class BloggerConfigIn(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    blog_id: str = ""
    access_token: str = ""
    refresh_token: str = ""

class BloggerStatusOut(BaseModel):
    blog_id: str; client_id: str; connected: bool; has_refresh_token: bool; has_secret: bool

@app.get("/blogger-config", response_model=BloggerStatusOut)
def get_blogger_config():
    cfg = blogger.load_config()
    return BloggerStatusOut(
        blog_id=cfg.get("blog_id", ""), client_id=cfg.get("client_id", ""),
        connected=bool(cfg.get("access_token")), has_refresh_token=bool(cfg.get("refresh_token")),
        has_secret=bool(cfg.get("client_secret"))
    )

@app.post("/blogger-config")
def set_blogger_config(cfg: BloggerConfigIn):
    data = blogger.load_config()
    if cfg.client_id: data["client_id"] = cfg.client_id.strip()
    if cfg.client_secret: data["client_secret"] = cfg.client_secret.strip()
    if cfg.blog_id: data["blog_id"] = cfg.blog_id.strip()
    if cfg.access_token: data["access_token"] = cfg.access_token.strip()
    if cfg.refresh_token: data["refresh_token"] = cfg.refresh_token.strip()
    blogger.save_config(data)
    return {"status": "saved"}

@app.get("/blogger/auth-url")
def get_blogger_auth_url(request: Request):
    cfg = blogger.load_config()
    cid = cfg.get("client_id")
    if not cid: raise HTTPException(status_code=400, detail="Save Client ID first")
    redirect_uri = str(request.base_url).rstrip("/") + "/blogger/callback"
    print(f"Blogger OAuth redirect_uri: {redirect_uri}")
    return {"auth_url": blogger.get_auth_url(cid, redirect_uri), "redirect_uri": redirect_uri}

@app.get("/blogger/callback")
def blogger_callback(request: Request, code: str = None, error: str = None):
    if error:
        return HTMLResponse(f"<html><body><h3>OAuth error: {error}</h3><script>window.close()</script></body></html>")
    if not code:
        return HTMLResponse("<html><body><h3>No authorization code received</h3><script>window.close()</script></body></html>")
    cfg = blogger.load_config()
    cid, cs = cfg.get("client_id"), cfg.get("client_secret")
    if not cid or not cs:
        return HTMLResponse("<html><body><h3>Client ID or Secret not saved</h3><script>window.close()</script></body></html>")
    redirect_uri = str(request.base_url).rstrip("/") + "/blogger/callback"
    print(f"Exchanging code with redirect_uri: {redirect_uri}")
    tok = blogger.exchange_code(cid, cs, code, redirect_uri)
    if "access_token" in tok:
        cfg["access_token"] = tok["access_token"]
        if "refresh_token" in tok: cfg["refresh_token"] = tok["refresh_token"]
        blogger.save_config(cfg)
        return HTMLResponse('<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh"><h2 style="color:green">Connected to Blogger!</h2><script>window.close()</script></body></html>')
    err_detail = tok.get("error_description", tok.get("error", "Failed"))
    print(f"Blogger token exchange failed: {tok}")
    return HTMLResponse(f"<html><body><h3>Error: {err_detail}</h3><script>window.close()</script></body></html>")

@app.post("/articles/{article_id}/publish-blogger")
def publish_article_blogger(article_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT a.title, a.description, a.edited_content, COALESCE(f.title, '') AS feed_title FROM articles a LEFT JOIN feeds f ON a.feed_id = f.id WHERE a.id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=404, detail="Article not found")
    title, description, edited_content, feed_title = row
    content = edited_content or description or ""
    labels = ["EduFeed"]
    if feed_title: labels.append(feed_title.replace(" ", "_"))
    result = blogger.publish_post(title, content, labels)
    if result["success"]:
        c = get_db()
        c.execute("UPDATE articles SET is_posted = 1 WHERE id = ?", (article_id,))
        c.commit()
        c.close()
    return result

# ── Static files ─────────────────────────────────────────────────────────────

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    reload_flag = os.environ.get("EDUFEED_RELOAD", "").strip().lower() in ("1", "true", "yes")
    host = os.environ.get("HOST") or "127.0.0.1"
    port = int(os.environ.get("PORT") or 8002)
    uvicorn.run("main:app", host=host, port=port, reload=reload_flag)
