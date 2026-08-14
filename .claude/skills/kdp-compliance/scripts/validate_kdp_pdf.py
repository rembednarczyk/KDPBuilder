#!/usr/bin/env python3
"""
KDP coloring-book PDF validator.

Checks a print-ready interior PDF against Amazon KDP requirements:
  - page size (trim vs bleed), consistent across all pages
  - page-count limits for the chosen trim size and paper type
  - effective image resolution (DPI) on content pages
  - grayscale / no color (KDP B&W coloring books are black on white)
  - possible shading or gradients (line art should be pure line art)
  - blank backing pages for single-sided layout (optional)
  - font embedding (if any text is present)
  - encryption (KDP rejects locked PDFs)

Specs come from ../references/kdp_specs.json (single source of truth).

Usage:
  python validate_kdp_pdf.py book.pdf --trim 8.5x11 --paper bw_white
  python validate_kdp_pdf.py book.pdf --trim 8.5x8.5 --bleed on --check-single-sided
  python validate_kdp_pdf.py book.pdf --trim 8.5x11 --json > report.json

Exit code: 0 if no FAIL-level issues, 1 otherwise.
Use --strict to make WARN-level issues fail too (useful in CI).

Dependencies: PyMuPDF (pip install pymupdf). numpy is optional
(pip install numpy) and enables the color / shading / blank-page checks.
"""

import argparse
import json
import os
import sys

try:
    import pymupdf as fitz  # PyMuPDF 1.24+
except ImportError:
    try:
        import fitz  # older PyMuPDF
    except ImportError:
        sys.stderr.write(
            "PyMuPDF is required. Install it with:  pip install pymupdf\n"
        )
        sys.exit(2)

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"
_SEVERITY = {PASS: 0, INFO: 0, WARN: 1, FAIL: 2}


class Report:
    def __init__(self):
        self.checks = []
        self.meta = {}

    def add(self, name, status, message, details=None):
        self.checks.append(
            {"check": name, "status": status, "message": message, "details": details or {}}
        )

    def worst(self):
        return max((_SEVERITY[c["status"]] for c in self.checks), default=0)

    def result(self, strict=False):
        w = self.worst()
        if w >= 2:
            return FAIL
        if w >= 1:
            return FAIL if strict else WARN
        return PASS


def load_specs(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_specs_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "references", "kdp_specs.json"))


# ----------------------------------------------------------------------------
# Per-page data collection (one render pass)
# ----------------------------------------------------------------------------

def collect_page_data(doc, analysis_dpi):
    pages = []
    for i, page in enumerate(doc):
        rect = page.rect
        w_in = rect.width / 72.0
        h_in = rect.height / 72.0
        data = {
            "index": i + 1,
            "w_in": round(w_in, 4),
            "h_in": round(h_in, 4),
            "rotation": page.rotation,
            "main_dpi": None,
            "has_raster": False,
            "colored_frac": None,
            "ink_frac": None,
            "midtone_frac": None,
            "edge_white_frac": None,
        }

        # Effective DPI of the largest placed image (no numpy needed)
        main = _main_image_dpi(page)
        if main is not None:
            data["has_raster"] = True
            data["main_dpi"] = round(min(main["dpi_x"], main["dpi_y"]), 1)
            data["main_area_frac"] = round(main["area_frac"], 3)

        # Pixel statistics (needs numpy)
        if HAVE_NUMPY:
            stats = _pixel_stats(page, analysis_dpi)
            data.update(stats)

        pages.append(data)
    return pages


def _main_image_dpi(page):
    try:
        infos = page.get_image_info(xrefs=True)
    except TypeError:
        infos = page.get_image_info()
    page_area = page.rect.width * page.rect.height
    best = None
    for info in infos:
        bbox = fitz.Rect(info["bbox"])
        w_pt, h_pt = bbox.width, bbox.height
        px_w = info.get("width", 0)
        px_h = info.get("height", 0)
        if w_pt <= 0 or h_pt <= 0 or px_w <= 0 or px_h <= 0:
            continue
        area_frac = (w_pt * h_pt) / page_area if page_area > 0 else 0.0
        cand = {
            "dpi_x": px_w / (w_pt / 72.0),
            "dpi_y": px_h / (h_pt / 72.0),
            "area_frac": area_frac,
        }
        if best is None or cand["area_frac"] > best["area_frac"]:
            best = cand
    return best


def _pixel_stats(page, dpi):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    arr = arr.reshape(pix.height, pix.width, 3).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    total = arr.shape[0] * arr.shape[1]

    ring = max(1, int(round(dpi * 0.02)))  # ~0.02 inch border
    edge = np.concatenate(
        [
            gray[:ring, :].ravel(),
            gray[-ring:, :].ravel(),
            gray[:, :ring].ravel(),
            gray[:, -ring:].ravel(),
        ]
    )
    return {
        "colored_frac": round(float(np.count_nonzero(sat > 25)) / total, 5),
        "ink_frac": round(float(np.count_nonzero(gray < 200)) / total, 5),
        "midtone_frac": round(float(np.count_nonzero((gray >= 30) & (gray <= 225))) / total, 5),
        "edge_white_frac": round(float(np.count_nonzero(edge >= 245)) / edge.size, 5),
    }


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------

def check_encryption(doc, report):
    if getattr(doc, "needs_pass", False):
        report.add("encryption", FAIL,
                   "PDF is password protected. Remove the password before uploading to KDP.")
        return
    if getattr(doc, "is_encrypted", False):
        report.add("encryption", WARN,
                   "PDF has encryption or permission flags set. Export a clean, unprotected PDF for KDP.")
    else:
        report.add("encryption", PASS, "No encryption or password protection.")


def check_dimensions(pages, spec_trim, bleed_mode, tol, report):
    tw, th = spec_trim["w"], spec_trim["h"]
    exp_nb = (tw, th)
    add_w = SPECS["bleed"]["add_to_width"]
    add_h = SPECS["bleed"]["add_to_height"]
    exp_b = (tw + add_w, th + add_h)

    def classify(w, h):
        # returns "no_bleed", "with_bleed", or None; also try swapped (landscape)
        for label, (ew, eh) in (("no_bleed", exp_nb), ("with_bleed", exp_b)):
            if abs(w - ew) <= tol and abs(h - eh) <= tol:
                return label, False
            if abs(w - eh) <= tol and abs(h - ew) <= tol:
                return label, True  # swapped / landscape
        return None, False

    modes = {}
    swapped_any = False
    offenders = []
    for p in pages:
        label, swapped = classify(p["w_in"], p["h_in"])
        p["size_mode"] = label
        if label is None:
            offenders.append({"page": p["index"], "size_in": [p["w_in"], p["h_in"]]})
        else:
            modes[label] = modes.get(label, 0) + 1
            swapped_any = swapped_any or swapped

    details = {
        "trim": [tw, th],
        "expected_no_bleed_in": [round(exp_nb[0], 3), round(exp_nb[1], 3)],
        "expected_with_bleed_in": [round(exp_b[0], 3), round(exp_b[1], 3)],
        "tolerance_in": tol,
        "page_modes": modes,
    }
    if offenders:
        details["mismatched_pages"] = offenders[:15]
        details["mismatched_count"] = len(offenders)
        report.add("page_size", FAIL,
                   "%d page(s) do not match the trim or bleed size for %s x %s." % (len(offenders), tw, th),
                   details)
        return None
    if len(modes) > 1:
        report.add("page_size", FAIL,
                   "Pages mix bleed and no-bleed sizes. KDP needs one consistent setup for the whole file.",
                   details)
        return None

    detected = next(iter(modes))
    if swapped_any:
        report.add("page_size", WARN,
                   "Pages match %s but in landscape orientation. Confirm this is intended." % detected,
                   details)
    if bleed_mode in ("on", "off"):
        want = "with_bleed" if bleed_mode == "on" else "no_bleed"
        if detected != want:
            report.add("page_size", FAIL,
                       "You asked for bleed=%s but the file is set up as %s." % (bleed_mode, detected),
                       details)
            return detected
    report.add("page_size", PASS,
               "All pages are %s at %s x %s inch." % (detected, tw, th), details)
    return detected


def check_page_count(doc, spec_trim, paper, single_sided, report):
    n = doc.page_count
    limits = spec_trim["page_counts"].get(paper)
    details = {"pages": n, "paper": paper, "limits": limits}
    if limits is None:
        report.add("page_count", WARN,
                   "Paper type '%s' is not available for this trim size." % paper, details)
    else:
        lo, hi = limits
        if n < lo or n > hi:
            report.add("page_count", FAIL,
                       "Page count %d is outside the allowed range %d-%d for %s on %s." % (n, lo, hi, _trim_label(spec_trim), paper),
                       details)
        else:
            report.add("page_count", PASS,
                       "Page count %d is within the allowed range %d-%d." % (n, lo, hi), details)
    if n % 2 != 0:
        report.add("page_count_parity", WARN,
                   "Page count is odd (%d). KDP interiors are usually even; single-sided coloring books should be even." % n)
    elif single_sided:
        report.add("page_count_parity", INFO,
                   "Even page count (%d) -> about %d designs if single-sided with blank backs." % (n, n // 2))


def check_dpi(pages, threshold, report):
    content = [p for p in pages if p.get("has_raster")]
    vector_pages = [p["index"] for p in pages
                    if not p.get("has_raster") and (p.get("ink_frac") or 0) > 0.003]
    if not content:
        if vector_pages:
            report.add("resolution", INFO,
                       "No raster images on content pages (looks like vector line art, which is resolution independent).")
        else:
            report.add("resolution", INFO, "No raster content pages found to measure.")
        return
    below = [{"page": p["index"], "dpi": p["main_dpi"]} for p in content
             if p["main_dpi"] is not None and p["main_dpi"] < threshold]
    min_dpi = min(p["main_dpi"] for p in content if p["main_dpi"] is not None)
    details = {"threshold_dpi": threshold, "min_effective_dpi": min_dpi,
               "content_pages_measured": len(content)}
    if below:
        details["pages_below_threshold"] = below[:15]
        details["below_count"] = len(below)
        report.add("resolution", WARN,
                   "%d content page(s) are below %d DPI (min %.0f). Low-resolution line art prints blurry." % (len(below), threshold, min_dpi),
                   details)
    else:
        report.add("resolution", PASS,
                   "All measured content pages are at or above %d DPI (min %.0f)." % (threshold, min_dpi),
                   details)
    if vector_pages:
        report.add("resolution_vector", INFO,
                   "%d page(s) have no raster image (vector line art)." % len(vector_pages))


def check_color(pages, paper, report):
    if not HAVE_NUMPY:
        report.add("grayscale", INFO, "Skipped (install numpy to check for color).")
        return
    if paper in ("standard_color", "premium_color"):
        report.add("grayscale", INFO, "Color paper selected; grayscale check skipped.")
        return
    colored = [{"page": p["index"], "colored_frac": p["colored_frac"]} for p in pages
               if p.get("colored_frac") is not None and p["colored_frac"] > 0.005]
    if colored:
        report.add("grayscale", WARN,
                   "%d page(s) contain color. A B&W coloring book should be pure black on white." % len(colored),
                   {"colored_pages": colored[:15]})
    else:
        report.add("grayscale", PASS, "No meaningful color detected; pages are grayscale.")


def check_shading(pages, report):
    if not HAVE_NUMPY:
        report.add("line_art_purity", INFO, "Skipped (install numpy to check for shading).")
        return
    threshold = 0.15
    shaded = [{"page": p["index"], "midtone_frac": p["midtone_frac"]} for p in pages
              if p.get("midtone_frac") is not None and p["midtone_frac"] > threshold]
    if shaded:
        report.add("line_art_purity", WARN,
                   "%d page(s) have many mid-gray pixels, which suggests shading or gradients. Line art should be pure black lines on white." % len(shaded),
                   {"threshold_midtone_frac": threshold, "pages": shaded[:15]})
    else:
        report.add("line_art_purity", PASS,
                   "Little mid-tone content; pages look like clean line art.")


def check_single_sided(pages, blank_max, report):
    if not HAVE_NUMPY:
        report.add("single_sided", INFO, "Skipped (install numpy to check blank backing pages).")
        return
    n = len(pages)
    blanks = [p["index"] for p in pages if p.get("ink_frac") is not None and p["ink_frac"] <= blank_max]
    content = [p["index"] for p in pages if p["index"] not in blanks]
    blank_frac = len(blanks) / n if n else 0
    details = {"blank_pages": len(blanks), "content_pages": len(content),
               "blank_fraction": round(blank_frac, 3)}
    # A single-sided layout has content clustered on one parity, blanks on the other.
    odd_content = sum(1 for i in content if i % 2 == 1)
    even_content = len(content) - odd_content
    clean_alternation = (min(odd_content, even_content) <= max(1, int(0.1 * len(content)))) if content else False
    details["content_on_odd"] = odd_content
    details["content_on_even"] = even_content
    if blank_frac < 0.35:
        report.add("single_sided", WARN,
                   "Only %.0f%% of pages are blank. Single-sided coloring books need a blank backing page per design (~50%% blank)." % (100 * blank_frac),
                   details)
    elif not clean_alternation:
        report.add("single_sided", WARN,
                   "Blank and content pages do not alternate cleanly. Check that each design has a blank page behind it.",
                   details)
    else:
        report.add("single_sided", PASS,
                   "Content and blank backing pages alternate as expected (~%.0f%% blank)." % (100 * blank_frac),
                   details)


def check_bleed_edges(pages, detected_mode, report):
    if not HAVE_NUMPY or detected_mode != "with_bleed":
        return
    suspects = [p["index"] for p in pages
                if p.get("edge_white_frac") is not None
                and p.get("ink_frac") is not None
                and p["ink_frac"] > 0.02
                and p["edge_white_frac"] >= 0.98]
    if suspects:
        report.add("bleed_edges", WARN,
                   "%d page(s) with art have a white edge, so the image may not reach the trim edge. Extend art into the bleed." % len(suspects),
                   {"pages": suspects[:15]})
    else:
        report.add("bleed_edges", PASS, "Art on bleed pages reaches the page edges.")


def check_fonts(doc, report):
    seen = {}
    for page in doc:
        for f in page.get_fonts(full=True):
            xref = f[0]
            if xref in seen:
                continue
            basefont = f[3]
            embedded = True
            try:
                buf = doc.extract_font(xref)
                # extract_font returns (basefont, ext, type, buffer)
                embedded = bool(buf and len(buf) >= 4 and buf[3])
            except Exception:
                embedded = True  # do not fail on inspection errors
            seen[xref] = {"font": basefont, "embedded": embedded}
    if not seen:
        report.add("fonts", INFO, "No fonts found (image-only interior).")
        return
    not_embedded = [v["font"] for v in seen.values() if not v["embedded"]]
    if not_embedded:
        report.add("fonts", WARN,
                   "%d font(s) are not embedded: %s. Embed all fonts before uploading." % (len(not_embedded), ", ".join(sorted(set(not_embedded)))),
                   {"not_embedded": sorted(set(not_embedded))})
    else:
        report.add("fonts", PASS, "All %d font(s) are embedded." % len(seen))


# ----------------------------------------------------------------------------
# Helpers and reporting
# ----------------------------------------------------------------------------

def _trim_label(spec_trim):
    return "%sx%s" % (spec_trim["w"], spec_trim["h"])


def print_report(report, strict):
    tag = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL", INFO: "INFO"}
    print("KDP coloring-book PDF validation")
    print("=" * 60)
    for k, v in report.meta.items():
        print("%-16s %s" % (k + ":", v))
    print("-" * 60)
    for c in report.checks:
        print("[%s] %-18s %s" % (tag[c["status"]], c["check"], c["message"]))
    print("-" * 60)
    result = report.result(strict)
    print("RESULT: %s" % result)
    if not HAVE_NUMPY:
        print("Note: numpy not installed; color, shading, blank-page and bleed-edge checks were skipped.")
    print("Manual checks still required: line weight (min 0.75 pt), safe zone for any text,")
    print("closed contours, and a printed proof copy. See SKILL.md.")


def main():
    ap = argparse.ArgumentParser(description="Validate a coloring-book interior PDF against KDP specs.")
    ap.add_argument("pdf", help="Path to the interior PDF")
    ap.add_argument("--trim", required=True, help="Trim size key, e.g. 8.5x11 or 8.5x8.5")
    ap.add_argument("--paper", default="bw_white",
                    help="Paper type: bw_white, bw_cream, bw_groundwood, standard_color, premium_color")
    ap.add_argument("--bleed", choices=["auto", "on", "off"], default="auto",
                    help="Expected bleed setup (default: auto-detect)")
    ap.add_argument("--dpi-threshold", type=float, default=None, help="Minimum effective DPI (default from specs)")
    ap.add_argument("--tolerance", type=float, default=0.02, help="Page-size tolerance in inches (default 0.02)")
    ap.add_argument("--analysis-dpi", type=int, default=100, help="Render DPI for pixel checks (default 100)")
    ap.add_argument("--check-single-sided", action="store_true", help="Check blank backing pages")
    ap.add_argument("--specs", default=None, help="Path to kdp_specs.json (default: bundled)")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    ap.add_argument("--json", action="store_true", help="Print the report as JSON")
    args = ap.parse_args()

    global SPECS
    SPECS = load_specs(args.specs or default_specs_path())

    if args.trim not in SPECS["trim_sizes"]:
        sys.stderr.write("Unknown trim '%s'. Known: %s\n" % (args.trim, ", ".join(SPECS["trim_sizes"])))
        sys.exit(2)
    spec_trim = SPECS["trim_sizes"][args.trim]
    dpi_threshold = args.dpi_threshold or SPECS["resolution"]["recommended_min_dpi"]
    blank_max = SPECS["coloring_book"]["blank_page_max_ink_fraction"]

    if not os.path.exists(args.pdf):
        sys.stderr.write("File not found: %s\n" % args.pdf)
        sys.exit(2)

    report = Report()
    try:
        doc = fitz.open(args.pdf)
    except Exception as e:
        sys.stderr.write("Could not open PDF: %s\n" % e)
        sys.exit(2)

    report.meta = {
        "file": os.path.basename(args.pdf),
        "trim": args.trim,
        "paper": args.paper,
        "pages": doc.page_count,
    }

    check_encryption(doc, report)
    if getattr(doc, "needs_pass", False):
        _emit(report, args)
        sys.exit(1)

    pages = collect_page_data(doc, args.analysis_dpi)
    detected = check_dimensions(pages, spec_trim, args.bleed, args.tolerance, report)
    check_page_count(doc, spec_trim, args.paper, args.check_single_sided, report)
    check_dpi(pages, dpi_threshold, report)
    check_color(pages, args.paper, report)
    check_shading(pages, report)
    check_bleed_edges(pages, detected, report)
    if args.check_single_sided:
        check_single_sided(pages, blank_max, report)
    check_fonts(doc, report)

    _emit(report, args, pages)
    sys.exit(0 if report.result(args.strict) != FAIL else 1)


def _emit(report, args, pages=None):
    if args.json:
        out = {"meta": report.meta, "result": report.result(args.strict), "checks": report.checks}
        if pages is not None:
            out["pages"] = pages
        print(json.dumps(out, indent=2))
    else:
        print_report(report, args.strict)


if __name__ == "__main__":
    main()
