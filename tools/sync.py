#!/usr/bin/env python3
"""Re-fetch every album's GPT chat; report which changed, then refresh the catalog.

Changed chats still need their notes re-distilled into albums/<slug>.json (done by Claude via the md-cover skill),
then build_site.py + git push.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
changed = []
for f in sorted((ROOT / "private").glob("*.chat-url.txt")):
    slug = f.name.removesuffix(".chat-url.txt")
    r = subprocess.run([PY, ROOT / "tools/fetch_chat.py", slug], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode == 10:
        changed.append(slug)
subprocess.run([PY, ROOT / "tools/catalog.py"])
print("CHANGED:", " ".join(changed) if changed else "(none)")
