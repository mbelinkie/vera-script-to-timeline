"""ElevenLabs Scribe v2 via OpenRouter: the recommended STT cloud recogniser.

Study evidence: best words on the halting presenter (WER 2.8% after script
reconciliation, names 23/23), fewest displaced words, best #53 take recovery.
Native word starts run late, so its anchors always go through the aligner.

Requires the project's stored cloud consent (Producer decision 4) and an
OpenRouter key in the environment (`OPENROUTER_API_KEY`). The key never
appears in artifacts, refusal messages or logs. Audio is sent as mono FLAC
(ffmpeg). Verbatim transcription; audio-event tagging off. Script keyterms
are optional and hashed into the artifact identity.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
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
    require_cloud_consent,
    require_language,
)

URL = "https://openrouter.ai/api/v1/audio/transcriptions"
MODEL = "elevenlabs/scribe-v2"
Transport = Callable[[str, dict[str, str], bytes, float], Json]


def _http_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> Json:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed: Json = json.loads(response.read())
        return parsed


def _flac(audio: AudioRef, ffmpeg: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="vera-flac-") as tmp:
        out = Path(tmp) / "audio.flac"
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(audio.path),
                    "-ac",
                    "1",
                    "-c:a",
                    "flac",
                    str(out),
                ],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as error:
            raise PortRefusal(
                "recognizer", "runtime-missing", "ffmpeg is not available."
            ) from error
        except subprocess.CalledProcessError as error:
            raise PortRefusal(
                "recognizer", "input-invalid", "Audio could not be encoded."
            ) from error
        return out.read_bytes()


def scribe_tokens(raw: Json) -> list[Token]:
    tokens = []
    for w in raw.get("words", []):
        kind = w.get("type", "word")
        text = str(w.get("word", w.get("text", ""))).strip()
        if kind == "spacing" or not text:
            continue
        start, end = w.get("start"), w.get("end")
        tokens.append(
            Token(
                text,
                "event" if kind == "audio_event" else "word",
                None if start is None else float(start),
                None if end is None else float(end),
                "word",
                w.get("logprob", w.get("confidence")),
            )
        )
    return tokens


class ElevenLabsCloudRecognizer:
    def __init__(
        self,
        *,
        keyterms: tuple[str, ...] | None = None,
        transport: Transport | None = None,
        ffmpeg: str = "ffmpeg",
        timeout_s: float = 600.0,
    ) -> None:
        self.keyterms, self.transport = keyterms, transport or _http_post
        self.ffmpeg, self.timeout_s = ffmpeg, timeout_s

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "cloud", "word")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        require_language(self.capabilities(), language, "recognizer")
        policy_id = require_cloud_consent(policy, "ElevenLabs via OpenRouter")
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise PortRefusal(
                "recognizer", "runtime-missing", "No OpenRouter key is configured."
            )
        options: Json = {"tag_audio_events": False}
        if self.keyterms:
            options["keyterms"] = list(self.keyterms)
        body = {
            "model": MODEL,
            "response_format": "verbose_json",
            "timestamp_granularities": ["word"],
            "language": language.split("-")[0],
            "input_audio": {
                "data": base64.b64encode(_flac(audio, self.ffmpeg)).decode(),
                "format": "flac",
            },
            "provider": {"options": {"elevenlabs": options}},
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            raw = self.transport(
                URL, headers, json.dumps(body).encode(), self.timeout_s
            )
        except urllib.error.HTTPError as error:
            retry = error.code in (408, 429) or error.code >= 500
            raise PortRefusal(
                "recognizer",
                "provider-failed",
                f"Cloud recogniser returned HTTP {error.code}.",
                retryable=retry,
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise PortRefusal(
                "recognizer",
                "provider-failed",
                "Cloud recogniser was unreachable.",
                retryable=True,
            ) from error
        tokens = scribe_tokens(raw)
        if not any(t.kind == "word" for t in tokens):
            raise PortRefusal(
                "recognizer",
                "provider-failed",
                "Cloud recogniser returned no words.",
                retryable=True,
            )
        params = {
            "model": MODEL,
            "verbatim": True,
            "tagAudioEvents": False,
            "via": "openrouter",
        }
        info = RecognizerInfo(
            "asr-cloud",
            "elevenlabs",
            "scribe-v2",
            str(raw.get("model", MODEL)),
            params,
            self.keyterms,
        )
        return recognition_artifact(
            audio, info, tokens, language=language, consent_policy=policy_id
        )
