"""Pixel-level scan of a finished interior PDF.

Goes deeper than the compliance validator by analysing the actual pixels of
each page's embedded image (not a re-render, which would add anti-aliasing):

  - purity: pixels are truly pure black and white, no leftover gray
  - line weight: thinnest stroke width in points, via a distance transform
  - stray marks: tiny isolated ink specks that read as dirt
  - margin: how much ink sits inside the outer safe margin
  - regions: count of enclosed white areas, a weak proxy for closed contours

Raster pages are analysed from the embedded image at its native resolution.
Vector pages are rendered at --render-dpi as a fallback.

Depends on PyMuPDF, numpy and scipy.
"""

from __future__ import annotations

import io
import json
import os
import sys

import numpy as np
import pymupdf
from scipy import ndimage

from . import specs as kspecs

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"
_SEV = {PASS: 0, INFO: 0, WARN: 1, FAIL: 2}


def _largest_image_xref(page):
    try:
        infos = page.get_image_info(xrefs=True)
    except TypeError:
        infos = page.get_image_info()
    best = None
    for info in infos:
        bbox = pymupdf.Rect(info["bbox"])
        area = bbox.width * bbox.height
        if best is None or area > best[0]:
            best = (area, info)
    return best[1] if best else None


def _page_gray(doc, page, render_dpi):
    """Return (gray uint8 array, dpi) for a page.

    Prefers the embedded image at native resolution; falls back to a render.
    """
    info = _largest_image_xref(page)
    if info and info.get("xref"):
        try:
            ext = doc.extract_image(info["xref"])
            img = _pil_gray(ext["image"])
            bbox = pymupdf.Rect(info["bbox"])
            w_in = bbox.width / 72.0
            h_in = bbox.height / 72.0
            dpi = min(img.shape[1] / w_in, img.shape[0] / h_in) if w_in and h_in else render_dpi
            return img, float(dpi)
        except Exception:
            pass
    pix = page.get_pixmap(dpi=render_dpi, colorspace=pymupdf.csGRAY, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return arr.copy(), float(render_dpi)


def _pil_gray(data: bytes) -> np.ndarray:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    return np.asarray(img.convert("L"), dtype=np.uint8)


def _line_widths_pt(dt: np.ndarray, dpi: float):
    """Stroke widths in points along line centerlines, via distance transform."""
    if dt.max() == 0:
        return None
    ridge = (ndimage.maximum_filter(dt, size=3) == dt) & (dt > 0)
    half = dt[ridge]
    if half.size == 0:
        return None
    widths_px = 2.0 * half
    to_pt = 72.0 / dpi
    return {
        "min_pt": float(np.min(widths_px) * to_pt),
        "p5_pt": float(np.percentile(widths_px, 5) * to_pt),
        "median_pt": float(np.median(widths_px) * to_pt),
    }


def _scan_page(gray, dpi, index, min_line_pt, margin_in, gray_tol=0.004, speck_in=0.01):
    h, w = gray.shape
    total = h * w
    ink = gray < 128
    # purity: mid-gray pixels that are NOT next to a black edge. Anti-aliasing
    # from scaling leaves a thin gray ring around lines and is expected; real
    # shading or gradients shows as gray away from edges.
    gray_mask = (gray >= 24) & (gray <= 232)
    edge_zone = ndimage.binary_dilation(ink, iterations=2) & ~ink
    interior_gray = int(np.count_nonzero(gray_mask & ~edge_zone))
    gray_frac = interior_gray / total
    edge_gray_frac = int(np.count_nonzero(gray_mask & edge_zone)) / total

    dt = ndimage.distance_transform_edt(ink) if ink.any() else np.zeros_like(gray, dtype=float)
    widths = _line_widths_pt(dt, dpi)

    # Solid fills: ink deep inside a region thicker than a normal outline. Bold
    # line art should have almost none; a filled blob (a bubble gone solid) or an
    # intended solid (kawaii eyes) both show here, so this flags spots to review.
    solid_half_px = 0.03 * dpi  # regions thicker than ~0.06 inch
    ink_px = max(1, int(ink.sum()))
    solid_frac = int(np.count_nonzero(dt > solid_half_px)) / ink_px

    # stray specks: tiny isolated ink components
    speck_area = max(1, int((speck_in * dpi) ** 2))
    lbl, n = ndimage.label(ink)
    specks = 0
    if n:
        sizes = np.bincount(lbl.ravel())
        sizes[0] = 0
        specks = int(np.count_nonzero((sizes > 0) & (sizes < speck_area)))

    # ink inside the outer safe margin band
    m = max(1, int(margin_in * dpi))
    band = np.zeros_like(ink)
    band[:m, :] = band[-m:, :] = band[:, :m] = band[:, -m:] = True
    ink_in_band = int(np.count_nonzero(ink & band))
    band_ink_frac = ink_in_band / max(1, int(np.count_nonzero(ink)))

    # enclosed white regions (weak closed-contour proxy)
    paper = ~ink
    plbl, pn = ndimage.label(paper)
    border_labels = set(plbl[0, :]) | set(plbl[-1, :]) | set(plbl[:, 0]) | set(plbl[:, -1])
    border_labels.discard(0)
    enclosed = int(pn - len(border_labels))

    return {
        "page": index,
        "px": [w, h],
        "dpi": round(dpi, 1),
        "gray_frac": round(gray_frac, 5),
        "edge_gray_frac": round(edge_gray_frac, 5),
        "solid_frac": round(solid_frac, 4),
        "line_widths_pt": widths,
        "specks": specks,
        "band_ink_frac": round(band_ink_frac, 4),
        "enclosed_regions": enclosed,
    }


def scan_pdf(path, trim, paper="bw_white", bleed=False, render_dpi=200,
             min_line_pt=None, specs=None):
    specs = specs or kspecs.load_specs()
    min_line_pt = min_line_pt or float(specs["line_art"]["min_line_weight_pt"])
    margin_in = kspecs.min_margin_in(specs, bleed)

    doc = pymupdf.open(path)
    pages = []
    for i, page in enumerate(doc):
        gray, dpi = _page_gray(doc, page, render_dpi)
        pages.append(_scan_page(gray, dpi, i + 1, min_line_pt, margin_in))
    doc.close()

    # Aggregate into checks.
    checks = []

    def add(name, status, msg, details=None):
        checks.append({"check": name, "status": status, "message": msg, "details": details or {}})

    impure = [p["page"] for p in pages if p["gray_frac"] > 0.01]
    if impure:
        add("purity", WARN,
            "%d page(s) have many gray pixels; lines should be pure black on white." % len(impure),
            {"pages": impure[:15]})
    else:
        add("purity", PASS, "Pages are pure black and white.")

    measured = [p for p in pages if p["line_widths_pt"]]
    thin = [{"page": p["page"], "p5_pt": round(p["line_widths_pt"]["p5_pt"], 2)}
            for p in measured if p["line_widths_pt"]["p5_pt"] < min_line_pt]
    if thin:
        add("line_weight", WARN,
            "%d page(s) have thin lines below %.2f pt (5th percentile)." % (len(thin), min_line_pt),
            {"min_line_pt": min_line_pt, "pages": thin[:15]})
    elif measured:
        add("line_weight", PASS, "Thinnest lines are at or above %.2f pt on all pages." % min_line_pt)
    else:
        add("line_weight", INFO, "No ink measured for line weight.")

    speckly = [{"page": p["page"], "specks": p["specks"]} for p in pages if p["specks"] > 20]
    if speckly:
        add("stray_marks", WARN,
            "%d page(s) have many tiny ink specks; check for stray marks." % len(speckly),
            {"pages": speckly[:15]})
    else:
        add("stray_marks", PASS, "No unusual speck counts.")

    heavy_margin = [{"page": p["page"], "band_ink_frac": p["band_ink_frac"]}
                    for p in pages if p["band_ink_frac"] > 0.25]
    if heavy_margin:
        add("safe_margin", WARN,
            "%d page(s) have a lot of ink inside the outer margin; check the safe zone." % len(heavy_margin),
            {"pages": heavy_margin[:15]})
    else:
        add("safe_margin", PASS, "Little ink inside the outer margin.")

    # Solid-fill hint: cannot tell an artifact blob from intended kawaii eyes,
    # so this only points a human at the pages with the most solid ink.
    ranked = sorted((p for p in pages if p["line_widths_pt"]),
                    key=lambda p: p.get("solid_frac", 0), reverse=True)
    worst_solid = [{"page": p["page"], "solid_frac": p["solid_frac"]} for p in ranked[:5]]
    add("solid_fill", INFO,
        "Pages with the most solid ink (review for filled-blob artifacts; note kawaii eyes also count).",
        {"top_pages": worst_solid})

    open_pages = [p["page"] for p in pages if p.get("enclosed_regions", 0) == 0
                  and (p["line_widths_pt"] is not None)]
    add("closed_contours", INFO,
        "Enclosed white regions counted per page (weak proxy). %d page(s) show none." % len(open_pages),
        {"experimental": True, "pages_without_enclosed_regions": open_pages[:15]})

    worst = max((_SEV[c["status"]] for c in checks), default=0)
    result = FAIL if worst >= 2 else (WARN if worst >= 1 else PASS)
    return {"meta": {"file": os.path.basename(path), "trim": trim, "pages": len(pages)},
            "result": result, "checks": checks, "page_data": pages}


def print_report(report):
    tag = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL", INFO: "INFO"}
    print("KDP pixel-level scan")
    print("=" * 60)
    for k, v in report["meta"].items():
        print("%-12s %s" % (k + ":", v))
    print("-" * 60)
    for c in report["checks"]:
        print("[%s] %-16s %s" % (tag[c["status"]], c["check"], c["message"]))
    print("-" * 60)
    print("RESULT: %s" % report["result"])
    print("Note: closed-contour check is experimental; still review pages by hand.")
