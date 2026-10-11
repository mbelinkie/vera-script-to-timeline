"""YouTube automatic captions as a RecognizerPort source (Producer decision 3).

Reads yt-dlp's json3 caption file (fetching is the caller's job, inside the
product's authorised acquisition flow). Auto captions carry a start per word
and no end, so anchors are `word_start_with_derived_end`: end = min(next word
start, start + 0.5 s), capped at the caption event end. Bracketed tags such as
`[Music]` become events. Measured on two keyed recordings: native starts run
64-108 ms late (median), so captions are anchors for the aligner, never cuts.
"""

from __future__ import annotations

import json
from pathlib import Path

from vera_word_timing.artifacts import (
    AudioRef,
    Json,
    RecognizerInfo,
    Token,
    recognition_artifact,
)
from vera_word_timing.ports import (
    Capabilities,
    PortRefusal,
    ProjectPolicy,
    require_language,
)

MAX_WORD_S = 0.5


def caption_tokens(json3: Json) -> list[Token]:
    """Tokens from a json3 caption file, honest about what timing it carries.

    Auto captions: one word per segment with its own offset, so each word gets
    a real start; its end is derived (next word start, at most +0.5 s) and
    never runs past its caption event. Manual captions: a segment holds a
    whole line with no per-word offsets, so its words carry the cue interval
    with `cue` precision instead of invented word starts.
    """
    tokens: list[Token] = []
    starts: list[tuple[int, float, float]] = []  # (token index, start, event end)
    for event in json3.get("events", []):
        if "segs" not in event or event.get("aAppend"):
            continue
        t0 = event["tStartMs"] / 1000
        event_end = max(t0, t0 + event.get("dDurationMs", 0) / 1000)
        segs = [seg for seg in event["segs"] if seg.get("utf8", "").strip()]
        per_word = len(segs) > 1 or any("tOffsetMs" in seg for seg in segs)
        for seg in segs:
            text = seg["utf8"].strip()
            if text.startswith("[") and text.endswith("]"):
                tokens.append(Token(text, "event", t0, event_end, "cue"))
                continue
            words = text.split()
            if per_word and len(words) == 1:
                start = t0 + seg.get("tOffsetMs", 0) / 1000
                starts.append((len(tokens), start, event_end))
                tokens.append(
                    Token(words[0], "word", start, start, "word_start_with_derived_end")
                )
            else:
                tokens.extend(Token(w, "word", t0, event_end, "cue") for w in words)
    for n, (index, start, event_end) in enumerate(starts):
        nxt = starts[n + 1][1] if n + 1 < len(starts) else event_end
        cap = min(start + MAX_WORD_S, event_end, nxt if nxt > start else event_end)
        end = max(cap, start + 0.01) if event_end > start else start + 0.01
        t = tokens[index]
        tokens[index] = Token(t.display, t.kind, start, end, t.precision)
    return tokens


class YouTubeCaptionRecognizer:
    def __init__(self, json3_path: Path) -> None:
        self.json3_path = json3_path

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "local", "word_start_with_derived_end")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        require_language(self.capabilities(), language, "recognizer")
        try:
            data = json.loads(self.json3_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PortRefusal(
                "recognizer", "input-invalid", "Caption file is missing or not json3."
            ) from error
        tokens = caption_tokens(data)
        if not any(t.kind == "word" for t in tokens):
            raise PortRefusal(
                "recognizer", "input-invalid", "Caption file has no words."
            )
        info = RecognizerInfo(
            "caption",
            "youtube",
            "auto-captions",
            None,
            {"format": "json3", "maxWordS": MAX_WORD_S},
        )
        return recognition_artifact(
            audio, info, tokens, language=language, consent_policy=None
        )
