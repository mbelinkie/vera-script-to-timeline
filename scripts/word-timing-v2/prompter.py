"""Parse a VERA prompter script into words, pronunciation guides and keyterms.

Conventions in the prompter text:
- `(on)` / `(off)` mark places where a take may restart. They are kept as
  restart points and are not words.
- `[BAH-ra BAH-da BAS-tu]` is a pronunciation guide. It covers the N words
  just before it, where N is the number of space-separated parts. `KAJ [kai]`
  covers one word.
- A line ending in ":" introduces a clip; the line's words are still read.

Keyterms (for recogniser vocabulary) are found automatically:
- quoted phrases;
- runs of capitalised words that do not start a sentence (`Tommy Cash`);
- any word missing from the pronunciation dictionary (`KAJ`, `Windows95Man`).
All-caps words that are in the dictionary (`REAL`, `DID`) are emphasis, not
names. Numerals and short dictionary words (`No`) are dropped.

Usage: prompter.py --script X.txt --dictionary english_us_arpa.dict --out prompter.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from textnorm import normalise_token

TOKEN = re.compile(r"\((?:on|off)\)|\[[^\]]+\]|[“\"][^”\"]+[”\"]|[^\s]+")


def load_dictionary(path: Path) -> set[str]:
    return {line.split()[0].casefold() for line in path.read_text(errors="ignore").splitlines() if line.strip()}


def parse(text: str, dictionary: set[str]) -> dict:
    words: list[dict] = []
    restarts: list[int] = []
    quotes: list[str] = []
    sentence_start = True
    for raw in TOKEN.findall(text.replace("’", "'")):
        if raw in ("(on)", "(off)"):
            restarts.append(len(words))
            continue
        if raw.startswith("["):
            parts = raw[1:-1].split()
            for word, guide in zip(words[-len(parts):], parts):
                word["guide"] = guide
            continue
        inner = raw
        if raw[0] in "“\"":
            inner = raw.strip("“”\"")
            quotes.append(inner.strip(" .,!?;:"))
        for piece in inner.split():
            display = piece.strip("“”\"()")
            spoken = normalise_token(display)
            if not spoken:
                continue
            words.append({"display": display.strip(".,!?;:"), "spoken": spoken,
                          "sentenceStart": sentence_start,
                          "capitalised": display[:1].isupper(),
                          "inDictionary": all(s in dictionary for s in spoken)})
            sentence_start = display.endswith((".", "!", "?", ":")) or display.endswith((".\"", "?\"", ".”"))

    keyterms: list[str] = []

    def add(term: str) -> None:
        term = term.strip(" .,!?;:")
        single = " " not in term
        if single and (term.isdigit() or (len(term) <= 3 and term.casefold() in dictionary)):
            return  # numerals and short common words are not useful vocabulary
        if term and term.casefold() not in {k.casefold() for k in keyterms}:
            keyterms.append(term)

    for quote in quotes:
        if len(quote.split()) <= 6:
            add(quote)
    run: list[str] = []
    for w in words + [{"capitalised": False, "sentenceStart": True, "display": ""}]:
        is_name = w["capitalised"] and not w["sentenceStart"] and not (w["display"].isupper() and w.get("inDictionary"))
        if is_name and w["display"] not in ("I", "I'm"):
            run.append(w["display"])
            continue
        if run:
            add(" ".join(run))
            run = []
    for w in words:
        if not w["inDictionary"]:
            add(w["display"])
    return {"words": words, "restartPoints": restarts,
            "guides": [{"index": n, "display": w["display"], "guide": w["guide"]} for n, w in enumerate(words) if "guide" in w],
            "keyterms": keyterms}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--dictionary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = parse(args.script.read_text(), load_dictionary(args.dictionary))
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(f'{len(result["words"])} words, {len(result["restartPoints"])} restart points, '
          f'{len(result["guides"])} guided words')
    print("keyterms:", result["keyterms"])


if __name__ == "__main__":
    main()
