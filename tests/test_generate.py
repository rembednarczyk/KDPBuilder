import io

import pytest
from PIL import Image

from kdpbuilder import generate as kgen


def _png_bytes(color=0):
    img = Image.new("L", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeBackend:
    """Stand-in for GeminiBackend: records calls, returns a tiny PNG."""

    def __init__(self):
        self.calls = []

    def generate(self, prompt, negative=None, aspect_ratio=None):
        self.calls.append({"prompt": prompt, "negative": negative, "aspect": aspect_ratio})
        return _png_bytes()


class FlakyBackend(FakeBackend):
    def __init__(self, fails):
        super().__init__()
        self.fails = fails

    def generate(self, prompt, negative=None, aspect_ratio=None):
        if len(self.calls) < self.fails:
            self.calls.append({"fail": True})
            raise RuntimeError("transient")
        return super().generate(prompt, negative, aspect_ratio)


def test_aspect_for_common_trims():
    assert kgen.aspect_for(8.5, 8.5) == "1:1"
    assert kgen.aspect_for(8.5, 11.0) == "3:4"
    assert kgen.aspect_for(6.0, 9.0) == "2:3"


def test_extract_image_from_response():
    class Blob:
        data = b"IMG"

    class Part:
        inline_data = Blob()

    class Content:
        parts = [Part()]

    class Cand:
        content = Content()

    class Resp:
        candidates = [Cand()]

    assert kgen._extract_image(Resp()) == b"IMG"


def test_extract_image_raises_without_image():
    class Resp:
        candidates = []
        text = "I cannot do that"

    with pytest.raises(kgen.GenerateError):
        kgen._extract_image(Resp())


def test_generate_images_writes_and_names(tmp_path):
    prompts = [
        {"page": 1, "scene": "sitting inside a teacup", "prompt": "p1", "negative_prompt": "n1"},
        {"page": 2, "scene": "wearing a tiny crown", "prompt": "p2"},
    ]
    backend = FakeBackend()
    saved = kgen.generate_images(prompts, tmp_path, backend, aspect_ratio="3:4", log=lambda *a: None)
    assert len(saved) == 2
    assert (tmp_path / "001_sitting-inside-a-teacup.png").exists()
    assert (tmp_path / "002_wearing-a-tiny-crown.png").exists()
    assert backend.calls[0]["aspect"] == "3:4"
    assert backend.calls[0]["negative"] == "n1"
    assert backend.calls[1]["negative"] is None


def test_generate_images_resume_skips_existing(tmp_path):
    prompts = [{"page": 1, "scene": "s", "prompt": "p"}]
    (tmp_path / "001_s.png").write_bytes(b"old")
    backend = FakeBackend()
    kgen.generate_images(prompts, tmp_path, backend, resume=True, log=lambda *a: None)
    assert backend.calls == []  # nothing generated
    assert (tmp_path / "001_s.png").read_bytes() == b"old"


def test_generate_images_limit(tmp_path):
    prompts = [{"page": i, "prompt": "p%d" % i} for i in range(1, 6)]
    backend = FakeBackend()
    saved = kgen.generate_images(prompts, tmp_path, backend, limit=2, log=lambda *a: None)
    assert len(saved) == 2


def test_retry_recovers(tmp_path):
    prompts = [{"page": 1, "prompt": "p"}]
    backend = FlakyBackend(fails=2)
    # patch sleep so the test is fast
    orig = kgen.time.sleep
    kgen.time.sleep = lambda *_: None
    try:
        saved = kgen.generate_images(prompts, tmp_path, backend, retries=3, log=lambda *a: None)
    finally:
        kgen.time.sleep = orig
    assert len(saved) == 1


def test_load_prompts_file_csv_and_json(tmp_path):
    import csv
    import json

    js = tmp_path / "p.json"
    js.write_text(json.dumps([{"page": 1, "prompt": "a", "negative_prompt": "b"}]), encoding="utf-8")
    assert kgen.load_prompts_file(js)[0]["prompt"] == "a"

    cs = tmp_path / "p.csv"
    with open(cs, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["page", "scene", "prompt", "negative_prompt"])
        w.writerow([1, "scene", "a", "b"])
    rows = kgen.load_prompts_file(cs)
    assert rows[0]["prompt"] == "a" and rows[0]["scene"] == "scene"
