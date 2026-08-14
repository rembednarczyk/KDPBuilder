"""Repeatable keyword miner for competitor listings.

Given saved listing text (for example an Amazon page dump), extract candidate
keyword phrases with their frequency, filtering HTML/JS noise and stopwords.
This does not give search volume; it surfaces the phrases competitors actually
use so you can validate them in Amazon autocomplete and a volume tool.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_TOKEN = re.compile(r"[a-zA-ZąćęłńóśźżáéíóúñäöüßА-я]+", re.UNICODE)

_STOP = {
    "pl": {"i", "w", "we", "na", "do", "dla", "z", "ze", "o", "u", "a", "to", "że",
           "się", "jest", "są", "nie", "po", "od", "za", "the", "oraz", "co", "jak",
           "czy", "tym", "ten", "ta", "te", "już", "lub", "albo", "być", "ma", "sobie"},
    "en": {"the", "a", "an", "for", "to", "of", "and", "with", "in", "on", "your",
           "this", "that", "is", "are", "it", "as", "at", "by", "or", "you", "from",
           "our", "we", "all", "will", "can", "so", "up"},
}

# HTML/JS and Amazon-page noise tokens to drop.
_NOISE = {
    "translate", "translatex", "translatey", "translation", "template", "templates",
    "relative", "latency", "platform", "platformid", "slot", "slate", "render",
    "width", "height", "function", "var", "json", "http", "https", "www", "com",
    "amp", "quot", "apos", "nbsp", "src", "href", "div", "span", "css", "px", "url",
    "ref", "dib", "tag", "qid", "sprefix", "aria", "svg", "data", "img", "html",
    "true", "false", "null", "undefined", "enabled", "disabled", "crid", "asin",
    "aps", "noss", "sr", "mk", "pl", "en", "utf", "gp", "dp",
}


def _tokens(line: str):
    return [t.lower() for t in _TOKEN.findall(line)]


def _keep(tok: str) -> bool:
    # Natural words are short-ish; long runs are concatenated code identifiers.
    return 3 <= len(tok) <= 18 and tok not in _NOISE


def mine(texts, lang="pl", ngram=(1, 3), top=40, min_count=2, contains=None):
    """Return [(phrase, count), ...] ranked by count.

    Phrases are 1..n word n-grams built within a line. A phrase is dropped if it
    is only stopwords, contains a noise token, or starts/ends with a stopword.

    contains: optional list of substrings/roots. When set, keep only phrases
    that contain at least one of them. Use this on raw HTML/JS page dumps to
    focus on domain phrases (e.g. ["kolorowank", "aksolot", "dziec"]) instead of
    markup boilerplate.
    """
    stop = _STOP.get(lang, set())
    roots = [r.lower() for r in contains] if contains else None
    lo, hi = ngram
    counts = Counter()
    for text in texts:
        for line in text.splitlines():
            toks = [t for t in _tokens(line) if _keep(t)]
            if not toks:
                continue
            for n in range(lo, hi + 1):
                for i in range(len(toks) - n + 1):
                    gram = toks[i:i + n]
                    if all(t in stop for t in gram):
                        continue
                    if gram[0] in stop or gram[-1] in stop:
                        continue
                    phrase = " ".join(gram)
                    if roots and not any(r in phrase for r in roots):
                        continue
                    counts[phrase] += 1
    ranked = [(p, c) for p, c in counts.most_common() if c >= min_count]
    return ranked[:top]


def mine_files(paths, **kw):
    texts = [Path(p).read_text(encoding="utf-8", errors="ignore") for p in paths]
    return mine(texts, **kw)


# Handy seed roots for the coloring-book niche (pass to `contains`).
NICHE_ROOTS_PL = ["kolorowank", "aksolot", "axolot", "dziec", "przedszk", "prezent",
                  "wiek", "grub", "zwierz", "morsk", "kawaii", "malow", "wodn"]
NICHE_ROOTS_EN = ["coloring", "axolotl", "kids", "toddler", "kawaii", "cute", "animal",
                  "ocean", "sea", "gift", "preschool", "bold", "easy"]
