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

    if title:
        # Start large (about a fifth of the front width) and shrink to fit.
        font, lines, lh = _fit_block(draw, title, font_title, fw, px(2.4), int(fw * 0.22))
        top = px(reg["bleed_in"] + safe)
        # subtle white plate behind the title for legibility on busy art
        block_h = len(lines) * lh
        draw.rectangle([fx0 - px(0.1), top - px(0.1), fx1 + px(0.1), top + block_h + px(0.1)],
                       fill=(255, 255, 255))
        _draw_lines(draw, lines, font, lh, fcx, top, tit_col)
        cursor = top + block_h + px(0.15)
        if subtitle:
            sfont, slines, slh = _fit_block(draw, subtitle, font_body, fw, px(1.0), int(fw * 0.09))
            sblock = len(slines) * slh
            draw.rectangle([fx0 - px(0.08), cursor - px(0.06), fx1 + px(0.08), cursor + sblock + px(0.06)],
                           fill=(255, 255, 255))
            _draw_lines(draw, slines, sfont, slh, fcx, cursor, tcol)

    if author:
        afont, alines, alh = _fit_block(draw, author, font_body, fw, px(0.8), int(fw * 0.09))
        ablock = len(alines) * alh
        atop = H - px(reg["bleed_in"] + safe) - ablock
        draw.rectangle([fx0 - px(0.08), atop - px(0.06), fx1 + px(0.08), atop + ablock + px(0.06)],
                       fill=(255, 255, 255))
        _draw_lines(draw, alines, afont, alh, fcx, atop, tcol)

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
