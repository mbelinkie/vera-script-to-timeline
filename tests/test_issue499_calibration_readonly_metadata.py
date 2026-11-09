"""Phase14: no-native / no-replay negative SDK mocks for the spent v2 Roll case."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/issue-499-calibration-readonly-metadata.py"
)
spec = importlib.util.spec_from_file_location("issue499_metadata", SCRIPT)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class FakeMedia:
    def __init__(self, uid: str, path: str) -> None:
        self.uid, self.path = uid, path

    def GetUniqueId(self) -> str:
        return self.uid

    def GetClipProperty(self) -> dict[str, str]:
        return {
            "File Path": self.path,
            "Frames": "720",
            "FPS": "23.976",
            "Online Status": "Online",
            "Type": "Video",
        }


class FakeClip:
    def __init__(self, row: dict[str, Any], path: str) -> None:
        self.row = row
        self.media = FakeMedia(row["mediaUid"], path)

    def GetUniqueId(self) -> str:
        return cast(str, self.row["uid"])

    def GetMediaPoolItem(self) -> FakeMedia:
        return self.media

    def GetLinkedItems(self) -> list[FakeClip]:
        return []

    def GetStart(self, _frame: bool) -> int:
        return cast(int, self.row["recordStart"])

    def GetDuration(self, _frame: bool) -> int:
        return cast(int, self.row["recordDuration"])

    def GetEnd(self, _frame: bool) -> int:
        return cast(int, self.row["recordStart"]) + cast(
            int, self.row["recordDuration"]
        )

    def GetSourceStartFrame(self) -> int:
        return cast(int, self.row["sourceStart"])

    def GetSourceEndFrame(self) -> int:
        return cast(int, self.row["sourceEnd"])

    def GetSourceStartTime(self) -> float:
        return cast(int, self.row["sourceStart"]) * 1001 / 24000

    def GetSourceEndTime(self) -> float:
        return cast(int, self.row["sourceEnd"]) * 1001 / 24000


class FakeTimeline:
    def __init__(self, geom: dict[str, Any], path: str) -> None:
        self.entries: dict[tuple[str, int], list[FakeClip]] = {}
        for row in geom["items"]:
            key = (row["kind"], row["track"])
            self.entries.setdefault(key, []).append(FakeClip(row, path))
        self.calls: list[str] = []

    def GetName(self) -> str:
        return cast(str, probe.CASE_NAME)

    def GetUniqueId(self) -> str:
        return "timeline-123"

    def GetTrackCount(self, kind: str) -> int:
        return {"video": 5, "audio": 1, "subtitle": 0}[kind]

    def GetTrackName(self, kind: str, index: int) -> str:
        return cast(
            str, next(n for k, i, n in probe.EXPECTED_TRACKS if (kind, index) == (k, i))
        )

    def GetIsTrackLocked(self, kind: str, index: int) -> bool:
        return (kind, index) != ("video", 1)

    def GetItemListInTrack(self, kind: str, index: int) -> list[FakeClip]:
        self.calls.append(f"GetItemListInTrack({kind},{index})")
        return self.entries.get((kind, index), [])


class FakeProject:
    def __init__(self, timeline: FakeTimeline) -> None:
        self.timeline = timeline

    def GetName(self) -> str:
        return cast(str, probe.CASE_NAME)

    def GetUniqueId(self) -> str:
        return "project-123"

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.timeline

    def IsRenderingInProgress(self) -> bool:
        return False


class FakeManager:
    def __init__(self, project: FakeProject) -> None:
        self.project = project

    def GetCurrentProject(self) -> FakeProject:
        return self.project

    def GetCurrentFolder(self) -> str:
        return ""


class FakeResolve:
    def __init__(self, manager: FakeManager) -> None:
        self.manager = manager

    def GetVersion(self) -> list[Any]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> FakeManager:
        return self.manager


def geometry() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    v1 = (
        (0, 351, 0, 351),
        (351, 127, 24, 151),
        (478, 237, 0, 237),
        (715, 214, 0, 214),
        (929, 261, 0, 261),
        (1190, 217, 0, 217),
    )
    for j, (start, duration, source_start, source_end) in enumerate(v1):
        rows.append(
            {
                "uid": f"clip-{j}",
                "mediaUid": "media-root",
                "kind": "video",
                "track": 1,
                "recordStart": start,
                "recordDuration": duration,
                "sourceStart": source_start,
                "sourceEnd": source_end,
                "links": [],
            }
        )
    for j, (kind, track, start, duration) in enumerate(
        (
            ("video", 2, 71, 47),
            ("video", 2, 800, 70),
            ("audio", 1, 0, 478),
            ("audio", 1, 478, 452),
            ("audio", 1, 930, 477),
        ),
        start=6,
    ):
        rows.append(
            {
                "uid": f"clip-{j}",
                "mediaUid": f"media-{j}",
                "kind": kind,
                "track": track,
                "recordStart": start,
                "recordDuration": duration,
                "sourceStart": 0,
                "sourceEnd": duration,
                "links": [],
            }
        )
    rows.sort(key=lambda r: (r["kind"], r["track"], r["recordStart"], r["uid"]))
    tracks = [
        {"kind": k, "index": i, "name": n, "locked": (k, i) != ("video", 1)}
        for k, i, n in probe.EXPECTED_TRACKS
    ]
    return {"tracks": tracks, "items": rows}


@pytest.fixture
def fake_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Path]:
    root = tmp_path / "case"
    (root / "assets").mkdir(parents=True)
    root.chmod(0o700)
    (root / "assets").chmod(0o700)
    sample = root / "assets" / "root.mp4"
    sample.write_bytes(b"dummy fixed source, synthetic only")
    monkeypatch.setattr(
        probe,
        "ASSET_HASHES",
        {**probe.ASSET_HASHES, "root.mp4": probe.sha(sample.read_bytes())},
    )
    geo = geometry()
    timeline = FakeTimeline(geo, str(sample))
    resolve = FakeResolve(FakeManager(FakeProject(timeline)))
    evidence = {
        "target": {
            "projectUid": "project-123",
            "timelineUid": "timeline-123",
            "folder": "",
        },
        "reopened": deepcopy(geo),
        "before": {},
    }
    return resolve, evidence, root


def test_observe_is_read_only_redacted_and_not_a_m4_acceptance(
    fake_case: tuple[Any, Any, Path],
) -> None:
    sdk, evidence, root = fake_case
    report = probe.observe(sdk, evidence, root, lambda: probe.SOURCE_GRAPH)
    assert report["nativeEditPerformed"] is False
    assert report["itemsVerified"] == 11 and report["tracksVerified"] == 6
    assert report["boundary"]["right"]["raw"]["GetSourceStartFrame"] == 24
    assert (
        report["boundary"]["right"]["hostNormalizationInterpretation"]["sourceStart"]
        == 24
    )
    assert (
        report["boundary"]["right"]["hostNormalizationInterpretation"][
            "heldStillTimeNormalizationApplied"
        ]
        is False
    )
    assert report["boundary"]["left"]["GetSourceStartTime"]["available"] is True
    assert report["boundary"]["right"]["sdkClipPropertyType"] == "Video"
    assert str(root) not in json.dumps(report) and "project-123" not in json.dumps(
        report
    )
    assert "media-root" not in json.dumps(report) and "clip-1" not in json.dumps(report)
    assert report["evidenceSha256"] == probe.sha(
        probe.canonical({k: v for k, v in report.items() if k != "evidenceSha256"})
    )
    assert (
        len(sdk.manager.project.timeline.calls) == 12
    )  # two exact six-track snapshots


@pytest.mark.parametrize(
    "change",
    [
        "project",
        "timeline",
        "uid",
        "mediauid",
        "range",
        "path",
        "fps",
        "source",
        "render",
        "lock",
    ],
)
def test_fail_closed_without_edit_or_replay(
    fake_case: tuple[Any, Any, Path], monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    sdk, evidence, root = fake_case
    timeline = sdk.manager.project.timeline

    def source() -> str:
        return cast(str, probe.SOURCE_GRAPH)

    if change == "project":
        evidence["target"]["projectUid"] = "other-project"
    if change == "timeline":
        evidence["target"]["timelineUid"] = "other-timeline"
    if change == "uid":
        timeline.entries[("video", 1)][0].row["uid"] = "unexpected-uid"
    if change == "mediauid":
        timeline.entries[("video", 1)][0].media.uid = "other-media"
    if change == "range":
        timeline.entries[("video", 1)][1].row["sourceStart"] = 25
    if change == "path":
        timeline.entries[("video", 1)][0].media.path = "/not-the-calibration.mp4"
    if change == "fps":
        monkeypatch.setattr(
            timeline.entries[("video", 1)][0].media,
            "GetClipProperty",
            lambda: {
                "File Path": str(root / "assets" / "root.mp4"),
                "Frames": "720",
                "FPS": "0",
                "Online Status": "Online",
            },
        )
    if change == "source":

        def changed_source() -> str:
            return "f" * 64

        source = changed_source
    if change == "render":
        monkeypatch.setattr(sdk.manager.project, "IsRenderingInProgress", lambda: True)
    if change == "lock":
        monkeypatch.setattr(timeline, "GetIsTrackLocked", lambda *_: False)
    with pytest.raises(probe.Refusal):
        probe.observe(sdk, evidence, root, source)
    assert not any(
        "Set" in name or "Save" in name or "Load" in name for name in timeline.calls
    )


def test_late_host_geometry_drift_is_refused(
    fake_case: tuple[Any, Any, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk, evidence, root = fake_case
    timeline = sdk.manager.project.timeline
    orig = timeline.GetItemListInTrack
    number = 0

    def drift(kind: str, index: int) -> list[FakeClip]:
        nonlocal number
        number += 1
        if number == 7:
            timeline.entries[("video", 1)][1].row["recordStart"] = 352
        return cast(list[FakeClip], orig(kind, index))

    monkeypatch.setattr(timeline, "GetItemListInTrack", drift)
    with pytest.raises(probe.Refusal):
        probe.observe(sdk, evidence, root, lambda: probe.SOURCE_GRAPH)


def test_v1_media_uid_swap_after_inventory_is_refused(
    fake_case: tuple[Any, Any, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk, evidence, root = fake_case
    left_clip = sdk.manager.project.timeline.entries[("video", 1)][0]
    first_media = left_clip.media
    reads = 0

    def swapped_media() -> FakeMedia:
        nonlocal reads
        reads += 1
        if reads == 1:
            return cast(FakeMedia, first_media)
        return FakeMedia("replaced-source", first_media.path)

    monkeypatch.setattr(left_clip, "GetMediaPoolItem", swapped_media)
    with pytest.raises(probe.Refusal, match="media UID changed"):
        probe.observe(sdk, evidence, root, lambda: probe.SOURCE_GRAPH)


def test_asset_directory_symlink_cannot_redirect_read(
    fake_case: tuple[Any, Any, Path],
) -> None:
    sdk, evidence, root = fake_case
    (root / "assets").rename(root / "redirect")
    (root / "assets").symlink_to(root / "redirect", target_is_directory=True)
    with pytest.raises(probe.Refusal, match="pinned internal"):
        probe.observe(sdk, evidence, root, lambda: probe.SOURCE_GRAPH)


def test_private_immutable_evidence_auth_and_no_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "v2"
    root.mkdir(mode=0o700)
    evidence: dict[str, Any] = {}
    for key in probe.EVIDENCE_HASHES:
        if key == "authority":
            evidence[key] = {
                "schema": "vera.issue499.direct-roll-calibration.authority/v1",
                "projectName": probe.CASE_NAME,
                "baseCommit": probe.BASE_COMMIT,
                "checkoutCommit": probe.CALIBRATION_COMMIT,
                "sourceGraphSha256": probe.SOURCE_GRAPH,
                "pythonSha256": probe.SCRIPT_HASHES[
                    "issue-499-direct-roll-calibration.py"
                ],
                "setupSha256": probe.SCRIPT_HASHES[
                    "issue-499-direct-roll-setup.applescript"
                ],
                "rollSha256": probe.SCRIPT_HASHES[
                    "issue-499-direct-roll-once.applescript"
                ],
                "authorized": (
                    "one_new_disposable_project_and_at_most_one_roll_start_to_playhead"
                ),
            }
        else:
            evidence[key] = {}
    target = {"projectUid": "one-project", "timelineUid": "one-timeline", "folder": ""}
    geo = geometry()
    evidence["pristine.json"] = {
        "target": target,
        "native": {},
        "sourceCommit": probe.BASE_COMMIT,
        "graph": probe.SOURCE_GRAPH,
        "assets": probe.ASSET_HASHES,
    }
    evidence["post-roll-observation.json"] = {
        "target": target,
        "before": {},
        "after": geo,
        "readError": None,
    }
    evidence["reopened.json"] = {"target": target, "native": geo}
    evidence["saved.json"] = {"target": target, "saved": True}
    evidence["closed.json"] = {"target": target, "closed": True}
    evidence["roll-intent.json"] = {
        "target": target,
        "from": 327,
        "to": 351,
        "scriptSha256": probe.SCRIPT_HASHES["issue-499-direct-roll-once.applescript"],
    }
    paths = {
        key: (tmp_path / "authority.json" if key == "authority" else root / key)
        for key in evidence
    }
    pinned = {}
    for key, value in evidence.items():
        raw = probe.canonical(value)
        paths[key].write_bytes(raw)
        paths[key].chmod(0o600)
        pinned[key] = probe.sha(raw)
    evidence["roll-intent.json"]["baselineSha256"] = pinned["pristine.json"]
    paths["roll-intent.json"].write_bytes(probe.canonical(evidence["roll-intent.json"]))
    pinned["roll-intent.json"] = probe.sha(paths["roll-intent.json"].read_bytes())
    monkeypatch.setattr(probe, "EVIDENCE_HASHES", pinned)
    assert probe.case_evidence(root, paths["authority"])["reopened"] == geo
    paths["roll-intent.json"].write_bytes(b"{}\n")
    with pytest.raises(probe.Refusal):
        probe.case_evidence(root, paths["authority"])
    paths["roll-intent.json"].write_bytes(probe.canonical(evidence["roll-intent.json"]))
    paths["roll-intent.json"].chmod(0o644)
    assert stat.S_IMODE(os.stat(paths["roll-intent.json"]).st_mode) == 0o644
    with pytest.raises(probe.Refusal):
        probe.case_evidence(root, paths["authority"])


def test_live_entry_refuses_wrong_script_digest_before_any_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe.owner,
        "_local_resolve_connection",
        lambda: pytest.fail("must not contact SDK"),
    )
    with pytest.raises(probe.Refusal):
        probe.execute("0" * 64)


def test_busy_owner_refuses_before_sdk_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe, "script_and_source_attested", lambda: None)

    def busy(*, output_lane: bool) -> Any:
        assert output_lane is True
        raise probe.Refusal("native owner busy")

    monkeypatch.setattr(probe.owner, "native_owner", busy)
    monkeypatch.setattr(
        probe.owner,
        "_local_resolve_connection",
        lambda: pytest.fail("must not contact SDK"),
    )
    with pytest.raises(probe.Refusal, match="owner busy"):
        probe.execute(probe.sha(SCRIPT.read_bytes()))


def test_missing_time_getter_stays_missing_not_invented(
    fake_case: tuple[Any, Any, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk, evidence, root = fake_case
    monkeypatch.setattr(FakeClip, "GetSourceStartTime", None)
    report = probe.observe(sdk, evidence, root, lambda: probe.SOURCE_GRAPH)
    assert report["boundary"]["right"]["GetSourceStartTime"] == {
        "available": False,
        "raw": None,
    }
    assert (
        report["boundary"]["right"]["hostNormalizationInterpretation"][
            "heldStillTimeNormalizationApplied"
        ]
        is False
    )


def test_default_command_is_deferred_no_sdk(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setattr(
        probe.owner,
        "_local_resolve_connection",
        lambda: pytest.fail("must not contact SDK"),
    )
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])
    assert probe.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "DEFERRED"
