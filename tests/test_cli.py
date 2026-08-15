import argparse
import json

from kdpbuilder.cli import _fill_from_book


def _spec(tmp_path, **cover):
    data = {
        "theme": "axolotl",
        "age": "5-6",
        "style": "kawaii",
        "designs": 40,
        "trim": "8.5x11",
        "paper": "bw_white",
    }
    if cover:
        data["cover"] = cover
    p = tmp_path / "book.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_fill_from_book_fills_unset_fields(tmp_path):
    book = _spec(tmp_path)
    args = argparse.Namespace(book=book, theme=None, age=None, style=None, count=None, trim=None)
    spec = _fill_from_book(args, ["theme", "age", "style", "count", "trim"])
    assert (args.theme, args.age, args.style, args.count, args.trim) == \
        ("axolotl", "5-6", "kawaii", 40, "8.5x11")
    assert spec["theme"] == "axolotl"


def test_explicit_flag_wins_over_spec(tmp_path):
    book = _spec(tmp_path)
    args = argparse.Namespace(book=book, theme="cat", age=None, style=None, count=None, trim=None)
    _fill_from_book(args, ["theme", "age", "style", "count", "trim"])
    assert args.theme == "cat"  # explicit flag kept
    assert args.age == "5-6"    # unset field still filled from spec


def test_no_book_is_a_noop(tmp_path):
    args = argparse.Namespace(book=None, theme=None)
    assert _fill_from_book(args, ["theme"]) is None
    assert args.theme is None


def test_only_requested_keys_are_filled(tmp_path):
    book = _spec(tmp_path)
    args = argparse.Namespace(book=book, theme=None, age=None)
    _fill_from_book(args, ["theme"])  # age not requested
    assert args.theme == "axolotl"
    assert args.age is None
