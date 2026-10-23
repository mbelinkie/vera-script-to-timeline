from __future__ import annotations

from typing import Protocol

from vera_timeline_agent.narration.models import ProviderResult, SynthesisRequest


class SpeechProviderError(RuntimeError):
    """A request cannot produce usable speech; callers must not retry blindly."""


class SpeechSynthesisProvider(Protocol):
    adapter_version: str

    def prepare_input(self, request: SynthesisRequest) -> bytes: ...

    def synthesize(self, request: SynthesisRequest) -> ProviderResult: ...
