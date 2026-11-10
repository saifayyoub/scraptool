import re
import requests
import trafilatura

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

_TRUNC_MARKERS = [
    "read more", "readmore", "continue reading", "keep reading", "full story",
    "lire la suite", "continue lendo", "weiterlesen",
    "اقرأ المزيد", "أكمل القراءة", "المزيد",
]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

_SHORT_THRESHOLD = 400


def strip_html(html):
    if not html:
        return ""
    html = _SCRIPT_RE.sub(" ", html)
    return _TAG_RE.sub(" ", html)


def visible_length(html):
    return len(strip_html(html).strip())


def has_truncation_marker(html):
    if not html:
        return False
    low = strip_html(html).lower()
    for marker in _TRUNC_MARKERS:
        if marker in low:
            return True
    if re.search(r"(?:\.{3,}|…)\s*$", low.strip()):
        return True
    return False


def needs_full_text(html, threshold=_SHORT_THRESHOLD):
    """True when the feed content looks like a summary/title instead of the article."""
    if not html:
        return True
    return visible_length(html) < threshold or has_truncation_marker(html)


def get_entry_content(entry):
    """Prefer the full content (content:encoded) over the truncated summary."""
    content = entry.get("content")
    if content:
        for c in content:
            val = c.get("value") if isinstance(c, dict) else None
            if val:
                return val
    for key in ("summary", "description"):
        val = entry.get(key)
        if val:
            return val
    return ""


def extract_full_text(url, timeout=20):
    """Fetch the article page and return the main article HTML (or None on failure)."""
    if not url or url.startswith("urn:"):
        return None
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,en;q=0.9,ar;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if any(t in ctype for t in ("image/", "application/pdf", "application/json", "audio/", "video/")):
            return None
        data = resp.content
    except Exception:
        return None
    if not data:
        return None
    try:
        out = trafilatura.extract(
            data,
            output_format="html",
            include_formatting=True,
            include_links=True,
            include_images=True,
            include_tables=True,
            favor_recall=True,
        )
    except Exception:
        return None
    if out:
        out = out.strip()
        if visible_length(out) >= 20:
            return out
    return None


def prepare_entry(entry, feed_id, enable_fulltext=True, skip_extract=False):
    """Build the stored fields for one feed entry, extracting full text when needed."""
    title = entry.get("title", "No Title")
    link = (entry.get("link") or "").strip()
    if not link:
        link = f"urn:edufeed:{feed_id}:{hash(title)}"
    published = entry.get("published", entry.get("updated", ""))
    raw = get_entry_content(entry)
    description = raw
    fulltext_attempted = 0
    if enable_fulltext and not skip_extract and needs_full_text(raw):
        extracted = extract_full_text(link)
        fulltext_attempted = 1
        if extracted:
            description = extracted
    return {
        "title": title,
        "link": link,
        "published": published,
        "description": description,
        "raw": raw,
        "fulltext_attempted": fulltext_attempted,
    }


def process_feed_entries(cursor, feed_id, entries, max_entries, enable_fulltext=True):
    """Insert or update articles for the given feed entries. Returns (new, updated)."""
    new_articles = 0
    updated_articles = 0
    for entry in reversed(entries[:max_entries]):
        raw_link = (entry.get("link") or "").strip()
        existing_attempted = False
        if raw_link:
            cursor.execute("SELECT fulltext_attempted FROM articles WHERE link = ?", (raw_link,))
            row = cursor.fetchone()
            existing_attempted = bool(row and row["fulltext_attempted"])
        info = prepare_entry(entry, feed_id, enable_fulltext=enable_fulltext, skip_extract=existing_attempted)
        try:
            cursor.execute("""
                INSERT INTO articles (feed_id, title, link, published_date, description, fulltext_attempted, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (feed_id, info["title"], info["link"], info["published"], info["description"], info["fulltext_attempted"]))
            new_articles += 1
        except Exception:
            cursor.execute(
                "SELECT title, description, published_date, fulltext_attempted FROM articles WHERE link = ?",
                (info["link"],),
            )
            existing = cursor.fetchone()
            if existing:
                old_title, old_desc, old_pub, old_attempted = existing["title"], existing["description"], existing["published_date"], existing["fulltext_attempted"]
                new_desc = info["description"]
                if old_attempted and not info["fulltext_attempted"] and needs_full_text(info["raw"]):
                    new_desc = old_desc
                if old_title != info["title"] or old_desc != new_desc or old_pub != info["published"]:
                    new_attempted = existing["fulltext_attempted"]
                    if info["fulltext_attempted"]:
                        new_attempted = 1
                    cursor.execute("""
                        UPDATE articles SET title = ?, published_date = ?, description = ?,
                            fulltext_attempted = ?, updated_at = CURRENT_TIMESTAMP, is_done = 0, is_read = 0
                        WHERE link = ?
                    """, (info["title"], info["published"], new_desc, new_attempted, info["link"]))
                    updated_articles += 1
    return new_articles, updated_articles
