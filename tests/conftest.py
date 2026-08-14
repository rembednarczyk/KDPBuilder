import numpy as np
import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def line_art():
    """A synthetic bold line-art design: black outlines on white, some gray."""
    img = Image.new("RGB", (900, 1100), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((150, 150, 750, 750), outline=(0, 0, 0), width=10)
    d.rectangle((250, 800, 650, 1000), outline=(0, 0, 0), width=10)
    # a faint gray gradient patch that cleanup should remove
    d.rectangle((300, 300, 600, 600), fill=(170, 170, 170))
    return img


@pytest.fixture
def designs(line_art):
    return [line_art.copy() for _ in range(6)]
