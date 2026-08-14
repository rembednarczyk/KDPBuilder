"""Access to KDP print specs.

The numbers live in one place only: the kdp-compliance skill's
references/kdp_specs.json. This module loads that file so the generation
pipeline and the validator never drift apart. Do not restate specs in code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class SpecError(ValueError):
    """Raised when a trim size or paper type is not known to the specs."""


def default_specs_path() -> Path:
    """Locate kdp_specs.json.

    Order: KDP_SPECS_PATH env var, then the bundled skill file relative to the
    repository root (this package sits at the repo root next to .claude/).
    """
    env = os.environ.get("KDP_SPECS_PATH")
    if env:
        return Path(env)
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / ".claude" / "skills" / "kdp-compliance" / "references" / "kdp_specs.json"


def load_specs(path: str | os.PathLike | None = None) -> dict:
    p = Path(path) if path else default_specs_path()
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def trim(specs: dict, trim_key: str) -> dict:
    """Return {'w', 'h', 'page_counts'} for a trim key like '8.5x11'."""
    sizes = specs["trim_sizes"]
    if trim_key not in sizes:
        raise SpecError(
            "Unknown trim '%s'. Known: %s" % (trim_key, ", ".join(sizes))
        )
    return sizes[trim_key]


def page_size_in(specs: dict, trim_key: str, bleed: bool) -> tuple[float, float]:
    """Page size in inches, with or without bleed."""
    t = trim(specs, trim_key)
    w, h = float(t["w"]), float(t["h"])
    if bleed:
        w += float(specs["bleed"]["add_to_width"])
        h += float(specs["bleed"]["add_to_height"])
    return w, h


def page_count_limits(specs: dict, trim_key: str, paper: str) -> tuple[int, int]:
    t = trim(specs, trim_key)
    limits = t["page_counts"].get(paper)
    if limits is None:
        raise SpecError(
            "Paper '%s' is not available for trim %s." % (paper, trim_key)
        )
    return int(limits[0]), int(limits[1])


def min_margin_in(specs: dict, bleed: bool) -> float:
    m = specs["margins"]
    return float(m["outside_min_with_bleed_in"] if bleed else m["outside_min_no_bleed_in"])


def gutter_in(specs: dict, page_count: int) -> float:
    """Minimum inside (binding) margin for a given page count."""
    table = specs["margins"]["gutter_by_pages"]
    for max_pages, margin in table:
        if page_count <= max_pages:
            return float(margin)
    return float(table[-1][1])


def recommended_dpi(specs: dict) -> int:
    return int(specs["resolution"]["recommended_min_dpi"])


# ----------------------------------------------------------------------------
# Cover geometry
# ----------------------------------------------------------------------------

def paper_thickness_in(specs: dict, paper: str) -> float:
    table = specs["cover"]["paper_thickness_in"]
    if paper not in table:
        raise SpecError("No cover paper thickness for '%s'." % paper)
    return float(table[paper])


def spine_width_in(specs: dict, page_count: int, paper: str) -> float:
    """Spine width in inches: page count times per-page paper thickness."""
    return page_count * paper_thickness_in(specs, paper)


def spine_text_allowed(specs: dict, page_count: int) -> bool:
    return page_count >= int(specs["cover"]["min_pages_for_spine_text"])


def full_cover_size_in(specs: dict, trim_key: str, page_count: int, paper: str) -> tuple[float, float]:
    """Full wrap cover size in inches (back + spine + front, plus bleed).

    width  = 2*bleed + 2*trim_width + spine
    height = trim_height + 2*bleed
    """
    t = trim(specs, trim_key)
    tw, th = float(t["w"]), float(t["h"])
    bleed = float(specs["cover"]["bleed_each_edge_in"])
    spine = spine_width_in(specs, page_count, paper)
    return (2 * bleed + 2 * tw + spine, th + 2 * bleed)


def cover_regions_in(specs: dict, trim_key: str, page_count: int, paper: str) -> dict:
    """X boundaries (inches from the left) of back, spine and front panels."""
    t = trim(specs, trim_key)
    tw = float(t["w"])
    bleed = float(specs["cover"]["bleed_each_edge_in"])
    spine = spine_width_in(specs, page_count, paper)
    back_x0 = bleed
    spine_x0 = bleed + tw
    front_x0 = bleed + tw + spine
    front_x1 = bleed + tw + spine + tw
    return {
        "bleed_in": bleed,
        "trim_w_in": tw,
        "spine_w_in": spine,
        "back_x0": back_x0,
        "spine_x0": spine_x0,
        "front_x0": front_x0,
        "front_x1": front_x1,
    }


def paper_types(specs: dict) -> list[str]:
    return list(specs["paper_types"])
