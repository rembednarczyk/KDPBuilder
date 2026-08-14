import subprocess
import sys
from pathlib import Path

import pymupdf

from kdpbuilder import assemble as kassemble
from kdpbuilder import imageprep


def _validator():
    root = Path(__file__).resolve().parent.parent
    return root / ".claude" / "skills" / "kdp-compliance" / "scripts" / "validate_kdp_pdf.py"


def test_build_interior_page_geometry(tmp_path, designs):
    cleaned = [imageprep.clean(d) for d in designs]
    out = tmp_path / "interior.pdf"
    summary = kassemble.build_interior(cleaned, out, trim="8.5x11", single_sided=True)
    assert summary["pages"] == len(designs) * 2
    doc = pymupdf.open(out)
    assert doc.page_count == len(designs) * 2
    for page in doc:
        w_in = page.rect.width / 72.0
        h_in = page.rect.height / 72.0
        assert abs(w_in - 8.5) < 0.01
        assert abs(h_in - 11.0) < 0.01
    doc.close()


def test_blank_backs_present(tmp_path, designs):
    cleaned = [imageprep.clean(d) for d in designs]
    out = tmp_path / "interior.pdf"
    kassemble.build_interior(cleaned, out, trim="8.5x11", single_sided=True)
    doc = pymupdf.open(out)
    # odd (1-based) pages carry designs, even pages are blank backs
    for i, page in enumerate(doc):
        images = page.get_images()
        if i % 2 == 0:
            assert images, "design page %d should hold an image" % (i + 1)
        else:
            assert not images, "backing page %d should be blank" % (i + 1)
    doc.close()


def test_bleed_page_size(tmp_path, designs):
    cleaned = [imageprep.clean(d) for d in designs]
    out = tmp_path / "bleed.pdf"
    kassemble.build_interior(cleaned, out, trim="8.5x11", bleed=True, single_sided=False)
    doc = pymupdf.open(out)
    page = doc[0]
    assert abs(page.rect.width / 72.0 - 8.625) < 0.01
    assert abs(page.rect.height / 72.0 - 11.25) < 0.01
    doc.close()


def test_effective_dpi_is_300(tmp_path, designs):
    cleaned = [imageprep.clean(d) for d in designs]
    out = tmp_path / "interior.pdf"
    kassemble.build_interior(cleaned, out, trim="8.5x11", dpi=300, single_sided=True)
    doc = pymupdf.open(out)
    page = doc[0]
    info = page.get_image_info()[0]
    # full-page canvas at 300 dpi -> width px / width in ~= 300
    dpi_x = info["width"] / (page.rect.width / 72.0)
    assert 290 <= dpi_x <= 310
    doc.close()


def test_end_to_end_validates_pass(tmp_path, designs):
    """A book built by the pipeline must pass the kdp-compliance validator."""
    cleaned = [imageprep.clean(d) for d in designs]
    # pad to KDP minimum of 24 pages (12 designs single-sided)
    while len(cleaned) < 12:
        cleaned.append(cleaned[0].copy())
    out = tmp_path / "interior.pdf"
    kassemble.build_interior(cleaned, out, trim="8.5x11", single_sided=True)
    script = _validator()
    if not script.exists():
        return
    res = subprocess.run(
        [sys.executable, str(script), str(out), "--trim", "8.5x11",
         "--paper", "bw_white", "--check-single-sided"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
