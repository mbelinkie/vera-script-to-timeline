"""Pinned public speech and genuine offline alignment inputs for #312.

No network or speech engine is invoked here. The alignment result must come
from the existing MFA engine; numerical fixture marks are never substituted.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import uuid
import wave
from pathlib import Path
from typing import Any

from .narration.models import canonical_json_bytes

SOURCE_URL = "https://www.samplefiles.online/files/sample-speech-long.wav"
RIGHTS_URL = "https://www.samplefiles.online/sample-audio-for-transcription"
TRANSCRIPT_URL = "https://www.samplefiles.online/files/sample-speech-transcript.txt"
SOURCE_SHA256 = "4fc321495965ba347e9c71b7680da2c81f06d4ebbe538ef8b4f4ce40970aaf8b"
TRANSCRIPT_SHA256 = "1a13386dbb4ff8e9078d4d7888e699b1af953e6d9df40cc5687b98e28e04625d"
TEXT = (
    "This long form speech sample was generated for testing transcription pipelines "
    "end to end. It contains several sentences with varied vocabulary, numbers like "
    "forty two and nineteen eighty four, and common technical words such as audio, "
    "sample rate, waveform, and transcript. A good speech to text test file should "
    "exercise punctuation, pauses, and longer utterances, because real world "
    "recordings are rarely short or clean. If your model can transcribe this "
    "paragraph accurately, your pipeline handles sustained input, not just single "
    "words."
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def words() -> list[str]:
    return TEXT.split()


def verify_source(root: Path) -> tuple[bytes, dict[str, Any]]:
    """Bind the small downloaded WAV, exact transcript and retained rights page."""
    if any(part.is_symlink() for part in (root.absolute(), *root.absolute().parents)):
        raise ValueError("symbolic-link source refused")
    paths = [
        root / name for name in ("source-long.wav", "transcript.txt", "rights.html")
    ]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("complete regular source files required")
    raw, transcript, rights = (path.read_bytes() for path in paths)
    if digest(raw) != SOURCE_SHA256 or digest(transcript) != TRANSCRIPT_SHA256:
        raise ValueError("pinned public source or transcript differs")
    if b"CC0" not in rights or b"synthesized" not in rights:
        raise ValueError("retained first-party rights declaration required")
    with wave.open(io.BytesIO(raw), "rb") as stream:
        if (
            stream.getnchannels(),
            stream.getsampwidth(),
            stream.getframerate(),
            stream.getnframes(),
            stream.getcomptype(),
        ) != (1, 2, 16000, 615969, "NONE"):
            raise ValueError("public speech PCM profile differs")
        pcm = stream.readframes(stream.getnframes())
    return pcm, {
        "schemaVersion": "issue-312-public-speech-source/v1",
        "url": SOURCE_URL,
        "sha256": "sha256:" + SOURCE_SHA256,
        "transcriptUrl": TRANSCRIPT_URL,
        "transcriptSha256": "sha256:" + TRANSCRIPT_SHA256,
        "rightsUrl": RIGHTS_URL,
        "rightsSha256": "sha256:" + digest(rights),
        "license": "CC0-1.0",
        "originalSynthesizer": "eSpeak NG 1.51 formant synthesis (source declaration)",
        "text": TEXT,
        "wordCount": len(words()),
        "sampleRate": 16000,
        "durationSamples": len(pcm) // 2,
    }


def prepare_alignment(root: Path, output: Path) -> Path:
    """Create the existing MFA engine's segment file, without running it."""
    pcm, manifest = verify_source(root)
    value = {
        "audio": "source-long.wav",
        "offsetSec": 0,
        "segments": [
            {
                "id": "issue312-public-long",
                "start": 0,
                "end": len(pcm) / 2 / 16000,
                "words": [
                    {"i": index, "text": word} for index, word in enumerate(words())
                ],
            }
        ],
    }
    with output.open("xb") as stream:
        stream.write(canonical_json_bytes(value))
    with output.with_suffix(".source.json").open("xb") as stream:
        stream.write(canonical_json_bytes(manifest))
    return output


def checked_alignment(
    value: dict[str, Any], duration_samples: int = 615969
) -> list[dict[str, Any]]:
    """Refuse failed, partial, unordered or out-of-extent MFA output."""
    if (
        value.get("aligner") != "A-MFA"
        or value.get("variant") != "english_us_arpa"
        or value.get("provenance", {}).get("settings", {}).get("mfaExitCode") != 0
        or not value.get("provenance", {}).get("models")
    ):
        raise ValueError("successful pinned MFA provenance required")
    result = value.get("words")
    if not isinstance(result, list) or len(result) != len(words()):
        raise ValueError("complete exact transcript alignment required")
    previous_start, previous_end = -1, -1
    checked = []
    for index, (word, row) in enumerate(zip(words(), result, strict=True)):
        if row.get("i") != index or row.get("status") != "aligned":
            raise ValueError("unaligned or reordered word refused")
        start, end = row.get("start"), row.get("end")
        if (
            type(start) not in {int, float}
            or type(end) not in {int, float}
            or not math.isfinite(start)
            or not math.isfinite(end)
        ):
            raise ValueError("finite measured word bounds required")
        # MFA's engine emits millisecond precision. Preserve it as source samples.
        first, last = round(start * 16000), round(end * 16000)
        if not (
            0 <= first < last <= duration_samples
            and first > previous_start
            and first >= previous_end
        ):
            raise ValueError("invalid measured word interval")
        checked.append({"text": word, "startSample": first, "endSample": last})
        previous_start, previous_end = first, last
    return checked


def row_recipes(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    """Two complete sentence groups near 45 words, alternating across 30 rows.

    A split must occur in a measured quiet gap. The alternate uses the other
    complete passage, so a one-row edit replaces the whole row rather than
    cutting an old narration asset.
    """
    aligned = checked_alignment(alignment)
    candidates = [
        index + 1
        for index, word in enumerate(words()[:-1])
        if word.endswith(".")
        and 35 <= index + 1 <= 55
        and aligned[index + 1]["startSample"] > aligned[index]["endSample"]
    ]
    if not candidates:
        raise ValueError("no near-45-word sentence split has a measured quiet gap")
    split = min(candidates, key=lambda index: abs(index - len(aligned) / 2))
    cut = (aligned[split - 1]["endSample"] + aligned[split]["startSample"]) // 2
    recipes = []
    for first_word, last_word, first_sample, last_sample in (
        (0, split, 0, cut),
        (split, len(aligned), cut, 615969),
    ):
        selected = aligned[first_word:last_word]
        text = " ".join(word["text"] for word in selected)
        tokens = []
        for index, match in enumerate(re.finditer(r"\S+", text)):
            source = selected[index]
            tokens.append(
                {
                    "text": match.group(),
                    "startOffset": match.start(),
                    "endOffset": match.end(),
                    "startSample": source["startSample"] - first_sample,
                    "endSample": source["endSample"] - first_sample,
                }
            )
        recipes.append(
            {
                "text": text,
                "firstSample": first_sample,
                "exclusiveSample": last_sample,
                "tokens": tokens,
            }
        )
    return recipes


def prepare_rows(
    source_root: Path, alignment_path: Path, output: Path, rows: int
) -> Path:
    """Import public speech through the normal local cache/normalizer/measurement.

    This adapter replays recorded public PCM with genuine MFA-derived marks;
    it never synthesizes speech or calls a provider. Its provenance explicitly
    names both the public recording and the offline source of word starts.
    """
    from .narration.cache import NarrationCache
    from .narration.configuration import PricingPolicy
    from .narration.measure import load_asset, measure_asset
    from .narration.models import ProviderResult, ProviderTimingMark, VoiceProfile
    from .narration.normalize import Normalizer
    from .narration.service import NarrationService, ServiceConfig

    if rows not in {6, 30}:
        raise ValueError("six rehearsal or thirty representative rows required")
    pcm, source = verify_source(source_root)
    alignment_raw = alignment_path.read_bytes()
    recipes = row_recipes(json.loads(alignment_raw))
    root = output.absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("symbolic-link output refused")
    root.mkdir(parents=True, exist_ok=False)
    cache = NarrationCache(root / "cache")
    profile = VoiceProfile(
        profile_id="issue312-public-cc0-replay-v1",
        provider="public_cc0_replay",
        region="offline",
        engine="recorded-espeak-ng-1.51",
        voice_id="SampleFiles-formant",
        voice_version=SOURCE_SHA256,
        language="en-US",
    )

    def entity(label: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:issue312:{label}"))

    records = []
    for ordinal in range(rows + 1):
        alternate = ordinal == rows
        row_index = 0 if alternate else ordinal
        recipe = recipes[1 if alternate else ordinal % 2]
        block = {
            "type": "narration",
            "id": entity(f"row:{row_index}"),
            "version": 2 if alternate else 1,
            "text": recipe["text"],
            "tokens": [
                {
                    "id": entity(
                        f"row:{row_index}:token:{index}:v{2 if alternate else 1}"
                    ),
                    "value": token["text"],
                    "startOffset": token["startOffset"],
                    "endOffset": token["endOffset"],
                }
                for index, token in enumerate(recipe["tokens"])
            ],
        }
        raw_pcm = pcm[recipe["firstSample"] * 2 : recipe["exclusiveSample"] * 2]
        # A small disclosed, row-specific quiet tail gives independent PCM
        # identities without changing speech or forcing a nominal duration.
        raw_pcm += bytes((1600 + ordinal) * 2)
        marks = tuple(
            ProviderTimingMark(
                kind="word",
                time_ms=round(token["startSample"] / 16),
                start_byte=token["startOffset"],
                end_byte=token["endOffset"],
                start_utf16=token["startOffset"],
                end_utf16=token["endOffset"],
                value=token["text"],
                time_sample=token["startSample"],
                sample_rate=16000,
            )
            for token in recipe["tokens"]
        )
        replay_input = canonical_json_bytes(
            {
                "source": source,
                "alignmentHash": "sha256:" + digest(alignment_raw),
                "ordinal": ordinal,
                "recipe": recipe,
                "wordStartAuthority": "offline MFA alignment; no native TTS marks",
            }
        )

        class PinnedPublicReplay:
            adapter_version = "issue312-pinned-public-replay/v1"

            def __init__(
                self,
                text: str,
                input_bytes: bytes,
                audio: bytes,
                timing: tuple[ProviderTimingMark, ...],
            ) -> None:
                self.text = text
                self.input_bytes = input_bytes
                self.pcm = audio
                self.marks = timing

            def prepare_input(self, request: Any) -> bytes:
                if request.text != self.text:
                    raise ValueError("public replay text differs")
                return self.input_bytes

            def synthesize(self, request: Any) -> ProviderResult:
                return ProviderResult(
                    audio_bytes=self.pcm,
                    audio_format="pcm_s16le",
                    sample_rate=16000,
                    channels=1,
                    provider_input=self.prepare_input(request),
                    timing_marks=self.marks,
                    provider_input_format="json",
                    provenance={
                        "provider": "public_cc0_replay",
                        "region": "offline",
                        "engine": profile.engine,
                        "voiceId": profile.voice_id,
                        "voiceVersion": profile.voice_version,
                        "wordStartAuthority": "offline MFA English alignment",
                    },
                )

        service = NarrationService(
            cache=cache,
            provider=PinnedPublicReplay(recipe["text"], replay_input, raw_pcm, marks),
            normalizer=Normalizer(),
            config=ServiceConfig(
                profile=profile,
                max_cost_usd=0,
                data_policy_attestation="public_cc0_offline_replay",
                pricing_policy=PricingPolicy("offline-zero/v1", "characters", 0),
            ),
        )
        asset = service.process_block(block)
        if asset.status != "ready":
            raise ValueError(
                f"public narration normalization refused: {asset.failure_reason}"
            )
        key = f"{asset.block_id}/{asset.asset_id}"
        locator = f"narration-measurements/{asset.asset_id}.measurement.json"
        measured = measure_asset(
            load_asset(cache, key), block, artifact_locator=locator
        )
        folder = root / "narration-measurements"
        folder.mkdir(exist_ok=True)
        (root / locator).write_bytes(measured.artifact_bytes)
        evidence_path = folder / f"{asset.asset_id}.boundary-evidence.json"
        evidence_path.write_bytes(canonical_json_bytes(measured.evidence))
        records.append(
            {
                "ordinal": ordinal,
                "alternate": alternate,
                "block": block,
                "assetKey": key,
                "evidence": measured.evidence,
                "evidenceFile": str(evidence_path.relative_to(root)),
                "measurementFile": locator,
                "audioFile": "cache/" + asset.locators["audio"],
                "timingFile": "cache/" + asset.locators["timing"],
            }
        )
    result = root / "speech-rows.json"
    result.write_bytes(
        canonical_json_bytes(
            {
                "schemaVersion": "issue-312-public-speech-rows/v1",
                "source": source,
                "alignmentHash": "sha256:" + digest(alignment_raw),
                "alignmentProvenance": json.loads(alignment_raw)["provenance"],
                "onsetLimitation": "MFA onsets; no native TTS speech marks available",
                "rows": records,
            }
        )
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alignment", type=Path)
    parser.add_argument("--rows", type=int, default=6)
    arguments = parser.parse_args()
    if arguments.alignment:
        print(
            prepare_rows(
                arguments.source_root,
                arguments.alignment,
                arguments.output,
                arguments.rows,
            )
        )
    else:
        print(prepare_alignment(arguments.source_root, arguments.output))
