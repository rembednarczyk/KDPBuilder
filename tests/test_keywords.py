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


def test_segment_breaks_ngrams_at_markup():
    # On one line, markup between words must not form a cross-boundary bigram.
    line = '<span class="csa">kolorowanka</span><div>dzieci</div>'
    off = _top_phrases(kkw.mine([line], lang="pl", ngram=(2, 2), min_count=1))
    on = _top_phrases(kkw.mine([line], lang="pl", ngram=(2, 2), min_count=1, segment=True))
    assert any("kolorowanka dzieci" == p for p in off)      # adjacency without segmentation
    assert not any("kolorowanka dzieci" == p for p in on)   # broken by the tags


def test_normalize_groups_inflections():
    text = "kolorowanka\nkolorowanki\nkolorowanek\nkolorowanka"
    plain = dict(kkw.mine([text], lang="pl", ngram=(1, 1), min_count=1))
    norm = dict(kkw.mine([text], lang="pl", ngram=(1, 1), min_count=1, normalize=True))
    # plain keeps forms apart; normalize aggregates them under one surface form
    assert max(norm.values()) >= 4
    assert max(plain.values()) <= 2


def test_pack_kdp_fields_phrases():
    phrases = ["kolorowanka dla dzieci", "x" * 60, "aksolotl kawaii", "grube linie"]
    fields = kkw.pack_kdp_fields(phrases, mode="phrases")
    assert "kolorowanka dla dzieci" in fields
    assert all(len(f) <= kkw.KDP_FIELD_LIMIT for f in fields)  # over-limit phrase skipped
    assert len(fields) <= kkw.KDP_FIELD_COUNT


def test_pack_kdp_fields_dense_dedupes():
    phrases = ["kolorowanka dzieci", "dzieci prezent", "kolorowanka aksolotl"]
    fields = kkw.pack_kdp_fields(phrases, mode="dense")
    joined = " ".join(fields).split()
    assert len(joined) == len(set(joined))  # no repeated tokens
    assert all(len(f) <= kkw.KDP_FIELD_LIMIT for f in fields)


def test_to_csv_flags_over_limit(tmp_path):
    import csv

    rows = [("short phrase", 5), ("y" * 55, 3)]
    out = tmp_path / "k.csv"
    kkw.to_csv(rows, out)
    with open(out, encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    assert data[0]["over_kdp_limit"] == "False"
    assert data[1]["over_kdp_limit"] == "True"
