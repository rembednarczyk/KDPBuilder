import pytest
import pymupdf
from PIL import Image, ImageDraw

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


def test_wraparound_with_thumbnails(tmp_path, specs, front):
    thumbs = [Image.new("L", (600, 800), 255) for _ in range(6)]
    for t in thumbs:
        ImageDraw.Draw(t).ellipse((100, 150, 500, 650), outline=0, width=8)
    out = tmp_path / "wrap.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", subtitle="Kolorowanka dla dzieci", author="Kolorowe Skarby",
        blurb="Wielka kolorowanka.", thumbnails=thumbs, count_badge="40 wzorow",
        wrap=True, dpi=120, specs=specs,
    )
    assert summary["wrap"] is True
    assert summary["thumbnails"] == 6
    assert pymupdf.open(out).page_count == 1


def test_banner_asset_slot(tmp_path, specs, front):
    # a decoration asset dropped into the subtitle slot is used instead of the
    # procedural banner; text still composits on top.
    asset = Image.new("RGBA", (800, 200), (200, 40, 120, 255))
    out = tmp_path / "asset.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", subtitle="Kolorowanka dla dzieci",
        banner_assets={"subtitle": asset}, dpi=120, specs=specs,
    )
    assert summary["spine_text"] == "included"
    assert pymupdf.open(out).page_count == 1


def test_title_asset_replaces_script_title(tmp_path, specs, front):
    # a baked title graphic is placed as-is; the summary marks the title source
    # as 'asset', and the string title is still used for the spine.
    title_img = Image.new("RGBA", (1400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(title_img).text((40, 120), "AKSOLOTKI", fill=(255, 200, 0, 255))
    out = tmp_path / "title_asset.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", author="Kolorowe Skarby",
        title_asset=title_img, dpi=120, specs=specs,
    )
    assert summary["title"] == "asset"
    assert summary["spine_text"] == "included"  # spine still built from the string
    assert pymupdf.open(out).page_count == 1


def test_default_title_is_script(tmp_path, specs, front):
    out = tmp_path / "title_script.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", dpi=120, specs=specs,
    )
    assert summary["title"] == "script"


def test_logo_placed(tmp_path, specs, front):
    logo = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rounded_rectangle((10, 10, 390, 190), radius=30, fill=(255, 0, 0, 255))
    out = tmp_path / "logo.pdf"
    summary = kcover.build_cover(
        front, out, trim="8.5x11", page_count=80, paper="bw_white",
        title="Aksolotki", logo=logo, logo_where="back", dpi=120, specs=specs,
    )
    assert summary["logo"] is True
    assert pymupdf.open(out).page_count == 1


def test_build_cover_smaller_dpi_runs(tmp_path, specs, front):
    # Polish diacritics must render without error using the default font.
    out = tmp_path / "cover_pl.pdf"
    kcover.build_cover(
        front, out, trim="8.5x8.5", page_count=88, paper="bw_white",
        title="Zażółć gęślą jaźń", author="Ćma Żółć", blurb="Grube kontury, duże pola.",
        dpi=120, specs=specs,
    )
    assert out.exists()
