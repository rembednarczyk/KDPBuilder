"""Assemble a print-ready KDP paperback cover (full wrap) as one PDF.

Layout, left to right: back cover, spine, front cover, with bleed on all four
outer edges. Geometry (spine width, full size, panel boundaries) comes from
kdpbuilder.specs, which reads the shared kdp_specs.json.

The cover is a wraparound: the front art's background is extended across the
spine and back so the image reads as one continuous piece. The back shows a
scattered collage of interior-page thumbnails (tilted cards with soft shadows),
a design-count sticker, floating bubbles and frosted text panels, in a clean
modern style. Title and other text are typeset here, not baked into the AI
image, so spelling and placement stay under our control.

The KDP barcode is added automatically on the back bottom-right; that area is
kept clear. Always confirm the final spine width against the KDP cover
calculator before uploading; paper thickness can change.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import specs as kspecs

_BUNDLED_TITLE = Path(__file__).resolve().parent / "data" / "fonts" / "Baloo2-ExtraBold.ttf"
# Rounded, bold, playful title font (Baloo 2, OFL) for the niche look; fall back
# to DejaVu Bold if the bundled file is missing.
DEFAULT_TITLE_FONT = str(_BUNDLED_TITLE) if _BUNDLED_TITLE.exists() else \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEFAULT_BODY_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _hex(color) -> tuple:
    if isinstance(color, tuple):
        return color
    c = color.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_block(draw, text, font_path, max_w, max_h, start_size, min_size=10):
    """Largest font size (<= start_size) whose wrapped text fits the box."""
    size = start_size
    while size >= min_size:
        font = _font(font_path, size)
        lines = _wrap(draw, text, font, max_w)
        line_h = font.getbbox("Ag")[3] + int(size * 0.25)
        if len(lines) * line_h <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines, line_h
        size -= 2
    font = _font(font_path, min_size)
    return font, _wrap(draw, text, font, max_w), font.getbbox("Ag")[3] + int(min_size * 0.25)


def _draw_lines(draw, lines, font, line_h, cx, top, fill, align="center"):
    y = top
    for line in lines:
        w = draw.textlength(line, font=font)
        x = cx - w / 2 if align == "center" else cx
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


def _draw_lines_outlined(odraw, lines, font, line_h, cx, top, fill, outline, ow, shadow_off):
    """Centered lines with a thick outline and a soft drop shadow (RGBA overlay)."""
    y = top
    for line in lines:
        w = odraw.textlength(line, font=font)
        x = cx - w / 2
        odraw.text((x + shadow_off, y + shadow_off), line, font=font,
                   fill=(0, 0, 0, 110), stroke_width=ow, stroke_fill=(0, 0, 0, 110))
        odraw.text((x, y), line, font=font, fill=fill, stroke_width=ow, stroke_fill=outline)
        y += line_h
    return y


def _fill_cover(art: Image.Image, box_w, box_h) -> Image.Image:
    src = art.convert("RGB")
    scale = max(box_w / src.width, box_h / src.height)
    new = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))), Image.LANCZOS)
    left = (new.width - box_w) // 2
    top = (new.height - box_h) // 2
    return new.crop((left, top, left + box_w, top + box_h))


# --- wraparound and decoration helpers -----------------------------------

def _extend_bg_left(art_box: Image.Image, width: int, height: int) -> Image.Image:
    """Continue the art's background leftward by repeating its left-edge color
    per row, so the water/gradient flows across the spine onto the back."""
    a = np.asarray(art_box.convert("RGB"))
    edge = max(1, int(a.shape[1] * 0.03))
    row = a[:, :edge, :].mean(axis=1).astype("uint8")  # (H, 3) per-row colour
    # smooth vertically so edge detail (plants) does not print as hard bands
    col = Image.fromarray(row[:, None, :], "RGB").filter(
        ImageFilter.GaussianBlur(max(2, a.shape[0] // 110)))
    row = np.asarray(col)[:, 0, :]
    strip = Image.fromarray(np.repeat(row[:, None, :], max(1, width), axis=1), "RGB")
    return strip.resize((max(1, width), height), Image.LANCZOS)


def _bubbles(draw, x0, x1, y0, y1, seed, n=26):
    """Scatter soft translucent bubbles for a light, modern feel."""
    rng = random.Random(seed)
    span = max(1, y1 - y0)
    for _ in range(n):
        r = rng.randint(int(span * 0.012), int(span * 0.05))
        x = rng.randint(x0, x1)
        y = rng.randint(y0, y1)
        a = rng.randint(16, 46)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, a))
        draw.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, a + 45),
                     width=max(2, r // 7))


def _sparkle(draw, cx, cy, r, color):
    """A small four-point star accent."""
    draw.polygon([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy),
                  (cx + r * 0.28, cy + r * 0.28), (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
                  (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], fill=color)


def _thumb_card(thumb: Image.Image, w: int, h: int, pad: int, radius: int) -> Image.Image:
    """A white rounded card with the interior design inset (RGBA)."""
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    ImageDraw.Draw(card).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=(255, 255, 255, 255))
    inner = _fill_cover(thumb, w - 2 * pad, h - 2 * pad)
    imask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(imask).rounded_rectangle([0, 0, inner.size[0] - 1, inner.size[1] - 1],
                                            radius=max(2, radius // 2), fill=255)
    card.paste(inner, (pad, pad), imask)
    card.putalpha(Image.composite(card.split()[-1], Image.new("L", (w, h), 0), mask))
    return card


def _paste_card(layer: Image.Image, thumb, center, angle, w, h):
    """Paste a tilted thumbnail card with a soft drop shadow onto an RGBA layer."""
    pad = max(4, w // 22)
    radius = max(6, w // 12)
    card = _thumb_card(thumb, w, h, pad, radius)
    rot = card.rotate(angle, expand=True, resample=Image.BICUBIC)
    blur = max(6, w // 14)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.split()[-1].point(lambda a: int(a * 0.38)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    cx, cy = center
    ox, oy = int(cx - rot.width / 2), int(cy - rot.height / 2)
    off = max(4, w // 26)
    layer.alpha_composite(shadow, (ox + off, oy + off))
    layer.alpha_composite(rot, (ox, oy))


def _burst_badge(layer, center, r, text, font_path, fill, outline, text_color):
    """A starburst sticker with centered text (e.g. the design count)."""
    size = int(r * 2.4)
    b = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    cx = cy = size / 2
    pts = []
    n = 14
    for i in range(n * 2):
        ang = math.pi * i / n
        rr = r if i % 2 == 0 else r * 0.78
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=fill, outline=outline)
    # centered two-line text
    lines = text.split("\n")
    fs = int(r * 0.5)
    font = _font(font_path, fs)
    lh = font.getbbox("Ag")[3] + int(fs * 0.1)
    ty = cy - (len(lines) * lh) / 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text((cx - w / 2, ty), ln, font=font, fill=text_color)
        ty += lh
    b = b.rotate(-12, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(b, (int(center[0] - b.width / 2), int(center[1] - b.height / 2)))


def _pick(items, k):
    if len(items) <= k:
        return list(items)
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def build_cover(
    front_art: Image.Image,
    out_path: str | Path,
    trim: str,
    page_count: int,
    paper: str = "bw_white",
    title: str = "",
    subtitle: str | None = None,
    author: str | None = None,
    blurb: str | None = None,
    bg_color="#FCE7A2",
    text_color="#213241",
    title_color=None,
    title_fill="#FFFFFF",
    title_outline="#12303A",
    banner_color="#FFFFFF",
    banner_alpha=210,
    thumbnails: list | None = None,
    count_badge: str | None = None,
    decorations: bool = True,
    wrap: bool = True,
    dpi: int = 300,
    font_title: str = DEFAULT_TITLE_FONT,
    font_body: str = DEFAULT_BODY_FONT,
    specs: dict | None = None,
) -> dict:
    specs = specs or kspecs.load_specs()
    full_w_in, full_h_in = kspecs.full_cover_size_in(specs, trim, page_count, paper)
    reg = kspecs.cover_regions_in(specs, trim, page_count, paper)
    safe = kspecs.min_margin_in(specs, bleed=True)

    W, H = round(full_w_in * dpi), round(full_h_in * dpi)
    px = lambda v: round(v * dpi)
    tcol = _hex(text_color)
    accent = _hex(title_fill or "#FFE14D")
    accent_outline = _hex(title_outline)

    # --- background: hero art on the front, extended across spine + back ---
    canvas = Image.new("RGB", (W, H), _hex(bg_color))
    front_x0_px = px(reg["front_x0"])
    art_box = _fill_cover(front_art, W - front_x0_px, H)
    canvas.paste(art_box, (front_x0_px, 0))
    if wrap and front_x0_px > 0:
        canvas.paste(_extend_bg_left(art_box, front_x0_px, H), (0, 0))

    # layers composited in order: decorations (bubbles), cards, then text
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(deco)
    tdraw = ImageDraw.Draw(text)

    if decorations:
        _bubbles(ddraw, 0, W, 0, H, seed=page_count * 100 + len(title), n=30)

    # --- back cover: blurb panel + thumbnail collage + count sticker ---
    bx0, bx1 = px(reg["back_x0"] + safe), px(reg["spine_x0"] - safe)
    by0, by1 = px(reg["bleed_in"] + safe), H - px(reg["bleed_in"] + safe)
    bcx = (bx0 + bx1) / 2
    bw = bx1 - bx0
    barcode_w, barcode_h = specs["cover"]["barcode_clear_in"]

    blurb_bottom = by0
    if blurb:
        bfont, blines, blh = _fit_block(tdraw, blurb, font_body, bw - px(0.5), px(2.2), int(bw * 0.055))
        panel_h = len(blines) * blh + px(0.4)
        tdraw.rounded_rectangle([bx0, by0, bx1, by0 + panel_h], radius=px(0.16),
                                fill=_hex(banner_color) + (215,))
        _draw_lines(tdraw, blines, bfont, blh, bcx, by0 + px(0.2), tcol + (255,))
        blurb_bottom = by0 + panel_h

    if thumbnails:
        picks = _pick(list(thumbnails), 5)
        ax0, ax1 = bx0, bx1
        ay0 = blurb_bottom + px(0.25)
        ay1 = by1 - px(barcode_h) - px(0.2)  # keep clear of the barcode
        cw = int((ax1 - ax0) * 0.46)
        ch = int(cw * 1.28)
        spots = [(0.27, 0.28, -9), (0.71, 0.24, 8), (0.30, 0.72, -6),
                 (0.70, 0.70, 9), (0.49, 0.50, -3)]
        for thumb, (fx, fy, ang) in zip(picks, spots[:len(picks)]):
            cx = ax0 + fx * (ax1 - ax0)
            cy = ay0 + fy * (ay1 - ay0)
            _paste_card(cards, thumb, (cx, cy), ang, cw, ch)

    # --- front cover: title, subtitle/author banner, count sticker ---
    fx0, fx1 = px(reg["front_x0"] + safe), px(reg["front_x1"] - safe)
    fcx = (fx0 + fx1) / 2
    fw = fx1 - fx0
    tit_fill = _hex(title_fill or title_color or "#FFFFFF") + (255,)
    tit_outline = _hex(title_outline) + (255,)

    if title:
        font, lines, lh = _fit_block(tdraw, title, font_title, fw, px(2.6), int(fw * 0.24))
        ow = max(2, int(font.size * 0.09))
        soff = max(2, int(font.size * 0.06))
        _draw_lines_outlined(tdraw, lines, font, lh, fcx, px(reg["bleed_in"] + safe),
                             tit_fill, tit_outline, ow, soff)

    # Subtitle and author use the rounded title font so the front reads as one
    # cohesive playful design; the back blurb stays in the body font for reading.
    band_lines = []
    if subtitle:
        sfont, slines, slh = _fit_block(tdraw, subtitle, font_title, fw - px(0.4), px(1.1), int(fw * 0.07))
        band_lines.append((slines, sfont, slh))
    if author:
        afont, alines, alh = _fit_block(tdraw, author, font_title, fw - px(0.4), px(0.7), int(fw * 0.06))
        band_lines.append((alines, afont, alh))
    if band_lines:
        pad = px(0.18)
        content_h = sum(len(l) * lh2 for l, _, lh2 in band_lines) + (len(band_lines) - 1) * px(0.05)
        band_bottom = H - px(reg["bleed_in"] + safe)
        band_top = band_bottom - content_h - 2 * pad
        tdraw.rounded_rectangle([fx0, band_top, fx1, band_bottom], radius=px(0.16),
                                fill=_hex(banner_color) + (int(banner_alpha),))
        y = band_top + pad
        for lines2, font2, lh2 in band_lines:
            y = _draw_lines(tdraw, lines2, font2, lh2, fcx, y, tcol + (255,)) + px(0.05)

    if count_badge:
        r = px(0.7)
        _burst_badge(text, (fx1 - r * 0.6, px(reg["bleed_in"] + safe) + px(2.9)), r,
                     count_badge, font_title, accent + (255,), accent_outline + (255,), accent_outline + (255,))
        if decorations:
            for sx, sy, sr in [(fx0 + px(0.3), px(3.5), px(0.12)), (fx1 - px(0.4), H - px(3.2), px(0.1))]:
                _sparkle(tdraw, sx, sy, sr, accent + (230,))

    # --- spine text over the wraparound background ---
    spine_note = "omitted (page count below KDP minimum)"
    if kspecs.spine_text_allowed(specs, page_count) and reg["spine_w_in"] > 0.1:
        spine_txt = title if not author else "%s  -  %s" % (title, author)
        s_safe = specs["cover"]["spine_text_safe_in"]
        s_w_px = px(reg["spine_w_in"] - 2 * s_safe)
        s_h_px = px(full_h_in - 2 * (reg["bleed_in"] + safe))
        strip = Image.new("RGBA", (max(1, s_h_px), max(1, s_w_px)), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(strip)
        sfont, slines, slh = _fit_block(sdraw, spine_txt, font_title, s_h_px, s_w_px, int(s_w_px * 0.7))
        _draw_lines(sdraw, slines, sfont, slh, s_h_px / 2, (s_w_px - len(slines) * slh) / 2,
                    _hex("#FFFFFF") + (255,))
        strip = strip.rotate(90, expand=True)
        sx = px(reg["spine_x0"]) + (px(reg["spine_w_in"]) - strip.width) // 2
        text.alpha_composite(strip, (sx, (H - strip.height) // 2))
        spine_note = "included"

    # --- compose all layers and save as a single-page PDF ---
    out = Image.alpha_composite(canvas.convert("RGBA"), deco)
    out = Image.alpha_composite(out, cards)
    out = Image.alpha_composite(out, text).convert("RGB")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=full_w_in * 72.0, height=full_h_in * 72.0)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(0, 0, full_w_in * 72.0, full_h_in * 72.0), stream=buf.getvalue())
    doc.save(str(out_path), garbage=4, deflate=True)
    doc.close()

    return {
        "file": str(out_path),
        "trim": trim,
        "paper": paper,
        "page_count": page_count,
        "spine_in": round(reg["spine_w_in"], 4),
        "full_cover_in": [round(full_w_in, 3), round(full_h_in, 3)],
        "dpi": dpi,
        "spine_text": spine_note,
        "wrap": bool(wrap),
        "thumbnails": len(thumbnails) if thumbnails else 0,
    }
