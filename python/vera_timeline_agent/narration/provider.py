from __future__ import annotations

from typing import Protocol

from vera_timeline_agent.narration.models import ProviderResult, SynthesisRequest


class SpeechProviderError(RuntimeError):
    """A request cannot produce usable speech; callers must not retry blindly."""

    def __init__(
        self,
        message: str,
        *,
        request_rejected: bool = False,
        response_files: dict[str, bytes] | None = None,
    ) -> None:
        super().__init__(message)
        self.request_rejected = request_rejected
        self.response_files = response_files


class SpeechSynthesisProvider(Protocol):
    adapter_version: str

    def prepare_input(self, request: SynthesisRequest) -> bytes: ...

    def synthesize(self, request: SynthesisRequest) -> ProviderResult: ...
