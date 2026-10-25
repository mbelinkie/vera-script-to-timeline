"""Host-owned output observation, explicit revision and fresh-build bridge.

Only concrete product sessions supply evidence. JSON is a transport, never a
native receipt, source authenticator, operator approval or provider capability.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from . import qualification_output_v2 as output
from .narration.campaign import CAP_MICRO_USD, Ledger
from .narration.service import NarrationService
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
    _json_hash,
    _ledger_head,
    _parse,
    _refusal,
    _shape,
)
from .roundtrip_v2_audio import verify_measured_narration_evidence
from .roundtrip_v2_narration import (
    campaign_ledger,
    finalize_replacement_row_v2,
    guard_service,
    measure_replacement_row_v2,
    preflight_provider_call,
    prepare_replacement_row_v2,
)
from .roundtrip_v2_records import ROOT, _open_file, proof_source_hashes_v2

Json = dict[str, Any]
BRIDGE = ROOT / "packages/contracts/src/qualification-output-proof-cli.ts"
SESSION_SCHEMA = "qualification-output-proof-session/v1"
PREFLIGHT_SCHEMA = "qualification-output-revised-preflight/v1"
SUPPORT_SCHEMA = "qualification-output-omission-support/v2"


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
def _load_terminal_output_with_comparison(
    controller: QualificationOutputController,
) -> tuple[output.TerminalOutput, Json]:
    """Load a terminal and retain the comparison verified during this load.

    Recomputing #214 authenticates commitment, reservation, geometry, fixed
    decode and terminal CAS ancestry against the entire current UID chain.
    """
    _require(
        type(controller) is QualificationOutputController,
        "concrete output controller required",
    )
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
    comparison_result = output._terminal_comparison(result, controller.trust)
    return result, comparison_result


@_refusal
def load_terminal_output(
    controller: QualificationOutputController,
) -> output.TerminalOutput:
    """Reopen the result between exact pre/post environment checks."""
    _require(
        type(controller) is QualificationOutputController,
        "concrete output controller required",
    )
    controller._environment_current()
    result, _comparison = _load_terminal_output_with_comparison(controller)
    controller._environment_current()
    return result


def _boundary_hash(value: Json) -> str:
    """sha256CanonicalJson of the TypeScript compiler: sorted, indent 2, newline."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


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

    def evidence(self, case_id: str) -> Json:
        """Derive a new-domain transport only from reauthenticated native outputs.

        C carries machine-derived omission support (#215): the word is isolated
        by the measured narration evidence and the observed native cut; nobody
        enters a timestamp, token or review.
        """
        self._current()
        _require(case_id in {"A", "B", "C"}, "supported isolated case required")
        pristine, pristine_comparison = _load_terminal_output_with_comparison(
            self.baseline
        )
        edited, edited_comparison = _load_terminal_output_with_comparison(self.edited)
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
            pair = output._compare_prediction_pair_from_verified(
                pristine, edited, pristine_comparison, edited_comparison
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
        value = {
            "schemaVersion": "qualification-output-observation-batch/v1",
            "lane": LANE,
            "documentHash": facts["documentHash"],
            "dependenciesHash": facts["dependenciesHash"],
            "cases": [observation],
        }
        if case_id == "C":
            # Machine-derived by the TypeScript bridge from the measured
            # evidence and the observed native cut; `infer` below re-derives it.
            observation["omissionSupport"] = self.derive_omission_support(value)
        self._pure({"mode": "infer", "evidence": value})
        self._current()
        return value

    def derive_omission_support(self, evidence: Json) -> Json:
        """Support v2 for evidence whose omissionSupport is null (TS bridge)."""
        return self._pure({"mode": "derive_omission", "evidence": evidence})

    def observe(self, case_id: str) -> Path:
        evidence = self.evidence(case_id)
        pin = _retain(self.root / "evidence.json", _canonical(evidence))
        omission = None
        support = evidence["cases"][0]["omissionSupport"]
        if support is not None:
            omission = self._retain_omission_support(support)
        origin = {
            "proofSessionSha256": self.session_pin["sha256"],
            "evidenceSha256": pin["sha256"],
            "omissionSupport": omission,
        }
        receipt = self.baseline.vault._issue(
            "output_proposal_evidence",
            origin,
            (_pinned(pin), _pinned(self.session_pin)),
        )
        _retain(self.root / "evidence-receipt.json", receipt)
        return Path(pin["path"])

    def _omission_boundary(self, support: Json) -> Json:
        dependencies = _parse(self.baseline.blobs["executionDependenciesSha256"])
        rows = [
            row
            for row in dependencies.get("narrationBoundaryEvidence") or []
            if row["blockId"] == support["blockId"]
        ]
        _require(len(rows) == 1, "one measured boundary evidence row required")
        _require(
            _boundary_hash(rows[0]) == support["boundaryEvidenceHash"],
            "omission support names different boundary evidence",
        )
        return rows[0]  # type: ignore[no-any-return]

    def _retain_omission_support(self, support: Json) -> Json:
        """Retain the machine-derived record and its measured-evidence origin.

        The three retained files keep the preflight's closed omission pin
        triple: the sealed support receipt, the derived support record and
        the measured boundary evidence it was derived from. No reviewer exists.
        """
        support_raw = _canonical(support)
        boundary_raw = _canonical(self._omission_boundary(support))
        support_pin = _retain(self.root / "omission-support.json", support_raw)
        boundary_pin = _retain(
            self.root / "omission-measured-evidence.json", boundary_raw
        )
        payload = {
            "proofSessionSha256": self.session_pin["sha256"],
            "derivation": "machine_measured_audio_boundaries/v1",
            "support": support,
            "supportSha256": support_pin["sha256"],
            "boundaryEvidenceSha256": boundary_pin["sha256"],
        }
        receipt = self.baseline.vault._issue(
            "output_omission_review", payload, (support_raw, boundary_raw)
        )
        return _retain(self.root / "omission-support-receipt.json", receipt)

    def _verify_omission_support(self, pin: Json | None, support: Json | None) -> None:
        if pin is None or support is None:
            _require(pin is None and support is None, "omission support origin differs")
            return
        receipt = _pinned(pin)
        payload = _parse(receipt).get("payload")
        _require(type(payload) is dict, "authenticated omission support required")
        assert isinstance(payload, dict)
        self.baseline.vault.authenticate("output_omission_review", receipt, payload)
        _require(
            payload["proofSessionSha256"] == self.session_pin["sha256"]
            and payload["derivation"] == "machine_measured_audio_boundaries/v1"
            and payload["support"] == support
            and payload["supportSha256"] == _hash(_canonical(support))
            and _pin(self.root / "omission-support.json")["sha256"]
            == payload["supportSha256"]
            and _pin(self.root / "omission-measured-evidence.json")["sha256"]
            == payload["boundaryEvidenceSha256"]
            and _canonical(self._omission_boundary(support))
            == _pinned(_pin(self.root / "omission-measured-evidence.json")),
            "omission support lineage differs",
        )

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
        actual = self.evidence(evidence["cases"][0]["caseId"])
        _require(
            _canonical(actual) == raw, "native output evidence changed before decision"
        )
        self._verify_omission_support(
            origin["omissionSupport"], actual["cases"][0]["omissionSupport"]
        )
        return evidence

    def infer(self) -> Json:
        """Expose machine inference and any legal, still-undecided C boundaries."""
        return self._pure({"mode": "infer", "evidence": self._evidence()})

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
        """Seal explicit semantics and any C boundary choice before media work.

        The pure stage checks the choice against the inferred conflict before
        any decision claim is retained. The complete decision and resulting
        stage are sealed together and recomputed before regeneration/proposal.
        """
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

    def _accepted_inference_with_evidence(self, evidence: Json) -> Json:
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
                "evidence": evidence,
                "inferenceDecision": decision,
            }
        )
        _require(
            _canonical(stage) == _read(self.root / "stage.json")
            and payload["stageSha256"] == _hash(_canonical(stage)),
            "staged revision changed",
        )
        return decision

    def _accepted_inference(self) -> Json:
        return self._accepted_inference_with_evidence(self._evidence())

    def _stage(self) -> Json:
        """The staged revision; callers recompute it through _accepted_inference."""
        return _parse(_read(self.root / "stage.json"))

    def _regeneration_request(self, stage: Json) -> Json | None:
        regeneration = stage["regeneration"]
        if regeneration is None:
            return None
        _shape(
            regeneration,
            "schemaVersion lane policy blockId blockRevision text textHash "
            "revisedDocumentHash evidenceHash decisionHash",
            "regeneration request",
        )
        _require(
            regeneration["schemaVersion"]
            == "qualification-output-regeneration-request/v1"
            and regeneration["lane"] == LANE
            and regeneration["policy"] == "replace_whole_row",
            "whole-row regeneration request required",
        )
        return {
            "schemaVersion": "issue-189-v2-row-request/v1",
            **{
                k: v
                for k, v in regeneration.items()
                if k not in {"schemaVersion", "lane"}
            },
        }

    def _generation_authorization(
        self,
        request: Json,
        service: NarrationService,
        ledger: Ledger,
        cap_micro_usd: int,
    ) -> bytes:
        """Exact spend/privacy scope of this one regeneration, bound to the
        explicitly accepted inference, its staged request and the ledger."""
        return _canonical(
            {
                "schemaVersion": "issue-215-generation-authorization/v1",
                "lane": LANE,
                "proofSessionSha256": self.session_pin["sha256"],
                "inferenceDecisionSha256": _hash(
                    _read(self.root / "inference-decision.json")
                ),
                "stageSha256": _hash(_read(self.root / "stage.json")),
                "request": request,
                "dataPolicyAttestation": service.config.data_policy_attestation,
                "profileId": service.config.profile.profile_id,
                "maxCostUsd": service.config.max_cost_usd,
                "ledgerPath": str(ledger.path),
                "capMicroUsd": cap_micro_usd,
            }
        )

    def regenerate_row(
        self,
        *,
        service: NarrationService,
        ledger: Ledger | None = None,
        confirm_provider_call: bool,
        cap_micro_usd: int = CAP_MICRO_USD,
    ) -> Json | None:
        """Regenerate the entire accepted-omission row, measure it, hand it off.

        Runs only after an explicitly accepted inference (a rejection or an
        undecided inference refuses here, before any provider contact). The
        new text is synthesized as a whole row through the guarded service
        (cache hit: no call, no charge); the fresh asset is measured with #182
        and finalized into the RowHandoffV2 that ``proposal`` consumes. Returns
        None when the accepted proposal changes no narration text.

        The spend is recorded only in the approved campaign ledger
        (``ledger=None``); any other ledger path is refused outside tests, and a
        ``reserved``/``attempted`` ledger row for the same request without a
        cached result is never resent.

        Cost note: the paid replacement audio stays cached once synthesized.
        Rejecting the later revision proposal leaves that audio cached and the
        canonical text unchanged; only rejecting the *inference* (before this
        step) avoids synthesis.
        """
        ledger = campaign_ledger(ledger)
        with self._decision_lock():
            self._accepted_inference()
            stage = self._stage()
            request = self._regeneration_request(stage)
            if request is None:
                return None
            document, prior = stage["document"], stage["dependencies"]
            row = next(
                block
                for block in document["activeDraft"]["blocks"]
                if block["id"] == request["blockId"] and block["type"] == "narration"
            )
            root = self.root / "regeneration"
            authorization = self._generation_authorization(
                request, service, ledger, cap_micro_usd
            )
            retained: dict[str, bytes] = {}

            def authenticate(kind: str, raw: bytes, expected: Json) -> None:
                if kind == "synthesis_authorization":
                    _require(
                        raw == authorization
                        and expected["request"] == request
                        and expected["service"]["config"]["data_policy_attestation"]
                        == service.config.data_policy_attestation
                        and expected["service"]["cacheRoot"] == str(service.cache.root),
                        "synthesis authorization differs from the accepted request",
                    )
                elif kind == "replacement_boundaries":
                    _require(
                        "timing" in retained and expected["request"] == request,
                        "measured replacement boundaries need their measured timing",
                    )
                    verify_measured_narration_evidence(
                        expected["boundaryEvidence"],
                        timing=retained["timing"],
                        artifact=raw,
                        audio_sha256=expected["audio"]["audioHash"],
                    )
                else:
                    raise OutputConsistencyError("unsupported regeneration receipt")

            # Decide before any intent or reservation exists whether a real call
            # is needed and allowed; a cache hit proceeds without one.
            preflight_provider_call(
                service,
                row,
                ledger=ledger,
                confirm_provider_call=confirm_provider_call,
                cap_micro_usd=cap_micro_usd,
            )
            guarded = guard_service(
                service,
                ledger,
                confirm_provider_call=confirm_provider_call,
                cap_micro_usd=cap_micro_usd,
            )
            prepare_replacement_row_v2(
                root,
                request=request,
                document=document,
                prior_dependencies=prior,
                service=guarded,
                authorization=authorization,
                authenticate=authenticate,
            )
            evidence, artifact, timing = measure_replacement_row_v2(
                root, row=row, service=guarded, project_root=self.root
            )
            retained["timing"] = timing
            finalized = finalize_replacement_row_v2(
                root,
                request=request,
                document=document,
                prior_dependencies=prior,
                service=guarded,
                authorization=authorization,
                boundary_evidence=evidence,
                review_artifact=artifact,
                authenticate=authenticate,
            )
            handoff_raw = _read(root / "row-handoff.json")
            payload = {
                "proofSessionSha256": self.session_pin["sha256"],
                "kind": "whole-row-regeneration-handoff/v1",
                "stageSha256": _hash(_read(self.root / "stage.json")),
                "handoffSha256": _hash(handoff_raw),
                "previewSha256": _hash(_read(root / "replacement-preview.json")),
                "generationSha256": _hash(_read(root / "generation.json")),
                "measurementArtifactHash": "sha256:" + _hash(artifact),
            }
            receipt = self.baseline.vault._issue(
                "output_proposal_evidence",
                payload,
                (
                    handoff_raw,
                    _read(root / "replacement-preview.json"),
                    _read(root / "generation.json"),
                    artifact,
                ),
            )
            _retain(root / "handoff-receipt.json", receipt)
            return copy.deepcopy(finalized["handoff"])  # type: ignore[no-any-return]

    def _regenerated_handoff(self, stage: Json) -> Json | None:
        """The one handoff the verified finalizer produced for this stage.

        A caller cannot supply one: it must carry the proof vault's seal over
        the exact retained handoff/preview/generation bytes for this stage.
        """
        if stage["regeneration"] is None:
            return None
        root = self.root / "regeneration"
        _require(
            (root / "row-handoff.json").is_file()
            and (root / "handoff-receipt.json").is_file(),
            "accepted omission needs its whole-row regeneration (regenerate step) "
            "before a proposal",
        )
        raw = _read(root / "row-handoff.json")
        receipt = _read(root / "handoff-receipt.json")
        payload = _parse(receipt).get("payload")
        _require(type(payload) is dict, "sealed regeneration handoff required")
        assert isinstance(payload, dict)
        self.baseline.vault.authenticate("output_proposal_evidence", receipt, payload)
        handoff = _parse(raw)
        _require(
            payload.get("kind") == "whole-row-regeneration-handoff/v1"
            and payload["proofSessionSha256"] == self.session_pin["sha256"]
            and payload["stageSha256"] == _hash(_read(self.root / "stage.json"))
            and payload["handoffSha256"] == _hash(raw)
            and payload["previewSha256"]
            == _hash(_read(root / "replacement-preview.json"))
            and payload["generationSha256"] == _hash(_read(root / "generation.json"))
            and handoff["request"] == self._regeneration_request(stage),
            "regeneration handoff lineage differs",
        )
        return handoff

    def proposal(
        self, *, prepared_media: list[Json] | None = None, handoff: Json | None = None
    ) -> Json:
        _require(
            handoff is None,
            "manual replacement handoff refused; a handoff comes only from the "
            "verified whole-row regeneration step",
        )
        decision = self._accepted_inference()
        candidate = self._pure(
            {
                "mode": "proposal",
                "evidence": self._evidence(),
                "inferenceDecision": decision,
                "preparedMedia": prepared_media or [],
                "handoff": self._regenerated_handoff(self._stage()),
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
            _require(
                candidate["inferenceDecision"] == inference_decision
                and candidate["inferenceHistory"] == [],
                "proposal differs from the retained inference decision",
            )
            _require(
                candidate["request"]["handoff"]
                == self._regenerated_handoff(self._stage()),
                "candidate bypasses verified whole-row regeneration",
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
        evidence = self._evidence()
        inference_decision = self._accepted_inference_with_evidence(evidence)
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
            candidate["request"]["handoff"] == self._regenerated_handoff(self._stage()),
            "replacement handoff differs from the verified whole-row regeneration",
        )
        decision = _parse(_read(self.root / "decision.json"))
        self._check_decision_claim(
            "revision", candidate["proposalHash"], _canonical(decision)
        )
        _require(
            _canonical(evidence) == _read(self.root / "evidence.json"),
            "evidence changed during accepted revision",
        )
        result = self._pure(
            {
                "mode": "decide",
                "evidence": evidence,
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
        # Closed legacy names; the machine lineage fills them: sealed support
        # receipt, derived support record, measured boundary evidence.
        source_receipt = source_review = None
        if omission is not None:
            source_receipt = _pin(self.root / "omission-support.json")
            source_review = _pin(self.root / "omission-measured-evidence.json")
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
def _verify_revised_preflight_with_proof_v2(
    path: Path, expected_sha256: str
) -> tuple[Json, QualificationOutputProofV2]:
    """Return the validated proof for immediate same-operation reservation checks."""
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
    return copy.deepcopy(record), proof


@_refusal
def verify_revised_preflight_v2(path: Path, expected_sha256: str) -> Json:
    """Static default-deny replacement; no legacy preflight or selected verifier."""
    record, _proof = _verify_revised_preflight_with_proof_v2(path, expected_sha256)
    return record


def _verify_revised_rebuild_reservation_for_proof_v2(
    record: Json,
    preflight_sha256: str,
    *,
    admission_path: Path,
    target: Json,
    case_id: str,
    invocation_id: str,
    proof: QualificationOutputProofV2,
) -> None:
    """Check a reservation against the caller's freshly current proof object."""
    _require(
        record["proofSession"] == proof.session_pin,
        "preflight proof differs from the current proof session",
    )
    _check_revised_rebuild_reservation_v2(
        record,
        preflight_sha256,
        admission_path=admission_path,
        target=target,
        case_id=case_id,
        invocation_id=invocation_id,
        proof=proof,
    )


@_refusal
def _check_revised_rebuild_reservation_v2(
    record: Json,
    preflight_sha256: str,
    *,
    admission_path: Path,
    target: Json,
    case_id: str,
    invocation_id: str,
    proof: QualificationOutputProofV2,
) -> None:
    """Validate reservation fields after the proof's currentness was checked."""
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
    _verify_revised_rebuild_reservation_for_proof_v2(
        record,
        preflight_sha256,
        admission_path=admission_path,
        target=target,
        case_id=case_id,
        invocation_id=invocation_id,
        proof=proof,
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
    narration_evidence_paths: dict[str, dict[str, Path]] | None = None,
) -> Path:
    """Bind an accepted revision to a fresh verified package and a fresh target.

    Measured narration evidence files are tracked and hashed by the admission,
    whose currentness check (on every session load) refuses swapped bytes.
    """
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
        narration_evidence_paths=narration_evidence_paths,
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
