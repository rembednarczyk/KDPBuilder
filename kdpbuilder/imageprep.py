"""Image cleanup for line art (workflow steps 3 and 4).

Takes a raw AI-generated line-art image and produces clean black-and-white:
grays, shadows and gradients removed by thresholding, optional line
thickening for young children. Output stays pure black on white.

These operations are deterministic and testable. They do not invent detail;
treat the result as a half-product and still review each page by hand.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def _otsu_threshold(gray: np.ndarray) -> int:
    """Otsu's method: pick the 0-255 cut that best splits ink from paper."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0.0
    best_t = 127
    best_var = -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var = var
            best_t = t
    return best_t


def to_pure_bw(img: Image.Image, threshold: int | None = None) -> Image.Image:
    """Flatten to pure black-and-white.

    threshold: 0-255 cut; pixels darker become black, lighter become white.
    None uses Otsu to pick the cut automatically. Any transparency is
    composited onto white first so paper stays white.
    """
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    gray = np.asarray(img.convert("L"), dtype=np.uint8)
    t = _otsu_threshold(gray) if threshold is None else int(threshold)
    bw = np.where(gray <= t, 0, 255).astype(np.uint8)
    return Image.fromarray(bw, mode="L")


def thicken_lines(img: Image.Image, amount: int = 1) -> Image.Image:
    """Grow black lines by `amount` pixels for a bolder look.

    amount 0 is a no-op. Works on a black-on-white image by taking a local
    minimum, which spreads dark pixels outward.
    """
    if amount <= 0:
        return img
    size = 2 * amount + 1
    return img.filter(ImageFilter.MinFilter(size))


def autocrop(img: Image.Image, margin_frac: float = 0.04) -> Image.Image:
    """Trim surrounding white and re-add an even white margin.

    Keeps designs centered and consistently framed. margin_frac is a fraction
    of the longer side. Returns the original if the page looks empty.
    """
    gray = img.convert("L")
    inverted = ImageOps.invert(gray)
    bbox = inverted.getbbox()
    if bbox is None:
        return img
    cropped = img.crop(bbox)
    pad = int(round(max(cropped.size) * margin_frac))
    out = Image.new("L", (cropped.width + 2 * pad, cropped.height + 2 * pad), 255)
    out.paste(cropped.convert("L"), (pad, pad))
    return out


def clean(
    img: Image.Image,
    threshold: int | None = None,
    thicken: int = 0,
    crop: bool = True,
) -> Image.Image:
    """Full cleanup: pure B&W, optional autocrop, optional line thickening."""
    out = to_pure_bw(img, threshold=threshold)
    if crop:
        out = autocrop(out)
    if thicken:
        out = thicken_lines(out, thicken)
    return out


def color_fraction(img: Image.Image) -> float:
    """Fraction of pixels with real color (saturation), for quick QA."""
    arr = np.asarray(img.convert("RGB"), dtype=np.int16)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    return float(np.count_nonzero((mx - mn) > 25)) / (arr.shape[0] * arr.shape[1])


def midtone_fraction(img: Image.Image) -> float:
    """Fraction of mid-gray pixels, a proxy for leftover shading."""
    gray = np.asarray(img.convert("L"), dtype=np.uint8)
    return float(np.count_nonzero((gray >= 30) & (gray <= 225))) / gray.size
