"""Prepare project-local media and the inputs consumed by build_timeline_cli."""

from __future__ import annotations

import argparse
import sys
import tempfile
import unicodedata
from collections.abc import Callable, Mapping
from pathlib import Path
from time import monotonic
from typing import Any

from .build_compiler_bridge import invoke_bridge
from .build_jobs import BuildJobError, publish_immutable_output
from .build_stage_receipt import canonical_json, hash_file
from .build_timeline_once import _companion
from .media_preparation import MediaPreparationError, MediaTools
from .narration.cache import NarrationCache
from .narration.cli import _validate_script
from .narration.configuration import DEFAULT_PROFILE_ID, provider_for
from .narration.models import identity_hash, sha256_bytes
from .narration.normalize import Normalizer
from .narration.service import VOICE_PROFILES, NarrationService
from .narration.stage_directions import is_direction_only
from .placeholder_slate import render_placeholder_slate
from .prep_media_inputs import (
    compiler_media_needs,
    prepare_cut_inputs,
    prepare_still_inputs,
    read_json_object,
)
from .prep_media_research_still import (
    KeptStillReader,
    ResearchStillError,
    bind_research_still_descriptor,
    materialize_research_still,
)
from .quote_box_inputs import freeze_quote_box_inputs
from .research_cut_binding import (
    bind_research_cut,
    copy_cut,
    find_cached_research_cut,
    research_clip_folder,
)
from .v2_package import _compiler_hash

Json = dict[str, Any]


def _plain(path: Path) -> Path:
    path = path.absolute()
    if ".." in path.parts or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Prep Media paths must be local and cannot use symlinks")
    return path


def _label(snapshot: Json) -> str:
    title = snapshot["video"]["title"]
    sanitized = "".join(
        " " if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"} else char
        for char in title
    )
    return " ".join(sanitized.split())[:100] or snapshot["clipId"]


def failed_fetch_slate(row: Json) -> None:
    """Build-only placeholder; duration is logged time, with no source-frame claim."""
    snapshot = row.pop("researchClip")
    selection = snapshot["loggedSelection"]
    duration = selection["exportEndMs"] - selection["exportStartMs"]
    if not 0 < duration <= (1 << 53) - 1:
        raise ValueError("Failed Research clip has no positive logged duration")
    row["payload"].update(
        pictureKind="intentional_placeholder",
        source={
            "kind": "intentional_placeholder",
            "text": f"Unavailable: {_label(snapshot)}",
        },
        audioPolicy="mute",
    )
    row["visualOnlyTiming"] = {"kind": "visual_only", "durationOverrideMs": duration}


def _handoff_hash(root: Path) -> str:
    return identity_hash(
        {
            name: hash_file(_plain(root / name))
            for name in (
                "compiler-dependencies.json",
                "preparation-paths.json",
                "media-paths.json",
                "script.json",
                "prep-media.json",
            )
        }
    ).removeprefix("sha256:")


def _reuse_handoff(
    root: Path,
    key: str,
    document: Json,
    media_root: Path,
    report: Callable[[str], None],
) -> Path | None:
    for path in sorted(root.glob(f"{key}-*")):
        _plain(path)
        info = read_json_object(path / "prep-media.json")
        if not info["reusable"]:
            continue
        if path.name != f"{key}-{_handoff_hash(path)}":
            raise ValueError("Prepared build inputs changed on disk")
        if any(not _plain(Path(locator)).exists() for locator in info["assets"]):
            continue
        for locator, digest in info["assets"].items():
            if hash_file(_plain(Path(locator))) != digest:
                raise ValueError("A prepared media file changed on disk")
        for row in document["activeDraft"]["blocks"]:
            if row["type"] == "visual_only" and row.get("researchClip"):
                started = monotonic()
                snapshot = row["researchClip"]
                if (
                    find_cached_research_cut(
                        research_clip_folder(media_root, snapshot), snapshot
                    )
                    is None
                ):
                    raise ValueError("A verified project Research copy is missing")
                report(f"{_label(snapshot)}: reused ({monotonic() - started:.2f}s)")
        for timing in read_json_object(path / "compiler-dependencies.json")[
            "narrationTimingMaps"
        ]:
            report(f"Narration {timing['blockId']}: reused")
        return path
    return None


def _check_narrated_research(document: Json) -> None:
    for row in document["activeDraft"]["blocks"]:
        if row["type"] != "narration" or row["state"] != "active":
            continue
        attached = (row.get("attachedFootage") or {}).get("clip", {})
        sequence = row.get("primaryVisualSequence") or {}
        visuals = [
            attached,
            *(slot.get("payload", {}) for slot in sequence.get("slots", [])),
        ]
        for visual in visuals:
            snapshot = visual.get("researchClip")
            if snapshot and not visual.get("frameBinding"):
                raise ValueError(
                    f"RESEARCH_MEDIA_UNRESOLVED: {_label(snapshot)} on narration "
                    f"row {row['id']} needs a verified source binding"
                )


def _research_still_occurrences(document: Json) -> list[tuple[Json, Json]]:
    """Return active kept-still payloads with their compiler occurrence owner."""
    occurrences: list[tuple[Json, Json]] = []

    def add(value: Any, owner: Json) -> None:
        if isinstance(value, dict) and value.get("researchStill") is not None:
            occurrences.append((value, owner))

    draft = document.get("activeDraft")
    blocks = draft.get("blocks") if isinstance(draft, dict) else None
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict) or (block.get("type"), block.get("state")) != (
            "narration",
            "active",
        ):
            continue
        sequence = block.get("primaryVisualSequence")
        if isinstance(sequence, dict) and isinstance(
            slots := sequence.get("slots"), list
        ):
            for slot in slots:
                if isinstance(slot, dict) and slot.get("kind") == "content":
                    add(
                        slot.get("payload"),
                        {
                            "kind": "primary_slot",
                            "sequenceId": sequence.get("id"),
                            "slotId": slot.get("id"),
                        },
                    )
        overlays = block.get("overlayEvents")
        for overlay in overlays if isinstance(overlays, list) else []:
            if isinstance(overlay, dict):
                add(
                    overlay.get("payload"),
                    {
                        "kind": "overlay_event",
                        "blockId": block.get("id"),
                        "overlayEventId": overlay.get("id"),
                    },
                )
    return occurrences


def _prepare_research_stills(
    occurrences: list[tuple[Json, Json]],
    dependencies: Json,
    media_paths: Json,
    media_root: Path,
    *,
    tools: MediaTools,
    research_origin: str,
    reader: KeptStillReader | None,
) -> None:
    """Resolve kept stills before compiler needs and ordinary still preparation."""
    for payload, owner in occurrences:
        snapshot = payload.get("researchStill")
        source = payload.get("source")
        if (
            not isinstance(snapshot, Mapping)
            or not isinstance(source, Mapping)
            or source.get("kind") != "media_reference"
            or not isinstance(source.get("mediaReferenceId"), str)
            or payload.get("pictureKind") != "image"
        ):
            raise ResearchStillError(
                "Research still must use an ordinary image media reference"
            )
        payload_id = payload.get("payloadId")
        media_reference_id = source["mediaReferenceId"]
        matches = [
            (index, descriptor)
            for index, descriptor in enumerate(dependencies["occurrenceResolutions"])
            if descriptor.get("payloadId") == payload_id
        ]
        if len(matches) > 1:
            raise ResearchStillError(
                "Research still occurrence has no unique frozen source descriptor"
            )
        foreign = [
            descriptor
            for descriptor in dependencies["occurrenceResolutions"]
            if descriptor.get("mediaReferenceId") == media_reference_id
            and descriptor.get("payloadId") != payload_id
        ]
        if foreign:
            raise ResearchStillError(
                "Research still media reference is already bound to another occurrence"
            )
        if matches:
            index, descriptor = matches[0]
            if descriptor.get("owner") != owner:
                raise ResearchStillError(
                    "Research still descriptor owner differs from its saved occurrence"
                )
        else:
            index = len(dependencies["occurrenceResolutions"])
            descriptor = {
                "payloadId": payload_id,
                "owner": owner,
                "mediaReferenceId": media_reference_id,
            }
            dependencies["occurrenceResolutions"].append(descriptor)
        if descriptor.get("mediaReferenceId") != media_reference_id:
            raise ResearchStillError(
                "Research still source identity differs from its occurrence descriptor"
            )
        materialized = materialize_research_still(
            snapshot,
            media_root,
            reader=reader,
            research_origin=research_origin,
        )
        dependencies["occurrenceResolutions"][index] = bind_research_still_descriptor(
            descriptor,
            materialized,
            tools=tools,
            frame_rate=dependencies["timeline"]["frameRate"],
        )
        media_paths[f"source:{media_reference_id}"] = str(materialized.source_path)


def prepare_project(
    script: Path,
    input_root: Path,
    project_root: Path,
    *,
    acquire: Callable[[Json], Path | None],
    narration: Callable[..., None],
    report: Callable[[str], None] = print,
    tools: MediaTools | None = None,
    narration_key: str = "default",
    speech_cuts: bool = False,
    research_origin: str = "http://127.0.0.1:43110",
    catalog_origin: str = "http://127.0.0.1:43111",
    research_still_reader: KeptStillReader | None = None,
) -> Path:
    """Prepare the active draft; the input script and previous builds stay intact.

    The acquisition callback returns None only for an evidenced failed download.
    Every other failure stops preparation and leaves unbound source data intact.
    """
    started = monotonic()
    script, input_root, project_root = map(_plain, (script, input_root, project_root))
    if not project_root.is_dir():
        raise ValueError("Choose an existing project directory")
    raw_document = read_json_object(script)
    dependency_path = _companion(input_root, "compiler-dependencies.json")
    if dependency_path is None:
        raise ValueError("Prep Media requires compiler-dependencies.json")
    dependencies = read_json_object(dependency_path)
    if dependencies.get("schemaVersion") != "compiler-dependencies/v2":
        raise ValueError("Prep Media requires v2 compiler settings")
    if speech_cuts and dependencies["compiler"]["version"] == "compiler/v2":
        dependencies["compiler"]["version"] = "compiler/v2-speech-cuts"
    frozen = dependencies["document"]
    for document_key, frozen_key in (
        ("id", "documentId"),
        ("projectId", "projectId"),
        ("liveContentHash", "contentHash"),
        ("liveHeadSequence", "liveHeadSequence"),
    ):
        if raw_document[document_key] != frozen[frozen_key]:
            raise ValueError("Compiler inputs belong to a different frozen script")
    authored_digest = _compiler_hash(raw_document)
    freeze_quote_box_inputs(raw_document, dependencies)

    def validated_document() -> Json:
        document, diagnostics = _validate_script(script)
        if (
            document != raw_document
            or raw_document.get("schemaVersion") != "script-document/v2"
        ):
            raise ValueError(
                f"Prep Media requires a valid v2 script: {diagnostics[:500]}"
            )
        return raw_document

    media_root = _plain(project_root / "Media")
    media_root.mkdir(exist_ok=True)

    def companion(name: str) -> Json:
        path = _companion(input_root, name)
        return read_json_object(path) if path is not None else {}

    preparations = companion("preparation-paths.json")
    media_paths = companion("media-paths.json")
    tools = tools or MediaTools()
    kept_stills = _research_still_occurrences(raw_document)
    if kept_stills:
        validated_document()
        _prepare_research_stills(
            kept_stills,
            dependencies,
            media_paths,
            media_root,
            tools=tools,
            research_origin=catalog_origin,
            reader=research_still_reader,
        )
    root = _plain(media_root / "Build Inputs")
    root.mkdir(exist_ok=True)
    key = identity_hash(
        {
            "version": 3,
            "document": raw_document,
            "dependencies": dependencies,
            "preparations": preparations,
            "mediaPaths": media_paths,
            "voice": narration_key,
        }
    ).removeprefix("sha256:")
    prior = _reuse_handoff(root, key, raw_document, media_root, report)
    if prior is not None:
        report(f"Reused prepared build inputs; total {monotonic() - started:.2f}s")
        return prior
    document = raw_document if kept_stills else validated_document()
    _check_narrated_research(document)
    cut_sources: dict[str, Path] = {}
    clip_times: dict[str, tuple[str, str, float]] = {}
    mappings = dependencies["occurrenceResolutions"]
    ready = reused = failed = 0
    # A failed acquisition is reused within a single run, but a later run retries.
    failed_revisions: set[tuple[str, int]] = set()
    for row in document["activeDraft"]["blocks"]:
        if row["type"] != "visual_only" or not row.get("researchClip"):
            continue
        snapshot = row["researchClip"]
        item_start = monotonic()
        name = _label(snapshot)
        payload_id = row["payload"]["payloadId"]
        directory = research_clip_folder(media_root, snapshot)
        cut = find_cached_research_cut(directory, snapshot)
        status = "reused"
        if cut is None:
            revision = (snapshot["clipId"], snapshot["clipVersion"])
            candidate = None if revision in failed_revisions else acquire(snapshot)
            if candidate is None:
                if row.get("frameBinding") is not None:
                    raise ValueError(
                        "Failed acquisition cannot replace a verified Research binding"
                    )
                failed_revisions.add(revision)
                failed_fetch_slate(row)
                report(
                    f"{name}: fetch failed; labelled slate "
                    f"({monotonic() - item_start:.2f}s)"
                )
                failed += 1
                continue
            cut = copy_cut(candidate, snapshot, directory)
            status = "copied"
        # Keep already prepared inputs from other sources, and replace only the
        # matching Research descriptor after verifying the same source binding.
        path, _, descriptor = bind_research_cut(row, cut, tools)
        mappings[:] = [entry for entry in mappings if entry["payloadId"] != payload_id]
        mappings.append(descriptor)
        cut_sources[payload_id] = path
        clip_times[payload_id] = (name, status, monotonic() - item_start)
        ready += 1
        reused += status == "reused"

    if cut_sources or failed:
        document.pop("liveContentHash")
        document["liveContentHash"] = _compiler_hash(document)
        frozen["contentHash"] = document["liveContentHash"]

    def report_cut(payload_id: str, reused_media: bool, elapsed: float) -> None:
        name, status, clip_time = clip_times[payload_id]
        action = "reused" if status == "reused" and reused_media else "prepared"
        report(f"{name}: {action} ({clip_time + elapsed:.2f}s)")

    with tempfile.TemporaryDirectory(prefix=".prep-", dir=root) as attempt:
        stage = Path(attempt) / "inputs"
        stage.mkdir()
        prepared_script = stage / "script.json"
        prepared_script.write_bytes(canonical_json(document))
        narration(prepared_script, dependencies, media_paths, media_root)
        needs = compiler_media_needs(prepared_script, dependencies, media_root)
        dependencies["timeline"]["durationFrames"] = needs["durationFrames"]
        still_delivery = prepare_still_inputs(
            needs,
            dependencies,
            media_paths,
            preparations,
            media_root,
            tools=tools,
            report=report,
        )
        cut_delivery = prepare_cut_inputs(
            prepared_script,
            dependencies,
            cut_sources,
            preparations,
            media_root,
            tools=tools,
            needs=needs,
            report=report_cut,
        )
        delivery = {**cut_delivery, **still_delivery}
        keys = {
            entry["preparedMediaRequirementKey"]
            for entry in mappings
            if entry.get("preparedMediaRequirementKey") is not None
        }
        dependencies["preparedMedia"] = [
            binding
            for binding in dependencies["preparedMedia"]
            if binding["requirementKey"] in keys
        ]
        preparations = {
            key: value for key, value in preparations.items() if key in keys
        }
        for filename, value in (
            ("compiler-dependencies.json", dependencies),
            ("preparation-paths.json", preparations),
        ):
            (stage / filename).write_bytes(canonical_json(value))
        # Use the shipping compiler to preserve its refusal for all other
        # unbound input and check the final, reusable handoff before publishing.
        built = invoke_bridge(
            "compile", prepared_script, stage / "compiler-dependencies.json"
        )
        manifest = built.result["manifest"]
        delivered = {}
        for source in manifest["sources"]:
            if source.get("preparationRequirementKey") in still_delivery:
                media_paths.pop(f"source:{source['mediaReferenceId']}", None)
        for source in manifest["sources"]:
            pair = delivery.get(source.get("preparationRequirementKey"))
            if pair is None:
                continue
            original, prepared = pair
            source_id = source["id"]
            delivered[source_id] = prepared
            media_paths[f"original:{source_id}"] = str(original)
            media_paths[f"source:{source_id}"] = str(prepared.video_path)
        for event in manifest["events"]:
            locator = f"event:{event['eventId']}"
            provenance = event["provenance"]
            treatment = event.get("pictureTreatment", {})
            if (
                event["kind"] == "placeholder"
                and treatment.get("kind") == "slate"
                and treatment.get("purpose") == "intentional"
                and locator not in media_paths
            ):
                text = treatment["text"]
                size = manifest["timeline"]
                data = render_placeholder_slate(text, size["width"], size["height"])
                digest = sha256_bytes(data).removeprefix("sha256:")
                path = _plain(media_root / "Slates" / f"{digest}.png")
                publish_immutable_output(path, data)
                media_paths[locator] = str(path)
            elif event["kind"] == "source_audio":
                audio = delivered.get(provenance["sourceId"])
                if audio is not None:
                    if audio.audio_path is None:
                        raise ValueError("Prepared Research audio sidecar is missing")
                    media_paths[locator] = str(audio.audio_path)
        (stage / "media-paths.json").write_bytes(canonical_json(media_paths))
        assets = set(preparations.values()) | set(media_paths.values())
        (stage / "prep-media.json").write_bytes(
            canonical_json(
                {
                    "reusable": not failed,
                    "authoredDocumentDigest": authored_digest,
                    "preparedScriptSha256": hash_file(prepared_script),
                    "assets": {
                        path: hash_file(_plain(Path(path))) for path in sorted(assets)
                    },
                }
            )
        )
        destination = _plain(root / f"{key}-{_handoff_hash(stage)}")
        if not destination.exists():
            stage.rename(destination)
        else:
            for path in stage.iterdir():
                existing = _plain(destination / path.name)
                if existing.read_bytes() != path.read_bytes():
                    raise ValueError("Prepared compiler inputs were modified")
    report(
        f"Research clips: {ready} ready ({reused} reused), {failed} slates; "
        f"total {monotonic() - started:.2f}s"
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    from .prep_media_narration import (
        narration_service_config,
        prepare_v2_narration_inputs,
    )
    from .prep_media_research import acquire_research_cut

    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--script", required=True, type=Path)
    command.add_argument(
        "--inputs", type=Path, help="Frozen v2 compiler settings directory"
    )
    command.add_argument("--project-root", required=True, type=Path)
    command.add_argument("--research-export-root", type=Path)
    command.add_argument("--research-origin", default="http://127.0.0.1:43110")
    command.add_argument("--catalog-origin", default="http://127.0.0.1:43111")
    command.add_argument("--confirm-source-rights", action="store_true")
    command.add_argument(
        "--voice-profile",
        choices=tuple(sorted(VOICE_PROFILES)),
        default=DEFAULT_PROFILE_ID,
    )
    command.add_argument(
        "--data-policy",
        choices=(
            "opt_out_confirmed",
            "provider_terms_accepted",
            "fish_terms_accepted",
            "inworld_terms_accepted",
        ),
    )
    command.add_argument("--confirm-provider-call", action="store_true")
    command.add_argument("--max-cost-usd", type=float, default=0.0)
    args = command.parse_args(argv)

    def acquire(snapshot: Json) -> Path | None:
        if args.research_export_root is None or not args.confirm_source_rights:
            raise ValueError(
                "A missing clip requires --research-export-root "
                "and --confirm-source-rights"
            )
        result = acquire_research_cut(
            snapshot,
            args.research_export_root,
            research_origin=args.research_origin,
            catalog_origin=args.catalog_origin,
        )
        return result if isinstance(result, Path) else None

    def narration(
        script: Path, dependencies: Json, media_paths: Json, media_root: Path
    ) -> None:
        recorded_ids = {
            row["blockId"] for row in dependencies.get("narrationBoundaryEvidence", [])
        }
        if not any(
            block["type"] == "narration"
            and block["state"] == "active"
            and block["id"] not in recorded_ids
            and not is_direction_only(block)
            for block in read_json_object(script)["activeDraft"]["blocks"]
        ):
            return
        config = narration_service_config(
            args.voice_profile,
            data_policy_attestation=args.data_policy,
            max_cost_usd=args.max_cost_usd,
        )
        service = NarrationService(
            cache=NarrationCache(_plain(media_root / "Narration")),
            provider=provider_for(config.profile),
            normalizer=Normalizer(),
            config=config,
        )
        prepared = prepare_v2_narration_inputs(
            script,
            service,
            confirm_provider_call=args.confirm_provider_call,
            data_policy_attestation=args.data_policy,
            max_cost_usd=args.max_cost_usd,
            skip_block_ids=recorded_ids,
            measure_quiet_gaps=dependencies["compiler"]["version"]
            == "compiler/v2-speech-cuts",
        )
        for timing in dependencies["narrationTimingMaps"]:
            if timing["blockId"] not in recorded_ids:
                media_paths.pop(f"source:{timing['narrationAssetId']}", None)
        dependencies["narrationTimingMaps"] = prepared.narration_timing_maps
        if dependencies["compiler"]["version"] == "compiler/v2-speech-cuts":
            dependencies["narrationQuietGapEvidence"] = prepared.quiet_gaps
        media_paths.update(prepared.media_paths)

    try:
        prepared_root = prepare_project(
            args.script,
            args.inputs or args.script.parent,
            args.project_root,
            acquire=acquire,
            narration=narration,
            narration_key=f"{args.voice_profile}:{args.data_policy}",
            speech_cuts=True,
            research_origin=args.research_origin,
            catalog_origin=args.catalog_origin,
        )
    except (
        BuildJobError,
        OSError,
        KeyError,
        ValueError,
        MediaPreparationError,
    ) as error:
        print(f"Prep Media stopped: {error}", file=sys.stderr)
        return 1
    print(f"Prepared script: {prepared_root / 'script.json'}")
    print(f"Build inputs: {prepared_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
