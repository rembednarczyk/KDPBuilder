"""Command-line entry point for the coloring-book pipeline.

Subcommands:
  prompt    build a line-art prompt for one subject (step 1)
  prep      clean raw images to pure black-and-white line art (steps 3-4)
  assemble  build a single-sided interior PDF at the target trim (steps 5-6)
  build     prep + assemble + validate, end to end
  validate  run the kdp-compliance validator on a finished PDF
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from . import assemble as kassemble
from . import cover as kcover
from . import generate as kgenerate
from . import imageprep
from . import prompts
from . import specs as kspecs

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _list_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def _validator_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return (
        repo_root
        / ".claude"
        / "skills"
        / "kdp-compliance"
        / "scripts"
        / "validate_kdp_pdf.py"
    )


def cmd_prompt(args) -> int:
    lib = prompts.load_prompt_lib()
    if args.theme:
        subject = prompts.compose_subject(args.theme, args.scene, lib)
    elif args.subject:
        subject = args.subject
    else:
        sys.stderr.write("Provide a subject or --theme.\n")
        return 2
    try:
        pair = prompts.build_pair(
            subject, age=args.age, style=args.style, season=args.season, extra=args.extra, lib=lib
        )
    except prompts.PromptError as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    if args.json:
        print(json.dumps(pair, indent=2, ensure_ascii=False))
    else:
        print("PROMPT:\n" + pair["prompt"])
        print("\nNEGATIVE:\n" + pair["negative_prompt"])
    return 0


def cmd_book_prompts(args) -> int:
    lib = prompts.load_prompt_lib()
    try:
        pages = prompts.build_book(
            theme=args.theme, age=args.age, style=args.style,
            count=args.count, season=args.season, extra=args.extra, lib=lib,
        )
    except prompts.PromptError as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    if args.format == "csv":
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["page", "scene", "prompt", "negative_prompt"])
        for p in pages:
            w.writerow([p["page"], p["scene"], p["prompt"], p["negative_prompt"]])
        text = buf.getvalue()
    else:
        text = json.dumps(pages, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("Wrote %d prompt(s) to %s" % (len(pages), args.out))
    else:
        print(text)
    return 0


def cmd_generate(args) -> int:
    lib = prompts.load_prompt_lib()
    if args.prompts:
        try:
            items = kgenerate.load_prompts_file(args.prompts)
        except kgenerate.GenerateError as e:
            sys.stderr.write(str(e) + "\n")
            return 2
    elif args.theme and args.age and args.style:
        try:
            items = prompts.build_book(
                theme=args.theme, age=args.age, style=args.style,
                count=args.count, season=args.season, lib=lib,
            )
        except prompts.PromptError as e:
            sys.stderr.write(str(e) + "\n")
            return 2
    else:
        sys.stderr.write("Provide --prompts FILE, or --theme --age --style to build them.\n")
        return 2

    aspect = args.aspect
    if aspect is None and args.trim:
        specs = kspecs.load_specs()
        t = kspecs.trim(specs, args.trim)
        aspect = kgenerate.aspect_for(float(t["w"]), float(t["h"]))

    try:
        backend = kgenerate.GeminiBackend(model=args.model, image_size=args.image_size)
    except kgenerate.GenerateError as e:
        sys.stderr.write(str(e) + "\n")
        return 2

    print("Generating with model %s at %s, aspect %s..." % (backend.model, args.image_size, aspect or "default"))
    saved = kgenerate.generate_images(
        items, out_dir=args.out, backend=backend, aspect_ratio=aspect,
        sleep=args.sleep, retries=args.retries, resume=not args.no_resume, limit=args.limit,
    )
    print("Done. %d image(s) in %s" % (len(saved), args.out))
    print("Next: review each page, then clean and assemble:")
    print("  python -m kdpbuilder.cli build %s --out interior.pdf --trim %s" % (args.out, args.trim or "8.5x11"))
    return 0


def cmd_cover(args) -> int:
    from PIL import Image

    specs = kspecs.load_specs()
    if args.front:
        front = Image.open(args.front)
    elif args.theme and args.generate_front:
        lib = prompts.load_prompt_lib()
        try:
            pair = prompts.build_cover_prompt(args.theme, lib=lib)
            backend = kgenerate.GeminiBackend(model=args.model, image_size=args.image_size)
        except (prompts.PromptError, kgenerate.GenerateError) as e:
            sys.stderr.write(str(e) + "\n")
            return 2
        t = kspecs.trim(specs, args.trim)
        aspect = kgenerate.aspect_for(float(t["w"]), float(t["h"]))
        print("Generating front cover art with %s..." % backend.model)
        data = backend.generate(pair["prompt"], pair["negative_prompt"], aspect)
        import io

        front = Image.open(io.BytesIO(data))
    else:
        sys.stderr.write("Provide --front IMAGE, or --theme with --generate-front.\n")
        return 2

    try:
        summary = kcover.build_cover(
            front, out_path=args.out, trim=args.trim, page_count=args.pages, paper=args.paper,
            title=args.title, subtitle=args.subtitle, author=args.author, blurb=args.blurb,
            bg_color=args.bg, text_color=args.text, title_color=args.title_color,
            title_fill=args.title_fill, title_outline=args.title_outline,
            banner_color=args.banner, banner_alpha=args.banner_alpha,
            font_title=args.font_title or kcover.DEFAULT_TITLE_FONT,
            font_body=args.font_body or kcover.DEFAULT_BODY_FONT, specs=specs,
        )
    except Exception as e:
        sys.stderr.write("Cover build failed: %s\n" % e)
        return 2
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Confirm the spine (%s in) against the KDP cover calculator before uploading." % summary["spine_in"])
    return 0


def cmd_keywords(args) -> int:
    from . import keywords as kkw

    contains = None
    if args.contains == "niche":
        contains = kkw.NICHE_ROOTS_EN if args.lang == "en" else kkw.NICHE_ROOTS_PL
    elif args.contains:
        contains = [r.strip() for r in args.contains.split(",") if r.strip()]
    try:
        ranked = kkw.mine_files(args.files, lang=args.lang, ngram=(args.min_n, args.max_n),
                                top=args.top, min_count=args.min_count, contains=contains)
    except FileNotFoundError as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    if args.json:
        print(json.dumps([{"phrase": p, "count": c} for p, c in ranked], indent=2, ensure_ascii=False))
    else:
        for p, c in ranked:
            print("%5d  %s" % (c, p))
    return 0


def cmd_catalog(args) -> int:
    lib = prompts.load_prompt_lib()
    out = {
        "themes": prompts.list_themes(lib),
        "age_groups": {k: v["label"] for k, v in lib["age_groups"].items()},
        "styles": {k: v["label"] for k, v in lib["styles"].items()},
        "seasons": list(lib["styles"]["seasonal"].get("seasons", {})),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_prep(args) -> int:
    src = Path(args.in_dir)
    dst = Path(args.out_dir)
    dst.mkdir(parents=True, exist_ok=True)
    images = _list_images(src)
    if not images:
        sys.stderr.write("No images found in %s\n" % src)
        return 2
    for p in images:
        img = Image.open(p)
        out = imageprep.clean(
            img,
            threshold=args.threshold,
            thicken=args.thicken,
            crop=not args.no_crop,
        )
        target = dst / (p.stem + ".png")
        out.save(target)
        print("cleaned %s -> %s" % (p.name, target.name))
    print("%d image(s) cleaned." % len(images))
    return 0


def cmd_assemble(args) -> int:
    src = Path(args.img_dir)
    images = _list_images(src)
    if not images:
        sys.stderr.write("No images found in %s\n" % src)
        return 2
    designs = kassemble.load_images(images)
    summary = kassemble.build_interior(
        designs,
        out_path=args.out,
        trim=args.trim,
        paper=args.paper,
        bleed=args.bleed,
        single_sided=not args.no_single_sided,
        dpi=args.dpi,
        gutter=not args.no_gutter,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_scan(args) -> int:
    from . import scan as kscan

    report = kscan.scan_pdf(
        args.pdf, trim=args.trim, paper=args.paper, bleed=args.bleed,
        render_dpi=args.render_dpi, min_line_pt=args.min_line_pt,
    )
    if args.json:
        out = dict(report)
        if not args.page_data:
            out.pop("page_data", None)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        kscan.print_report(report)
    return 0 if report["result"] != "FAIL" else 1


def cmd_validate(args) -> int:
    script = _validator_path()
    if not script.exists():
        sys.stderr.write("Validator not found at %s\n" % script)
        return 2
    cmd = [sys.executable, str(script), args.pdf, "--trim", args.trim, "--paper", args.paper]
    if args.bleed:
        cmd += ["--bleed", "on"]
    if not args.no_single_sided:
        cmd += ["--check-single-sided"]
    if args.strict:
        cmd += ["--strict"]
    if args.json:
        cmd += ["--json"]
    return subprocess.call(cmd)


def cmd_build(args) -> int:
    src = Path(args.img_dir)
    images = _list_images(src)
    if not images:
        sys.stderr.write("No images found in %s\n" % src)
        return 2
    print("Cleaning %d image(s)..." % len(images))
    designs = []
    for p in images:
        img = Image.open(p)
        designs.append(
            imageprep.clean(
                img, threshold=args.threshold, thicken=args.thicken, crop=not args.no_crop
            )
        )
    print("Assembling interior...")
    summary = kassemble.build_interior(
        designs,
        out_path=args.out,
        trim=args.trim,
        paper=args.paper,
        bleed=args.bleed,
        single_sided=not args.no_single_sided,
        dpi=args.dpi,
        gutter=not args.no_gutter,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Validating...")
    v = argparse.Namespace(
        pdf=args.out,
        trim=args.trim,
        paper=args.paper,
        bleed=args.bleed,
        no_single_sided=args.no_single_sided,
        strict=args.strict,
        json=False,
    )
    return cmd_validate(v)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kdpbuilder", description="Coloring-book pipeline for Amazon KDP.")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prompt", help="Build a line-art prompt for one design.")
    p.add_argument("subject", nargs="?", default=None, help="Free subject text (or use --theme).")
    p.add_argument("--theme", help="Theme key from the library, e.g. axolotl.")
    p.add_argument("--scene", help="Scene text to append to the theme subject.")
    p.add_argument("--age", help="Age group: 3-4, 5-6, 6-7.")
    p.add_argument("--style", help="Style: kawaii, cozy, seasonal, ...")
    p.add_argument("--season", help="Season for the seasonal style.")
    p.add_argument("--extra", nargs="*", default=None, help="Extra positive terms.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("book-prompts", help="Build prompts for a whole book (one per page).")
    p.add_argument("--theme", required=True, help="Theme key, e.g. axolotl.")
    p.add_argument("--age", required=True, help="Age group: 3-4, 5-6, 6-7.")
    p.add_argument("--style", required=True, help="Style: kawaii, cozy, seasonal, ...")
    p.add_argument("--count", type=int, default=40, help="Number of designs (default 40).")
    p.add_argument("--season", help="Season for the seasonal style.")
    p.add_argument("--extra", nargs="*", default=None, help="Extra positive terms.")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--out", help="Write to this file instead of stdout.")
    p.set_defaults(func=cmd_book_prompts)

    p = sub.add_parser("generate", help="Generate raw line-art images via the Gemini API.")
    p.add_argument("--out", required=True, help="Folder for the generated PNGs.")
    p.add_argument("--prompts", help="Prompts file from book-prompts (.json or .csv).")
    p.add_argument("--theme", help="Theme key (if not using --prompts).")
    p.add_argument("--age", help="Age group (if not using --prompts).")
    p.add_argument("--style", help="Style (if not using --prompts).")
    p.add_argument("--count", type=int, default=40, help="Designs when building prompts inline.")
    p.add_argument("--season", help="Season for the seasonal style.")
    p.add_argument("--trim", help="Trim key; sets the aspect ratio to match, e.g. 8.5x11.")
    p.add_argument("--aspect", help="Override aspect ratio (1:1, 3:4, 2:3, ...).")
    p.add_argument("--image-size", default="2K", choices=kgenerate.SUPPORTED_SIZES,
                   help="2K is enough for interiors (pipeline upscales to a 300 DPI page) and about half the cost of 4K.")
    p.add_argument("--model", default=None, help="Model id (default NB2 gemini-3.1-flash-image or GEMINI_IMAGE_MODEL).")
    p.add_argument("--sleep", type=float, default=0.0, help="Seconds to wait between images.")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--limit", type=int, default=None, help="Only generate the first N prompts.")
    p.add_argument("--no-resume", action="store_true", help="Regenerate even if a file exists.")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("cover", help="Build a full-wrap KDP paperback cover PDF.")
    p.add_argument("--out", required=True, help="Output cover PDF path.")
    p.add_argument("--trim", required=True, help="Trim key, e.g. 8.5x11.")
    p.add_argument("--pages", type=int, required=True, help="Final interior page count (sets spine width).")
    p.add_argument("--paper", default="bw_white")
    p.add_argument("--title", default="", help="Cover title.")
    p.add_argument("--subtitle", default=None)
    p.add_argument("--author", default=None)
    p.add_argument("--blurb", default=None, help="Back-cover text.")
    p.add_argument("--front", help="Front cover art image (color).")
    p.add_argument("--theme", help="Theme to generate front art from (with --generate-front).")
    p.add_argument("--generate-front", action="store_true", help="Generate front art via Gemini.")
    p.add_argument("--image-size", default="4K", choices=kgenerate.SUPPORTED_SIZES)
    p.add_argument("--model", default=None, help="Model for front art generation.")
    p.add_argument("--bg", default="#FCE7A2", help="Background color (hex).")
    p.add_argument("--text", default="#213241", help="Text color for banner and back (hex).")
    p.add_argument("--title-color", default=None, help="Deprecated alias for --title-fill.")
    p.add_argument("--title-fill", default="#FFFFFF", help="Title letter color (hex).")
    p.add_argument("--title-outline", default="#12303A", help="Title outline color (hex).")
    p.add_argument("--banner", default="#FFFFFF", help="Subtitle banner color (hex).")
    p.add_argument("--banner-alpha", type=int, default=210, help="Banner opacity 0-255.")
    p.add_argument("--font-title", default=None, help="TTF path for the title.")
    p.add_argument("--font-body", default=None, help="TTF path for body text.")
    p.set_defaults(func=cmd_cover)

    p = sub.add_parser("keywords", help="Mine candidate keyword phrases from saved competitor text.")
    p.add_argument("files", nargs="+", help="Text files (e.g. saved Amazon listing dumps).")
    p.add_argument("--lang", default="pl", choices=["pl", "en"])
    p.add_argument("--min-n", type=int, default=1, help="Minimum phrase length in words.")
    p.add_argument("--max-n", type=int, default=3, help="Maximum phrase length in words.")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--min-count", type=int, default=2)
    p.add_argument("--contains", default=None,
                   help="Keep only phrases containing one of these roots (comma-separated), "
                        "or 'niche' for the built-in coloring-book roots. Use on HTML dumps.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_keywords)

    p = sub.add_parser("catalog", help="List available themes, age groups, styles and seasons.")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("prep", help="Clean raw images to pure black-and-white line art.")
    p.add_argument("in_dir")
    p.add_argument("out_dir")
    p.add_argument("--threshold", type=int, default=None, help="0-255 cut (default: Otsu auto).")
    p.add_argument("--thicken", type=int, default=0, help="Grow lines by N pixels.")
    p.add_argument("--no-crop", action="store_true", help="Do not autocrop and reframe.")
    p.set_defaults(func=cmd_prep)

    for name, help_text in (("assemble", "Build the interior PDF."), ("build", "prep + assemble + validate.")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("img_dir")
        p.add_argument("--out", required=True, help="Output PDF path.")
        p.add_argument("--trim", required=True, help="Trim key, e.g. 8.5x11 or 8.5x8.5.")
        p.add_argument("--paper", default="bw_white")
        p.add_argument("--bleed", action="store_true", help="Set up with bleed (art to edge).")
        p.add_argument("--dpi", type=int, default=None, help="Render DPI (default from specs).")
        p.add_argument("--no-single-sided", action="store_true", help="Skip blank backing pages.")
        p.add_argument("--no-gutter", action="store_true",
                       help="Use a symmetric margin instead of a larger binding-side gutter.")
        if name == "build":
            p.add_argument("--threshold", type=int, default=None)
            p.add_argument("--thicken", type=int, default=0)
            p.add_argument("--no-crop", action="store_true")
            p.add_argument("--strict", action="store_true")
            p.set_defaults(func=cmd_build)
        else:
            p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("scan", help="Pixel-level scan (purity, line weight, specks, margins).")
    p.add_argument("pdf")
    p.add_argument("--trim", required=True)
    p.add_argument("--paper", default="bw_white")
    p.add_argument("--bleed", action="store_true")
    p.add_argument("--render-dpi", type=int, default=200, help="Render DPI for vector pages.")
    p.add_argument("--min-line-pt", type=float, default=None, help="Minimum line weight in points.")
    p.add_argument("--json", action="store_true")
    p.add_argument("--page-data", action="store_true", help="Include per-page data in JSON.")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("validate", help="Run the kdp-compliance validator.")
    p.add_argument("pdf")
    p.add_argument("--trim", required=True)
    p.add_argument("--paper", default="bw_white")
    p.add_argument("--bleed", action="store_true")
    p.add_argument("--no-single-sided", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_validate)

    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
