import pytest

from kdpbuilder import specs as kspecs


@pytest.fixture(scope="module")
def specs():
    return kspecs.load_specs()


def test_specs_load(specs):
    assert "trim_sizes" in specs
    assert "8.5x11" in specs["trim_sizes"]


def test_page_size_no_bleed(specs):
    w, h = kspecs.page_size_in(specs, "8.5x11", bleed=False)
    assert (w, h) == (8.5, 11.0)


def test_page_size_with_bleed(specs):
    w, h = kspecs.page_size_in(specs, "8.5x11", bleed=True)
    # KDP: +0.125 width, +0.25 height
    assert round(w, 3) == 8.625
    assert round(h, 3) == 11.25


def test_unknown_trim_raises(specs):
    with pytest.raises(kspecs.SpecError):
        kspecs.trim(specs, "9x9")


def test_page_count_limits(specs):
    lo, hi = kspecs.page_count_limits(specs, "8.5x11", "bw_white")
    assert lo == 24 and hi == 590


def test_gutter_grows_with_pages(specs):
    assert kspecs.gutter_in(specs, 100) <= kspecs.gutter_in(specs, 600)


def test_recommended_dpi(specs):
    assert kspecs.recommended_dpi(specs) == 300
