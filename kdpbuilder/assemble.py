"""Assemble a print-ready interior PDF (workflow steps 5 and 6).

Places each cleaned design on a page at the exact KDP page size, at the
target DPI, and inserts a blank backing page for single-sided printing so
markers do not show through. Supports bleed and no-bleed setups.

Page geometry and margins come from kdpbuilder.specs, which reads the shared
kdp_specs.json. Nothing about the sizes is hardcoded here.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image

from . import specs as kspecs


def _compose_page_canvas(
    design: Image.Image,
    canvas_px: tuple[int, int],
    margin_px: int,
    mode: str,
) -> Image.Image:
    """Render one full-page white canvas with the design placed on it.

    mode 'fit' scales the design inside the margin box and centers it (for
    no-bleed interiors). mode 'fill' covers the whole page edge to edge and
    crops the overflow (for bleed pages where art reaches the trim).
    """
    cw, ch = canvas_px
    canvas = Image.new("L", (cw, ch), 255)
    src = design.convert("L")

    if mode == "fill":
        box_w, box_h = cw, ch
        off_x, off_y = 0, 0
        scale = max(box_w / src.width, box_h / src.height)
        new = src.resize(
            (max(1, round(src.width * scale)), max(1, round(src.height * scale))),
            Image.LANCZOS,
        )
        left = (new.width - box_w) // 2
        top = (new.height - box_h) // 2
        new = new.crop((left, top, left + box_w, top + box_h))
        canvas.paste(new, (off_x, off_y))
        return canvas

    # fit
    box_w = max(1, cw - 2 * margin_px)
    box_h = max(1, ch - 2 * margin_px)
    scale = min(box_w / src.width, box_h / src.height)
    new = src.resize(
        (max(1, round(src.width * scale)), max(1, round(src.height * scale))),
        Image.LANCZOS,
    )
    off_x = (cw - new.width) // 2
    off_y = (ch - new.height) // 2
    canvas.paste(new, (off_x, off_y))
    return canvas


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def build_interior(
    designs: list[Image.Image],
    out_path: str | Path,
    trim: str,
    paper: str = "bw_white",
    bleed: bool = False,
    single_sided: bool = True,
    dpi: int | None = None,
    specs: dict | None = None,
    mode: str | None = None,
) -> dict:
    """Build the interior PDF and return a small summary dict.

    designs: cleaned black-on-white images, one per page/design.
    single_sided: insert a blank page after each design (coloring-book default).
    bleed: if True, page = trim + bleed and designs fill to the edge.
    """
    specs = specs or kspecs.load_specs()
    dpi = dpi or kspecs.recommended_dpi(specs)
    mode = mode or ("fill" if bleed else "fit")

    page_w_in, page_h_in = kspecs.page_size_in(specs, trim, bleed)
    page_w_pt, page_h_pt = page_w_in * 72.0, page_h_in * 72.0
    canvas_px = (round(page_w_in * dpi), round(page_h_in * dpi))

    total_pages = len(designs) * (2 if single_sided else 1)
    margin_in = max(
        kspecs.min_margin_in(specs, bleed),
        kspecs.gutter_in(specs, total_pages),
    )
    margin_px = round(margin_in * dpi)

    doc = pymupdf.open()
    rect = pymupdf.Rect(0, 0, page_w_pt, page_h_pt)
    for design in designs:
        page = doc.new_page(width=page_w_pt, height=page_h_pt)
        canvas = _compose_page_canvas(design, canvas_px, margin_px, mode)
        page.insert_image(rect, stream=_png_bytes(canvas))
        if single_sided:
            doc.new_page(width=page_w_pt, height=page_h_pt)  # blank back

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path), garbage=4, deflate=True)
    doc.close()

    return {
        "file": str(out_path),
        "trim": trim,
        "paper": paper,
        "bleed": bleed,
        "single_sided": single_sided,
        "dpi": dpi,
        "designs": len(designs),
        "pages": total_pages,
        "page_size_in": [round(page_w_in, 3), round(page_h_in, 3)],
        "margin_in": round(margin_in, 3),
    }


def load_images(paths: list[str | Path]) -> list[Image.Image]:
    return [Image.open(p) for p in paths]
