#!/usr/bin/env python3
"""Generate a printable A4 PDF (opens editable in Affinity / Illustrator) for a MiniDisc insert.

Layout follows the 2025-03+ hand-made paradigm:
  insert  W x H (default 73 x 126.3 mm), fold at FOLD (63 mm) from top
    front : cover square W x W pinned to top (overflows past the fold), one title line above the fold
    back  : blurred cover, tracklist, QR (-> liner-notes page), date bottom-right
  disc label 55 x 36 mm below the insert, centre-cropped cover
Guides: thin cut outline + dashed fold line + corner crop marks (delete in Affinity if unwanted).

usage: make_cover.py albums/<slug>.json out.pdf [--width 73 --height 126.3 --fold 63
        --label 55x36 --base-url https://mengdream.github.io/md-liner-notes --no-times]
"""
import argparse
import io
import json
import tempfile
from pathlib import Path

import fitz  # pymupdf
import qrcode
from fontTools.ttLib import TTCollection
from PIL import Image, ImageEnhance, ImageFilter, ImageStat

MM = 72 / 25.4
DPI = 450
ROOT = Path(__file__).resolve().parent.parent
FONTS = {  # (ttc, index) — system fonts so Affinity can keep text editable
    "song": ("/System/Library/Fonts/Supplemental/Songti.ttc", 3),       # STSongti-SC-Light
    "serif": ("/System/Library/Fonts/Supplemental/Baskerville.ttc", 0),  # Baskerville
    "serif_i": ("/System/Library/Fonts/Supplemental/Baskerville.ttc", 2),
}


def font_files():
    out = {}
    tmp = Path(tempfile.mkdtemp())
    for key, (ttc, idx) in FONTS.items():
        p = tmp / f"{key}.ttf"
        TTCollection(ttc)[idx].save(p)
        out[key] = str(p)
    return out


def px(mm):
    return max(1, round(mm / 25.4 * DPI))


def crop_to(img, w_mm, h_mm, cx=0.5, cy=0.5):
    """Centre-crop img to aspect w:h (cx/cy = focal point 0..1) and resample to DPI."""
    W, H = img.size
    tr = w_mm / h_mm
    if W / H > tr:
        nw, nh = round(H * tr), H
    else:
        nw, nh = W, round(W / tr)
    x = min(max(0, round(cx * W - nw / 2)), W - nw)
    y = min(max(0, round(cy * H - nh / 2)), H - nh)
    return img.crop((x, y, x + nw, y + nh)).resize((px(w_mm), px(h_mm)), Image.LANCZOS)


def label_image(img, w_mm, h_mm, cx=0.5, cy=0.5, zoom=1.0):
    """Disc label: crop around focal point; zoom < 1 shows more of the cover than fits,
    filling the leftover edges with a blurred, stretched copy so nothing looks letterboxed."""
    if zoom >= 1:
        return crop_to(img, w_mm, h_mm, cx, cy)
    out_w, out_h = px(w_mm), px(h_mm)
    bg = crop_to(img, w_mm, h_mm, cx, cy).filter(ImageFilter.GaussianBlur(out_w / 25))
    W, H = img.size
    s = min(out_w / W, out_h / H) / zoom                  # zoom=1 -> whole image fits the short side
    s = max(s, min(out_w / W, out_h / H))                 # never smaller than "fit whole cover"
    fg = img.resize((round(W * s), round(H * s)), Image.LANCZOS)
    x = round(out_w / 2 - cx * fg.width)
    y = round(out_h / 2 - cy * fg.height)
    x = min(max(x, out_w - fg.width), 0) if fg.width >= out_w else (out_w - fg.width) // 2
    y = min(max(y, out_h - fg.height), 0) if fg.height >= out_h else (out_h - fg.height) // 2
    mask = Image.new("L", fg.size, 255)
    feather = round(min(fg.size) * 0.04)
    if feather:
        from PIL import ImageDraw
        mask = Image.new("L", fg.size, 0)
        ImageDraw.Draw(mask).rectangle((feather, feather, fg.width - feather, fg.height - feather), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    bg.paste(fg, (x, y), mask)
    return bg


def patch_out(img, box):
    """Hide a logo etc.: fill normalized box (x0,y0,x1,y1) with the heavily blurred surroundings."""
    from PIL import ImageDraw
    W, H = img.size
    x0, y0, x1, y1 = round(box[0] * W), round(box[1] * H), round(box[2] * W), round(box[3] * H)
    blur = img.filter(ImageFilter.GaussianBlur(max(x1 - x0, y1 - y0) / 2.5))
    mask = Image.new("L", img.size, 0)
    f = round(min(x1 - x0, y1 - y0) * 0.25)
    ImageDraw.Draw(mask).rectangle((x0 - f, y0 - f, x1 + f, y1 + f), fill=255)
    out = img.copy()
    out.paste(blur, (0, 0), mask.filter(ImageFilter.GaussianBlur(f)))
    return out


def jpg(img):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=92)
    return b.getvalue()


def has_cjk(s):
    return any(ord(c) >= 0x2E80 for c in s)


def luminance(img):
    r, g, b = ImageStat.Stat(img.convert("RGB")).mean
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("album")
    ap.add_argument("out")
    ap.add_argument("--width", type=float, default=73)
    ap.add_argument("--height", type=float, default=126.3)
    ap.add_argument("--fold", type=float, default=63)
    ap.add_argument("--label", default="55x36")
    ap.add_argument("--base-url", default="https://mengdream.github.io/md-liner-notes")
    ap.add_argument("--label-focus", help="cx,cy focal point 0..1 (default: album json label_focus or 0.5,0.5)")
    ap.add_argument("--label-zoom", type=float, help="<1 zooms out to show more of the cover (json: label_zoom)")
    ap.add_argument("--title-gap", type=float, default=1.2,
                    help="front title baseline distance above the fold, mm (descenders must clear the crease)")
    ap.add_argument("--no-times", action="store_true")
    ap.add_argument("--no-guides", action="store_true")
    a = ap.parse_args()

    album_path = Path(a.album)
    A = json.loads(album_path.read_text())
    cover = Image.open(album_path.parent / A["slug"] / A["cover"]).convert("RGB")
    W, H, F = a.width, a.height, a.fold
    LW, LH = (float(v) for v in a.label.lower().split("x"))
    X0, Y0 = 11.0, 13.8                     # same origin as the hand-made files
    fonts = font_files()

    doc = fitz.open()
    page = doc.new_page(width=210 * MM, height=297 * MM)
    for k, f in fonts.items():
        page.insert_font(fontname=k, fontfile=f)

    def R(x, y, w, h):
        return fitz.Rect((X0 + x) * MM, (Y0 + y) * MM, (X0 + x + w) * MM, (Y0 + y + h) * MM)

    def text(x, y, s, font, size, color, align="left", shadow=False):
        w = fitz.Font(fontfile=fonts[font]).text_length(s, fontsize=size)
        px_ = (X0 + x) * MM - (w if align == "right" else 0)
        if shadow:
            page.insert_text(fitz.Point(px_ + 0.2 * MM, (Y0 + y + 0.2) * MM), s, fontname=font,
                             fontsize=size, color=(0, 0, 0), fill_opacity=0.45)
        page.insert_text(fitz.Point(px_, (Y0 + y) * MM), s, fontname=font, fontsize=size, color=color)
        return w / MM

    # ---- back: blurred cover fills the back panel (under the overflow band)
    back = cover.resize((1200, 1200)).filter(ImageFilter.GaussianBlur(40))
    back = Image.blend(back, Image.new("RGB", back.size, tuple(int(c) for c in ImageStat.Stat(back).mean)), 0.45)
    lum = luminance(back)
    dark = lum < 0.55
    back = ImageEnhance.Brightness(back).enhance(0.8 if dark else 1.08)
    page.insert_image(R(0, F, W, H - F), stream=jpg(crop_to(back, W, H - F, cy=0.4)))

    # ---- front: square cover pinned to top, overflowing past the fold (the band shows on the back)
    over = min(W, H) - F
    page.insert_image(R(0, 0, W, min(W, H)), stream=jpg(crop_to(cover, W, min(W, H))))

    ink = (1, 1, 1) if dark else (0.29, 0.17, 0.07)       # white on dark blur, warm brown on light
    sub = (0.85, 0.85, 0.85) if dark else (0.45, 0.33, 0.22)

    # front title line (above the fold), like "philip glass  第一小提琴协奏曲"
    front_band = crop_to(cover, W, min(W, H)).crop((0, px(F - 7), px(W), px(F)))
    t_ink = (1, 1, 1) if luminance(front_band) < 0.6 else (0.14, 0.1, 0.09)
    x = 2.5
    x += text(x, F - a.title_gap, f"{A['artist']}  ", "serif", 8.5, t_ink, shadow=t_ink == (1, 1, 1))
    if A.get("artist_zh"):
        x += text(x, F - a.title_gap, f"{A['artist_zh']}  ", "song", 8.5, t_ink, shadow=t_ink == (1, 1, 1))
    text(x, F - a.title_gap, A.get("title_zh", ""), "song", 8.5, t_ink, shadow=t_ink == (1, 1, 1))

    # ---- back: tracklist
    top = F + over + 4.2
    n = len(A["tracks"])
    avail = H - top - 3.5
    lead = min(3.6, avail / n)
    size = min(8.0, lead / 25.4 * 72 / 1.3)                # leading ≈ 1.3 × font size
    for i, t in enumerate(A["tracks"]):
        y = top + i * lead
        num = f"{t['n']}."
        x = 2.4
        x += text(x, y, num, "serif", size, ink) + 0.6
        x += text(x, y, t["title"], "song" if has_cjk(t["title"]) else "serif", size, ink)
        if not a.no_times and t.get("time"):
            text(x + 1.4, y, t["time"], "serif_i", size * 0.85, sub)

    # ---- QR -> liner notes page, bottom-right, with a small paper-white pad for reliable scanning
    url = f"{a.base_url.rstrip('/')}/albums/{A['slug']}/"
    q = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20)
    q.add_data(url)
    q.make(fit=True)
    qs = 13.0
    qx, qy = W - qs - 2.0, H - qs - 6.0
    b = io.BytesIO()
    q.make_image(fill_color="black", back_color="white").save(b, "PNG")
    page.insert_image(R(qx, qy, qs, qs), stream=b.getvalue())
    text(W - 2.0, H - 2.4, A.get("recorded", ""), "song", 8, ink, align="right")

    # ---- disc label
    ly = H + 16.8
    lcx, lcy = (float(v) for v in (a.label_focus or A.get("label_focus", "0.5,0.5")).split(","))
    lzoom = a.label_zoom or A.get("label_zoom", 1.0)
    label_src = cover
    for box in A.get("label_hide", []):              # e.g. record-label logo that pokes into the crop
        label_src = patch_out(label_src, box)
    page.insert_image(R(0, ly, LW, LH), stream=jpg(label_image(label_src, LW, LH, lcx, lcy, lzoom)))

    # ---- guides
    if not a.no_guides:
        sh = page.new_shape()
        for (x, y, w, h) in ((0, 0, W, H), (0, ly, LW, LH)):
            sh.draw_rect(R(x, y, w, h))
        sh.finish(color=(0.75, 0.75, 0.75), width=0.25)
        sh.draw_line(R(0, F, 0, 0).tl + (-3 * MM, 0), R(0, F, 0, 0).tl + (-0.8 * MM, 0))
        sh.draw_line(R(W, F, 0, 0).tl + (0.8 * MM, 0), R(W, F, 0, 0).tl + (3 * MM, 0))
        sh.finish(color=(0.6, 0.6, 0.6), width=0.3, dashes="[1 1] 0")
        sh.commit()
        page.insert_text(fitz.Point((X0 + W + 4) * MM, (Y0 + F + 1) * MM), f"fold {F}", fontsize=5, color=(0.6, 0.6, 0.6))
        page.insert_text(fitz.Point((X0 + W + 4) * MM, (Y0 + 3) * MM),
                         f"insert {W} x {H} mm", fontsize=5, color=(0.6, 0.6, 0.6))
        page.insert_text(fitz.Point((X0 + LW + 4) * MM, (Y0 + ly + 3) * MM),
                         f"label {LW:g} x {LH:g} mm", fontsize=5, color=(0.6, 0.6, 0.6))

    doc.set_metadata({"title": f"{A['artist']} - {A['title']} MD cover", "creator": "md-liner-notes"})
    doc.subset_fonts()
    doc.save(a.out, garbage=4, deflate=True)
    print(f"wrote {a.out}  ({'dark' if dark else 'light'} back, lead {lead:.2f}mm, size {size:.1f}pt)  QR -> {url}")


if __name__ == "__main__":
    main()
