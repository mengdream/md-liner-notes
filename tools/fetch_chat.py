#!/usr/bin/env python3
"""Fetch a ChatGPT share link and save the conversation as private/<slug>.chat.md.

usage: fetch_chat.py <slug> [url]      re-fetch all urls in private/<slug>.chat-url.txt (one per line);
                                       a url given on the command line is appended to that list first.
An album can have several conversations (and one conversation can cover several albums).
Exit code 0 = unchanged, 10 = new or changed (prints the new turns).
Everything goes to private/ (git-ignored): raw chats are never published.
"""
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "private"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"


def fetch(url):
    return subprocess.run(["curl", "-sL", "-A", UA, url], capture_output=True, text=True, check=True).stdout


def decode(html):
    """Share pages embed a turbo-stream (flat array with index references) in streamController.enqueue calls."""
    s = "".join(json.loads(c) for c in re.findall(r'streamController\.enqueue\((".*?")\);', html, re.S))
    arr = next(json.loads(l) for l in s.split("\n") if l.strip().startswith("["))
    memo = {}

    def dec(i):
        if not isinstance(i, int) or i < 0:
            return None if isinstance(i, int) else i
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, dict):
            o = memo[i] = {}
            for k, val in v.items():
                o[arr[int(k[1:])] if k.startswith("_") else k] = dec(val)
            return o
        if isinstance(v, list):
            o = memo[i] = []
            o.extend(dec(x) for x in v)
            return o
        return v

    root = dec(0)
    seen = set()

    def find(o):
        if id(o) in seen:
            return None
        seen.add(id(o))
        if isinstance(o, dict):
            if isinstance(o.get("mapping"), dict):
                return o
            vals = o.values()
        elif isinstance(o, list):
            vals = o
        else:
            return None
        for v in vals:
            r = find(v)
            if r:
                return r

    return find(root)


def to_markdown(d, url):
    m, node, seq = d["mapping"], d.get("current_node"), []
    while node:
        seq.append(m[node])
        node = m[node].get("parent")
    out = [f"# {d.get('title')}", "", f"来源：{url}", ""]
    for n in reversed(seq):
        msg = n.get("message")
        if not msg or msg["author"]["role"] not in ("user", "assistant"):
            continue
        if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        c = msg.get("content") or {}
        txt = "\n".join(p for p in (c.get("parts") or []) if isinstance(p, str)).strip()
        if c.get("content_type") not in ("text", "multimodal_text") or not txt:
            continue
        txt = re.sub(r".*?", "", txt)          # strip citation markers
        out += ["## 用户" if msg["author"]["role"] == "user" else "## GPT", "", txt, ""]
    return "\n".join(out)


def main():
    slug = sys.argv[1]
    PRIV.mkdir(exist_ok=True)
    url_file = PRIV / f"{slug}.chat-url.txt"
    urls = url_file.read_text().split() if url_file.exists() else []
    if len(sys.argv) > 2 and sys.argv[2] not in urls:
        urls.append(sys.argv[2])
    url_file.write_text("\n".join(urls) + "\n")
    sys.setrecursionlimit(200000)
    threading.stack_size(512 * 1024 * 1024)
    mds = []
    for url in urls:
        result = {}
        t = threading.Thread(target=lambda: result.update(d=decode(fetch(url))))
        t.start()
        t.join()
        mds.append(to_markdown(result["d"], url))
    md = "\n\n---\n\n".join(mds)
    sync = PRIV / "sync.json"
    state = json.loads(sync.read_text()) if sync.exists() else {}
    from datetime import datetime
    state[slug] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sync.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    out = PRIV / f"{slug}.chat.md"
    old = out.read_text() if out.exists() else ""
    if md == old:
        print(f"{slug}: unchanged")
        return 0
    out.write_text(md)
    if old and md.startswith(old.rstrip()):
        print(f"{slug}: UPDATED, new turns:\n" + md[len(old.rstrip()):])
    else:
        print(f"{slug}: {'NEW' if not old else 'CHANGED (rewritten)'} -> {out}")
    return 10


if __name__ == "__main__":
    sys.exit(main())
