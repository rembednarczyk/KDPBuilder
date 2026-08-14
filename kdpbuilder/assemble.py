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
    margins_px: tuple[int, int, int, int],
    mode: str,
) -> Image.Image:
    """Render one full-page white canvas with the design placed on it.

    margins_px is (left, right, top, bottom). mode 'fit' scales the design
    inside that box and centers it there (so an asymmetric gutter shifts the
    design toward the outer edge). mode 'fill' covers the whole page edge to
    edge and crops the overflow (for bleed pages where art reaches the trim).
    """
    cw, ch = canvas_px
    canvas = Image.new("L", (cw, ch), 255)
    src = design.convert("L")

    if mode == "fill":
        scale = max(cw / src.width, ch / src.height)
        new = src.resize(
            (max(1, round(src.width * scale)), max(1, round(src.height * scale))),
            Image.LANCZOS,
        )
        left = (new.width - cw) // 2
        top = (new.height - ch) // 2
        canvas.paste(new.crop((left, top, left + cw, top + ch)), (0, 0))
        return canvas

    # fit inside the (possibly asymmetric) margin box
    ml, mr, mt, mb = margins_px
    box_w = max(1, cw - ml - mr)
    box_h = max(1, ch - mt - mb)
    scale = min(box_w / src.width, box_h / src.height)
    new = src.resize(
        (max(1, round(src.width * scale)), max(1, round(src.height * scale))),
        Image.LANCZOS,
    )
    off_x = ml + (box_w - new.width) // 2
    off_y = mt + (box_h - new.height) // 2
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
    gutter: bool = True,
) -> dict:
    """Build the interior PDF and return a small summary dict.

    designs: cleaned black-on-white images, one per page/design.
    single_sided: insert a blank page after each design (coloring-book default).
    bleed: if True, page = trim + bleed and designs fill to the edge.
    gutter: if True (no-bleed only), use a larger binding-side margin that
        alternates left/right by page so nothing is lost in the spine.
    """
    specs = specs or kspecs.load_specs()
    dpi = dpi or kspecs.recommended_dpi(specs)
    mode = mode or ("fill" if bleed else "fit")

    page_w_in, page_h_in = kspecs.page_size_in(specs, trim, bleed)
    page_w_pt, page_h_pt = page_w_in * 72.0, page_h_in * 72.0
    canvas_px = (round(page_w_in * dpi), round(page_h_in * dpi))

    total_pages = len(designs) * (2 if single_sided else 1)
    outer_in = kspecs.min_margin_in(specs, bleed)
    inner_in = max(outer_in, kspecs.gutter_in(specs, total_pages))
    sym_px = round(inner_in * dpi)
    outer_px = round(outer_in * dpi)
    inner_px = round(inner_in * dpi)

    def margins_for(page_no: int):
        # No asymmetry for bleed or when gutter is off: symmetric safe margin.
        if mode == "fill" or not gutter:
            return (sym_px, sym_px, sym_px, sym_px)
        # Recto (odd page) binds on the left, verso (even) on the right.
        if page_no % 2 == 1:
            return (inner_px, outer_px, outer_px, outer_px)
        return (outer_px, inner_px, outer_px, outer_px)

    doc = pymupdf.open()
    rect = pymupdf.Rect(0, 0, page_w_pt, page_h_pt)
    for i, design in enumerate(designs):
        page_no = (2 * i + 1) if single_sided else (i + 1)
        page = doc.new_page(width=page_w_pt, height=page_h_pt)
        canvas = _compose_page_canvas(design, canvas_px, margins_for(page_no), mode)
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
        "gutter": bool(gutter and mode != "fill"),
        "inner_margin_in": round(inner_in, 3),
        "outer_margin_in": round(outer_in, 3),
    }


def load_images(paths: list[str | Path]) -> list[Image.Image]:
    return [Image.open(p) for p in paths]
