"""Fake-native tests for the issue #259 OTIO-import probe and host finalizer."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "python"))
from test_issue257_sample_precision_compare import _native_pcm, _source_wav
from vera_timeline_agent import sample_import_compare_v2 as compare
from vera_timeline_agent import sample_import_probe_v2 as probe
from vera_timeline_agent import sample_precision_compare_v2 as pcm_base
from vera_timeline_agent import sample_precision_probe_v2 as base
from vera_timeline_agent import workflow_v2_cli
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

_fixtures: Any = importlib.import_module("test_issue257_sample_precision_probe")
_environment = _fixtures._environment
_NativeState = _fixtures._NativeState
_Project = _fixtures._Project
_Folder = _fixtures._Folder
_TimelineMedia = _fixtures._TimelineMedia

SAMPLES = [((index * 7919) % (1 << 20)) - (1 << 19) for index in range(400400)]


def _quantize(sample: int) -> int:
    """Round to the 2002-sample video grid like the #257 AppendToTimeline route."""
    return round(sample / 2002) * 2002


# ----------------------------------------------------------------------------
# Fake Resolve with ImportTimelineFromFile (and, deliberately, no Append/Delete)
# ----------------------------------------------------------------------------


class _S(_NativeState):  # type: ignore[misc,valid-type]
    def __init__(
        self,
        request: dict[str, Any],
        *,
        quantize_roles: tuple[str, ...] = (),
        missing_getter: str | None = None,
        absent_getter: str | None = None,
        empty_job: bool = False,
        import_none: bool = False,
        frame_rate: str = "23.976",
        extra_target_item: bool = False,
        project_uid: str | None = None,
        job_timeline: str = "candidate",
        readback: str = "exact",
        subtype_raises: bool = False,
        remap_after_reopen: bool = False,
    ) -> None:
        super().__init__(request)
        self.job_timeline = job_timeline
        self.readback = readback
        self.subtype_raises = subtype_raises
        self.remap_after_reopen = remap_after_reopen
        if project_uid is not None:
            self.project_uid = project_uid
        self.source_path = cast(str, request["sourcePath"])
        self.quantize_roles = quantize_roles
        self.missing_getter = missing_getter
        self.absent_getter = absent_getter
        self.empty_job = empty_job
        self.import_none = import_none
        self.frame_rate = frame_rate
        self.timelines: list[dict[str, Any]] = [
            {
                "uid": self.timeline_uid,
                "name": self.timeline_name,
                "audio": (
                    [{"uid": "stray", "record": (0, 2002), "source": (0, 2002)}]
                    if extra_target_item
                    else []
                ),
                "video": [],
                "video_tracks": 1,
            }
        ]
        self.current_uid = self.timeline_uid
        self.calls: list[str] = []


class _Media:
    def __init__(self, path: str) -> None:
        self.path = path

    def GetUniqueId(self) -> str:
        return "media-" + hashlib.sha256(self.path.encode()).hexdigest()[:8]

    def GetClipProperty(self) -> dict[str, str]:
        return {"Online Status": "Online", "File Path": self.path}


class _Item:
    def __init__(self, state: _S, row: dict[str, Any], *, path: str) -> None:
        self.state, self.row, self.path = state, row, path

    def __getattribute__(self, name: str) -> Any:
        state = object.__getattribute__(self, "state")
        if name == state.absent_getter:
            raise AttributeError(name)
        if name == state.missing_getter:

            def refuse(*_args: Any) -> Any:
                raise RuntimeError(f"{name} failed")

            return refuse
        return object.__getattribute__(self, name)

    def GetUniqueId(self) -> str:
        return cast(str, self.row["uid"])

    def GetMediaPoolItem(self) -> _Media:
        return _Media(self.path)

    def GetStart(self, sub: bool = False) -> float:
        frames = self.row["record"][0] / 2002
        return frames if sub else float(int(frames))

    def GetEnd(self, sub: bool = False) -> float:
        frames = self.row["record"][1] / 2002
        return frames if sub else float(int(frames))

    def GetDuration(self, sub: bool = False) -> float:
        frames = (self.row["record"][1] - self.row["record"][0]) / 2002
        return frames if sub else float(int(frames))

    def GetSourceStartFrame(self) -> float:
        return cast(float, self.row["source"][0] / 2002)

    def GetSourceEndFrame(self) -> float:
        return cast(float, self.row["source"][1] / 2002)

    def GetSourceStartTime(self) -> float:
        return cast(float, self.row["source"][0] / 48000)

    def GetSourceEndTime(self) -> float:
        return cast(float, self.row["source"][1] / 48000)

    def GetSourceAudioChannelMapping(self) -> str:
        state = object.__getattribute__(self, "state")
        return "stereo" if state.remap_after_reopen and state.epoch >= 1 else "mono"


class _Timeline:
    def __init__(self, state: _S, row: dict[str, Any]) -> None:
        self.state, self.row, self.epoch = state, row, state.epoch

    def _live(self) -> None:
        if self.epoch != self.state.epoch:
            raise RuntimeError("stale timeline handle after project reopen")

    def GetUniqueId(self) -> str:
        return cast(str, self.row["uid"])

    def GetName(self) -> str:
        return cast(str, self.row["name"])

    def GetSetting(self, key: str) -> str:
        self._live()
        return {
            "timelineFrameRate": (
                "23.976"
                if self.row is self.state.timelines[0]
                else self.state.frame_rate
            ),
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }[key]

    def GetStartFrame(self) -> int:
        return 0

    def GetStartTimecode(self) -> str:
        return "00:00:00:00"

    def GetTrackCount(self, kind: str) -> int:
        return cast(
            int, {"audio": 1, "video": self.row["video_tracks"], "subtitle": 0}[kind]
        )

    def GetTrackSubType(self, kind: str, index: int) -> str:
        assert kind == "audio" and index == 1
        if self.state.subtype_raises:
            raise RuntimeError("GetTrackSubType failed")
        return "mono"

    def GetMarkers(self) -> dict[str, Any]:
        return {}

    def GetMediaPoolItem(self) -> Any:
        return _TimelineMedia(self.state)

    def GetItemListInTrack(self, kind: str, index: int) -> list[_Item]:
        self._live()
        assert index == 1
        rows = self.row["audio"] if kind == "audio" else self.row["video"]
        path = (
            self.state.source_path
            if kind == "audio"
            else cast(dict[str, str], self.state.request["picture"] or {}).get(
                "path", ""
            )
        )
        return [_Item(self.state, row, path=path) for row in rows]


class _Pool:
    def __init__(self, state: _S) -> None:
        self.state = state

    def GetRootFolder(self) -> Any:
        return _Folder(self.state)

    def ImportTimelineFromFile(
        self, path: str, options: dict[str, Any]
    ) -> _Timeline | None:
        state = self.state
        state.calls.append("ImportTimelineFromFile")
        if state.import_none:
            return None
        role = options["timelineName"].split("-")[1]
        document = json.loads(Path(path).read_text())
        audio: list[dict[str, Any]] = []
        video: list[dict[str, Any]] = []
        for track in document["tracks"]["children"]:
            cursor = 0
            for child in track["children"]:
                span = child["source_range"]
                start = int(span["start_time"]["value"])
                duration = int(span["duration"]["value"])
                if child["OTIO_SCHEMA"].startswith("Clip"):
                    source = (start, start + duration)
                    if track["kind"] == "Audio" and role in state.quantize_roles:
                        source = (_quantize(source[0]), _quantize(source[1]))
                    row = {
                        "uid": f"item-{state.next_uid}",
                        "record": (cursor, cursor + duration),
                        "source": source,
                    }
                    state.next_uid += 1
                    (audio if track["kind"] == "Audio" else video).append(row)
                cursor += duration
        timeline_row: dict[str, Any] = {
            "uid": f"timeline-{state.next_uid}",
            "name": options["timelineName"],
            "audio": audio,
            "video": video,
            "video_tracks": 1 if video else 0,
        }
        state.next_uid += 1
        state.timelines.append(timeline_row)
        state.current_uid = timeline_row["uid"]
        if not state.media:
            state.media.append({"uid": "media-source", "path": state.source_path})
        return _Timeline(state, timeline_row)


class _P(_Project):  # type: ignore[misc,valid-type]
    def __init__(self, state: _S) -> None:
        super().__init__(state)
        self.s = state
        self.pool = _Pool(state)

    def GetUniqueId(self) -> str:
        return self.s.project_uid

    def _row(self) -> dict[str, Any]:
        return next(t for t in self.s.timelines if t["uid"] == self.s.current_uid)

    def GetCurrentTimeline(self) -> _Timeline:
        return _Timeline(self.s, self._row())

    def GetTimelineCount(self) -> int:
        return len(self.s.timelines)

    def GetTimelineByIndex(self, index: int) -> _Timeline:
        return _Timeline(self.s, self.s.timelines[index - 1])

    def SetCurrentTimeline(self, timeline: _Timeline) -> bool:
        timeline._live()
        self.s.current_uid = timeline.GetUniqueId()
        return True

    def AddRenderJob(self) -> str:
        if self.s.empty_job:
            return ""
        job_id = cast(str, super().AddRenderJob())
        if self.s.job_timeline == "candidate":
            self.s.queue[-1]["TimelineName"] = self._row()["name"]
        elif self.s.job_timeline == "other":
            self.s.queue[-1]["TimelineName"] = "some-other-timeline"
        return job_id

    def GetRenderSettings(self) -> dict[str, Any]:
        if self.s.readback == "raises":
            raise RuntimeError("GetRenderSettings failed")
        settings = cast(dict[str, Any], super().GetRenderSettings())
        if self.s.readback == "differs":
            settings["TargetDir"] = "/somewhere/else"
        return settings


class _Manager:
    def __init__(self, state: _S) -> None:
        self.state = state
        self.current: Any = _P(state)

    def GetCurrentProject(self) -> Any:
        return self.current

    def SaveProject(self) -> bool:
        return True

    def CloseProject(self, project: _P) -> bool:
        assert project is self.current
        self.current = object()
        return True

    def LoadProject(self, name: str) -> _P:
        assert name == self.state.project_name
        self.state.epoch += 1
        self.state.current_uid = self.state.timelines[0]["uid"]
        self.current = _P(self.state)
        return cast(_P, self.current)


class _Resolve:
    def __init__(self, state: _S) -> None:
        self.manager = _Manager(state)

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[Any]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> _Manager:
        return self.manager


# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------


class _Env:
    def __init__(self) -> None:
        self.request_path: Path
        self.request: dict[str, Any]
        self.request_sha: str
        self.installed_request: Path
        self.tmp: Path
        self.release_root: Path


def _picture_stub(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(b"disposable black picture control")
    path.chmod(0o400)


def _env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_picture: bool = True
) -> _Env:
    _, _, _ = _environment(tmp_path, monkeypatch)
    fixture = json.loads((tmp_path / "evidence" / "request.json").read_text())
    source_path = Path(fixture["sourcePath"])
    review_path = Path(fixture["reviewPath"])
    source_wav, source_pcm = _source_wav(SAMPLES)
    source_path.write_bytes(source_wav)
    source_sha = hashlib.sha256(source_wav).hexdigest()
    pcm_sha = hashlib.sha256(source_pcm).hexdigest()
    monkeypatch.setattr(base, "SOURCE_SHA256", source_sha)
    monkeypatch.setattr(base, "SOURCE_PCM_SHA256", pcm_sha)
    review = json.loads(review_path.read_text())
    review["originalSourceAudioHash"] = f"sha256:{source_sha}"
    review["sourcePcmSha256"] = f"sha256:{pcm_sha}"
    review_path.write_text(json.dumps(review, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(
        base, "REVIEW_SHA256", hashlib.sha256(review_path.read_bytes()).hexdigest()
    )
    env = _Env()
    env.tmp = tmp_path
    env.release_root = tmp_path / "import-release"
    workflow_v2_cli.build_sample_import_release_v2(env.release_root)
    installed_root = tmp_path / "installed-plugin"
    shutil.copytree(env.release_root, installed_root)
    monkeypatch.setattr(
        probe,
        "__file__",
        str(
            installed_root
            / "vera-delivery-v2/python/vera_timeline_agent/sample_import_probe_v2.py"
        ),
    )
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "import-state")
    monkeypatch.setattr(probe, "generate_black_picture", _picture_stub)
    env.request_path = probe.prepare_import_request(
        release_root=env.release_root,
        output=tmp_path / "import-evidence",
        source=source_path,
        review=review_path,
        target=fixture["target"],
        producer_authorization=fixture["producerAuthorization"],
        task_id=fixture["taskId"],
        with_picture=with_picture,
    )
    payload = env.request_path.read_bytes()
    env.request_sha = hashlib.sha256(payload).hexdigest()
    env.installed_request = installed_root / "vera-delivery-v2/request.json"
    env.installed_request.write_bytes(payload)
    env.installed_request.chmod(0o400)
    monkeypatch.setattr(pcm_base, "_INSTALLED_REQUEST_PATH", env.installed_request)
    env.request = probe.load_import_request(env.request_path, env.request_sha)
    return env


def _run(env: _Env, **options: Any) -> tuple[dict[str, Any], _Resolve, _S]:
    state = _S(env.request, **options)
    resolve = _Resolve(state)
    result_path = probe.run_sample_import_probe(
        resolve, env.installed_request, expected_request_sha256=env.request_sha
    )
    return json.loads(result_path.read_text()), resolve, state


def _geometry(env: _Env, result: dict[str, Any]) -> dict[str, Any]:
    return compare.analyze_geometry(
        result["observations"],
        result["timelines"],
        env.request["imports"],
        env.request["sourcePath"],
    )


# ----------------------------------------------------------------------------
# OTIO writer and request
# ----------------------------------------------------------------------------


def test_otio_writer_exact_sample_times_gap_and_deterministic_bytes(
    tmp_path: Path,
) -> None:
    rows = probe.expected_imports(
        "0" * 8 + "-1111-2222-3333-" + "4" * 12, tmp_path, with_picture=True
    )
    by_role = {row["role"]: row for row in rows}
    payload = probe.otio_bytes(
        by_role["candidate"], source_path="/media/original.wav", picture_path="/p/b.mov"
    )
    assert payload == probe.otio_bytes(
        by_role["candidate"], source_path="/media/original.wav", picture_path="/p/b.mov"
    )
    document = json.loads(payload)
    assert document["global_start_time"]["rate"] == 48000.0
    tracks = {t["kind"]: t for t in document["tracks"]["children"]}
    audio = tracks["Audio"]["children"]
    assert [child["OTIO_SCHEMA"] for child in audio] == ["Clip.2", "Gap.1", "Clip.2"]
    spans = [
        (
            child["source_range"]["start_time"]["value"],
            child["source_range"]["duration"]["value"],
        )
        for child in audio
    ]
    assert spans == [(0.0, 232320.0), (0.0, 9120.0), (241440.0, 158960.0)]
    for child in audio:
        for stamp in (
            child["source_range"]["start_time"],
            child["source_range"]["duration"],
        ):
            assert stamp["rate"] == 48000.0
    assert 241440.0 + 158960.0 == 400400.0
    assert (
        tracks["Video"]["children"][0]["source_range"]["duration"]["value"] == 400400.0
    )
    probe.verify_otio_payload(
        payload,
        by_role["candidate"],
        source_path="/media/original.wav",
        picture_path="/p/b.mov",
    )
    # Off-grid calibration source edges are half a frame off the 2002 grid.
    calibration = json.loads(
        probe.otio_bytes(
            by_role["calibration"],
            source_path="/media/original.wav",
            picture_path="/p/b.mov",
        )
    )
    clip = {t["kind"]: t for t in calibration["tracks"]["children"]}["Audio"][
        "children"
    ][0]
    start = clip["source_range"]["start_time"]["value"]
    assert start == 101101.0 and start % 2002 != 0
    assert (start + clip["source_range"]["duration"]["value"]) % 2002 == 1001
    tampered = payload.replace(b"232320.0", b"232232.0")
    with pytest.raises(ValueError, match="differs"):
        probe.verify_otio_payload(
            tampered,
            by_role["candidate"],
            source_path="/media/original.wav",
            picture_path="/p/b.mov",
        )
    with pytest.raises(ValueError, match="unmodified original"):
        probe.verify_otio_payload(
            payload,
            by_role["candidate"],
            source_path="/media/other.wav",
            picture_path="/p/b.mov",
        )


def test_prepare_pins_hashed_immutable_inputs_and_closed_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    request = env.request
    inputs = Path(request["inputsDir"])
    assert inputs == tmp_path / "import-state" / "inputs" / request["requestId"]
    assert [row["role"] for row in request["imports"]] == list(probe.ROLES)
    for row in request["imports"]:
        payload = Path(row["otioPath"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["otioSha256"]
        assert not Path(row["otioPath"]).stat().st_mode & 0o222
        probe.verify_otio_payload(
            payload,
            row,
            source_path=request["sourcePath"],
            picture_path=request["picture"]["path"],
        )
    assert request["picture"]["frames"] == 200
    assert (
        request["picture"]["sha256"]
        == hashlib.sha256(Path(request["picture"]["path"]).read_bytes()).hexdigest()
    )
    forged = json.loads(env.request_path.read_text())
    forged["imports"][2]["plan"]["audioClips"][0]["sourceEnd"] = 232232
    with pytest.raises(ValueError, match="import plan differs"):
        probe._validate_request(forged)
    forged = json.loads(env.request_path.read_text())
    forged["imports"][0]["otioPath"] = str(tmp_path / "elsewhere.otio")
    with pytest.raises(ValueError, match="import plan differs"):
        probe._validate_request(forged)
    forged = json.loads(env.request_path.read_text())
    forged["unexpected"] = 1
    with pytest.raises(ValueError, match="fields"):
        probe._validate_request(forged)


def test_audio_only_request_has_no_picture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch, with_picture=False)
    assert env.request["picture"] is None
    document = json.loads(Path(env.request["imports"][2]["otioPath"]).read_text())
    assert [t["kind"] for t in document["tracks"]["children"]] == ["Audio"]


# ----------------------------------------------------------------------------
# Native run: construction, identity, refusals
# ----------------------------------------------------------------------------


def test_runner_constructs_only_by_import_and_pins_new_timelines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, resolve, state = _run(env)

    assert result["status"] == "rendered_for_pcm_verification"
    assert [(r["stage"], r["method"]) for r in result["effects"]] == list(
        probe.EFFECT_SEQUENCE
    )
    assert all(r["status"] == "returned" for r in result["effects"])
    assert all(Path(r["journalPath"]).is_file() for r in result["effects"])
    assert state.calls == ["ImportTimelineFromFile"] * 3
    assert not any(hasattr(_P, name) for name in ("AppendToTimeline", "DeleteClips"))
    imports = {r["stage"]: r for r in result["effects"]}
    for row in env.request["imports"]:
        effect = imports[f"import_{row['role']}"]
        assert effect["arguments"] == [row["otioPath"], probe.import_options(row)]
    uids = {role: result["timelines"][role]["uid"] for role in probe.ROLES}
    assert len({*uids.values(), env.request["target"]["timelineUid"]}) == 4
    for role in probe.ROLES:
        assert result["timelines"][role]["name"].startswith(f"VERA259-{role}-")
    assert [o["stage"] for o in result["observations"]] == list(
        probe.OBSERVATION_STAGES
    )
    candidate = result["observations"][-1]
    item = candidate["tracks"]["audio"][0]["items"][1]
    assert item["rawGetters"]["GetSourceStartTime"]["value"] == 241440 / 48000
    assert item["rawGetters"]["GetSourceAudioChannelMapping"]["value"] == "mono"
    # Documented getters absent from this fake are recorded, never guessed.
    assert item["rawGetters"]["GetLeftOffset(True)"]["status"] == "unsupported"
    assert candidate["tracks"]["audio"][0]["subType"]["value"] == "mono"
    # Only the candidate is rendered; the queue holds exactly its job.
    assert len(state.queue) == 1
    assert result["render"]["status"] == "rendered_for_pcm_verification"
    assert result["render"]["jobId"] == "job-257"
    assert result["sourceIntegrity"]["unchanged"] is True
    assert _geometry(env, result)["status"] == "pass"
    assert resolve.manager.current is not None


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"extra_target_item": True}, "not empty"),
        ({"project_uid": "someone-elses-project"}, "differs from the explicitly"),
    ],
)
def test_runner_refuses_wrong_or_nonempty_target_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: dict[str, Any],
    message: str,
) -> None:
    env = _env(tmp_path, monkeypatch)
    state = _S(env.request, **options)
    with pytest.raises(ValueError, match=message):
        probe.run_sample_import_probe(
            _Resolve(state),
            env.installed_request,
            expected_request_sha256=env.request_sha,
        )
    assert state.calls == []
    assert not (tmp_path / "import-state" / "intents").exists()


def test_runner_refuses_populated_project_timeline_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    state = _S(env.request)
    state.timelines.append(
        {"uid": "other", "name": "other", "audio": [], "video": [], "video_tracks": 0}
    )
    with pytest.raises(ValueError, match="timelines other than"):
        probe.run_sample_import_probe(
            _Resolve(state),
            env.installed_request,
            expected_request_sha256=env.request_sha,
        )
    assert state.calls == []


def test_authority_is_single_use_and_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    _run(env)
    # The evidence directory is consumed, so a second run is refused.
    with pytest.raises(ValueError, match="already used"):
        _run(env)
    # Even with fresh evidence the target/request intent claim is one-use.
    (Path(env.request["outputDir"]) / "result.json").chmod(0o600)
    (Path(env.request["outputDir"]) / "result.json").unlink()
    shutil.rmtree(Path(env.request["outputDir"]) / "journal")
    with pytest.raises(FileExistsError):
        _run(env)

    stale = json.loads(env.installed_request.read_text())
    stale["issuedAt"] = "2000-01-01T00:00:00+00:00"
    stale["expiresAt"] = "2000-01-01T00:30:00+00:00"
    payload = (json.dumps(stale, sort_keys=True, indent=2) + "\n").encode()
    env.installed_request.chmod(0o600)
    env.installed_request.write_bytes(payload)
    with pytest.raises(ValueError, match="expired"):
        probe.run_sample_import_probe(
            _Resolve(_S(env.request)),
            env.installed_request,
            expected_request_sha256=hashlib.sha256(payload).hexdigest(),
        )


@pytest.mark.parametrize("mutation", ["source", "otio", "picture"])
def test_runner_refuses_changed_pinned_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    env = _env(tmp_path, monkeypatch)
    if mutation == "source":
        path = Path(env.request["sourcePath"])
        path.write_bytes(path.read_bytes() + b"x")
        message = "source bytes changed"
    else:
        path = (
            Path(env.request["imports"][2]["otioPath"])
            if mutation == "otio"
            else Path(env.request["picture"]["path"])
        )
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b" ")
        message = "changed"
    state = _S(env.request)
    with pytest.raises(ValueError, match=message):
        probe.run_sample_import_probe(
            _Resolve(state),
            env.installed_request,
            expected_request_sha256=env.request_sha,
        )
    assert state.calls == []


def test_import_that_returns_no_timeline_is_retained_as_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, state = _run(env, import_none=True)
    assert result["status"] == "unsupported"
    assert "returned no timeline" in result["failure"]["message"]
    assert [r["stage"] for r in result["effects"]] == ["import_control"]
    assert state.queue == []
    assert result["render"] == {"status": "incomplete"}


def test_wrong_frame_rate_stops_before_more_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, state = _run(env, frame_rate="48000")
    assert result["status"] == "unsupported"
    assert "not 23.976 fps" in result["failure"]["message"]
    assert state.calls == ["ImportTimelineFromFile"]


def test_empty_add_render_job_is_an_explicit_limited_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, state = _run(env, empty_job=True)
    assert result["status"] == "render_limited"
    assert result["render"]["status"] == "add_render_job_returned_no_job"
    assert result["render"]["addRenderJobReturn"] == ""
    assert result["render"]["queueAfterAttempt"] == []
    assert state.queue == []
    assert result["effects"][-1]["stage"] == "render_add_job"
    assert result["effects"][-1]["returnValue"] == ""
    assert not Path(probe.render_output_path(env.request)).exists()
    assert _geometry(env, result)["status"] == "pass"


# ----------------------------------------------------------------------------
# Geometry interpretation
# ----------------------------------------------------------------------------


def test_exact_geometry_passes_with_calibrated_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env)
    geometry = _geometry(env, result)
    assert geometry["status"] == "pass"
    assert geometry["semantics"] == {
        "recordEndEndpoint": "exclusive",
        "sourceUnit": "seconds",
        "sourceEndEndpoint": "exclusive",
    }
    for stage in ("candidate_imported", "candidate_after_reopen"):
        rows = geometry["candidateChecks"][stage]
        assert rows[0]["actual"]["sourceEndExclusive"] == 232320
        assert rows[1]["actual"]["sourceStart"] == 241440
        assert rows[1]["actual"]["recordStart"] == 241440


def test_quantized_candidate_edges_are_unsupported_when_calibration_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env, quantize_roles=("candidate",))
    geometry = _geometry(env, result)
    assert geometry["status"] == "mismatch"
    assert geometry["calibrationOffGridExact"] is True
    first, second = geometry["candidateChecks"]["candidate_after_reopen"]
    assert first["actual"]["sourceEndExclusive"] == 232232
    assert second["actual"]["sourceStart"] == 242242
    assert second["errorsSamples"]["sourceStart"] == 802
    assert _verdict_of(geometry, "rendered_for_pcm_verification") == (
        "unsupported",
        "measured_geometry_mismatch",
    )


def test_quantization_not_separable_from_getters_is_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env, quantize_roles=("calibration", "candidate"))
    geometry = _geometry(env, result)
    assert geometry["status"] == "ambiguous"
    assert "not separable" in geometry["reason"]
    assert geometry["calibrationOffGridExact"] is False


def test_getter_unavailable_or_failing_is_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env, missing_getter="GetSourceStartTime")
    geometry = _geometry(env, result)
    assert geometry["status"] == "ambiguous"
    assert "GetSourceStartTime" in geometry["reason"]
    assert _verdict_of(geometry, "rendered_for_pcm_verification")[0] == "ambiguous"


def test_absent_getter_is_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch, with_picture=False)
    result, _, _ = _run(env, absent_getter="GetSourceEndTime")
    geometry = _geometry(env, result)
    assert geometry["status"] == "unsupported"
    assert _verdict_of(geometry, "rendered_for_pcm_verification")[0] == "unsupported"


def _verdict_of(geometry: dict[str, Any], native: str) -> tuple[str, str | None]:
    return compare._verdict(native, geometry, {"status": "pass"}, source_unchanged=True)


# ----------------------------------------------------------------------------
# Host finalization (decoded PCM is substituted at the decoder boundary only)
# ----------------------------------------------------------------------------


def _finalize(
    env: _Env,
    monkeypatch: pytest.MonkeyPatch,
    native_pcm: bytes | None,
    **options: Any,
) -> dict[str, Any]:
    result_path = probe.run_sample_import_probe(
        _Resolve(state := _S(env.request, **options)),
        env.installed_request,
        expected_request_sha256=env.request_sha,
    )
    del state
    env.installed_request.rename(env.installed_request.with_name("archived.json"))
    env.installed_request.write_bytes(b"replacement after native execution\n")
    if native_pcm is not None:
        monkeypatch.setattr(
            pcm_base,
            "_decode_probe_mov",
            lambda _p, _s: (native_pcm, {"decoderIdentitySha256": "c" * 64}),
        )
    final = compare.finalize_import_probe(
        env.request_path,
        result_path,
        env.tmp / f"final-{len(list(env.tmp.iterdir()))}.json",
    )
    return cast(dict[str, Any], json.loads(final.read_text()))


def test_exact_geometry_and_matching_pcm_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    report = _finalize(env, monkeypatch, _native_pcm(SAMPLES))
    assert report["status"] == "supported"
    assert report["geometry"]["status"] == "pass"
    assert report["pcm"]["status"] == "pass"
    assert report["nativeRequestPath"] == str(env.installed_request)
    assert report["sourceIntegrity"]["unchanged"] is True


def test_pcm_mismatch_with_exact_geometry_is_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    shifted = [0, *SAMPLES[:-1]]
    report = _finalize(env, monkeypatch, _native_pcm(shifted))
    assert report["geometry"]["status"] == "pass"
    assert report["pcm"]["status"] == "fail"
    assert report["status"] == "unsupported"
    assert report["reasonCategory"] == "measured_pcm_mismatch"


def test_quantized_geometry_is_unsupported_even_if_pcm_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    report = _finalize(
        env, monkeypatch, _native_pcm(SAMPLES), quantize_roles=("candidate",)
    )
    assert report["geometry"]["status"] == "mismatch"
    assert report["status"] == "unsupported"
    assert report["reasonCategory"] == "measured_geometry_mismatch"


def test_missing_job_is_limited_not_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    report = _finalize(env, monkeypatch, None, empty_job=True)
    assert report["nativeResultStatus"] == "render_limited"
    assert report["nativeRender"] == {"status": "unsupported"}
    assert report["status"] == "ambiguous"
    assert report["reasonCategory"] == "render_limited"
    assert report["pcm"]["status"] == "unsupported"


def test_finalizer_refuses_tampered_native_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result_path = probe.run_sample_import_probe(
        _Resolve(_S(env.request)),
        env.installed_request,
        expected_request_sha256=env.request_sha,
    )
    assert result_path == Path(env.request["outputDir"]) / "result.json"
    result = json.loads(result_path.read_text())
    result["effects"][0]["arguments"][1]["importSourceClips"] = False
    result_path.chmod(0o600)
    result_path.write_text(json.dumps(result))
    result_path.chmod(0o400)
    with pytest.raises(
        pcm_base.SamplePrecisionCompareError,
        match="native effect journal content differs",
    ):
        compare.finalize_import_probe(
            env.request_path, result_path, tmp_path / "forged-final.json"
        )


@pytest.mark.parametrize("mode", ["absent", "other"])
def test_job_not_bound_to_candidate_timeline_never_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, state = _run(env, job_timeline=mode)
    assert result["status"] == "render_limited"
    assert result["render"]["status"] == "render_job_not_bound_to_candidate"
    assert "StartRendering" not in [row["method"] for row in result["effects"]]
    assert not Path(probe.render_output_path(env.request)).exists()
    assert state.render_status != "Complete"


def test_finalizer_requires_job_timeline_to_equal_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    # The native check is bypassed by a forged-but-consistent recorded job:
    # the finalizer must independently refuse a job not bound to the candidate.
    result, _, _ = _run(env)
    result["render"]["job"]["TimelineName"] = "some-other-timeline"
    with pytest.raises(pcm_base.SamplePrecisionCompareError, match="candidate"):
        compare._authenticate_render(env.request, result)
    del result["render"]["job"]["TimelineName"]
    with pytest.raises(pcm_base.SamplePrecisionCompareError, match="candidate"):
        compare._authenticate_render(env.request, result)


@pytest.mark.parametrize(
    "options",
    [
        {"subtype_raises": True},
        {"absent_getter": "GetSourceAudioChannelMapping"},
        {"missing_getter": "GetSourceAudioChannelMapping"},
        {"remap_after_reopen": True},
    ],
)
def test_unverified_or_changed_channel_layout_is_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env, **options)
    geometry = _geometry(env, result)
    assert geometry["status"] == "ambiguous"
    assert geometry["channelLayoutProblem"]
    assert geometry["channelLayout"]["candidate_imported"]["trackSubType"] is not None
    assert _verdict_of(geometry, "rendered_for_pcm_verification")[0] == "ambiguous"


def test_observed_identical_channel_layout_is_recorded_in_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, _ = _run(env)
    layout = _geometry(env, result)["channelLayout"]
    for stage in ("candidate_imported", "candidate_after_reopen"):
        assert layout[stage]["trackSubType"] == {"observed": True, "value": "mono"}
        assert all(
            row == {"observed": True, "value": "mono"}
            for row in layout[stage]["itemChannelMappings"]
        )


def test_render_settings_readback_mismatch_stops_before_add_render_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    result, _, state = _run(env, readback="differs")
    assert result["status"] == "render_limited"
    assert result["render"]["status"] == "render_settings_readback_differs"
    assert result["render"]["settings"]["readback"]["status"] == "mismatch"
    assert state.queue == []
    assert result["effects"][-1]["stage"] == "render_set_settings"
    assert "render_add_job" not in [row["stage"] for row in result["effects"]]


def test_finalizer_accepts_readback_mismatch_limited_result_as_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    report = _finalize(env, monkeypatch, None, readback="differs")
    assert report["nativeResultStatus"] == "render_limited"
    assert report["status"] == "ambiguous"
    assert report["reasonCategory"] == "render_limited"


def test_unavailable_settings_readback_is_recorded_but_never_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env(tmp_path, monkeypatch)
    report = _finalize(env, monkeypatch, _native_pcm(SAMPLES), readback="raises")
    assert report["nativeRender"]["settings"]["readback"]["status"] == "ambiguous"
    assert report["nativeRender"]["settingsReadbackVerified"] is False
    assert report["status"] == "ambiguous"
    assert report["reasonCategory"] == "render_settings_readback_unavailable"


# ----------------------------------------------------------------------------
# Release, dispatch and installed inventory
# ----------------------------------------------------------------------------


def test_import_release_is_separate_and_tamper_evident(tmp_path: Path) -> None:
    root = tmp_path / "release"
    manifest = workflow_v2_cli.build_sample_import_release_v2(root)
    assert set(workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES) - set(
        workflow_v2_cli.SAMPLE_PRECISION_RUNTIME_FILES
    ) == {"sample_import_probe_v2.py"}
    assert (
        "sample_import_probe_v2.py"
        not in workflow_v2_cli.SAMPLE_PRECISION_RUNTIME_FILES
    )
    assert "sample_import_probe_v2.py" not in workflow_v2_cli.OUTPUT_RUNTIME_FILES
    assert tuple(probe.RELEASE_RUNTIME_FILES) == tuple(
        workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES
    )
    assert (
        workflow_v2_cli._verify_release_files(
            root, workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES
        )
        == manifest
    )
    module = (
        root
        / workflow_v2_cli.RELEASE_NAME
        / "python/vera_timeline_agent/sample_import_probe_v2.py"
    )
    module.write_bytes(module.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="repository-owned runtime"):
        workflow_v2_cli._verify_release_files(
            root, workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES
        )


def test_delivery_script_inventory_matches_cli_release() -> None:
    script = Path(__file__).parents[1] / "integrations/resolve/VERA Delivery v2.py"
    environment: dict[str, tuple[str, ...]] = {}

    def evaluate(node: ast.expr) -> tuple[str, ...]:
        assert isinstance(node, ast.Tuple)
        names: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                assert isinstance(element.value, ast.Name)
                names.extend(environment[element.value.id])
            else:
                assert isinstance(element, ast.Constant)
                names.append(cast(str, element.value))
        return tuple(names)

    for statement in ast.parse(script.read_text()).body:
        if (
            isinstance(statement, ast.Assign)
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id
            in {
                "TI_RUNTIME_FILES",
                "TI_SAMPLE_PRECISION_RUNTIME_FILES",
                "TI_SAMPLE_IMPORT_RUNTIME_FILES",
            }
        ):
            environment[statement.targets[0].id] = evaluate(statement.value)
    assert environment["TI_SAMPLE_IMPORT_RUNTIME_FILES"] == tuple(
        workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES
    )
    assert environment["TI_SAMPLE_PRECISION_RUNTIME_FILES"] == tuple(
        workflow_v2_cli.SAMPLE_PRECISION_RUNTIME_FILES
    )


def test_import_dispatch_retains_request_pin_and_precision_dispatch_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import sample_precision_probe_v2 as precision

    calls: list[tuple[str, Path, str]] = []

    def import_run(
        resolve: object, path: Path, *, expected_request_sha256: str
    ) -> Path:
        calls.append(("import", path, expected_request_sha256))
        return tmp_path / "result.json"

    def precision_run(
        resolve: object, path: Path, *, expected_request_sha256: str
    ) -> Path:
        calls.append(("precision", path, expected_request_sha256))
        return tmp_path / "result.json"

    monkeypatch.setattr(probe, "run_sample_import_probe", import_run)
    monkeypatch.setattr(precision, "run_sample_precision_probe", precision_run)
    for schema, label in (
        (probe.REQUEST_SCHEMA, "import"),
        (precision.REQUEST_SCHEMA, "precision"),
    ):
        request = tmp_path / f"{label}.json"
        request.write_text(json.dumps({"schemaVersion": schema}))
        pin = sha256(request)
        run_installed_request_v2(object(), request, expected_request_sha256=pin)
        assert calls[-1] == (label, request, pin)
        request.write_text(request.read_text() + " ")
        with pytest.raises(ValueError, match="changed"):
            run_installed_request_v2(object(), request, expected_request_sha256=pin)
    assert len(calls) == 2


def test_cli_import_commands_are_wired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Any] = []

    def release(output: Path) -> Path:
        seen.append(("release", output))
        output.write_text("stub")
        return output

    monkeypatch.setattr(workflow_v2_cli, "build_sample_import_release_v2", release)
    target = tmp_path / "r"
    assert workflow_v2_cli.main(["sample-import-release", "--output", str(target)]) == 0
    assert seen == [("release", target)]
    with pytest.raises(SystemExit):
        workflow_v2_cli.main(["sample-import-prepare", "--release", str(tmp_path)])


@pytest.mark.slow
def test_black_picture_control_is_generated_deterministically_by_pinned_ffmpeg(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first.mov", tmp_path / "second.mov"
    probe.generate_black_picture(first)
    probe.generate_black_picture(second)
    assert first.read_bytes() == second.read_bytes()
    assert not first.stat().st_mode & 0o222
