"""Text normalisation shared by every aligner input (plan section 5, shared rules)."""

from __future__ import annotations

import re

from num2words import num2words

_EDGE_PUNCT = re.compile(r"^[^\w']+|[^\w']+$")
_INNER_JUNK = re.compile(r"[^\w'\-]")


def _spoken_numeral(token: str) -> list[str]:
    digits = token.lstrip("'’")
    value = int(digits)
    if len(digits) == 4 and 1100 <= value <= 2099:
        spoken = num2words(value, to="year")
    else:
        spoken = num2words(value)
    return [part for part in re.split(r"[\s\-,]+", spoken.replace(" and ", " ")) if part]


def normalise_token(display: str) -> list[str]:
    """Return the spoken words for one display token (empty if nothing is spoken)."""
    token = display.replace("’", "'").strip()
    if re.fullmatch(r"['’]?\d+", token):
        return _spoken_numeral(token)
    token = _EDGE_PUNCT.sub("", token)
    token = _INNER_JUNK.sub("", token).strip("'-").casefold()
    return [token] if token else []


def word_entries(display_tokens: list[str]) -> list[dict[str, object]]:
    """Contract `words` entries for a token list; numerals get `sub` indices."""
    entries: list[dict[str, object]] = []
    for index, display in enumerate(display_tokens):
        spoken = normalise_token(display)
        for sub, text in enumerate(spoken):
            entry: dict[str, object] = {"i": index, "text": text, "display": display}
            if len(spoken) > 1:
                entry["sub"] = sub
            entries.append(entry)
    return entries
