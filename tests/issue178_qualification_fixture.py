"""Build real-media, ordinary-package qualification inputs for issue #178."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

from issue174_media_fixture import SyntheticMedia, generate_synthetic_media
from test_issue174_real_media import issue174_descriptor
from vera_timeline_agent.media_preparation import (
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.qualification_output_package_v2 import (
    MATRIX_PROFILE,
    QualificationOutputAdmissionV2,
    admit_qualification_package_v2,
)
from vera_timeline_agent.v2_package import V2PackageResult, build_v2_package

Json = dict[str, Any]
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
_COMPILER_CLI = REPOSITORY_ROOT / "packages/contracts/src/issue-190-compile-cli.ts"
_INPUT_TEMPLATE = (
    REPOSITORY_ROOT
    / "tests/data/authoring_v2/issue_173/compiler/selected-clip-ntsc.input.golden.json"
)
_SOURCE_ORIGIN_FRAME = 3000
_SOURCE_IN_OFFSET = 10
_TARGET_RATE = Fraction(24000, 1001)
_AUDIO_POLICIES = Literal["mute", "quiet", "full"]


@dataclass(frozen=True)
class QualificationCase:
    """The actual preparations and verified package produced for one case."""

    case_name: str
    root: Path
    document_path: Path
    dependencies_path: Path
    manifest_path: Path
    report_path: Path
    package_root: Path
    admitted_root: Path
    source_paths: dict[str, Path]
    preparations: dict[str, PreparedMedia]
    manifest: Json
    report: Json
    build: V2PackageResult
    admission: QualificationOutputAdmissionV2
    expected_frame_ordinals: dict[str, tuple[int, ...]]
    expected_audio_samples: dict[str, tuple[int, ...]]
    audio_policies: dict[str, str]
    expected_audio_gain_db: dict[str, float | None]
    payload_ids: dict[str, str]
    expected_record_frames: dict[str, int]


@dataclass(frozen=True)
class _Clip:
    label: str
    rate: Fraction
    source_in_frame: int
    source_frames: int
    source: Path
    media: SyntheticMedia
    prepared: PreparedMedia
    occurrence: Json
    block: Json
    audio_policy: _AUDIO_POLICIES
    has_audio: bool


@dataclass(frozen=True)
class _ClipSpec:
    label: str
    rate: Fraction
    source_frames: int
    audio_policy: _AUDIO_POLICIES = "full"
    has_audio: bool = True
    selected_range: bool = True
    duration_override_ms: int | None = None
    source_system: Literal["research", "local_import"] = "local_import"


_CASES: dict[str, tuple[_ClipSpec, ...]] = {
    "mixed25_30": (
        _ClipSpec("clip-1-25fps", Fraction(25), 1001, source_system="research"),
        _ClipSpec("clip-2-30fps", Fraction(30), 90, audio_policy="mute"),
    ),
    "same_rate": (_ClipSpec("clip-1-24000_1001fps", _TARGET_RATE, 72),),
    "fractional29_24nonzeroinpoint": (
        _ClipSpec("clip-1-30000_1001fps", Fraction(30000, 1001), 300),
        _ClipSpec("clip-2-24fps", Fraction(24), 72, audio_policy="mute"),
    ),
    "endpoint10s": (
        _ClipSpec("clip-1-25fps", Fraction(25), 250, audio_policy="mute"),
        _ClipSpec("reference-full", _TARGET_RATE, 72),
    ),
    "audio_no": (
        _ClipSpec("clip-1-24000_1001fps", _TARGET_RATE, 72, audio_policy="mute"),
        _ClipSpec("reference-full", _TARGET_RATE, 72),
    ),
    "audio_quiet": (
        _ClipSpec("clip-1-24000_1001fps", _TARGET_RATE, 72, audio_policy="quiet"),
    ),
    "audio_full": (_ClipSpec("clip-1-24000_1001fps", _TARGET_RATE, 72),),
    "duration_default_72": (
        _ClipSpec("clip-1-24000_1001fps", _TARGET_RATE, 72, selected_range=False),
    ),
    "duration_override_72": (
        _ClipSpec(
            "clip-1-24000_1001fps",
            _TARGET_RATE,
            72,
            audio_policy="mute",
            selected_range=False,
            duration_override_ms=3003,
        ),
    ),
}


def _uuid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#178-qualification:v1:{label}"))


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _compiler_hash(value: object) -> str:
    from vera_timeline_agent.v2_package import _compiler_hash as compiler_hash

    return compiler_hash(value)


def _refresh_document_binding(document: Json, dependencies: Json) -> None:
    text = "\n".join(
        block["text"]
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    )
    text_hash = _raw_hash(text.encode("utf-8"))
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    dependencies["document"].update(
        {
            "documentId": document["id"],
            "projectId": document["projectId"],
            "liveHeadSequence": document["liveHeadSequence"],
            "contentHash": document["liveContentHash"],
            "textHash": text_hash,
            "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
        }
    )


def _compile(document_path: Path, dependencies_path: Path) -> tuple[Json, Json]:
    if not _NODE.is_file() or _NODE.is_symlink() or not _COMPILER_CLI.is_file():
        raise ValueError("pinned Node 24.19.0 compiler runtime is unavailable")
    environment = {"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)}
    version = subprocess.run(
        [str(_NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env=environment,
    )
    if (
        version.returncode != 0
        or version.stdout.strip() != b"v24.19.0"
        or version.stderr
    ):
        raise ValueError("pinned Node 24.19.0 runtime check failed")
    result = subprocess.run(
        [str(_NODE), str(_COMPILER_CLI), str(document_path), str(dependencies_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env=environment,
    )
    if result.returncode != 0 or result.stderr:
        detail = result.stderr.decode("utf-8", errors="replace")
        raise ValueError(
            f"TypeScript compiler refused the qualification inputs: {detail}"
        )
    envelope = cast(Json, json.loads(result.stdout))
    compiled = cast(Json, envelope["result"])
    if compiled.get("ok") is not True:
        raise ValueError("TypeScript compiler did not return an accepted build")
    (document_path.parent / "timeline-manifest-v2.json").write_bytes(
        compiled["manifestJson"].encode()
    )
    (document_path.parent / "build-report-v2.json").write_bytes(
        compiled["reportJson"].encode()
    )
    return cast(Json, compiled["manifest"]), cast(Json, compiled["report"])


def _prepare_clip(
    *,
    root: Path,
    spec: _ClipSpec,
    tools: MediaTools,
    reuse_existing_media: bool = False,
) -> _Clip:
    label = spec.label
    rate = spec.rate
    source_offset = _SOURCE_IN_OFFSET
    source_frame_count = (
        source_offset + spec.source_frames + (10 if spec.selected_range else 0)
    )
    flash_frames = (
        source_offset + 1,
        source_offset + spec.source_frames // 2,
        source_offset + spec.source_frames - 1,
    )
    if reuse_existing_media:
        media_root = root / "sources" / label / "issue174-media"
        video = media_root / "source.mov"
        audio = media_root / "source.pcm24.wav"
        muxed = media_root / "source-pcm_s24le.mov" if spec.has_audio else None
        if (
            not video.is_file()
            or not audio.is_file()
            or (spec.has_audio and (muxed is None or not muxed.is_file()))
        ):
            raise ValueError(f"retained synthetic source is incomplete: {label}")
        click_samples = tuple(
            (frame * 48000 * rate.denominator + rate.numerator // 2) // rate.numerator
            for frame in flash_frames
        )
        media = SyntheticMedia(
            path=video,
            audio_path=audio,
            muxed_path=muxed,
            rate=rate,
            frame_count=source_frame_count,
            start_pts=Fraction(0),
            flash_frames=flash_frames,
            click_samples=click_samples,
            commands=(),
            hashes={},
            probe_hashes={},
        )
    else:
        media = generate_synthetic_media(
            root / "sources" / label,
            rate=rate,
            frame_count=source_frame_count,
            flash_frames=flash_frames,
            audio_sample_rate=48000,
            audio_channels=2,
            extension=".mov",
            mux_audio="pcm_s24le" if spec.has_audio else None,
            ffmpeg=tools.ffmpeg,
            ffprobe=tools.ffprobe,
        )
    source = media.muxed_path if spec.has_audio else media.path
    if source is None:
        raise ValueError("qualification source path is unavailable")
    inspection = inspect_media(
        source,
        video_stream_index=0,
        audio_stream_index=1 if spec.has_audio else None,
        tools=tools,
    )
    block_id = _uuid(f"{label}:block")
    payload_id = _uuid(f"{label}:payload")
    media_reference_id = _uuid(f"{label}:media-reference")
    occurrence = issue174_descriptor(
        inspection,
        rate=rate,
        audio=spec.has_audio,
        in_frame=_SOURCE_ORIGIN_FRAME + source_offset,
    )
    occurrence["sourceSnapshot"]["system"] = spec.source_system
    occurrence["payloadId"] = payload_id
    occurrence["owner"] = {"kind": "visual_only_block", "blockId": block_id}
    occurrence["mediaReferenceId"] = media_reference_id
    occurrence["sourceSnapshot"]["snapshotId"] = _uuid(f"{label}:snapshot")
    occurrence["sourceSnapshot"]["packageId"] = _uuid(f"{label}:package")
    if spec.selected_range:
        occurrence["selectedSourceRange"] = {
            "startFrame": _SOURCE_ORIGIN_FRAME + source_offset,
            "endFrame": _SOURCE_ORIGIN_FRAME + source_offset + spec.source_frames,
        }
    requested_range = {
        "sourceInFrame": _SOURCE_ORIGIN_FRAME + source_offset,
        "duration": wire(Fraction(spec.source_frames, 1) / rate),
        "preHandle": wire(Fraction(0)),
        "postHandle": wire(Fraction(0)),
    }
    authorization = PreparationAuthorization(
        reference=f"issue-178-{label}",
        read_roots=(source.parent,),
        write_root=root / "preparations" / label,
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    prepared = prepare_media(
        source,
        cast(Any, occurrence),
        cast(Any, requested_range),
        cast(Any, wire(_TARGET_RATE)),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=1 if spec.has_audio else None,
        tools=tools,
    )
    occurrence["preparedMediaRequirementKey"] = prepared.binding["requirementKey"]
    block: Json = {
        "type": "visual_only",
        "id": block_id,
        "orderKey": "a0",
        "version": 1,
        "payload": {
            "kind": "visual",
            "payloadId": payload_id,
            "pictureKind": "clip",
            "source": {
                "kind": "media_reference",
                "mediaReferenceId": media_reference_id,
            },
            "audioPolicy": spec.audio_policy,
            "framingPolicy": "contain",
        },
        "visualOnlyTiming": {"kind": "visual_only"},
    }
    if spec.selected_range:
        block["visualOnlyTiming"]["selectedSourceRange"] = {
            "startFrame": _SOURCE_ORIGIN_FRAME + source_offset,
            "durationFrames": spec.source_frames,
        }
    if spec.duration_override_ms is not None:
        block["visualOnlyTiming"]["durationOverrideMs"] = spec.duration_override_ms
    return _Clip(
        label,
        rate,
        _SOURCE_ORIGIN_FRAME + source_offset,
        spec.source_frames,
        source,
        media,
        prepared,
        occurrence,
        block,
        spec.audio_policy,
        spec.has_audio,
    )


def _expected_ordinals(clip: _Clip) -> tuple[int, ...]:
    frame_count = int(clip.prepared.binding["verification"]["decodedFrameCount"])
    start = (
        Fraction(0)
        if clip.prepared.binding["mode"] == "verified_reuse"
        else Fraction(clip.source_in_frame - _SOURCE_ORIGIN_FRAME, 1) / clip.rate
    )
    return tuple(
        math.floor((start + Fraction(frame, 1) / _TARGET_RATE) * clip.rate)
        for frame in range(frame_count)
    )


def _expected_audio_positions(clip: _Clip) -> tuple[int, ...]:
    if not clip.has_audio:
        return ()
    record = cast(Json, json.loads(clip.prepared.receipt_path.read_bytes()))
    audio = cast(Json, record["audio"])
    if audio["sourceFirstSample"] != audio["resampledFirstSample"]:
        raise ValueError("48 kHz source click positions do not map one-to-one")
    first = int(audio["sourceFirstSample"])
    exclusive = int(audio["sourceExclusiveSample"])
    return tuple(
        sample - first
        for sample in clip.media.click_samples
        if first <= sample < exclusive
    )


def _build_case_inputs(root: Path, clips: tuple[_Clip, ...]) -> tuple[Path, Path]:
    template = cast(Json, json.loads(_INPUT_TEMPLATE.read_bytes()))
    document = copy.deepcopy(template["document"])
    dependencies = copy.deepcopy(template["dependencies"])
    document["id"] = _uuid("document")
    document["projectId"] = _uuid("project")
    compiler_core = REPOSITORY_ROOT / "packages/contracts/src/compiler-core-v2.ts"
    dependencies["compiler"]["sourceHash"] = (
        "sha256:" + hashlib.sha256(compiler_core.read_bytes()).hexdigest()
    )
    for track in dependencies["tracks"]:
        if track["id"] == dependencies["roles"]["sourceAudioTrackIds"][0]:
            track["index"] = 3
    dependencies["tracks"].append(
        {"id": "narration-second", "kind": "audio", "index": 2, "name": "Narration 2"}
    )
    document["activeDraft"]["blocks"] = []
    dependencies["occurrenceResolutions"] = []
    dependencies["preparedMedia"] = []
    dependencies["timeline"]["durationFrames"] = sum(
        _record_frames(clip, dependencies) for clip in clips
    )
    for index, clip in enumerate(clips):
        block = copy.deepcopy(clip.block)
        block["orderKey"] = f"{chr(ord('a') + index)}0"
        document["activeDraft"]["blocks"].append(block)
        dependencies["occurrenceResolutions"].append(copy.deepcopy(clip.occurrence))
        dependencies["preparedMedia"].append(copy.deepcopy(clip.prepared.binding))
    _refresh_document_binding(document, dependencies)
    document_path = root / "inputs/script-document-v2.json"
    dependencies_path = root / "inputs/compiler-dependencies-v2.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    return document_path, dependencies_path


def _record_frames(clip: _Clip, dependencies: Json) -> int:
    timing = clip.block["visualOnlyTiming"]
    if "selectedSourceRange" in timing:
        duration = Fraction(clip.source_frames, 1) / clip.rate
        return math.ceil(duration * _TARGET_RATE)
    duration_ms = timing.get(
        "durationOverrideMs",
        dependencies["authoringDefaults"]["visualOnlyStillDurationMs"],
    )
    return math.ceil(Fraction(duration_ms, 1000) * _TARGET_RATE)


def _package_media_paths(manifest: Json, clips: tuple[_Clip, ...]) -> dict[str, Path]:
    by_requirement = {clip.prepared.binding["requirementKey"]: clip for clip in clips}
    source_by_id: dict[str, _Clip] = {}
    media_paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        requirement = source.get("preparationRequirementKey")
        if requirement is None:
            continue
        clip = by_requirement[requirement]
        source_id = source["id"]
        source_by_id[source_id] = clip
        media_paths[f"source:{source_id}"] = clip.prepared.video_path
        media_paths[f"original:{source_id}"] = clip.source
    for event in manifest["events"]:
        if event["kind"] != "source_audio":
            continue
        source_id = event["provenance"]["sourceId"]
        clip = source_by_id[source_id]
        if clip.prepared.audio_path is None:
            raise ValueError("compiled source-audio event has no actual P5 WAV")
        media_paths[f"event:{event['eventId']}"] = clip.prepared.audio_path
    return media_paths


def prepare_qualification_case(
    root: Path,
    case_name: str,
    *,
    reuse_media_from: Path | None = None,
) -> QualificationCase:
    """Prepare, compile, package, and admit one issue-owned real-media case.

    The caller owns a new absolute output directory, usually a pytest ``tmp_path``.
    ``reuse_media_from`` copies an earlier fixture's real sources/preparations so
    the authored inputs can be recompiled and readmitted without re-encoding.
    """
    specs = _CASES.get(case_name)
    if specs is None:
        raise ValueError(f"unsupported issue 178 qualification case: {case_name!r}")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("absolute qualification output root required")
    if root.exists() or root.is_symlink():
        raise ValueError("qualification output root must be new")
    root.mkdir(parents=True)
    reuse_existing_media = reuse_media_from is not None
    if reuse_media_from is not None:
        if (
            not reuse_media_from.is_absolute()
            or not reuse_media_from.is_dir()
            or reuse_media_from.is_symlink()
        ):
            raise ValueError(
                "existing qualification media root must be a real directory"
            )
        for directory in ("sources", "preparations"):
            source_directory = reuse_media_from / directory
            if not source_directory.is_dir() or source_directory.is_symlink():
                raise ValueError(f"retained qualification {directory} are unavailable")
            shutil.copytree(source_directory, root / directory)
    tools = MediaTools()
    clips = tuple(
        _prepare_clip(
            root=root,
            spec=spec,
            tools=tools,
            reuse_existing_media=reuse_existing_media,
        )
        for spec in specs
    )
    document_path, dependencies_path = _build_case_inputs(root, clips)
    manifest, report = _compile(document_path, dependencies_path)
    manifest_path = root / "inputs/timeline-manifest-v2.json"
    report_path = root / "inputs/build-report-v2.json"
    preparation_paths = {
        clip.prepared.binding["requirementKey"]: clip.prepared.receipt_path
        for clip in clips
    }
    package_root = root / "package"
    build = build_v2_package(
        manifest_path,
        report_path,
        document_path,
        dependencies_path,
        package_root,
        media_paths=_package_media_paths(manifest, clips),
        preparation_paths=preparation_paths,
    )
    admitted_root = root / "admitted"
    admission = admit_qualification_package_v2(
        admitted_root,
        profile=MATRIX_PROFILE,
        package_root=package_root,
        preparation_paths=preparation_paths,
    )
    dependencies = cast(Json, json.loads(dependencies_path.read_bytes()))
    expected_frame_ordinals = {clip.label: _expected_ordinals(clip) for clip in clips}
    expected_audio_samples = {
        clip.label: _expected_audio_positions(clip) for clip in clips
    }
    audio_policies: dict[str, str] = {clip.label: clip.audio_policy for clip in clips}
    expected_audio_gain_db = {
        clip.label: {"mute": None, "quiet": -18.0, "full": 0.0}[clip.audio_policy]
        for clip in clips
    }
    expected_record_frames = {
        clip.label: _record_frames(clip, dependencies) for clip in clips
    }
    _write_json(
        root / "qualification-case.json",
        {
            "schemaVersion": "issue178-qualification-case/v1",
            "caseName": case_name,
            "manifest": manifest,
            "preparations": {
                clip.label: {
                    "videoPath": clip.prepared.video_path.relative_to(root).as_posix(),
                    "audioPath": (
                        clip.prepared.audio_path.relative_to(root).as_posix()
                        if clip.prepared.audio_path is not None
                        else None
                    ),
                    "receiptPath": clip.prepared.receipt_path.relative_to(
                        root
                    ).as_posix(),
                    "binding": clip.prepared.binding,
                }
                for clip in clips
            },
            "expectedFrameOrdinals": expected_frame_ordinals,
            "expectedAudioSamples": expected_audio_samples,
            "audioPolicies": audio_policies,
            "expectedAudioGainDb": expected_audio_gain_db,
            "expectedRecordFrames": expected_record_frames,
            "sourceInpoints": {clip.label: clip.source_in_frame for clip in clips},
        },
    )
    return QualificationCase(
        case_name=case_name,
        root=root,
        document_path=document_path,
        dependencies_path=dependencies_path,
        manifest_path=manifest_path,
        report_path=report_path,
        package_root=package_root,
        admitted_root=admitted_root,
        source_paths={clip.label: clip.source for clip in clips},
        preparations={clip.label: clip.prepared for clip in clips},
        manifest=manifest,
        report=report,
        build=build,
        admission=admission,
        expected_frame_ordinals=expected_frame_ordinals,
        expected_audio_samples=expected_audio_samples,
        audio_policies=audio_policies,
        expected_audio_gain_db=expected_audio_gain_db,
        payload_ids={clip.label: clip.occurrence["payloadId"] for clip in clips},
        expected_record_frames=expected_record_frames,
    )
