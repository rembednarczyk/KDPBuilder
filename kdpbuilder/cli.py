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
    pair = prompts.build_pair(args.subject, extra=args.extra)
    if args.json:
        print(json.dumps(pair, indent=2, ensure_ascii=False))
    else:
        print("PROMPT:\n" + pair["prompt"])
        print("\nNEGATIVE:\n" + pair["negative_prompt"])
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

    p = sub.add_parser("prompt", help="Build a line-art prompt for one subject.")
    p.add_argument("subject")
    p.add_argument("--extra", nargs="*", default=None, help="Extra positive terms.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_prompt)

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
