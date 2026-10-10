"""Adapter conformance suite (#168 draft §5): the minimum any engine must satisfy.

`check_pair` runs a recogniser and an aligner on one audio input and returns
human-readable failures (empty = conformant). The same suite applies to the
deterministic fakes and to every real adapter, so swapping engines never
changes what consumers can rely on.
"""

from __future__ import annotations

from experiments.issue45.artifacts import AudioRef, Json, schema_errors
from experiments.issue45.normalize import normalise_token
from experiments.issue45.ports import (
    AlignerPort,
    PortRefusal,
    ProjectPolicy,
    RecognizerPort,
)


def _expect_refusal(fn: object, code: str, label: str) -> list[str]:
    try:
        fn()  # type: ignore[operator]
    except PortRefusal as r:
        bad = (
            []
            if r.code == code
            else [f"{label}: refused with {r.code!r}, expected {code!r}"]
        )
        return bad + [f"{label}: refusal record {e}" for e in schema_errors(r.record())]
    return [f"{label}: expected a {code!r} refusal, got an artifact"]


def check_alignment(audio: AudioRef, recognition: Json, alignment: Json) -> list[str]:
    fails = [f"alignment schema: {e}" for e in schema_errors(alignment)]
    if alignment["identity"]["recognitionArtifactId"] != recognition["artifactId"]:
        fails.append("alignment does not reference its recognition artifact")
    tokens = recognition["tokens"]
    by_token: dict[int, list[Json]] = {}
    for w in alignment["words"]:
        if not 0 <= w["tokenIndex"] < len(tokens):
            fails.append(f"unit references missing token {w['tokenIndex']}")
            continue
        by_token.setdefault(w["tokenIndex"], []).append(w)
    for i, t in enumerate(tokens):
        expected = [] if t["kind"] == "event" else normalise_token(t["display"])
        got = [w["text"] for w in sorted(by_token.get(i, []), key=lambda w: w["sub"])]
        if got != expected:
            fails.append(
                f"normalisation map: token {i} {t['display']!r} -> {got}, "
                f"expected {expected}"
            )
    duration_ms = audio.duration_samples * 1000 // audio.sample_rate
    last = -1
    for w in alignment["words"]:
        if w["status"] == "unaligned":
            continue
        s, e = w["startMs"], w["endMs"]
        if not 0 <= s < e <= duration_ms + 1:
            fails.append(
                f"unit {w['tokenIndex']}.{w['sub']} has invalid bounds {s}-{e}"
            )
        if s < last:
            fails.append(
                f"unit {w['tokenIndex']}.{w['sub']} starts before the previous "
                "aligned unit"
            )
        last = max(last, s)
    return fails


def check_pair(
    recognizer: RecognizerPort,
    aligner: AlignerPort,
    audio: AudioRef,
    *,
    language: str,
    policy: ProjectPolicy,
) -> list[str]:
    fails: list[str] = []
    rec = recognizer.recognise(audio, language=language, policy=policy)
    fails += [f"recognition schema: {e}" for e in schema_errors(rec)]
    # Local engines must be deterministic. Cloud services are not run-to-run
    # deterministic (ElevenLabs returned 4 different spans on a repeat call of
    # recording B), so each cloud call is its own immutable artifact; adapters
    # must still be deterministic for an identical provider response, which
    # the transport-injected unit tests cover.
    if recognizer.capabilities().processing == "local" and (
        recognizer.recognise(audio, language=language, policy=policy)["artifactId"]
        != rec["artifactId"]
    ):
        fails.append("recognition is not deterministic for identical input")
    if rec["identity"]["recognizer"]["kind"] == "reference-text":
        fails.append("reference-text recognisers are evaluation-only (D-P009)")
    ali = aligner.align(audio, rec, policy=policy)
    fails += check_alignment(audio, rec, ali)
    if aligner.align(audio, rec, policy=policy)["artifactId"] != ali["artifactId"]:
        fails.append("alignment is not deterministic for identical input")
    fails += _expect_refusal(
        lambda: recognizer.recognise(audio, language="zz", policy=policy),
        "capability-missing",
        "unsupported language",
    )
    if recognizer.capabilities().processing == "cloud":
        fails += _expect_refusal(
            lambda: recognizer.recognise(
                audio, language=language, policy=ProjectPolicy()
            ),
            "consent-missing",
            "cloud without consent",
        )
    return fails
