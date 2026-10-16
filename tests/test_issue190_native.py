"""Issue-owned refusal tests; fake native facts cannot claim qualification."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from issue190_case import make_proof_case
from issue190_native_fixture import FakeResolve, fake_controls
from test_workflow_v2 import _FakeAdapter
from vera_timeline_agent.roundtrip_v2_build import PreparedProofBuildV2
from vera_timeline_agent.roundtrip_v2_native import (
    NativeProofBoundaryV2,
    _controls,
    _get,
    _rate,
    _speed,
)
from vera_timeline_agent.roundtrip_v2_records import (
    ProofNativeError,
    _file_hash,
    proof_source_hashes_v2,
)
from vera_timeline_agent.workflow_v2 import load_verified_package_v2

# Public package/compiler handoffs and complete media hash reads run serially.
pytestmark = pytest.mark.slow


def controls() -> dict[str, Any]:
    return {
        "programControls": {
            "gainDb": 0,
            "effects": [],
            "limiter": False,
            "automation": [],
            "destination": "stereo-program",
        },
        "routes": [
            {
                "itemUid": "audio-item",
                "sourceId": "narration-source",
                "controls": {
                    "enabled": True,
                    "mute": False,
                    "solo": False,
                    "gainDb": 0,
                    "pan": 0,
                    "effects": [],
                    "sends": [],
                    "automation": [],
                    "destination": "stereo-program",
                    "channelMap": "mono-dual",
                },
            }
        ],
    }


def test_explicit_complete_controls_and_rational_profile() -> None:
    _controls(controls(), {"audio-item"})
    assert _rate({"numerator": 24000, "denominator": 1001}).denominator == 1001


@pytest.mark.parametrize(
    "attack",
    [
        "missing-route",
        "duplicate",
        "unknown-route",
        "extra-control",
        "solo",
        "send",
        "effect",
        "unknown-programme",
        "boolean-gain",
        "nan-gain",
    ],
)
def test_unknown_or_incomplete_controls_refuse(attack: str) -> None:
    value = controls()
    route = value["routes"][0]
    if attack == "missing-route":
        value["routes"] = []
    elif attack == "duplicate":
        value["routes"].append(copy.deepcopy(route))
    elif attack == "unknown-route":
        route["itemUid"] = "unowned"
    elif attack == "extra-control":
        route["controls"]["unreadable"] = None
    elif attack == "solo":
        route["controls"]["solo"] = True
    elif attack == "send":
        route["controls"]["sends"] = ["unread-bus"]
    elif attack == "effect":
        route["controls"]["effects"] = ["unread-plugin"]
    elif attack == "unknown-programme":
        value["programControls"]["limiter"] = None
    elif attack == "boolean-gain":
        route["controls"]["gainDb"] = False
    else:
        route["controls"]["gainDb"] = float("nan")
    with pytest.raises(ProofNativeError):
        _controls(value, {"audio-item"})


@pytest.mark.parametrize(
    "value",
    [
        {"numerator": 48000, "denominator": 2002},
        {"numerator": True, "denominator": 1},
        {"numerator": 24, "denominator": 0},
        {"numerator": 24, "denominator": 1, "approximate": True},
    ],
)
def test_inexact_rate_refuses(value: dict[str, Any]) -> None:
    with pytest.raises(ProofNativeError):
        _rate(value)


def test_unavailable_native_interface_is_explicit_handoff() -> None:
    with pytest.raises(ProofNativeError, match="operator handoff"):
        _get(object(), "GetRenderJobList")


@pytest.mark.parametrize(
    "value",
    [
        100,
        {"Percentage": 100},
        {
            "Percentage": True,
            "PitchCorrection": False,
            "StretchKeyframesToFit": False,
            "RippleTimeline": False,
        },
        {
            "Percentage": 101,
            "PitchCorrection": False,
            "StretchKeyframesToFit": False,
            "RippleTimeline": False,
        },
    ],
)
def test_incomplete_or_inexact_actual_speed_options_refuse(value: Any) -> None:
    with pytest.raises(ProofNativeError):
        _speed(value)


@pytest.fixture(scope="module", params=["default", "verified-reuse"])
def prepared(tmp_path_factory: Any, request: Any) -> tuple[Any, Path, Path]:
    root = tmp_path_factory.mktemp("issue190-native-package")
    _, probe = make_proof_case(root, scenario=request.param)
    build = PreparedProofBuildV2(root, authenticate=lambda *_: None, read_probe=probe)
    build.prepare_package()
    package = load_verified_package_v2(
        build.attestation_path, _file_hash(build.attestation_path)[7:]
    )
    return package, build.attestation_path, build.execution / "proof-package.json"


@pytest.fixture
def native(
    prepared: tuple[Any, Path, Path], tmp_path: Path
) -> tuple[NativeProofBoundaryV2, FakeResolve, dict[str, Any], _FakeAdapter]:
    package, attestation, proof = prepared
    resolve = FakeResolve(package)
    adapter = _FakeAdapter()
    boundary = NativeProofBoundaryV2(
        resolve,
        attestation_path=attestation,
        attestation_hash=_file_hash(attestation),
        proof_package_path=proof,
        proof_package_hash=_file_hash(proof),
        evidence_root=tmp_path / "native",
        authenticate=lambda *_: None,
        authority=b"fake-test-authority",
        code_hashes=proof_source_hashes_v2(),
        read_controls=fake_controls,
        adapter_factory=lambda _: adapter,
    )
    target = {
        "projectUid": resolve.project.uid,
        "timelineUid": resolve.project.timeline.uid,
    }
    return boundary, resolve, target, adapter


def test_public_delivery_once_and_readonly_recovery(native: Any) -> None:
    boundary, _, _, adapter = native
    result = boundary.deliver()
    assert result["status"] == "verified"
    assert adapter.calls.count("create_project") == 1
    assert boundary.recover_delivery()["nativeEffects"] == 0
    with pytest.raises(ProofNativeError, match="read-only recovery"):
        boundary.deliver()
    assert adapter.calls.count("create_project") == 1


@pytest.mark.parametrize(
    ("attack", "message"),
    [
        ("intent-owner", "delivery intent ownership differs"),
        ("effect-intent", "delivery effect ancestry differs"),
        ("effect-attestation", "delivery effect attestation differs"),
        ("complete-effect", "delivery completion ancestry differs"),
    ],
)
def test_copied_or_drifted_delivery_records_refuse_recovery(
    native: Any, attack: str, message: str
) -> None:
    boundary, _, _, adapter = native
    boundary.deliver()
    name = (
        "delivery-intent.json"
        if attack == "intent-owner"
        else "delivery-complete.json"
        if attack == "complete-effect"
        else "delivery-effect.json"
    )
    path = boundary.root / name
    record = json.loads(path.read_bytes())
    if attack == "intent-owner":
        record["owner"] = str(boundary.root.parent / "foreign-owner")
    elif attack == "effect-intent":
        record["intentHash"] = "sha256:" + "0" * 64
    elif attack == "effect-attestation":
        record["result"]["attestationSha256"] = "0" * 64
    else:
        record["effectHash"] = "sha256:" + "0" * 64
    path.chmod(0o600)
    path.write_text(json.dumps(record))
    before = list(adapter.calls)
    with pytest.raises(ProofNativeError, match=message):
        boundary.recover_delivery()
    assert adapter.calls == before


def test_observation_records_explicit_external_or_owned_delivery_lineage(
    native: Any,
) -> None:
    boundary, resolve, target, _ = native
    mapping = resolve.project.timeline.mapping
    external = boundary.capture(target, mapping, "external")
    assert external["deliveryLineage"] == {
        "kind": "externally_supplied_target",
        "target": target,
    }
    boundary.deliver()
    owned = boundary.capture(target, mapping, "owned")
    assert owned["deliveryLineage"]["kind"] == "owned_verified_delivery"
    assert owned["deliveryLineage"]["completionHash"] == _file_hash(
        boundary.root / "delivery-complete.json"
    )


def test_failed_owned_delivery_cannot_be_captured_as_external_target(
    native: Any,
) -> None:
    boundary, resolve, target, adapter = native
    adapter.fail_on = "place_event"
    boundary.deliver()
    with pytest.raises(ProofNativeError, match="incomplete or failed delivery"):
        boundary.capture(target, resolve.project.timeline.mapping, "failed")
    assert not (boundary.root / "observations").exists()


@pytest.mark.parametrize(
    "attack", ["disabled", "missing-enabled", "missing-locked", "unknown-locked"]
)
def test_complete_track_state_refuses_unknown_or_disabled(
    native: Any, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    boundary, resolve, target, _ = native
    timeline = resolve.project.timeline
    if attack == "disabled":
        timeline.track_enabled = False
    elif attack == "unknown-locked":
        monkeypatch.setattr(timeline, "GetIsTrackLocked", lambda *_: 0)
    else:
        method = (
            "GetIsTrackEnabled" if attack == "missing-enabled" else "GetIsTrackLocked"
        )
        monkeypatch.setattr(timeline, method, None)
    with pytest.raises(
        ProofNativeError, match=r"track state|unavailable native interface"
    ):
        boundary.capture(target, timeline.mapping, "track")
    assert not (boundary.root / "observations").exists()


def test_fractional_public_delivery_refusal_precedes_adapter_creation(
    tmp_path: Path,
) -> None:
    _, probe = make_proof_case(tmp_path, rate="ntsc")
    build = PreparedProofBuildV2(
        tmp_path, authenticate=lambda *_: None, read_probe=probe
    )
    build.prepare_package()
    package = load_verified_package_v2(
        build.attestation_path, _file_hash(build.attestation_path)[7:]
    )
    factory_calls: list[str] = []

    def factory(_: Any) -> Any:
        factory_calls.append("called")
        raise AssertionError("fractional-rate public refusal must precede adapter")

    boundary = NativeProofBoundaryV2(
        FakeResolve(package),
        attestation_path=build.attestation_path,
        attestation_hash=_file_hash(build.attestation_path),
        proof_package_path=build.execution / "proof-package.json",
        proof_package_hash=_file_hash(build.execution / "proof-package.json"),
        evidence_root=tmp_path / "native",
        authenticate=lambda *_: None,
        authority=b"fake",
        code_hashes=proof_source_hashes_v2(),
        read_controls=fake_controls,
        adapter_factory=factory,
    )
    result = boundary.deliver()
    assert result["status"] == "stopped_safely"
    assert result["nativeRateQualified"] is False
    assert factory_calls == []
    assert not (boundary.root / "delivery-complete.json").exists()
    assert boundary.recover_delivery()["nativeEffects"] == 0
    with pytest.raises(ProofNativeError, match="read-only recovery"):
        boundary.deliver()
    assert factory_calls == []


@pytest.mark.parametrize(
    "stage", ["collision", "create_project", "place_event", "save_close_reopen"]
)
def test_failed_delivery_retains_effect_and_cannot_retry(
    native: Any, stage: str
) -> None:
    boundary, _, _, adapter = native
    adapter.fail_on = stage
    result = boundary.deliver()
    assert result["status"] in {"mutation_failed", "stopped_safely"}
    assert result["partialTargetRetained"] == (stage != "collision")
    before = list(adapter.calls)
    with pytest.raises(ProofNativeError):
        boundary.deliver()
    assert adapter.calls == before
    assert not (boundary.root / "delivery-complete.json").exists()


def test_capture_binds_adjacent_raw_and_derived_hashes(native: Any) -> None:
    boundary, resolve, target, _ = native
    receipt = boundary.capture(target, resolve.project.timeline.mapping, "before")
    assert receipt["adjacentConsistent"] is True
    assert receipt["evidenceLevel"] == "injected_execution_unqualified"
    assert receipt["rawHash"] == _file_hash(boundary.root / "observations/before.json")
    assert receipt["derivedAudioHash"] == _file_hash(
        boundary.root / "observations/before.audio.json"
    )
    with pytest.raises(FileExistsError):
        boundary.capture(target, resolve.project.timeline.mapping, "before")


@pytest.mark.parametrize(
    "attack", ["target", "adjacent", "mapping", "controls", "item", "rate"]
)
def test_capture_drift_refuses_without_evidence_or_render(
    native: Any, attack: str
) -> None:
    boundary, resolve, target, _ = native
    timeline = resolve.project.timeline
    if attack == "target":
        timeline.uid = "other"
    elif attack == "adjacent":
        timeline.drift_markers = True
    elif attack == "mapping":
        timeline.mapping["stale"] = dict(next(iter(timeline.mapping.values())))
    elif attack == "controls":
        boundary.read_controls = None
    elif attack == "item":
        next(iter(timeline.items.values()))[0].enabled = False
    else:
        timeline.timeline["frameRate"] = {
            "numerator": timeline.timeline["frameRate"]["numerator"] + 1,
            "denominator": 1,
        }
    with pytest.raises(ProofNativeError):
        boundary.capture(target, timeline.mapping, "bad")
    assert not (boundary.root / "observations").exists()
    assert resolve.project.calls == []


def render_args(native: Any) -> dict[str, Any]:
    boundary, resolve, target, _ = native
    mapping = resolve.project.timeline.mapping
    receipt = boundary.capture(target, mapping, "render_input")
    return {
        "target": target,
        "mapping": mapping,
        "observation_hash": receipt["rawHash"],
        "output": boundary.root / "renders/programme.wav",
        "render_format": "wav",
        "render_codec": "LinearPCM",
    }


def test_actual_render_complete_and_repeat_is_readonly(native: Any) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    result = boundary.render_complete_programme(**args)
    assert result["status"] == "complete"
    assert result["outputHash"] == _file_hash(args["output"])
    assert result["jobId"] == "actual-fake-job"
    calls = list(resolve.project.calls)
    assert boundary.render_complete_programme(**args) == result
    assert resolve.project.calls == calls == ["format", "settings", "add", "start"]


def test_pending_owned_render_only_polls_on_resume(native: Any) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    project = resolve.project
    project.pending = True
    assert boundary.render_complete_programme(**args)["status"] == "pending"
    calls = list(project.calls)
    project.status = "Complete"
    project.write_output()
    assert boundary.render_complete_programme(**args)["status"] == "complete"
    assert project.calls == calls


@pytest.mark.parametrize(
    "attack", ["target", "queue-id", "queue-settings", "poll-failed", "start-record"]
)
def test_pending_render_drift_refuses_without_restart(native: Any, attack: str) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    project = resolve.project
    project.pending = True
    assert boundary.render_complete_programme(**args)["status"] == "pending"
    calls = list(project.calls)
    if attack == "target":
        project.uid = "different-project"
    elif attack == "queue-id":
        project.queue[0]["JobId"] = "unowned-job"
    elif attack == "queue-settings":
        project.queue[0]["MarkOut"] -= 1
    elif attack == "poll-failed":
        project.status = "Failed"
    else:
        from issue190_case import write

        record = next(boundary.root.glob("render/*/start-returned.json"))
        record.chmod(0o600)
        write(record, {"jobId": "unowned-job", "returned": True})
    with pytest.raises(ProofNativeError):
        boundary.render_complete_programme(**args)
    assert project.calls == calls


def test_render_stale_observation_refuses_before_effect(native: Any) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    args["observation_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ProofNativeError, match="currentness"):
        boundary.render_complete_programme(**args)
    assert resolve.project.calls == []


@pytest.mark.parametrize(
    "attack",
    [
        "format",
        "settings",
        "job-id",
        "output",
        "job-settings",
        "unknown-control",
        "uncertain",
        "incomplete",
        "short",
        "mono",
        "truncated",
    ],
)
def test_render_refusals_preserve_intent_and_never_restart(
    native: Any, attack: str
) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    resolve.project.attack = attack
    with pytest.raises((ProofNativeError, RuntimeError)):
        boundary.render_complete_programme(**args)
    calls = list(resolve.project.calls)
    with pytest.raises(ProofNativeError):
        boundary.render_complete_programme(**args)
    assert resolve.project.calls == calls
    assert not list(boundary.root.glob("render/*/complete.json"))


def test_output_path_reservation_survives_changed_parameters(native: Any) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    resolve.project.attack = "format"
    with pytest.raises(ProofNativeError):
        boundary.render_complete_programme(**args)
    calls = list(resolve.project.calls)
    args["render_codec"] = "another"
    with pytest.raises(ProofNativeError, match="already reserved"):
        boundary.render_complete_programme(**args)
    assert resolve.project.calls == calls


def test_preexisting_output_and_queue_collision_never_mutate(native: Any) -> None:
    boundary, resolve, _, _ = native
    args = render_args(native)
    output = args["output"]
    output.parent.mkdir(parents=True)
    output.write_bytes(b"owned by other operation")
    with pytest.raises(ProofNativeError, match="collision"):
        boundary.render_complete_programme(**args)
    assert resolve.project.calls == []
    output.unlink()  # Only this test's newly created temporary artifact.
    resolve.project.queue.append(
        {
            "JobId": "other",
            "OutputFilename": output.name,
            "TargetDir": str(output.parent),
        }
    )
    with pytest.raises(ProofNativeError, match="already claimed"):
        boundary.render_complete_programme(**args)
    assert resolve.project.calls == []


def test_split_audio_source_keeps_two_verified_segments(native: Any) -> None:
    boundary, resolve, target, _ = native
    timeline = resolve.project.timeline
    audio_tracks = [
        items
        for (kind, _), items in timeline.items.items()
        if kind == "audio" and items
    ]
    if not audio_tracks:
        boundary.capture(target, timeline.mapping, "visual_only")
        return
    items = audio_tracks[0]
    first = items[0]
    second = copy.copy(first)
    second.uid += ":split"
    half = first.duration // 2
    second.start += half
    second.duration -= half
    second.source_start += half
    first.duration = half
    first.source_end = first.source_start + half - 1
    items.append(second)
    timeline.mapping[second.uid] = dict(timeline.mapping[first.uid])
    receipt = boundary.capture(target, timeline.mapping, "split")
    from vera_timeline_agent.roundtrip_v2_records import _operator_bytes, _parse

    derived = _parse(_operator_bytes(boundary.root / "observations/split.audio.json"))
    route = next(
        r
        for r in derived["routes"]
        if r["sourceId"] == timeline.mapping[first.uid]["sourceId"]
    )
    assert len(route["segments"]) == 2
    assert route["segments"][0]["sourceEnd"] == route["segments"][1]["sourceStart"]
    assert receipt["adjacentConsistent"]
