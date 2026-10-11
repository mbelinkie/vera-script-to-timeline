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
    raw: list[tuple[float, str, float]] = []
    for event in json3.get("events", []):
        if "segs" not in event or event.get("aAppend"):
            continue
        t0 = event["tStartMs"]
        event_end = (t0 + event.get("dDurationMs", 0)) / 1000
        for seg in event["segs"]:
            text = seg.get("utf8", "").strip()
            if text:
                raw.append(((t0 + seg.get("tOffsetMs", 0)) / 1000, text, event_end))
    tokens = []
    for k, (start, text, event_end) in enumerate(raw):
        nxt = raw[k + 1][0] if k + 1 < len(raw) else event_end
        end = max(
            min(start + MAX_WORD_S, nxt if nxt > start else event_end), start + 0.01
        )
        event = text.startswith("[") and text.endswith("]")
        tokens.append(
            Token(
                text,
                "event" if event else "word",
                start,
                end,
                "word_start_with_derived_end",
            )
        )
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
