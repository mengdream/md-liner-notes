#!/usr/bin/env python3
"""Render albums/*.json into docs/ (GitHub Pages).

docs/index.html                    album index
docs/albums/<slug>/index.html      liner notes (tracks #t1.., essays); raw GPT chats stay in private/ and are never published
"""
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALBUMS = ROOT / "albums"
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


def album_page(a):
    tracks = "".join(
        f'<li id="t{t["n"]}"><div class="tr"><span class="n">{t["n"]:02d}</span>'
        f'<span class="t">{e(t["title"])}</span><span class="d">{e(t["time"])}</span></div>'
        + (f'<p class="cr">{e(t["credit"])}</p>' if t.get("credit") else "")
        + (f'<p>{e(t["note"])}</p>' if t.get("note") else "") + "</li>"
        for t in a["tracks"])
    credits = "".join(f"<li>{e(c)}</li>" for c in a.get("credits", []))
    essays = "".join(f'<div class="essay"><h3>{e(s["h"])}</h3><p>{e(s["p"])}</p></div>'
                     for s in a.get("essays", []))
    title_zh = f' <span style="color:var(--mute);font-weight:400">{e(a["title_zh"])}</span>' if a.get("title_zh") else ""
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
<footer><a href="../../">← 全部 MD</a></footer>"""
    return page(f"{a['title']} — MD", body)


def main():
    albums = []
    for f in sorted(ALBUMS.glob("*.json")):
        a = json.loads(f.read_text())
        out = DOCS / "albums" / a["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(album_page(a))
        src_cover = ALBUMS / a["slug"] / a["cover"]
        if src_cover.exists():
            shutil.copy(src_cover, out / a["cover"])
        albums.append(a)
    albums.sort(key=lambda a: a.get("recorded", ""), reverse=True)
    grid = "".join(
        f'<a href="albums/{a["slug"]}/"><img src="albums/{a["slug"]}/{a["cover"]}" alt=""><br>'
        f'<b>{e(a["title"])}</b><br><span style="color:var(--mute)">{e(a["artist"])}</span></a>'
        for a in albums)
    (DOCS / "index.html").write_text(page("MD Liner Notes", f'<h1 style="font:600 22px Avenir Next,sans-serif">MD Liner Notes</h1><div class="grid">{grid}</div>'))
    (DOCS / ".nojekyll").write_text("")
    print(f"built {len(albums)} album(s)")


if __name__ == "__main__":
    main()
