"""Host-owned output observation, explicit revision and fresh-build bridge.

Only concrete product sessions supply evidence. JSON is a transport, never a
native receipt, source authenticator, operator approval or provider capability.
"""

from __future__ import annotations

import copy
import fcntl
import os
import pwd
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import qualification_output_v2 as output
from .qualification_output_controller_v2 import (
    HOST_STATE_ROOT,
    QualificationOutputController,
    _hash,
    _publish,
    _read,
    _require,
    _safe,
    load_output_session,
)
from .qualification_output_records_v2 import (
    LANE,
    OutputConsistencyError,
    _canonical,
    _digest,
    _integer,
    _json_hash,
    _ledger_head,
    _parse,
    _refusal,
    _shape,
)
from .roundtrip_v2_records import ROOT, _open_file, proof_source_hashes_v2

Json = dict[str, Any]
BRIDGE = ROOT / "packages/contracts/src/qualification-output-proof-cli.ts"
SESSION_SCHEMA = "qualification-output-proof-session/v1"
PREFLIGHT_SCHEMA = "qualification-output-revised-preflight/v1"


class _PairTrust:
    """Route each exact phase context to its own concrete product receipt vault."""

    def __init__(
        self,
        baseline: QualificationOutputController,
        edited: QualificationOutputController,
    ) -> None:
        self.baseline = baseline
        self.edited = edited

    def checked_now(self) -> datetime:
        return self.baseline.trust.checked_now()

    def authenticate(self, kind: str, receipt: bytes, expected: Json) -> None:
        context = expected.get("context")
        if context is None and isinstance(expected.get("geometry"), dict):
            context = expected["geometry"].get("context")
        if context is None or context == self.baseline.context:
            controller = self.baseline
        elif context == self.edited.context:
            controller = self.edited
        else:
            raise OutputConsistencyError("receipt context is outside this output pair")
        controller.trust.authenticate(kind, receipt, expected)


def _pin(path: Path) -> Json:
    raw = _read(path)
    _require(path.stat().st_nlink == 1, "aliased proof file refused")
    return {"path": str(path), "sha256": _hash(raw)}


def _pinned(pin: Json) -> bytes:
    _shape(pin, "path sha256", "proof file pin")
    _digest(pin["sha256"])
    _require(type(pin["path"]) is str, "proof path required")
    path = Path(pin["path"])
    raw = _read(path)
    _require(
        path.stat().st_nlink == 1 and _hash(raw) == pin["sha256"],
        "proof file bytes or identity changed",
    )
    return raw


def _retain(path: Path, raw: bytes) -> Json:
    if path.exists():
        _require(_read(path) == raw, "immutable proof output already differs")
    else:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _publish(path, raw)
    return _pin(path)


@_refusal
def load_terminal_output(
    controller: QualificationOutputController,
) -> output.TerminalOutput:
    """Reopen the complete controller-owned result without rerendering/decoding.

    Recomputing #214 authenticates commitment, reservation, geometry, fixed
    decode and terminal CAS ancestry against the entire current UID chain.
    """
    _require(
        type(controller) is QualificationOutputController,
        "concrete output controller required",
    )
    controller._environment_current()
    ledger = controller.journal.history()
    entries = [row for row in ledger if row["context"] == controller.context]
    _require(
        bool(entries) and entries[-1]["state"] == "compared_consistent",
        "complete consistent terminal output required",
    )
    terminal_entry = entries[-1]
    artifacts = controller.journal.artifacts
    vault = controller.vault.root
    comparison_raw = _read(artifacts / terminal_entry["resultRawSha256"])
    comparison = _parse(comparison_raw)
    commitment = _read(artifacts / comparison["commitmentRawSha256"])
    commitment_value = _parse(commitment)
    reservation = _read(artifacts / comparison["reservationRawSha256"])
    reservation_value = _parse(reservation)
    decode_raw = _read(artifacts / comparison["decodeRecordRawSha256"])
    decode = _parse(decode_raw)
    post_geometry = _read(vault / comparison["postGeometryRawSha256"])
    post_value = _parse(post_geometry)
    # These readers also reauthenticate each fixed native request/result chain.
    controller._native_result(controller._render_sequences()[-1])
    inputs = controller._pre_capture_inputs(validate_prediction=False)
    completed = output.CommittedOutput(
        inputs=inputs,
        commitment=commitment,
        commitment_receipt=_read(vault / commitment_value["commitmentReceiptSha256"]),
        prediction=_read(
            artifacts / commitment_value["predictionBytesSha256"], maximum=48_000_000
        ),
        reservation=reservation,
        reservation_receipt=_read(
            vault / reservation_value["reservationReceiptSha256"]
        ),
        post_geometry=post_geometry,
        post_geometry_receipt=_read(vault / post_value["receiptSha256"]),
        decode_record=decode_raw,
        decode_receipt=_read(vault / decode["decodeReceiptSha256"]),
        decoded_samples=_read(
            artifacts / decode["decodedSamplesSha256"], maximum=24_000_000
        ),
        # Reopen the immutable lineage already authenticated by the terminal
        # comparison. The live builder requires a still-reserved attempt and
        # cannot be called after that attempt has reached its terminal state.
        lineage=_read(artifacts / _hash(_canonical(comparison["renderLineage"]))),
        ledger=ledger[: terminal_entry["sequence"]],
    )
    result = output.TerminalOutput(
        completed,
        comparison_raw,
        _read(vault / comparison["comparisonReceiptSha256"]),
        ledger,
    )
    output._terminal_comparison(result, controller.trust)
    controller._environment_current()
    return result


class QualificationOutputProofV2:
    """One immutable observation pair and one serialized explicit decision."""

    def __init__(self, session_path: Path, expected_sha256: str) -> None:
        raw = _read(session_path)
        _require(_hash(raw) == expected_sha256, "proof session pin differs")
        session = _shape(
            _parse(raw),
            "schemaVersion lane baselineSession editedSession sourceHashes",
            "proof session",
        )
        _require(
            session["schemaVersion"] == SESSION_SCHEMA and session["lane"] == LANE,
            "new output proof session required",
        )
        self.session_path = session_path
        self.session_pin = _pin(session_path)
        self.root = session_path.parent
        self.session = session
        self.baseline = load_output_session(
            Path(session["baselineSession"]["path"]),
            session["baselineSession"]["sha256"],
        )
        self.edited = load_output_session(
            Path(session["editedSession"]["path"]), session["editedSession"]["sha256"]
        )
        self._current()

    def _current(self) -> None:
        _pinned(self.session_pin)
        _require(
            self.session["sourceHashes"] == proof_source_hashes_v2(),
            "output proof source graph changed",
        )
        for key in ("baselineSession", "editedSession"):
            _pinned(self.session[key])
        self.baseline._environment_current()
        self.edited._environment_current()
        left, right = self.baseline.context, self.edited.context
        _require(
            left["phase"] == "pristine"
            and right["phase"] == "edited"
            and left["target"] == right["target"]
            and left["caseId"] == right["caseId"],
            "same-target isolated pristine/edited pair required",
        )
        _require(
            all(
                left[k] == right[k]
                for k in left
                if k
                not in {
                    "phase",
                    "invocationId",
                    "binding",
                    "preflightSha256",
                    "preparationSha256",
                }
            ),
            "original document AND dependencies or pair input identities differ",
        )

    @contextmanager
    def _decision_lock(self) -> Iterator[None]:
        with os.fdopen(
            _open_file(self.root / "decision.lock", os.O_RDWR | os.O_CREAT, 0o600),
            "r+b",
        ) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _pure(self, request: Json) -> Json:
        self._current()
        request = {
            "schemaVersion": "qualification-output-pure-request/v1",
            "mode": "baseline",
            "evidence": None,
            "preparedMedia": [],
            "handoff": None,
            "inferenceDecision": None,
            "inferenceHistory": [],
            "candidate": None,
            "decision": None,
            "history": [],
            **copy.deepcopy(request),
        }
        request["document"] = _parse(self.baseline.blobs["executionDocumentSha256"])
        request["dependencies"] = _parse(
            self.baseline.blobs["executionDependenciesSha256"]
        )
        if request["mode"] == "decide":
            # The candidate binds its accepted inference decision and material;
            # the closed CLI refuses a second competing copy of that decision.
            request["inferenceDecision"] = None
            request["preparedMedia"] = request["candidate"]["request"]["preparedMedia"]
            request["handoff"] = request["candidate"]["request"]["handoff"]
        raw = _canonical(request)
        path = self.root / "pure" / _hash(raw) / "request.json"
        _retain(path, raw)
        node = shutil.which("node")
        _require(node is not None, "locked Node unavailable")
        assert node is not None
        result = subprocess.run(
            [node, str(BRIDGE), str(path)],
            capture_output=True,
            check=False,
            timeout=120,
        )
        _require(
            result.returncode == 0,
            "output proposal refused: "
            + result.stderr.decode("utf-8", errors="replace"),
        )
        envelope = _shape(
            _parse(result.stdout),
            "schemaVersion runtime inputHash result",
            "pure output result",
        )
        _require(
            envelope["schemaVersion"] == "qualification-output-pure-result/v1"
            and envelope["runtime"] == "v24.19.0"
            and envelope["inputHash"] == "sha256:" + _hash(raw),
            "pure result input/runtime/domain differs",
        )
        _require(type(envelope["result"]) is dict, "pure object result required")
        _retain(path.with_name("result.json"), result.stdout)
        self._current()
        return copy.deepcopy(envelope["result"])

    def evidence(self, case_id: str, *, omission_support: Json | None = None) -> Json:
        """Derive a new-domain transport only from reauthenticated native outputs."""
        self._current()
        _require(case_id in {"A", "B", "C"}, "supported isolated case required")
        pristine = load_terminal_output(self.baseline)
        edited = load_terminal_output(self.edited)
        before, after = pristine.output, edited.output
        pair = None
        equality = None
        if case_id == "A":
            _require(
                before.prediction == after.prediction
                and before.decoded_samples == after.decoded_samples,
                "picture-only edit must preserve identical predicted AND decoded audio",
            )
            equality = {
                "schemaVersion": "qualification-output-audio-equality/v1",
                "lane": LANE,
                "caseId": case_id,
                "pristinePredictionSha256": _hash(before.prediction),
                "editedPredictionSha256": _hash(after.prediction),
                "pristineDecodedSamplesSha256": _hash(before.decoded_samples),
                "editedDecodedSamplesSha256": _hash(after.decoded_samples),
                "predictionByteLength": len(before.prediction),
                "decodedSampleByteLength": len(before.decoded_samples),
                "sampleCount": len(before.prediction) // 16,
            }
        else:
            pair = output.compare_prediction_pair(
                pristine, edited, trust=_PairTrust(self.baseline, self.edited)
            )
        facts = self._pure({"mode": "baseline"})
        observation = {
            "schemaVersion": "qualification-output-observation/v1",
            "lane": LANE,
            "caseId": case_id,
            "pristineGeometryJson": before.inputs.geometry.decode(),
            "editedGeometryJson": after.inputs.geometry.decode(),
            "pristineInputBindingJson": before.inputs.input_binding.decode(),
            "editedInputBindingJson": after.inputs.input_binding.decode(),
            "pristineComparisonJson": pristine.comparison.decode(),
            "editedComparisonJson": edited.comparison.decode(),
            "pairJson": None if pair is None else _canonical(pair).decode(),
            "audioEquality": equality,
            "omissionSupport": None,
        }
        if case_id == "C":
            _require(
                omission_support is not None,
                "C requires independent source support and edited-mix listening",
            )
            assert omission_support is not None
            receipt = _pinned(omission_support)
            payload = _parse(receipt).get("payload")
            _require(type(payload) is dict, "authenticated omission support required")
            assert isinstance(payload, dict)
            self.baseline.vault.authenticate("output_omission_review", receipt, payload)
            _shape(
                payload,
                "proofSessionSha256 support sourceReviewReceipt",
                "omission review origin",
            )
            source_receipt = _pinned(payload["sourceReviewReceipt"])
            source_payload = _shape(
                _parse(source_receipt).get("payload"),
                "proofSessionSha256 sourceReview editedOutputSha256 "
                "reviewer reviewedAt",
                "source/listening review",
            )
            self.baseline.vault.authenticate(
                "output_omission_review", source_receipt, source_payload
            )
            _pinned(source_payload["sourceReview"])
            _require(
                source_payload["proofSessionSha256"] == self.session_pin["sha256"]
                and source_payload["editedOutputSha256"]
                == _parse(edited.comparison)["renderLineage"]["sourceOutputRawSha256"]
                and payload["support"]["reviewReceiptSha256"] == _hash(source_receipt),
                "source/listening review lineage differs",
            )
            _require(
                payload["proofSessionSha256"] == self.session_pin["sha256"],
                "omission review belongs to another proof",
            )
            observation["omissionSupport"] = payload["support"]
        else:
            _require(omission_support is None, "unexpected omission support")
        value = {
            "schemaVersion": "qualification-output-observation-batch/v1",
            "lane": LANE,
            "documentHash": facts["documentHash"],
            "dependenciesHash": facts["dependenciesHash"],
            "cases": [observation],
        }
        self._pure({"mode": "infer", "evidence": value})
        self._current()
        return value

    def observe(self, case_id: str, *, omission_support: Json | None = None) -> Path:
        evidence = self.evidence(case_id, omission_support=omission_support)
        pin = _retain(self.root / "evidence.json", _canonical(evidence))
        origin = {
            "proofSessionSha256": self.session_pin["sha256"],
            "evidenceSha256": pin["sha256"],
            "omissionSupport": omission_support,
        }
        receipt = self.baseline.vault._issue(
            "output_proposal_evidence",
            origin,
            (_pinned(pin), _pinned(self.session_pin)),
        )
        _retain(self.root / "evidence-receipt.json", receipt)
        return Path(pin["path"])

    def _evidence(self) -> Json:
        raw = _read(self.root / "evidence.json")
        receipt = _read(self.root / "evidence-receipt.json")
        origin = _parse(receipt).get("payload")
        _require(type(origin) is dict, "authenticated observation origin required")
        assert isinstance(origin, dict)
        self.baseline.vault.authenticate("output_proposal_evidence", receipt, origin)
        _shape(
            origin,
            "proofSessionSha256 evidenceSha256 omissionSupport",
            "evidence origin",
        )
        _require(
            origin["proofSessionSha256"] == self.session_pin["sha256"]
            and origin["evidenceSha256"] == _hash(raw),
            "observation origin differs",
        )
        evidence = _parse(raw)
        actual = self.evidence(
            evidence["cases"][0]["caseId"], omission_support=origin["omissionSupport"]
        )
        _require(
            _canonical(actual) == raw, "native output evidence changed before decision"
        )
        return evidence

    def infer(self) -> Json:
        return self._pure({"mode": "infer", "evidence": self._evidence()})

    def prepare_omission_review_plan(
        self, source_review: Path, destination: Path
    ) -> Path:
        """Bind a reviewed source-support artifact to this actual edited output.

        This proposal requires attended confirmation of independent source and
        edited-mix listening. It is never evidence merely because it is JSON.
        """
        self._current()
        pristine, edited = (
            load_terminal_output(self.baseline),
            load_terminal_output(self.edited),
        )
        pair = output.compare_prediction_pair(
            pristine, edited, trust=_PairTrust(self.baseline, self.edited)
        )
        facts = self._pure({"mode": "baseline"})
        document = _parse(self.baseline.blobs["executionDocumentSha256"])
        manifest = self.baseline.admission.manifest
        review_pin = _pin(source_review)
        review = _shape(
            _parse(_pinned(review_pin)),
            "schemaVersion method reviewerReference reviewId reviewRevision "
            "documentHash blockId blockRevision textHash sourceHash supports",
            "selected source review",
        )
        _require(
            review["schemaVersion"] == "issue-189-v2-selected-review/v1"
            and review["method"] == "independent_source_listening_waveform/v1"
            and review["documentHash"] == facts["documentHash"],
            "independent reviewed source artifact for this document required",
        )
        rows = [
            row
            for row in document["activeDraft"]["blocks"]
            if row["id"] == review["blockId"] and row["type"] == "narration"
        ]
        _require(len(rows) == 1, "unique reviewed narration row required")
        row = rows[0]
        _require(
            row["version"] == review["blockRevision"]
            and len(row["tokens"]) > 12
            and review["textHash"] == "sha256:" + _hash(row["text"].encode()),
            "reviewed row revision/text differs",
        )
        events = [
            event
            for event in manifest["events"]
            if event["kind"] == "narration"
            and event["provenance"]["blockId"] == row["id"]
        ]
        _require(len(events) == 1, "unique admitted narration source required")
        event = events[0]
        source_id = event["provenance"]["sourceId"]
        source = next(
            entry
            for entry in self.baseline.admission.source_entries
            if entry["sourceId"] == source_id
        )
        _require(
            review["sourceHash"] == "sha256:" + source["pcmFileSha256"],
            "review source is not the original admitted PCM",
        )
        before_geometry = _parse(pristine.output.inputs.geometry)["geometry"]
        after_geometry = _parse(edited.output.inputs.geometry)["geometry"]
        original = [
            item
            for item in before_geometry["items"]
            if item["eventId"] == event["eventId"]
        ]
        segments = sorted(
            [
                item
                for item in after_geometry["items"]
                if item["eventId"] == event["eventId"]
            ],
            key=lambda item: item["recordStart"],
        )
        _require(
            len(original) == 1 and len(segments) == 2,
            "actual two-segment narration lift required",
        )
        left, right = segments
        start_frame = left["recordStart"] + left["recordDuration"]
        end_frame = right["recordStart"]
        cut_start = (
            left["sourceStart"] + left["sourceDuration"] - source["nativeFrameOrigin"]
        ) * output.FRAME + source["pcmSampleOrigin"]
        cut_end = (
            right["sourceStart"] - source["nativeFrameOrigin"]
        ) * output.FRAME + source["pcmSampleOrigin"]
        _require(
            start_frame < end_frame
            and cut_start < cut_end
            and cut_end - cut_start == (end_frame - start_frame) * output.FRAME,
            "exact nonripple source/record cut required",
        )
        supports = review["supports"]
        _require(
            type(supports) is list and len(supports) == 3,
            "token10/11/12 independent source supports required",
        )
        intervals = []
        for support, token in zip(supports, row["tokens"][10:13], strict=True):
            _shape(
                support,
                "tokenId startOffset endOffset quotedText onsetSample endSample",
                "independent token support",
            )
            _require(
                (
                    support["tokenId"],
                    support["startOffset"],
                    support["endOffset"],
                    support["quotedText"],
                )
                == (
                    token["id"],
                    token["startOffset"],
                    token["endOffset"],
                    token["value"],
                ),
                "reviewed token identity/offset/quote differs",
            )
            start, end = (
                _integer(support["onsetSample"]),
                _integer(support["endSample"], 1),
            )
            _require(
                start < end <= source["durationSamples"],
                "reviewed source support bounds differ",
            )
            intervals.append({"startSample": start, "endSample": end})
        previous, selected, following = intervals
        _require(
            previous["endSample"]
            <= cut_start
            <= selected["startSample"]
            < selected["endSample"]
            <= cut_end
            <= following["startSample"],
            "cut clips a neighbour or incompletely removes token11",
        )
        support = {
            "schemaVersion": "qualification-output-omission-support/v1",
            "lane": LANE,
            "caseId": "C",
            "documentHash": facts["documentHash"],
            "dependenciesHash": facts["dependenciesHash"],
            "blockId": row["id"],
            "blockRevision": row["version"],
            "selectedTokenId": row["tokens"][11]["id"],
            "leftNeighborTokenId": row["tokens"][10]["id"],
            "rightNeighborTokenId": row["tokens"][12]["id"],
            "selectedSourceInterval": selected,
            "leftNeighborSourceInterval": previous,
            "rightNeighborSourceInterval": following,
            "recordIntervalFrames": {"startFrame": start_frame, "endFrame": end_frame},
            "audioSha256": source["pcmFileSha256"],
            "nativeFrameOrigin": source["nativeFrameOrigin"],
            "pcmSampleOrigin": source["pcmSampleOrigin"],
            "timingHash": event["provenance"]["timingMapHash"].removeprefix("sha256:"),
            "reviewArtifactSha256": review_pin["sha256"],
            "pristineGeometryRawSha256": _hash(pristine.output.inputs.geometry),
            "editedGeometryRawSha256": _hash(edited.output.inputs.geometry),
            "pristineComparisonRawSha256": _hash(pristine.comparison),
            "editedComparisonRawSha256": _hash(edited.comparison),
            "pairRawSha256": _hash(_canonical(pair)),
        }
        plan = {
            "schemaVersion": "qualification-output-omission-review-plan/v1",
            "lane": LANE,
            "authorityStatus": "review_only_not_authority",
            "proofSession": self.session_pin,
            "sourceReview": review_pin,
            "support": support,
            "editedOutputSha256": _parse(edited.comparison)["renderLineage"][
                "sourceOutputRawSha256"
            ],
            "requiredReview": (
                "Independently listen to original token10/11/12 and inspect "
                "their source supports; listen to the actual edited mix, "
                "confirm token11 alone is absent and both neighbours remain complete."
            ),
        }
        _retain(destination, _canonical(plan))
        return destination

    def _decision_claim_path(self, name: str) -> Path:
        _require(name in {"inference", "revision"}, "unsupported decision claim")
        identity = _json_hash(
            {
                "caseId": self.baseline.context["caseId"],
                "pristineLedgerHead": _ledger_head(self.baseline.journal.history()),
                "editedLedgerHead": _ledger_head(self.edited.journal.history()),
            }
        )
        return (
            self.baseline.journal.directory
            / "proof-decisions"
            / f"{name}-{identity}.json"
        )

    def _claim_decision(self, name: str, identity: str, raw: bytes) -> None:
        """One decision across proof directories on the complete native UID chain."""
        _require(identity.startswith("sha256:"), "canonical decision identity required")
        _digest(identity[7:])
        directory = self.baseline.journal.directory / "proof-decisions"
        directory.mkdir(mode=0o700, exist_ok=True)
        path = self._decision_claim_path(name)
        with self.baseline.journal._lock():
            _require(not path.exists(), "proposal already decided on this native chain")
            _publish(path, raw)

    def _check_decision_claim(self, name: str, identity: str, raw: bytes) -> None:
        _require(identity.startswith("sha256:"), "canonical decision identity required")
        _digest(identity[7:])
        _require(
            _read(self._decision_claim_path(name)) == raw,
            "retained native-chain decision differs",
        )

    def decide_inference(self, decision: Json) -> Json:
        """Accept/reject observed semantics before preparing replacement media."""
        with self._decision_lock():
            _require(
                not (self.root / "inference-decision.json").exists(),
                "inference already decided; retain the original decision",
            )
            evidence = self._evidence()
            inference = self._pure({"mode": "infer", "evidence": evidence})
            stage = self._pure(
                {"mode": "stage", "evidence": evidence, "inferenceDecision": decision}
            )
            raw = _canonical(decision)
            self._claim_decision("inference", inference["inferenceHash"], raw)
            _retain(self.root / "inference-decision.json", raw)
            _retain(self.root / "stage.json", _canonical(stage))
            payload = {
                "proofSessionSha256": self.session_pin["sha256"],
                "inferenceHash": inference["inferenceHash"],
                "decisionSha256": _hash(raw),
                "stageSha256": _hash(_canonical(stage)),
            }
            receipt = self.baseline.vault._issue(
                "output_proposal_decision",
                payload,
                (raw, _canonical(stage), _canonical(evidence)),
            )
            _retain(self.root / "inference-decision-receipt.json", receipt)
            return stage

    def _accepted_inference(self) -> Json:
        raw = _read(self.root / "inference-decision.json")
        decision = _parse(raw)
        _require(
            decision.get("outcome") == "accept",
            "inference was rejected or is undecided",
        )
        receipt = _read(self.root / "inference-decision-receipt.json")
        payload = _parse(receipt).get("payload")
        _require(type(payload) is dict, "sealed inference decision required")
        assert isinstance(payload, dict)
        self.baseline.vault.authenticate("output_proposal_decision", receipt, payload)
        self._check_decision_claim("inference", payload["inferenceHash"], raw)
        _require(
            payload["proofSessionSha256"] == self.session_pin["sha256"]
            and payload["decisionSha256"] == _hash(raw),
            "accepted decision lineage differs",
        )
        stage = self._pure(
            {
                "mode": "stage",
                "evidence": self._evidence(),
                "inferenceDecision": decision,
            }
        )
        _require(
            _canonical(stage) == _read(self.root / "stage.json")
            and payload["stageSha256"] == _hash(_canonical(stage)),
            "staged revision changed",
        )
        return decision

    def proposal(
        self, *, prepared_media: list[Json] | None = None, handoff: Json | None = None
    ) -> Json:
        _require(
            handoff is None,
            "manual replacement handoff refused; retain the accepted regeneration "
            "request until the concrete provider/cache/review finalizer is wired",
        )
        decision = self._accepted_inference()
        candidate = self._pure(
            {
                "mode": "proposal",
                "evidence": self._evidence(),
                "inferenceDecision": decision,
                "preparedMedia": prepared_media or [],
                "handoff": handoff,
            }
        )
        _retain(self.root / "proposal.json", _canonical(candidate))
        revision = candidate["revision"]
        _require(
            type(revision["comparisonText"]) is str,
            "readable revision comparison required",
        )
        _retain(self.root / "comparison.md", revision["comparisonText"].encode())
        return candidate

    def decide(self, decision: Json) -> Json:
        with self._decision_lock():
            _require(
                not (self.root / "revision-ledger.json").exists(),
                "revision already decided; no replay",
            )
            inference_decision = self._accepted_inference()
            candidate_raw = _read(self.root / "proposal.json")
            candidate = _parse(candidate_raw)
            result = self._pure(
                {
                    "mode": "decide",
                    "evidence": self._evidence(),
                    "inferenceDecision": inference_decision,
                    "candidate": candidate,
                    "decision": decision,
                }
            )
            raw = _canonical(decision)
            self._claim_decision("revision", candidate["proposalHash"], raw)
            result_raw = _canonical(result)
            _retain(self.root / "decision.json", raw)
            _retain(self.root / "result.json", result_raw)
            ledger = {
                "schemaVersion": "qualification-output-revision-ledger/v1",
                "lane": LANE,
                "proofSessionSha256": self.session_pin["sha256"],
                "evidenceSha256": _hash(_read(self.root / "evidence.json")),
                "inferenceDecisionSha256": _hash(
                    _read(self.root / "inference-decision.json")
                ),
                "candidateSha256": _hash(candidate_raw),
                "decisionSha256": _hash(raw),
                "resultSha256": _hash(result_raw),
                "outcome": result["outcome"],
                "history": result["history"],
            }
            ledger_raw = _canonical(ledger)
            _retain(self.root / "revision-ledger.json", ledger_raw)
            receipt = self.baseline.vault._issue(
                "output_proposal_decision",
                ledger,
                (raw, result_raw, candidate_raw, ledger_raw),
            )
            _retain(self.root / "decision-receipt.json", receipt)
            if result["outcome"] == "accept":
                _retain(
                    self.root / "revision-document.json", _canonical(result["document"])
                )
                _retain(
                    self.root / "revision-dependencies.json",
                    _canonical(result["dependencies"]),
                )
                _retain(
                    self.root / "revision-manifest.json",
                    candidate["revision"]["manifestJson"].encode(),
                )
                _retain(
                    self.root / "revision-report.json",
                    candidate["revision"]["reportJson"].encode(),
                )
            return result

    def accepted_revision(self) -> tuple[Json, Json]:
        """Recompute both decisions and all new canonical bytes before a build."""
        inference_decision = self._accepted_inference()
        ledger_raw = _read(self.root / "revision-ledger.json")
        ledger = _shape(
            _parse(ledger_raw),
            "schemaVersion lane proofSessionSha256 evidenceSha256 "
            "inferenceDecisionSha256 candidateSha256 decisionSha256 "
            "resultSha256 outcome history",
            "revision ledger",
        )
        _require(
            ledger["schemaVersion"] == "qualification-output-revision-ledger/v1"
            and ledger["lane"] == LANE
            and ledger["outcome"] == "accept"
            and ledger["proofSessionSha256"] == self.session_pin["sha256"],
            "accepted new-domain revision required",
        )
        self.baseline.vault.authenticate(
            "output_proposal_decision",
            _read(self.root / "decision-receipt.json"),
            ledger,
        )
        for field, name in (
            ("evidenceSha256", "evidence"),
            ("inferenceDecisionSha256", "inference-decision"),
            ("candidateSha256", "proposal"),
            ("decisionSha256", "decision"),
            ("resultSha256", "result"),
        ):
            _require(
                _hash(_read(self.root / f"{name}.json")) == ledger[field],
                "revision decision/input lineage changed",
            )
        candidate = _parse(_read(self.root / "proposal.json"))
        _require(
            candidate["request"]["handoff"] is None,
            "replacement handoff requires a concrete authenticated finalizer",
        )
        decision = _parse(_read(self.root / "decision.json"))
        self._check_decision_claim(
            "revision", candidate["proposalHash"], _canonical(decision)
        )
        result = self._pure(
            {
                "mode": "decide",
                "evidence": self._evidence(),
                "inferenceDecision": inference_decision,
                "candidate": candidate,
                "decision": decision,
            }
        )
        _require(
            _canonical(result) == _read(self.root / "result.json")
            and result["outcome"] == "accept"
            and result["history"] == ledger["history"],
            "accepted revision no longer recomputes",
        )
        for name, raw in (
            ("document", _canonical(result["document"])),
            ("dependencies", _canonical(result["dependencies"])),
            ("manifest", candidate["revision"]["manifestJson"].encode()),
            ("report", candidate["revision"]["reportJson"].encode()),
        ):
            _require(
                _read(self.root / f"revision-{name}.json") == raw,
                "revised canonical or compiled bytes changed",
            )
        return result, candidate

    def prepare_revised_preflight(self) -> Path:
        _, candidate = self.accepted_revision()
        original = self.baseline.admission
        pins = {
            "originalInputs": {
                "document": _pin(original.original_document_path),
                "dependencies": _pin(original.original_dependencies_path),
            },
            "baselineInputs": {
                "document": _pin(original.execution_document_path),
                "dependencies": _pin(original.execution_dependencies_path),
            },
            "executionInputs": {
                "document": _pin(self.root / "revision-document.json"),
                "dependencies": _pin(self.root / "revision-dependencies.json"),
            },
            "manifest": _pin(self.root / "revision-manifest.json"),
            "report": _pin(self.root / "revision-report.json"),
            "evidence": _pin(self.root / "evidence.json"),
            "proposal": _pin(self.root / "proposal.json"),
            "decision": _pin(self.root / "decision.json"),
            "result": _pin(self.root / "result.json"),
            "revisionLedger": _pin(self.root / "revision-ledger.json"),
            "acceptedDecisionReceipt": _pin(self.root / "decision-receipt.json"),
            "proofFiles": self._lineage_files(candidate),
        }
        required = [
            *pins["originalInputs"].values(),
            *pins["baselineInputs"].values(),
            *pins["executionInputs"].values(),
            *(
                value
                for key, value in pins.items()
                if key
                not in {
                    "originalInputs",
                    "baselineInputs",
                    "executionInputs",
                    "proofFiles",
                }
            ),
            *(pin for pin in pins["proofFiles"].values() if pin is not None),
            self.session_pin,
        ]
        payload = {
            "schemaVersion": PREFLIGHT_SCHEMA,
            "lane": LANE,
            "status": "prepared",
            "sourceHashes": proof_source_hashes_v2(),
            "proofSession": self.session_pin,
            **pins,
            "verifiedFiles": {pin["path"]: pin["sha256"] for pin in required},
        }
        receipt = self.baseline.vault._issue(
            "output_revised_preflight", payload, tuple(_pinned(pin) for pin in required)
        )
        receipt_pin = _retain(self.root / "revised-preflight-receipt.json", receipt)
        preflight = {**payload, "receipt": receipt_pin}
        path = self.root / "revised-preflight.json"
        _retain(path, _canonical(preflight))
        verify_revised_preflight_v2(path, _hash(_read(path)))
        return path

    def _lineage_files(self, candidate: Json) -> Json:
        inference_hash = candidate["inference"]["inferenceHash"]
        proposal_hash = candidate["proposalHash"]
        for digest in (inference_hash, proposal_hash):
            _require(digest.startswith("sha256:"), "new-domain proposal hash required")
            _digest(digest[7:])
        origin = _parse(_read(self.root / "evidence-receipt.json"))["payload"]
        omission = origin["omissionSupport"]
        source_receipt = source_review = None
        if omission is not None:
            outer = _parse(_pinned(omission))["payload"]
            source_receipt = outer["sourceReviewReceipt"]
            source_review = _parse(_pinned(source_receipt))["payload"]["sourceReview"]
        return {
            "evidenceReceipt": _pin(self.root / "evidence-receipt.json"),
            "inferenceDecision": _pin(self.root / "inference-decision.json"),
            "inferenceDecisionReceipt": _pin(
                self.root / "inference-decision-receipt.json"
            ),
            "stage": _pin(self.root / "stage.json"),
            "inferenceClaim": _pin(self._decision_claim_path("inference")),
            "revisionClaim": _pin(self._decision_claim_path("revision")),
            "omissionSupport": omission,
            "omissionSourceReviewReceipt": source_receipt,
            "omissionSourceReview": source_review,
        }


@_refusal
def verify_revised_preflight_v2(path: Path, expected_sha256: str) -> Json:
    """Static default-deny replacement; no legacy preflight or selected verifier."""
    raw = _pinned({"path": str(path), "sha256": expected_sha256})
    record = _shape(
        _parse(raw),
        "schemaVersion lane status sourceHashes proofSession originalInputs "
        "baselineInputs executionInputs manifest report evidence proposal "
        "decision result revisionLedger acceptedDecisionReceipt proofFiles "
        "verifiedFiles receipt",
        "output revised preflight",
    )
    _require(
        record["schemaVersion"] == PREFLIGHT_SCHEMA
        and record["lane"] == LANE
        and record["status"] == "prepared"
        and record["sourceHashes"] == proof_source_hashes_v2(),
        "current new-domain revised preflight required",
    )
    proof_pin = record["proofSession"]
    _pinned(proof_pin)
    proof = QualificationOutputProofV2(Path(proof_pin["path"]), proof_pin["sha256"])
    payload = {k: v for k, v in record.items() if k != "receipt"}
    proof.baseline.vault.authenticate(
        "output_revised_preflight", _pinned(record["receipt"]), payload
    )
    required = [proof_pin]
    for key in ("originalInputs", "baselineInputs", "executionInputs"):
        pair = _shape(record[key], "document dependencies", key)
        required.extend(pair.values())
    for key in (
        "manifest",
        "report",
        "evidence",
        "proposal",
        "decision",
        "result",
        "revisionLedger",
        "acceptedDecisionReceipt",
    ):
        required.append(record[key])
    proof_files = _shape(
        record["proofFiles"],
        "evidenceReceipt inferenceDecision inferenceDecisionReceipt stage "
        "inferenceClaim revisionClaim omissionSupport omissionSourceReviewReceipt "
        "omissionSourceReview",
        "proof file closure",
    )
    required.extend(pin for pin in proof_files.values() if pin is not None)
    _require(
        record["verifiedFiles"] == {pin["path"]: pin["sha256"] for pin in required},
        "revised verified-file inventory differs",
    )
    for pin in required:
        _pinned(pin)
    _require(
        record["originalInputs"]
        == {
            "document": _pin(proof.baseline.admission.original_document_path),
            "dependencies": _pin(proof.baseline.admission.original_dependencies_path),
        },
        "original document AND dependencies pins differ",
    )
    _require(
        record["baselineInputs"]
        == {
            "document": _pin(proof.baseline.admission.execution_document_path),
            "dependencies": _pin(proof.baseline.admission.execution_dependencies_path),
        },
        "baseline execution input pins differ",
    )
    result, candidate = proof.accepted_revision()
    _require(
        proof_files == proof._lineage_files(candidate),
        "early observation/decision/review file closure differs",
    )
    _require(
        _pinned(record["executionInputs"]["document"]) == _canonical(result["document"])
        and _pinned(record["executionInputs"]["dependencies"])
        == _canonical(result["dependencies"])
        and _pinned(record["manifest"])
        == candidate["revision"]["manifestJson"].encode()
        and _pinned(record["report"]) == candidate["revision"]["reportJson"].encode(),
        "newly compiled revised inputs differ",
    )
    baseline_build = _parse(_pinned(record["baselineInputs"]["dependencies"]))["build"]
    revised_build = result["dependencies"]["build"]
    _require(
        all(
            revised_build[key] != baseline_build[key]
            for key in ("buildId", "manifestId", "reportId")
        ),
        "fresh compiler build/manifest/report identities required",
    )
    return copy.deepcopy(record)


@_refusal
def verify_revised_rebuild_reservation_v2(
    record: Json,
    preflight_sha256: str,
    *,
    admission_path: Path,
    target: Json,
    case_id: str,
    invocation_id: str,
) -> None:
    """Reopened sessions cannot choose another target, invocation or admission."""
    proof_pin = record["proofSession"]
    proof = QualificationOutputProofV2(Path(proof_pin["path"]), proof_pin["sha256"])
    _require(
        case_id == proof.baseline.context["caseId"]
        and target["timelineUid"] != proof.baseline.context["target"]["timelineUid"],
        "rebuild requires the baseline case and a fresh target timeline UID",
    )
    reservation = (
        proof.baseline.journal.directory
        / "proof-rebuilds"
        / (record["revisionLedger"]["sha256"] + ".json")
    )
    _require(reservation.is_file(), "fresh rebuild reservation is absent")
    _require(
        _parse(_read(reservation))
        == {
            "proofSession": proof.session_pin,
            "preflightSha256": preflight_sha256,
            "outputRoot": str(admission_path.parent.parent),
            "target": target,
            "caseId": case_id,
            "invocationId": invocation_id,
            "admission": _pin(admission_path),
        },
        "fresh rebuild reservation differs from this session",
    )


def prepare_output_proof_v2(
    root: Path,
    *,
    baseline_session: Path,
    baseline_sha256: str,
    edited_session: Path,
    edited_sha256: str,
) -> Path:
    """Prepare a host proof from two actual sessions; no effects or authority."""
    _safe(root)
    _require(not root.exists(), "new proof root required")
    for path, digest in (
        (baseline_session, baseline_sha256),
        (edited_session, edited_sha256),
    ):
        _require(_pin(path)["sha256"] == digest, "output session raw pin differs")
        load_output_session(path, digest)
    root.mkdir(mode=0o700, parents=True)
    value = {
        "schemaVersion": SESSION_SCHEMA,
        "lane": LANE,
        "baselineSession": _pin(baseline_session),
        "editedSession": _pin(edited_session),
        "sourceHashes": proof_source_hashes_v2(),
    }
    path = root / "session.json"
    _publish(path, _canonical(value))
    QualificationOutputProofV2(path, _hash(_read(path)))
    return path


def _write_controller_session(
    root: Path, controller: QualificationOutputController
) -> Path:
    value = {
        "schemaVersion": "qualification-output-session/v1",
        "lane": LANE,
        "profile": controller.admission.profile,
        "admissionPath": str(controller.admission.admission_path),
        "admissionSha256": _hash(_read(controller.admission.admission_path)),
        "releaseRoot": str(controller.release_root),
        "context": controller.context,
        "hostJournalRoot": str(HOST_STATE_ROOT),
    }
    if controller.revised_preflight is not None:
        value["revisedPreflight"] = {
            "path": str(controller.revised_preflight[0]),
            "sha256": controller.revised_preflight[1],
        }
    path = root / "session.json"
    _publish(path, _canonical(value))
    controller.prepare_operator_plan(root / "operator-plan.json")
    return path


def prepare_edited_output_session(
    root: Path, *, baseline_session: Path, baseline_sha256: str
) -> Path:
    """Propose observation/render of the same edited target; no clip effects."""
    baseline = load_output_session(baseline_session, baseline_sha256)
    _require(baseline.context["phase"] == "pristine", "pristine baseline required")
    load_terminal_output(baseline)
    _safe(root)
    _require(not root.exists(), "new edited session root required")
    root.mkdir(mode=0o700, parents=True)
    controller = QualificationOutputController(
        HOST_STATE_ROOT,
        admission=baseline.admission,
        release_root=baseline.release_root,
        target=baseline.context["target"],
        case_id=baseline.context["caseId"],
        phase="edited",
        invocation_id=str(uuid.uuid4()),
    )
    return _write_controller_session(root, controller)


def prepare_revised_output_session(
    root: Path,
    *,
    proof_session: Path,
    proof_sha256: str,
    package_root: Path,
    preparation_paths: dict[str, Path],
    target: Json,
) -> Path:
    """Bind an accepted revision to a fresh verified package and a fresh target."""
    from .qualification_output_package_v2 import admit_qualification_revision_v2

    proof = QualificationOutputProofV2(proof_session, proof_sha256)
    preflight_path = proof.prepare_revised_preflight()
    preflight_sha256 = _hash(_read(preflight_path))
    _require(
        target["timelineUid"] != proof.baseline.context["target"]["timelineUid"],
        "fresh target timeline UID required",
    )
    _safe(root)
    _require(not root.exists(), "new revised session root required")
    root.mkdir(mode=0o700, parents=True)
    admission = admit_qualification_revision_v2(
        root / "admitted",
        package_root=package_root,
        preparation_paths=preparation_paths,
        revised_preflight_path=preflight_path,
        revised_preflight_sha256=preflight_sha256,
    )
    invocation_id = str(uuid.uuid4())
    # A new directory or target cannot reset this accepted revision's effects.
    reservation_root = proof.baseline.journal.directory / "proof-rebuilds"
    reservation_root.mkdir(mode=0o700, exist_ok=True)
    reservation = reservation_root / (
        _pin(proof.root / "revision-ledger.json")["sha256"] + ".json"
    )
    with proof.baseline.journal._lock():
        _require(
            not reservation.exists(),
            "accepted revision already reserved for a fresh build",
        )
        _publish(
            reservation,
            _canonical(
                {
                    "proofSession": proof.session_pin,
                    "preflightSha256": preflight_sha256,
                    "outputRoot": str(root),
                    "target": target,
                    "caseId": proof.baseline.context["caseId"],
                    "invocationId": invocation_id,
                    "admission": _pin(admission.admission_path),
                }
            ),
        )
    controller = QualificationOutputController.from_revised(
        HOST_STATE_ROOT,
        admission=admission,
        release_root=proof.baseline.release_root,
        target=target,
        case_id=proof.baseline.context["caseId"],
        invocation_id=invocation_id,
        revised_preflight_path=preflight_path,
        revised_preflight_sha256=preflight_sha256,
    )
    return _write_controller_session(root, controller)


def build_output_revision_package(
    proof_session: Path,
    proof_sha256: str,
    output_root: Path,
    *,
    media_paths: dict[str, Path],
    preparation_paths: dict[str, Path],
) -> Path:
    """Use the ordinary package writer on the freshly recompiled accepted inputs."""
    from .v2_package import build_v2_package

    proof = QualificationOutputProofV2(proof_session, proof_sha256)
    preflight = verify_revised_preflight_v2(
        proof.prepare_revised_preflight(),
        _hash(_read(proof.root / "revised-preflight.json")),
    )
    build_v2_package(
        Path(preflight["manifest"]["path"]),
        Path(preflight["report"]["path"]),
        Path(preflight["executionInputs"]["document"]["path"]),
        Path(preflight["executionInputs"]["dependencies"]["path"]),
        output_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    proof._current()
    return output_root


def issue_output_omission_review(plan_path: Path, output_path: Path) -> Path:
    """Human listening receipt. Agents must never answer the review prompt.

    Only the person who listened to both sources may confirm this step;
    filesystem access, waveform inspection and machine alignment are not review.
    """
    raw = _read(plan_path)
    plan = _shape(
        _parse(raw),
        "schemaVersion lane authorityStatus proofSession sourceReview support "
        "editedOutputSha256 requiredReview",
        "omission listening plan",
    )
    _require(
        plan["schemaVersion"] == "qualification-output-omission-review-plan/v1"
        and plan["lane"] == LANE
        and plan["authorityStatus"] == "review_only_not_authority",
        "review-only omission plan required",
    )
    pin = plan["proofSession"]
    proof = QualificationOutputProofV2(Path(pin["path"]), pin["sha256"])
    proof.prepare_omission_review_plan(Path(plan["sourceReview"]["path"]), plan_path)
    _require(_read(plan_path) == raw, "omission plan changed before review")
    _safe(output_path)
    _require(
        not output_path.exists()
        and output_path.parent.is_dir()
        and output_path.parent.stat().st_uid == os.getuid()
        and output_path.parent.stat().st_mode & 0o077 == 0,
        "new private review receipt destination required",
    )
    phrase = "REVIEWED " + _hash(raw)
    with open("/dev/tty", "r+", encoding="utf-8") as terminal:
        _require(terminal.isatty(), "attended source and edited-mix review required")
        terminal.write(plan["requiredReview"] + "\n")
        terminal.write(
            f"Exact review plan: {plan_path}\n"
            f"Only after completing that review, type {phrase}: "
        )
        terminal.flush()
        answer = terminal.readline(256).rstrip("\r\n")
    _require(answer == phrase, "source/listening review was not confirmed")
    proof.prepare_omission_review_plan(Path(plan["sourceReview"]["path"]), plan_path)
    source_payload = {
        "proofSessionSha256": pin["sha256"],
        "sourceReview": plan["sourceReview"],
        "editedOutputSha256": plan["editedOutputSha256"],
        "reviewer": pwd.getpwuid(os.getuid()).pw_name,
        "reviewedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    source_receipt = proof.baseline.vault._issue(
        "output_omission_review", source_payload, (_pinned(plan["sourceReview"]), raw)
    )
    source_pin = _retain(
        proof.root / "omission-source-review-receipt.json", source_receipt
    )
    support = {**plan["support"], "reviewReceiptSha256": _hash(source_receipt)}
    payload = {
        "proofSessionSha256": pin["sha256"],
        "support": support,
        "sourceReviewReceipt": source_pin,
    }
    receipt = proof.baseline.vault._issue(
        "output_omission_review", payload, (source_receipt, raw, _canonical(support))
    )
    _retain(output_path, receipt)
    return output_path
