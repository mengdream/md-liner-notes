#!/usr/bin/env python3
"""Re-fetch GPT chats; report which changed, then refresh the catalog.

usage: sync.py                 all albums
       sync.py 准备中 richter   only albums matching any keyword (slug, title, title_zh, artist, artist_zh,
                               design file name; case-insensitive substring)
Changed chats still need their notes re-distilled into albums/<slug>.json (done by Claude via the md-cover skill),
then build_site.py + git push.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def haystack(slug):
    f = ROOT / "albums" / f"{slug}.json"
    a = json.loads(f.read_text()) if f.exists() else {}
    fields = [slug] + [a.get(k, "") for k in ("title", "title_zh", "artist", "artist_zh")] + a.get("design_files", [])
    return " ".join(fields).lower()


def main():
    keys = [k.lower() for k in sys.argv[1:]]
    slugs = [f.name.removesuffix(".chat-url.txt") for f in sorted((ROOT / "private").glob("*.chat-url.txt"))]
    if keys:
        slugs = [s for s in slugs if any(k in haystack(s) for k in keys)]
        if not slugs:
            print(f"no album matches {' '.join(sys.argv[1:])}")
            return 1
    changed = []
    for slug in slugs:
        r = subprocess.run([PY, ROOT / "tools/fetch_chat.py", slug], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode == 10:
            changed.append(slug)
    subprocess.run([PY, ROOT / "tools/catalog.py"])
    print("CHANGED:", " ".join(changed) if changed else "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
