"""RecognizerPort / AlignerPort (D-P009, #168 draft).

Ports return an artifact (a schema-valid dict) or raise `PortRefusal`. They
never fall back to another provider or to cloud; a missing local runtime is a
visible `runtime-missing` refusal. Provider types, paths and errors stay inside
adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from experiments.issue45.artifacts import AudioRef, Json

Port = Literal["recognizer", "aligner", "audio-prep"]
RefusalCode = Literal[
    "capability-missing",
    "runtime-missing",
    "consent-missing",
    "input-invalid",
    "provider-failed",
    "timeout",
    "cancelled",
]


class PortRefusal(Exception):
    def __init__(
        self, port: Port, code: RefusalCode, message: str, *, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.port, self.code, self.retryable = port, code, retryable

    def record(self) -> Json:
        return {
            "schemaVersion": "port-refusal/v1",
            "port": self.port,
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class Capabilities:
    languages: frozenset[str]
    processing: Literal["local", "cloud"]
    timing: Literal[
        "word", "word_start_with_derived_end", "segment", "cue", "none", "acoustic"
    ]


@dataclass(frozen=True)
class ProjectPolicy:
    """Per-project settings a port must respect.

    Producer decision 4: cloud recognition needs a stored consent policy.
    """

    cloud_consent_policy_id: str | None = None


class RecognizerPort(Protocol):
    def capabilities(self) -> Capabilities: ...

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json: ...


class AlignerPort(Protocol):
    def capabilities(self) -> Capabilities: ...

    def align(
        self, audio: AudioRef, recognition: Json, *, policy: ProjectPolicy
    ) -> Json: ...


def require_cloud_consent(policy: ProjectPolicy, provider: str) -> str:
    if not policy.cloud_consent_policy_id:
        raise PortRefusal(
            "recognizer",
            "consent-missing",
            f"Cloud recognition with {provider} needs this project's stored "
            "cloud consent.",
        )
    return policy.cloud_consent_policy_id


def require_language(
    caps: Capabilities, language: str, port: Literal["recognizer", "aligner"]
) -> None:
    if language.split("-")[0] not in caps.languages:
        raise PortRefusal(
            port,
            "capability-missing",
            f"Language {language!r} is not supported by this profile.",
        )
