from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from issue177_package_fixture import _refresh_document_closure, make_package_case
from vera_timeline_agent import native_image_motion, v2_package, workflow_v2
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.package_cache import PackageCache
from vera_timeline_agent.v2_package import (
    BUILD_DIRECTORY,
    OTIO_FILENAME,
    VERIFICATION_FILENAME,
    V2PackageError,
    V2PackageVerification,
    _compiler_hash,
    _delivery_view,
    _InputArtifact,
    _Preparation,
    _render_slate,
    _source_audio_range,
    _validate_manifest_semantics,
    build_v2_package,
    verify_v2_package,
)
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2 import run_workflow_delivery_v2
from vera_timeline_agent.workflow_v2_cli import (
    _verify_release,
    attest_package_v2,
    build_release_v2,
)


def _issue336_case(
    case: Any, motion: dict[str, Any], *, project_default: dict[str, Any] | None = None
) -> None:
    """Write hash-closed authored input with a new frozen motion override."""
    document = json.loads(case.document_path.read_text())
    dependencies = json.loads(case.dependencies_path.read_text())
    manifest = json.loads(case.manifest_path.read_text())
    report = json.loads(case.report_path.read_text())
    document["activeDraft"]["blocks"][0]["payload"]["imageMotion"] = motion
    if motion.get("mode") == "native_dynamic_zoom":
        document["activeDraft"]["blocks"][0]["payload"]["framingPolicy"] = "cover"
        manifest["events"][0]["pictureTreatment"]["framingPolicy"] = "cover"
    if project_default is not None:
        dependencies["authoringDefaults"]["imageMotionDefault"] = project_default
        manifest["authoringDefaults"]["imageMotionDefault"] = project_default
    manifest["events"][0]["pictureTreatment"]["imageMotion"] = motion
    _refresh_document_closure(document, dependencies, manifest, report)
    for path, value in (
        (case.document_path, document),
        (case.dependencies_path, dependencies),
        (case.manifest_path, manifest),
        (case.report_path, report),
    ):
        path.write_bytes(canonical_json_bytes(value))


@pytest.mark.parametrize(
    ("key", "number", "js_number"),
    [
        ("focusX", 0.00005, "0.00005"),
        ("focusY", 1e-7, "1e-7"),
        ("scale", 1e-6, "0.000001"),
        ("scale", 1e20, "100000000000000000000"),
        ("scale", 1e21, "1e+21"),
    ],
)
def test_issue336_compiler_small_float_hash_matches_js_number_to_string(
    key: str, number: float, js_number: str
) -> None:
    canonical = f'{{\n  "{key}": {js_number}\n}}\n'
    expected = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    assert _compiler_hash({key: number}) == expected


def _issue336_synthetic_qualification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only tests inject this fake; production_qualification refuses all requests."""

    def fake(
        motion: dict[str, Any], binding: Any, framing: str, **_verified: Any
    ) -> Any:
        enabled = motion["mode"] == "native_dynamic_zoom"
        return native_image_motion.Qualification(
            edition="studio",
            version="21.1.1.10",
            route="native_otio",
            binding=binding,
            motion_hash=native_image_motion.motion_hash(motion),
            framing=framing,
            background="#000000",
            source_width=1920,
            source_height=1080,
            focus_proven=enabled,
            native_start_center=(0.0, 0.0) if enabled else None,
            native_end_center=(0.03, -0.02) if enabled else None,
            native_start_scale=0.8 if enabled else None,
            native_end_scale=(1 / 1.2) if enabled else None,
        )

    monkeypatch.setattr(native_image_motion, "production_qualification", fake)


_ISSUE336_NATIVE = {
    "mode": "native_dynamic_zoom",
    "start": {"focusX": 0.5, "focusY": 0.5, "scale": 1.25},
    "end": {"focusX": 0.53, "focusY": 0.52, "scale": 1.2},
    "easing": "linear",
}


class _Issue336NativeRouteAdapter:
    """Trace the one-use native route without claiming fake Studio pixels."""

    def __init__(
        self, *, collision: bool = False, unknown_import: bool = False
    ) -> None:
        self.calls: list[str] = []
        self.collision = collision
        self.unknown_import = unknown_import

    def connected_facts(self) -> Any:
        self.calls.append("connected")
        return SimpleNamespace(
            edition="studio",
            version="21.1.1",
            build="10",
            suffix="",
            scripting_available=True,
        )

    def probe(self, _settings: Any) -> tuple[str, ...]:
        self.calls.append("probe")
        return ()

    def check_project_name_available(self, _name: str) -> None:
        self.calls.append("collision")
        if self.collision:
            raise ValueError("named target has already been used")

    def assert_current_target(self) -> None:
        self.calls.append("target")

    def create_project(self, _name: str) -> None:
        self.calls.append("create_project")

    def configure_project(self, _settings: Any) -> None:
        self.calls.append("configure_project")

    def import_verified_otio(self, path: Path, view: Any, _name: str) -> None:
        self.calls.append("native_otio")
        assert path.is_file()
        assert len(view["events"]) > 0
        # The signed package keeps portable relative paths, but the actual
        # Studio import must receive an independently bound host-local file.
        native = json.loads(path.read_text())
        clips = [
            child
            for track in native["tracks"]["children"]
            for child in track["children"]
            if child.get("OTIO_SCHEMA") == "Clip.2"
        ]
        assert len(clips) == len(view["events"])
        for clip in clips:
            reference = clip["media_references"][clip["active_media_reference_key"]]
            resolved = Path(reference["target_url"])
            assert resolved.is_absolute() and resolved.is_file()
        if self.unknown_import:
            raise RuntimeError("uncertain Resolve timeline import")

    def add_v2_marker(self, _marker: Any) -> None:
        self.calls.append("marker")

    def save_close_reopen(self, _name: str) -> None:
        self.calls.append("save_close_reopen")

    def verify(self, _view: Any) -> tuple[str, ...]:
        self.calls.append("verify")
        return ()


@pytest.mark.parametrize("motion", [{"mode": "none"}, _ISSUE336_NATIVE])
def test_issue336_uses_one_guarded_whole_native_otio_without_append_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, motion: dict[str, Any]
) -> None:
    case = make_package_case(tmp_path, rate="25fps")
    _issue336_case(case, motion)
    _issue336_synthetic_qualification(monkeypatch)
    built = case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "delivery.json")
    view = json.loads(
        (
            case.project_root / "Builds" / built.build_id / "delivery-view.json"
        ).read_text()
    )
    bytes_before = {
        str(path): path.read_bytes()
        for path in case.project_root.rglob("*")
        if path.is_file()
    }
    adapter = _Issue336NativeRouteAdapter()
    result = run_workflow_delivery_v2(
        object(),
        attestation,
        sha256(attestation),
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
    )
    assert result["status"] == "verified", result
    assert result["nativeOtioMotionRoute"] is True
    assert adapter.calls.count("native_otio") == 1
    assert adapter.calls.count("marker") == len(view["markers"])
    assert adapter.calls[-2:] == ["save_close_reopen", "verify"]
    assert "place_event" not in adapter.calls
    assert "import_media" not in adapter.calls
    assert "create_timeline" not in adapter.calls
    assert all(Path(path).read_bytes() == value for path, value in bytes_before.items())
    assert verify_v2_package(case.project_root).build_id == built.build_id

    collision = _Issue336NativeRouteAdapter(collision=True)
    duplicate = run_workflow_delivery_v2(
        object(),
        attestation,
        sha256(attestation),
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: collision,
    )
    assert duplicate["status"] == "stopped_safely"
    assert collision.calls == ["connected", "probe", "collision"]

    unknown = _Issue336NativeRouteAdapter(unknown_import=True)
    failed = run_workflow_delivery_v2(
        object(),
        attestation,
        sha256(attestation),
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: unknown,
    )
    assert failed["status"] == "mutation_failed"
    assert failed["partialTargetRetained"] is True
    assert unknown.calls.count("native_otio") == 1
    assert "verify" not in unknown.calls
    assert all(Path(path).read_bytes() == value for path, value in bytes_before.items())


def test_issue336_older_studio_must_refuse_native_motion_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path, rate="25fps")
    _issue336_case(case, _ISSUE336_NATIVE)
    _issue336_synthetic_qualification(monkeypatch)
    case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "delivery.json")

    class PreviousStudio(_Issue336NativeRouteAdapter):
        def connected_facts(self) -> Any:
            self.calls.append("connected")
            return SimpleNamespace(
                edition="studio",
                version="21.1.0",
                build="14",
                suffix="",
                scripting_available=True,
            )

    adapter = PreviousStudio()
    result = run_workflow_delivery_v2(
        object(),
        attestation,
        sha256(attestation),
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
    )
    assert result["status"] == "stopped_safely", result
    assert result["partialTargetRetained"] is False
    assert result["verified"] is False
    assert adapter.calls == ["connected"]


def test_issue336_rechecks_otio_after_one_shot_import_before_saving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path, rate="25fps")
    _issue336_case(case, {"mode": "none"})
    _issue336_synthetic_qualification(monkeypatch)
    built = case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "delivery.json")
    path = case.project_root / BUILD_DIRECTORY / built.build_id / OTIO_FILENAME
    original = path.read_bytes()

    class SwappingAdapter(_Issue336NativeRouteAdapter):
        def import_verified_otio(self, path: Path, view: Any, name: str) -> None:
            super().import_verified_otio(path, view, name)
            path.write_bytes(path.read_bytes() + b"\n")

    adapter = SwappingAdapter()
    try:
        result = run_workflow_delivery_v2(
            object(),
            attestation,
            sha256(attestation),
            action="build",
            authorize_new_nonproduction=True,
            external_scripting="None",
            adapter_factory=lambda _: adapter,
        )
        assert result["status"] == "mutation_failed", result
        assert result["partialTargetRetained"] is True
        assert adapter.calls.count("native_otio") == 1
        assert "save_close_reopen" not in adapter.calls
    finally:
        path.write_bytes(original)
    assert verify_v2_package(case.project_root).build_id == built.build_id


def test_issue336_host_native_binding_cannot_be_modified_or_repaired_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path, rate="25fps")
    _issue336_case(case, {"mode": "none"})
    _issue336_synthetic_qualification(monkeypatch)
    built = case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "attestation.json")
    package = workflow_v2.load_verified_package_v2(attestation, sha256(attestation))
    signed = workflow_v2._verify_native_otio_plan(package)
    original = signed.read_bytes()
    bound, digest = workflow_v2._bind_native_otio_media_to_host(
        package, signed, attestation, sha256(attestation)
    )
    assert bound.is_file() and bound.parent == attestation.parent
    assert bound != signed and bound.is_relative_to(case.project_root) is False
    assert sha256(bound) == digest
    # The portable, hash-attested source never changes when deriving the
    # absolute host-local references consumed by Resolve.
    assert signed.read_bytes() == original
    bound.write_bytes(bound.read_bytes() + b"\n")
    with pytest.raises(workflow_v2.WorkflowV2Error, match="no overwrite"):
        workflow_v2._bind_native_otio_media_to_host(
            package, signed, attestation, sha256(attestation)
        )
    assert signed.read_bytes() == original
    assert verify_v2_package(case.project_root).build_id == built.build_id


@pytest.mark.parametrize(
    "mutation",
    ["effect", "source", "gap", "duplicate", "extent", "source-start", "marker"],
)
def test_issue336_injected_runtime_refuses_changed_attested_otio_before_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    case = make_package_case(
        tmp_path, rate="25fps", scenario="root-child-overlay-return"
    )
    case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "handoff.json")
    package = workflow_v2.load_verified_package_v2(attestation, sha256(attestation))
    path = workflow_v2._verify_native_otio_plan(package)
    original = path.read_bytes()
    otio = json.loads(original)
    tracks = otio["tracks"]["children"]
    clip = next(
        child
        for track in tracks
        for child in track["children"]
        if child["OTIO_SCHEMA"] == "Clip.2"
    )
    if mutation == "effect":
        clip["effects"].append(
            {"OTIO_SCHEMA": "Effect.1", "effect_name": "Resolve Effect"}
        )
    elif mutation == "source":
        clip["media_references"][clip["active_media_reference_key"]]["target_url"] = (
            "Media/other.mov"
        )
    elif mutation == "gap":
        gap = next(
            child
            for track in tracks
            for child in track["children"]
            if child["OTIO_SCHEMA"] == "Gap.1"
        )
        gap["source_range"]["duration"]["value"] += 1
    elif mutation == "duplicate":
        tracks.append(tracks[0])
    elif mutation == "source-start":
        clip["source_range"]["start_time"]["value"] += 1
    elif mutation == "marker":
        # This fixture has no timeline markers; adding one must be refused.
        otio["tracks"]["markers"].append({"OTIO_SCHEMA": "Marker.2"})
    else:
        clip["source_range"]["duration"]["value"] += 1
    path.write_text(json.dumps(otio), encoding="utf-8")
    with pytest.raises(workflow_v2.WorkflowV2Error, match="native OTIO"):
        workflow_v2._verify_native_otio_plan(package)
    # Independent attestation also refuses byte-changed inventory.
    assert (
        run_workflow_delivery_v2(
            object(),
            attestation,
            sha256(attestation),
            action="build",
            authorize_new_nonproduction=True,
            external_scripting="None",
            adapter_factory=lambda _: pytest.fail("tampering reached Resolve"),
        )["status"]
        == "stopped_safely"
    )
    path.write_bytes(original)
    assert workflow_v2._verify_native_otio_plan(package) == path


def test_issue336_release_closes_native_motion_runtime(tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    release_manifest = build_release_v2(release_dir)
    assert _verify_release(release_dir) == release_manifest
    module = (
        release_dir
        / "vera-delivery-v2/python/vera_timeline_agent/native_image_motion.py"
    )
    assert module.is_file()
    module.write_bytes(module.read_bytes() + b"# altered\n")
    with pytest.raises(ValueError, match="installed release differs"):
        _verify_release(release_dir)


@pytest.mark.parametrize("rate", ["25fps", "ntsc"])
@pytest.mark.parametrize("motion", [{"mode": "none"}, _ISSUE336_NATIVE])
def test_issue336_native_effect_roundtrip_and_exact_record_extent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rate: str, motion: dict[str, Any]
) -> None:
    case = make_package_case(tmp_path, rate=rate)
    _issue336_case(case, motion)
    _issue336_synthetic_qualification(monkeypatch)
    result = case.build()
    assert verify_v2_package(case.project_root).build_id == result.build_id
    build_root = case.project_root / BUILD_DIRECTORY / result.build_id
    view = json.loads((build_root / "delivery-view.json").read_text())
    event = view["events"][0]
    assert event["pictureTreatment"]["imageMotion"] == motion
    assert (
        event["recordRange"]["durationFrames"] == event["sourceRange"]["durationFrames"]
    )
    timeline = otio.adapters.read_from_file(str(build_root / OTIO_FILENAME))
    clip = timeline.tracks[0][0]
    assert len(clip.effects) == 2
    assert clip.metadata["vera"]["motion_qualification"].startswith("sha256:")
    assert clip.effects[0].metadata["Resolve_OTIO"]["Type"] == 59
    assert clip.effects[0].metadata["Resolve_OTIO"]["Enabled"] == (
        motion["mode"] != "none"
    )
    assert clip.effects[1].metadata["Resolve_OTIO"]["Type"] == 22
    assert case.build().reused is True


def test_issue336_unqualified_motion_refuses_before_any_package_write(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    _issue336_case(case, _ISSUE336_NATIVE)
    with pytest.raises(V2PackageError, match="no qualified output profile"):
        case.build()
    assert not case.project_root.exists()


def test_issue336_explicit_none_wins_frozen_native_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path)
    _issue336_case(case, {"mode": "none"}, project_default=_ISSUE336_NATIVE)
    _issue336_synthetic_qualification(monkeypatch)
    built = case.build()
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    clip = otio.adapters.read_from_file(str(build_root / OTIO_FILENAME)).tracks[0][0]
    assert clip.effects[0].metadata["Resolve_OTIO"]["Enabled"] is False
    assert verify_v2_package(case.project_root).build_id == built.build_id


@pytest.mark.parametrize(
    "tamper", ["drop_none", "substitute_native", "changed_override"]
)
def test_issue336_refuses_manifest_motion_divergence_from_authoring(
    tmp_path: Path, tamper: str
) -> None:
    case = make_package_case(tmp_path)
    if tamper == "changed_override":
        _issue336_case(case, {"mode": "none"}, project_default=_ISSUE336_NATIVE)
    else:
        _issue336_case(case, {"mode": "none"})
    document = json.loads(case.document_path.read_text())
    dependencies = json.loads(case.dependencies_path.read_text())
    manifest = json.loads(case.manifest_path.read_text())
    report = json.loads(case.report_path.read_text())
    if tamper == "drop_none":
        manifest["events"][0]["pictureTreatment"].pop("imageMotion")
    elif tamper == "substitute_native":
        manifest["events"][0]["pictureTreatment"]["imageMotion"] = _ISSUE336_NATIVE
    else:
        document["activeDraft"]["blocks"][0]["payload"].pop("imageMotion")
    _refresh_document_closure(document, dependencies, manifest, report)
    for path, value in (
        (case.document_path, document),
        (case.dependencies_path, dependencies),
        (case.manifest_path, manifest),
        (case.report_path, report),
    ):
        path.write_bytes(canonical_json_bytes(value))
    with pytest.raises(V2PackageError, match="motion differs from frozen authored"):
        case.build()
    assert not case.project_root.exists()


@pytest.mark.parametrize("tamper", ["type", "pointf", "double", "enabled", "extra"])
def test_issue336_native_otio_tamper_refused_even_with_rehashed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    case = make_package_case(tmp_path)
    _issue336_case(case, _ISSUE336_NATIVE)
    _issue336_synthetic_qualification(monkeypatch)
    built = case.build()
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    path = build_root / OTIO_FILENAME
    timeline = otio.adapters.read_from_file(str(path))
    clip = timeline.tracks[0][0]
    effect = clip.effects[0].metadata["Resolve_OTIO"]
    if tamper == "type":
        effect["Type"] = 58
    elif tamper == "pointf":
        effect["Parameters"][0]["Key Frames"]["-86400"]["Variant Type"] = "Double"
    elif tamper == "double":
        effect["Parameters"][1]["Key Frames"]["-85400"]["Value"] = 500.0
    elif tamper == "enabled":
        effect["Enabled"] = False
    else:
        clip.effects.append(otio.schema.Effect(effect_name="Resolve Effect"))
    otio.adapters.write_to_file(timeline, str(path), adapter_name="otio_json")
    receipt_path = build_root / VERIFICATION_FILENAME
    receipt = json.loads(receipt_path.read_text())
    rel = (Path(BUILD_DIRECTORY) / built.build_id / OTIO_FILENAME).as_posix()
    receipt["fileHashes"][rel] = (
        "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    )
    receipt_path.write_bytes(canonical_json_bytes(receipt))
    with pytest.raises(V2PackageError, match=r"OTIO event .* native effect"):
        verify_v2_package(case.project_root)


@dataclass(frozen=True)
class _ConnectedFacts:
    edition: str = "studio"
    scripting_available: bool = True
    suffix: str = ""
    version: str = "21.1.1"
    build: str = "10"


class _ReadOnlyPreflightAdapter:
    def connected_facts(self) -> _ConnectedFacts:
        return _ConnectedFacts()

    def probe(self, _settings: Any) -> tuple[str, ...]:
        return ()

    def check_project_name_available(self, _name: str) -> None:
        return None


def test_build_verify_and_exact_retry(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)

    created = case.build()

    assert created.project_root == case.project_root
    assert created.reused is False
    verification = verify_v2_package(case.project_root)
    assert verification == V2PackageVerification(
        build_id="00000000-0000-4000-8000-000000000003",
        event_count=1,
        marker_count=0,
        media_count=1,
    )
    package_root = case.project_root / "Builds" / verification.build_id
    package_dir = f"Builds/{verification.build_id}"
    expected_files = {
        f"{package_dir}/{name}"
        for name in (
            "timeline-manifest.json",
            "build-report.json",
            "script-document.json",
            "compiler-dependencies.json",
            "delivery-view.json",
            "timeline.otio",
            "package-verification.json",
        )
    }
    source_id = json.loads(case.manifest_path.read_text())["sources"][0]["id"]
    expected_files.update(
        {
            f"{package_dir}/Preparation/receipts/"
            "a8ba8b26cd56f0f2cbb282a939a4326d1434e4ef74ab84df83599a6ec174cc47/receipt.json",
            f"{package_dir}/Preparation/original/{source_id}.mov",
            f"Media/Resolved/{source_id}.mov",
        }
    )
    receipt = json.loads((package_root / "package-verification.json").read_text())
    assert receipt["schemaVersion"] == "v2-package-verification/v1"
    assert receipt["status"] == "ready_to_import"
    assert set(receipt["fileHashes"]) == expected_files - {
        f"{package_dir}/package-verification.json"
    }
    assert len(receipt["sourceHashes"]) == 1
    assert set(receipt["preparations"]) == {"prep:occurrence-1"}

    retried = case.build()

    assert retried.reused is True
    assert verify_v2_package(case.project_root) == verification


def _cached_build(
    case: Any,
    root: Path,
    cache_root: Path | None,
) -> tuple[dict[str, bytes], tuple[int, int]]:
    counts: list[tuple[int, int]] = []
    built = build_v2_package(
        case.manifest_path,
        case.report_path,
        case.document_path,
        case.dependencies_path,
        root,
        media_paths=case.media_paths,
        preparation_paths=case.preparation_paths,
        package_cache=cache_root,
        cache_observer=lambda reused, processed: counts.append((reused, processed)),
    )
    assert built.project_root == root
    assert verify_v2_package(root).build_id == built.build_id
    bytes_by_path = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    return bytes_by_path, counts[-1] if counts else (0, 0)


def test_package_cache_is_byte_identical_and_skips_all_warm_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path / "fixture")
    cache_root = tmp_path / "cache"
    originals = set(case.media_paths.values())
    unique_count = len(originals)
    read_counts = {"hash": 0, "copy": 0}
    real_hash = v2_package._file_hash
    real_copy = v2_package._copy_input_file

    def tracked_hash(path: Path) -> str:
        if path in originals:
            read_counts["hash"] += 1
        return real_hash(path)

    def tracked_copy(
        source: Path, destination: Path, expected: str | None = None
    ) -> str:
        if source in originals:
            read_counts["copy"] += 1
        return real_copy(source, destination, expected)

    monkeypatch.setattr(v2_package, "_file_hash", tracked_hash)
    monkeypatch.setattr(v2_package, "_copy_input_file", tracked_copy)
    no_cache, _ = _cached_build(case, tmp_path / "no-cache", None)
    assert read_counts["hash"] >= unique_count
    read_counts.update(hash=0, copy=0)

    cold, cold_counts = _cached_build(case, tmp_path / "cold", cache_root)
    assert cold == no_cache
    assert cold_counts == (0, unique_count)
    read_counts.update(hash=0, copy=0)

    warm, warm_counts = _cached_build(case, tmp_path / "warm", cache_root)
    assert warm == no_cache
    assert warm_counts == (unique_count, 0)
    assert read_counts == {"hash": 0, "copy": 0}

    # Even an edit that preserves all bytes, length and path invalidates its
    # input's mtime identity and reprocesses only that physical input.
    edited = next(iter(originals))
    info = edited.stat()
    os.utime(edited, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000))
    read_counts.update(hash=0, copy=0)
    changed, changed_counts = _cached_build(case, tmp_path / "one-edited", cache_root)
    assert changed == no_cache
    assert changed_counts == (unique_count - 1, 1)
    assert read_counts == {"hash": 0, "copy": 1}


def test_cache_corruption_retries_once_from_source_and_refuses_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path / "fixture")
    cache_root = tmp_path / "cache"
    expected, _ = _cached_build(case, tmp_path / "cold", cache_root)
    original = next(iter(case.media_paths.values()))
    digest = "sha256:" + hashlib.sha256(original.read_bytes()).hexdigest()
    store = PackageCache(cache_root)
    entry = store.lookup(original, digest)
    assert entry is not None
    entry.blob.write_bytes(b"\xff" * entry.blob.stat().st_size)

    actual_build = v2_package._build_v2_package
    attempts: list[int] = []

    def counted_build(*args: Any, **kwargs: Any) -> Any:
        attempts.append(1)
        return actual_build(*args, **kwargs)

    monkeypatch.setattr(v2_package, "_build_v2_package", counted_build)

    recovered, counts = _cached_build(case, tmp_path / "recovered", cache_root)
    assert len(attempts) == 2  # bad cache plus exactly one source-only retry
    assert recovered == expected
    assert counts == (0, len(set(case.media_paths.values())))
    assert store.lookup(original, digest) is not None

    # A missing/unwritable or symlinked cache root is merely a miss.
    missing, counts = _cached_build(
        case, tmp_path / "missing-output", tmp_path / "missing-cache"
    )
    assert missing == expected
    assert counts[0] == 0
    target = tmp_path / "redirected-cache"
    target.mkdir()
    (tmp_path / "linked-cache").symlink_to(target, target_is_directory=True)
    linked, counts = _cached_build(
        case, tmp_path / "linked-output", tmp_path / "linked-cache"
    )
    assert linked == expected
    assert counts[0] == 0
    assert not list(target.iterdir())

    cached_media = next((tmp_path / "recovered" / "Media").rglob("*.mov"))
    cached_media.write_bytes(b"tampered published package")
    with pytest.raises(V2PackageError, match="file hash mismatch"):
        verify_v2_package(tmp_path / "recovered")

    # A same-length source edit with an unchanged manifest hash remains fatal.
    original.write_bytes(b"\x00" * original.stat().st_size)
    with pytest.raises(V2PackageError, match="media hash mismatch"):
        _cached_build(case, tmp_path / "stale-source", cache_root)

    # Source symlinks must refuse even if the cache has a previously valid hit.
    symlink_case = replace(case, media_paths=dict(case.media_paths))
    key = next(iter(symlink_case.media_paths))
    source = symlink_case.media_paths[key]
    link = source.with_name("linked-asset" + source.suffix)
    link.symlink_to(source)
    symlink_case.media_paths[key] = link
    with pytest.raises(V2PackageError, match="symbolic link"):
        _cached_build(symlink_case, tmp_path / "linked-source", cache_root)


def test_cached_source_drift_during_clone_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_package_case(tmp_path / "fixture")
    cache_root = tmp_path / "cache"
    _cached_build(case, tmp_path / "cold", cache_root)
    real_materialize = PackageCache.materialize

    def change_source(
        self: PackageCache, entry: Any, destination: Path, **kwargs: Any
    ) -> bool:
        copied = real_materialize(self, entry, destination, **kwargs)
        info = entry.source.stat()
        os.utime(
            entry.source,
            ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000),
        )
        return copied

    monkeypatch.setattr(PackageCache, "materialize", change_source)
    with pytest.raises(V2PackageError, match="changed while staging"):
        _cached_build(case, tmp_path / "racing-source", cache_root)


def test_cache_cannot_be_inside_immutable_package_root(tmp_path: Path) -> None:
    case = make_package_case(tmp_path / "fixture")
    destination = tmp_path / "output"
    with pytest.raises(V2PackageError, match="outside the package directory"):
        _cached_build(case, destination, destination / "media-cache")
    assert not destination.exists()


@pytest.mark.parametrize("scenario", ["source-audio-quiet", "source-audio-full"])
def test_cached_source_audio_reuses_input_without_bypassing_endpoint_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    case = make_package_case(tmp_path / "fixture", scenario=scenario)
    cache_root = tmp_path / "cache"
    originals = set(case.media_paths.values())
    original_read = Path.read_bytes
    original_hash = v2_package._file_hash
    original_copy = v2_package._copy_input_file
    source_reads: list[Path] = []

    def read_bytes(path: Path) -> bytes:
        if path in originals:
            source_reads.append(path)
        return original_read(path)

    def hash_file(path: Path) -> str:
        if path in originals:
            source_reads.append(path)
        return original_hash(path)

    def copy_source(path: Path, destination: Path, expected: str | None = None) -> str:
        if path in originals:
            source_reads.append(path)
        return original_copy(path, destination, expected)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(v2_package, "_file_hash", hash_file)
    monkeypatch.setattr(v2_package, "_copy_input_file", copy_source)
    cold, counts = _cached_build(case, tmp_path / "cold", cache_root)
    assert counts[1] >= 1
    source_reads.clear()
    warm, counts = _cached_build(case, tmp_path / "warm", cache_root)
    assert warm == cold
    assert counts == (len(originals), 0)
    assert not source_reads


def test_corrupted_cached_wav_is_rebuilt_before_audio_projection(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path / "fixture", scenario="source-audio-quiet")
    cache_root = tmp_path / "cache"
    cold, _ = _cached_build(case, tmp_path / "cold", cache_root)
    wav = next(path for path in case.media_paths.values() if path.suffix == ".wav")
    digest = "sha256:" + hashlib.sha256(wav.read_bytes()).hexdigest()
    entry = PackageCache(cache_root).lookup(wav, digest)
    assert entry is not None
    entry.blob.write_bytes(b"\x00" * entry.blob.stat().st_size)
    recovered, counts = _cached_build(case, tmp_path / "recovered", cache_root)
    assert recovered == cold
    assert counts == (0, len(set(case.media_paths.values())))


@pytest.mark.parametrize(
    "scenario",
    [
        "verified-reuse",
        "root-child-overlay-return",
        "source-audio-quiet",
        "source-audio-full",
    ],
)
def test_public_packages_attest_and_pass_read_only_preflight(
    tmp_path: Path, scenario: str
) -> None:
    case = make_package_case(tmp_path, scenario=scenario)
    built = case.build()
    verified = verify_v2_package(case.project_root)
    attestation = attest_package_v2(
        case.project_root, tmp_path / "package-attestation.json"
    )

    result = run_workflow_delivery_v2(
        object(),
        attestation,
        sha256(attestation),
        adapter_factory=lambda _resolve: _ReadOnlyPreflightAdapter(),
    )

    assert verified.build_id == built.build_id
    assert result["status"] == "preflight_passed"
    if scenario == "verified-reuse":
        package = case.project_root / "Builds" / built.build_id
        manifest = json.loads((package / "timeline-manifest.json").read_text())
        report = json.loads((package / "build-report.json").read_text())
        assert manifest["preparationBindings"][0]["mode"] == "verified_reuse"
        assert report["mediaPreparation"]["requirements"][0]["status"] == "reused"
    if scenario == "root-child-overlay-return":
        package = case.project_root / "Builds" / built.build_id
        manifest = json.loads((package / "timeline-manifest.json").read_text())
        view = json.loads((package / "delivery-view.json").read_text())
        child = next(
            event
            for event in view["events"]
            if event["v2Event"]["provenance"]["payloadId"]
            == "00000000-0000-4000-8000-000000000020"
        )
        assert manifest["composition"]["returns"]
        assert child["trackKind"] == "video"
    if scenario.startswith("source-audio-"):
        package = case.project_root / "Builds" / built.build_id
        view = json.loads((package / "delivery-view.json").read_text())
        assert any(event["kind"] == "source_audio" for event in view["events"])


def test_derived_preparation_cannot_claim_reuse_status(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    report = json.loads(case.report_path.read_text())
    report["mediaPreparation"]["requirements"][0]["status"] = "reused"
    case.report_path.write_bytes(canonical_json_bytes(report))

    with pytest.raises(V2PackageError, match="build report preparation result differs"):
        case.build()


def test_child_role_lists_may_be_unsorted_when_track_layers_are_valid(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="root-child-overlay-return")
    document = json.loads(case.document_path.read_text())
    dependencies = json.loads(case.dependencies_path.read_text())
    manifest = json.loads(case.manifest_path.read_text())
    child_ids = dependencies["roles"]["childTrackIds"]
    existing = next(
        track for track in dependencies["tracks"] if track["id"] == child_ids[0]
    )
    second_id = "video-child-second"
    second_index = existing["index"] + 1
    for track in dependencies["tracks"]:
        if track["kind"] == "video" and track["index"] >= second_index:
            track["index"] += 1
    dependencies["tracks"].append(
        {"id": second_id, "kind": "video", "index": second_index, "name": "Child 2"}
    )
    dependencies["roles"]["childTrackIds"] = [second_id, child_ids[0]]
    manifest["tracks"] = copy.deepcopy(dependencies["tracks"])
    manifest["roles"] = copy.deepcopy(dependencies["roles"])
    manifest["composition"]["childTrackIds"] = list(
        dependencies["roles"]["childTrackIds"]
    )

    _validate_manifest_semantics(document, dependencies, manifest)


def test_unsupported_slate_dimensions_use_package_error() -> None:
    with pytest.raises(V2PackageError, match="placeholder slate cannot be rendered"):
        _render_slate("oversized", 16_385, 1_080)


def test_build_requires_explicit_media_bytes_to_match_the_manifest(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    delivered = case.media_paths[
        next(key for key in case.media_paths if key.startswith("source:"))
    ]
    delivered.write_bytes(b"different delivered bytes")

    with pytest.raises(V2PackageError, match="media hash mismatch"):
        case.build()

    assert not case.project_root.exists()


def test_verify_refuses_tampered_package_media(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    case.build()
    media = next((case.project_root / "Media" / "Resolved").iterdir())
    media.write_bytes(b"tampered after publication")

    with pytest.raises(V2PackageError, match="file hash mismatch"):
        verify_v2_package(case.project_root)


def test_build_refuses_different_inputs_at_an_existing_build_root(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    case.build()
    case.document_path.write_bytes(case.document_path.read_bytes() + b"\n")

    with pytest.raises(V2PackageError, match="not the same verified package"):
        case.build()


def test_build_rejects_symlinked_supplied_media(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    key = next(key for key in case.media_paths if key.startswith("source:"))
    source = case.media_paths[key]
    link = source.with_name("media-link.mov")
    link.symlink_to(source)
    case.media_paths[key] = link

    with pytest.raises(V2PackageError, match="symbolic link"):
        case.build()


def test_build_round_trips_accepted_24000_over_1001_timeline(tmp_path: Path) -> None:
    case = make_package_case(tmp_path, rate="ntsc")

    created = case.build()
    verified = verify_v2_package(case.project_root)
    package_root = case.project_root / BUILD_DIRECTORY / created.build_id
    view = json.loads((package_root / "delivery-view.json").read_text())

    assert verified.build_id == created.build_id
    assert view["timeline"]["frameRate"] == {"numerator": 24000, "denominator": 1001}


def test_public_root_child_overlay_return_package_round_trip_without_source_audio(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="root-child-overlay-return")

    built = case.build()
    verified = verify_v2_package(case.project_root)
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / "delivery-view.json").read_text())
    timeline = otio.adapters.read_from_file(str(build_root / OTIO_FILENAME))
    topology_events = {(event["kind"], event["trackId"]) for event in view["events"]}

    assert verified.event_count == 4
    assert {
        ("primary_visual", "video-root"),
        ("primary_visual", "video-child"),
        ("overlay_visual", "video-overlay"),
    } <= topology_events
    assert view["composition"]["returns"][0]["recordFrame"] == 48
    assert view["composition"]["returns"][0]["emitsNewSourceEvent"] is False
    track_ids = [track.metadata["vera"]["track_id"] for track in timeline.tracks]
    assert track_ids == [
        "video-root",
        "video-child",
        "video-overlay",
        "placeholder",
        "presenter",
        "markers",
        "narration",
    ]
    clips = [
        child
        for track in timeline.tracks
        for child in track
        if isinstance(child, otio.schema.Clip)
    ]
    assert any(
        clip.metadata["vera"]["v2_event"]["trackRole"] == "child" for clip in clips
    )


@pytest.mark.parametrize(
    ("scenario", "policy", "gain_db"),
    [
        ("source-audio-quiet", "quiet", -18),
        ("source-audio-full", "full", 0),
    ],
)
def test_public_package_build_verifies_aligned_source_audio(
    tmp_path: Path, scenario: str, policy: str, gain_db: int
) -> None:
    case = make_package_case(tmp_path, scenario=scenario)

    built = case.build()
    verified = verify_v2_package(case.project_root)
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / "delivery-view.json").read_text())
    audio_event = next(
        event for event in view["events"] if event["kind"] == "source_audio"
    )

    assert verified.event_count == 2
    assert verified.media_count == 2
    assert audio_event["gainDb"] == gain_db
    assert audio_event["v2Event"]["audio"]["audioPolicy"] == policy
    assert audio_event["sourceRange"] == {"startFrame": 0, "durationFrames": 240}


def test_public_package_build_preserves_no_source_audio_case(tmp_path: Path) -> None:
    case = make_package_case(tmp_path, scenario="source-audio-no")

    built = case.build()
    verified = verify_v2_package(case.project_root)
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / "delivery-view.json").read_text())

    assert verified.event_count == 1
    assert all(event["kind"] != "source_audio" for event in view["events"])


def test_package_build_and_verification_accept_occurrences_sharing_a_preparation(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="shared-preparation")

    case.build()
    verified = verify_v2_package(case.project_root)
    manifest = json.loads(case.manifest_path.read_text())
    report = json.loads(case.report_path.read_text())
    media_sources = [
        source for source in manifest["sources"] if "mediaReferenceId" in source
    ]

    assert verified.event_count == 3
    assert len(media_sources) == 1
    assert len(manifest["preparationBindings"]) == 1
    assert len(report["mediaPreparation"]["requirements"]) == 1
    assert len(report["sourceSufficiency"]) == 2
    assert len(report["eventResults"]) == 3


def test_package_refuses_shared_preparation_with_conflicting_occurrence_identity(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="shared-preparation")
    dependencies = json.loads(case.dependencies_path.read_text())
    first_occurrence = dependencies["occurrenceResolutions"][0]
    first_occurrence["sourceSnapshot"]["snapshotId"] = (
        "00000000-0000-4000-8000-000000000200"
    )
    case.dependencies_path.write_bytes(canonical_json_bytes(dependencies))
    report = json.loads(case.report_path.read_text())
    report["dependenciesHash"] = _compiler_hash(dependencies)
    case.report_path.write_bytes(canonical_json_bytes(report))

    with pytest.raises(V2PackageError, match="input mapping is stale"):
        case.build()

    assert not case.project_root.exists()


def test_public_package_build_refuses_cross_track_source_audio_overlap(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="source-audio-overlap")

    with pytest.raises(V2PackageError, match="enabled source-audio events overlap"):
        case.build()

    assert not case.project_root.exists()


def test_package_renders_and_binds_authored_intentional_slate(tmp_path: Path) -> None:
    case = make_package_case(tmp_path, scenario="intentional-slate")

    built = case.build()
    verified = verify_v2_package(case.project_root)
    build_root = case.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / "delivery-view.json").read_text())
    slate_event = next(
        event for event in view["events"] if event["kind"] == "placeholder"
    )

    assert verified.event_count == 1
    assert slate_event["pictureTreatment"] == {
        "kind": "slate",
        "purpose": "intentional",
        "text": "Intentional slate",
    }
    slate_source = next(
        source for source in view["sources"] if source["id"] == slate_event["sourceId"]
    )
    slate_path = case.project_root / slate_source["path"]
    assert hashlib.sha256(slate_path.read_bytes()).hexdigest() == slate_source[
        "contentHash"
    ].removeprefix("sha256:")


def test_build_rejects_preparation_status_mismatch_for_empty_binding_set(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path, scenario="intentional-slate")
    report = json.loads(case.report_path.read_text())
    report["mediaPreparation"]["status"] = "complete"
    case.report_path.write_bytes(canonical_json_bytes(report))

    with pytest.raises(
        V2PackageError,
        match="build report media preparation does not cover the exact binding set",
    ):
        case.build()

    assert not case.project_root.exists()


def test_root_child_overlay_same_track_overlap_is_refused() -> None:
    fixture = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
    stem = fixture / "root-child-overlay-return"
    inputs = json.loads(Path(f"{stem}.input.golden.json").read_text())
    manifest = json.loads(Path(f"{stem}.manifest.golden.json").read_text())
    _close_test_mapping_hashes(inputs["dependencies"], manifest)
    overlay = copy.deepcopy(
        next(event for event in manifest["events"] if event["kind"] == "overlay_visual")
    )
    overlay["eventId"] = "00000000-0000-4000-8000-000000000099"
    manifest["events"].append(overlay)

    with pytest.raises(V2PackageError, match="overlap on video-overlay"):
        _validate_manifest_semantics(
            inputs["document"], inputs["dependencies"], manifest
        )


def test_build_rejects_stale_preparation_inputs(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    receipt_path = next(iter(case.preparation_paths.values()))
    receipt = json.loads(receipt_path.read_text())
    receipt["inputs"]["profile"]["profileVersion"] = "stale synthetic profile"
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(V2PackageError, match="input mapping is stale"):
        case.build()

    assert not case.project_root.exists()


@pytest.mark.parametrize(("policy", "gain_db"), [("quiet", -18), ("full", 0)])
def test_delivery_view_maps_44100_source_samples_to_verified_wav(
    policy: str, gain_db: int
) -> None:
    fixture = (
        Path(__file__).parent
        / "data/authoring_v2/issue_173/compiler/selected-clip-ntsc.manifest.golden.json"
    )
    manifest_data = json.loads(fixture.read_text())
    event = copy.deepcopy(
        next(
            event
            for event in manifest_data["events"]
            if event["kind"] == "source_audio"
        )
    )
    event["recordRange"] = {"startFrame": 0, "endFrame": 25}
    event["audio"].update(
        {
            "audioPolicy": policy,
            "gainDb": gain_db,
            "sampleRange": {"startFrame": 44100, "endFrame": 88200},
        }
    )
    event["sourceTimeMapping"]["sourceFrameMap"]["sourceAudioStreamMappings"][0][
        "sampleRate"
    ] = 44100
    binding = {"syntheticBinding": True}
    event["preparationBindingHash"] = _compiler_hash(binding)
    wav_probe = {
        "streams": [{"codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 1}]
    }
    audio_record = {
        "probe": wav_probe,
        "resampledFirstSample": 48000,
        "decodedSamples": 48000,
    }
    preparation = _Preparation(
        "prep:source-audio", {"binding": binding, "audio": audio_record}, b"", "", ""
    )
    event_id = event["eventId"]
    artifact = _InputArtifact(
        f"event:{event_id}",
        Path("."),
        f"Media/Resolved/{event_id}.wav",
        "sha256:" + "1" * 64,
        "audio",
    )
    manifest = {
        "timeline": {
            "frameRate": {"numerator": 25, "denominator": 1},
            "startFrame": 0,
            "durationFrames": 25,
        },
        "tracks": [
            {
                "id": event["trackId"],
                "index": 1,
                "kind": "audio",
                "name": "Source audio",
            }
        ],
        "sources": [],
        "events": [event],
        "composition": {},
    }

    view = _delivery_view(
        manifest,
        {},
        {preparation.requirement_key: preparation},
        {artifact.key: artifact},
        validate=False,
    )

    assert view["events"][0]["sourceRange"] == {
        "startFrame": 0,
        "durationFrames": 25,
    }
    assert view["events"][0]["gainDb"] == gain_db
    assert view["events"][0]["v2Event"]["audio"]["audioPolicy"] == policy


def test_source_audio_refuses_fractional_timeline_frame_mapping() -> None:
    fixture = (
        Path(__file__).parent
        / "data/authoring_v2/issue_173/compiler/selected-clip-ntsc.manifest.golden.json"
    )
    manifest_data = json.loads(fixture.read_text())
    event = copy.deepcopy(
        next(
            event
            for event in manifest_data["events"]
            if event["kind"] == "source_audio"
        )
    )
    event["recordRange"] = {"startFrame": 0, "endFrame": 24}
    event["audio"]["sampleRange"] = {"startFrame": 44100, "endFrame": 88200}
    event["sourceTimeMapping"]["sourceFrameMap"]["sourceAudioStreamMappings"][0][
        "sampleRate"
    ] = 44100
    preparation = _Preparation(
        "prep:source-audio",
        {
            "audio": {
                "probe": {
                    "streams": [
                        {
                            "codec_name": "pcm_s24le",
                            "sample_rate": "48000",
                            "channels": 1,
                        }
                    ]
                },
                "resampledFirstSample": 48000,
                "decodedSamples": 48000,
            }
        },
        b"",
        "",
        "",
    )

    with pytest.raises(V2PackageError, match="does not map to exact timeline frames"):
        _source_audio_range(event, preparation, Fraction(24000, 1001))


def test_verify_checks_otio_metadata_after_receipt_hash_rebinding(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    created = case.build()
    package_root = case.project_root / BUILD_DIRECTORY / created.build_id
    otio_path = package_root / OTIO_FILENAME
    timeline = otio.adapters.read_from_file(str(otio_path))
    clip = timeline.tracks[0][0]
    clip.metadata["vera"]["v2_event"] = {"tampered": True}
    otio.adapters.write_to_file(timeline, str(otio_path))

    receipt_path = package_root / VERIFICATION_FILENAME
    receipt = json.loads(receipt_path.read_text())
    package_relative_path = (
        Path(BUILD_DIRECTORY) / created.build_id / OTIO_FILENAME
    ).as_posix()
    receipt["fileHashes"][package_relative_path] = (
        "sha256:" + hashlib.sha256(otio_path.read_bytes()).hexdigest()
    )
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(
        V2PackageError, match=r"OTIO event .* differs from delivery view"
    ):
        verify_v2_package(case.project_root)


def test_build_rejects_symlinked_output_ancestor_before_creating_files(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    case.project_root = linked_parent / "v2-project"

    with pytest.raises(V2PackageError, match="symbolic link"):
        case.build()

    assert list(real_parent.iterdir()) == []


def test_build_preserves_failed_staging_for_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vera_timeline_agent.v2_package as package_module

    case = make_package_case(tmp_path)

    def fail_after_staging(staging: Path, **kwargs: object) -> None:
        marker = staging / "partial-evidence.txt"
        marker.write_text("synthetic interrupted package build")
        raise V2PackageError("synthetic staging failure")

    monkeypatch.setattr(package_module, "_build_staging", fail_after_staging)

    with pytest.raises(V2PackageError, match="partial package retained at") as error:
        case.build()

    retained = Path(str(error.value).rsplit(" at ", maxsplit=1)[-1])
    assert (retained / "partial-evidence.txt").read_text() == (
        "synthetic interrupted package build"
    )


def _close_test_mapping_hashes(
    dependencies: dict[str, Any], manifest: dict[str, Any]
) -> None:
    """Rebind the accepted topology fixture's historical placeholder hashes."""
    bindings_by_requirement = {}
    for binding in manifest["preparationBindings"]:
        mapping = binding["timeMapping"]
        mapping["mappingHash"] = identity_hash(
            {key: value for key, value in mapping.items() if key != "mappingHash"}
        )
        bindings_by_requirement[binding["requirementKey"]] = binding
    dependencies["preparedMedia"] = copy.deepcopy(manifest["preparationBindings"])

    sources = {source["id"]: source for source in manifest["sources"]}
    for source in sources.values():
        if "narrationAudio" in source:
            continue
        binding = bindings_by_requirement[source["preparationRequirementKey"]]
        source["sourceTimeMapping"] = copy.deepcopy(binding["timeMapping"])
        source["sourceFrameMap"] = copy.deepcopy(
            binding["timeMapping"]["sourceFrameMap"]
        )
    for event in manifest["events"]:
        if event["kind"] not in {"primary_visual", "overlay_visual"}:
            continue
        source = sources[event["provenance"]["sourceId"]]
        binding = bindings_by_requirement[source["preparationRequirementKey"]]
        event["preparationBindingHash"] = _compiler_hash(binding)
        event["sourceTimeMapping"] = copy.deepcopy(binding["timeMapping"])
