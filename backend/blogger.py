import os
import json
import requests
import urllib.parse

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "blogger_config.json")
SCOPES = ["https://www.googleapis.com/auth/blogger"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_auth_url(client_id, redirect_uri):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

def exchange_code(client_id, client_secret, code, redirect_uri):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    })
    return resp.json()

def refresh_access_token(client_id, client_secret, refresh_token):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    return resp.json()

def get_valid_token():
    cfg = load_config()
    access_token = cfg.get("access_token")
    refresh = cfg.get("refresh_token")
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    if not access_token:
        return None
    if not refresh or not client_id or not client_secret:
        return access_token
    # Try refreshing proactively to avoid failures
    tok = refresh_access_token(client_id, client_secret, refresh)
    if "access_token" in tok:
        cfg["access_token"] = tok["access_token"]
        save_config(cfg)
        return tok["access_token"]
    return access_token

def publish_post(title, content, labels=None):
    cfg = load_config()
    blog_id = cfg.get("blog_id")
    access_token = get_valid_token()
    if not blog_id or not access_token:
        doc = ("Blogger not fully configured. "
               "Add your Client ID, Client Secret, Blog ID, then click 'Connect to Blogger'.")
        return {"success": False, "error": doc}

    body = {
        "kind": "blogger#post",
        "title": title,
        "content": content
    }
    if labels:
        body["labels"] = labels

    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(url, json=body, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return {"success": True, "url": data.get("url"), "id": data.get("id")}
    return {"success": False, "error": f"Blogger API error: {resp.status_code} - {resp.text}"}
