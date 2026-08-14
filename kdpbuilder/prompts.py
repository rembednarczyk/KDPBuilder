"""Line-art prompt builder (workflow step 1).

Produces prompts for generating clean coloring-book line art in the
bold-and-easy style for ages 3 to 6. The output of any image model is a
half-product; clean it with imageprep and review each page by hand.
"""

from __future__ import annotations

# Fixed style anchors so every page in a book shares the same character of line.
STYLE_CORE = [
    "black and white coloring book page",
    "bold clean outlines",
    "thick uniform line weight",
    "simple shapes",
    "large open areas to color",
    "no shading",
    "no gradients",
    "no gray",
    "pure white background",
    "one subject centered",
    "high contrast line art",
]

NEGATIVE = [
    "shading",
    "gradient",
    "grayscale fill",
    "photorealistic",
    "3d render",
    "texture",
    "cross-hatching",
    "watermark",
    "text",
    "signature",
    "color",
    "busy background",
    "tiny details",
]


def build_prompt(subject: str, extra: list[str] | None = None) -> str:
    """Positive prompt for one design."""
    parts = [subject.strip().rstrip(".")] + STYLE_CORE
    if extra:
        parts += [e.strip() for e in extra if e.strip()]
    return ", ".join(parts)


def negative_prompt(extra: list[str] | None = None) -> str:
    parts = list(NEGATIVE)
    if extra:
        parts += [e.strip() for e in extra if e.strip()]
    return ", ".join(parts)


def build_pair(subject: str, extra: list[str] | None = None) -> dict:
    """Return both prompts plus the subject, ready to feed an image model."""
    return {
        "subject": subject.strip(),
        "prompt": build_prompt(subject, extra),
        "negative_prompt": negative_prompt(),
    }
