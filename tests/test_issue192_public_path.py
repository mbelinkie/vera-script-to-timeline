"""Combined genuine B1/B3/core/package path over injected sanitized fakes.

Native fractional creation must truthfully refuse. This never qualifies Studio,
real acoustic evidence, the real R16 specimen or a real provider.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from issue190_case import pin, write
from issue192_public_case import (
    AUTHORITY,
    FRAME,
    RATE,
    FakeAuthority,
    MaterializedCase,
    fresh_boundary,
    id_for,
    service_case,
)
from vera_timeline_agent.narration.models import identity_hash, sha256_bytes
from vera_timeline_agent.roundtrip_build import ProofBuildError
from vera_timeline_agent.roundtrip_v2_narration import (
    finalize_replacement_row_v2,
    prepare_replacement_row_v2,
)
from vera_timeline_agent.roundtrip_v2_native import NativeProofBoundaryV2
from vera_timeline_agent.roundtrip_v2_proof import ProofSessionV2
from vera_timeline_agent.roundtrip_v2_records import JsonObject, ProofNativeError
from vera_timeline_agent.roundtrip_v2_revised_build import (
    PreparedRevisedProofBuildV2,
    verify_revised_preflight_v2,
)

pytestmark = pytest.mark.slow


def target(resolve: Any) -> dict[str, str]:
    return {
        "projectUid": resolve.project.uid,
        "timelineUid": resolve.project.timeline.uid,
    }


def edit(resolve: Any, kind: str) -> None:
    timeline = resolve.project.timeline
    for (track_kind, _), items in list(timeline.items.items()):
        for item in list(items):
            if kind == "A" and track_kind == "video":
                if item.start == 311 and item.duration == 145:
                    item.duration += 113
                    item.source_end += 113
                elif item.start == 456 and item.duration == 136:
                    item.start += 113
                    item.duration -= 113
                    item.source_end -= 113
            elif kind == "B":
                if item.start == 952:
                    item.duration -= 25
                    item.source_end -= 25
                elif item.start == 1044:
                    item.start -= 25
            elif (
                kind == "C"
                and track_kind == "audio"
                and item.start == 0
                and item.duration == 200
            ):
                # Row1 also has Quiet source audio at0; only narration is lifted.
                event = timeline.mapping[item.uid]["eventId"]
                if resolve.project.kinds[event] != "narration":
                    continue
                left, right = copy.copy(item), copy.copy(item)
                left.uid += ":left"
                right.uid += ":right"
                left.duration = 121
                left.source_end = left.source_start + 120
                right.start = 127
                right.duration = 73
                right.source_start += 127
                items[items.index(item) : items.index(item) + 1] = [left, right]
                owner = timeline.mapping.pop(item.uid)
                timeline.mapping[left.uid] = copy.deepcopy(owner)
                timeline.mapping[right.uid] = copy.deepcopy(owner)
                assert timeline.mapping[right.uid]["eventId"] == event
    if kind == "B":
        timeline.timeline["durationFrames"] = 1082


def selected_files(
    root: Path,
    authority: FakeAuthority,
    case: MaterializedCase,
    session: ProofSessionV2,
    baseline: dict[str, Any],
    current: dict[str, Any],
    second: dict[str, Any],
    pristine_render: Path,
    edited_render: Path,
) -> dict[str, Any]:
    root.mkdir()
    before, after = (json.loads(packet["audioJson"]) for packet in (baseline, current))
    assert current["audioJson"] == second["audioJson"]
    for name, packet in (
        ("baseline", baseline),
        ("current-a", current),
        ("current-b", second),
    ):
        (root / f"{name}.json").write_bytes(packet["audioJson"].encode())
    raw = json.loads(baseline["rawJson"])
    sources: list[JsonObject] = []
    seen = set()
    for item in raw["items"]:
        if item["kind"] != "audio" or item["sourceId"] in seen:
            continue
        seen.add(item["sourceId"])
        path = root / f"source-{len(sources)}.wav"
        path.write_bytes(Path(item["sourcePath"]).read_bytes())
        import wave

        with wave.open(str(path), "rb") as stream:
            sources.append(
                {
                    "id": item["sourceId"],
                    "path": path.name,
                    "sha256": sha256_bytes(path.read_bytes()),
                    "channels": stream.getnchannels(),
                    "durationSamples": stream.getnframes(),
                }
            )
    primary = next(
        e["provenance"]["sourceId"]
        for e in case.manifest["events"]
        if e["kind"] == "narration" and e["provenance"]["blockId"] == id_for(10)
    )
    profile = {
        "schemaVersion": "issue-189-v2-selected-audio-profile/v1",
        "documentHash": session.document_hash,
        "blockId": id_for(10),
        "blockRevision": 1,
        "primarySourceId": primary,
        "extentFrames": 1107,
        "frameRate": RATE,
        "sources": sources,
        "selectedTokenIds": [id_for(1011)],
    }
    write(root / "profile.json", profile)
    phash = pin(root / "profile.json")["sha256"]
    row = next(
        b for b in case.document["activeDraft"]["blocks"] if b["id"] == id_for(10)
    )
    review = {
        "schemaVersion": "issue-189-v2-selected-review/v1",
        "method": "independent_source_listening_waveform/v1",
        "reviewerReference": "synthetic fake reviewer only",
        "reviewId": "fake-192-selected",
        "reviewRevision": 1,
        "documentHash": session.document_hash,
        "blockId": row["id"],
        "blockRevision": row["version"],
        "textHash": sha256_bytes(row["text"].encode()),
        "sourceHash": next(s["sha256"] for s in sources if s["id"] == primary),
        "supports": [],
    }
    for index, start, end in ((10, 119, 120), (11, 121, 126), (12, 127, 128)):
        token = row["tokens"][index]
        review["supports"].append(
            {
                "tokenId": token["id"],
                "quotedText": token["value"],
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
                "onsetSample": start * FRAME + 300,
                "endSample": end * FRAME + FRAME - 300,
            }
        )
    write(root / "review.json", review)
    authority.records[pin(root / "review.json")["sha256"]] = ("selected_review", review)
    for name, packet in (
        ("baseline", baseline),
        ("current-a", current),
        ("current-b", second),
    ):
        authority.receipt(
            root,
            f"{name}-receipt.json",
            "native_observation",
            {
                "target": before["target"],
                "observationHash": sha256_bytes(packet["audioJson"].encode()),
                "profileHash": phash,
            },
        )
    for name, packet, source in (
        ("pristine", baseline, pristine_render),
        ("edited", current, edited_render),
    ):
        (root / f"{name}.wav").write_bytes(source.read_bytes())
        authority.receipt(
            root,
            f"{name}-receipt.json",
            "native_render",
            {
                "target": before["target"],
                "observationHash": sha256_bytes(packet["audioJson"].encode()),
                "outputHash": pin(root / f"{name}.wav")["sha256"],
                "profileHash": phash,
                "settings": {
                    "startFrame": 0,
                    "endFrame": 1107,
                    "frameRate": RATE,
                    "sampleRate": 48000,
                    "channels": 2,
                    "codec": "pcm",
                },
            },
        )
    old_route = next(r for r in before["routes"] if r["sourceId"] == primary)
    new_route = next(r for r in after["routes"] if r["sourceId"] == primary)
    authority.receipt(
        root,
        "lift-receipt.json",
        "native_audio_lift",
        {
            "target": before["target"],
            "baselineHash": sha256_bytes(baseline["audioJson"].encode()),
            "currentHash": sha256_bytes(current["audioJson"].encode()),
            "primarySourceId": primary,
            "sourceHash": review["sourceHash"],
            "originalSegment": old_route["segments"][0],
            "retainedSegments": new_route["segments"],
            "sourceIntervalSamples": {"start": 121 * FRAME, "end": 127 * FRAME},
            "recordIntervalFrames": {"start": 121, "end": 127},
            "operation": "lift_audio_without_ripple",
        },
    )
    authority.receipt(
        root,
        "listening-receipt.json",
        "edited_mix_listening",
        {
            "documentHash": session.document_hash,
            "reviewHash": pin(root / "review.json")["sha256"],
            "editedRenderHash": pin(root / "edited.wav")["sha256"],
            "selectedTokenIds": [id_for(1011)],
            "neighborTokenIds": [id_for(1010), id_for(1012)],
        },
    )
    return profile


def test_public_b1_b3_core_fresh_package_and_truthful_native_refusal(
    tmp_path: Path,
) -> None:
    authority = FakeAuthority()
    baseline_case = MaterializedCase(tmp_path / "baseline", authority)
    original_pins = {
        p["path"]: p["sha256"]
        for p in baseline_case.request["executionInputs"].values()
    }
    isolated = []
    for kind in ("A", "B", "C"):
        boundary, resolve, adapter = baseline_case.native(tmp_path / f"native-{kind}")
        session = ProofSessionV2(
            tmp_path / f"session-{kind}",
            baseline=baseline_case.build,
            boundary=boundary,
            authenticate=authority,
            authority=AUTHORITY,
        )
        before = session.capture(
            target(resolve), resolve.project.timeline.mapping, f"before_{kind}"
        )
        if kind == "C":
            pristine = boundary.root / "renders/pristine.wav"
            result = boundary.render_complete_programme(
                target=target(resolve),
                mapping=resolve.project.timeline.mapping,
                observation_hash=sha256_bytes(before["rawJson"].encode()),
                output=pristine,
                render_format="wav",
                render_codec="LinearPCM",
            )
            assert result["status"] == "complete"
        edit(resolve, kind)
        current = session.capture(
            target(resolve), resolve.project.timeline.mapping, f"after_{kind}"
        )
        if kind == "C":
            edited = boundary.root / "renders/edited.wav"
            result = boundary.render_complete_programme(
                target=target(resolve),
                mapping=resolve.project.timeline.mapping,
                observation_hash=sha256_bytes(current["rawJson"].encode()),
                output=edited,
                render_format="wav",
                render_codec="LinearPCM",
            )
            assert result["status"] == "complete"
            second = session.capture(
                target(resolve), resolve.project.timeline.mapping, "adjacent_C"
            )
            selected = tmp_path / "selected"
            selected_files(
                selected,
                authority,
                baseline_case,
                session,
                before,
                current,
                second,
                pristine,
                edited,
            )
            value = session.evidence(
                before,
                current,
                omission_root=selected,
                profile_pin=pin(selected / "profile.json"),
                row_id=id_for(10),
            )
            assert value["omission"]["status"] == "verified"
            assert value["omission"]["tokenIds"] == [id_for(1011)]
            assert len(value["omission"]["channels"]) == 2
        else:
            value = session.evidence(before, current)
        isolated.append((session, value))
        assert adapter.calls == []  # Captures/render use existing injected fake target.
    owner = isolated[0][0]
    composed = owner.compose(isolated)
    inferred = owner._pure("infer", evidence=composed)
    d1_configured = 187
    prepared = []
    for n, duration in ((30, d1_configured), (51, 67)):
        binding = copy.deepcopy(
            next(
                b
                for b in baseline_case.dependencies["preparedMedia"]
                if b["requirementKey"] == f"192:prep:{n}"
            )
        )
        from fractions import Fraction

        seconds = Fraction(duration * 1001, 24000)
        binding["requestedRange"]["duration"] = {
            "numerator": seconds.numerator,
            "denominator": seconds.denominator,
        }
        prepared.append(binding)
    decision = {
        "schemaVersion": "issue-192-v2-inference-decision/v1",
        "inferenceHash": identity_hash(inferred),
        "outcome": "accept",
    }
    stage = owner.stage(composed, decision, prepared_media=prepared)
    authority.stage = stage
    service, provider = service_case(tmp_path / "cache", d1_configured)
    generation = tmp_path / "generation"
    args = {
        "request": stage["regeneration"],
        "document": stage["document"],
        "prior_dependencies": stage["dependencies"],
        "service": service,
        "authorization": b"explicit fake service authorization",
        "authenticate": authority,
    }
    receipt = prepare_replacement_row_v2(generation, **args)
    assert provider.calls == 1
    assert prepare_replacement_row_v2(generation, **args) == receipt
    assert provider.calls == 1
    boundaries = fresh_boundary(stage, service, receipt)
    finalized = finalize_replacement_row_v2(
        generation,
        **args,
        boundary_evidence=boundaries,
        review_artifact=b"fresh synthetic source-boundary review",
    )
    authority.handoff = finalized["handoff"]
    candidate = owner.proposal(
        composed, prepared_media=prepared, handoff=finalized["handoff"]
    )
    assert candidate["proposal"]["request"]["handoff"][
        "priorDependenciesHash"
    ] == identity_hash(stage["dependencies"])
    approved = {
        "schemaVersion": "issue-202-v2-decision/v1",
        "proposalHash": candidate["proposal"]["proposalHash"],
        "historyHash": identity_hash([]),
        "outcome": "accept",
    }
    actual = owner.decide(composed, candidate, approved, [])
    row_asset = service.cache.read(
        "assets", f"{id_for(10)}/{receipt['assetId']}", "asset.json"
    )
    assert row_asset is not None
    review_path = generation / "review.bin"
    review_path.write_bytes(b"fresh synthetic source-boundary review")
    fresh_files = {
        "audio": row_asset.path / "narration.wav",
        "timing": row_asset.path / "timing.json",
        "review": review_path,
        "receipt": generation / "generation.json",
    }
    rebuilt_case = MaterializedCase(
        tmp_path / "rebuilt",
        authority,
        prior=baseline_case,
        document=actual["document"],
        dependencies=actual["dependencies"],
        fresh_narration=fresh_files,
    )
    revised_root = tmp_path / "revised-consumer"
    revised_root.mkdir()
    revised_request: JsonObject = {
        "schemaVersion": "issue-192-v2-revised-build/v1",
        "lane": "synthetic_revision",
        "originalFiles": baseline_case.request["originalFiles"],
        **{
            key: rebuilt_case.request[key]
            for key in (
                "executionInputs",
                "sourcePins",
                "media",
                "preparations",
                "narrationReceipts",
                "authority",
            )
        },
    }
    write(revised_root / "revised-build-v2.json", revised_request)
    revised = PreparedRevisedProofBuildV2(
        revised_root,
        request_pin=pin(revised_root / "revised-build-v2.json"),
        session=owner,
        authenticate=authority,
        read_probe=rebuilt_case.probe,
    )
    package = owner.prepare_rebuild(candidate, revised)
    assert package["evidenceLevel"] == "local_prepared"
    manifest = rebuilt_case.manifest
    new_row = next(
        e
        for e in manifest["events"]
        if e["kind"] == "narration" and e["provenance"]["blockId"] == id_for(10)
    )
    d1_actual = (
        new_row["recordRange"]["endFrame"] - new_row["recordRange"]["startFrame"]
    )
    assert d1_actual == boundaries["audio"]["durationSamples"] // FRAME == 187
    assert manifest["timeline"]["durationFrames"] == 1082 + d1_actual - 200
    assert provider.calls == 1
    # Independently rebound attacks exercise the new public consumer. No original
    # input, accepted package, fixture or actual decision file is edited.
    for attack in ("original", "source", "decision-input", "old-timing", "media"):
        bad_root = tmp_path / f"revised-bad-{attack}"
        bad_root.mkdir()
        bad = copy.deepcopy(revised_request)
        if attack == "original":
            bad["originalFiles"]["dependencies"] = rebuilt_case.request[
                "executionInputs"
            ]["dependencies"]
        elif attack == "source":
            bad["sourcePins"]["python/vera_timeline_agent/roundtrip_v2_proof.py"] = (
                "sha256:" + "0" * 64
            )
        elif attack == "decision-input":
            bad["executionInputs"]["dependencies"] = baseline_case.request[
                "executionInputs"
            ]["dependencies"]
        elif attack == "old-timing":
            bad["narrationReceipts"][id_for(10)]["timing"] = baseline_case.request[
                "narrationReceipts"
            ][id_for(10)]["timing"]
        else:
            key = next(iter(bad["media"]))
            bad["media"][key]["sha256"] = "sha256:" + "0" * 64
        write(bad_root / "revised-build-v2.json", bad)
        with pytest.raises((ProofNativeError, ProofBuildError)):
            bad_build = PreparedRevisedProofBuildV2(
                bad_root,
                request_pin=pin(bad_root / "revised-build-v2.json"),
                session=owner,
                authenticate=authority,
                read_probe=rebuilt_case.probe,
            )
            bad_build.prepare_package()
        assert not (bad_root / "delivery-complete.json").exists()
    preflight = json.loads(revised.preflight_path.read_bytes())
    for attack in (
        "relabel",
        "stale-decision",
        "missing-original-pin",
        "wrong-package-input",
    ):
        bad = copy.deepcopy(preflight)
        if attack == "relabel":
            bad["lane"] = bad["revisionBinding"]["lane"] = "r16_private_revision"
        elif attack == "stale-decision":
            bad["revisionBinding"]["decision"]["sha256"] = "sha256:" + "0" * 64
        elif attack == "missing-original-pin":
            bad["verifiedFiles"].pop(
                bad["revisionBinding"]["originalFiles"]["document"]["path"]
            )
        else:
            bad["executionInputs"]["dependencies"] = baseline_case.request[
                "executionInputs"
            ]["dependencies"]
        with pytest.raises((ProofNativeError, ProofBuildError)):
            verify_revised_preflight_v2(
                bad, authenticate=authority, authority=AUTHORITY
            )
    refused_service, refused_provider = service_case(tmp_path / "refused-cache", 187)
    refused_provider.fail = True
    refused_args = {**args, "service": refused_service}
    with pytest.raises(ProofBuildError):
        prepare_replacement_row_v2(tmp_path / "refused-generation", **refused_args)
    assert refused_provider.calls == 1
    refused_provider.fail = False
    with pytest.raises(ProofBuildError, match="uncertain synthesis"):
        prepare_replacement_row_v2(
            tmp_path / "other-refused-generation", **refused_args
        )
    assert refused_provider.calls == 1
    fresh_boundary_port, fresh_resolve, fresh_adapter = rebuilt_case.native(
        tmp_path / "fresh-native", revised=revised
    )
    assert (
        fresh_boundary_port.binding["schemaVersion"]
        == "issue-192-v2-revised-native-binding/v1"
    )
    parameters = dict(
        resolve=fresh_resolve,
        attestation_path=revised.attestation_path,
        attestation_hash=pin(revised.attestation_path)["sha256"],
        proof_package_path=revised.execution / "proof-package.json",
        proof_package_hash=pin(revised.execution / "proof-package.json")["sha256"],
        evidence_root=tmp_path / "initial-rejects-revised",
        authenticate=authority,
        authority=AUTHORITY,
        code_hashes=preflight["sourceHashes"],
    )
    with pytest.raises(ProofNativeError):
        NativeProofBoundaryV2(**parameters)
    assert not (parameters["evidence_root"] / "binding.json").exists()
    # The new route rejects a wrong raw pin before constructing a binding.
    with pytest.raises(ProofNativeError):
        NativeProofBoundaryV2.from_revised_proof(
            **{**parameters, "evidence_root": tmp_path / "wrong-raw-pin"},
            revised_preflight_path=revised.preflight_path,
            revised_preflight_hash="sha256:" + "0" * 64,
        )
    assert not (tmp_path / "wrong-raw-pin/binding.json").exists()
    # Immutable bytes alone cannot prove that an external decision registry is
    # still current; the trusted port runs before every inherited operation.
    original_auth = fresh_boundary_port.authenticate

    def stale_authority(kind: str, raw: bytes, context: dict[str, Any]) -> None:
        if kind == "revised_native_lineage":
            raise ProofNativeError("external accepted-decision registry became stale")
        original_auth(kind, raw, context)

    fresh_boundary_port.authenticate = stale_authority
    operations: tuple[Callable[[], JsonObject], ...] = (
        lambda: fresh_boundary_port.deliver(),
        lambda: fresh_boundary_port.recover_delivery(),
        lambda: fresh_boundary_port.capture(
            target(fresh_resolve), fresh_resolve.project.timeline.mapping, "stale"
        ),
    )
    for operation in operations:
        with pytest.raises(ProofNativeError, match="registry became stale"):
            operation()
    assert fresh_adapter.calls == []
    assert not (fresh_boundary_port.root / "delivery-intent.json").exists()
    fresh_boundary_port.authenticate = original_auth
    delivery = owner.request_fresh_delivery(revised, fresh_boundary_port)
    assert delivery["status"] == "stopped_safely"
    assert delivery["nativeRateQualified"] is False
    assert fresh_adapter.calls == []
    assert owner.recover_delivery(fresh_boundary_port)["nativeEffects"] == 0
    with pytest.raises(ProofNativeError, match="read-only recovery"):
        owner.request_fresh_delivery(revised, fresh_boundary_port)
    assert fresh_adapter.calls == []
    for path, expected in original_pins.items():
        assert pin(Path(path))["sha256"] == expected
