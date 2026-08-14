import io

import pymupdf
import pytest
from PIL import Image, ImageDraw

from kdpbuilder import scan as kscan

# 8.5 x 11 at 300 DPI so 1 px = 0.24 pt (lets us test the 0.75 pt threshold).
PW, PH = 2550, 3300


def _make_pdf(tmp_path, img, name="p.pdf"):
    doc = pymupdf.open()
    W, H = 8.5 * 72, 11.0 * 72
    page = doc.new_page(width=W, height=H)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(0, 0, W, H), stream=buf.getvalue())
    out = tmp_path / name
    doc.save(str(out))
    doc.close()
    return out


def _blank():
    return Image.new("RGB", (PW, PH), (255, 255, 255))


def _status(report, check):
    return next(c["status"] for c in report["checks"] if c["check"] == check)


def test_thick_line_passes_line_weight(tmp_path):
    img = _blank()
    d = ImageDraw.Draw(img)
    d.ellipse((600, 800, 1900, 2400), outline=(0, 0, 0), width=14)  # ~3.4 pt
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status(report, "line_weight") == "PASS"
    assert _status(report, "purity") == "PASS"


def test_thin_line_flagged(tmp_path):
    img = _blank()
    d = ImageDraw.Draw(img)
    d.line((300, 300, 2200, 300), fill=(0, 0, 0), width=2)  # ~0.48 pt
    d.line((300, 500, 2200, 500), fill=(0, 0, 0), width=2)
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status(report, "line_weight") == "WARN"


def test_gray_patch_flagged(tmp_path):
    img = _blank()
    ImageDraw.Draw(img).rectangle((800, 800, 1800, 1800), fill=(128, 128, 128))
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status(report, "purity") == "WARN"


def test_specks_flagged(tmp_path):
    img = _blank()
    d = ImageDraw.Draw(img)
    # one bold shape plus many tiny specks
    d.ellipse((900, 1200, 1600, 1900), outline=(0, 0, 0), width=14)
    for i in range(30):
        x, y = 200 + i * 60, 200
        d.point((x, y), fill=(0, 0, 0))
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status(report, "stray_marks") == "WARN"


def _status_of(report, check):
    return next(c["status"] for c in report["checks"] if c["check"] == check)


def test_closed_box_passes_contours(tmp_path):
    img = _blank()
    d = ImageDraw.Draw(img)
    d.rectangle((700, 900, 1800, 2200), outline=(0, 0, 0), width=16)  # thick, sealed
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status_of(report, "closed_contours") == "PASS"


def test_thin_wall_flagged_as_leak(tmp_path):
    img = _blank()
    d = ImageDraw.Draw(img)
    # three thick walls, one very thin wall: the interior is enclosed but the
    # thin wall is a weak seal that opens under a 1 px erosion.
    x0, y0, x1, y1 = 700, 900, 1800, 2200
    d.line((x0, y0, x1, y0), fill=(0, 0, 0), width=16)  # top
    d.line((x0, y0, x0, y1), fill=(0, 0, 0), width=16)  # left
    d.line((x1, y0, x1, y1), fill=(0, 0, 0), width=16)  # right
    d.line((x0, y1, x1, y1), fill=(0, 0, 0), width=1)   # bottom, thin
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    assert _status_of(report, "closed_contours") == "WARN"


def test_report_structure(tmp_path):
    img = _blank()
    ImageDraw.Draw(img).ellipse((700, 900, 1800, 2200), outline=(0, 0, 0), width=14)
    pdf = _make_pdf(tmp_path, img)
    report = kscan.scan_pdf(pdf, trim="8.5x11")
    names = {c["check"] for c in report["checks"]}
    assert {"purity", "line_weight", "stray_marks", "safe_margin", "closed_contours"} <= names
    assert report["meta"]["pages"] == 1
    assert report["result"] in ("PASS", "WARN", "FAIL")
