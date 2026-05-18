from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import re
from database import get_db

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

class LinkedInImport(BaseModel):
    url: str

def extract_meta_content(html: str, property_name: str) -> str:
    # Attempt to find <meta property="og:title" content="...">
    pattern = f'<meta[^>]*property=[\'"]{property_name}[\'"][^>]*content=[\'"]([^\'"]*)[\'"]'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try name= instead of property=
    pattern2 = f'<meta[^>]*name=[\'"]{property_name}[\'"][^>]*content=[\'"]([^\'"]*)[\'"]'
    match2 = re.search(pattern2, html, re.IGNORECASE)
    if match2:
        return match2.group(1)
        
    return ""

@router.post("/import")
def import_linkedin_post(req: LinkedInImport):
    if not req.url.startswith("https://www.linkedin.com/"):
        raise HTTPException(status_code=400, detail="Not a valid LinkedIn URL")

    # Basic unauthenticated request
    # Note: LinkedIn heavily restricts unauthenticated scraping.
    # We will try to fetch og tags.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        response = requests.get(req.url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        # If it fails, we will still insert an empty stub for the user to edit manually,
        # since LinkedIn might block us.
        title = "Imported LinkedIn Post (Content Blocked)"
        description = "Could not automatically fetch content. Please edit manually."
    else:
        html = response.text
        title = extract_meta_content(html, "og:title")
        description = extract_meta_content(html, "og:description")
        image_url = extract_meta_content(html, "og:image")
        
        # Fallbacks
        if not title:
            # Try to grab <title> tag
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1) if title_match else "Unknown LinkedIn Post"
            
        if not description:
            description = "No description available. You can add your content here."
            
        if image_url:
            description = f'<p><img src="{image_url}" alt="LinkedIn Image" style="max-width: 100%; height: auto;"/></p><p>{description}</p>'

    # Clean up standard LinkedIn title suffixes if present
    if " | LinkedIn" in title:
        title = title.replace(" | LinkedIn", "")

    # Insert into database (feed_id = NULL for manual imports)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (title, link, description, is_read, is_done)
            VALUES (?, ?, ?, ?, ?)
        """, (title, req.url, description, 0, 0))
        conn.commit()
    except Exception as e:
        conn.close()
        # Might fail if link already exists
        raise HTTPException(status_code=400, detail="Post already imported or database error.")
        
    conn.close()
    return {"status": "success", "title": title}
