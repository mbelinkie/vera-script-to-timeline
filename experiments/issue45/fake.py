"""Deterministic fake recogniser and aligner for product tests and conformance.

The fake recogniser "hears" a fixed script at a fixed pace; the fake aligner
times every unit from the recognition anchors and marks configured tokens
unaligned. Same inputs always give the same artifacts.
"""

from __future__ import annotations

from experiments.issue45.artifacts import (
    AlignedTime,
    AudioRef,
    Json,
    RecognizerInfo,
    Token,
    alignment_artifact,
    recognition_artifact,
    tool,
)
from experiments.issue45.normalize import units
from experiments.issue45.ports import (
    Capabilities,
    PortRefusal,
    ProjectPolicy,
    require_language,
)

WORD_S = 0.3


class FakeRecognizer:
    def __init__(self, words: list[str], *, start: float = 0.5) -> None:
        self.words, self.start = words, start

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "local", "word")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        require_language(self.capabilities(), language, "recognizer")
        duration = audio.duration_samples / audio.sample_rate
        if self.start + WORD_S * len(self.words) > duration:
            raise PortRefusal(
                "recognizer",
                "input-invalid",
                "Audio is shorter than the fake transcript.",
            )
        tokens = [
            Token(
                w,
                "word",
                self.start + n * WORD_S,
                self.start + (n + 1) * WORD_S,
                "word",
            )
            for n, w in enumerate(self.words)
        ]
        return recognition_artifact(
            audio,
            RecognizerInfo("asr-local", "vera-fake", "fake-recognizer", "1"),
            tokens,
            language=language,
            consent_policy=None,
        )


class FakeAligner:
    def __init__(self, unaligned: frozenset[int] = frozenset()) -> None:
        self.unaligned = unaligned

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "local", "acoustic")

    def align(
        self, audio: AudioRef, recognition: Json, *, policy: ProjectPolicy
    ) -> Json:
        require_language(
            self.capabilities(), recognition["identity"]["language"], "aligner"
        )
        tokens = recognition["tokens"]
        times = []
        for u in units([t["display"] if t["kind"] != "event" else "" for t in tokens]):
            t = tokens[u.token_index]
            if (
                u.token_index in self.unaligned
                or t["anchorStartMs"] is None
                or t["anchorEndMs"] is None
            ):
                times.append(AlignedTime(u, None, None))
                continue
            n = sum(1 for x in units([t["display"]]))
            span = (t["anchorEndMs"] - t["anchorStartMs"]) / 1000 / n
            s = t["anchorStartMs"] / 1000 + u.sub * span
            times.append(AlignedTime(u, s, s + span))
        return alignment_artifact(
            recognition,
            audio,
            tool("vera-fake-aligner", "1", {}),
            tool("vera-fake-segmentation", "1", {}),
            times,
        )
