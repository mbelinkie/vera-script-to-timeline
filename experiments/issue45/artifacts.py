"""Builders and validation for the #168 draft artifacts.

Artifact ids are `sha256:` over canonical JSON (UTF-8, sorted keys, compact
separators, no NaN) with `artifactId` omitted, so identical inputs give
identical ids and any identity change gives a new artifact. Times are integer
source milliseconds; missing timing stays null.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource

from experiments.issue45.normalize import Unit

Json = dict[str, Any]
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
RecognizerKind = Literal["asr-local", "asr-cloud", "caption", "reference-text"]
AnchorPrecision = Literal[
    "word", "word_start_with_derived_end", "segment", "cue", "none"
]


def canonical(obj: object) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def content_hash(obj: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def to_ms(seconds: float | None) -> int | None:
    if seconds is None:
        return None
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"invalid source time {seconds!r}")
    return round(seconds * 1000)


def with_id(body: Json) -> Json:
    if "artifactId" in body:
        raise ValueError("body already carries an artifactId")
    return {**body, "artifactId": content_hash(body)}


@dataclass(frozen=True)
class AudioRef:
    """A local audio file plus the prep chain that produced it from the original."""

    path: Path
    original_hash: str
    sample_rate: int
    duration_samples: int
    prep: tuple[Json, ...] = ()

    def identity(self) -> Json:
        return {
            "hash": self.original_hash,
            "sampleRate": self.sample_rate,
            "durationSamples": self.duration_samples,
        }


@dataclass(frozen=True)
class Token:
    display: str
    kind: Literal["word", "event", "filler"]
    start: float | None
    end: float | None
    precision: AnchorPrecision
    confidence: float | None = None


@dataclass(frozen=True)
class RecognizerInfo:
    kind: RecognizerKind
    provider: str
    model: str
    model_revision: str | None
    parameters: Json = field(default_factory=dict)
    keyterms: tuple[str, ...] | None = None


def recognition_artifact(
    audio: AudioRef,
    info: RecognizerInfo,
    tokens: list[Token],
    *,
    language: str,
    consent_policy: str | None,
) -> Json:
    cloud = info.kind == "asr-cloud"
    consent: Json = {
        "processing": "cloud" if cloud else "local",
        "policyId": consent_policy,
    }
    if cloud:
        consent["cloudProvider"] = info.provider
    return with_id(
        {
            "schemaVersion": "recognition-artifact/v1",
            "identity": {
                "audio": audio.identity(),
                "prep": list(audio.prep),
                "language": language,
                "recognizer": {
                    "kind": info.kind,
                    "provider": info.provider,
                    "model": info.model,
                    "modelRevision": info.model_revision,
                    "parametersHash": content_hash(info.parameters),
                    "keytermsHash": None
                    if info.keyterms is None
                    else content_hash(list(info.keyterms)),
                },
            },
            "consent": consent,
            "tokens": [
                {
                    "index": n,
                    "display": t.display,
                    "kind": t.kind,
                    "anchorStartMs": to_ms(t.start),
                    "anchorEndMs": to_ms(t.end),
                    "anchorPrecision": t.precision if t.start is not None else "none",
                    "providerConfidence": t.confidence,
                }
                for n, t in enumerate(tokens)
            ],
        }
    )


@dataclass(frozen=True)
class AlignedTime:
    unit: Unit
    start: float | None
    end: float | None

    @property
    def status(self) -> str:
        return (
            "acoustic"
            if self.start is not None and self.end is not None
            else "unaligned"
        )


def tool(name: str, version: str, parameters: Json, **extra: str | None) -> Json:
    out: Json = {
        "name": name,
        "version": version,
        "parametersHash": content_hash(parameters),
    }
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def alignment_artifact(
    recognition: Json,
    audio: AudioRef,
    aligner: Json,
    segmentation: Json,
    times: list[AlignedTime],
    *,
    reconcile_id: str | None = None,
    agreement: Json | None = None,
) -> Json:
    words = []
    for t in times:
        acoustic = t.status == "acoustic"
        words.append(
            {
                "tokenIndex": t.unit.token_index,
                "sub": t.unit.sub,
                "text": t.unit.text,
                "startMs": to_ms(t.start) if acoustic else None,
                "endMs": to_ms(t.end) if acoustic else None,
                "status": t.status,
                "alignerScore": None,
            }
        )
    body: Json = {
        "schemaVersion": "alignment-artifact/v1",
        "words": words,
        "identity": {
            "recognitionArtifactId": recognition["artifactId"],
            "reconcileArtifactId": reconcile_id,
            "audio": audio.identity(),
            "prep": list(audio.prep),
            "aligner": aligner,
            "segmentation": segmentation,
        },
    }
    if agreement is not None:
        body["agreement"] = agreement
    return with_id(body)


def agreement_block(
    words: list[Json],
    partner_times: dict[tuple[int, int], tuple[int | None, int | None]],
    partner: Json,
    tau_ms: int = 70,
) -> Json:
    """Accept a boundary only when the partner aligner places it within tau_ms."""
    bounds = []
    for w in words:
        if w["status"] != "acoustic":
            continue
        p_start, p_end = partner_times.get((w["tokenIndex"], w["sub"]), (None, None))
        for side, mine, theirs in (
            ("onset", w["startMs"], p_start),
            ("offset", w["endMs"], p_end),
        ):
            delta = None if theirs is None else mine - theirs
            verdict = (
                "accepted"
                if delta is not None and abs(delta) <= tau_ms
                else "needs_review"
            )
            bounds.append(
                {
                    "tokenIndex": w["tokenIndex"],
                    "sub": w["sub"],
                    "side": side,
                    "verdict": verdict,
                    "deltaMs": delta,
                }
            )
    return {"partner": partner, "tauMs": tau_ms, "boundaries": bounds}


@cache
def _validators() -> dict[str, Any]:
    schemas = {
        p.name: json.loads(p.read_text()) for p in SCHEMA_DIR.glob("*.schema.json")
    }
    resources = [(s["$id"], Resource.from_contents(s)) for s in schemas.values()]
    resources += [(name, Resource.from_contents(s)) for name, s in schemas.items()]
    registry: Registry[Any] = Registry().with_resources(resources)
    return {
        s["properties"]["schemaVersion"]["const"]: Draft202012Validator(
            s, registry=registry
        )
        for s in schemas.values()
    }


def schema_errors(doc: Json) -> list[str]:
    """Schema violations for an artifact or refusal record (empty = valid)."""
    validator = _validators().get(str(doc.get("schemaVersion")))
    if validator is None:
        return [f"unknown schemaVersion {doc.get('schemaVersion')!r}"]
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]
