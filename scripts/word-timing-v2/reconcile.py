"""Reconcile a recogniser transcript with the prompter script (T-CR).

The presenter reads the script in order but may restart (jump back), skip
words, misread, or add stumbles. The alignment walks the recogniser's words
and gives each one either a script position or "inserted". It does this with
dynamic programming over script positions:

- advancing to the next script word costs nothing;
- skipping ahead costs SKIP per skipped word, capped at JUMP;
- jumping back to any earlier position (a restart) costs JUMP;
- leaving a heard word unaligned (a stumble or ad-lib) costs INSERT;
- an aligned pair scores EXACT if identical, SOUNDALIKE if similar, and
  MISMATCH otherwise.

Only **names** take the script's spelling: script words that are keyterms,
carry a pronunciation guide, or are missing from the dictionary. A heard word
aligned to a name by sound-alike gets the name's spelling. So does an
unaligned heard word (a repeat or false start) that sounds like a name within
NEARBY script positions of where the reading was. No replacement happens when
both the heard word and the script word are ordinary dictionary words
("swede" vs "Swedes"), because that is a real word heard, maybe a misreading. Every other heard
word keeps its recognised text, so a real misreading is not "corrected" away.
Times are never changed.

Output fields per word, and who should read them:
- `text`: the spelling to use for **matching and timing**. It is the script's
  spelling when a heard word was a sound-alike of a script name, otherwise the
  heard word.
- `heard`: what the recogniser actually heard. This is the **presenter
  fidelity evidence**. The take stage (#53/#45) must read `heard`, not `text`,
  to detect misreadings, including mispronounced names, which are a reason to
  reject a take.
- `scriptIndex` / `scriptSpelling`: where the word sits in the script, and the
  script spelling applied (if any).

Usage: reconcile.py --tc T-C-x.json --prompter prompter.json --dictionary english_us_arpa.dict --out T-CR-x.json
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from prompter import load_dictionary
from textnorm import normalise_token

EXACT, SOUNDALIKE, MISMATCH = 3.0, 1.0, -2.0
INSERT, SKIP, JUMP = 1.5, 0.6, 4.0
SOUNDALIKE_RATIO = 0.6
NEARBY = 3


def sound_key(word: str) -> str:
    """Crude spelling-independent key: fold accents and common sound-alikes."""
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


def script_units(prompter: dict) -> list[dict]:
    names = {t.casefold() for term in prompter["keyterms"] for t in term.split()}
    units = []
    for w in prompter["words"]:
        is_name = (
            w["display"].casefold() in names or "guide" in w or not w["inDictionary"]
        )
        for spoken in w["spoken"]:
            units.append({"text": spoken, "display": w["display"], "name": is_name})
    return units


def align(hyp: list[str], script: list[dict]) -> list[int | None]:
    n_s = len(script)
    neg = float("-inf")
    # f[p+1]: best score with last aligned script position p (p = -1 means none yet)
    f = [0.0] + [neg] * n_s
    back: list[list[tuple[int, int | None]]] = []
    for word in hyp:
        pair = [
            EXACT
            if word == u["text"]
            else SOUNDALIKE
            if similar(word, u["text"])
            else MISMATCH
            for u in script
        ]
        new = [neg] * (n_s + 1)
        choice: list[tuple[int, int | None]] = [(0, None)] * (n_s + 1)
        for p1 in range(n_s + 1):  # stay: insert this word
            if f[p1] - INSERT > new[p1]:
                new[p1], choice[p1] = f[p1] - INSERT, (p1, None)
        # Predecessor state q = last aligned position + 1. Aligning to script j:
        #   q == j: advance (free); q < j: skip j - q words, cost min(SKIP*(j-q), JUMP);
        #   q > j: jump back (restart), cost JUMP.
        suffix_best, suffix_arg = [neg] * (n_s + 2), [0] * (n_s + 2)
        for q in range(n_s, -1, -1):
            if f[q] >= suffix_best[q + 1]:
                suffix_best[q], suffix_arg[q] = f[q], q
            else:
                suffix_best[q], suffix_arg[q] = suffix_best[q + 1], suffix_arg[q + 1]
        lin_best, lin_arg = neg, 0  # max over q < j of f[q] + SKIP*q
        pre_best, pre_arg = neg, 0  # max over q < j of f[q]
        for j in range(n_s):
            cands = [(f[j], j), (suffix_best[j + 1] - JUMP, suffix_arg[j + 1])]
            if lin_best > neg:
                cands.append((lin_best - SKIP * j, lin_arg))
                cands.append((pre_best - JUMP, pre_arg))
            score, src = max(cands)
            if score + pair[j] > new[j + 1]:
                new[j + 1], choice[j + 1] = score + pair[j], (src, j)
            if f[j] + SKIP * j > lin_best:
                lin_best, lin_arg = f[j] + SKIP * j, j
            if f[j] > pre_best:
                pre_best, pre_arg = f[j], j
        f = new
        back.append(choice)
    # trace back
    state = max(range(n_s + 1), key=lambda p1: f[p1])
    result: list[int | None] = [None] * len(hyp)
    for i in range(len(hyp) - 1, -1, -1):
        prev, j = back[i][state]
        result[i] = j
        state = prev
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--tc", "--prompter", "--dictionary", "--out"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    dictionary = load_dictionary(args.dictionary)
    tc = json.loads(args.tc.read_text())
    script = script_units(json.loads(args.prompter.read_text()))
    words = []
    for w in tc["words"]:
        if w.get("type") == "event":
            continue
        for text in normalise_token(str(w["text"])):
            words.append({**w, "text": text, "heard": text})
    mapping = align([w["text"] for w in words], script)
    changed = 0
    for n, (w, j) in enumerate(zip(words, mapping)):
        w["scriptIndex"] = j
        target = j
        if j is None:
            # Unaligned (a repeat, fragment or false start): look for a name near
            # where the reading was, within NEARBY positions of its aligned neighbours.
            near = [m for m in mapping[max(0, n - 3) : n + 4] if m is not None]
            pool = {
                k
                for m in near
                for k in range(max(0, m - NEARBY), min(len(script), m + NEARBY + 1))
            }
            hits = [
                k
                for k in sorted(pool)
                if script[k]["name"] and similar(w["text"], script[k]["text"])
            ]
            target = hits[0] if hits else None
        if (
            target is not None
            and script[target]["name"]
            and w["text"] != script[target]["text"]
            and similar(w["text"], script[target]["text"])
            and not (w["text"] in dictionary and script[target]["text"] in dictionary)
        ):
            w["text"] = script[target]["text"]
            w["scriptSpelling"] = script[target]["display"]
            changed += 1
    aligned = sum(j is not None for j in mapping)
    out = {
        "source": tc["source"].replace("T-C-", "T-CR-"),
        "provider": tc.get("provider"),
        "model": tc.get("model"),
        "words": [
            {"k": n, **{k: v for k, v in w.items() if k != "k"}}
            for n, w in enumerate(words)
        ],
        "transcript": " ".join(w["text"] for w in words),
        "fields": {
            "text": "spelling for matching and timing (script spelling for sound-alike names)",
            "heard": "recogniser's own word: presenter-fidelity evidence for the take stage; "
            "misreadings and mispronounced names show here",
        },
        "provenance": {
            "reconciledFrom": args.tc.name,
            "prompter": args.prompter.name,
            "weights": {
                "exact": EXACT,
                "soundalike": SOUNDALIKE,
                "mismatch": MISMATCH,
                "insert": INSERT,
                "skip": SKIP,
                "jump": JUMP,
                "ratio": SOUNDALIKE_RATIO,
            },
            "alignedToScript": aligned,
            "inserted": len(words) - aligned,
            "nameSpellingsChanged": changed,
        },
    }
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(
        f"{out['source']}: {aligned}/{len(words)} heard words aligned to script, "
        f"{len(words) - aligned} inserted, {changed} name spellings taken from script"
    )


if __name__ == "__main__":
    main()
