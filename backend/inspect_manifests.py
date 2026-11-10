import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for b in ["batch3", "batch4", "batch5"]:
    man = json.load(
        open(rf"C:\Users\pc\Documents\OpenCood\Content\{b}\manifest.json", encoding="utf-8")
    )
    print("===", b, len(man), "entries")
    for r in man:
        print(f"  id={r['id']:>2} {r['lang']:<2} {r['title'][:90]}")
