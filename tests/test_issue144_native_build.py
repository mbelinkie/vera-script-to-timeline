from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from test_issue144_prepared_build import _inputs
from vera_timeline_agent.build_jobs import StageContext, UncertainResult
from vera_timeline_agent.roundtrip_build import PreparedBuild, load_operator_json
from vera_timeline_agent.roundtrip_native import NativeStages
from vera_timeline_agent.studio_spike import (
    BLACKMAGIC_BUNDLE_ID,
    ConnectedFacts,
    LocalFacts,
)


def _local() -> LocalFacts:
    return LocalFacts(
        os_name="macOS",
        os_version="15.1",
        architecture="arm64",
        app_path="/Applications/DaVinci Resolve/DaVinci Resolve.app",
        app_installed=True,
        install_source="blackmagic_package_receipt",
        bundle_name="DaVinci Resolve",
        bundle_identifier=BLACKMAGIC_BUNDLE_ID,
        bundle_version="21.0.4",
        bundle_build="21.0.40005",
        mas_receipt=False,
        package_receipt_id="com.blackmagic-design.ManifestLite",
        package_receipt_version="21.0.4",
        scripting_module_path="/sdk/script.py",
        scripting_module_installed=True,
        scripting_docs_path="/sdk/README.txt",
        scripting_docs_installed=True,
    )


class InjectedStudio:
    """Explicit fake native boundary; compiler/package/job code remains real."""

    def __init__(self, build: PreparedBuild, *, lost_response: bool = False) -> None:
        self.build = build
        self.lost_response = lost_response
        self.create_count = 0
        self.inspect_count = 0
        self.created = False
        self.bad_readback = False
        self.manifest: dict[str, Any] = {}
        self.sources: dict[str, Path] = {}

    def connected_facts(self) -> ConnectedFacts:
        return ConnectedFacts("DaVinci Resolve Studio", "studio", "21.0.4", "5", True)

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        return ()

    def check_project_name_available(self, name: str) -> None:
        if self.created:
            raise RuntimeError("target already exists")

    def create_project(self, name: str) -> None:
        assert self.build.intent_path.exists(), "effect preceded durable intent"
        intent = load_operator_json(self.build.intent_path)
        assert intent["projectName"] == name
        assert intent["snapshotId"] == self.build.snapshot_id
        self.create_count += 1
        self.created = True
        if self.lost_response:
            raise RuntimeError("creation response lost; target remains")

    def configure_project(self, settings: Mapping[str, str]) -> None:
        pass

    def create_bin(self, name: str) -> None:
        pass

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        self.sources = dict(sources)

    def create_timeline(self, name: str) -> None:
        pass

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        pass

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        pass

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        pass

    def save_close_reopen(self, project_name: str) -> None:
        pass

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        self.manifest = dict(manifest)
        return ()

    def inspect(self, package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        self.inspect_count += 1
        assert self.created
        sources = {row["id"]: row for row in manifest["sources"]}
        items = []
        for index, event in enumerate(manifest["events"]):
            source = sources[event["sourceId"]]
            source_path = package / (
                source["path"]
                if source["kind"] != "placeholder"
                else f"Media/Placeholders/{source['id']}.png"
            )
            items.append(
                {
                    "itemUid": f"item-{index}",
                    "mediaUid": f"media-{source['id']}",
                    "event": copy.deepcopy(event),
                    "sourcePath": str(source_path),
                    "sourceHash": "sha256:"
                    + hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "enabled": True,
                    "speed": 100,
                }
            )
        if self.bad_readback:
            items[0]["event"]["recordRange"]["startFrame"] += 1
        return {
            "schemaVersion": "issue-144-native-readback/v1",
            "projectUid": "fake-project",
            "timelineUid": "fake-timeline",
            "projectName": f"VERA Studio build {manifest['buildId']}",
            "timelineName": f"VERA build {manifest['buildId']}",
            "timeline": manifest["timeline"],
            "tracks": manifest["tracks"],
            "items": items,
            "markers": manifest["markers"],
        }


def _setup(tmp_path: Path) -> tuple[PreparedBuild, InjectedStudio, NativeStages]:
    root = tmp_path / "proof"
    _inputs(root)
    build = PreparedBuild(root)
    studio = InjectedStudio(build)
    stages = NativeStages(
        build,
        adapter_factory=lambda _: studio,
        local_facts=_local(),
        inspector=studio.inspect,
    )
    return build, studio, stages


def test_actual_pipeline_completes_with_injected_native_boundary_and_replays(
    tmp_path: Path,
) -> None:
    build, studio, stages = _setup(tmp_path)
    result = build.run(adapter=stages)
    assert result["status"] == "complete", result["lastError"]
    assert studio.create_count == 1
    assert studio.inspect_count >= 2
    receipts = [
        load_operator_json(Path(row["path"]))
        for row in result["stages"]
        if row["name"] in {"building_resolve_timeline", "verifying_timeline"}
    ]
    assert all(row["evidenceLevel"] == "synthetic_injected" for row in receipts)
    assert not (build.root / "baseline.json").exists()
    assert build.run(adapter=stages)["status"] == "complete"
    assert studio.create_count == 1


def test_exclusive_intent_reservation_has_exactly_one_owner(tmp_path: Path) -> None:
    build, _, stages = _setup(tmp_path)
    build.run()
    context = StageContext(
        project_id=build.document["projectId"],
        job_id=build.job_id,
        snapshot_id=build.snapshot_id,
        stage="building_resolve_timeline",
        stage_key="not-used-for-intent",
        output_path=build.run_root / "unused",
        attempt_id=1,
        lease_epoch=1,
        report_progress=lambda _: None,
        renew_lease=lambda: None,
    )
    manifest = load_operator_json(build.manifest_path)

    def reserve(_: int) -> bool:
        try:
            stages._reserve_intent(context, manifest)
            return True
        except UncertainResult:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, (1, 2)))
    assert sorted(results) == [False, True]
    assert load_operator_json(build.intent_path)["snapshotId"] == build.snapshot_id
    assert not stages.result_path.exists()


def test_lost_creation_response_never_retries_or_publishes_baseline(
    tmp_path: Path,
) -> None:
    build, studio, stages = _setup(tmp_path)
    studio.lost_response = True
    result = build.run(adapter=stages)
    assert result["status"] == "waiting"
    assert studio.create_count == 1
    assert build.intent_path.exists()
    assert not (build.root / "baseline.json").exists()
    assert build.store is not None
    build.store.resume(build.document["projectId"], build.job_id)
    assert build.run(adapter=stages)["status"] == "waiting"
    assert studio.create_count == 1


@pytest.mark.parametrize("case", ["lost_result", "changed_target", "wrong_uid"])
def test_interrupted_or_changed_result_cannot_retry_effect(
    tmp_path: Path,
    case: str,
) -> None:
    build, studio, stages = _setup(tmp_path)
    build.run(adapter=stages)
    if case == "lost_result":
        stages.result_path.unlink()
    elif case == "changed_target":
        studio.bad_readback = True
    else:
        original = studio.inspect

        def wrong(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
            result = original(package, manifest)
            result["timelineUid"] = "another-timeline"
            return result

        stages.inspector = wrong
    with pytest.raises(
        (RuntimeError, OSError), match=r"uncertain|changed|missing|identity"
    ):
        build.run(adapter=stages)
    assert studio.create_count == 1
    assert not (build.root / "baseline.json").exists()
