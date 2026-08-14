import pytest

from kdpbuilder import prompts


@pytest.fixture(scope="module")
def lib():
    return prompts.load_prompt_lib()


def test_library_loads(lib):
    assert "axolotl" in prompts.list_themes(lib)
    assert set(prompts.list_age_groups(lib)) == {"3-4", "4-8", "5-6", "6-7"}
    assert "kawaii" in prompts.list_styles(lib)


def test_all_themes_well_formed(lib):
    for key in prompts.list_themes(lib):
        t = lib["themes"][key]
        assert t.get("subject_base") is not None
        assert len(t.get("scenes", [])) >= 8
        assert t.get("keywords_pl") and t.get("keywords_en")
        # every theme can build a full book without error
        pages = prompts.build_book(key, age="4-8", style="kawaii", count=5, lib=lib)
        assert len(pages) == 5


def test_new_themes_present(lib):
    for key in ("dinosaur", "unicorn", "ocean", "cat"):
        assert key in prompts.list_themes(lib)


def test_decoration_prompts(lib):
    keys = prompts.list_decorations(lib)
    assert len(keys) >= 8
    for d in prompts.build_decorations(lib=lib):
        assert "no text" in d["prompt"]
        assert "plain solid white background" in d["prompt"]
        assert "text" in d["negative_prompt"]
    with pytest.raises(prompts.PromptError):
        prompts.build_decoration_prompt("nope", lib=lib)


def test_core_and_negatives_always_present(lib):
    pair = prompts.build_pair("cute axolotl", age="5-6", style="kawaii", lib=lib)
    assert "coloring page" in pair["prompt"]
    assert "no shading" in pair["prompt"]
    assert "color" in pair["negative_prompt"]
    assert "kawaii style" in pair["prompt"]


def test_age_changes_terms(lib):
    young = prompts.build_prompt("cute axolotl", age="3-4", lib=lib)
    older = prompts.build_prompt("cute axolotl", age="6-7", lib=lib)
    assert "extra thick bold outlines" in young
    assert "extra thick bold outlines" not in older
    assert "decorative patterns" in older


def test_seasonal_injects_season_terms(lib):
    p = prompts.build_prompt("cute axolotl", style="seasonal", season="christmas", lib=lib)
    assert "santa hat" in p


def test_unknown_keys_raise(lib):
    with pytest.raises(prompts.PromptError):
        prompts.build_prompt("x", style="nope", lib=lib)
    with pytest.raises(prompts.PromptError):
        prompts.build_prompt("x", age="99", lib=lib)
    with pytest.raises(prompts.PromptError):
        prompts.build_prompt("x", style="seasonal", season="nope", lib=lib)


def test_no_duplicate_terms(lib):
    terms = prompts.build_prompt("cute axolotl", age="5-6", style="kawaii", lib=lib).split(", ")
    assert len(terms) == len(set(terms))


def test_build_book_varies_scenes_fixes_style(lib):
    pages = prompts.build_book("axolotl", age="5-6", style="kawaii", count=40, lib=lib)
    assert len(pages) == 40
    assert all(p["page"] == i + 1 for i, p in enumerate(pages))
    # style anchor constant across the whole book
    assert all("kawaii style" in p["prompt"] for p in pages)
    # scenes vary: at least as many distinct scenes as the library holds
    n_scenes = len(prompts.scenes_for("axolotl", lib))
    assert len({p["scene"] for p in pages}) == n_scenes


def test_compose_subject(lib):
    s = prompts.compose_subject("axolotl", "wearing a tiny crown like a little king", lib)
    assert s.startswith("cute axolotl")
    assert "crown" in s
