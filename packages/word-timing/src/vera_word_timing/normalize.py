"""Display token -> spoken aligner units (the many-to-many normalisation map).

Rules (ported from the word-timing v2 study, without its num2words dependency):
- edge punctuation and quote marks are stripped ("1998." -> 1998);
- tokens split at hyphens and letter/digit boundaries
  ("quote-unquote" -> quote, unquote; "Windows95Man" -> windows, 95, man);
- digit runs are spelled out in English; a 4-digit run from 1100 to 2099 is
  read as a year ("1998" -> nineteen ninety eight, "2005" -> two thousand five);
- words are case-folded; apostrophes inside a word are kept.

Each unit keeps (token index, sub index), so every unit maps back to exactly
one display token and display tokens are never merged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EDGE = re.compile(r"^[^\w']+|[^\w']+$")
_PARTS = re.compile(r"(?:[^\W\d_]|')+|\d+")
_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]
_SCALES = [(1_000_000_000, "billion"), (1_000_000, "million"), (1000, "thousand")]


def _below_hundred(n: int) -> list[str]:
    if n < 20:
        return [_ONES[n]]
    tens, ones = divmod(n, 10)
    return [_TENS[tens]] + ([_ONES[ones]] if ones else [])


def _below_thousand(n: int) -> list[str]:
    hundreds, rest = divmod(n, 100)
    out = [_ONES[hundreds], "hundred"] if hundreds else []
    return out + (_below_hundred(rest) if rest or not out else [])


def cardinal(n: int) -> list[str]:
    """English cardinal words, no 'and' ("105" -> one hundred five)."""
    if n < 0:
        raise ValueError("negative numbers are not spoken tokens")
    if n == 0:
        return ["zero"]
    words: list[str] = []
    for value, name in _SCALES:
        if n >= value:
            head, n = divmod(n, value)
            words += [*cardinal(head), name]
    if n:
        words += _below_thousand(n)
    return words


def year(n: int) -> list[str]:
    """Year reading for 1100-2099.

    "1998" -> nineteen ninety eight; "1900" -> nineteen hundred.
    """
    high, low = divmod(n, 100)
    if 2000 <= n <= 2009:
        return cardinal(n)
    if low == 0:
        return [*_below_hundred(high), "hundred"]
    tail = ["oh", _ONES[low]] if low < 10 else _below_hundred(low)
    return _below_hundred(high) + tail


def spoken_numeral(digits: str) -> list[str]:
    value = int(digits)
    return (
        year(value) if len(digits) == 4 and 1100 <= value <= 2099 else cardinal(value)
    )


def normalise_token(display: str, language: str = "en") -> list[str]:
    """Spoken words for one display token (empty if nothing is spoken).

    Numerals are spelled out for English only. Other languages keep digits:
    Canary emits spoken-form numbers, so digits are rare there, and an
    English reading of a German number would be wrong.
    """
    token = _EDGE.sub("", display.replace("\u2019", "'").replace("\u2018", "'").strip())
    english = language.split("-")[0] == "en"
    words: list[str] = []
    for part in _PARTS.findall(token):
        if part.isdigit():
            words.extend(
                spoken_numeral(part) if language.split("-")[0] == "en" else [part]
            )
        else:
            # casefold() would turn German "ß" into "ss" and miss the MFA
            # German dictionary; plain lower() keeps it. English is unchanged.
            stripped = part.strip("'")
            word = stripped.casefold() if english else stripped.lower()
            if word:
                words.append(word)
    return words


@dataclass(frozen=True)
class Unit:
    token_index: int
    sub: int
    text: str


def units(display_tokens: list[str], language: str = "en") -> list[Unit]:
    """Aligner units for a token list, in order; multi-word tokens get sub 0, 1, ..."""
    return [
        Unit(i, sub, text)
        for i, display in enumerate(display_tokens)
        for sub, text in enumerate(normalise_token(display, language))
    ]
