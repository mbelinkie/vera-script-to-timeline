"""Fixed zero-lag gates, precommit lineage and adversarial sibling refusals."""

from __future__ import annotations

import json
import struct
from array import array
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from test_issue214_prediction import (
    Case,
    case,
    change_items,
    committed,
    refresh_package_inputs,
)
from test_issue214_records import canonical, context, digest
from vera_timeline_agent import qualification_output_records_v2 as r
from vera_timeline_agent import qualification_output_v2 as q
from vera_timeline_agent.roundtrip_audio import _metrics as old_metrics


def independently_rendered(c: Case) -> list[int]:
    """Integer oracle from synthetic input intent, never prediction bytes."""
    geometry = json.loads(c.inputs.geometry)["geometry"]
    source = c.binding["sourceEntries"][0]
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    gain = (manifest["events"][0].get("audio") or {}).get("gainDb", 0)
    values = [0] * (geometry["extentFrames"] * q.FRAME * 2)
    for item in geometry["items"]:
        if item["kind"] != "audio":
            continue
        start = (item["sourceStart"] - source["nativeFrameOrigin"]) * q.FRAME + source[
            "pcmSampleOrigin"
        ]
        for offset in range(item["recordDuration"] * q.FRAME):
            for channel in range(2):
                source_channel = 0 if source["channels"] == 1 else channel
                value = c.samples[
                    (start + offset) * source["channels"] + source_channel
                ]
                values[(item["recordStart"] * q.FRAME + offset) * 2 + channel] += round(
                    value * 10 ** (gain / 20)
                )
    return values


def rendered(c: Case, values: list[int] | None = None) -> q.CommittedOutput:
    raw, commitment_receipt, prediction = committed(c)
    ctx = c.binding["context"]
    commit = json.loads(raw)
    ledger_event = {
        "context": ctx,
        "state": "committed",
        "commitmentRawSha256": digest(raw),
        "commitmentPayloadSha256": digest(
            canonical(
                {
                    key: value
                    for key, value in commit.items()
                    if key != "commitmentReceiptSha256"
                }
            )
        ),
        "predictionBytesSha256": digest(prediction),
        "reservationRawSha256": None,
        "resultRawSha256": None,
    }
    ledger = r._append_ledger([], ledger_event, r.EMPTY_HEAD)
    reservation = {
        "schemaVersion": "qualification-output-reservation/v1",
        "lane": r.LANE,
        "context": ctx,
        "commitmentRawSha256": digest(raw),
        "commitmentPayloadSha256": ledger_event["commitmentPayloadSha256"],
        "renderIntentSha256": digest(b"render intent"),
        "reservationId": "reservation-1",
        "reservedAt": "2026-10-15T01:00:00Z",
    }
    reservation_receipt = c.trust.seal("output_render_reservation", reservation)
    reservation["reservationReceiptSha256"] = digest(reservation_receipt)
    reservation_raw = canonical(reservation)
    ledger = r._append_ledger(
        ledger,
        {
            **ledger_event,
            "state": "reserved_by_render_intent",
            "reservationRawSha256": digest(reservation_raw),
        },
        r._ledger_head(ledger),
    )
    lineage = {
        "schemaVersion": "qualification-output-lineage/v1",
        "lane": r.LANE,
        "context": ctx,
        "commitmentRawSha256": digest(raw),
        "reservationRawSha256": digest(reservation_raw),
        "renderIntentSha256": reservation["renderIntentSha256"],
        "effectReceiptSha256": digest(b"effect"),
        "startReceiptSha256": digest(b"start"),
        "completionReceiptSha256": digest(b"completion"),
        "jobId": "native-job-1",
        "sourceOutputRawSha256": digest(b"same delivered MOV"),
    }
    snapshot = json.loads(c.inputs.geometry)
    snapshot["capturedAt"] = "2026-10-15T01:00:00Z"
    snapshot["capturePhase"] = "post_render"
    snapshot.pop("receiptSha256")
    post_receipt = c.trust.seal(
        "output_geometry_snapshot",
        {**snapshot, "inputBinding": c.binding, "renderLineage": lineage},
    )
    snapshot["receiptSha256"] = digest(post_receipt)
    data = independently_rendered(c) if values is None else values
    decoded = b"".join(struct.pack("<i", x) for x in data)
    decode = {
        "schemaVersion": "qualification-output-decode/v1",
        "lane": r.LANE,
        "context": ctx,
        "sourceOutputRawSha256": lineage["sourceOutputRawSha256"],
        "container": "mov",
        "videoCodec": "prores422",
        "audioCodec": "lpcm",
        "audioBitDepth": 24,
        "audioSampleRate": 48000,
        "audioChannels": 2,
        "sampleCount": commit["extentFrames"] * q.FRAME,
        "decodedSamplesSha256": digest(decoded),
        "decoderIdentitySha256": digest(b"decoder binary"),
        "decoderSourceGraphSha256": digest(b"decoder source"),
        "decoderCommandSha256": digest(b"exact decode command"),
    }
    decode_receipt = c.trust.seal(
        "output_decode_record", {**decode, "renderLineage": lineage}
    )
    decode["decodeReceiptSha256"] = digest(decode_receipt)
    return q.CommittedOutput(
        c.inputs,
        raw,
        commitment_receipt,
        prediction,
        reservation_raw,
        reservation_receipt,
        canonical(snapshot),
        post_receipt,
        canonical(decode),
        decode_receipt,
        decoded,
        canonical(lineage),
        ledger,
    )


def terminal(c: Case, output: q.CommittedOutput) -> q.TerminalOutput:
    result = q.compare_committed_output(output, trust=c.trust)
    receipt = c.trust.seal("output_residual_comparison", result)
    raw = canonical({**result, "comparisonReceiptSha256": digest(receipt)})
    ledger = q._terminal_append(output, raw, receipt, output.ledger, c.trust)
    return q.TerminalOutput(replace(output, ledger=ledger), raw, receipt, ledger)


def test_reserved_effect_finishes_after_commitment_expiry_and_appends() -> None:
    c = case()
    output = rendered(c)
    c.trust.now = datetime(2026, 10, 15, 3, tzinfo=UTC)
    post = json.loads(output.post_geometry)
    post.update(capturedAt="2026-10-15T03:00:00Z", expiresAt="2026-10-15T04:00:00Z")
    post.pop("receiptSha256")
    seal = c.trust.seal(
        "output_geometry_snapshot",
        {
            **post,
            "inputBinding": c.binding,
            "renderLineage": json.loads(output.lineage),
        },
    )
    post["receiptSha256"] = digest(seal)
    output = replace(output, post_geometry=canonical(post), post_geometry_receipt=seal)
    sealed = terminal(c, output)
    assert json.loads(sealed.comparison)["status"] == "compared_consistent"
    assert sealed.ledger[-1]["state"] == "compared_consistent"
    with pytest.raises(r.OutputConsistencyError, match="expiry"):
        q.verify_prediction_commitment(
            c.inputs,
            output.commitment,
            output.commitment_receipt,
            output.prediction,
            trust=c.trust,
        )
    bad = json.loads(output.reservation)
    bad["reservedAt"] = "2026-10-15T02:00:01Z"
    with pytest.raises(r.OutputConsistencyError, match="chronology"):
        q.compare_committed_output(
            replace(output, reservation=canonical(bad)), trust=c.trust
        )


def test_post_capture_requires_distinct_phase_and_completion_binding() -> None:
    c = case()
    output = rendered(c)
    with pytest.raises(r.OutputConsistencyError, match="replayed"):
        q.compare_committed_output(
            replace(
                output,
                post_geometry=c.inputs.geometry,
                post_geometry_receipt=c.inputs.geometry_receipt,
            ),
            trust=c.trust,
        )
    post = json.loads(output.post_geometry)
    post.pop("receiptSha256")
    seal = c.trust.seal("output_geometry_snapshot", {**post, "inputBinding": c.binding})
    post["receiptSha256"] = digest(seal)
    with pytest.raises(r.OutputConsistencyError, match="authentication"):
        q.compare_committed_output(
            replace(output, post_geometry=canonical(post), post_geometry_receipt=seal),
            trust=c.trust,
        )


@pytest.mark.parametrize("gain", [0, -18])
def test_complete_prepared_source_audio_full_and_quiet(gain: int) -> None:
    c = case(kind="source_audio", gain=gain, source_start=2, q_origin=48000)
    result = q.compare_committed_output(rendered(c), trust=c.trust)
    assert result["status"] == "compared_consistent"


def test_pair_requires_sealed_terminals_in_complete_current_ledgers() -> None:
    a, b = case(), case(phase="edited")
    a.trust.seals.update(b.trust.seals)
    b.trust = a.trust
    item = json.loads(b.inputs.geometry)["geometry"]["items"][0]
    change_items(b, [{**item, "recordDuration": 2, "sourceDuration": 2}])
    left, right = terminal(a, rendered(a)), terminal(b, rendered(b))
    result = q.compare_prediction_pair(left, right, trust=a.trust)
    assert result["geometryStability"] == result["controlStability"] == "not_claimed"
    assert result["pristineLedgerHeadSha256"] == r._ledger_head(left.ledger)
    with pytest.raises(r.OutputConsistencyError, match="absent"):
        q.compare_prediction_pair(
            replace(left, ledger=left.ledger[:-1]), right, trust=a.trust
        )


def test_complete_comparison_and_acyclic_terminal_cas() -> None:
    c = case()
    output = rendered(c)
    result = q.compare_committed_output(output, trust=c.trust)
    assert result["status"] == "compared_consistent"
    assert (
        result["metrics"]
        == [
            {
                "residualRms": 0.0,
                "maximumSliding20msResidualRms": 0.0,
                "consistent": True,
            }
        ]
        * 2
    )
    assert result["internalControls"] == "unverified"
    assert result["geometryStability"] == result["controlStability"] == "not_claimed"
    assert result["futureAuthority"] is False
    assert result["preGeometryRawSha256"] != result["postGeometryRawSha256"]
    assert "postTerminalLedgerSha256" not in result
    receipt = c.trust.seal("output_residual_comparison", result)
    result_raw = canonical({**result, "comparisonReceiptSha256": digest(receipt)})
    terminal = q._terminal_append(output, result_raw, receipt, output.ledger, c.trust)
    assert terminal[-1]["resultRawSha256"] == digest(result_raw)
    assert terminal[-1]["priorHeadSha256"] == result["priorLedgerHeadSha256"]
    with pytest.raises(r.OutputConsistencyError):
        q._terminal_append(output, result_raw, receipt, terminal, c.trust)
    with pytest.raises(r.OutputConsistencyError, match="already"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=terminal)
    changed = context(packageSha256="a" * 64)
    event = {
        key: terminal[-1][key]
        for key in (
            "context",
            "state",
            "commitmentRawSha256",
            "commitmentPayloadSha256",
            "predictionBytesSha256",
            "reservationRawSha256",
            "resultRawSha256",
        )
    }
    event.update(
        context=changed,
        state="committed",
        reservationRawSha256=None,
        resultRawSha256=None,
    )
    interleaved = r._append_ledger(output.ledger, event, r._ledger_head(output.ledger))
    with pytest.raises(r.OutputConsistencyError, match="CAS"):
        q._terminal_append(output, result_raw, receipt, interleaved, c.trust)


def test_fixed_metrics_differential_and_subthreshold_limit() -> None:
    count = 400 * q.FRAME
    signal = [array("d", [0.1]) * count for _ in range(2)]
    for peak, expected in ((0.18, True), (0.19, False)):
        output = [channel[:] for channel in signal]
        output[0][1000] += peak
        metrics = q._metrics(signal, output)
        assert metrics[0]["consistent"] is expected
        assert metrics[1]["consistent"] is True
        for channel in range(2):
            assert (
                metrics[channel]
                == old_metrics([signal[channel]], [output[channel]], [[1.0]])[0]
            )
    offset = [array("d", (x + 0.0005 for x in ch)) for ch in signal]
    assert all(not ch["consistent"] for ch in q._metrics(signal, offset))


@pytest.mark.parametrize("gain", [10 ** (-18 / 20), 10 ** (-3 / 20), 0.0])
def test_wrong_level_pan_law_and_silenced_output_refuse_without_fitting(
    gain: float,
) -> None:
    c = case()
    values = [round(x * gain) for x in independently_rendered(c)]
    result = q.compare_committed_output(rendered(c, values), trust=c.trust)
    assert result["status"] == "compared_refused"


def test_observable_one_sample_shift_refuses_at_zero_lag() -> None:
    c = case()
    values = independently_rendered(c)
    # An independently specified isolated 0.8FS impulse makes this shift observable.
    channel = array("d", [0.1]) * (6 * q.FRAME)
    channel[1500] = 0.8
    shifted = array("d", [0.0, *channel[:-1]])
    assert not q._metrics([channel, channel], [shifted, shifted])[0]["consistent"]
    result = q.compare_committed_output(
        rendered(c, [0, 0, *values[:-2]]), trust=c.trust
    )
    assert result["status"] == "compared_refused"


@pytest.mark.parametrize("silent_channel", [False, True])
def test_nonvacuity_requires_each_expected_channel(silent_channel: bool) -> None:
    c = case(silent=not silent_channel, channels=2, silent_right=silent_channel)
    with pytest.raises(r.OutputConsistencyError, match="vacuous"):
        q.compare_committed_output(rendered(c), trust=c.trust)


@pytest.mark.parametrize("code", [-(2**23), 2**23 - 1, 2**23])
def test_render_clipping_codes_refuse(code: int) -> None:
    c = case()
    values = independently_rendered(c)
    values[4] = code
    with pytest.raises(r.OutputConsistencyError, match="clipping"):
        q.compare_committed_output(rendered(c, values), trust=c.trust)


@pytest.mark.parametrize(
    "field,value",
    [
        ("container", "wav"),
        ("audioBitDepth", 16),
        ("audioChannels", True),
        ("sampleCount", 1),
        ("sourceOutputRawSha256", "f" * 64),
    ],
)
def test_decode_profile_and_output_mismatch_refuse(field: str, value: Any) -> None:
    c = case()
    output = rendered(c)
    decode = json.loads(output.decode_record)
    decode[field] = value
    with pytest.raises(r.OutputConsistencyError):
        q.compare_committed_output(
            replace(output, decode_record=canonical(decode)), trust=c.trust
        )


def test_forged_job_lineage_decode_and_receipt_refuse() -> None:
    c = case()
    output = rendered(c)
    lineage = json.loads(output.lineage)
    lineage["jobId"] = "other-job"
    with pytest.raises(r.OutputConsistencyError, match="authentication"):
        q.compare_committed_output(
            replace(output, lineage=canonical(lineage)), trust=c.trust
        )
    with pytest.raises(r.OutputConsistencyError):
        q.compare_committed_output(
            replace(output, decode_receipt=b"forged"), trust=c.trust
        )
    with pytest.raises(r.OutputConsistencyError):
        q.compare_committed_output(
            replace(output, decoded_samples=output.decoded_samples[:-4]), trust=c.trust
        )
    snapshot = json.loads(output.post_geometry)
    snapshot["geometry"]["tracks"][0]["name"] = "changed"
    with pytest.raises(r.OutputConsistencyError):
        q.compare_committed_output(
            replace(output, post_geometry=canonical(snapshot)), trust=c.trust
        )


def test_audio_changing_pair_and_video_only_identical_audio() -> None:
    pristine, edited = case(), case(phase="edited")
    edited.trust = pristine.trust
    # Capture using the same independent product trust store.
    edited.capture()
    sid = next(iter(edited.inputs.source_proofs))
    pristine.trust.seals.update(case().trust.seals)
    assert sid
    item = json.loads(edited.inputs.geometry)["geometry"]["items"][0]
    change_items(edited, [{**item, "recordDuration": 2, "sourceDuration": 2}])
    left, right = rendered(pristine), rendered(edited)
    result = q.compare_prediction_pair(
        terminal(pristine, left), terminal(edited, right), trust=pristine.trust
    )
    assert all(
        any(not row["consistent"] for row in metric)
        for metric in result["crossMetrics"].values()
    )
    unchanged = case(phase="edited")
    pristine.trust.seals.update(unchanged.trust.seals)
    unchanged.trust = pristine.trust
    same_audio = rendered(unchanged)
    assert (
        q.compare_committed_output(same_audio, trust=pristine.trust)["status"]
        == "compared_consistent"
    )
    with pytest.raises(r.OutputConsistencyError, match="indistinguishable"):
        q.compare_prediction_pair(
            terminal(pristine, left),
            terminal(unchanged, same_audio),
            trust=pristine.trust,
        )


def add_picture(c: Case) -> None:
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    visual_hash = digest(b"independent picture source")
    manifest["sources"].append({"id": "visual-source"})
    manifest["events"].append(
        {
            "eventId": "visual-event",
            "kind": "primary_visual",
            "trackId": "video-1",
            "recordRange": {"startFrame": 0, "endFrame": 2},
            "sourceRange": {"startFrame": 0, "endFrame": 2},
            "provenance": {
                "sourceId": "visual-source",
                "deliveredSourceHash": "sha256:" + visual_hash,
            },
        }
    )
    blobs = dict(c.inputs.blobs)
    blobs["manifestSha256"] = canonical(manifest)
    ctx = context(
        phase=c.binding["context"]["phase"],
        caseId="A",
        **{key: digest(raw) for key, raw in blobs.items()},
    )
    c.binding["context"] = ctx
    c.binding["delivery"].append(
        {
            "eventId": "visual-event",
            "kind": "primary_visual",
            "recordRange": {"startFrame": 0, "durationFrames": 2},
            "sourceRange": {"startFrame": 0, "durationFrames": 2},
        }
    )
    c.binding["nativeSources"].append(
        {"sourceId": "visual-source", "nativeSourceSha256": visual_hash}
    )
    c.binding["tracks"].append(
        {
            "trackId": "video-1",
            "kind": "video",
            "index": 1,
            "name": "Picture",
            "enabled": True,
            "locked": False,
        }
    )
    snapshot = json.loads(c.inputs.geometry)
    geometry = snapshot["geometry"]
    visual = {
        **geometry["items"][0],
        "itemUid": "visual-item",
        "eventId": "visual-event",
        "sourceId": "visual-source",
        "mediaUid": "visual-media",
        "kind": "video",
        "trackId": "video-1",
        "recordStart": 4 if ctx["phase"] == "edited" else 0,
        "recordDuration": 2,
        "sourceStart": 0,
        "sourceDuration": 2,
        "sourceMappingSha256": visual_hash,
    }
    geometry.update(context=ctx, tracks=c.binding["tracks"])
    c.inputs = replace(c.inputs, blobs=blobs, geometry=canonical(snapshot))
    change_items(
        c,
        sorted(
            [geometry["items"][0], visual],
            key=lambda row: (row["recordStart"], row["itemUid"]),
        ),
    )
    refresh_package_inputs(c)


def test_case_a_picture_move_keeps_identical_per_output_audio_consistent() -> None:
    outputs: list[q.CommittedOutput] = []
    cases = [case(), case(phase="edited")]
    trust = cases[0].trust
    for c in cases:
        trust.seals.update(c.trust.seals)
        c.trust = trust
        add_picture(c)
        outputs.append(rendered(c))
    # A keeps identical audio; it needs no pair-discrimination claim.
    assert outputs[0].prediction == outputs[1].prediction
    assert outputs[0].inputs.geometry != outputs[1].inputs.geometry
    assert all(
        q.compare_committed_output(output, trust=trust)["status"]
        == "compared_consistent"
        for output in outputs
    )


def test_legacy_strict_consumers_refuse_sibling_records(tmp_path: Any) -> None:
    from vera_timeline_agent.roundtrip_build import ProofBuildError
    from vera_timeline_agent.roundtrip_v2_audio import (
        _observation,
        verify_selected_omission_v2,
    )
    from vera_timeline_agent.roundtrip_v2_native import _controls
    from vera_timeline_agent.roundtrip_v2_records import ProofNativeError
    from vera_timeline_agent.roundtrip_v2_revised_build import (
        verify_revised_preflight_v2,
    )

    c = case()
    commitment, _, _ = committed(c)
    value = json.loads(commitment)
    with pytest.raises(ProofNativeError):
        _controls(value, set())
    with pytest.raises(ProofBuildError):
        _observation(value, {}, 6, c.binding["context"]["target"])
    with pytest.raises(ProofNativeError):
        verify_revised_preflight_v2(
            value, authenticate=c.trust.authenticate, authority=b"unused"
        )
    from test_issue191_audio import case as strict_case

    args = strict_case(tmp_path)
    assert verify_selected_omission_v2(tmp_path, **args)["status"] == "verified"
    old = {
        name: (tmp_path / name).read_bytes()
        for name in ("baseline.json", "baseline-receipt.json", "pristine-receipt.json")
    }
    for raw in old.values():
        with pytest.raises(r.OutputConsistencyError):
            q.create_prediction(
                replace(c.inputs, geometry=raw), trust=c.trust, ledger=[]
            )
        output = rendered(c)
        with pytest.raises(r.OutputConsistencyError):
            q.compare_committed_output(
                replace(output, decode_record=raw), trust=c.trust
            )
    # All prior document/profile/source/review gates pass; the old consumer
    # actually opens the replacement observation and rejects its sibling shape.
    (tmp_path / "baseline.json").write_bytes(commitment)
    args["baseline_hash"] = "sha256:" + digest(commitment)
    report = verify_selected_omission_v2(tmp_path, **args)
    assert report["status"] == "refused" and "observation shape" in report["reason"]
    assert report["inputHashes"]["baseline.json"] == args["baseline_hash"]


@pytest.mark.parametrize("field", ["recordRange", "sourceRange"])
def test_resealed_video_delivery_shift_refuses_authoritative_manifest(
    field: str,
) -> None:
    c = case()
    add_picture(c)
    assert q.create_prediction(c.inputs, trust=c.trust, ledger=[]).pcm
    blobs = dict(c.inputs.blobs)
    view = json.loads(blobs["packageSha256"])
    row = next(row for row in view["events"] if row["kind"] == "primary_visual")
    row[field]["startFrame"] = 1
    next(row for row in c.binding["delivery"] if row["kind"] == "primary_visual")[
        field
    ]["startFrame"] = 1
    blobs["packageSha256"] = canonical(view)
    ctx = context(
        phase=c.binding["context"]["phase"],
        caseId=c.binding["context"]["caseId"],
        **{key: digest(raw) for key, raw in blobs.items()},
    )
    c.binding["context"] = ctx
    snapshot = json.loads(c.inputs.geometry)
    snapshot["geometry"]["context"] = ctx
    c.inputs = replace(c.inputs, blobs=blobs, geometry=canonical(snapshot))
    c.capture()
    with pytest.raises(r.OutputConsistencyError, match="derivation"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=[])


@pytest.mark.slow
def test_full_programme_bound_complete_prediction_and_comparison() -> None:
    c = case(frames=1498)
    output = rendered(c)
    assert len(output.prediction) == 1498 * q.FRAME * 16 <= 48_000_000
    assert (
        q.compare_committed_output(output, trust=c.trust)["status"]
        == "compared_consistent"
    )
