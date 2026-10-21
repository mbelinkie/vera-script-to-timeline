"""Prepare #215 generated-narration (Polly campaign) baseline packages.

Every audible track here is campaign-generated Amazon Polly speech (#182
campaign ``issue182-20261020``).  No recorded or supplied audio is used:

* A/C/D: the campaign baseline narration asset (cache WAV + its measured
  ``measured_audio_boundaries/v1`` evidence) over a narration row extended to two
  placeholder-slate picture slots, so a picture boundary can move inside the row.
* B: two linked-AV picture clips whose audio stream is *derived from campaign
  generated Polly speech*: the campaign baseline WAV is decoded and two distinct
  slices, cut on the 2002-sample frame grid (24000/1001 fps at 48 kHz), are
  written as stereo pcm_s24le and muxed into synthetic picture MOVs.  There is no
  recorded, quoted, presenter or music audio.
* B67: the trimmed (67-frame) preparation of clip 1.  Its requirement key is the
  honest identity of its inputs (requestedRange included), so it differs from the
  baseline key; the revision core adopts the replacement's own key.  The receipt
  and binding are used as prepared, never re-keyed.

No provider/AWS calls; nothing is written under the campaign root.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import math
import sys
import uuid
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tests"))
sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from issue174_media_fixture import (  # noqa: E402
    _mux_audio,
    generate_synthetic_media,
)
from issue178_qualification_fixture import (  # noqa: E402
    _compile,
    _refresh_document_binding,
)
from issue215_real_fixture import (  # noqa: E402
    _decoded_stereo_channel_hashes,
    _file_hash,
    _fresh_directory,
    _read_json,
    _write_json,
)
from test_issue174_real_media import issue174_descriptor  # noqa: E402
from vera_timeline_agent import (  # noqa: E402
    qualification_output_package_v2 as _package,
)
from vera_timeline_agent import qualification_output_native_v2 as _native  # noqa: E402
from vera_timeline_agent.media_preparation import (  # noqa: E402
    MediaTools,
    PreparationAuthorization,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import identity_hash  # noqa: E402
from vera_timeline_agent.qualification_output_package_v2 import (  # noqa: E402
    MATRIX_PROFILE,
    admit_qualification_package_v2,
)
from vera_timeline_agent.v2_package import (  # noqa: E402
    _render_slate,
    build_v2_package,
)

Json = dict[str, Any]
TARGET_RATE = Fraction(24000, 1001)
FRAME_SAMPLES = 2002
BASELINE_DOCUMENT = (
    REPOSITORY_ROOT / "tests/data/issue182/campaign/baseline.v2.script-document.json"
)
TEMPLATE = (
    REPOSITORY_ROOT
    / "tests/data/authoring_v2/issue_173/compiler/selected-clip-ntsc.input.golden.json"
)
# The movable picture boundary sits before this baseline token ("crosses").
BOUNDARY_TOKEN_INDEX = 5
OMISSION_WORD = "slowly"
B_CLIPS = (("selected", 91, 111, (11, 51, 99)), ("downstream", 48, 68, (12, 34, 57)))
B_SOURCE_ORIGIN_FRAME = 3_000
B_SOURCE_IN_OFFSET = 10


@contextlib.contextmanager
def matrix_preparation_root(root: Path) -> Iterator[None]:
    """Point matrix admission at ``root`` unless it is already inside the real root.

    Matrix admission only trusts ``<root>/.../published/<key>/receipt.json`` below
    ``MATRIX_PREPARATION_ROOT``; a coordinator writing under the real root needs no
    override, fixtures and tests writing elsewhere do.
    """
    original = _package.MATRIX_PREPARATION_ROOT
    if root.is_relative_to(original):
        yield
        return
    _package.MATRIX_PREPARATION_ROOT = root
    try:
        yield
    finally:
        _package.MATRIX_PREPARATION_ROOT = original


def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-generated:{name}"))


# ----------------------------------------------------------------- campaign


@dataclass(frozen=True)
class Campaign:
    root: Path
    run: str
    evidence: Json
    evidence_path: Path
    measurement_path: Path
    timing_path: Path
    wav_path: Path

    @property
    def block_id(self) -> str:
        return cast(str, self.evidence["blockId"])

    @property
    def evidence_paths(self) -> dict[str, dict[str, Path]]:
        return {
            self.block_id: {
                "timing": self.timing_path,
                "measurement": self.measurement_path,
            }
        }


def load_campaign(root: Path, run: str = "baseline") -> Campaign:
    """Locate the one measured evidence row of a campaign run (read-only)."""
    root = root.resolve()
    folder = root / "out" / run / "narration-measurements"
    rows = sorted(folder.glob("*.boundary-evidence.json"))
    if len(rows) != 1:
        raise ValueError(f"expected exactly one measured evidence row in {run}")
    evidence = _read_json(rows[0])
    verification = evidence["verification"]
    if verification.get("method") != "measured_audio_boundaries/v1":
        raise ValueError("campaign evidence is not measured audio boundaries")
    measurement = root / "out" / verification["measurementArtifactLocator"]
    wav = root / "cache" / evidence["audio"]["locator"]
    timing = wav.parent / "timing.json"
    for path in (measurement, wav, timing):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"campaign input missing: {path.name}")
    if _file_hash(wav) != evidence["audio"]["audioHash"]:
        raise ValueError("campaign narration WAV differs from its evidence")
    return Campaign(root, run, evidence, rows[0], measurement, timing, wav)


# ----------------------------------------------------------- A/C document


def extended_baseline_document(campaign: Campaign) -> Json:
    """The campaign baseline with two placeholder-slate slots and audio muted."""
    document = _read_json(BASELINE_DOCUMENT)
    row = next(b for b in document["activeDraft"]["blocks"] if b["type"] == "narration")
    if row["id"] != campaign.block_id:
        raise ValueError("baseline document row differs from the campaign evidence")
    if [t["id"] for t in row["tokens"]] != [
        t["tokenId"] for t in campaign.evidence["tokens"]
    ]:
        raise ValueError("baseline tokens differ from the campaign evidence")
    sequence = row["primaryVisualSequence"]
    first = sequence["slots"][0]
    first["payload"] = _slate_payload("first", "ISSUE 215 GENERATED SLATE 1")
    token = row["tokens"][BOUNDARY_TOKEN_INDEX]
    second = {
        "id": _uuid("A:slot-2"),
        "kind": "content",
        "relation": {"kind": "sequential"},
        "boundaryBefore": {
            "kind": "spoken_word",
            "anchor": {
                "blockId": row["id"],
                "tokenId": token["id"],
                "quotedWord": token["value"],
                "anchorVersion": 1,
                "affinity": "before",
            },
        },
        "payload": _slate_payload("second", "ISSUE 215 GENERATED SLATE 2"),
        "playoutPolicy": "match_structural_interval",
        "version": 1,
    }
    sequence["slots"] = [first, second]
    sequence["version"] = int(sequence["version"]) + 1
    return document


def _slate_payload(label: str, text: str) -> Json:
    return {
        "kind": "visual",
        "payloadId": _uuid(f"A:payload:{label}"),
        "pictureKind": "intentional_placeholder",
        "source": {"kind": "intentional_placeholder", "text": text},
        "sourceUsage": None,
        "audioPolicy": "mute",
        "framingPolicy": "contain",
    }


def _base_dependencies(document: Json, label: str) -> Json:
    template = _read_json(TEMPLATE)
    dependencies = copy.deepcopy(template["dependencies"])
    source_audio_track = dependencies["roles"]["sourceAudioTrackIds"][0]
    for track in dependencies["tracks"]:
        if track["id"] == source_audio_track:
            track["index"] = 2
            break
    dependencies["compiler"]["sourceHash"] = _file_hash(
        REPOSITORY_ROOT / "packages/contracts/src/compiler-core-v2.ts"
    )
    for field in ("buildId", "manifestId", "reportId"):
        dependencies["build"][field] = _uuid(f"{label}:{field}")
    dependencies["document"]["documentId"] = document["id"]
    return cast(dict[str, Any], dependencies)


def prepare_narration_case(
    campaign: Campaign, output_root: Path, *, label: str, output_name: str
) -> Json:
    """Compile, package and admit (matrix profile) the measured-narration baseline."""
    case_root = output_root / output_name
    _fresh_directory(case_root)
    document = extended_baseline_document(campaign)
    dependencies = _base_dependencies(document, label)
    dependencies["occurrenceResolutions"] = []
    dependencies["preparedMedia"] = []
    dependencies["narrationTimingMaps"] = []
    dependencies["presenterAlignmentResolutions"] = []
    dependencies["narrationBoundaryEvidence"] = [copy.deepcopy(campaign.evidence)]
    audio = campaign.evidence["audio"]
    duration = Fraction(int(audio["durationSamples"]), int(audio["sampleRate"]))
    dependencies["timeline"]["durationFrames"] = math.ceil(duration * TARGET_RATE)
    _refresh_document_binding(document, dependencies)
    inputs = case_root / "inputs"
    document_path = inputs / "script-document-v2.json"
    dependencies_path = inputs / "compiler-dependencies-v2.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    manifest, report = _compile(document_path, dependencies_path)
    if report.get("status") != "ready":
        raise ValueError("compiler report is not ready")

    media_paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        if "narrationAudio" in source:
            if source["narrationAudio"]["audioHash"] != audio["audioHash"]:
                raise ValueError("compiled narration differs from the campaign asset")
            media_paths[f"source:{source['id']}"] = campaign.wav_path
    slates = 0
    for event in manifest["events"]:
        if (
            event["kind"] == "placeholder"
            and event["pictureTreatment"]["kind"] == "slate"
        ):
            path = case_root / "generated/placeholders" / f"{event['eventId']}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            timeline = manifest["timeline"]
            path.write_bytes(
                _render_slate(
                    event["pictureTreatment"]["text"],
                    int(timeline["width"]),
                    int(timeline["height"]),
                )
            )
            media_paths[f"event:{event['eventId']}"] = path
            slates += 1
    if slates < 2:
        raise ValueError("expected at least two placeholder slate events")
    package_root = case_root / "package"
    build = build_v2_package(
        inputs / "timeline-manifest-v2.json",
        inputs / "build-report-v2.json",
        document_path,
        dependencies_path,
        package_root,
        media_paths=media_paths,
        preparation_paths={},
    )
    admission = admit_qualification_package_v2(
        case_root / "admission",
        profile=MATRIX_PROFILE,
        package_root=package_root,
        preparation_paths={},
        narration_evidence_paths=campaign.evidence_paths,
    )
    admission.assert_current()
    _native._required_track_counts(admission.view)
    token_ids = [t["id"] for t in document["activeDraft"]["blocks"][0]["tokens"]]
    result: Json = {
        "case": label,
        "layer": "generated-original",
        "blockId": campaign.block_id,
        "narrationAssetId": campaign.evidence["narrationAssetId"],
        "audioHash": audio["audioHash"],
        "evidenceMethod": campaign.evidence["verification"]["method"],
        "timelineFrames": int(manifest["timeline"]["durationFrames"]),
        "slateEventCount": slates,
        "boundaryTokenId": token_ids[BOUNDARY_TOKEN_INDEX],
        "packageBuildId": build.build_id,
        "packageRoot": str(package_root),
        "admissionPath": str(admission.admission_path),
        "admitted": True,
        "reportPassed": True,
    }
    if label == "C":
        result["omission"] = _omission_target(campaign)
    _write_json(case_root / "fixture-summary.json", result)
    return result


def _omission_target(campaign: Campaign) -> Json:
    envelope = _read_json(campaign.root / "out" / campaign.run / "omission-slowly.json")
    if (
        envelope.get("quotedText") != OMISSION_WORD
        or envelope.get("uniquelySafe") is not True
    ):
        raise ValueError("campaign omission envelope is not a uniquely safe 'slowly'")
    return {
        "quotedText": envelope["quotedText"],
        "tokenId": envelope["tokenId"],
        "cutStartFrames": [
            envelope["cutStart"]["firstFrame"],
            envelope["cutStart"]["lastFrame"],
        ],
        "cutEndFrames": [
            envelope["cutEnd"]["firstFrame"],
            envelope["cutEnd"]["lastFrame"],
        ],
    }


# ------------------------------------------------------------------- B audio


def read_mono_pcm24(path: Path) -> bytes:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (
            1,
            3,
            48_000,
        ):
            raise ValueError("campaign WAV must be PCM24 mono 48 kHz")
        return stream.readframes(stream.getnframes())


def derive_clip_pcm(mono: bytes, start_frame: int, source_frames: int) -> bytes:
    """Stereo PCM24 for one clip, sliced on the 2002-sample frame grid.

    Left is the Polly slice; right is the same slice halved, so the channels and
    the two clips (different grid offsets) all decode to distinct content.
    """
    samples = len(mono) // 3
    start = start_frame * FRAME_SAMPLES
    count = source_frames * FRAME_SAMPLES + 2048
    if start < 0 or start + count > samples:
        raise ValueError("campaign narration is too short for the clip slice")
    out = bytearray()
    for index in range(start, start + count):
        left = int.from_bytes(mono[index * 3 : index * 3 + 3], "little", signed=True)
        out += left.to_bytes(3, "little", signed=True)
        out += (left // 2).to_bytes(3, "little", signed=True)
    return bytes(out)


def write_stereo_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(pcm)


def clip_slice_frames(mono_samples: int) -> list[int]:
    """Grid start frames for the two clips: head slice and tail slice."""
    first_len = B_CLIPS[0][2] * FRAME_SAMPLES + 2048
    second_len = B_CLIPS[1][2] * FRAME_SAMPLES + 2048
    tail = (mono_samples - second_len) // FRAME_SAMPLES
    if first_len > mono_samples or tail < 0:
        raise ValueError("campaign narration is too short for both B clips")
    return [0, tail]


def prepare_b_linked_av_case(campaign: Campaign, output_root: Path) -> Json:
    """Two linked-AV clips whose audio is derived from campaign Polly speech."""
    case_root = output_root / "B-generated"
    _fresh_directory(case_root)
    tools = MediaTools()
    tool_hash = identity_hash(tools.fingerprint())
    mono = read_mono_pcm24(campaign.wav_path)
    starts = clip_slice_frames(len(mono) // 3)
    clips: list[Json] = []
    identities: list[Json] = []
    for index, (label, selected_frames, source_frames, flashes) in enumerate(B_CLIPS):
        media = generate_synthetic_media(
            case_root / "sources" / label,
            rate=TARGET_RATE,
            frame_count=source_frames,
            flash_frames=flashes,
            audio_sample_rate=48_000,
            audio_channels=2,
            extension=".mov",
            ffmpeg=tools.ffmpeg,
            ffprobe=tools.ffprobe,
        )
        polly_wav = media.path.parent / "polly-derived.pcm24.wav"
        write_stereo_wav(polly_wav, derive_clip_pcm(mono, starts[index], source_frames))
        source = media.path.parent / "source-pcm_s24le.mov"
        _mux_audio(
            media.path,
            polly_wav,
            source,
            start_pts=Fraction(0),
            codec="pcm_s24le",
            ffmpeg=tools.ffmpeg,
        )
        inspection = inspect_media(
            source, video_stream_index=0, audio_stream_index=1, tools=tools
        )
        if (
            inspection.audio is None
            or inspection.audio.get("channels") != 2
            or int(inspection.audio.get("sample_rate", 0)) != 48_000
        ):
            raise ValueError("B source must carry decoded stereo 48 kHz audio")
        block_id, payload_id, reference_id = (
            _uuid(f"B:{label}:{kind}") for kind in ("block", "payload", "reference")
        )
        source_in = B_SOURCE_ORIGIN_FRAME + B_SOURCE_IN_OFFSET
        occurrence = issue174_descriptor(
            inspection, rate=TARGET_RATE, audio=True, in_frame=source_in
        )
        occurrence["payloadId"] = payload_id
        occurrence["owner"] = {"kind": "visual_only_block", "blockId": block_id}
        occurrence["mediaReferenceId"] = reference_id
        occurrence["sourceSnapshot"].update(
            {
                "system": "local_import",
                "snapshotId": _uuid(f"B:{label}:snapshot"),
                "packageId": _uuid(f"B:{label}:package"),
            }
        )
        occurrence["selectedSourceRange"] = {
            "startFrame": source_in,
            "endFrame": source_in + selected_frames,
        }
        requested = {
            "sourceInFrame": source_in,
            "duration": wire(Fraction(selected_frames, 1) / TARGET_RATE),
            "preHandle": wire(Fraction(0)),
            "postHandle": wire(Fraction(0)),
        }
        preparation = prepare_media(
            source,
            cast(Any, occurrence),
            cast(Any, requested),
            cast(Any, wire(TARGET_RATE)),
            authorization=PreparationAuthorization(
                reference=f"issue-215-generated-B-{label}",
                read_roots=(source.parent,),
                write_root=case_root / "preparations" / label,
                tool_hash=tool_hash,
                minimum_free_bytes=0,
            ),
            video_stream_index=0,
            audio_stream_index=1,
            tools=tools,
        )
        occurrence["preparedMediaRequirementKey"] = preparation.binding[
            "requirementKey"
        ]
        block = {
            "type": "visual_only",
            "id": block_id,
            "orderKey": f"{chr(ord('a') + index)}0",
            "version": 1,
            "payload": {
                "kind": "visual",
                "payloadId": payload_id,
                "pictureKind": "clip",
                "source": {"kind": "media_reference", "mediaReferenceId": reference_id},
                "audioPolicy": "full",
                "framingPolicy": "contain",
            },
            "visualOnlyTiming": {
                "kind": "visual_only",
                "selectedSourceRange": {
                    "startFrame": source_in,
                    "durationFrames": selected_frames,
                },
            },
        }
        identities.append(
            {
                "label": label,
                "rawSourceHash": _file_hash(source),
                "decodedChannelHashes": _decoded_stereo_channel_hashes(source, tools),
                "pollyGridStartFrame": starts[index],
            }
        )
        clips.append(
            {
                "label": label,
                "source": source,
                "prepared": preparation,
                "occurrence": occurrence,
                "block": block,
                "selectedFrames": selected_frames,
            }
        )
    if identities[0]["rawSourceHash"] == identities[1]["rawSourceHash"] or any(
        a == b
        for a, b in zip(
            identities[0]["decodedChannelHashes"],
            identities[1]["decodedChannelHashes"],
            strict=True,
        )
    ):
        raise ValueError("B clip audio content aliases")

    document = copy.deepcopy(_read_json(TEMPLATE)["document"])
    dependencies = _base_dependencies(document, "B")
    document["id"] = _uuid("B:document")
    document["projectId"] = _uuid("B:project")
    dependencies["document"]["documentId"] = document["id"]
    document["activeDraft"]["blocks"] = [clip["block"] for clip in clips]
    dependencies["timeline"]["durationFrames"] = sum(c["selectedFrames"] for c in clips)
    dependencies["occurrenceResolutions"] = [c["occurrence"] for c in clips]
    dependencies["preparedMedia"] = [c["prepared"].binding for c in clips]
    for field in (
        "narrationBoundaryEvidence",
        "narrationTimingMaps",
        "presenterAlignmentResolutions",
    ):
        if field in dependencies:
            dependencies[field] = []
    source_audio_track = dependencies["roles"]["sourceAudioTrackIds"][0]
    for track in dependencies["tracks"]:
        if track["id"] == source_audio_track:
            track["index"] = 3
    if not any(t["id"] == "narration-second" for t in dependencies["tracks"]):
        dependencies["tracks"].append(
            {
                "id": "narration-second",
                "kind": "audio",
                "index": 2,
                "name": "Narration 2",
            }
        )
    # Fixture identity is deterministic from the case labels.
    document["projectId"] = _uuid("B:project")
    _refresh_document_binding(document, dependencies)
    inputs = case_root / "inputs"
    document_path = inputs / "script-document-v2.json"
    dependencies_path = inputs / "compiler-dependencies-v2.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    manifest, report = _compile(document_path, dependencies_path)
    if report.get("status") != "ready":
        raise ValueError("B compiler report is not ready")

    by_requirement = {c["prepared"].binding["requirementKey"]: c for c in clips}
    media_paths: dict[str, Path] = {}
    preparation_paths = {
        key: clip["prepared"].receipt_path for key, clip in by_requirement.items()
    }
    source_clip: dict[str, Json] = {}
    for source in manifest["sources"]:
        requirement = source.get("preparationRequirementKey")
        if requirement is None:
            continue
        clip = by_requirement[requirement]
        source_clip[source["id"]] = clip
        media_paths[f"source:{source['id']}"] = clip["prepared"].video_path
        media_paths[f"original:{source['id']}"] = clip["source"]
    audio_events = [e for e in manifest["events"] if e["kind"] == "source_audio"]
    for event in audio_events:
        prepared_audio = source_clip[event["provenance"]["sourceId"]][
            "prepared"
        ].audio_path
        if prepared_audio is None:
            raise ValueError("B source-audio event lacks prepared audio")
        media_paths[f"event:{event['eventId']}"] = prepared_audio
    if len(audio_events) != 2 or any(
        e["audio"].get("audioPolicy") != "full" for e in audio_events
    ):
        raise ValueError("B must compile two full-policy linked source-audio events")
    package_root = case_root / "package"
    build = build_v2_package(
        inputs / "timeline-manifest-v2.json",
        inputs / "build-report-v2.json",
        document_path,
        dependencies_path,
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    with matrix_preparation_root(case_root / "preparations"):
        admission = admit_qualification_package_v2(
            case_root / "admission",
            profile=MATRIX_PROFILE,
            package_root=package_root,
            preparation_paths=preparation_paths,
        )
    admission.assert_current()
    _native._required_track_counts(admission.view)
    _write_json(
        case_root / "fixture-paths.json",
        {
            clip["label"]: {
                "source": str(clip["source"]),
                "receipt": str(clip["prepared"].receipt_path),
                "video": str(clip["prepared"].video_path),
                "audio": str(clip["prepared"].audio_path),
            }
            for clip in clips
        },
    )
    result: Json = {
        "case": "B",
        "layer": "generated-original",
        "audioOrigin": "derived from campaign-generated Polly speech",
        "selectedSourceFrameCounts": [c[1] for c in B_CLIPS],
        "timelineFrames": int(manifest["timeline"]["durationFrames"]),
        "sourceAudioEventCount": len(audio_events),
        "sourceIdentities": identities,
        "packageBuildId": build.build_id,
        "packageRoot": str(package_root),
        "admissionPath": str(admission.admission_path),
        "admitted": True,
        "reportPassed": True,
    }
    _write_json(case_root / "fixture-summary.json", result)
    return result


def prepare_b_selected_67(output_root: Path) -> Json:
    """The 67-frame trim preparation of clip 1, with its own honest requirement key.

    The binding keeps the baseline source, profile (tool hash), target rate,
    authorization reference and mode; only the requested range (and therefore the
    key, an identity hash of the inputs) differs.  Nothing is re-keyed.
    """
    baseline_root = output_root / "B-generated"
    case_root = output_root / "B-selected-67-candidate"
    _fresh_directory(case_root)
    dependencies = _read_json(baseline_root / "inputs/compiler-dependencies-v2.json")
    occurrence = copy.deepcopy(dependencies["occurrenceResolutions"][0])
    baseline = dependencies["preparedMedia"][0]
    if occurrence["preparedMediaRequirementKey"] != baseline["requirementKey"]:
        raise ValueError("B selected occurrence does not match its binding")
    source_in = int(occurrence["selectedSourceRange"]["startFrame"])
    if int(occurrence["selectedSourceRange"]["endFrame"]) - source_in != 91:
        raise ValueError("B canonical selected range is not 91 frames")
    source = baseline_root / "sources/selected/issue174-media/source-pcm_s24le.mov"
    if _file_hash(source) != occurrence["sourceSnapshot"]["contentHash"]:
        raise ValueError("B selected source bytes differ from the occurrence")
    occurrence["selectedSourceRange"] = {
        "startFrame": source_in,
        "endFrame": source_in + 67,
    }
    requested = copy.deepcopy(baseline["requestedRange"])
    requested["duration"] = wire(Fraction(67, 1) / TARGET_RATE)
    tools = MediaTools()
    prepared = prepare_media(
        source,
        cast(Any, occurrence),
        cast(Any, requested),
        cast(Any, wire(TARGET_RATE)),
        authorization=PreparationAuthorization(
            reference=baseline["authorizationReference"],
            read_roots=(source.parent,),
            write_root=case_root / "preparations/selected",
            tool_hash=baseline["profile"]["toolHash"],
            minimum_free_bytes=0,
        ),
        video_stream_index=0,
        audio_stream_index=1,
        tools=tools,
    )
    receipt = _read_json(prepared.receipt_path)
    if (
        len(receipt.get("geometry", {}).get("selectedPackageFrames", [])) != 67
        or prepared.audio_path is None
    ):
        raise ValueError("B 67-frame preparation did not verify the requested range")
    binding = copy.deepcopy(dict(prepared.binding))
    key = binding["requirementKey"]
    if key == baseline["requirementKey"]:
        raise ValueError("B 67-frame preparation must have its own honest key")
    occurrence["preparedMediaRequirementKey"] = key
    for field in (
        "originalSource",
        "profile",
        "targetRate",
        "authorizationReference",
        "mode",
    ):
        if binding[field] != baseline[field]:
            raise ValueError(f"B 67-frame binding changed {field}")
    _write_json(case_root / "occurrence-resolution-v2.json", occurrence)
    _write_json(case_root / "prepared-media-binding-v1.json", binding)
    result: Json = {
        "case": "B",
        "purpose": "post-trim-media-preparation-only",
        "selectedSourceFrameCount": 67,
        "requirementKey": key,
        "baselineRequirementKey": baseline["requirementKey"],
        "bindingPath": str(case_root / "prepared-media-binding-v1.json"),
        "receiptPath": str(prepared.receipt_path),
        "preparedVideoPath": str(prepared.video_path),
        "preparedAudioPath": str(prepared.audio_path),
        "occurrencePath": str(case_root / "occurrence-resolution-v2.json"),
        "packageBuilt": False,
    }
    _write_json(case_root / "preparation-summary.json", result)
    return result


def build_b_trimmed_package(output_root: Path) -> Json:
    """Rebuild B with clip 1 trimmed to 67 frames under its own honest key.

    Uses the binding/receipt from :func:`prepare_b_selected_67` unchanged (clip 2 is
    unchanged, so it shifts earlier).  ``keyEqualsIdentityOfInputs`` records that the
    key is the identity hash of the receipt inputs, as matrix admission requires.
    """
    baseline = output_root / "B-generated"
    candidate = output_root / "B-selected-67-candidate"
    case_root = output_root / "B-trimmed-generated"
    _fresh_directory(case_root)
    document = _read_json(baseline / "inputs/script-document-v2.json")
    dependencies = _read_json(baseline / "inputs/compiler-dependencies-v2.json")
    paths = _read_json(baseline / "fixture-paths.json")
    summary = _read_json(candidate / "preparation-summary.json")
    binding = _read_json(candidate / "prepared-media-binding-v1.json")
    occurrence = _read_json(candidate / "occurrence-resolution-v2.json")
    block = document["activeDraft"]["blocks"][0]
    block["visualOnlyTiming"]["selectedSourceRange"]["durationFrames"] = 67
    block["version"] = int(block["version"]) + 1
    dependencies["occurrenceResolutions"][0] = occurrence
    dependencies["preparedMedia"][0] = binding
    dependencies["timeline"]["durationFrames"] = 67 + B_CLIPS[1][1]
    for field in ("buildId", "manifestId", "reportId"):
        dependencies["build"][field] = _uuid(f"B-trim:{field}")
    _refresh_document_binding(document, dependencies)
    inputs = case_root / "inputs"
    document_path = inputs / "script-document-v2.json"
    dependencies_path = inputs / "compiler-dependencies-v2.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    manifest, report = _compile(document_path, dependencies_path)
    if report.get("status") != "ready":
        raise ValueError("trimmed B compiler report is not ready")
    key = binding["requirementKey"]
    other_key = dependencies["preparedMedia"][1]["requirementKey"]
    source_clip = {
        key: {
            "video": summary["preparedVideoPath"],
            "audio": summary["preparedAudioPath"],
            "source": paths["selected"]["source"],
        },
        other_key: paths["downstream"],
    }
    media_paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        requirement = source.get("preparationRequirementKey")
        if requirement is None:
            continue
        media_paths[f"source:{source['id']}"] = Path(source_clip[requirement]["video"])
        media_paths[f"original:{source['id']}"] = Path(
            source_clip[requirement]["source"]
        )
    for event in manifest["events"]:
        if event["kind"] == "source_audio":
            requirement = next(
                s["preparationRequirementKey"]
                for s in manifest["sources"]
                if s["id"] == event["provenance"]["sourceId"]
            )
            media_paths[f"event:{event['eventId']}"] = Path(
                source_clip[requirement]["audio"]
            )
    build = build_v2_package(
        inputs / "timeline-manifest-v2.json",
        inputs / "build-report-v2.json",
        document_path,
        dependencies_path,
        case_root / "package",
        media_paths=media_paths,
        preparation_paths={
            key: Path(summary["receiptPath"]),
            other_key: Path(paths["downstream"]["receipt"]),
        },
    )
    receipt = _read_json(Path(summary["receiptPath"]))
    result: Json = {
        "case": "B",
        "layer": "trimmed-honest-key",
        "timelineFrames": int(manifest["timeline"]["durationFrames"]),
        "requirementKey": key,
        "packageBuildId": build.build_id,
        "packageRoot": str(case_root / "package"),
        "keyEqualsIdentityOfInputs": key == identity_hash(receipt["inputs"]),
    }
    _write_json(case_root / "fixture-summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--case", choices=("A", "B", "B67", "B67-PACKAGE", "C"), default="A"
    )
    args = parser.parse_args()
    if not args.output_root.is_absolute():
        raise ValueError("output root must be absolute")
    args.output_root.mkdir(parents=True, exist_ok=True)
    output_root = args.output_root
    campaign = load_campaign(args.campaign_root)
    if args.case in {"A", "C"}:
        result = prepare_narration_case(
            campaign,
            output_root,
            label=args.case,
            output_name=f"{args.case}-generated",
        )
    elif args.case == "B":
        result = prepare_b_linked_av_case(campaign, output_root)
    elif args.case == "B67":
        result = prepare_b_selected_67(output_root)
    else:
        result = build_b_trimmed_package(output_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
