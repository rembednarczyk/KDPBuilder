import pytest
import pymupdf
from PIL import Image

from kdpbuilder import cover as kcover
from kdpbuilder import specs as kspecs


@pytest.fixture(scope="module")
def specs():
    return kspecs.load_specs()


@pytest.fixture
def front():
    # simple color art stand-in
    img = Image.new("RGB", (1200, 1600), (120, 200, 240))
    return img


def test_spine_width(specs):
    # 80 pages on white = 80 * 0.002252
    assert kspecs.spine_width_in(specs, 80, "bw_white") == pytest.approx(0.18016, abs=1e-5)


def test_full_cover_size(specs):
    w, h = kspecs.full_cover_size_in(specs, "8.5x11", 80, "bw_white")
    # width = 0.25 + 17 + 0.18016 ; height = 11.25
    assert w == pytest.approx(17.43016, abs=1e-4)
    assert h == pytest.approx(11.25, abs=1e-6)


def test_spine_text_threshold(specs):
    assert kspecs.spine_text_allowed(specs, 80) is True
    assert kspecs.spine_text_allowed(specs, 40) is False


def test_regions_ordered(specs):
    reg = kspecs.cover_regions_in(specs, "8.5x11", 80, "bw_white")
    assert reg["back_x0"] < reg["spine_x0"] < reg["front_x0"] < reg["front_x1"]
    assert reg["spine_w_in"] == pytest.approx(0.18016, abs=1e-5)


def test_build_cover_page_size(tmp_path, specs, front):
    out = tmp_path / "cover.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", subtitle="40 uroczych wzorow", author="Test Author",
        blurb="Wielka kolorowanka dla dzieci.", dpi=150, specs=specs,
    )
    assert summary["spine_text"] == "included"
    doc = pymupdf.open(out)
    assert doc.page_count == 1
    page = doc[0]
    assert page.rect.width / 72.0 == pytest.approx(17.43016, abs=0.02)
    assert page.rect.height / 72.0 == pytest.approx(11.25, abs=0.02)
    doc.close()


def test_thin_book_omits_spine_text(tmp_path, specs, front):
    out = tmp_path / "cover_thin.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=40, paper="bw_white",
        title="Aksolotki", dpi=150, specs=specs,
    )
    assert "omitted" in summary["spine_text"]


def test_build_cover_smaller_dpi_runs(tmp_path, specs, front):
    # Polish diacritics must render without error using the default font.
    out = tmp_path / "cover_pl.pdf"
    kcover.build_cover(
        front, out, trim="8.5x8.5", page_count=88, paper="bw_white",
        title="Zażółć gęślą jaźń", author="Ćma Żółć", blurb="Grube kontury, duże pola.",
        dpi=120, specs=specs,
    )
    assert out.exists()
