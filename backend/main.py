from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from database import init_db, get_db
from pydantic import BaseModel
from typing import List, Optional
import feedparser
import linkedin
import facebook
import instagram

# Initialize database on startup
init_db()

app = FastAPI(title="EduFeed API", description="Local-first productivity RSS reader backend")

# Allow local frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(linkedin.router)
app.include_router(facebook.router)
app.include_router(instagram.router)


class FeedCreate(BaseModel):
    url: str

class ArticleEdit(BaseModel):
    title: str
    description: str
    content: str

class ArticleStatusUpdate(BaseModel):
    status_type: str
    value: bool

@app.get("/")
def read_root():
    return {"status": "EduFeed Backend is running. Ready to curate."}

@app.post("/feeds/")
def add_feed(feed: FeedCreate):
    parsed = feedparser.parse(feed.url)
    if not parsed.entries:
        raise HTTPException(status_code=400, detail="Invalid feed or no entries found.")
    title = parsed.feed.get('title', feed.url)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO feeds (title, url) VALUES (?, ?)", (title, feed.url))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail="Feed already exists or database error.")
    conn.close()
    return {"status": "success", "title": title}

@app.get("/feeds/")
def list_feeds():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feeds")
    feeds = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return feeds

@app.post("/sync/")
def sync_feeds():
    print("Starting sync...")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, url, title FROM feeds")
        feeds = cursor.fetchall()
        
        new_articles = 0
        for feed in feeds:
            try:
                # Use safe printing for Windows
                safe_title = feed['title'].encode('ascii', 'ignore').decode()
                print(f"Syncing feed: {safe_title}")
                parsed = feedparser.parse(feed["url"])
                if hasattr(parsed, 'bozo_exception') and parsed.bozo_exception:
                    print(f"Warning: Potential issue with feed: {str(parsed.bozo_exception).encode('ascii', 'ignore').decode()}")
                
                # Reverse entries to ensure newest articles get higher IDs
                for entry in reversed(parsed.entries):
                    title = entry.get("title", "No Title")
                    link = entry.get("link", "")
                    published = entry.get("published", "")
                    description = entry.get("summary", entry.get("description", ""))
                    
                    try:
                        cursor.execute("""
                            INSERT INTO articles (feed_id, title, link, published_date, description)
                            VALUES (?, ?, ?, ?, ?)
                        """, (feed["id"], title, link, published, description))
                        new_articles += 1
                    except Exception as e:
                        # Likely duplicate link
                        pass
                conn.commit()
            except Exception as e:
                print(f"Error syncing feed: {str(e).encode('ascii', 'ignore').decode()}")
                continue
                
        return {"status": "success", "new_articles_count": new_articles}
    except Exception as e:
        print(f"Critical sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        conn.close()

@app.get("/articles/")
def list_articles(feed_id: Optional[str] = None, status_filter: Optional[str] = "undone", search: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM articles WHERE 1=1"
    params = []
    
    if feed_id == "linkedin":
        query += " AND feed_id IS NULL AND link LIKE '%linkedin.com%'"
    elif feed_id == "facebook":
        query += " AND feed_id IS NULL AND (link LIKE '%facebook.com%' OR link LIKE '%fb.watch%' OR link LIKE '%fb.com%')"
    elif feed_id == "instagram":
        query += " AND feed_id IS NULL AND (link LIKE '%instagram.com%' OR link LIKE '%instagr.am%')"
    elif feed_id == "manual":
        query += " AND feed_id IS NULL AND NOT (link LIKE '%linkedin.com%' OR link LIKE '%facebook.com%' OR link LIKE '%fb.watch%' OR link LIKE '%fb.com%' OR link LIKE '%instagram.com%' OR link LIKE '%instagr.am%')"
    elif feed_id and feed_id != "all":
        query += " AND feed_id = ?"
        params.append(int(feed_id))
        
    if status_filter == "unread":
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
        
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR edited_title LIKE ? OR edited_content LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term, search_term])
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

@app.post("/articles/{article_id}/status")
def update_status(article_id: int, status_update: ArticleStatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    
    col_map = {
        "read": "is_read",
        "unread": "is_read",
        "posted": "is_posted",
        "whatsapped": "is_whatsapped",
        "done": "is_done"
    }
    
    if status_update.status_type not in col_map:
        raise HTTPException(status_code=400, detail="Invalid status type")
        
    col = col_map[status_update.status_type]
    val = 1 if status_update.value else 0
    if status_update.status_type == "unread":
        col = "is_read"
        val = 0
        
    cursor.execute(f"UPDATE articles SET {col} = ? WHERE id = ?", (val, article_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/articles/{article_id}")
def edit_article(article_id: int, edit: ArticleEdit):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE articles 
        SET edited_title = ?, edited_description = ?, edited_content = ?, is_done = 1, is_read = 1
        WHERE id = ?
    """, (edit.title, edit.description, edit.content, article_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/feeds/{feed_id}")
def delete_feed(feed_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Delete undone articles from this feed
        cursor.execute("DELETE FROM articles WHERE feed_id = ? AND is_done = 0", (feed_id,))
        # 2. Unlink done articles (so they remain as manual/archived)
        cursor.execute("UPDATE articles SET feed_id = NULL WHERE feed_id = ? AND is_done = 1", (feed_id,))
        # 3. Delete the feed itself
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    return {"status": "success"}

@app.get("/stats/")
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    # Total feeds
    cursor.execute("SELECT COUNT(*) FROM feeds")
    total_feeds = cursor.fetchone()[0]
    
    # Feeds added this week (last 7 days)
    cursor.execute("SELECT COUNT(*) FROM feeds WHERE added_at >= datetime('now', '-7 days')")
    feeds_this_week = cursor.fetchone()[0]
    
    # Undone articles
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 0")
    undone_posts = cursor.fetchone()[0]
    
    # New articles today (last 24 hours)
    cursor.execute("SELECT COUNT(*) FROM articles WHERE added_at >= datetime('now', '-1 day')")
    new_articles_today = cursor.fetchone()[0]
    
    # Done articles
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1")
    done_posts = cursor.fetchone()[0]
    
    # Completion rate
    total_articles = undone_posts + done_posts
    completion_rate = round((done_posts / total_articles * 100), 1) if total_articles > 0 else 0
    
    # Whatsapped articles
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped = 1")
    whatsapped = cursor.fetchone()[0]
    
    # Posted articles
    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_posted = 1")
    posted = cursor.fetchone()[0]
    
    # Social Imports Counts
    cursor.execute("SELECT COUNT(*) FROM articles WHERE feed_id IS NULL AND link LIKE '%linkedin.com%'")
    linkedin_imports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles WHERE feed_id IS NULL AND (link LIKE '%facebook.com%' OR link LIKE '%fb.watch%' OR link LIKE '%fb.com%')")
    facebook_imports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles WHERE feed_id IS NULL AND (link LIKE '%instagram.com%' OR link LIKE '%instagr.am%')")
    instagram_imports = cursor.fetchone()[0]

    # Real Weekly Activity (Last 7 days based on added_at)
    import datetime
    labels = []
    done_counts = []
    undone_counts = []
    whatsapped_counts = []
    posted_counts = []
    
    for i in range(6, -1, -1):
        date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        labels.append((datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%a'))
        
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 1 AND date(added_at) = ?", (date,))
        done_counts.append(cursor.fetchone()[0])
        
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_done = 0 AND date(added_at) = ?", (date,))
        undone_counts.append(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_whatsapped = 1 AND date(added_at) = ?", (date,))
        whatsapped_counts.append(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_posted = 1 AND date(added_at) = ?", (date,))
        posted_counts.append(cursor.fetchone()[0])
    
    weekly_data = {
        "labels": labels,
        "done": done_counts,
        "undone": undone_counts,
        "whatsapped": whatsapped_counts,
        "posted": posted_counts
    }
    
    # Recent activity (Last 5 articles with activity)
    cursor.execute("""
        SELECT title, is_done, is_posted, is_whatsapped 
        FROM articles 
        WHERE is_done = 1 OR is_posted = 1 OR is_whatsapped = 1
        ORDER BY id DESC LIMIT 5
    """)
    recent = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {
        "total_feeds": total_feeds,
        "feeds_this_week": feeds_this_week,
        "undone_posts": undone_posts,
        "new_articles_today": new_articles_today,
        "done_posts": done_posts,
        "completion_rate": completion_rate,
        "whatsapped": whatsapped,
        "posted": posted,
        "linkedin_imports": linkedin_imports,
        "facebook_imports": facebook_imports,
        "instagram_imports": instagram_imports,
        "weekly_data": weekly_data,
        "recent_activity": recent
    }

@app.delete("/articles/{article_id}")
def delete_article(article_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Serve static files from the frontend directory
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
