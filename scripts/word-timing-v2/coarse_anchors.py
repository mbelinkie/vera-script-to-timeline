"""Coarse word anchors for segment assignment only (never scored).

Chirp 3 transcribes each VAD segment separately. A text alignment then maps its
words onto the reference entries, and entries left unmatched get the time of
their nearest matched neighbour. The output is a contract RESULT file used
only by `segment.py assign`.

Usage: coarse_anchors.py --vad vad.json --audio REC-16k.wav --tokens tokens.json --out anchors.json
"""

from __future__ import annotations

import argparse
import base64
import difflib
import io
import json
import subprocess
import urllib.request
from pathlib import Path

import soundfile

from textnorm import normalise_token, word_entries

PROJECT = "vera-word-timing"


def chirp3(pcm: bytes, token: str) -> list[dict[str, float | str]]:
    body = {"config": {"autoDecodingConfig": {}, "languageCodes": ["en-US"], "model": "chirp_3",
                       "features": {"enableWordTimeOffsets": True}},
            "content": base64.b64encode(pcm).decode()}
    url = f"https://us-speech.googleapis.com/v2/projects/{PROJECT}/locations/us/recognizers/_:recognize"
    request = urllib.request.Request(url, json.dumps(body).encode(), {
        "Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT, "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(request, timeout=300))
    words = []
    for result in data.get("results", []):
        for w in result["alternatives"][0].get("words", []):
            words.append({"word": w["word"], "start": float(w.get("startOffset", "0s")[:-1]),
                          "end": float(w.get("endOffset", "0s")[:-1])})
    return words


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--vad", "--audio", "--tokens", "--out"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    token = subprocess.check_output(["gcloud", "auth", "application-default", "print-access-token"], text=True).strip()
    audio, rate = soundfile.read(str(args.audio), dtype="int16")
    hyp: list[dict[str, float | str]] = []
    for start, end in json.loads(args.vad.read_text())["segments"]:
        buffer = io.BytesIO()
        soundfile.write(buffer, audio[int(start * rate):int(end * rate)], rate, format="WAV", subtype="PCM_16")
        for w in chirp3(buffer.getvalue(), token):
            for text in normalise_token(str(w["word"])):
                hyp.append({"text": text, "start": start + float(w["start"]), "end": start + float(w["end"])})

    entries = word_entries(json.loads(args.tokens.read_text()))
    times: list[tuple[float, float] | None] = [None] * len(entries)
    matcher = difflib.SequenceMatcher(a=[e["text"] for e in entries], b=[h["text"] for h in hyp], autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            h = hyp[block.b + k]
            times[block.a + k] = (float(h["start"]), float(h["end"]))
    matched = sum(t is not None for t in times)
    known = [n for n, t in enumerate(times) if t is not None]
    for n, t in enumerate(times):
        if t is None:
            nearest = min(known, key=lambda k: abs(k - n))
            times[n] = times[nearest]
    rows = []
    for entry, (s, e) in zip(entries, times):  # type: ignore[misc]
        row = {"i": entry["i"], "start": round(s, 3), "end": round(e, 3), "status": "aligned"}
        if "sub" in entry:
            row["sub"] = entry["sub"]
        rows.append(row)
    args.out.write_text(json.dumps({"aligner": "coarse-chirp3-anchor", "matchedEntries": matched,
                                    "totalEntries": len(entries), "hypothesisWords": len(hyp), "words": rows}, indent=1))
    print(f"matched {matched}/{len(entries)} entries; chirp words {len(hyp)}")


if __name__ == "__main__":
    main()
