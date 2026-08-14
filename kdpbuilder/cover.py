"""Assemble a print-ready KDP paperback cover (full wrap) as one PDF.

Layout, left to right: back cover, spine, front cover, with bleed on all four
outer edges. Geometry (spine width, full size, panel boundaries) comes from
kdpbuilder.specs, which reads the shared kdp_specs.json.

The front art is full-color raster (generate it with the cover prompt). Title
and other text are typeset here, not baked into the AI image, so spelling and
placement stay under our control.

Always confirm the final spine width against the KDP cover calculator before
uploading; paper thickness can change.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from . import specs as kspecs

DEFAULT_TITLE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
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
    """Centered lines with a thick outline and a soft drop shadow (RGBA overlay).

    This is the niche look: bold letters that pop straight over the art, no
    white plate behind them.
    """
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
    canvas = Image.new("RGB", (W, H), _hex(bg_color))
    draw = ImageDraw.Draw(canvas)
    tcol = _hex(text_color)
    tit_col = _hex(title_color) if title_color else tcol

    # Front art fills the front panel plus the outer bleed (right/top/bottom).
    front_x0_px = round(reg["front_x0"] * dpi)
    art_box = _fill_cover(front_art, W - front_x0_px, H)
    canvas.paste(art_box, (front_x0_px, 0))

    px = lambda v: round(v * dpi)
    # Front text region (inside the front trim, respecting the safe margin).
    fx0 = px(reg["front_x0"] + safe)
    fx1 = px(reg["front_x1"] - safe)
    fcx = (fx0 + fx1) / 2
    fw = fx1 - fx0

    # Front text goes on an RGBA overlay so the title outline, drop shadow and
    # the translucent subtitle banner all composite cleanly over the art.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    tit_fill = _hex(title_fill or title_color or "#FFFFFF") + (255,)
    tit_outline = _hex(title_outline) + (255,)

    if title:
        # Big outlined title straight on the art, no plate.
        font, lines, lh = _fit_block(odraw, title, font_title, fw, px(2.6), int(fw * 0.24))
        ow = max(2, int(font.size * 0.09))
        soff = max(2, int(font.size * 0.06))
        _draw_lines_outlined(odraw, lines, font, lh, fcx, px(reg["bleed_in"] + safe),
                             tit_fill, tit_outline, ow, soff)

    # Subtitle and author on a translucent rounded banner near the bottom.
    band_lines = []
    if subtitle:
        sfont, slines, slh = _fit_block(odraw, subtitle, font_body, fw - px(0.4), px(1.1), int(fw * 0.075))
        band_lines.append((slines, sfont, slh))
    if author:
        afont, alines, alh = _fit_block(odraw, author, font_body, fw - px(0.4), px(0.7), int(fw * 0.075))
        band_lines.append((alines, afont, alh))
    if band_lines:
        pad = px(0.18)
        content_h = sum(len(l) * lh2 for l, _, lh2 in band_lines) + (len(band_lines) - 1) * px(0.05)
        band_bottom = H - px(reg["bleed_in"] + safe)
        band_top = band_bottom - content_h - 2 * pad
        odraw.rounded_rectangle([fx0, band_top, fx1, band_bottom], radius=px(0.16),
                                fill=_hex(banner_color) + (int(banner_alpha),))
        y = band_top + pad
        for lines2, font2, lh2 in band_lines:
            y = _draw_lines(odraw, lines2, font2, lh2, fcx, y, tcol + (255,)) + px(0.05)

    # Back cover blurb (upper area; leave the bottom clear for the KDP barcode).
    if blurb:
        bx0 = px(reg["back_x0"] + safe)
        bx1 = px(reg["spine_x0"] - safe)
        bcx = (bx0 + bx1) / 2
        bw = bx1 - bx0
        barcode_h = specs["cover"]["barcode_clear_in"][1]
        avail_h = H - px(reg["bleed_in"] + safe) * 2 - px(barcode_h)
        bfont, blines, blh = _fit_block(draw, blurb, font_body, bw, avail_h, int(bw * 0.06))
        _draw_lines(draw, blines, bfont, blh, bcx, px(reg["bleed_in"] + safe) + px(0.3), tcol, align="center")

    # Spine text, only when the page count allows it.
    spine_note = "omitted (page count below KDP minimum)"
    if kspecs.spine_text_allowed(specs, page_count) and reg["spine_w_in"] > 0.1:
        spine_txt = title if not author else "%s  -  %s" % (title, author)
        s_safe = specs["cover"]["spine_text_safe_in"]
        s_w_px = px(reg["spine_w_in"] - 2 * s_safe)
        s_h_px = px(full_h_in - 2 * (reg["bleed_in"] + safe))
        strip = Image.new("RGB", (max(1, s_h_px), max(1, s_w_px)), _hex(bg_color))
        sdraw = ImageDraw.Draw(strip)
        sfont, slines, slh = _fit_block(sdraw, spine_txt, font_title, s_h_px, s_w_px, int(s_w_px * 0.7))
        _draw_lines(sdraw, slines, sfont, slh, s_h_px / 2, (s_w_px - len(slines) * slh) / 2, tcol)
        strip = strip.rotate(90, expand=True)
        sx = px(reg["spine_x0"]) + (px(reg["spine_w_in"]) - strip.width) // 2
        sy = (H - strip.height) // 2
        canvas.paste(strip, (sx, sy))
        spine_note = "included"

    # Composite the front text overlay (title outline, shadow, banner) over the art.
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    # Save as a single-page PDF at the exact point size.
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=full_w_in * 72.0, height=full_h_in * 72.0)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
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
    }
