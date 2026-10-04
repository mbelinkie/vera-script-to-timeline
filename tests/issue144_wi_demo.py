"""Executable, entirely synthetic #144 walkthrough; no application connection.

Runs the actual host CLI in this process so the explicitly fake native world and
provider remain available across commands. Compiler/package/jobs/assembly/cache
and file WI paths are real. This cannot qualify a real Resolve build or provider.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from issue144_composition_fixture import decisions, setup
from issue144_wi_fixture import REGISTRY, GraphStudio, WireBoundary
from vera_timeline_agent.roundtrip_build import ROOT, PreparedBuild, load_operator_json
from vera_timeline_agent.roundtrip_driver import main as host_main
from vera_timeline_agent.roundtrip_wi import encoded, exclusive, file_hash

Json = dict[str, Any]


def run_demo(directory: Path) -> Json:
    directory = directory.absolute()
    if directory.exists() or any(p.is_symlink() for p in directory.parents):
        raise ValueError("a new, independently owned demo directory is required")
    directory.mkdir(parents=True)
    session, boundary, provider, service = setup(
        directory, boundary_factory=WireBoundary, initialize=False
    )
    assert isinstance(boundary, WireBoundary)
    REGISTRY[str(session.root)] = {
        "native_provider": boundary.native,
        "capture": boundary.capture,
        "omission_evidence": boundary.evidence,
        "narration_service": service,
    }
    helpers = (
        "issue144_wi_demo.py",
        "issue144_wi_fixture.py",
        "issue144_composition_fixture.py",
        "issue144_omission_fixture.py",
        "test_issue144_wi.py",
        "test_issue144_native_build.py",
        "test_issue144_prepared_build.py",
        "test_issue144_proof_session.py",
        "test_issue144_row_narration.py",
        "test_issue144_audio_evidence.py",
    )
    pins = {
        str(ROOT / "tests" / name): file_hash(ROOT / "tests" / name) for name in helpers
    }
    source = directory / "operator-boundary.py"
    exclusive(
        source,
        (
            "from issue144_wi_fixture import REGISTRY\n"
            f"FILE_PINS = {pins!r}\n"
            "def make_boundary(root):\n    return REGISTRY[str(root)]\n"
        ).encode(),
    )
    arguments = [
        "--proof-root",
        str(session.root),
        "--boundary-file",
        str(source),
        "--boundary-sha256",
        file_hash(source),
    ]
    actions: list[Json] = []

    def run(action: str, key: str | None = None, *, expected: str) -> Json:
        argv = [action, *arguments]
        if key is not None:
            argv += ["--decision-key", key]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = host_main(argv)
        result = json.loads(output.getvalue())
        record = {"argv": argv, "exitCode": code, "result": result}
        exclusive(
            directory / "commands" / f"{len(actions):02d}-{action}.json",
            encoded(record),
        )
        actions.append(record)
        assert result["status"] == expected, record
        assert code == (2 if expected == "refused" else 0), record
        return dict(result)

    original_inputs = dict(session.build.raw)
    run("build", expected="complete")
    run("bind-baseline", expected="bound")
    pointer = session.pointer.read_bytes()
    run("bind-omission-evidence", expected="prepared")

    # Negative real getter evidence: only the muted picture is shortened. Restore
    # only that explicit fake edit before attempting the required linked bundle.
    studio = next(iter(boundary.studios.values()))
    assert isinstance(studio, GraphStudio)
    manifest = load_operator_json(session.build.manifest_path)
    identity = load_operator_json(Path(boundary.requests[-1]["identityPath"]))
    narration = next(
        e
        for e in manifest["events"]
        if e["kind"] == "audio" and e["provenance"]["authoringId"] == boundary.row_id
    )
    uid = identity["occurrences"][narration["id"]]["itemUid"]
    primary = next(i for items in studio.items.values() for i in items if i.uid == uid)
    picture = primary.links[0]
    picture.duration -= 25
    refused = run("propose-omission", expected="refused")
    refused_request = boundary.requests[-1]
    basis = {k: v for k, v in refused_request.items() if k != "nonce"}
    from vera_timeline_agent.roundtrip_wi import digest

    refused_path = (
        session.root
        / "captures"
        / digest(encoded(basis))[7:]
        / refused_request["nonce"]
    )
    assert (refused_path / "refused.json").is_file()
    assert not (refused_path / "consumed.json").exists()
    picture.duration += 25
    assert session.pointer.read_bytes() == pointer and not provider.requests
    assert not (session.root / "decisions").exists()

    boundary.edit = True
    proposed = run("propose-omission", expected="proposed")
    report = load_operator_json(Path(proposed["reportPath"]))
    assert report["schemaVersion"] == "issue-144-composed-proposal/v1"
    rows = report["compositionInspection"]["result"]["visualReport"]["rows"]
    assert sorted(p["operation"] for p in rows) == ["move", "trim"]
    assert len(report["audio"]["omittedTokenIds"]) == 1
    decisions(session, proposed["reportHash"])
    accepted = run("decide-omission", expected="prepared_revision")
    key = accepted["decisionKey"]
    compared = run("compare", key, expected="compared")
    comparison = Path(compared["path"]).read_text()
    assert "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel" in comparison
    assert "Alpha Bravo Delta Echo Foxtrot Golf Hotel" in comparison
    assert "voiceover:" in comparison and "Echo Foxtrot" in comparison
    assert "Golf (use_source)" in comparison
    revised_doc = load_operator_json(
        Path(accepted["revisionRoot"]) / "script-document.json"
    )
    row = next(
        b for b in revised_doc["activeDraft"]["blocks"] if b["id"] == boundary.row_id
    )
    assert (
        revised_doc["activeDraft"]["blocks"][-1]
        == session.build.document["activeDraft"]["blocks"][-1]
    )
    generated = run("generate-omission", key, expected="finalized")
    assert len(provider.requests) == 1 and provider.requests[0].text == row["text"]
    revised = PreparedBuild(Path(accepted["revisionRoot"]))
    assert (
        revised.dependencies["narration"][1]
        == session.build.dependencies["narration"][1]
    )
    assert (
        revised.dependencies["narration"][0]["audioHash"]
        != session.build.dependencies["narration"][0]["audioHash"]
    )
    rebuilt = run("rebuild", key, expected="complete")
    assert session.pointer.read_bytes() == pointer
    promoted = run("promote", key, expected="promoted")
    new_pointer = session.pointer.read_bytes()
    assert new_pointer != pointer
    for action, expected_result in (
        ("decide-omission", accepted),
        ("generate-omission", generated),
        ("rebuild", rebuilt),
        ("promote", promoted),
    ):
        replay = run(
            action,
            None if action == "decide-omission" else key,
            expected=expected_result["status"],
        )
        assert replay == expected_result
    assert session.pointer.read_bytes() == new_pointer and len(provider.requests) == 1
    assert len(boundary.studios) == 2 and all(
        s.create_count == 1 for s in boundary.studios.values()
    )
    assert all(
        (session.root / name).read_bytes() == raw
        for name, raw in original_inputs.items()
    )
    assert list((session.root / "captures").glob("*/*/raw-0.json"))
    assert list((session.root / "captures").glob("*/*/response.json"))
    assert list((session.root / "wi-effects").glob("*/complete.json"))
    assert boundary.render_calls.count("queue") > 0
    result = {
        "schemaVersion": "issue-144-synthetic-wi-demo/v1",
        "status": "complete",
        "evidenceLevel": "synthetic_injected",
        "proofRoot": str(session.root),
        "comparisonPath": compared["path"],
        "comparisonHash": compared["sha256"],
        "pictureOnlyRefused": refused["status"] == "refused",
        "providerRequests": len(provider.requests),
        "nativeTargets": len(boundary.studios),
        "proofLinkCalls": sum(
            s.link_calls
            for s in boundary.studios.values()
            if isinstance(s, GraphStudio)
        ),
        "renderQueueCalls": boundary.render_calls.count("queue"),
        "decisionKey": key,
        "limitations": (
            "In-process fake native world, fixture supports/calibration/renderer/"
            "provider; no real qualification or human-finishing preservation."
        ),
    }
    exclusive(directory / "demo-result.json", encoded(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output_directory), sort_keys=True))
