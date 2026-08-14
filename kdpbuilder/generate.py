"""Image generation via the Gemini API (Nano Banana).

Turns a list of prompts into raw line-art images on disk. The rest of the
pipeline (imageprep -> assemble -> validate) takes over from there.

The raw output of any model is a half-product. Review each page by hand before
assembling (workflow step 6); this module does not decide a book is print-ready.

The Gemini SDK (google-genai) is imported lazily, so the rest of the package
works without it. Install with: pip install google-genai
Set the key in the environment: export GEMINI_API_KEY=...
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

# Model names change; override with --model or GEMINI_IMAGE_MODEL.
# gemini-3-pro-image      = Nano Banana Pro (highest quality, up to 4K)
# gemini-3.1-flash-image  = Nano Banana 2 tier (cheaper, faster)
# gemini-3.1-flash-lite-image = cheapest flash image
# These use the generate_content API. Imagen models (imagen-4.0-*) use a
# different predict API and are not supported by this backend.
DEFAULT_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")

SUPPORTED_ASPECT = ["1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"]
SUPPORTED_SIZES = ["1K", "2K", "4K"]


def aspect_for(w_in: float, h_in: float) -> str:
    """Closest supported aspect ratio to a trim's width/height."""
    target = w_in / h_in
    def val(a):
        n, d = a.split(":")
        return float(n) / float(d)
    return min(SUPPORTED_ASPECT, key=lambda a: abs(val(a) - target))


def _slug(text: str, limit: int = 30) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-")[:limit] or "design"


class GenerateError(RuntimeError):
    pass


class GeminiBackend:
    """Thin wrapper over google-genai for single-image generation."""

    def __init__(self, api_key: str | None = None, model: str | None = None, image_size: str = "4K"):
        try:
            from google import genai  # lazy: keeps the package importable without the SDK
        except ImportError as e:
            raise GenerateError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from e
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GenerateError("Set GEMINI_API_KEY (or pass api_key=...).")
        if image_size not in SUPPORTED_SIZES:
            raise GenerateError("image_size must be one of %s." % SUPPORTED_SIZES)
        self._genai = genai
        self.client = genai.Client(api_key=key)
        self.model = model or DEFAULT_MODEL
        self.image_size = image_size

    def generate(self, prompt: str, negative: str | None = None, aspect_ratio: str | None = None) -> bytes:
        from google.genai import types

        text = prompt
        if negative:
            text += "\n\nDo not include: " + negative
        image_cfg = types.ImageConfig(image_size=self.image_size)
        if aspect_ratio:
            image_cfg.aspect_ratio = aspect_ratio
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"], image_config=image_cfg
        )
        resp = self.client.models.generate_content(model=self.model, contents=text, config=config)
        return _extract_image(resp)


def _extract_image(resp) -> bytes:
    """Pull the first inline image blob out of a generate_content response."""
    for cand in getattr(resp, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            blob = getattr(part, "inline_data", None)
            data = getattr(blob, "data", None) if blob else None
            if data:
                return data
    # Surface a text reason if the model returned words instead of an image.
    reason = getattr(resp, "text", None)
    raise GenerateError("No image returned by the model." + (" Model said: %s" % reason if reason else ""))


def _with_retry(fn, retries: int, log):
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:  # transient API/network errors
            if attempt >= retries:
                raise
            log("  attempt %d failed (%s); retrying in %.0fs" % (attempt, e, delay))
            time.sleep(delay)
            delay *= 2


def load_prompts_file(path: str | Path) -> list[dict]:
    """Read prompts from a book-prompts .json or .csv file."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise GenerateError("JSON prompts file must be a list of objects.")
        return data
    if p.suffix.lower() == ".csv":
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    raise GenerateError("Unsupported prompts file type: %s (use .json or .csv)." % p.suffix)


def generate_images(
    prompts: list[dict],
    out_dir: str | Path,
    backend,
    aspect_ratio: str | None = None,
    sleep: float = 0.0,
    retries: int = 3,
    resume: bool = True,
    limit: int | None = None,
    log=print,
) -> list[Path]:
    """Generate one image per prompt and save PNGs to out_dir.

    Each prompt is a dict with at least a 'prompt' key; optional 'page',
    'scene', 'negative_prompt'. Files are named NNN_slug.png so they sort by
    page. Existing files are skipped when resume is True, so a run can restart.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    items = prompts[:limit] if limit else prompts
    for i, item in enumerate(items):
        page = int(item.get("page", i + 1))
        scene = item.get("scene") or ""
        name = "%03d_%s.png" % (page, _slug(scene)) if scene else "%03d.png" % page
        target = out / name
        if resume and target.exists():
            log("skip existing %s" % name)
            saved.append(target)
            continue
        neg = item.get("negative_prompt") or None
        data = _with_retry(
            lambda: backend.generate(item["prompt"], neg, aspect_ratio), retries, log
        )
        target.write_bytes(data)
        saved.append(target)
        log("saved %s (%d/%d)" % (name, i + 1, len(items)))
        if sleep:
            time.sleep(sleep)
    return saved
