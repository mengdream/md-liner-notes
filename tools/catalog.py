#!/usr/bin/env python3
"""Write the MD folder catalog (MD目录.md): every design file, plus liner-notes page and GPT chat per album.

Lives in the private iCloud folder, so it may contain the ChatGPT share links (never published).
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Docs/MD"
SITE = "https://mengdream.github.io/md-liner-notes"
DESIGN_EXT = {".ai", ".af", ".pdf", ".psd"}
SKIP = {"MD350中文使用说明书.pdf"}


def main():
    sync = ROOT / "private/sync.json"
    sync = json.loads(sync.read_text()) if sync.exists() else {}
    albums = [json.loads(f.read_text()) for f in sorted((ROOT / "albums").glob("*.json"))]
    by_file = {f: a for a in albums for f in a.get("design_files", [])}

    rows = []
    for a in sorted(albums, key=lambda a: a.get("recorded", ""), reverse=True):
        url_f = ROOT / "private" / f"{a['slug']}.chat-url.txt"
        urls = url_f.read_text().split() if url_f.exists() else []
        chat = " ".join(f"[对话{i + 1 if len(urls) > 1 else ''}]({u})" for i, u in enumerate(urls))
        files = "<br>".join(a.get("design_files", []))
        name = f"{a['title_zh']} {a['title']}" if a.get("title_zh") else a["title"]
        rows.append(f"| {name} | {a.get('artist_zh') or a['artist']} | {a.get('recorded','')} | {files} "
                    f"| [网页]({SITE}/albums/{a['slug']}/) | {chat} | {sync.get(a['slug'], '')} |")

    files = sorted((p for p in MD_DIR.iterdir() if p.suffix.lower() in DESIGN_EXT and p.name not in SKIP),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    frows = []
    for p in files:
        a = by_file.get(p.name)
        web = f"[网页]({SITE}/albums/{a['slug']}/)" if a else ""
        frows.append(f"| {p.stem} | {p.suffix[1:]} | {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d} | {web} |")

    out = f"""# MD 目录

> 由 `~/Sites/md-liner-notes/tools/catalog.py` 自动生成，请不要手改（改了会被覆盖）。更新于 {datetime.now():%Y-%m-%d %H:%M}。
> 想要同步 GPT 对话时，对 Claude 说“同步 MD 对话”：会重新抓每条对话链接，有新内容就更新对应的网页。
> 网页目录：{SITE}/

## 有曲目介绍网页的专辑（{len(albums)}）

| 专辑 | 艺人 | 录制 | 设计文件 | 网页 | GPT 对话 | 对话最后同步 |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

## 全部设计文件（{len(files)}）

| 文件 | 格式 | 修改日期 | 网页 |
|---|---|---|---|
{chr(10).join(frows)}
"""
    (MD_DIR / "MD目录.md").write_text(out)
    print(f"catalog: {len(albums)} albums, {len(files)} design files -> {MD_DIR / 'MD目录.md'}")


if __name__ == "__main__":
    main()
