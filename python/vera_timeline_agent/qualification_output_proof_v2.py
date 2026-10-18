"""Host-owned output observation, explicit revision and fresh-build bridge.

Only concrete product sessions supply evidence. JSON is a transport, never a
native receipt, source authenticator, operator approval or provider capability.
"""

from __future__ import annotations

import copy
import fcntl
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import qualification_output_v2 as output
from .qualification_output_controller_v2 import (
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
    _parse,
    _refusal,
    _shape,
)
from .roundtrip_v2_records import ROOT, _open_file, proof_source_hashes_v2

Json = dict[str, Any]
BRIDGE = ROOT / "packages/contracts/src/qualification-output-proof-cli.ts"
SESSION_SCHEMA = "qualification-output-proof-session/v1"
PREFLIGHT_SCHEMA = "qualification-output-revised-preflight/v1"


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
    post_geometry = _read(artifacts / comparison["postGeometryRawSha256"])
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
        lineage=controller._render_lineage(),
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
        request = copy.deepcopy(request)
        request["document"] = _parse(self.baseline.blobs["executionDocumentSha256"])
        request["dependencies"] = _parse(
            self.baseline.blobs["executionDependenciesSha256"]
        )
        raw = _canonical(request)
        path = self.root / "pure" / _hash(raw) / "request.json"
        _retain(path, raw)
        node = shutil.which("node")
        _require(node is not None, "locked Node unavailable")
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
