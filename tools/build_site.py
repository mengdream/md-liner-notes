#!/usr/bin/env python3
"""Render albums/*.json and listening/*.json into docs/ (GitHub Pages).

docs/index.html                      album index + listening sessions
docs/albums/<slug>/index.html        liner notes (tracks #t1.., essays)
docs/listening/<slug>/index.html     listening session timeline
"""
import html
import json
import shutil
import urllib.request
import urllib.parse
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALBUMS = ROOT / "albums"
LISTENING = ROOT / "listening"
DOCS = ROOT / "docs"

CSS = """
:root{--bg:#f4f1ea;--fg:#1d1b18;--mute:#77716a;--line:#d9d3c8;--acc:#9a5b2e;--card:#fbf9f4}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--fg:#ece7de;--mute:#9a938a;--line:#34302b;--acc:#d49a67;--card:#1e1c19}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.75 -apple-system,"PingFang SC","Hiragino Sans GB",sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px 80px}
a{color:var(--acc)}
.hero{display:grid;grid-template-columns:140px 1fr;gap:18px;align-items:end;margin:8px 0 28px}
.hero img{width:140px;height:140px;object-fit:cover;border-radius:4px;box-shadow:0 6px 24px rgba(0,0,0,.18)}
.hero h1{font:600 26px/1.2 "Avenir Next","Helvetica Neue",sans-serif;margin:0 0 4px;letter-spacing:.01em}
.hero .by{color:var(--mute);font-size:14px;line-height:1.5}
.meta{font:12px/1.6 ui-monospace,Menlo,monospace;color:var(--mute);letter-spacing:.04em;text-transform:uppercase}
.intro{margin:0 0 28px}
h2{font:600 13px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);margin:40px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
ol.tracks{list-style:none;margin:0;padding:0}
ol.tracks li{padding:14px 0;border-bottom:1px solid var(--line);scroll-margin-top:12px}
ol.tracks li:target{background:var(--card);margin:0 -12px;padding:14px 12px;border-radius:6px}
.tr{display:flex;gap:12px;align-items:baseline}
.tr .n{font:600 13px ui-monospace,Menlo,monospace;color:var(--acc);min-width:22px}
.tr .t{flex:1;font-weight:600}
.tr .d{font:13px ui-monospace,Menlo,monospace;color:var(--mute)}
.tracks p{margin:4px 0 0 34px;color:var(--fg);opacity:.86;font-size:15px}
.tracks p.cr{margin-top:0;font-size:12px;color:var(--mute);opacity:1}
.links a{display:inline-block;margin:0 14px 6px 0}
.credits{font-size:14px;color:var(--mute);padding-left:18px}
.essay h3{font-size:17px;margin:22px 0 6px}
.essay p{margin:0}
footer{margin-top:48px;font-size:12px;color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:18px}
.grid a{text-decoration:none;color:var(--fg);font-size:14px}
.grid img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:4px}
"""

e = html.escape


def page(title, body, extra_head=""):
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style>{extra_head}</head>
<body><main>{body}</main></body></html>"""


def related_html(a, by_slug):
    rel = [by_slug[s] for s in a.get("related", []) if s in by_slug]
    if not rel:
        return ""
    items = "".join(
        f'<a href="../{r["slug"]}/"><img src="../{r["slug"]}/{r["cover"]}" alt=""><br><b>{e(r["title"])}</b><br>'
        f'<span style="color:var(--mute)">{e(r["artist"])}</span></a>' for r in rel)
    return f'<h2>相关专辑</h2><div class="grid">{items}</div>'


def album_page(a, by_slug):
    tracks = "".join(
        f'<li id="t{t["n"]}"><div class="tr"><span class="n">{t["n"]:02d}</span>'
        f'<span class="t">{e(t["title"])}</span><span class="d">{e(t.get("time", ""))}</span></div>'
        + (f'<p class="cr">{e(t["credit"])}</p>' if t.get("credit") else "")
        + (f'<p>{e(t["note"])}</p>' if t.get("note") else "") + "</li>"
        for t in a["tracks"])
    credits = "".join(f"<li>{e(c)}</li>" for c in a.get("credits", []))
    essays = "".join(f'<div class="essay"><h3>{e(s["h"])}</h3><p>{e(s["p"])}</p></div>'
                     for s in a.get("essays", []))
    title_zh = f'<br><span style="color:var(--mute);font-weight:400">{e(a["title_zh"])}</span>' if a.get("title_zh") else ""
    body = f"""
<div class="hero"><img src="{e(a['cover'])}" alt="">
<div><div class="meta">{e(a.get('label',''))} · {e(a.get('released',''))}</div>
<h1>{e(a['title'])}{title_zh}</h1>
<div class="by">{e(a['artist'])}{' · ' + e(a['artist_zh']) if a.get('artist_zh') else ''}<br>{e(a.get('performers',''))}</div></div></div>
<p class="intro">{e(a.get('intro',''))}</p>
<div class="meta">MD · {e(a.get('md_mode',''))} · 录于 {e(a.get('recorded',''))} · 总长 {e(a.get('total',''))}</div>
{'<h2>歌词</h2><div class="links">' + ''.join(f'<a href="{e(u)}">{e(n)}</a>' for n, u in a['lyrics_links']) + '</div>' if a.get('lyrics_links') else ''}
<h2>Tracks</h2><ol class="tracks">{tracks}</ol>
{'<h2>Credits</h2><ul class="credits">' + credits + '</ul>' if credits else ''}
{'<h2>Notes</h2>' + essays if essays else ''}
{related_html(a, by_slug)}
<footer><a href="../../">← 全部 MD</a></footer>"""
    return page(f"{a['title']} — MD", body)


def download_cover(artist, title, album, dest_path):
    """Download cover art from iTunes Search API."""
    try:
        # Try with album first if available
        if album:
            queries = [
                f"{artist} {album}",
                f"{title} {artist}",
                album
            ]
        else:
            queries = [f"{artist} {title}", title]
        
        for query in queries:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=5"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
                if data.get("results"):
                    for result in data["results"]:
                        artwork_url = result.get("artworkUrl100", "").replace("100x100", "600x600")
                        if artwork_url:
                            try:
                                with urllib.request.urlopen(artwork_url, timeout=10) as img_response:
                                    dest_path.write_bytes(img_response.read())
                                    return True
                            except Exception:
                                continue
        return False
    except Exception:
        return False


def create_placeholder_cover(dest_path, title):
    """Create a simple SVG placeholder cover."""
    svg = f'''<svg width="600" height="600" xmlns="http://www.w3.org/2000/svg">
<rect width="600" height="600" fill="#d9d3c8"/>
<text x="300" y="320" font-family="system-ui,sans-serif" font-size="18" fill="#77716a" text-anchor="middle" dominant-baseline="middle">♪</text>
</svg>'''
    dest_path.write_text(svg.strip())
    dest_path.rename(dest_path.with_suffix('.svg'))
    return dest_path.with_suffix('.svg')


def listening_page(session):
    """Generate HTML for a listening session."""
    ctx = session["context"]
    md_cross = session.get("md_crossover")
    
    # MD crossover callout
    md_html = ""
    if md_cross:
        # Use relative path for the existing album page
        album_link = f"../../albums/{md_cross['slug']}/"
        md_html = f'''<div style="background:var(--card);padding:18px;border-radius:6px;border-left:3px solid var(--acc);margin:24px 0">
<div style="font:600 13px ui-monospace,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);margin-bottom:8px">MD 交汇 · MiniDisc Crossover</div>
<p style="margin:0 0 6px"><b>{e(md_cross["title"])}</b> · {e(md_cross["artist"])}</p>
<p style="margin:0;font-size:14px;color:var(--mute)">{e(md_cross["note"])}</p>
<p style="margin:8px 0 0"><a href="{album_link}">→ 查看完整衬页</a></p></div>'''
    
    # Timeline
    timeline_items = []
    for t in session["tracks"]:
        time_badge = f'<span class="meta" style="min-width:80px">{e(t["approx_time"] or "")}</span>' if t.get("approx_time") else ''
        cover_filename = t.get("_cover_file") or f"{t['artist']}-{t['title']}".replace("/", "-").replace(" ", "-")[:60] + ".jpg"
        cover_html = f'<img src="covers/{e(cover_filename)}" alt="" style="width:64px;height:64px;object-fit:cover;border-radius:3px;box-shadow:0 2px 8px rgba(0,0,0,.15)">'
        
        spotify_link = f'https://www.google.com/search?q=site:open.spotify.com+{urllib.parse.quote(t.get("spotify_search", ""))}'
        source_badge = f'<a href="{spotify_link}" style="display:inline-block;background:var(--acc);color:#fff;font:600 9px ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border-radius:3px;text-decoration:none;margin-left:8px">Spotify</a>'
        
        md_badge = ''
        if t.get("md"):
            md_badge = '<span style="display:inline-block;background:var(--card);border:1px solid var(--acc);color:var(--acc);font:600 9px ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border-radius:3px;margin-left:8px">MD</span>'
        
        performers = f'<div style="font-size:13px;color:var(--mute);margin-top:2px">{e(t["performers"])}</div>' if t.get("performers") else ''
        intro = f'<p style="margin:8px 0 0;font-size:14px;opacity:.86">{e(t["intro"])}</p>' if t.get("intro") else ''
        user_note = f'<p style="margin:8px 0 0;font-size:14px;color:var(--mute);font-style:italic;padding-left:12px;border-left:2px solid var(--line)">体会：{e(t["user_note"])}</p>' if t.get("user_note") else ''
        
        timeline_items.append(f'''<div style="display:flex;gap:14px;padding:20px 0;border-bottom:1px solid var(--line)">
{time_badge}
{cover_html}
<div style="flex:1">
<div><b>{e(t["title"])}</b> {source_badge}{md_badge}</div>
<div style="font-size:14px;color:var(--mute);margin-top:2px">{e(t["artist"])} · {e(t["album"] or "")}</div>
{performers}
{intro}
{user_note}
</div></div>''')
    
    timeline_html = "".join(timeline_items)
    
    body = f'''
<div style="margin-bottom:32px">
<div class="meta">{e(session["date"])} · {e(ctx["device"])}</div>
<h1 style="font:600 26px/1.2 Avenir Next,Helvetica Neue,sans-serif;margin:8px 0">{e(session["title"])}</h1>
<p style="font-size:15px;color:var(--mute);line-height:1.6;margin:12px 0 0">{e(ctx["zh"])}</p>
</div>
{md_html}
<h2>听歌时间线 · Timeline</h2>
{timeline_html}
<footer><a href="../../">← 返回首页</a></footer>'''
    
    return page(f"{session['title']} — 听歌日记", body)


def main():
    # Build albums
    albums = [json.loads(f.read_text()) for f in sorted(ALBUMS.glob("*.json"))]
    by_slug = {a["slug"]: a for a in albums}
    for a in albums:
        out = DOCS / "albums" / a["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(album_page(a, by_slug))
        src_cover = ALBUMS / a["slug"] / a["cover"]
        if src_cover.exists():
            shutil.copy(src_cover, out / a["cover"])
    
    # Build listening sessions
    sessions = []
    if LISTENING.exists():
        sessions = [json.loads(f.read_text()) for f in sorted(LISTENING.glob("*.json"))]
        for sess in sessions:
            out = DOCS / "listening" / sess["slug"]
            covers_dir = out / "covers"
            covers_dir.mkdir(parents=True, exist_ok=True)
            
            # Download covers
            print(f"Downloading covers for {sess['slug']}...")
            for t in sess["tracks"]:
                cover_filename = f"{t['artist']}-{t['title']}".replace("/", "-").replace(" ", "-")[:60] + ".jpg"
                cover_path = covers_dir / cover_filename
                if not cover_path.exists():
                    if download_cover(t["artist"], t["title"], t.get("album"), cover_path):
                        print(f"  ✓ {t['title']}")
                        time.sleep(0.3)  # Rate limiting
                    else:
                        # Create a placeholder SVG
                        svg_path = create_placeholder_cover(cover_path, t["title"])
                        print(f"  ⚠ {t['title']} (placeholder)")
                        # Update the filename in memory for HTML generation
                        t["_cover_file"] = svg_path.name
            
            (out / "index.html").write_text(listening_page(sess))
    
    # Build index
    albums.sort(key=lambda a: a.get("recorded", ""), reverse=True)
    album_grid = "".join(
        f'<a href="albums/{a["slug"]}/"><img src="albums/{a["slug"]}/{a["cover"]}" alt=""><br>'
        f'<b>{e(a["title"])}</b><br><span style="color:var(--mute)">{e(a["artist"])}</span></a>'
        for a in albums)
    
    listening_section = ""
    if sessions:
        sessions.sort(key=lambda s: s["date"], reverse=True)
        listening_grid = "".join(
            f'<a href="listening/{s["slug"]}/" style="padding:14px;background:var(--card);border-radius:6px;border-left:3px solid var(--acc)">'
            f'<div class="meta" style="margin-bottom:4px">{e(s["date"])}</div>'
            f'<b>{e(s["title"])}</b><br>'
            f'<span style="color:var(--mute);font-size:13px">{e(s["context"]["source"])} · {len(s["tracks"])} tracks</span></a>'
            for s in sessions)
        listening_section = f'<h2 style="font:600 18px Avenir Next,sans-serif;margin:40px 0 18px;color:var(--acc)">听歌日记 · Listening</h2><div style="display:grid;gap:12px">{listening_grid}</div>'
    
    index_body = f'''<h1 style="font:600 22px Avenir Next,sans-serif">MD Liner Notes</h1>
{listening_section}
<h2 style="font:600 18px Avenir Next,sans-serif;margin:40px 0 18px">专辑衬页 · Albums</h2>
<div class="grid">{album_grid}</div>'''
    
    (DOCS / "index.html").write_text(page("MD Liner Notes", index_body))
    (DOCS / ".nojekyll").write_text("")
    print(f"✓ Built {len(albums)} album(s) and {len(sessions)} listening session(s)")


if __name__ == "__main__":
    main()
