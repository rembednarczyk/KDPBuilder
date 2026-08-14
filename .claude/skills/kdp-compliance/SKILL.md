---
name: kdp-compliance
description: >
  Validate and enforce Amazon KDP print compliance for children's coloring book
  interiors (and other low-content books). Use this whenever the user is preparing,
  generating, laying out, exporting, checking, or troubleshooting a coloring book
  for Amazon KDP; mentions KDP specs like trim size, bleed, 300 DPI, safe margins,
  single-sided printing, page-count limits, or grayscale line art; or asks to QA a
  print-ready PDF before publishing. Also use when building the coloring-book
  generation or typesetting pipeline so its output meets KDP requirements. Bundles a
  PDF validator (scripts/validate_kdp_pdf.py) and the authoritative KDP spec table
  (references/kdp_specs.json). Trigger even for short asks like "check my book PDF",
  "is this KDP ready", or "fix my coloring book file", in English or Polish.
---

# KDP compliance for coloring books

This skill keeps coloring-book interiors within Amazon KDP print requirements. It
holds the KDP specs in one place and runs an automated check on a finished
interior PDF.

`references/kdp_specs.json` is the single source of truth for the numbers. Read
those values instead of hardcoding specs in prose or in application code. If the
generation app needs the specs, load them from this file so nothing drifts.

## Product standard (context)

Coloring books for ages 3 to 6 use the "bold and easy" style: thick outlines,
simple shapes, large fill areas, one design per page. Books are printed
single-sided, so each design has a blank backing page and markers do not show
through. The common format is 40 designs, which is 80 interior pages.

## Headline KDP specs

Authoritative values live in `references/kdp_specs.json`. Summary:

- Trim: usually 8.5 x 11 or 8.5 x 8.5 inch.
- Bleed (only if art reaches the edge): page width = trim width + 0.125", page
  height = trim height + 0.25". So 8.5 x 11 becomes 8.625 x 11.25. If even one page
  bleeds, set up the whole file with bleed.
- Resolution: 300 DPI for raster art.
- Color: pure black lines on white, no shading or gradients.
- Line weight: minimum 0.75 pt (0.3 mm), thicker for young children.
- Safe zone: keep any text at least 0.25" from the trim edge (0.375" with bleed).
- Page counts (black ink on white): 8.5 x 11 and 8.5 x 8.5 allow 24 to 590 pages.
  Other sizes and paper types are in the JSON.

## Running the validator

Install once:

```bash
pip install pymupdf numpy
```

PyMuPDF is required. numpy is optional and enables the color, shading, blank-page,
and bleed-edge checks.

Basic run:

```bash
python scripts/validate_kdp_pdf.py interior.pdf --trim 8.5x11 --paper bw_white
```

Common options:

```bash
# Enforce a bleed setup and check the single-sided blank-back pattern
python scripts/validate_kdp_pdf.py interior.pdf --trim 8.5x8.5 --bleed on --check-single-sided

# Machine-readable output for the app's test suite
python scripts/validate_kdp_pdf.py interior.pdf --trim 8.5x11 --json > report.json

# Treat warnings as failures (useful in CI / a pre-publish gate)
python scripts/validate_kdp_pdf.py interior.pdf --trim 8.5x11 --strict
```

Flags: `--paper` (bw_white, bw_cream, bw_groundwood, standard_color, premium_color),
`--bleed` (auto, on, off), `--dpi-threshold`, `--tolerance` (page-size tolerance in
inches), `--analysis-dpi` (render DPI for pixel checks), `--check-single-sided`,
`--strict`, `--json`, `--specs` (path to a custom spec file).

Exit code is 0 when there are no FAIL-level issues and 1 otherwise. With `--strict`,
warnings also cause exit 1, so the validator works as a pre-publish gate.

## What the validator checks

- Encryption: locked PDFs are rejected by KDP (FAIL).
- Page size: every page matches the trim (no bleed) or trim+bleed size, and all
  pages use one consistent setup (FAIL on mismatch or mixed sizes).
- Page count: within the min and max for the trim size and paper type (FAIL if
  outside); parity note for single-sided design.
- Resolution: effective DPI of the main image on each content page (WARN below
  threshold). Vector pages are flagged as resolution independent.
- Grayscale: color pixels in a B&W book (WARN).
- Line-art purity: many mid-gray pixels suggest shading or gradients (WARN).
- Bleed edges: on bleed pages, whether art reaches the page edge (WARN if a white
  border is likely).
- Single-sided: blank backing pages present and alternating (optional, WARN).
- Fonts: any text uses embedded fonts (WARN if not embedded).

## What it does NOT check (verify these by hand)

The validator is deliberate about what it can measure reliably. These need a human
or a look at the source file:

- Line weight in points. Confirm the 0.75 pt minimum visually or in the source vector.
- Safe zone. Confirm important content and any text sit inside the safe margins.
- Closed contours and colorable regions. Look for gaps a marker would leak through.
- Artifacts and stray marks from AI generation.
- Real printed color and paper feel. Order a proof copy before scaling a title.

## Manual QA checklist before publishing

- Line weight looks thick enough for the target age.
- No shading, gradients, or gray fills; lines are solid black.
- Contours are closed; fill areas are clean.
- Safe margins respected; nothing important near the trim edge.
- Cover built to the KDP cover calculator size (spine plus bleed).
- Title, subtitle, and description written for the target market (PL or EN).
- AI disclosure set to "Yes, AI-Generated" for images.
- No protected characters, trademarks, or celebrity likenesses.
- Proof copy ordered and inspected.

## Using this in the generation app

The `kdpbuilder` package at the repo root is that app. Its `specs.py` loads this
JSON, `imageprep.py` cleans line art to pure B&W, and `assemble.py` builds the
single-sided interior; `kdpbuilder.cli build` runs the whole pipeline and then
this validator as the final gate.

- Load specs from `references/kdp_specs.json`; do not restate the numbers in code.
- Run `validate_kdp_pdf.py --json --strict` as a build step and fail the build on
  any FAIL. Parse `report.json` in tests.
- Keep the bleed formula and page-size logic here, not duplicated in the app.

## Updating specs

Edit `references/kdp_specs.json` only. Re-check against the KDP Help pages
(Set Trim Size, Bleed, and Margins; Paperback Submission Guidelines; Print Options)
before a large run, since KDP changes specs from time to time.
