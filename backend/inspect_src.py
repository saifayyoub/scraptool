import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for src in [
    r"C:\Users\pc\Downloads\articles_2026-08-11-22-57.json",
    r"C:\Users\pc\Downloads\articles_2026-08-11-23-13.json",
    r"C:\Users\pc\Downloads\articles_2026-08-11-23-30.json",
]:
    d = json.load(open(src, encoding="utf-8"))
    arts = d.get("articles", [])
    print("===", src)
    print("type of articles:", type(arts))
    print("keys of dict:", list(arts.keys())[:5] if isinstance(arts, dict) else "")
    if isinstance(arts, dict):
        items = []
        for k, v in arts.items():
            if isinstance(v, dict):
                items.append(v)
            else:
                items.append({"id": k, "title": str(v)})
        arts = items
    for a in arts:
        print(" id:", a.get("id"), "| lang:", a.get("lang"), "| title:", str(a.get("title"))[:80])
