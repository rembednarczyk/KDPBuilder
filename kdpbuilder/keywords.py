"""Repeatable keyword miner for competitor listings.

Given saved listing text (for example an Amazon page dump), extract candidate
keyword phrases with their frequency, filtering HTML/JS noise and stopwords.
This does not give search volume; it surfaces the phrases competitors actually
use so you can validate them in Amazon autocomplete and a volume tool.

Beyond mining, this module adds:
- autocomplete() / expand_seeds(): pull Amazon's own search suggestions for
  seeds, the closest-to-truth source of popular phrases (unofficial endpoint).
- mine(normalize=True): optional Polish inflection grouping so counts stop
  fragmenting across cases (kolorowanka / kolorowanki / kolorowanek).
- mine(segment=True): optional segmentation so n-grams do not span dropped
  punctuation, digits or markup on single-line HTML dumps.
- to_csv(): export mined phrases with a KDP 50-character field flag.
- pack_kdp_fields(): pack chosen phrases into the 7 KDP keyword fields.
"""

from __future__ import annotations

import csv
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    import requests
except ImportError:  # only needed for autocomplete()
    requests = None

# KDP keyword field limits (single source of truth).
KDP_FIELD_LIMIT = 50
KDP_FIELD_COUNT = 7

_TOKEN = re.compile(r"[a-zA-ZąćęłńóśźżáéíóúñäöüßА-я]+", re.UNICODE)
# Segment boundary: any run of characters that is neither a letter nor a space.
# Splitting on this keeps multi-word phrases inside a clause but breaks them at
# punctuation, digits and markup so n-grams do not jump across boundaries.
_SEG_SPLIT = re.compile(r"[^a-zA-ZąćęłńóśźżáéíóúñäöüßА-я ]+", re.UNICODE)

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


def _segments(line: str):
    """Split a line into word-only segments, breaking on punctuation/markup."""
    return [s for s in _SEG_SPLIT.split(line) if s.strip()]


def _keep(tok: str) -> bool:
    # Natural words are short-ish; long runs are concatenated code identifiers.
    return 3 <= len(tok) <= 18 and tok not in _NOISE


# --- Polish inflection grouping (optional, approximate) ------------------
# Groups inflected forms so counts aggregate instead of fragmenting across
# cases. This is a heuristic grouping key, not exact lemmatization. _PL_CANON
# pins the niche words that matter and is yours to extend; everything else falls
# back to conservative suffix stripping. Known limit: it does not merge
# stem-changing genitive plurals like "dziewczynek", so add those to _PL_CANON
# or pass a real lemmatizer via mine(stem_fn=) when accuracy matters.
_PL_SUFFIXES = sorted(
    {"iami", "ami", "ach", "ich", "ego", "emu", "ych", "ymi", "owi",
     "em", "om", "ej", "im", "ie", "ów", "y", "i", "a", "e", "u", "o", "ą", "ę"},
    key=len, reverse=True,
)

_PL_CANON = {
    "kolorowanka": "kolorowanka", "kolorowanki": "kolorowanka",
    "kolorowanek": "kolorowanka", "kolorowanke": "kolorowanka",
    "kolorowankę": "kolorowanka", "kolorowanką": "kolorowanka",
    "kolorowankach": "kolorowanka",
    "aksolotl": "aksolotl", "aksolotla": "aksolotl", "aksolotle": "aksolotl",
    "aksolotli": "aksolotl", "aksolotlem": "aksolotl", "aksolotlami": "aksolotl",
    "dziecko": "dziecko", "dziecka": "dziecko", "dzieci": "dziecko",
    "dzieciom": "dziecko", "dzieckiem": "dziecko",
    "zwierze": "zwierze", "zwierzę": "zwierze", "zwierzeta": "zwierze",
    "zwierzęta": "zwierze", "zwierzat": "zwierze", "zwierząt": "zwierze",
    "zwierzatka": "zwierze", "zwierzątka": "zwierze",
}


def _pl_stem(tok: str) -> str:
    """Approximate Polish stem, used for grouping counts only."""
    if tok in _PL_CANON:
        return _PL_CANON[tok]
    for suf in _PL_SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[: -len(suf)]
    return tok


def mine(texts, lang="pl", ngram=(1, 3), top=40, min_count=2, contains=None,
         normalize=False, segment=False, stem_fn=None):
    """Return [(phrase, count), ...] ranked by count.

    Phrases are 1..n word n-grams built within a segment (a whole line, or a
    punctuation-bounded run when segment=True). A phrase is dropped if it is only
    stopwords, contains a noise token, or starts/ends with a stopword.

    contains: optional list of substrings/roots. When set, keep only phrases that
    contain at least one of them (see NICHE_ROOTS_PL / NICHE_ROOTS_EN). Use this
    on raw HTML/JS page dumps to focus on domain phrases instead of boilerplate.

    normalize: when True and lang=="pl", group inflected forms so counts
    aggregate; the most common surface form is reported. Approximate, opt-in, and
    off by default so existing outputs stay stable.

    segment: when True, build n-grams inside punctuation-bounded runs so phrases
    do not span dropped punctuation, digits or markup on single-line dumps.

    stem_fn: optional callable token -> key that overrides the built-in grouping
    (e.g. a pystempel or Morfeusz lemmatizer, or an English stemmer). Implies
    grouping regardless of lang.
    """
    stop = _STOP.get(lang, set())
    roots = [r.lower() for r in contains] if contains else None
    lo, hi = ngram
    stemmer = stem_fn or (_pl_stem if (normalize and lang == "pl") else None)
    counts: Counter = Counter()
    surfaces: dict = defaultdict(Counter)  # stem key -> surface phrase -> freq
    for text in texts:
        for line in text.splitlines():
            units = _segments(line) if segment else [line]
            for unit in units:
                toks = [t for t in _tokens(unit) if _keep(t)]
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
                        if stemmer:
                            key = " ".join(stemmer(t) for t in gram)
                            counts[key] += 1
                            surfaces[key][phrase] += 1
                        else:
                            counts[phrase] += 1
    if stemmer:
        merged = [(surfaces[k].most_common(1)[0][0], c) for k, c in counts.items()]
        merged.sort(key=lambda kv: kv[1], reverse=True)
        ranked = [(p, c) for p, c in merged if c >= min_count]
    else:
        ranked = [(p, c) for p, c in counts.most_common() if c >= min_count]
    return ranked[:top]


def mine_files(paths, **kw):
    texts = [Path(p).read_text(encoding="utf-8", errors="ignore") for p in paths]
    return mine(texts, **kw)


# --- Amazon autocomplete expansion --------------------------------------
# Marketplace ids. If suggestions come back empty for a domain, grab the current
# id from a real browser request (network tab, the completion.amazon call) and
# update it here.
_MID = {"com": "ATVPDKIKX0DER", "pl": "A1C3SOZRARQ6R3"}


def autocomplete(prefix, domain="pl", alias="stripbooks", limit=11, pause=0.6, timeout=8):
    """Amazon search suggestions for a seed prefix (unofficial endpoint).

    This is the closest-to-truth source of popular phrases. The endpoint is
    undocumented, may change or rate-limit, and Amazon's terms restrict automated
    querying, so keep volume low, keep the pause, and treat results as a research
    aid. Needs `requests`. Returns [] on any failure.
    """
    if requests is None:
        raise RuntimeError("autocomplete() needs requests (pip install requests)")
    url = f"https://completion.amazon.{domain}/api/2017/suggestions"
    params = {"limit": limit, "prefix": prefix, "alias": alias,
              "site-variant": "desktop", "mid": _MID.get(domain, ""),
              "lop": "pl_PL" if domain == "pl" else "en_US"}
    values = []
    try:
        r = requests.get(url, params=params,
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        r.raise_for_status()
        values = [s.get("value", "") for s in r.json().get("suggestions", []) if s.get("value")]
    except Exception:
        values = []
    time.sleep(pause)  # be polite to the endpoint
    return values


def expand_seeds(seeds, domain="pl", alias="stripbooks", pause=0.6):
    """Map each seed to its Amazon autocomplete suggestions."""
    return {s: autocomplete(s, domain=domain, alias=alias, pause=pause) for s in seeds}


# --- KDP output helpers --------------------------------------------------
def to_csv(rows, path, encoding="utf-8-sig"):
    """Write mined [(phrase, count), ...] to CSV for the pipeline.

    Columns: phrase, count, words, chars, over_kdp_limit. over_kdp_limit is True
    when a phrase exceeds the 50-character KDP keyword field. utf-8-sig keeps
    Polish characters readable when the file is opened in Excel.
    """
    path = Path(path)
    with path.open("w", newline="", encoding=encoding) as fh:
        w = csv.writer(fh)
        w.writerow(["phrase", "count", "words", "chars", "over_kdp_limit"])
        for phrase, count in rows:
            chars = len(phrase)
            w.writerow([phrase, count, phrase.count(" ") + 1, chars, chars > KDP_FIELD_LIMIT])
    return path


def pack_kdp_fields(phrases, max_fields=KDP_FIELD_COUNT, max_chars=KDP_FIELD_LIMIT, mode="phrases"):
    """Pack ordered phrases (best first) into KDP keyword fields.

    mode="phrases": one phrase per field, kept intact, skipping any phrase longer
        than max_chars. Coherent, better for the semantic layer (COSMO/Rufus).
    mode="dense": deduplicate tokens across the whole set and greedily pack unique
        tokens into fields up to max_chars. An already-indexed token adds nothing
        when repeated, so this wastes no character budget at the cost of phrase
        readability.

    Returns up to max_fields strings.
    """
    if mode == "phrases":
        fields = []
        for p in phrases:
            if len(p) <= max_chars and p not in fields:
                fields.append(p)
            if len(fields) >= max_fields:
                break
        return fields
    if mode == "dense":
        seen, tokens = set(), []
        for p in phrases:
            for t in p.split():
                if len(t) <= max_chars and t not in seen:
                    seen.add(t)
                    tokens.append(t)
        fields, cur = [], ""
        for t in tokens:
            candidate = f"{cur} {t}".strip()
            if len(candidate) <= max_chars:
                cur = candidate
            else:
                fields.append(cur)
                cur = t
                if len(fields) >= max_fields:
                    cur = ""
                    break
        if cur and len(fields) < max_fields:
            fields.append(cur)
        return fields[:max_fields]
    raise ValueError("mode must be 'phrases' or 'dense'")


# Seed roots for the coloring-book niche (pass to `contains`). Diacritic and
# ASCII variants are included on purpose because competitor dumps vary in
# encoding.
NICHE_ROOTS_PL = [
    "kolorowank", "malowank", "ksiazk", "książk",
    "aksolot", "axolot",
    "dziec", "przedszk", "zerow", "malu", "latk", "roczn",
    "dziewczyn", "chlop", "chłop",
    "prezent", "urodzin", "mikolaj", "mikołaj", "choink", "gwiazdk",
    "swiat", "świąt", "wielkanoc", "halloween", "walentyn",
    "grub", "prost", "jednostron", "duz", "duż", "obrazk",
    "pierwsz", "nauk", "motoryk",
    "kawaii", "slodk", "słodk",
    "zwierz", "morsk", "ocean", "wodn", "podwodn", "ryb",
    "dino", "jednoroz", "jednoroż", "pojazd", "samochod", "kopark",
    "kosmos", "planet", "kot", "pies", "safari", "dzungl", "dżungl",
    "owad", "motyl", "kwiat", "liter", "cyfr", "alfabet", "ksztalt", "kształt", "kropk",
]

NICHE_ROOTS_EN = [
    "coloring", "color", "book",
    "axolotl", "kids", "toddler", "preschool",
    "girls", "boys", "ages",
    "first", "learn", "motor",
    "bold", "easy", "thick", "jumbo", "large", "simple",
    "gift", "birthday", "christmas", "easter", "halloween", "valentine",
    "cute", "kawaii",
    "ocean", "sea", "underwater", "marine", "fish",
    "dino", "unicorn", "truck", "digger", "construction", "car",
    "space", "planet", "rocket", "cat", "dog", "puppy", "kitten",
    "safari", "jungle", "zoo", "bug", "insect", "butterfly",
    "flower", "letter", "number", "alphabet", "shape", "dot", "marker",
]
