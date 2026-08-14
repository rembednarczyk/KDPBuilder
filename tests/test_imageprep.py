from kdpbuilder import imageprep


def test_to_pure_bw_is_binary(line_art):
    import numpy as np

    out = imageprep.to_pure_bw(line_art)
    values = set(np.unique(np.asarray(out.convert("L"))).tolist())
    assert values <= {0, 255}


def test_cleanup_removes_midtones(line_art):
    before = imageprep.midtone_fraction(line_art)
    after = imageprep.midtone_fraction(imageprep.to_pure_bw(line_art))
    assert before > 0.0
    assert after == 0.0


def test_cleanup_removes_color():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 400), (255, 255, 255))
    ImageDraw.Draw(img).ellipse((50, 50, 350, 350), outline=(200, 20, 20), width=12)
    assert imageprep.color_fraction(img) > 0.0
    cleaned = imageprep.clean(img)
    assert imageprep.color_fraction(cleaned) == 0.0


def test_thicken_adds_ink(line_art):
    bw = imageprep.to_pure_bw(line_art)
    import numpy as np

    thin_ink = np.count_nonzero(np.asarray(bw) < 128)
    thick = imageprep.thicken_lines(bw, amount=2)
    thick_ink = np.count_nonzero(np.asarray(thick) < 128)
    assert thick_ink > thin_ink


def test_autocrop_reduces_whitespace():
    from PIL import Image, ImageDraw

    img = Image.new("L", (800, 800), 255)
    ImageDraw.Draw(img).rectangle((350, 350, 450, 450), outline=0, width=6)
    cropped = imageprep.autocrop(img, margin_frac=0.05)
    assert cropped.width < img.width and cropped.height < img.height


def test_transparent_flattens_to_white():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(img).line((10, 10, 190, 190), fill=(0, 0, 0, 255), width=8)
    out = imageprep.to_pure_bw(img)
    # corners were transparent, must become white paper
    assert out.getpixel((0, 0)) == 255
