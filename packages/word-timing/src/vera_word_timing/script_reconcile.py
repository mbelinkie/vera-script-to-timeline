"""Prompter-script parsing and script reconciliation (Script to Timeline only).

Ported from the word-timing v2 study (`prompter.py`, `reconcile.py`). The
presenter reads the script in order but may restart, skip, misread or
stumble. A dynamic-programming walk gives every heard unit a script position
or "inserted" (advance free; skip SKIP per word capped at JUMP; restart JUMP;
insert INSERT; pair EXACT / SOUNDALIKE / MISMATCH).

Only **names** take the script's spelling (keyterms, words with a
pronunciation guide, or words missing from the pronunciation dictionary), and
never when both the heard and the script word are dictionary words
("swede" vs "Swedes" is a real word heard, maybe a misreading). `heard` keeps
the recogniser's word as presenter-fidelity evidence; `text` is used for
alignment. Times are never changed. Study result: names 23/23 (A) and 32/32
(B) for the best recognisers, with no non-name rewrites.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

from vera_word_timing.artifacts import Json, content_hash, with_id
from vera_word_timing.normalize import normalise_token

EXACT, SOUNDALIKE, MISMATCH = 3.0, 1.0, -2.0
INSERT, SKIP, JUMP = 1.5, 0.6, 4.0
SOUNDALIKE_RATIO = 0.6
NEARBY = 3
PARAMS = {
    "exact": EXACT,
    "soundalike": SOUNDALIKE,
    "mismatch": MISMATCH,
    "insert": INSERT,
    "skip": SKIP,
    "jump": JUMP,
    "ratio": SOUNDALIKE_RATIO,
    "nearby": NEARBY,
}
NOUN_CAPITALISING = {"de", "lb"}  # languages that capitalise common nouns
TOKEN = re.compile(r"\((?:on|off)\)|\[[^\]]+\]|[“\"][^”\"]+[”\"]|[^\s]+")


def load_dictionary_words(text: str, language: str = "en") -> set[str]:
    """Headwords of an MFA/ARPA pronunciation dictionary, folded like the tokens
    they are compared with (`normalise_token`: casefold for English, `lower()`
    elsewhere so "straße" stays distinct from "strasse")."""
    fold = str.casefold if language.split("-")[0] == "en" else str.lower
    return {fold(line.split()[0]) for line in text.splitlines() if line.strip()}


@dataclass(frozen=True)
class ScriptUnit:
    text: str
    display: str
    name: bool


@dataclass(frozen=True)
class Prompter:
    words: list[dict[str, Any]]
    restart_points: list[int]
    keyterms: list[str]
    language: str = "en"

    def units(self) -> list[ScriptUnit]:
        # Positive name evidence only: a pronunciation guide, or a word the script
        # capitalises somewhere other than at a sentence start. Sentence-initial
        # capitals ("Working home.") and dictionary absence alone never make a
        # word a name. German capitalises every noun, so there a capital also
        # needs the word to be missing from the dictionary.
        nouns_capitalised = self.language.split("-")[0] in NOUN_CAPITALISING
        names = {
            w["display"].casefold()
            for w in self.words
            if w["capitalised"]
            and not w["sentenceStart"]
            and w["display"] not in ("I", "I'm")
            and not (w["display"].isupper() and w["inDictionary"])
            and not (nouns_capitalised and w["inDictionary"])
        }
        out = []
        for w in self.words:
            is_name = w["display"].casefold() in names or "guide" in w
            out += [ScriptUnit(s, w["display"], is_name) for s in w["spoken"]]
        return out


def parse_prompter(text: str, dictionary: set[str], language: str = "en") -> Prompter:
    """`(on)`/`(off)` restart points, `[guide]` pronunciations, automatic keyterms."""
    words: list[dict[str, Any]] = []
    restarts: list[int] = []
    quotes: list[str] = []
    sentence_start = True
    for raw in TOKEN.findall(text.replace("\u2019", "'")):
        if raw in ("(on)", "(off)"):
            restarts.append(len(words))
            continue
        if raw.startswith("["):
            parts = raw[1:-1].split()
            for word, guide in zip(words[-len(parts) :], parts, strict=False):
                word["guide"] = guide
            continue
        inner = raw
        if raw[0] in '“"':
            inner = raw.strip('“”"')
            quotes.append(inner.strip(" .,!?;:"))
        for piece in inner.split():
            display = piece.strip('“”"()')
            spoken = normalise_token(display, language)
            if not spoken:
                continue
            words.append(
                {
                    "display": display.strip(".,!?;:"),
                    "spoken": spoken,
                    "sentenceStart": sentence_start,
                    "capitalised": display[:1].isupper(),
                    "inDictionary": all(s in dictionary for s in spoken),
                }
            )
            sentence_start = display.endswith((".", "!", "?", ":")) or display.endswith(
                ('."', '?"', ".”")
            )
    keyterms: list[str] = []

    def add(term: str) -> None:
        term = term.strip(" .,!?;:")
        if " " not in term and (
            term.isdigit() or (len(term) <= 3 and term.casefold() in dictionary)
        ):
            return
        if term and term.casefold() not in {k.casefold() for k in keyterms}:
            keyterms.append(term)

    for quote in quotes:
        if len(quote.split()) <= 6:
            add(quote)
    run: list[str] = []
    for w in [*words, {"capitalised": False, "sentenceStart": True, "display": ""}]:
        is_name = (
            w["capitalised"]
            and not w["sentenceStart"]
            and not (w["display"].isupper() and w.get("inDictionary"))
        )
        if is_name and w["display"] not in ("I", "I'm"):
            run.append(w["display"])
            continue
        if run:
            add(" ".join(run))
            run = []
    for w in words:
        if not w["inDictionary"]:
            add(w["display"])
    return Prompter(words, restarts, keyterms, language)


def sound_key(word: str) -> str:
    w = word.casefold()
    for a, b in (
        ("ä", "a"),
        ("ö", "o"),
        ("å", "a"),
        ("é", "e"),
        ("j", "y"),
        ("ph", "f"),
        ("ck", "k"),
        ("c", "k"),
        ("q", "k"),
        ("z", "s"),
        ("ts", "st"),
        ("ai", "ay"),
        ("ei", "ay"),
    ):
        w = w.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", w)


def similar(a: str, b: str) -> bool:
    if min(len(a), len(b)) < 3:
        return False
    return (
        difflib.SequenceMatcher(None, sound_key(a), sound_key(b)).ratio()
        >= SOUNDALIKE_RATIO
    )


def align_to_script(hyp: list[str], script: list[ScriptUnit]) -> list[int | None]:
    n_s = len(script)
    neg = float("-inf")
    f = [0.0] + [neg] * n_s  # f[p+1]: best score with last aligned script position p
    back: list[list[tuple[int, int | None]]] = []
    for word in hyp:
        pair = [
            EXACT
            if word == u.text
            else SOUNDALIKE
            if similar(word, u.text)
            else MISMATCH
            for u in script
        ]
        new = [neg] * (n_s + 1)
        choice: list[tuple[int, int | None]] = [(0, None)] * (n_s + 1)
        for p1 in range(n_s + 1):  # insert this word
            if f[p1] - INSERT > new[p1]:
                new[p1], choice[p1] = f[p1] - INSERT, (p1, None)
        suffix_best, suffix_arg = [neg] * (n_s + 2), [0] * (n_s + 2)
        for q in range(n_s, -1, -1):
            if f[q] >= suffix_best[q + 1]:
                suffix_best[q], suffix_arg[q] = f[q], q
            else:
                suffix_best[q], suffix_arg[q] = suffix_best[q + 1], suffix_arg[q + 1]
        lin_best, lin_arg, pre_best, pre_arg = neg, 0, neg, 0
        for j in range(n_s):
            cands = [(f[j], j), (suffix_best[j + 1] - JUMP, suffix_arg[j + 1])]
            if lin_best > neg:
                cands += [(lin_best - SKIP * j, lin_arg), (pre_best - JUMP, pre_arg)]
            score, src = max(cands)
            if score + pair[j] > new[j + 1]:
                new[j + 1], choice[j + 1] = score + pair[j], (src, j)
            if f[j] + SKIP * j > lin_best:
                lin_best, lin_arg = f[j] + SKIP * j, j
            if f[j] > pre_best:
                pre_best, pre_arg = f[j], j
        f = new
        back.append(choice)
    state = max(range(n_s + 1), key=lambda p1: f[p1])
    result: list[int | None] = [None] * len(hyp)
    for i in range(len(hyp) - 1, -1, -1):
        prev, pos = back[i][state]
        result[i] = pos
        state = prev
    return result


def reconcile(recognition: Json, script_text: str, dictionary_text: str) -> Json:
    """ScriptReconciliationV1 for a recognition artifact. Times are untouched."""
    language = recognition["identity"]["language"]
    dictionary = load_dictionary_words(dictionary_text, language)
    script = parse_prompter(script_text, dictionary, language).units()
    heard: list[tuple[int, int, str]] = []
    for t in recognition["tokens"]:
        if t["kind"] == "event":
            continue
        heard += [
            (t["index"], sub, s)
            for sub, s in enumerate(normalise_token(t["display"], language))
        ]
    mapping = align_to_script([h[2] for h in heard], script)
    units = []
    for n, ((index, sub, word), j) in enumerate(zip(heard, mapping, strict=True)):
        target = j
        if j is None:  # restart fragment / repeat: a name near where the reading was
            near = [m for m in mapping[max(0, n - 3) : n + 4] if m is not None]
            pool = {
                k
                for m in near
                for k in range(max(0, m - NEARBY), min(len(script), m + NEARBY + 1))
            }
            hits = [
                k
                for k in sorted(pool)
                if script[k].name and similar(word, script[k].text)
            ]
            target = hits[0] if hits else None
        text, spelling = word, None
        if (
            target is not None
            and script[target].name
            and word != script[target].text
            and similar(word, script[target].text)
            and not (word in dictionary and script[target].text in dictionary)
        ):
            text, spelling = script[target].text, script[target].display
        units.append(
            {
                "tokenIndex": index,
                "sub": sub,
                "heard": word,
                "text": text,
                "scriptIndex": j,
                "scriptSpelling": spelling,
            }
        )
    return with_id(
        {
            "schemaVersion": "script-reconciliation/v1",
            "units": units,
            "identity": {
                "recognitionArtifactId": recognition["artifactId"],
                "scriptHash": content_hash(script_text),
                "dictionaryHash": content_hash(dictionary_text),
                "parametersHash": content_hash(PARAMS),
            },
        }
    )
