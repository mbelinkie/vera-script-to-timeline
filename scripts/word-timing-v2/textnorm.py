"""Text normalisation shared by every aligner input (plan section 5, shared rules).

A display token becomes zero or more spoken words:
- edge punctuation and quote marks are stripped (`"1998."` -> `1998`);
- the token is split at hyphens and at letter/digit boundaries
  (`quote-unquote` -> quote, unquote; `Windows95Man` -> windows, 95, man);
- digit runs are spelled out (a 4-digit run from 1100 to 2099 as a year);
- words are case-folded, with apostrophes inside a word kept (`international's`).
"""

from __future__ import annotations

import re

from num2words import num2words

_EDGE = re.compile(r"^[^\w']+|[^\w']+$")
_PARTS = re.compile(r"(?:[^\W\d_]|')+|\d+")


def _spoken_numeral(digits: str) -> list[str]:
    value = int(digits)
    if len(digits) == 4 and 1100 <= value <= 2099:
        spoken = num2words(value, to="year")
    else:
        spoken = num2words(value)
    return [part for part in re.split(r"[\s\-,]+", spoken.replace(" and ", " ")) if part]


def normalise_token(display: str) -> list[str]:
    """Return the spoken words for one display token (empty if nothing is spoken)."""
    token = _EDGE.sub("", display.replace("’", "'").replace("‘", "'").strip())
    words: list[str] = []
    for part in _PARTS.findall(token):
        if part.isdigit():
            words.extend(_spoken_numeral(part))
        else:
            word = part.strip("'").casefold()
            if word:
                words.append(word)
    return words


def word_entries(display_tokens: list[str]) -> list[dict[str, object]]:
    """Contract `words` entries for a token list; multi-word tokens get `sub` indices."""
    entries: list[dict[str, object]] = []
    for index, display in enumerate(display_tokens):
        spoken = normalise_token(display)
        for sub, text in enumerate(spoken):
            entry: dict[str, object] = {"i": index, "text": text, "display": display}
            if len(spoken) > 1:
                entry["sub"] = sub
            entries.append(entry)
    return entries
