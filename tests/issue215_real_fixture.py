"""Prepare private real-media baseline packages for issue #215.

The private inputs are read from caller-supplied paths.  This helper prints only
aggregate fixture metadata; narration text and marker rows stay in the private
qualification-output directory.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
import uuid
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tests"))
sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from issue174_media_fixture import generate_synthetic_media  # noqa: E402
from issue178_qualification_fixture import (  # noqa: E402
    _compile,
    _refresh_document_binding,
)
from test_issue174_real_media import issue174_descriptor  # noqa: E402
from vera_timeline_agent.media_preparation import (  # noqa: E402
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import (  # noqa: E402
    canonical_json_bytes,
    identity_hash,
)
from vera_timeline_agent.v2_package import (  # noqa: E402
    _render_slate,
    build_v2_package,
)

Json = dict[str, Any]
TARGET_RATE = Fraction(24000, 1001)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _read_json(path: Path) -> Json:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return cast(Json, value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _fresh_directory(path: Path) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise ValueError("fixture output must be a new absolute directory")
    path.mkdir(parents=True)


def _target_narration(document: Json, token_count: int) -> Json:
    matches = [
        block
        for block in document["activeDraft"]["blocks"]
        if block.get("type") == "narration"
        and len(block.get("tokens", [])) == token_count
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {token_count}-token narration row")
    return cast(Json, matches[0])


def _filtered_narration_inputs(
    source_root: Path,
    target_root: Path,
    *,
    token_count: int,
    visual_slot_limit: int | None = None,
) -> tuple[Json, Json, Json, list[Json], dict[str, Json]]:
    source_document = _read_json(source_root / "script-document-v2.json")
    source_dependencies = _read_json(source_root / "compiler-dependencies-v2.json")
    row = _target_narration(source_document, token_count)
    sequence_id = row["primaryVisualSequence"]["id"]

    document = copy.deepcopy(source_document)
    document["activeDraft"]["blocks"] = [
        block
        for block in source_document["activeDraft"]["blocks"]
        if block.get("type") == "section" or block.get("id") == row["id"]
    ]
    selected_row = next(
        block
        for block in document["activeDraft"]["blocks"]
        if block.get("id") == row["id"]
    )
    slots = selected_row["primaryVisualSequence"]["slots"]
    if visual_slot_limit is not None:
        if visual_slot_limit < 1 or visual_slot_limit > len(slots):
            raise ValueError("visual slot limit is outside the selected sequence")
        selected_row["primaryVisualSequence"]["slots"] = slots[:visual_slot_limit]
        slots = selected_row["primaryVisualSequence"]["slots"]
    selected_slot_ids = {slot["id"] for slot in slots}
    owned_slate_slots: set[str] = set()
    slate_ordinal = 0
    for slot in selected_row["primaryVisualSequence"]["slots"]:
        payload = slot.get("payload", {})
        if payload.get("kind") == "visual" and payload.get("pictureKind") == "image":
            slate_ordinal += 1
            owned_slate_slots.add(slot["id"])
            payload["pictureKind"] = "intentional_placeholder"
            payload["source"] = {
                "kind": "intentional_placeholder",
                "text": f"ISSUE 215 {token_count}-TOKEN STILL {slate_ordinal}",
            }
        elif payload.get("kind") == "on_camera":
            slate_ordinal += 1
            owned_slate_slots.add(slot["id"])
            payload_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"vera:#215-real-{token_count}:presenter-slot:{slot['id']}",
                )
            )
            slot["payload"] = {
                "kind": "visual",
                "payloadId": payload_id,
                "pictureKind": "intentional_placeholder",
                "source": {
                    "kind": "intentional_placeholder",
                    "text": (
                        f"ISSUE 215 {token_count}-TOKEN PRESENTER HOLD {slate_ordinal}"
                    ),
                },
                "sourceUsage": None,
                "audioPolicy": "mute",
                "framingPolicy": "contain",
            }
    dependencies = copy.deepcopy(source_dependencies)
    occurrences = [
        copy.deepcopy(item)
        for item in source_dependencies.get("occurrenceResolutions", [])
        if (
            item.get("owner", {}).get("sequenceId") == sequence_id
            and item.get("owner", {}).get("slotId") in selected_slot_ids
        )
        or item.get("owner", {}).get("blockId") == row["id"]
    ]
    occurrences = [
        item
        for item in occurrences
        if item.get("owner", {}).get("slotId") not in owned_slate_slots
    ]
    requirement_keys = {
        item["preparedMediaRequirementKey"]
        for item in occurrences
        if item.get("preparedMediaRequirementKey")
    }
    original_bindings = {
        item["requirementKey"]: copy.deepcopy(item)
        for item in source_dependencies.get("preparedMedia", [])
        if item.get("requirementKey") in requirement_keys
    }
    dependencies["occurrenceResolutions"] = occurrences
    dependencies["preparedMedia"] = list(original_bindings.values())
    dependencies["narrationBoundaryEvidence"] = [
        copy.deepcopy(item)
        for item in source_dependencies.get("narrationBoundaryEvidence", [])
        if item.get("blockId") == row["id"]
    ]
    dependencies["narrationTimingMaps"] = [
        copy.deepcopy(item)
        for item in source_dependencies.get("narrationTimingMaps", [])
        if item.get("blockId") == row["id"]
    ]
    dependencies["presenterAlignmentResolutions"] = [
        copy.deepcopy(item)
        for item in source_dependencies.get("presenterAlignmentResolutions", [])
        if item.get("blockId") == row["id"]
    ]
    generic_presenter_still = _read_json(
        REPOSITORY_ROOT / "packages/contracts/src/assets/generic-torso-v1.json"
    )
    document.setdefault("scriptSettings", {})["presenterStillOverride"] = copy.deepcopy(
        generic_presenter_still
    )
    compiler_core = REPOSITORY_ROOT / "packages/contracts/src/compiler-core-v2.ts"
    dependencies["compiler"]["sourceHash"] = _file_hash(compiler_core)
    for identity_field in ("buildId", "manifestId", "reportId"):
        dependencies["build"][identity_field] = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"vera:#215-real:{target_root.name}:{identity_field}",
            )
        )
    dependencies["authoringDefaults"]["presenterStill"] = copy.deepcopy(
        generic_presenter_still
    )
    evidence = dependencies["narrationBoundaryEvidence"]
    if len(evidence) != 1:
        raise ValueError("selected narration row lacks its exact boundary evidence")
    audio = evidence[0]["audio"]
    duration = Fraction(int(audio["durationSamples"]), int(audio["sampleRate"]))
    dependencies["timeline"]["durationFrames"] = math.ceil(duration * TARGET_RATE)
    _refresh_document_binding(document, dependencies)

    _write_json(target_root / "inputs/script-document-v2.json", document)
    _write_json(target_root / "inputs/compiler-dependencies-v2.json", dependencies)
    return document, dependencies, row, occurrences, original_bindings


def _prepare_primary_stills(
    source_root: Path,
    target_root: Path,
    occurrences: list[Json],
    original_bindings: dict[str, Json],
) -> tuple[list[Json], dict[str, PreparedMedia], dict[str, Path]]:
    tools = MediaTools()
    new_bindings: list[Json] = []
    prepared_by_requirement: dict[str, PreparedMedia] = {}
    source_by_requirement: dict[str, Path] = {}
    for index, occurrence in enumerate(occurrences):
        old_key = occurrence.get("preparedMediaRequirementKey")
        if old_key is None:
            continue
        old_binding = original_bindings.get(old_key)
        if old_binding is None:
            raise ValueError("selected still lacks its source preparation binding")
        locator = old_binding.get("artifactLocator")
        if not isinstance(locator, str) or "://" in locator:
            raise ValueError("selected still locator is not source-root relative")
        source_path = (source_root / locator).resolve()
        if not source_path.is_file() or not source_path.is_relative_to(
            source_root.resolve()
        ):
            raise ValueError(
                "selected still source is unavailable under the supplied root"
            )
        requested_range = copy.deepcopy(old_binding["requestedRange"])
        target_rate = copy.deepcopy(old_binding["targetRate"])
        authorization = PreparationAuthorization(
            reference=f"issue-215-real-A-still-{index + 1}",
            read_roots=(source_path.parent,),
            write_root=target_root / "preparations" / f"still-{index + 1}",
            tool_hash=identity_hash(tools.fingerprint()),
            minimum_free_bytes=0,
        )
        prepared = prepare_media(
            source_path,
            cast(Any, occurrence),
            cast(Any, requested_range),
            cast(Any, target_rate),
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=None,
            tools=tools,
        )
        occurrence["preparedMediaRequirementKey"] = prepared.binding["requirementKey"]
        new_bindings.append(copy.deepcopy(prepared.binding))
        prepared_by_requirement[prepared.binding["requirementKey"]] = prepared
        source_by_requirement[prepared.binding["requirementKey"]] = source_path
    return new_bindings, prepared_by_requirement, source_by_requirement


def _media_inputs(
    manifest: Json,
    dependencies: Json,
    source_root: Path,
    target_root: Path,
    prepared_by_requirement: dict[str, PreparedMedia],
    source_by_requirement: dict[str, Path],
) -> tuple[dict[str, Path], dict[str, Path]]:
    media_paths: dict[str, Path] = {}
    preparation_paths = {
        key: value.receipt_path for key, value in prepared_by_requirement.items()
    }
    evidence_by_hash = {
        item["audioHash"]: item for item in dependencies["narrationBoundaryEvidence"]
    }
    occurrence_by_requirement = {
        item.get("preparedMediaRequirementKey"): item
        for item in dependencies["occurrenceResolutions"]
        if item.get("preparedMediaRequirementKey")
    }
    for source in manifest["sources"]:
        source_id = source["id"]
        if "narrationAudio" in source:
            narration = source["narrationAudio"]
            evidence = evidence_by_hash.get(narration["audioHash"])
            if evidence is None:
                raise ValueError("compiled narration source has no matching evidence")
            media_paths[f"source:{source_id}"] = (
                source_root / evidence["audio"]["locator"]
            ).resolve()
            continue
        requirement = source.get("preparationRequirementKey")
        if requirement is None:
            continue
        prepared = prepared_by_requirement.get(requirement)
        original = source_by_requirement.get(requirement)
        occurrence = occurrence_by_requirement.get(requirement)
        if prepared is None or original is None or occurrence is None:
            raise ValueError(
                "compiled visual source has no exact prepared-media mapping"
            )
        media_paths[f"source:{source_id}"] = prepared.video_path
        media_paths[f"original:{source_id}"] = original

    for event in manifest["events"]:
        if event["kind"] != "placeholder":
            continue
        treatment = event["pictureTreatment"]
        if treatment["kind"] == "slate":
            timeline = manifest["timeline"]
            slate_path = (
                target_root / "generated" / "placeholders" / f"{event['eventId']}.png"
            )
            slate_path.parent.mkdir(parents=True, exist_ok=True)
            slate_path.write_bytes(
                _render_slate(
                    treatment["text"],
                    int(timeline["width"]),
                    int(timeline["height"]),
                )
            )
            media_paths[f"event:{event['eventId']}"] = slate_path
        elif treatment["kind"] == "still":
            locator = treatment["reference"]["projectRelativeLocator"]
            still_path = REPOSITORY_ROOT / "packages/contracts/src" / locator
            media_paths[f"event:{event['eventId']}"] = still_path
    return media_paths, preparation_paths


def prepare_original_narration_case(
    source_root: Path,
    output_root: Path,
    *,
    label: str,
    token_count: int,
    visual_slot_limit: int | None = None,
    output_name: str | None = None,
) -> Json:
    case_root = output_root / (output_name or f"{label}-original")
    _fresh_directory(case_root)
    document, dependencies, row, occurrences, _old_bindings = (
        _filtered_narration_inputs(
            source_root,
            case_root,
            token_count=token_count,
            visual_slot_limit=visual_slot_limit,
        )
    )
    prepared: dict[str, PreparedMedia] = {}
    source_paths: dict[str, Path] = {}
    dependencies["preparedMedia"] = []
    dependencies["occurrenceResolutions"] = occurrences
    _refresh_document_binding(document, dependencies)
    _write_json(case_root / "inputs/script-document-v2.json", document)
    _write_json(case_root / "inputs/compiler-dependencies-v2.json", dependencies)
    manifest, report = _compile(
        case_root / "inputs/script-document-v2.json",
        case_root / "inputs/compiler-dependencies-v2.json",
    )
    manifest_path = case_root / "inputs/timeline-manifest-v2.json"
    report_path = case_root / "inputs/build-report-v2.json"
    media_paths, preparation_paths = _media_inputs(
        manifest,
        dependencies,
        source_root,
        case_root,
        prepared,
        source_paths,
    )
    package_root = case_root / "package"
    build = build_v2_package(
        manifest_path,
        report_path,
        case_root / "inputs/script-document-v2.json",
        case_root / "inputs/compiler-dependencies-v2.json",
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    result = {
        "case": label,
        "layer": "original",
        "tokenCount": len(row["tokens"]),
        "timelineFrames": int(manifest["timeline"]["durationFrames"]),
        "eventCount": len(manifest["events"]),
        "sourceCount": len(manifest["sources"]),
        "preparedStillCount": len(prepared),
        "compilerBuildId": manifest["buildId"],
        "packageBuildId": build.build_id,
        "packageRoot": str(package_root),
        "reportPassed": report.get("status") == "ready",
    }
    _write_json(case_root / "fixture-summary.json", result)
    return result


def _audition_time(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def prepare_c_audition_prefill(case_root: Path, source_root: Path) -> Json:
    """Write three privately scoped machine markers; never claim review."""
    document = _read_json(case_root / "inputs/script-document-v2.json")
    dependencies = _read_json(case_root / "inputs/compiler-dependencies-v2.json")
    row = _target_narration(document, 21)
    boundary_evidence = dependencies["narrationBoundaryEvidence"]
    if len(boundary_evidence) != 1:
        raise ValueError("C needs one exact narration audio binding")
    audio_record = boundary_evidence[0]["audio"]
    original_audio = (source_root / audio_record["locator"]).resolve()
    if not original_audio.is_file():
        raise ValueError("C source narration WAV is unavailable")
    original_hash = _file_hash(original_audio)
    if original_hash != audio_record["audioHash"]:
        raise ValueError(
            "C source narration bytes no longer match their retained binding"
        )

    route_root = Path.home() / ".local/share/vera/issue-148-vo1"
    alignment_path = route_root / "alignment.json"
    recognition_path = route_root / "recognition.json"
    reconciliation_path = route_root / "reconciliation.json"
    alignment = _read_json(alignment_path)
    recognition = _read_json(recognition_path)
    reconciliation = _read_json(reconciliation_path)
    identity = alignment["identity"]
    if (
        identity.get("recognitionArtifactId") != recognition.get("artifactId")
        or identity.get("reconcileArtifactId") != reconciliation.get("artifactId")
        or reconciliation.get("identity", {}).get("recognitionArtifactId")
        != recognition.get("artifactId")
    ):
        raise ValueError("C retained alignment route does not bind to recognition")
    aligned_audio_hash = identity["audio"]["hash"]
    resampled_audio = route_root / "vo1-16k.wav"
    if _file_hash(resampled_audio) != aligned_audio_hash:
        raise ValueError("C retained alignment audio bytes changed")

    sys.path.insert(0, str(REPOSITORY_ROOT / "packages/word-timing/src"))
    from vera_word_timing.artifacts import content_hash
    from vera_word_timing.normalize import normalise_token
    from vera_word_timing.script_reconcile import load_dictionary_words, parse_prompter

    script_path = route_root / "vo1-script.txt"
    script_text = script_path.read_text(encoding="utf-8")
    if reconciliation.get("identity", {}).get("scriptHash") != content_hash(
        script_text
    ):
        raise ValueError("C retained reconciliation is not bound to its script input")
    language = recognition["identity"]["language"]
    dictionary = load_dictionary_words(
        (route_root / "guides.dict").read_text(encoding="utf-8"), language
    )
    prompter = parse_prompter(script_text, dictionary, language)
    if len(prompter.words) != len(row["tokens"]):
        raise ValueError(
            "C retained script word inventory differs from canonical tokens"
        )
    script_unit_to_token: list[int] = []
    for token_index, (token, script_word) in enumerate(
        zip(row["tokens"], prompter.words, strict=True)
    ):
        if normalise_token(token["value"], language) != script_word["spoken"]:
            raise ValueError("C retained script order differs from canonical tokens")
        script_unit_to_token.extend([token_index] * len(script_word["spoken"]))

    source_rate = int(audio_record["sampleRate"])
    source_samples = int(audio_record["durationSamples"])
    aligned_rate = int(identity["audio"]["sampleRate"])
    aligned_samples = int(identity["audio"]["durationSamples"])
    if abs(
        Fraction(source_samples, source_rate) - Fraction(aligned_samples, aligned_rate)
    ) > Fraction(1, aligned_rate):
        raise ValueError("C alignment audio no longer preserves original source time")

    units = reconciliation.get("units", [])
    words = alignment.get("words", [])
    word_by_key = {
        (word.get("tokenIndex"), str(word.get("sub"))): word for word in words
    }
    selected: list[tuple[int, int, int, str]] = []
    for ordinal in (10, 11, 12):
        token_index = ordinal - 1
        script_indexes = [
            index
            for index, mapped_token in enumerate(script_unit_to_token)
            if mapped_token == token_index
        ]
        if len(script_indexes) != 1:
            raise ValueError("C requested token expands to more than one spoken word")
        matches = [unit for unit in units if unit.get("scriptIndex") in script_indexes]
        if len(matches) != 1:
            raise ValueError(
                "C requested token does not map to exactly one retained spoken word"
            )
        unit = matches[0]
        if unit.get("scriptSpelling") not in (
            None,
            prompter.words[token_index]["display"],
        ):
            raise ValueError("C retained script-to-speech correspondence changed")
        aligned = word_by_key.get((unit.get("tokenIndex"), str(unit.get("sub"))))
        if aligned is None:
            raise ValueError("C requested word has no exact retained alignment row")
        start_ms = int(aligned["startMs"])
        end_ms = int(aligned["endMs"])
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError("C machine timing has an invalid range")
        selected.append(
            (ordinal, start_ms, end_ms, str(row["tokens"][token_index]["value"]))
        )

    if any(left[2] > right[1] for left, right in pairwise(selected)):
        raise ValueError("C requested machine marker ranges overlap or are unordered")
    source_duration_ms = Fraction(source_samples * 1000, source_rate)
    if Fraction(selected[-1][2]) > source_duration_ms:
        raise ValueError("C machine marker exceeds the original narration")

    marker_root = case_root / "private-review"
    marker_root.mkdir(parents=True, exist_ok=True)
    marker_path = marker_root / "VO-01-markers-prefill.csv"
    with marker_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\r\n")
        writer.writerow(
            ("Name", "Start", "Duration", "Time Format", "Type", "Description")
        )
        for ordinal, start_ms, end_ms, display_name in selected:
            description = (
                "Requested end after token 11; machine prefill only; "
                "not human-reviewed."
                if ordinal == 11
                else "Context for requested token 11 end; machine prefill only; "
                "not human-reviewed."
            )
            writer.writerow(
                (
                    display_name,
                    _audition_time(start_ms),
                    _audition_time(end_ms - start_ms),
                    "decimal",
                    "Cue",
                    description,
                )
            )

    token_11 = next(item for item in selected if item[0] == 11)
    candidate_end_frame = math.ceil(Fraction(token_11[2], 1_000) * TARGET_RATE)
    boundary_ranges = [
        {
            "tokenOrdinal": ordinal,
            "startSample": start_ms * source_rate // 1_000,
            "endSampleExclusive": end_ms * source_rate // 1_000,
            "enclosingStartFrame": math.floor(Fraction(start_ms, 1_000) * TARGET_RATE),
            "enclosingEndFrameExclusive": math.ceil(
                Fraction(end_ms, 1_000) * TARGET_RATE
            ),
        }
        for ordinal, start_ms, end_ms, _ in selected
    ]
    token_10_range, token_11_range, token_12_range = boundary_ranges
    token11_cut_feasible = (
        token_11_range["enclosingStartFrame"]
        >= token_10_range["enclosingEndFrameExclusive"]
        and token_11_range["enclosingEndFrameExclusive"]
        <= token_12_range["enclosingStartFrame"]
    )
    provenance = {
        "schemaVersion": "issue215-c-audition-prefill-v1",
        "status": "machine_prefill_only",
        "humanReviewed": False,
        "sourceAudioHash": original_hash,
        "sourceAudioDurationSamples": source_samples,
        "sourceAudioSampleRate": source_rate,
        "alignmentAudioHash": aligned_audio_hash,
        "alignmentArtifactId": alignment.get("artifactId"),
        "alignmentFileHash": _file_hash(alignment_path),
        "scriptFileHash": _file_hash(script_path),
        "reconciliationScriptHash": reconciliation["identity"]["scriptHash"],
        "recognitionArtifactId": recognition.get("artifactId"),
        "reconciliationArtifactId": reconciliation.get("artifactId"),
        "scriptDocumentId": document.get("id"),
        "narrationBlockId": row.get("id"),
        "tokenOrdinals": [10, 11, 12],
        "markerCount": 3,
        "tokenCorrespondenceValidated": True,
        "originalTimeMappingValidated": True,
        "requestedToken11EndCandidateFrame": candidate_end_frame,
        "requestedGapStartFrame": 121,
        "candidateMatchesRequestedGapStart": candidate_end_frame == 121,
        "machineTokenBoundaryRanges": boundary_ranges,
        "token11CutFeasible": token11_cut_feasible,
        "markerFileHash": _file_hash(marker_path),
    }
    _write_json(marker_root / "prefill-provenance.json", provenance)
    return {
        "markerCount": 3,
        "markerFileHash": provenance["markerFileHash"],
        "candidateMatchesRequestedGapStart": candidate_end_frame == 121,
        "requestedToken11EndCandidateFrame": candidate_end_frame,
        "machineTokenBoundaryRanges": boundary_ranges,
        "token11CutFeasible": token11_cut_feasible,
        "humanReviewed": False,
    }


def _decoded_stereo_channel_hashes(source: Path, tools: MediaTools) -> list[str]:
    decoded = tools.run(
        [
            tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-acodec",
            "pcm_s24le",
            "-f",
            "s24le",
            "pipe:1",
        ]
    )
    if not decoded or len(decoded) % 6:
        raise ValueError("B source did not decode to complete stereo PCM-24 frames")
    channels = (bytearray(), bytearray())
    for offset in range(0, len(decoded), 6):
        channels[0].extend(decoded[offset : offset + 3])
        channels[1].extend(decoded[offset + 3 : offset + 6])
    return [_sha256(bytes(channel)) for channel in channels]


def prepare_b_linked_av_case(output_root: Path) -> Json:
    """Build a two-source, full-policy linked-AV baseline with distinct media."""
    case_root = output_root / "B-original"
    _fresh_directory(case_root)
    tools = MediaTools()
    tool_hash = identity_hash(tools.fingerprint())
    source_origin_frame = 3_000
    source_in_offset = 10
    clip_specs = (
        ("selected", 91, 111, (11, 51, 99)),
        ("downstream", 48, 68, (12, 34, 57)),
    )
    clips: list[dict[str, Any]] = []
    source_identities: list[Json] = []
    for index, (label, selected_frames, source_frames, flashes) in enumerate(
        clip_specs
    ):
        media = generate_synthetic_media(
            case_root / "sources" / label,
            rate=TARGET_RATE,
            frame_count=source_frames,
            flash_frames=flashes,
            audio_sample_rate=48_000,
            audio_channels=2,
            extension=".mov",
            mux_audio="pcm_s24le",
            ffmpeg=tools.ffmpeg,
            ffprobe=tools.ffprobe,
        )
        source = media.muxed_path
        if source is None or not source.is_file():
            raise ValueError("B synthetic source lacks its linked audio stream")
        inspection = inspect_media(
            source,
            video_stream_index=0,
            audio_stream_index=1,
            tools=tools,
        )
        if (
            inspection.audio is None
            or inspection.audio.get("channels") != 2
            or int(inspection.audio.get("sample_rate", 0)) != 48_000
        ):
            raise ValueError("B source must carry decoded stereo 48 kHz audio")

        block_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{label}:block")
        )
        payload_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{label}:payload")
        )
        reference_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{label}:reference")
        )
        snapshot_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{label}:snapshot")
        )
        package_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{label}:package")
        )
        source_in_frame = source_origin_frame + source_in_offset
        occurrence = issue174_descriptor(
            inspection,
            rate=TARGET_RATE,
            audio=True,
            in_frame=source_in_frame,
        )
        occurrence["payloadId"] = payload_id
        occurrence["owner"] = {"kind": "visual_only_block", "blockId": block_id}
        occurrence["mediaReferenceId"] = reference_id
        occurrence["sourceSnapshot"].update(
            {
                "system": "local_import",
                "snapshotId": snapshot_id,
                "packageId": package_id,
            }
        )
        occurrence["selectedSourceRange"] = {
            "startFrame": source_in_frame,
            "endFrame": source_in_frame + selected_frames,
        }
        requested_range = {
            "sourceInFrame": source_in_frame,
            "duration": wire(Fraction(selected_frames, 1) / TARGET_RATE),
            "preHandle": wire(Fraction(0)),
            "postHandle": wire(Fraction(0)),
        }
        preparation = prepare_media(
            source,
            cast(Any, occurrence),
            cast(Any, requested_range),
            cast(Any, wire(TARGET_RATE)),
            authorization=PreparationAuthorization(
                reference=f"issue-215-real-B-{label}",
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
                    "startFrame": source_in_frame,
                    "durationFrames": selected_frames,
                },
            },
        }
        decoded_channels = _decoded_stereo_channel_hashes(source, tools)
        source_identities.append(
            {
                "label": label,
                "rawSourceHash": _file_hash(source),
                "decodedChannelHashes": decoded_channels,
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

    if source_identities[0]["rawSourceHash"] == source_identities[1]["rawSourceHash"]:
        raise ValueError("B source files alias byte-for-byte")
    if any(
        left == right
        for left, right in zip(
            source_identities[0]["decodedChannelHashes"],
            source_identities[1]["decodedChannelHashes"],
            strict=True,
        )
    ):
        raise ValueError("B decoded source audio channels alias")

    template_path = (
        REPOSITORY_ROOT
        / "tests"
        / "data"
        / "authoring_v2"
        / "issue_173"
        / "compiler"
        / "selected-clip-ntsc.input.golden.json"
    )
    template = _read_json(template_path)
    document = copy.deepcopy(template["document"])
    dependencies = copy.deepcopy(template["dependencies"])
    document["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vera:#215-real:B:document"))
    document["projectId"] = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "vera:#215-real:B:project")
    )
    document["activeDraft"]["blocks"] = [clip["block"] for clip in clips]
    compiler_core = REPOSITORY_ROOT / "packages/contracts/src/compiler-core-v2.ts"
    dependencies["compiler"]["sourceHash"] = _file_hash(compiler_core)
    dependencies["timeline"]["durationFrames"] = sum(
        clip["selectedFrames"] for clip in clips
    )
    dependencies["occurrenceResolutions"] = [clip["occurrence"] for clip in clips]
    dependencies["preparedMedia"] = [clip["prepared"].binding for clip in clips]
    for field in (
        "narrationBoundaryEvidence",
        "narrationTimingMaps",
        "presenterAlignmentResolutions",
    ):
        if field in dependencies:
            dependencies[field] = []
    source_audio_track_id = dependencies["roles"]["sourceAudioTrackIds"][0]
    for track in dependencies["tracks"]:
        if track["id"] == source_audio_track_id:
            track["index"] = 3
    if not any(track["id"] == "narration-second" for track in dependencies["tracks"]):
        dependencies["tracks"].append(
            {
                "id": "narration-second",
                "kind": "audio",
                "index": 2,
                "name": "Narration 2",
            }
        )
    for field in ("buildId", "manifestId", "reportId"):
        dependencies["build"][field] = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#215-real:B:{field}")
        )
    _refresh_document_binding(document, dependencies)
    inputs_root = case_root / "inputs"
    document_path = inputs_root / "script-document-v2.json"
    dependencies_path = inputs_root / "compiler-dependencies-v2.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    manifest, report = _compile(document_path, dependencies_path)
    manifest_path = inputs_root / "timeline-manifest-v2.json"
    report_path = inputs_root / "build-report-v2.json"

    clips_by_requirement = {
        clip["prepared"].binding["requirementKey"]: clip for clip in clips
    }
    media_paths: dict[str, Path] = {}
    preparation_paths: dict[str, Path] = {}
    source_by_id: dict[str, dict[str, Any]] = {}
    for clip in clips:
        preparation_paths[clip["prepared"].binding["requirementKey"]] = clip[
            "prepared"
        ].receipt_path
    for source in manifest["sources"]:
        requirement = source.get("preparationRequirementKey")
        if requirement is None:
            continue
        clip = clips_by_requirement[requirement]
        source_id = source["id"]
        source_by_id[source_id] = clip
        media_paths[f"source:{source_id}"] = clip["prepared"].video_path
        media_paths[f"original:{source_id}"] = clip["source"]
    audio_events = [
        event for event in manifest["events"] if event["kind"] == "source_audio"
    ]
    for event in audio_events:
        source_id = event["provenance"]["sourceId"]
        clip = source_by_id[source_id]
        audio_path = clip["prepared"].audio_path
        if audio_path is None:
            raise ValueError("B compiled source-audio event lacks prepared audio")
        media_paths[f"event:{event['eventId']}"] = audio_path
    if len(audio_events) != 2 or any(
        event["audio"].get("audioPolicy") != "full" for event in audio_events
    ):
        raise ValueError("B must compile two full-policy linked source-audio events")

    package_root = case_root / "package"
    build = build_v2_package(
        manifest_path,
        report_path,
        document_path,
        dependencies_path,
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    result = {
        "case": "B",
        "layer": "original",
        "selectedSourceFrameCounts": [91, 48],
        "timelineFrames": int(manifest["timeline"]["durationFrames"]),
        "eventCount": len(manifest["events"]),
        "sourceCount": len(manifest["sources"]),
        "sourceAudioEventCount": len(audio_events),
        "sourceAudioPolicies": [
            event["audio"]["audioPolicy"] for event in audio_events
        ],
        "sourceIdentities": source_identities,
        "rawSourceHashesDistinct": source_identities[0]["rawSourceHash"]
        != source_identities[1]["rawSourceHash"],
        "decodedChannelHashesDistinct": all(
            left != right
            for left, right in zip(
                source_identities[0]["decodedChannelHashes"],
                source_identities[1]["decodedChannelHashes"],
                strict=True,
            )
        ),
        "compilerBuildId": manifest["buildId"],
        "packageBuildId": build.build_id,
        "packageRoot": str(package_root),
        "reportPassed": report.get("status") == "ready",
    }
    if not result["reportPassed"]:
        raise ValueError("B compiler report is not ready")
    _write_json(case_root / "fixture-summary.json", result)
    return result


def prepare_b_selected_67_candidate(output_root: Path) -> Json:
    """Prepare the exact 67-frame post-trim media receipt, without compiling it."""
    baseline_root = output_root / "B-original"
    case_root = output_root / "B-selected-67-candidate"
    _fresh_directory(case_root)
    dependencies = _read_json(baseline_root / "inputs/compiler-dependencies-v2.json")
    if len(dependencies.get("occurrenceResolutions", [])) != 2:
        raise ValueError("B baseline does not contain two canonical source occurrences")
    occurrence = copy.deepcopy(dependencies["occurrenceResolutions"][0])
    baseline_binding = dependencies["preparedMedia"][0]
    if occurrence.get("preparedMediaRequirementKey") != baseline_binding.get(
        "requirementKey"
    ):
        raise ValueError("B selected occurrence does not match its preparation binding")
    source_range = occurrence["selectedSourceRange"]
    source_in_frame = int(source_range["startFrame"])
    if int(source_range["endFrame"]) - source_in_frame != 91:
        raise ValueError("B canonical selected range is not the expected 91 frames")
    source = (
        baseline_root
        / "sources"
        / "selected"
        / "issue174-media"
        / "source-pcm_s24le.mov"
    )
    if (
        not source.is_file()
        or _file_hash(source) != occurrence["sourceSnapshot"]["contentHash"]
    ):
        raise ValueError("B selected source bytes differ from the canonical occurrence")

    occurrence["selectedSourceRange"] = {
        "startFrame": source_in_frame,
        "endFrame": source_in_frame + 67,
    }
    requested_range = copy.deepcopy(baseline_binding["requestedRange"])
    requested_range["sourceInFrame"] = source_in_frame
    requested_range["duration"] = wire(Fraction(67, 1) / TARGET_RATE)
    tools = MediaTools()
    prepared = prepare_media(
        source,
        cast(Any, occurrence),
        cast(Any, requested_range),
        cast(Any, wire(TARGET_RATE)),
        authorization=PreparationAuthorization(
            reference="issue-215-real-B-selected-67frame-candidate",
            read_roots=(source.parent,),
            write_root=case_root / "preparations" / "selected",
            tool_hash=identity_hash(tools.fingerprint()),
            minimum_free_bytes=0,
        ),
        video_stream_index=0,
        audio_stream_index=1,
        tools=tools,
    )
    occurrence["preparedMediaRequirementKey"] = prepared.binding["requirementKey"]
    _write_json(case_root / "occurrence-resolution-v2.json", occurrence)
    _write_json(case_root / "prepared-media-binding-v1.json", prepared.binding)
    receipt = _read_json(prepared.receipt_path)
    result = {
        "case": "B",
        "purpose": "post-trim-media-preparation-only",
        "sourceHash": _file_hash(source),
        "sourceInFrame": source_in_frame,
        "selectedSourceFrameCount": 67,
        "targetRate": wire(TARGET_RATE),
        "requirementKey": prepared.binding["requirementKey"],
        "receiptPath": str(prepared.receipt_path),
        "receiptHash": _file_hash(prepared.receipt_path),
        "bindingPath": str(case_root / "prepared-media-binding-v1.json"),
        "bindingHash": _file_hash(case_root / "prepared-media-binding-v1.json"),
        "occurrencePath": str(case_root / "occurrence-resolution-v2.json"),
        "preparedVideoPath": str(prepared.video_path),
        "preparedAudioPath": str(prepared.audio_path) if prepared.audio_path else None,
        "preparedDecodedFrameCount": len(
            receipt.get("geometry", {}).get("selectedPackageFrames", [])
        ),
        "packageBuilt": False,
    }
    if (
        result["preparedDecodedFrameCount"] != 67
        or prepared.audio_path is None
        or receipt.get("policy", {}).get("version") != "cfr_sample/v1"
        or int(receipt.get("audio", {}).get("decodedSamples", 0)) <= 0
    ):
        raise ValueError(
            "B 67-frame preparation receipt did not verify the requested range"
        )
    _write_json(case_root / "preparation-summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case", choices=("A", "B", "B67", "C"), default="A")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if not source_root.is_dir() or source_root.is_symlink():
        raise ValueError("source root must be an existing real directory")
    output_root = args.output_root
    if not output_root.is_absolute():
        raise ValueError("output root must be absolute")
    if not output_root.exists():
        output_root.mkdir(parents=True)
    if output_root.is_symlink() or not output_root.is_dir():
        raise ValueError("output root must be a real directory")
    if args.case == "A":
        result = prepare_original_narration_case(
            source_root,
            output_root,
            label="A",
            token_count=81,
            visual_slot_limit=2,
            output_name="A-original-02",
        )
    elif args.case == "B":
        result = prepare_b_linked_av_case(output_root)
    elif args.case == "B67":
        result = prepare_b_selected_67_candidate(output_root)
    else:
        result = prepare_original_narration_case(
            source_root,
            output_root,
            label="C",
            token_count=21,
            visual_slot_limit=1,
            output_name="C-original",
        )
        result["auditionPrefill"] = prepare_c_audition_prefill(
            output_root / "C-original", source_root
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
