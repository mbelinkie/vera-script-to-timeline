"""Hash-bound EV24 handoff and injected delivery; standard library only."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .studio_graphics_runtime import (
    ATLAS_SHA256,
    FILE_HASHES,
    TEMPLATE_REL,
    PublicStudioGraphicAdapter,
    StudioGraphicPackage,
    _canonical_json,
    _hash,
    _package_digest,
    _require_live_plan,
    transport_artifacts,
    validate_graphics,
)
from .studio_spike import PublicResolveAdapter as MediaAdapter
from .workflow_delivery import PublicResolveAdapter as WorkflowAdapter
from .workflow_delivery import run_workflow_delivery
from .workflow_package import (
    SOURCE_PINS,
    VerifiedPackage,
    file_inventory,
    load_verified_package,
    read_object,
    sha256,
)

GRAPHIC_PINS = {**SOURCE_PINS, "issue109": "8ef9f864acafbfa77ace5f3c699ef5cfb0e6ecb7"}
GRAPHIC_ATTESTATION = "vera-studio-graphic-attestation/v1"
GRAPHIC_REQUEST = "vera-studio-graphic-request/v1"


@dataclass(frozen=True)
class GraphicHandoff:
    root: Path
    manifest: dict[str, Any]
    attestation: dict[str, Any]
    studio: StudioGraphicPackage
    transport: VerifiedPackage


def load_graphic_handoff(path: Path, expected_sha256: str) -> GraphicHandoff:
    payload = path.read_bytes()
    if path.is_symlink() or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("graphic attestation hash mismatch or unsafe path")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("graphic attestation must contain one JSON object")
    if (
        value.get("schemaVersion") != GRAPHIC_ATTESTATION
        or value.get("status") != "ready_for_studio"
        or value.get("sourcePins") != GRAPHIC_PINS
    ):
        raise ValueError("unverified graphic attestation")
    root = Path(value["packageDir"])
    transport_path = Path(value["transportAttestationPath"])
    if (
        not root.is_absolute()
        or not transport_path.is_absolute()
        or path.resolve().is_relative_to(root.resolve())
        or value.get("packageFiles") != file_inventory(root)
        or any(p.is_file() and p.stat().st_nlink != 1 for p in root.rglob("*"))
    ):
        raise ValueError("stale or unsafe full Studio envelope")
    transport = load_verified_package(
        transport_path, value["transportAttestationSha256"]
    )
    if transport.root.resolve() != (root / "Transport").resolve():
        raise ValueError("transport belongs to another Studio envelope")
    for key in ("buildId", "projectName", "timelineName", "verifier", "verifiedAt"):
        if value.get(key) != transport.attestation[key]:
            raise ValueError("graphic and transport attestation identities differ")
    manifest = read_object(root / "timeline-manifest.json")
    report = read_object(root / "build-report.json")
    receipt = read_object(root / "studio-package.json")
    template = read_object(root / TEMPLATE_REL / "package-manifest.json")
    if (
        manifest["buildId"] != value["buildId"]
        or receipt["manifestHash"]
        != "sha256:" + sha256(root / "timeline-manifest.json")
        or receipt["reportHash"] != "sha256:" + sha256(root / "build-report.json")
        or receipt["packageDigest"] != _package_digest(template)
    ):
        raise ValueError("graphic compiler/template identity differs")
    validate_graphics(manifest)
    _require_live_plan(manifest, report)
    media, media_report = transport_artifacts(manifest, report)
    build = transport.root / "Builds" / value["buildId"]
    if (
        media != transport.manifest
        or (build / "timeline-manifest.json").read_bytes() != _canonical_json(media)
        or (build / "build-report.json").read_bytes() != _canonical_json(media_report)
    ):
        raise ValueError("attested transport differs from original compiler output")
    for name, digest in FILE_HASHES.items():
        if sha256(root / TEMPLATE_REL / name) != digest:
            raise ValueError("pinned graphic asset differs")
    studio = StudioGraphicPackage(root, manifest, report, template, media)
    return GraphicHandoff(root, manifest, value, studio, transport)


class InjectedGraphicAdapter(PublicStudioGraphicAdapter, WorkflowAdapter):
    """Reuse guarded #109 mutation and verify the exact two media destinations."""

    def __init__(self, resolve: Any, handoff: GraphicHandoff, guard: Any) -> None:
        super().__init__(resolve, handoff.studio)
        self.handoff_guard = guard

    def verify_package(self) -> None:
        self.handoff_guard()

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        # The runner validates exact injected edition/version/build before probe.
        return MediaAdapter.probe(self, settings)

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        super().import_media(sources)
        self.expected_paths = {source_id: path.resolve() for source_id, path in sources}

    def _verify_v1_media_inventory(
        self, manifest: Mapping[str, Any]
    ) -> tuple[str, ...]:
        timeline_media = self.timeline.GetMediaPoolItem()
        timeline_id = timeline_media.GetMediaId() if timeline_media else None
        graphic_ids = {
            source["id"]
            for source in self.graphic_package.manifest["sources"]
            if source["kind"] == "fusion_template"
        }
        expected: dict[str, dict[str, Path]] = {}
        for source in manifest["sources"]:
            folder = self.pool.GetRootFolder()
            names = (
                (self.template_bin_name,)
                if source["id"] in graphic_ids
                else tuple(self.created_bins)
            )
            for name in names:
                children = [
                    child
                    for child in folder.GetSubFolderList()
                    if child.GetName() == name
                ]
                if len(children) != 1:
                    return ("graphic/package media folder unavailable or ambiguous",)
                folder = children[0]
            expected.setdefault(folder.GetUniqueId(), {})[
                self.media_id_by_source[source["id"]]
            ] = self.expected_paths[source["id"]]
        discrepancies = []
        pending = [self.pool.GetRootFolder()]
        while pending:
            folder = pending.pop()
            clips = [
                clip
                for clip in folder.GetClipList()
                if clip.GetMediaId() != timeline_id
            ]
            wanted = expected.pop(folder.GetUniqueId(), {})
            if len(clips) != len(wanted) or {
                clip.GetMediaId() for clip in clips
            } != set(wanted):
                discrepancies.append("graphic/package media inventory differs")
            for clip in clips:
                observed = clip.GetClipProperty("File Path")
                if (
                    not isinstance(observed, str)
                    or not observed
                    or Path(observed).resolve() != wanted.get(clip.GetMediaId())
                ):
                    discrepancies.append("graphic/package media path differs")
            pending.extend(folder.GetSubFolderList())
        if expected:
            discrepancies.append("graphic/package media folder disappeared")
        return tuple(discrepancies)


def run_graphic_delivery(
    resolve: Any,
    attestation_path: Path,
    attestation_sha256: str,
    *,
    action: str = "preflight",
    authorize_new_nonproduction: bool = False,
    external_scripting: str | None = None,
) -> dict[str, Any]:
    try:
        handoff = load_graphic_handoff(attestation_path, attestation_sha256)
    except Exception as error:
        return {
            "schemaVersion": "vera-studio-graphic-result/v1",
            "sourcePins": GRAPHIC_PINS,
            "action": action,
            "discrepancies": [],
            "status": "stopped_safely",
            "verified": False,
            "partialTargetRetained": False,
            "message": str(error),
        }
    adapters: list[InjectedGraphicAdapter] = []

    def guard() -> None:
        if load_graphic_handoff(attestation_path, attestation_sha256) != handoff:
            raise ValueError("graphic handoff changed before native stage")

    def factory(injected: Any) -> InjectedGraphicAdapter:
        adapter = InjectedGraphicAdapter(injected, handoff, guard)
        adapters.append(adapter)
        return adapter

    result = run_workflow_delivery(
        resolve,
        Path(handoff.attestation["transportAttestationPath"]),
        handoff.attestation["transportAttestationSha256"],
        action=action,
        authorize_new_nonproduction=authorize_new_nonproduction,
        external_scripting=external_scripting,
        adapter_factory=factory,
        handoff_guard=guard,
    )
    result.update(
        schemaVersion="vera-studio-graphic-result/v1",
        sourcePins=GRAPHIC_PINS,
        graphicAttestationSha256=attestation_sha256,
        compilerManifestHash=_hash(_canonical_json(handoff.manifest)),
        atlasHash="sha256:" + ATLAS_SHA256,
        graphicObservations=adapters[0].graphic_observations if adapters else [],
        ev24Qualification="candidate-awaiting-native-and-producer-acceptance",
    )
    return result
