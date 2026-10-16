"""Injected Studio delivery: standard library only, no external connection."""

from __future__ import annotations

import platform
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .studio_spike import (
    PublicResolveAdapter as AcceptedResolveAdapter,
)
from .studio_spike import _project_settings
from .workflow_package import SOURCE_PINS, load_verified_package, sha256

DELIVERY_VERSION = "1"
SUPPORTED_IDENTITIES = {("21.1.0", "14"), ("21.1.1", "10")}


class PublicResolveAdapter(AcceptedResolveAdapter):
    """Keep #34 assembly calibration and add complete package inventory readback."""

    def __init__(self, resolve: Any) -> None:
        super().__init__(resolve)
        self.expected_project_id: str | None = None
        self.expected_timeline_id: str | None = None

    def create_project(self, name: str) -> None:
        super().create_project(name)
        identity = self.project.GetUniqueId()
        if not isinstance(identity, str) or not identity:
            raise ValueError("created project has no unique identity")
        self.expected_project_id = identity
        self.assert_current_target()

    def create_timeline(self, name: str) -> None:
        super().create_timeline(name)
        identity = self.timeline.GetUniqueId()
        if not isinstance(identity, str) or not identity:
            raise ValueError("created timeline has no unique identity")
        self.expected_timeline_id = identity
        self.assert_current_target()

    def assert_current_target(self) -> None:
        current = self.manager.GetCurrentProject()
        if (
            self.expected_project_id is None
            or current is None
            or current.GetUniqueId() != self.expected_project_id
            or self.project.GetUniqueId() != self.expected_project_id
        ):
            raise ValueError("current project changed; refusing native mutation")
        if self.expected_timeline_id is not None:
            timeline = current.GetCurrentTimeline()
            if timeline is None or timeline.GetUniqueId() != self.expected_timeline_id:
                raise ValueError("current timeline changed; refusing native mutation")

    def save_close_reopen(self, project_name: str) -> None:
        self.assert_current_target()
        if not self.manager.SaveProject():
            raise ValueError("SaveProject failed")
        self.assert_current_target()
        if not self.manager.CloseProject(self.project):
            raise ValueError("CloseProject failed after save")
        self.project = self.manager.LoadProject(project_name)
        if self.project is None:
            raise ValueError("LoadProject failed after close")
        if self.project.GetUniqueId() != self.expected_project_id:
            raise ValueError("reopened project unique identity differs")
        if self.project.GetTimelineCount() != 1:
            raise ValueError("reopened project must contain exactly one timeline")
        self.pool = self.project.GetMediaPool()
        self.timeline = self.project.GetCurrentTimeline()
        self.assert_current_target()

    def _still_end_frame_compensation(self) -> int:
        # 21.1.1/10 is a calibration candidate; reopened ranges must prove this.
        return 0

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        super().import_media(sources)
        self.expected_paths = {source_id: path.resolve() for source_id, path in sources}

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        discrepancies = list(super().verify(manifest))
        for track in manifest.get("tracks", []):
            if track["index"] > self.timeline.GetTrackCount(track["kind"]):
                continue
            expected = sorted(
                (
                    event
                    for event in manifest["events"]
                    if event["trackId"] == track["id"]
                ),
                key=lambda event: event["recordRange"]["startFrame"],
            )
            actual_items = sorted(
                self.timeline.GetItemListInTrack(track["kind"], track["index"]),
                key=lambda item: item.GetStart(False),
            )
            if len(expected) != len(actual_items):
                continue
            for event, item in zip(expected, actual_items, strict=True):
                source_range = event.get("sourceRange")
                if source_range is not None and item.GetSourceEndFrame() != (
                    source_range["startFrame"] + source_range["durationFrames"] - 1
                ):
                    # GetSourceEndFrame is inclusive in retained #141/#144 readback.
                    discrepancies.append(f"event {event['id']}: source end mismatch")
        markers = self.timeline.GetMarkers()
        expected_frames = {marker["frame"] for marker in manifest["markers"]}
        if not isinstance(markers, dict) or set(markers) != expected_frames:
            discrepancies.append("marker inventory differs from manifest")
        discrepancies.extend(self._verify_v1_media_inventory(manifest))
        return tuple(discrepancies)

    def _verify_v1_media_inventory(
        self, manifest: Mapping[str, Any]
    ) -> tuple[str, ...]:
        discrepancies: list[str] = []
        folder = self.pool.GetRootFolder()
        for name in self.created_bins:
            folder = next(
                (
                    child
                    for child in folder.GetSubFolderList()
                    if child.GetName() == name
                ),
                None,
            )
            if folder is None:
                return (*discrepancies, "package media folder is unavailable")
        timeline_media = self.timeline.GetMediaPoolItem()
        timeline_media_id = timeline_media.GetMediaId() if timeline_media else None
        media = [
            item
            for item in folder.GetClipList()
            if item.GetMediaId() != timeline_media_id
        ]
        if len(media) != len(manifest["sources"]):
            discrepancies.append("package media count differs from manifest")
        actual = {
            item.GetMediaId(): item.GetClipProperty("File Path") for item in media
        }
        for source in manifest["sources"]:
            source_id = source["id"]
            media_id = self.media_id_by_source[source_id]
            file_path = actual.get(media_id)
            if (
                not isinstance(file_path, str)
                or not file_path
                or Path(file_path).resolve() != self.expected_paths[source_id]
            ):
                discrepancies.append(
                    f"source {source_id}: reopened media identity differs"
                )
        pending = [self.pool.GetRootFolder()]
        while pending:
            current = pending.pop()
            if current.GetUniqueId() != folder.GetUniqueId() and any(
                item.GetMediaId() != timeline_media_id for item in current.GetClipList()
            ):
                discrepancies.append(
                    "unexpected media outside the package media folder"
                )
            pending.extend(current.GetSubFolderList())
        return tuple(discrepancies)


def run_workflow_delivery(
    resolve: Any,
    attestation_path: Path,
    attestation_sha256: str,
    *,
    action: str = "preflight",
    authorize_new_nonproduction: bool = False,
    external_scripting: str | None = None,
    adapter_factory: Callable[[Any], PublicResolveAdapter] | None = None,
    handoff_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """One audited operator action; failures never delete or reuse a target."""
    result: dict[str, Any] = {
        "schemaVersion": "vera-injected-delivery-result/v1",
        "deliveryVersion": DELIVERY_VERSION,
        "sourcePins": SOURCE_PINS,
        "startedAt": datetime.now(UTC).isoformat(),
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "injectedObjectAvailable": resolve is not None,
        "externalScriptingOperatorStatement": external_scripting,
        "action": action,
        "attestationSha256": attestation_sha256,
        "status": "stopped_safely",
        "verified": False,
        "discrepancies": [],
        "partialTargetRetained": False,
    }
    mutation_started = False
    try:
        if action not in {"preflight", "build"}:
            raise ValueError("action must be preflight or build")
        if action == "build" and (
            authorize_new_nonproduction is not True or external_scripting != "None"
        ):
            raise ValueError(
                "build requires explicit new nonproduction target authorization "
                "and operator confirmation of External Scripting None"
            )
        if handoff_guard is not None:
            handoff_guard()
        package = load_verified_package(attestation_path, attestation_sha256)
        manifest = package.manifest
        attestation = package.attestation
        result.update(
            {
                "buildId": attestation["buildId"],
                "projectName": attestation["projectName"],
                "timelineName": attestation["timelineName"],
                "packageDir": str(package.root),
                "verification": attestation["verification"],
                "verifier": attestation["verifier"],
                "packageVerifiedAt": attestation["verifiedAt"],
                "manifestSha256": sha256(
                    package.root
                    / "Builds"
                    / attestation["buildId"]
                    / "timeline-manifest.json"
                ),
            }
        )
        if resolve is None:
            raise ValueError("Resolve did not inject an API object")
        if manifest["timeline"]["startFrame"] != 0:
            raise ValueError("delivery supports only frame-zero timelines")
        adapter = (adapter_factory or PublicResolveAdapter)(resolve)
        connected = adapter.connected_facts()
        result["connected"] = asdict(connected)
        if (
            connected.edition != "studio"
            or not connected.scripting_available
            or connected.suffix
            or (connected.version, connected.build) not in SUPPORTED_IDENTITIES
        ):
            raise ValueError("unsupported injected Studio version/build/edition")
        result["versionEvidence"] = (
            "accepted-34-baseline"
            if connected.version == "21.1.0"
            else "21.1.1-10-calibration-candidate-awaiting-producer-acceptance"
        )
        settings = _project_settings(manifest["timeline"])
        result["manualCompletion"] = list(adapter.probe(settings))
        adapter.check_project_name_available(attestation["projectName"])
        load_verified_package(attestation_path, attestation_sha256)
        if action == "preflight":
            result["status"] = "preflight_passed"
            result["message"] = "Read-only injected preflight passed."
            return result

        def mutate(method: Any, *arguments: Any) -> None:
            nonlocal mutation_started
            if handoff_guard is not None:
                handoff_guard()
            current = load_verified_package(attestation_path, attestation_sha256)
            if current != package:
                raise ValueError("handoff changed before native mutation")
            if mutation_started:
                adapter.assert_current_target()
            mutation_started = True
            method(*arguments)

        mutate(adapter.create_project, attestation["projectName"])
        mutate(adapter.configure_project, settings)
        mutate(adapter.create_bin, "VERA Studio Assembly")
        mutate(adapter.create_bin, "Package Media")
        sources: list[tuple[str, Path]] = []
        for source in manifest["sources"]:
            path = (
                package.root / "Media" / "Placeholders" / f"{source['id']}.png"
                if source["kind"] == "placeholder"
                else package.root / source["path"]
            )
            sources.append((cast(str, source["id"]), path.resolve(strict=True)))
        mutate(adapter.import_media, sources)
        mutate(adapter.create_timeline, attestation["timelineName"])
        mutate(adapter.configure_tracks, manifest["tracks"])
        mutate(adapter.place_events, manifest["events"])
        import json

        for marker in manifest["markers"]:
            custom = json.dumps(
                {"markerId": marker["id"], "provenance": marker["provenance"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            mutate(adapter.add_marker, marker, custom)
        mutate(adapter.save_close_reopen, attestation["projectName"])
        if handoff_guard is not None:
            handoff_guard()
        load_verified_package(attestation_path, attestation_sha256)
        discrepancies = adapter.verify(manifest)
        result["discrepancies"] = list(discrepancies)
        result["verified"] = not discrepancies
        result["status"] = "verification_failed" if discrepancies else "verified"
        result["partialTargetRetained"] = bool(discrepancies)
        result["message"] = (
            "New project saved, reopened, and compared against the canonical manifest."
        )
    except Exception as error:
        result["status"] = "mutation_failed" if mutation_started else "stopped_safely"
        result["partialTargetRetained"] = mutation_started
        result["message"] = str(error)
        result["failureType"] = type(error).__name__
        result["discrepancies"] = [str(error)] if mutation_started else []
    finally:
        result["finishedAt"] = datetime.now(UTC).isoformat()
    return result
