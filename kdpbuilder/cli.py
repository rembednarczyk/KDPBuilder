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
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


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
        if name == "build":
            p.add_argument("--threshold", type=int, default=None)
            p.add_argument("--thicken", type=int, default=0)
            p.add_argument("--no-crop", action="store_true")
            p.add_argument("--strict", action="store_true")
            p.set_defaults(func=cmd_build)
        else:
            p.set_defaults(func=cmd_assemble)

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
