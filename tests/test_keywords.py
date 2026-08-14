from kdpbuilder import keywords as kkw

SAMPLE_PL = """
Kawaii Aksolotl Kolorowanka dla dzieci
Aksolotl kolorowanka dla dzieci w wieku 4-8 lat
kolorowanka dla dzieci, grube linie
translate template relativeWidth platformId
"""


def _top_phrases(ranked):
    return [p for p, _ in ranked]


def test_finds_common_phrases():
    ranked = kkw.mine([SAMPLE_PL], lang="pl", ngram=(1, 3), min_count=2)
    phrases = _top_phrases(ranked)
    assert "kolorowanka" in phrases
    assert any("kolorowanka dla dzieci" == p for p in phrases)


def test_drops_noise_tokens():
    ranked = kkw.mine([SAMPLE_PL], lang="pl", min_count=1)
    phrases = _top_phrases(ranked)
    assert not any("translate" in p or "template" in p or "platform" in p for p in phrases)


def test_drops_stopword_edges():
    ranked = kkw.mine([SAMPLE_PL], lang="pl", min_count=1)
    for p in _top_phrases(ranked):
        assert not p.split()[0] in kkw._STOP["pl"]
        assert not p.split()[-1] in kkw._STOP["pl"]


def test_min_count_filter():
    ranked = kkw.mine([SAMPLE_PL], lang="pl", min_count=3)
    for _, c in ranked:
        assert c >= 3


def test_en_language():
    text = "cute axolotl coloring book for kids\naxolotl coloring book bold and easy"
    ranked = kkw.mine([text], lang="en", min_count=2)
    phrases = _top_phrases(ranked)
    assert any("axolotl coloring" in p for p in phrases)
