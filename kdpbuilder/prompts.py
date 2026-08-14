"""Line-art prompt builder (workflow step 1).

Prompts are composed from a library in data/prompts.json: a theme (subject and
scenes), an age group (line weight and complexity), and a style (kawaii, cozy,
seasonal, and so on). The library is the single source of truth for prompt
content; edit the JSON, not this file.

The output of any image model is a half-product. Clean it with imageprep and
review each page by hand (workflow step 6).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def default_lib_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "prompts.json"


@lru_cache(maxsize=8)
def _load_cached(path_str: str) -> dict:
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prompt_lib(path: str | Path | None = None) -> dict:
    return _load_cached(str(path or default_lib_path()))


class PromptError(ValueError):
    """Unknown theme, age group, style, or season."""


def _get(lib, section, key):
    table = lib.get(section, {})
    if key not in table:
        raise PromptError(
            "Unknown %s '%s'. Known: %s" % (section, key, ", ".join(table))
        )
    return table[key]


def list_themes(lib=None):
    return list((lib or load_prompt_lib())["themes"])


def list_styles(lib=None):
    return list((lib or load_prompt_lib())["styles"])


def list_age_groups(lib=None):
    return list((lib or load_prompt_lib())["age_groups"])


def scenes_for(theme: str, lib=None):
    return list(_get(lib or load_prompt_lib(), "themes", theme)["scenes"])


def _dedupe(parts):
    seen, out = set(), []
    for p in parts:
        p = p.strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _style_terms(lib, style, season):
    s = _get(lib, "styles", style)
    terms = list(s.get("positive", []))
    if style == "seasonal" and season:
        seasons = s.get("seasons", {})
        if season not in seasons:
            raise PromptError(
                "Unknown season '%s'. Known: %s" % (season, ", ".join(seasons))
            )
        terms += list(seasons[season])
    return terms


def compose_subject(theme: str, scene: str | None = None, lib=None) -> str:
    t = _get(lib or load_prompt_lib(), "themes", theme)
    base = t["subject_base"]
    return "%s %s" % (base, scene.strip()) if scene else base


def build_prompt(
    subject: str,
    age: str | None = None,
    style: str | None = None,
    season: str | None = None,
    extra: list[str] | None = None,
    lib: dict | None = None,
) -> str:
    """Positive prompt: subject, then style, age complexity, and core anchors."""
    lib = lib or load_prompt_lib()
    parts = [subject.strip().rstrip(".")]
    if style:
        parts += _style_terms(lib, style, season)
    if age:
        parts += _get(lib, "age_groups", age).get("positive", [])
    parts += lib["base_style"]["core"]
    if extra:
        parts += extra
    return ", ".join(_dedupe(parts))


def negative_prompt(
    age: str | None = None,
    style: str | None = None,
    extra: list[str] | None = None,
    lib: dict | None = None,
) -> str:
    lib = lib or load_prompt_lib()
    parts = list(lib["base_style"]["negative"])
    if age:
        parts += _get(lib, "age_groups", age).get("negative", [])
    if extra:
        parts += extra
    return ", ".join(_dedupe(parts))


def build_pair(
    subject: str,
    age: str | None = None,
    style: str | None = None,
    season: str | None = None,
    extra: list[str] | None = None,
    lib: dict | None = None,
) -> dict:
    """Positive and negative prompt for one design from a ready subject string."""
    lib = lib or load_prompt_lib()
    return {
        "subject": subject.strip(),
        "prompt": build_prompt(subject, age=age, style=style, season=season, extra=extra, lib=lib),
        "negative_prompt": negative_prompt(age=age, style=style, lib=lib),
    }


def build_cover_prompt(theme: str, extra: list[str] | None = None, lib: dict | None = None) -> dict:
    """Positive and negative prompt for full-color, text-free cover art."""
    lib = lib or load_prompt_lib()
    subject = _get(lib, "themes", theme)["subject_base"]
    cover = lib["cover_style"]
    pos = [subject] + list(cover["positive"])
    if extra:
        pos += extra
    return {
        "subject": subject,
        "prompt": ", ".join(_dedupe(pos)),
        "negative_prompt": ", ".join(_dedupe(cover["negative"])),
    }


def build_book(
    theme: str,
    age: str,
    style: str,
    count: int,
    season: str | None = None,
    extra: list[str] | None = None,
    lib: dict | None = None,
) -> list[dict]:
    """Prompts for a whole book: style and age fixed, scene varied per page.

    Keeping theme, age and style constant is what holds the line style together
    across the book (workflow step 2). Reuse the same image-model seed too.
    """
    lib = lib or load_prompt_lib()
    # Validate inputs up front.
    _get(lib, "themes", theme)
    _get(lib, "age_groups", age)
    _get(lib, "styles", style)
    scenes = scenes_for(theme, lib)
    pages = []
    for i in range(count):
        scene = scenes[i % len(scenes)]
        subject = compose_subject(theme, scene, lib)
        pair = build_pair(subject, age=age, style=style, season=season, extra=extra, lib=lib)
        pair["page"] = i + 1
        pair["scene"] = scene
        pages.append(pair)
    return pages
