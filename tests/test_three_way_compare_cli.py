"""Offline-only boundary checks against a *real attested* synthetic v2 package."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent import three_way_compare_cli as cli
from vera_timeline_agent.build_compiler_bridge import BridgeOutput
from vera_timeline_agent.row_timeline_map import make_row_timeline_map
from vera_timeline_agent.v2_package import _compiler_hash
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import attest_package_v2


@pytest.fixture(scope="module")
def verified(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("three-way-verified")
    package_case = make_package_case(root / "inputs")
    package_case.build()
    output = root / "checked-output"
    output.mkdir()
    attestation = attest_package_v2(
        package_case.project_root, output / "v2-attestation.json"
    )
    package = load_verified_package_v2(
        attestation, hashlib.sha256(attestation.read_bytes()).hexdigest()
    )
    tracks = {track["id"]: track for track in package.view["tracks"]}
    observed = [
        {
            "eventId": event["id"],
            "resolveItemId": "synthetic-native-" + event["id"],
            "trackId": event["trackId"],
            "trackKind": tracks[event["trackId"]]["kind"],
            "trackIndex": tracks[event["trackId"]]["index"],
            "startFrame": event["recordRange"]["startFrame"],
            "durationFrames": event["recordRange"]["durationFrames"],
            "name": None,
            "mediaId": None,
            "sourceStartFrame": None,
            "sourceEndFrame": None,
        }
        for event in package.view["events"]
    ]
    saved = make_row_timeline_map(
        package.manifest,
        package.view,
        observed,
        project_name=package.attestation["projectName"],
        resolve_project_id="synthetic-original-project",
        timeline_name=package.attestation["timelineName"],
        timeline_id="synthetic-original-timeline",
        version=2,
    )
    observation = {
        "buildId": saved["buildId"],
        "documentId": saved["documentId"],
        "documentRevision": saved["documentRevision"],
        "timelineId": saved["timelineId"],
        "timelineName": saved["timelineName"],
        "differenceCount": 0,
        "cannotRead": ["grades", "effects", "media availability and source bytes"],
        "notCompared": [
            "timeline markers",
            "track settings",
            "clip inspector settings",
        ],
        "rows": [
            {
                "rowId": row["rowId"],
                "items": [
                    {
                        "eventId": item["eventId"],
                        "resolveItemId": item["resolveItemId"],
                        "status": ["unchanged"],
                    }
                    for item in row["items"]
                ],
            }
            for row in saved["rows"]
        ],
    }
    build = package.root / "Builds" / saved["buildId"]
    return {
        "output": output,
        "saved": saved,
        "observation": observation,
        "script": build / "script-document.json",
        "dependencies": build / "compiler-dependencies.json",
        "manifest": package.manifest,
        "report": json.loads((build / "build-report.json").read_bytes()),
    }


@pytest.fixture
def case(verified: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    output = tmp_path / "checked-output"
    output.mkdir()
    (output / "v2-attestation.json").write_bytes(
        (verified["output"] / "v2-attestation.json").read_bytes()
    )
    (output / "row-timeline-map.json").write_text(json.dumps(verified["saved"]))
    observation = tmp_path / "observation.json"
    observation.write_text(json.dumps(verified["observation"]))
    return {**verified, "output": output, "observation_path": observation}


def _bridge(case: dict[str, Any], *, tamper: str | None = None) -> cli.Bridge:
    manifest = copy.deepcopy(case["manifest"])
    report = copy.deepcopy(case["report"])
    if tamper == "blocked":
        report["status"] = "blocked"
    elif tamper == "manifest-id":
        manifest["id"] = "wrong-current-manifest"
    elif tamper == "document-id":
        report["document"]["documentId"] = "another-document"

    def invoke(kind: str, script: Path, dependencies: Path) -> BridgeOutput:
        assert kind == "compile"  # no media-needs/Resolve/build/save/delivery
        manifest_json = json.dumps(manifest)
        if tamper == "serialized":
            manifest_json = json.dumps({"other": True})
        return BridgeOutput(
            kind,
            hashlib.sha256(script.read_bytes()).hexdigest(),
            hashlib.sha256(dependencies.read_bytes()).hexdigest(),
            {
                "result": {
                    "ok": True,
                    "manifest": manifest,
                    "report": report,
                    "manifestJson": manifest_json,
                    "reportJson": json.dumps(report),
                }
            },
        )

    return invoke


def _run(case: dict[str, Any], *, bridge: cli.Bridge | None = None) -> dict[str, Any]:
    return cli.compare_offline(
        case["output"],
        case["observation_path"],
        case["script"],
        case["dependencies"],
        bridge=bridge or _bridge(case),
    )


def test_attested_synthetic_build_compares_without_resolve(
    case: dict[str, Any],
) -> None:
    first = _run(case)
    assert first == _run(case)
    assert first["baseline"]["timelineId"] == "synthetic-original-timeline"
    assert first["rows"]
    assert {row["state"] for row in first["rows"]} == {"unchanged"}
    assert first["observationCoverage"]["cannotRead"][:2] == ["grades", "effects"]


@pytest.mark.slow
def test_real_pinned_node_compile_is_offline_and_matches_attested_input(
    case: dict[str, Any],
    tmp_path: Path,
) -> None:
    # The packaged mock-media fixture is intentionally not freshly compilable;
    # use an independently checked ready prepared compiler fixture for current.
    fixtures = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
    source = json.loads((fixtures / "selected-clip-ntsc.input.golden.json").read_text())
    # Golden fixtures intentionally use illustrative hashes; close the authoring
    # identity for this test so the offline CLI can pin genuine source bytes.
    document = source["document"]
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    source["dependencies"]["document"]["contentHash"] = document["liveContentHash"]
    script = tmp_path / "current-script.json"
    dependencies = tmp_path / "current-dependencies.json"
    script.write_text(json.dumps(source["document"]))
    dependencies.write_text(json.dumps(source["dependencies"]))
    # Check the true Node compiler return contract without a Resolve connection.
    result = cli.compare_offline(
        case["output"],
        case["observation_path"],
        script,
        dependencies,
    )
    assert result["rows"]
    assert all(
        row["state"]
        in {"unchanged", "script_changed", "resolve_changed", "both_conflict"}
        for row in result["rows"]
    )


@pytest.mark.parametrize(
    "field", ["buildId", "timelineId", "documentId", "documentRevision", "timelineName"]
)
def test_wrong_observation_binding_refuses(case: dict[str, Any], field: str) -> None:
    report = json.loads(case["observation_path"].read_bytes())
    report[field] = -1 if field == "documentRevision" else "a-different-identity"
    case["observation_path"].write_text(json.dumps(report))
    with pytest.raises(ValueError, match="observation"):
        _run(case)


@pytest.mark.parametrize(
    "mutation", ["missing-item", "duplicate-item", "unready", "invalid-status"]
)
def test_incomplete_or_ambiguous_observation_refuses(
    case: dict[str, Any], mutation: str
) -> None:
    report = json.loads(case["observation_path"].read_bytes())
    first = report["rows"][0]["items"]
    if mutation == "missing-item":
        first.pop()
    elif mutation == "duplicate-item":
        first.append(copy.deepcopy(first[0]))
    elif mutation == "unready":
        report["status"] = "blocked"
    else:
        first[0]["status"] = ["made up"]
    case["observation_path"].write_text(json.dumps(report))
    with pytest.raises(ValueError, match=r"observation|omitted|duplicate|status"):
        _run(case)


@pytest.mark.parametrize(
    "tamper", ["blocked", "manifest-id", "document-id", "serialized"]
)
def test_refuses_unready_or_unpinned_compiler_output(
    case: dict[str, Any], tamper: str
) -> None:
    with pytest.raises((ValueError, KeyError, TypeError)):
        _run(case, bridge=_bridge(case, tamper=tamper))


def test_drifted_script_content_and_wrong_document_refuse(
    case: dict[str, Any], tmp_path: Path
) -> None:
    document = json.loads(case["script"].read_bytes())
    path = tmp_path / "changed-script.json"
    document["title"] = "Changed without recomputing its hash"
    path.write_text(json.dumps(document))
    case["script"] = path
    with pytest.raises(ValueError, match="content hash"):
        _run(case)
    document["id"] = "wrong-doc"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="different baseline document"):
        _run(case)


def test_missing_or_noncanonical_baseline_refuses(case: dict[str, Any]) -> None:
    saved_file = case["output"] / "row-timeline-map.json"
    original = saved_file.read_bytes()
    saved = json.loads(original)
    saved["rows"][0]["items"][0]["resolveItemId"] = "tampered"
    saved_file.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match=r"noncanonical|differs"):
        _run(case)
    saved_file.write_bytes(original)
    saved_file.unlink()
    with pytest.raises(ValueError, match="verified v2 row-timeline-map"):
        _run(case)


def test_symlink_observation_and_duplicate_json_keys_refuse(
    case: dict[str, Any], tmp_path: Path
) -> None:
    link = tmp_path / "report-link.json"
    link.symlink_to(case["observation_path"])
    case["observation_path"] = link
    with pytest.raises(ValueError, match="symbolic link"):
        _run(case)
    link.unlink()
    link.write_text('{"rows":[],"rows":[]}')
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        _run(case)


def test_example_command_is_byte_identical_and_has_explicit_caveat() -> None:
    command = [
        sys.executable,
        "-m",
        "vera_timeline_agent.three_way_compare_cli",
        "--example",
    ]
    one = subprocess.run(command, capture_output=True, check=True)
    two = subprocess.run(command, capture_output=True, check=True)
    assert one.stdout == two.stdout
    result = json.loads(one.stdout)
    assert [row["state"] for row in result["rows"]] == [
        "unchanged",
        "script_changed",
        "resolve_changed",
        "both_conflict",
    ]
    assert "allow-list is empty" in result["exampleOnly"]
    assert (
        one.stdout
        == (
            Path(__file__).parent / "data/three_way_compare/example.expected.json"
        ).read_bytes()
    )


def test_invalid_cli_args_or_missing_inputs_exit_two(
    case: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(
            [
                "--baseline-output",
                str(case["output"]),
                "--observation",
                str(case["observation_path"]),
                "--script",
                str(case["script"]),
                "--dependencies",
                str(case["dependencies"] / "missing.json"),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert "Cannot compare" in captured.err
    with pytest.raises(SystemExit) as error:
        cli.main(["--example", "--script", str(case["script"])])
    assert error.value.code == 2
