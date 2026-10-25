"""Host-only durable attempt ownership for the bounded output sibling.

Requests never supply history or choose an authenticator. The journal is keyed
by immutable target UIDs/case/phase and survives changed bindings/invocations.
This module cannot connect to Resolve or grant operator authority.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import hmac
import os
import platform
import pwd
import shutil
import stat
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import qualification_output_v2 as output
from .qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    CONTEXT_HASH_FIELDS,
    EMPTY_HEAD,
    LANE,
    OutputConsistencyError,
    _canonical,
    _context,
    _parse,
    _shape,
)
from .roundtrip_v2_records import _open_file

Json = dict[str, Any]
OPERATOR_PLAN_SCHEMA = "qualification-output-operator-plan/v1"
OPERATOR_PLAN_FIELDS = frozenset(
    {"schemaVersion", "lane", "authorityStatus", "proposal"}
)
OPERATOR_PLAN_STATUS = "review_only_not_authority"
OPERATOR_PROPOSAL_SCHEMA = "qualification-output-operator-proposal/v1"
OPERATOR_PROPOSAL_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "proposalStatus",
        "approvalId",
        "operator",
        "issuedAt",
        "expiresAt",
        "invocationId",
        "context",
        "target",
        "profile",
        "releaseManifestSha256",
        "installedReleaseSha256",
        "packageRoot",
        "packageSha256",
        "admissionSha256",
        "sourceGraphSha256",
        "outputPath",
        "settings",
        "actionPlan",
        "maxPolls",
        "confirmations",
        "oneUse",
    }
)
FINALIZE_REFUSAL_SCHEMA = "qualification-output-finalize-refusal/v1"
FINALIZE_REFUSAL_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "context",
        "capturePostResultSha256",
        "stage",
        "errorType",
        "reason",
    }
)
FINALIZE_CLOCK_SCHEMA = "qualification-output-finalize-clock/v1"
# Largest backward OS wall step a controller operation may recheck across. The
# measured backward steps were 57-189 ms; expiry windows are minutes long.
FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS = 1.0
# One mutable sample slot shared only by nested clocks in this request's checks.
_REQUEST_CLOCK_SAMPLE: ContextVar[list[tuple[datetime, float]] | None] = ContextVar(
    "request_clock_sample", default=None
)
HOST_STATE_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-host/v1/attempts"
)
_RECEIPT_KINDS = frozenset(
    {
        "output_geometry_snapshot",
        "output_prediction_commitment",
        "output_render_reservation",
        "output_decode_record",
        "output_residual_comparison",
        "output_proposal_evidence",
        "output_proposal_decision",
        "output_revised_preflight",
        "output_omission_review",
    }
)
ENTRY_FIELDS = frozenset(
    [
        "schemaVersion",
        "lane",
        "context",
        "sequence",
        "priorHeadSha256",
        "state",
        "commitmentRawSha256",
        "commitmentPayloadSha256",
        "predictionBytesSha256",
        "reservationRawSha256",
        "resultRawSha256",
        "entrySha256",
    ]
)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise OutputConsistencyError(message)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _operator_plan_proposal(raw: bytes) -> Json:
    """Extract a review-only proposal; it is not an operator approval."""
    wrapper = _shape(_parse(raw), OPERATOR_PLAN_FIELDS, "operator plan")
    _require(raw == _canonical(wrapper), "canonical operator plan bytes required")
    _require(
        wrapper["schemaVersion"] == OPERATOR_PLAN_SCHEMA
        and wrapper["lane"] == LANE
        and wrapper["authorityStatus"] == OPERATOR_PLAN_STATUS,
        "review-only operator plan required",
    )
    proposal = _shape(
        wrapper["proposal"], OPERATOR_PROPOSAL_FIELDS, "operator proposal"
    )
    _require(
        proposal["schemaVersion"] == OPERATOR_PROPOSAL_SCHEMA
        and proposal["lane"] == LANE
        and proposal["proposalStatus"] == OPERATOR_PLAN_STATUS,
        "review-only operator proposal required",
    )
    return proposal


def _approval_from_proposal(proposal: Json) -> Json:
    """Construct native approval content; the issuer supplies the consent path."""
    from .qualification_output_native_v2 import APPROVAL_FIELDS, APPROVAL_SCHEMA

    value = copy.deepcopy(proposal)
    value.pop("proposalStatus", None)
    value["schemaVersion"] = APPROVAL_SCHEMA
    return _shape(value, APPROVAL_FIELDS, "operator approval")


def _json_hash(value: Any) -> str:
    return _hash(_canonical(value))


def _safe(path: Path) -> None:
    _require(path.is_absolute(), "absolute journal path required")
    _require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        "symlink in journal path",
    )


def _read(path: Path, maximum: int = 8 * 1024 * 1024) -> bytes:
    _safe(path)
    descriptor = _open_file(path, os.O_RDONLY)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode), "regular journal file required")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    _safe(path)

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    _require(
        identity(before) == identity(after) == identity(path.stat()),
        "journal changed while reading",
    )
    _require(len(raw) <= maximum, "journal file exceeds bound")
    return raw


def _recovery_file_record(path: Path) -> Json:
    try:
        digest = _hash(_read(path))
    except FileNotFoundError:
        return {"path": str(path), "sha256": None}
    except (OutputConsistencyError, OSError) as error:
        return {"path": str(path), "error": str(error)}
    return {"path": str(path), "sha256": digest}


def _recovery_native_operations(context: Json) -> list[Json]:
    from .qualification_output_native_v2 import (
        RETRY_ACTION_PLAN,
        action_plan_for_context,
        native_request_paths,
    )

    operations = []
    for sequence, action in enumerate(
        (*action_plan_for_context(context), *RETRY_ACTION_PLAN[1:])
    ):
        result, _, intent, request = native_request_paths(context, sequence)
        if sequence == 6:
            action = "capture_post|retry_capture"
            if request.exists():
                try:
                    retained_action = _parse(_read(request)).get("action")
                    if retained_action in {"capture_post", "retry_capture"}:
                        action = retained_action
                except (OutputConsistencyError, OSError, ValueError):
                    pass
        effects_dir = request.parent / "effects"
        try:
            _safe(effects_dir)
            paths = sorted(
                [
                    *effects_dir.glob("*-intent.json"),
                    *effects_dir.glob("*-observed.json"),
                ]
            )[:4096]
            effects = [_recovery_file_record(path) for path in paths]
        except (OutputConsistencyError, OSError) as error:
            effects = [{"path": str(effects_dir), "error": str(error)}]
        operations.append(
            {
                "sequence": sequence,
                "action": action,
                "request": _recovery_file_record(request),
                "start": _recovery_file_record(request.parent / "native-start.json"),
                "intent": _recovery_file_record(intent),
                "result": _recovery_file_record(result),
                "effects": effects,
            }
        )
    return operations


def _recovery_finalize_refusals(directory: Path) -> list[Json]:
    """Read immutable post-capture refusal records without changing the journal."""
    records: list[Json] = []
    for path in sorted(directory.glob("finalize-refusal-*.json"))[:4096]:
        record = _recovery_file_record(path)
        if "sha256" not in record:
            records.append(record)
            continue
        try:
            _require(
                record["sha256"] == path.stem.removeprefix("finalize-refusal-"),
                "finalize refusal marker changed",
            )
            value = _parse(_read(path))
            _require(
                set(value) == FINALIZE_REFUSAL_FIELDS
                and value["schemaVersion"] == FINALIZE_REFUSAL_SCHEMA
                and value["lane"] == LANE,
                "closed finalize refusal record required",
            )
            _context(value["context"])
            _require(
                type(value["capturePostResultSha256"]) is str
                and len(value["capturePostResultSha256"]) == 64
                and all(
                    c in "0123456789abcdef" for c in value["capturePostResultSha256"]
                )
                and type(value["stage"]) is str
                and type(value["errorType"]) is str
                and type(value["reason"]) is str,
                "bounded finalize refusal details required",
            )
            record.update(
                {
                    "context": value["context"],
                    "capturePostResultSha256": value["capturePostResultSha256"],
                    "stage": value["stage"],
                    "errorType": value["errorType"],
                    "reason": value["reason"],
                }
            )
        except (OutputConsistencyError, OSError, ValueError) as error:
            record.pop("sha256", None)
            record["error"] = str(error)
        records.append(record)
    return records


def _sync_directory(path: Path) -> None:
    descriptor = _open_file(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(path: Path, raw: bytes) -> None:
    _safe(path)
    descriptor = _open_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o400)
    _sync_directory(path.parent)


def _chain(context: Json) -> Json:
    ctx = _context(context)
    return {
        "projectUid": ctx["target"]["projectUid"],
        "timelineUid": ctx["target"]["timelineUid"],
        "caseId": ctx["caseId"],
        "phase": ctx["phase"],
    }


def _binding(context: Json) -> str:
    return str(_context(context)["binding"]["bindingSha256"])


def _validated_history(rows: list[Json], chain: Json) -> str:
    _require(len(rows) <= 4096, "journal entry bound exceeded")
    head = EMPTY_HEAD
    last: dict[str, Json] = {}
    for sequence, row in enumerate(rows):
        _require(set(row) == ENTRY_FIELDS, "closed journal entry required")
        _require(
            row["schemaVersion"] == "qualification-output-attempt/v1"
            and row["lane"] == LANE
            and _chain(row["context"]) == chain
            and type(row["sequence"]) is int
            and row["sequence"] == sequence
            and row["priorHeadSha256"] == head,
            "incomplete target/case/phase chain",
        )
        _require(
            row["entrySha256"]
            == _json_hash({k: v for k, v in row.items() if k != "entrySha256"}),
            "journal entry hash differs",
        )
        for field in (
            "commitmentRawSha256",
            "commitmentPayloadSha256",
            "predictionBytesSha256",
        ):
            _require(
                type(row[field]) is str
                and len(row[field]) == 64
                and all(c in "0123456789abcdef" for c in row[field]),
                "invalid journal digest",
            )
        key = _binding(row["context"])
        prior = last.get(key)
        state = row["state"]
        _require(type(state) is str, "invalid attempt state")
        for field in ("reservationRawSha256", "resultRawSha256"):
            value = row[field]
            _require(
                value is None
                or (
                    type(value) is str
                    and len(value) == 64
                    and all(c in "0123456789abcdef" for c in value)
                ),
                "invalid attempt reference",
            )
        if state == "committed":
            _require(
                prior is None or prior["state"] in {"expired_unused", "render_failed"},
                "stable binding already attempted",
            )
            if prior:
                _require(
                    prior["predictionBytesSha256"] == row["predictionBytesSha256"]
                    and prior["context"] == row["context"],
                    "recommitted prediction or context changed",
                )
            if prior:
                failures = sum(
                    r["state"] == "render_failed" and _binding(r["context"]) == key
                    for r in rows[:sequence]
                )
                _require(
                    failures == (1 if prior["state"] == "render_failed" else 0),
                    "render retry budget exhausted",
                )
            _require(
                row["reservationRawSha256"] is None and row["resultRawSha256"] is None,
                "commitment has future references",
            )
        else:
            _require(prior is not None, "attempt lacks commitment")
            assert prior is not None
            _require(
                all(
                    row[k] == prior[k]
                    for k in (
                        "context",
                        "commitmentRawSha256",
                        "commitmentPayloadSha256",
                        "predictionBytesSha256",
                    )
                ),
                "attempt lineage changed",
            )
            if state == "expired_unused":
                _require(
                    prior["state"] == "committed"
                    and row["reservationRawSha256"] is None
                    and row["resultRawSha256"] is None,
                    "only unused commitment may expire",
                )
            elif state == "reserved_by_render_intent":
                _require(
                    prior["state"] == "committed"
                    and type(row["reservationRawSha256"]) is str
                    and len(row["reservationRawSha256"]) == 64
                    and row["resultRawSha256"] is None,
                    "exclusive reservation already used",
                )
            else:
                _require(
                    state
                    in {
                        "uncertain",
                        "render_failed",
                        "compared_consistent",
                        "compared_refused",
                    }
                    and prior["state"] == "reserved_by_render_intent"
                    and row["reservationRawSha256"] == prior["reservationRawSha256"],
                    "terminal or uncertain attempt cannot restart",
                )
                _require(
                    (
                        row["resultRawSha256"] is None
                        if state == "uncertain"
                        else type(row["resultRawSha256"]) is str
                        and len(row["resultRawSha256"]) == 64
                    ),
                    "invalid terminal result reference",
                )
        head = row["entrySha256"]
        last[key] = row
    return str(head)


class OutputAttemptJournal:
    """One trusted private root; no request-selected ledger/root/prefix.

    Each append writes its immutable pending record before its entry. A crash
    between them blocks the entire chain for read-only recovery, so an uncertain
    fsync/publication never permits a second render.
    """

    def __init__(self, root: Path, context: Json) -> None:
        _safe(root)
        self.root = root
        self.chain = _chain(context)
        self.directory = root / _json_hash(self.chain)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _safe(root)
        _require(root.stat().st_uid == os.getuid(), "journal owner differs")
        _require(root.stat().st_mode & 0o077 == 0, "journal root must be private")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.artifacts = self.directory / "artifacts"
        with self._lock():
            marker = self.directory / "chain.json"
            if not marker.exists():
                _require(
                    set(p.name for p in self.directory.iterdir()) == {"lock"},
                    "missing journal chain marker",
                )
                _publish(marker, _canonical(self.chain))
            _require(
                _parse(_read(marker)) == self.chain, "journal chain identity differs"
            )
            self.artifacts.mkdir(mode=0o700, exist_ok=True)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        _safe(self.directory)
        descriptor = _open_file(self.directory / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "r+b") as stream:
            _require(
                stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "regular lock required"
            )
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _load(self) -> list[Json]:
        _require(
            _parse(_read(self.directory / "chain.json")) == self.chain, "chain differs"
        )
        entries = sorted(self.directory.glob("entry-*.json"))
        pending = sorted(self.directory.glob("pending-*.json"))
        heads = sorted(self.directory.glob("head-*.json"))
        _require(
            len(entries) == len(pending) == len(heads),
            "partial append: read-only recovery required",
        )
        rows: list[Json] = []
        for sequence, (entry_path, pending_path) in enumerate(
            zip(entries, pending, strict=True)
        ):
            _require(
                entry_path.name == f"entry-{sequence:04d}.json"
                and pending_path.name == f"pending-{sequence:04d}.json",
                "truncated/reordered journal inventory",
            )
            raw = _read(entry_path)
            _require(raw == _read(pending_path), "partial journal publication")
            row = _parse(raw)
            _require(
                heads[sequence].name == f"head-{sequence:04d}.json"
                and _parse(_read(heads[sequence]))
                == {
                    "sequence": sequence,
                    "entrySha256": row["entrySha256"],
                },
                "journal head anchor differs",
            )
            rows.append(row)
        _validated_history(rows, self.chain)
        for row in rows:
            for field in (
                "commitmentRawSha256",
                "predictionBytesSha256",
                "reservationRawSha256",
                "resultRawSha256",
            ):
                digest = row[field]
                if digest is not None:
                    _require(
                        _hash(_read(self.artifacts / digest, maximum=48_000_000))
                        == digest,
                        "retained attempt artifact differs",
                    )
        return rows

    def _retain(self, raw: bytes) -> str:
        _require(
            type(raw) is bytes and len(raw) <= 48_000_000,
            "bounded attempt artifact required",
        )
        digest = _hash(raw)
        path = self.artifacts / digest
        if path.exists():
            _require(
                _read(path, maximum=48_000_000) == raw, "retained artifact collision"
            )
        else:
            _publish(path, raw)
        return digest

    def history(self) -> list[Json]:
        with self._lock():
            return copy.deepcopy(self._load())

    def _append(
        self, event: Json, *, expected_head: str, artifacts: tuple[bytes, ...] = ()
    ) -> Json:
        with self._lock():
            rows = self._load()
            head = _validated_history(rows, self.chain)
            _require(head == expected_head, "prior-terminal-head CAS refused")
            entry = {
                "schemaVersion": "qualification-output-attempt/v1",
                "lane": LANE,
                **copy.deepcopy(event),
                "sequence": len(rows),
                "priorHeadSha256": head,
            }
            entry["entrySha256"] = _json_hash(entry)
            _validated_history([*rows, entry], self.chain)
            for artifact in artifacts:
                self._retain(artifact)
            raw = _canonical(entry)
            _publish(self.directory / f"pending-{len(rows):04d}.json", raw)
            _publish(self.directory / f"entry-{len(rows):04d}.json", raw)
            _publish(
                self.directory / f"head-{len(rows):04d}.json",
                _canonical(
                    {
                        "sequence": len(rows),
                        "entrySha256": entry["entrySha256"],
                    }
                ),
            )
            return copy.deepcopy(entry)

    def commit(self, context: Json, commitment: bytes, prediction: bytes) -> Json:
        value = _parse(commitment)
        _require(value["context"] == context, "commitment context differs")
        _require(
            value["predictionBytesSha256"] == _hash(prediction), "prediction differs"
        )
        payload = {k: v for k, v in value.items() if k != "commitmentReceiptSha256"}
        rows = self.history()
        return self._append(
            {
                "context": context,
                "state": "committed",
                "commitmentRawSha256": _hash(commitment),
                "commitmentPayloadSha256": _json_hash(payload),
                "predictionBytesSha256": _hash(prediction),
                "reservationRawSha256": None,
                "resultRawSha256": None,
            },
            expected_head=_validated_history(rows, self.chain),
            artifacts=(commitment, prediction),
        )

    def transition(
        self,
        context: Json,
        state: str,
        *,
        expected_head: str,
        reservation: bytes | None = None,
        result: bytes | None = None,
    ) -> Json:
        rows = self.history()
        prior = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(context)
            ),
            None,
        )
        _require(
            prior is not None and prior["context"] == context, "unknown attempt context"
        )
        assert prior is not None
        event = {
            k: copy.deepcopy(prior[k])
            for k in (
                "context",
                "commitmentRawSha256",
                "commitmentPayloadSha256",
                "predictionBytesSha256",
                "reservationRawSha256",
                "resultRawSha256",
            )
        }
        event["state"] = state
        if reservation is not None:
            value = _parse(reservation)
            _require(
                value["context"] == context
                and value["commitmentRawSha256"] == prior["commitmentRawSha256"]
                and value["commitmentPayloadSha256"]
                == prior["commitmentPayloadSha256"],
                "reservation lineage differs",
            )
            event["reservationRawSha256"] = _hash(reservation)
        if result is not None:
            value = _parse(result)
            if state == "render_failed":
                _require(
                    value["context"] == context
                    and value["status"] == "partial"
                    and value["action"] == "poll_render"
                    and value["renderStatus"]["JobStatus"] in {"Failed", "Cancelled"}
                    and value["reservationSha256"] == prior["reservationRawSha256"]
                    and value["commitmentRawSha256"] == prior["commitmentRawSha256"],
                    "confirmed failed render lineage required",
                )
            else:
                _require(
                    value["context"] == context
                    and value["status"] == state
                    and value["priorLedgerHeadSha256"] == expected_head
                    and value["commitmentRawSha256"] == prior["commitmentRawSha256"]
                    and value["reservationRawSha256"] == prior["reservationRawSha256"],
                    "terminal lineage/head differs",
                )
            event["resultRawSha256"] = _hash(result)
        artifacts = tuple(raw for raw in (reservation, result) if raw is not None)
        return self._append(event, expected_head=expected_head, artifacts=artifacts)


def verify_revised_preflight_v2(
    path: Any = None, expected_sha256: str | None = None
) -> Json:
    """Static #215 port; an absent or legacy proof still fails closed."""
    _require(
        isinstance(path, Path) and expected_sha256 is not None,
        "#215 revised output preflight is unavailable without its bound proof",
    )
    from .qualification_output_proof_v2 import verify_revised_preflight_v2 as verify

    assert isinstance(path, Path) and expected_sha256 is not None
    return verify(path, expected_sha256)


def output_runtime_snapshot() -> bytes:
    """Collect actual locked host facts; callers cannot supply version labels."""
    _require(
        platform.python_implementation() == "CPython"
        and platform.python_version() == "3.12.14",
        "locked CPython 3.12.14 required",
    )
    versions: dict[str, str] = {}
    for executable, expected in (
        ("node", "v24.19.0"),
        ("npm", "11.17.0"),
        ("uv", "uv 0.12.5"),
    ):
        path = shutil.which(executable)
        _require(path is not None, f"locked {executable} unavailable")
        assert path is not None
        result = subprocess.run(
            [path, "--version"], capture_output=True, check=True, timeout=10
        )
        actual = result.stdout.decode("utf-8").strip()
        _require(
            (
                actual == expected
                if executable != "uv"
                else actual.split(" (")[0] == expected
            ),
            f"locked {executable} differs",
        )
        versions[executable] = expected.removeprefix("v").removeprefix("uv ")
    return _canonical(
        {
            "schemaVersion": "qualification-output-runtime/v1",
            "lane": LANE,
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "nodeVersion": versions["node"],
            "npmVersion": versions["npm"],
            "uvVersion": versions["uv"],
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }
    )


def output_release_snapshot(release_root: Path) -> bytes:
    """Independently reverify all installed content against current owned source."""
    from .workflow_v2_cli import _verify_output_release

    manifest_path = _verify_output_release(release_root)
    manifest = _parse(_read(manifest_path))
    return _canonical(
        {
            "schemaVersion": "qualification-output-release/v1",
            "lane": LANE,
            "files": {row["path"]: row["sha256"] for row in manifest["files"]},
        }
    )


def output_profile_snapshot(manifest: Json) -> bytes:
    """One finite picture/PCM route; no request-selected codec/settings profile."""
    timeline = manifest["timeline"]
    _require(
        timeline["frameRate"] == {"numerator": 24000, "denominator": 1001}
        and all(type(v) is int for v in timeline["frameRate"].values()),
        "qualification profile requires 24000/1001",
    )
    for field in ("width", "height"):
        _require(
            type(timeline[field]) is int and 1 <= timeline[field] <= 16384,
            "bounded picture dimensions required",
        )
    return _canonical(
        {
            "schemaVersion": "qualification-output-profile/v1",
            "lane": LANE,
            "container": "mov",
            "videoCodec": "prores422",
            "audioCodec": "lpcm",
            "audioBitDepth": 24,
            "sampleRate": 48000,
            "channels": 2,
            "rate": {"numerator": 24000, "denominator": 1001},
            "width": timeline["width"],
            "height": timeline["height"],
        }
    )


def issue_operator_approval(
    plan_path: Path,
    output_path: Path,
    *,
    session_path: Path | None = None,
    session_sha256: str | None = None,
    consent_reference: str | None = None,
    consent_instruction: str | None = None,
) -> Path:
    """Issue through attended review or an explicitly instructed local agent.

    Consent references attribute the agent's instruction; they do not authenticate
    a conversation. The trusted local agent must actually have received consent.
    """
    from .qualification_output_native_v2 import verify_operator_approval

    plan_raw = _read(plan_path)
    proposal = _operator_plan_proposal(plan_raw)
    _require(
        proposal["operator"] == pwd.getpwuid(os.getuid()).pw_name,
        "operator identity differs from local actor",
    )
    _safe(output_path)
    issuance_path = output_path.with_name(output_path.name + ".issuance.json")
    _require(
        not output_path.exists()
        and not issuance_path.exists()
        and not issuance_path.is_symlink()
        and output_path.parent.is_dir()
        and output_path.parent.stat().st_uid == os.getuid()
        and output_path.parent.stat().st_mode & 0o077 == 0,
        "new private operator approval destination required",
    )
    agent_fields = (
        session_path,
        session_sha256,
        consent_reference,
        consent_instruction,
    )
    agent_issued = any(value is not None for value in agent_fields)
    approval = _approval_from_proposal(proposal)
    if agent_issued:
        _require(
            isinstance(session_path, Path)
            and type(session_sha256) is str
            and all(
                type(value) is str and 0 < len(value.strip()) <= 4096
                for value in (consent_reference, consent_instruction)
            ),
            "agent issuance requires the pinned session and actual consent "
            "reference/instruction",
        )
        assert isinstance(session_path, Path) and isinstance(session_sha256, str)
        controller = load_output_session(session_path, session_sha256)
        controller._environment_current()
        from .qualification_output_native_v2 import (
            MAX_LIFETIME_SECONDS,
            RETRY_ACTION_PLAN,
            action_plan_for_context,
            next_native_operation,
            render_parent,
        )
        from .workflow_v2_cli import _verify_output_release

        retry = approval["actionPlan"] == list(RETRY_ACTION_PLAN)
        sequence, _ = next_native_operation(controller.context, retry=retry)
        _require(
            retry or sequence < len(action_plan_for_context(controller.context)),
            "completed run or retry requires its own bounded retry plan",
        )
        expected_output = render_parent(controller.context) / (
            controller.context["binding"]["bindingSha256"]
            + ("-retry-1.mov" if retry else ".mov")
        )
        _require(
            approval["context"] == controller.context
            and approval["profile"] == controller.admission.profile
            and approval["packageRoot"] == str(controller.admission.package_root)
            and approval["admissionSha256"]
            == _hash(_read(controller.admission.admission_path))
            and approval["releaseManifestSha256"]
            == _hash(_read(_verify_output_release(controller.release_root)))
            and approval["outputPath"] == str(expected_output),
            "operator plan is outside the current pinned session scope",
        )
        # Preparation is review-only; the live 30-minute window starts at issuance.
        now = controller.trust.checked_now()
        approval["issuedAt"] = _iso(now)
        approval["expiresAt"] = _iso(now + timedelta(seconds=MAX_LIFETIME_SECONDS))
    else:
        # The legacy human challenge continues to cover the complete proposal.
        print(plan_raw.decode("utf-8"))
        phrase = "APPROVE " + _hash(plan_raw)
        print(
            "Review the exact target, release, inputs, output and finite actions above."
        )
        with open("/dev/tty", "r+", encoding="utf-8") as terminal:
            _require(terminal.isatty(), "interactive operator terminal required")
            terminal.write(f"To issue this one-use product authority, type {phrase}: ")
            terminal.flush()
            answer = terminal.readline(256).rstrip("\r\n")
        _require(answer == phrase, "operator did not approve the exact plan")
    _require(_read(plan_path) == plan_raw, "operator plan changed during review")
    _require(
        _canonical(_operator_plan_proposal(plan_raw)) == _canonical(proposal),
        "operator proposal changed during review",
    )
    approval_raw = _canonical(approval)
    # Revalidate the constructed approval, then publish exactly those bytes.
    verify_operator_approval(
        approval_raw,
        context=proposal["context"],
        profile=proposal["profile"],
        admission_sha256=proposal["admissionSha256"],
        release_manifest_sha256=proposal["releaseManifestSha256"],
    )
    if agent_issued:
        _publish(
            issuance_path,
            _canonical(
                {
                    "schemaVersion": "qualification-output-agent-issuance/v1",
                    "issuanceMode": "agent_mediated_not_transcript_authenticated",
                    "consentReference": consent_reference,
                    "consentInstruction": consent_instruction,
                    "sessionPath": str(session_path),
                    "sessionSha256": session_sha256,
                    "planSha256": _hash(plan_raw),
                    "approvalSha256": _hash(approval_raw),
                    "scope": approval,
                }
            ),
        )
    _publish(output_path, approval_raw)
    return output_path


def prepare_output_session(
    output_root: Path,
    *,
    profile: str,
    target: Json,
    case_id: str,
    phase: str = "pristine",
    package_root: Path | None = None,
    preparation_paths: dict[str, Path] | None = None,
    narration_evidence_paths: dict[str, dict[str, Path]] | None = None,
    render_root: Path | None = None,
) -> Path:
    """Create reviewable host artifacts; no installation or native connection.

    Measured narration evidence files are tracked and hashed by the admission,
    whose currentness check (on every session load) refuses swapped bytes.
    """
    from .qualification_output_package_v2 import admit_qualification_package_v2
    from .workflow_v2_cli import build_output_release_v2

    _safe(output_root)
    _require(not output_root.exists(), "new output session root required")
    output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    admission = admit_qualification_package_v2(
        output_root / "admitted",
        profile=profile,
        package_root=package_root,
        preparation_paths=preparation_paths,
        narration_evidence_paths=narration_evidence_paths,
    )
    release_root = output_root / "release"
    build_output_release_v2(release_root)
    controller = QualificationOutputController(
        HOST_STATE_ROOT,
        admission=admission,
        release_root=release_root,
        target=target,
        case_id=case_id,
        phase=phase,
        invocation_id=str(uuid.uuid4()),
    )
    if render_root is not None:
        from .qualification_output_native_v2 import register_render_root

        register_render_root(controller.context, render_root)
    session = {
        "schemaVersion": "qualification-output-session/v1",
        "lane": LANE,
        "profile": profile,
        "admissionPath": str(admission.admission_path),
        "admissionSha256": _hash(_read(admission.admission_path)),
        "releaseRoot": str(release_root),
        "context": controller.context,
        "hostJournalRoot": str(HOST_STATE_ROOT),
    }
    session_path = output_root / "session.json"
    _publish(session_path, _canonical(session))
    controller.prepare_operator_plan(output_root / "operator-plan.json")
    return session_path


def load_output_session(
    session_path: Path, expected_sha256: str
) -> QualificationOutputController:
    """Reopen only a complete verified session, retaining its immutable UID chain."""
    from .qualification_output_package_v2 import _load_qualification_package_v2

    raw = _read(session_path)
    _require(_hash(raw) == expected_sha256, "session raw pin differs")
    session = _parse(raw)
    fields = {
        "schemaVersion",
        "lane",
        "profile",
        "admissionPath",
        "admissionSha256",
        "releaseRoot",
        "context",
        "hostJournalRoot",
    }
    if session.get("context", {}).get("phase") == "rebuild":
        fields.add("revisedPreflight")
    _require(
        set(session) == fields
        and session["schemaVersion"] == "qualification-output-session/v1"
        and session["lane"] == LANE
        and session["hostJournalRoot"] == str(HOST_STATE_ROOT),
        "closed owned session required",
    )
    admission = _load_qualification_package_v2(
        Path(session["admissionPath"]), session["admissionSha256"]
    )
    context = _context(session["context"])
    controller = QualificationOutputController(
        HOST_STATE_ROOT,
        admission=admission,
        release_root=Path(session["releaseRoot"]),
        target=context["target"],
        case_id=context["caseId"],
        phase=context["phase"],
        invocation_id=context["invocationId"],
        revised_preflight=(
            None
            if "revisedPreflight" not in session
            else (
                Path(session["revisedPreflight"]["path"]),
                session["revisedPreflight"]["sha256"],
            )
        ),
    )
    _require(
        controller.context == context, "session inputs/runtime/source/release changed"
    )
    return controller


class _ReceiptVault:
    """Private integrity seals, issued only after concrete product verification.

    The key authenticates retained payload/evidence bytes; it never authenticates
    their provenance by itself. The controller's fixed stage methods establish
    provenance before issuance. This is not an operator authority issuer.
    """

    def __init__(self, root: Path) -> None:
        _safe(root)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require(
            root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o077 == 0,
            "private receipt vault required",
        )
        self.root = root
        key_path = root / "key"
        if not key_path.exists():
            with suppress(FileExistsError):
                _publish(key_path, os.urandom(32))
        self.key = _read(key_path, maximum=32)
        _require(
            len(self.key) == 32 and key_path.stat().st_mode & 0o077 == 0,
            "invalid private receipt key",
        )

    def _issue(self, kind: str, payload: Json, evidence: tuple[bytes, ...]) -> bytes:
        _require(
            kind in _RECEIPT_KINDS and bool(evidence),
            "unsupported receipt kind/evidence",
        )
        hashes: list[str] = []
        for raw in evidence:
            _require(
                type(raw) is bytes and len(raw) <= 48_000_000,
                "bounded receipt evidence required",
            )
            digest = _hash(raw)
            path = self.root / digest
            if path.exists():
                _require(
                    _read(path, maximum=48_000_000) == raw, "receipt evidence collision"
                )
            else:
                try:
                    _publish(path, raw)
                except FileExistsError:
                    _require(
                        _read(path, maximum=48_000_000) == raw,
                        "receipt evidence collision",
                    )
            hashes.append(digest)
        value = {
            "schemaVersion": "qualification-output-host-receipt/v1",
            "lane": LANE,
            "kind": kind,
            "payload": copy.deepcopy(payload),
            "evidenceSha256": hashes,
        }
        raw = _canonical(value)
        value["mac"] = hmac.digest(self.key, raw, "sha256").hex()
        receipt = _canonical(value)
        path = self.root / _hash(receipt)
        if not path.exists():
            _publish(path, receipt)
        return receipt

    def authenticate(self, kind: str, receipt: bytes, expected: Json) -> None:
        _require(kind in _RECEIPT_KINDS, "unsupported sibling receipt kind")
        value = _parse(receipt)
        _require(
            set(value)
            == {"schemaVersion", "lane", "kind", "payload", "evidenceSha256", "mac"},
            "closed host receipt required",
        )
        _require(
            value["schemaVersion"] == "qualification-output-host-receipt/v1"
            and value["lane"] == LANE
            and value["kind"] == kind,
            "wrong receipt domain",
        )
        mac = value.pop("mac")
        _require(
            type(mac) is str
            and hmac.compare_digest(
                mac, hmac.digest(self.key, _canonical(value), "sha256").hex()
            ),
            "receipt integrity differs",
        )
        _require(
            _canonical(value["payload"]) == _canonical(expected),
            "receipt payload differs",
        )
        _require(_read(self.root / _hash(receipt)) == receipt, "unretained receipt")
        hashes = value["evidenceSha256"]
        _require(
            type(hashes) is list and 1 <= len(hashes) <= 64,
            "complete receipt evidence required",
        )
        for digest in hashes:
            _require(
                type(digest) is str
                and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest),
                "invalid receipt evidence digest",
            )
            _require(
                _hash(_read(self.root / digest, maximum=48_000_000)) == digest,
                "retained receipt evidence changed",
            )


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class HostClockRegression(OutputConsistencyError):
    """Wall time lagged monotonic time beyond sampling and slew bounds.

    macOS ``timed`` steps the wall clock with settimeofday, measured on the
    qualification Mac at -189 ms to +971 ms roughly hourly; A11's refusal
    followed a -63.8 ms step. Selected pre-write operations may recheck once.
    """

    def __init__(self, diagnostics: Json) -> None:
        super().__init__("host clock rollback/uncertainty")
        self.diagnostics = diagnostics

    @property
    def recheckable(self) -> bool:
        return bool(
            self.diagnostics["classification"] == "wall_lag"
            and self.diagnostics["lagSeconds"] <= FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS
        )


@contextmanager
def _request_clock_scope() -> Iterator[None]:
    token = _REQUEST_CLOCK_SAMPLE.set([])
    try:
        yield
    finally:
        _REQUEST_CLOCK_SAMPLE.reset(token)


class _ControllerTrust:
    """Statically bound provenance and clock; never selected by request JSON."""

    def __init__(self, vault: _ReceiptVault, admission: Any) -> None:
        self.vault = vault
        self.admission = admission
        self.wall = datetime.now(UTC)
        self.monotonic = time.monotonic()

    def checked_now(self) -> datetime:
        before = time.monotonic()
        now = datetime.now(UTC)
        after = time.monotonic()
        sample = _REQUEST_CLOCK_SAMPLE.get()
        anchors = [(self.wall, self.monotonic)]
        if sample is not None:
            anchors.extend(sample)
        for wall, monotonic in anchors:
            elapsed = before - monotonic
            wall_elapsed = (now - wall).total_seconds()
            if not (
                elapsed >= 0
                and now >= wall
                and wall_elapsed + 0.000002 + elapsed * 0.0005 >= elapsed
            ):
                raise HostClockRegression(
                    {
                        "classification": (
                            "monotonic_regression" if elapsed < 0 else "wall_lag"
                        ),
                        "priorWall": _iso(wall),
                        "observedWall": _iso(now),
                        "monotonicElapsedSeconds": elapsed,
                        "wallElapsedSeconds": wall_elapsed,
                        "lagSeconds": elapsed - wall_elapsed,
                        "lagPartsPerMillion": (
                            (elapsed - wall_elapsed) / elapsed * 1_000_000
                            if elapsed > 0
                            else None
                        ),
                        "toleranceSeconds": 0.000002 + max(elapsed, 0) * 0.0005,
                        "samplingWindowSeconds": after - before,
                        "wallBeforePriorSample": now < wall,
                    }
                )
        self.wall, self.monotonic = now, after
        if sample is not None:
            sample[:] = [(now, after)]
        return now

    def authenticate(self, kind: str, receipt: bytes, expected: Json) -> None:
        if kind in {"narration_preparation", "private_preparation"}:
            self.admission.verify_source_payload(kind, receipt, copy.deepcopy(expected))
            return
        self.vault.authenticate(kind, receipt, expected)


class QualificationOutputController:
    """Own prediction/reservation/comparison on one complete private UID chain.

    Inputs originate from the concrete package admission and installed native
    result verifiers. The controller has no user-supplied trust implementation,
    callback, signer, history, render command or module selection.
    """

    def __init__(
        self,
        root: Path,
        *,
        admission: Any,
        release_root: Path,
        target: Json,
        case_id: str,
        phase: str,
        invocation_id: str,
        revised_preflight: tuple[Path, str] | None = None,
    ) -> None:
        from .qualification_output_package_v2 import QualificationOutputAdmissionV2

        _require(
            type(admission) is QualificationOutputAdmissionV2,
            "concrete package admission required",
        )
        _require(
            root == HOST_STATE_ROOT, "controller uses the fixed complete host journal"
        )
        revision = None
        if phase == "rebuild":
            _require(
                revised_preflight is not None,
                "rebuild requires the accepted revised preflight",
            )
            assert revised_preflight is not None
            from .qualification_output_proof_v2 import (
                _verify_revised_preflight_with_proof_v2,
                _verify_revised_rebuild_reservation_for_proof_v2,
            )

            revision, proof = _verify_revised_preflight_with_proof_v2(
                *revised_preflight
            )
            proof._current()
            _verify_revised_rebuild_reservation_for_proof_v2(
                revision,
                revised_preflight[1],
                admission_path=admission.admission_path,
                target=target,
                case_id=case_id,
                invocation_id=invocation_id,
                proof=proof,
            )
        else:
            _require(revised_preflight is None, "revised proof requires rebuild phase")
        admission.assert_current()
        self.admission = admission
        self.release_root = release_root
        self.revised_preflight = revised_preflight
        self.blobs = dict(admission.blobs)
        from .roundtrip_v2_records import proof_source_hashes_v2

        self.blobs.update(
            {
                "hostSourceGraphSha256": _canonical(proof_source_hashes_v2()),
                "installedReleaseSha256": output_release_snapshot(release_root),
                "runtimeSha256": output_runtime_snapshot(),
                "profileSha256": output_profile_snapshot(admission.manifest),
            }
        )
        self.blobs["nativeSourceGraphSha256"] = _canonical(
            _parse(self.blobs["installedReleaseSha256"])["files"]
        )
        _require(
            self.blobs.keys() == CONTEXT_HASH_FIELDS,
            "complete admitted host input snapshots required",
        )
        context: Json = {key: _hash(raw) for key, raw in self.blobs.items()}
        context.update(
            {
                "lane": LANE,
                "target": copy.deepcopy(target),
                "caseId": case_id,
                "phase": phase,
                "invocationId": invocation_id,
                "binding": {"kind": "baseline"},
            }
        )
        if revision is not None:
            for name, key in (
                ("document", "executionDocumentSha256"),
                ("dependencies", "executionDependenciesSha256"),
            ):
                _require(
                    _hash(self.blobs[key])
                    == revision["executionInputs"][name]["sha256"],
                    "admitted revised execution input differs",
                )
            for name, key in (
                ("document", "originalDocumentSha256"),
                ("dependencies", "originalDependenciesSha256"),
            ):
                _require(
                    _hash(self.blobs[key])
                    == revision["originalInputs"][name]["sha256"],
                    "original document AND dependencies admission differs",
                )
            _require(
                _hash(self.blobs["manifestSha256"]) == revision["manifest"]["sha256"]
                and _hash(self.blobs["reportSha256"]) == revision["report"]["sha256"],
                "admitted revised compiler output differs",
            )
            context["binding"] = {
                "kind": "revised",
                "acceptedDecisionReceiptSha256": revision["acceptedDecisionReceipt"][
                    "sha256"
                ],
                "revisionLedgerSha256": revision["revisionLedger"]["sha256"],
                "proposalEvidenceSha256": revision["evidence"]["sha256"],
                "revisedDocumentSha256": revision["executionInputs"]["document"][
                    "sha256"
                ],
                "revisedDependenciesSha256": revision["executionInputs"][
                    "dependencies"
                ]["sha256"],
                "revisedManifestSha256": revision["manifest"]["sha256"],
            }
        projection = {
            key: value
            for key, value in context.items()
            if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
        }
        context["binding"]["bindingSha256"] = _json_hash(projection)
        self.context = copy.deepcopy(_context(context))
        self.journal = OutputAttemptJournal(root, self.context)
        self.vault = _ReceiptVault(self.journal.directory / "receipts")
        self.trust = _ControllerTrust(self.vault, admission)
        for raw in self.blobs.values():
            self.journal._retain(raw)

    def _environment_current(self) -> None:
        self.admission.assert_current()
        if self.revised_preflight is not None:
            from .qualification_output_proof_v2 import (
                _verify_revised_preflight_with_proof_v2,
                _verify_revised_rebuild_reservation_for_proof_v2,
            )

            revision, proof = _verify_revised_preflight_with_proof_v2(
                *self.revised_preflight
            )
            proof._current()
            _verify_revised_rebuild_reservation_for_proof_v2(
                revision,
                self.revised_preflight[1],
                admission_path=self.admission.admission_path,
                target=self.context["target"],
                case_id=self.context["caseId"],
                invocation_id=self.context["invocationId"],
                proof=proof,
            )
        from .roundtrip_v2_records import proof_source_hashes_v2

        _require(
            _canonical(proof_source_hashes_v2()) == self.blobs["hostSourceGraphSha256"],
            "current host source graph differs",
        )
        _require(
            output_release_snapshot(self.release_root)
            == self.blobs["installedReleaseSha256"],
            "current installed release differs",
        )
        _require(
            output_runtime_snapshot() == self.blobs["runtimeSha256"],
            "current runtime differs",
        )

    def _current(self, inputs: output.PredictionInputs) -> None:
        self._environment_current()
        binding = _parse(inputs.input_binding)
        _require(binding["context"] == self.context, "input context differs")
        for field, raw in inputs.blobs.items():
            _require(_hash(raw) == self.context[field], "input bytes differ")

    def _native_request_preflight(
        self, action: str, approval_path: Path
    ) -> tuple[bytes, Json, int, str | None, datetime]:
        """Repeatable checks only; never create or consume a native slot."""
        from .qualification_output_native_v2 import (
            native_action,
            next_native_operation,
            verify_operator_approval,
        )
        from .workflow_v2_cli import _verify_output_release

        self._environment_current()
        release_manifest = _verify_output_release(self.release_root)
        release_manifest_sha256 = _hash(_read(release_manifest))
        approval_raw = _read(approval_path)
        approval = _parse(approval_raw)
        read_only_action = action in {"poll_render", "capture_post"}
        verify_operator_approval(
            approval_raw,
            context=self.context,
            profile=self.admission.profile,
            admission_sha256=_hash(_read(self.admission.admission_path)),
            release_manifest_sha256=release_manifest_sha256,
            require_live=not read_only_action,
            require_output_absent=action
            in {
                "construct",
                "save_reopen",
                "capture_pre",
                "retry_capture",
                "queue_render",
            },
        )
        sequence, prior_head = (
            next_native_operation(self.context, retry=True)
            if action == "retry_capture"
            else next_native_operation(self.context)
        )
        _require(
            action == native_action(self.context, sequence),
            "native action must follow the fixed reviewed stage order",
        )
        now = self.trust.checked_now()
        if not read_only_action:
            _require(
                datetime.fromisoformat(approval["issuedAt"])
                <= now
                < datetime.fromisoformat(approval["expiresAt"]),
                "operator approval expired or not yet live",
            )
        return approval_raw, approval, sequence, prior_head, now

    @_request_clock_scope()
    def prepare_native_request(
        self,
        action: str,
        payload: Json,
        *,
        approval_path: Path,
        reservation: bytes | None = None,
        reservation_receipt: bytes | None = None,
        render_intent: bytes | None = None,
    ) -> Path:
        """Prepare one static action under genuine existing operator authority."""
        from .qualification_output_native_v2 import (
            AUTHORITY_SCHEMA,
            INTENT_SCHEMA,
            REQUEST_SCHEMA,
            native_request_paths,
            verify_native_request,
        )

        for recheck in (False, True):
            try:
                approval_raw, approval, sequence, prior_head, checked = (
                    self._native_request_preflight(action, approval_path)
                )
                break
            except HostClockRegression as error:
                if recheck:
                    self._retain_request_clock_record(
                        action, error.diagnostics, "terminal"
                    )
                elif self._prepare_clock_recheck(
                    error, stage="request_preparation", action=action
                ):
                    continue
                raise
        result_path, authority_path, intent_path, request_path = native_request_paths(
            self.context, sequence
        )
        _safe(request_path)
        operation_id = str(uuid.uuid4())
        now = _iso(checked)
        request_path.parent.mkdir(mode=0o700, parents=True, exist_ok=False)
        authority: Json = {
            "schemaVersion": AUTHORITY_SCHEMA,
            "lane": LANE,
            "profile": self.admission.profile,
            "authorityId": str(uuid.uuid4()),
            "operator": approval["operator"],
            # Native authority verification binds this byte-for-byte to the
            # human approval. The creation timestamp remains in the intent.
            "issuedAt": approval["issuedAt"],
            "expiresAt": approval["expiresAt"],
            "invocationId": self.context["invocationId"],
            "context": self.context,
            "target": self.context["target"],
            "action": action,
            "payloadSha256": _json_hash(payload),
            "packageSha256": self.context["packageSha256"],
            "admissionSha256": _hash(_read(self.admission.admission_path)),
            "sourceGraphSha256": self.context["nativeSourceGraphSha256"],
            "releaseSha256": self.context["installedReleaseSha256"],
            "releaseManifestSha256": approval["releaseManifestSha256"],
            **{
                key: self.context[key]
                for key in (
                    "originalDocumentSha256",
                    "originalDependenciesSha256",
                    "executionDocumentSha256",
                    "executionDependenciesSha256",
                )
            },
            "approvalPath": str(approval_path),
            "approvalSha256": _hash(approval_raw),
            "permissions": [action],
            "confirmations": approval["confirmations"],
            "oneUse": True,
        }
        authority_raw = _canonical(authority)
        _publish(authority_path, authority_raw)
        reservation_ref = None
        if reservation is not None:
            _require(reservation_receipt is not None, "reservation receipt required")
            assert reservation_receipt is not None
            reservation_value = _parse(reservation)
            self.trust.authenticate(
                "output_render_reservation",
                reservation_receipt,
                {
                    k: v
                    for k, v in reservation_value.items()
                    if k != "reservationReceiptSha256"
                },
            )
            _require(
                _read(self.journal.artifacts / _hash(reservation)) == reservation,
                "unowned reservation",
            )
            reservation_ref = {
                "path": str(self.journal.artifacts / _hash(reservation)),
                "sha256": _hash(reservation),
                "receiptPath": str(self.vault.root / _hash(reservation_receipt)),
                "receiptSha256": _hash(reservation_receipt),
            }
        intent = {
            "schemaVersion": INTENT_SCHEMA,
            "lane": LANE,
            "context": self.context,
            "action": action,
            "operationId": operation_id,
            "effectId": _json_hash(
                {
                    "chain": self.journal.chain,
                    "binding": _binding(self.context),
                    "action": action,
                    "sequence": sequence,
                }
            ),
            "sequence": sequence,
            "priorResultSha256": prior_head,
            "payloadSha256": _json_hash(payload),
            "authoritySha256": _hash(authority_raw),
            "reservationSha256": None if reservation is None else _hash(reservation),
            "createdAt": now,
        }
        intent_raw = _canonical(intent)
        _publish(intent_path, intent_raw)
        render_ref = None
        if render_intent is not None:
            path = self.journal.artifacts / self.journal._retain(render_intent)
            render_ref = {"path": str(path), "sha256": _hash(render_intent)}
        request = {
            "schemaVersion": REQUEST_SCHEMA,
            "lane": LANE,
            "profile": self.admission.profile,
            "action": action,
            "operationId": operation_id,
            "sequence": sequence,
            "priorResultSha256": prior_head,
            "context": self.context,
            "target": self.context["target"],
            "package": self.admission.native_package_ref(),
            "inputs": {
                "originalDocumentPath": str(self.admission.original_document_path),
                "originalDependenciesPath": str(
                    self.admission.original_dependencies_path
                ),
                "executionDocumentPath": str(self.admission.execution_document_path),
                "executionDependenciesPath": str(
                    self.admission.execution_dependencies_path
                ),
            },
            "sourceGraph": {
                "path": str(
                    self.journal.artifacts / self.context["nativeSourceGraphSha256"]
                ),
                "sha256": self.context["nativeSourceGraphSha256"],
            },
            "release": {
                "path": str(
                    self.journal.artifacts / self.context["installedReleaseSha256"]
                ),
                "sha256": self.context["installedReleaseSha256"],
            },
            "releaseManifestSha256": approval["releaseManifestSha256"],
            "renderIntent": render_ref,
            "authority": {"path": str(authority_path), "sha256": _hash(authority_raw)},
            "intent": {"path": str(intent_path), "sha256": _hash(intent_raw)},
            "reservation": reservation_ref,
            "payload": copy.deepcopy(payload),
            "resultPath": str(result_path),
        }
        if self.revised_preflight is not None:
            request["revisedPreflight"] = {
                "path": str(self.revised_preflight[0]),
                "sha256": self.revised_preflight[1],
            }
        raw = _canonical(request)
        verify_native_request(raw, expected_request_sha256=_hash(raw))
        _publish(request_path, raw)
        return request_path

    def _native_result(self, sequence: int) -> tuple[Path, str, Json]:
        from .qualification_output_native_v2 import (
            native_request_paths,
            verify_native_result,
        )

        result_path = native_request_paths(self.context, sequence)[0]
        raw = _read(result_path)
        digest = _hash(raw)
        result = verify_native_result(result_path, digest)
        _require(
            result["context"] == self.context
            and result["sequence"] == sequence
            and result["status"] == "complete",
            "complete native result for this session required",
        )
        return result_path, digest, result

    def _input_binding(self) -> tuple[bytes, Path]:
        path, digest, _ = self._native_result(1)
        raw = self.input_binding_from_native(path, digest)
        return raw, self.journal.artifacts / _hash(raw)

    def _pre_capture_inputs(
        self, *, validate_prediction: bool = True
    ) -> output.PredictionInputs:
        from .qualification_output_native_v2 import verify_native_request

        input_binding, input_path = self._input_binding()
        pre_sequence = self._render_sequences()[0]
        result_path, result_sha256, result = self._native_result(pre_sequence)
        request_path = Path(result["requestPath"])
        request_raw = _read(request_path)
        request = verify_native_request(
            request_raw, expected_request_sha256=result["requestSha256"]
        )
        _require(
            request["action"] in {"capture_pre", "retry_capture"}
            and request["payload"]
            == {
                "inputBindingPath": str(input_path),
                "inputBindingSha256": _hash(input_binding),
            }
            and _read(input_path) == input_binding,
            "pre-render request does not use the derived native binding",
        )
        inputs = self.capture_inputs(
            input_binding,
            result_path,
            result_sha256,
            validate_prediction=validate_prediction,
        )
        _require(
            isinstance(inputs, output.PredictionInputs),
            "pre-render prediction inputs required",
        )
        assert isinstance(inputs, output.PredictionInputs)
        return inputs

    def _latest_attempt(self) -> Json | None:
        prior = next(
            (
                row
                for row in reversed(self.journal.history())
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        if prior is not None:
            _require(
                prior["context"] == self.context,
                "attempt belongs to another invocation",
            )
        return prior

    def _attempt_materials(self, attempt: Json) -> dict[str, bytes]:
        _require(
            attempt["state"] in {"committed", "reserved_by_render_intent"},
            "live committed output attempt required",
        )
        commitment = _read(self.journal.artifacts / attempt["commitmentRawSha256"])
        commitment_value = _parse(commitment)
        commitment_receipt = _read(
            self.vault.root / commitment_value["commitmentReceiptSha256"]
        )
        prediction = _read(
            self.journal.artifacts / attempt["predictionBytesSha256"],
            maximum=48_000_000,
        )
        materials = {
            "commitment": commitment,
            "commitment_receipt": commitment_receipt,
            "prediction": prediction,
        }
        if attempt["state"] == "reserved_by_render_intent":
            reservation = _read(
                self.journal.artifacts / attempt["reservationRawSha256"]
            )
            reservation_value = _parse(reservation)
            render_intent = _read(
                self.journal.artifacts / reservation_value["renderIntentSha256"]
            )
            reservation_receipt = _read(
                self.vault.root / reservation_value["reservationReceiptSha256"]
            )
            materials.update(
                {
                    "reservation": reservation,
                    "reservation_receipt": reservation_receipt,
                    "render_intent": render_intent,
                }
            )
        return materials

    def _ensure_prediction(
        self, inputs: output.PredictionInputs
    ) -> tuple[bytes, bytes, bytes]:
        attempt = self._latest_attempt()
        if attempt is None or attempt["state"] in {"expired_unused", "render_failed"}:
            return self.publish_prediction(inputs)
        materials = self._attempt_materials(attempt)
        output.verify_prediction_commitment(
            inputs,
            materials["commitment"],
            materials["commitment_receipt"],
            materials["prediction"],
            trust=self.trust,
        )
        return (
            materials["commitment"],
            materials["commitment_receipt"],
            materials["prediction"],
        )

    def _prepare_render_intent(self, approval_path: Path, commitment: bytes) -> bytes:
        from .qualification_output_native_v2 import (
            RENDER_INTENT_SCHEMA,
            verify_operator_approval,
            verify_render_intent,
        )
        from .workflow_v2_cli import _verify_output_release

        self._environment_current()
        release_manifest = _verify_output_release(self.release_root)
        approval_raw = _read(approval_path)
        approval = verify_operator_approval(
            approval_raw,
            context=self.context,
            profile=self.admission.profile,
            admission_sha256=_hash(_read(self.admission.admission_path)),
            release_manifest_sha256=_hash(_read(release_manifest)),
            require_live=True,
        )
        value = {
            "schemaVersion": RENDER_INTENT_SCHEMA,
            "lane": LANE,
            "context": self.context,
            "commitmentRawSha256": _hash(commitment),
            "outputPath": approval["outputPath"],
            "settings": approval["settings"],
            "profile": self.admission.profile,
            "authorityPath": str(approval_path),
            "authoritySha256": _hash(approval_raw),
        }
        raw = _canonical(value)
        verify_render_intent(
            raw,
            context=self.context,
            commitment_sha256=_hash(commitment),
        )
        self.journal._retain(raw)
        return raw

    def _render_sequences(self) -> tuple[int, int, int, int, int]:
        from .qualification_output_native_v2 import native_request_paths

        retry_path = native_request_paths(self.context, 6)[0]
        if retry_path.exists():
            raw = _read(retry_path)
            if _parse(raw)["action"] == "retry_capture":
                self._native_result(6)
                return 6, 7, 8, 9, 10
        return 2, 3, 4, 5, 6

    def _render_lineage(self) -> bytes:
        _, queue_sequence, start_sequence, completion_sequence, _ = (
            self._render_sequences()
        )
        queued = self._native_result(queue_sequence)
        started = self._native_result(start_sequence)
        completed = self._native_result(completion_sequence)
        return self.render_lineage(
            queued=(queued[0], queued[1]),
            started=(started[0], started[1]),
            completed=(completed[0], completed[1]),
        )

    def prepare_next_native_request(self, approval_path: Path) -> Path:
        """Prepare exactly the next reviewed native action from the fixed chain."""
        from .qualification_output_native_v2 import (
            native_action,
            native_request_paths,
            next_native_operation,
        )

        sequence, _ = next_native_operation(self.context)
        action = native_action(self.context, sequence)
        payload: Json = {}
        reservation: bytes | None = None
        reservation_receipt: bytes | None = None
        render_intent: bytes | None = None

        (
            pre_sequence,
            queue_sequence,
            start_sequence,
            completion_sequence,
            post_sequence,
        ) = self._render_sequences()
        if sequence == pre_sequence:
            input_binding, input_path = self._input_binding()
            payload = {
                "inputBindingPath": str(input_path),
                "inputBindingSha256": _hash(input_binding),
            }
        elif sequence == queue_sequence:
            inputs = self._pre_capture_inputs()
            commitment, commitment_receipt, prediction = self._ensure_prediction(inputs)
            attempt = self._latest_attempt()
            _require(attempt is not None, "committed output attempt required")
            assert attempt is not None
            if attempt["state"] == "committed":
                render_intent = self._prepare_render_intent(approval_path, commitment)
                reservation, reservation_receipt = self.reserve(
                    inputs,
                    commitment=commitment,
                    commitment_receipt=commitment_receipt,
                    prediction=prediction,
                    render_intent=render_intent,
                )
            else:
                materials = self._attempt_materials(attempt)
                reservation = materials["reservation"]
                reservation_receipt = materials["reservation_receipt"]
                render_intent = materials["render_intent"]
            _require(
                reservation is not None
                and reservation_receipt is not None
                and render_intent is not None,
                "reserved render intent required for queue stage",
            )
            assert render_intent is not None
            intent = _parse(render_intent)
            payload = {
                "settings": intent["settings"],
                "outputPath": intent["outputPath"],
                "outputFilename": Path(intent["outputPath"]).stem,
            }
        elif sequence == start_sequence:
            _, _, queued = self._native_result(queue_sequence)
            attempt = self._latest_attempt()
            _require(attempt is not None, "reserved output attempt required")
            assert attempt is not None
            materials = self._attempt_materials(attempt)
            reservation = materials["reservation"]
            reservation_receipt = materials["reservation_receipt"]
            render_intent = materials["render_intent"]
            result_path = native_request_paths(self.context, queue_sequence)[0]
            payload = {
                "jobId": queued["jobId"],
                "queuedResultPath": str(result_path),
                "queuedResultSha256": _hash(_read(result_path)),
            }
        elif sequence == completion_sequence:
            _, _, started = self._native_result(start_sequence)
            attempt = self._latest_attempt()
            _require(attempt is not None, "reserved output attempt required")
            assert attempt is not None
            materials = self._attempt_materials(attempt)
            reservation = materials["reservation"]
            reservation_receipt = materials["reservation_receipt"]
            render_intent = materials["render_intent"]
            result_path = native_request_paths(self.context, start_sequence)[0]
            payload = {
                "jobId": started["jobId"],
                "startedResultPath": str(result_path),
                "startedResultSha256": _hash(_read(result_path)),
            }
        elif sequence == post_sequence:
            input_binding, input_path = self._input_binding()
            lineage = self._render_lineage()
            attempt = self._latest_attempt()
            _require(attempt is not None, "reserved output attempt required")
            assert attempt is not None
            materials = self._attempt_materials(attempt)
            reservation = materials["reservation"]
            reservation_receipt = materials["reservation_receipt"]
            render_intent = materials["render_intent"]
            lineage_path = self.journal.artifacts / _hash(lineage)
            completion_path = native_request_paths(self.context, completion_sequence)[0]
            payload = {
                "inputBindingPath": str(input_path),
                "inputBindingSha256": _hash(input_binding),
                "renderLineagePath": str(lineage_path),
                "renderLineageSha256": _hash(lineage),
                "completionResultPath": str(completion_path),
                "completionResultSha256": _hash(_read(completion_path)),
            }

        request_path = self.prepare_native_request(
            action,
            payload,
            approval_path=approval_path,
            reservation=reservation,
            reservation_receipt=reservation_receipt,
            render_intent=render_intent,
        )
        self._publish_native_operator_handoff(request_path, sequence, action)
        return request_path

    def _publish_native_operator_handoff(
        self, request_path: Path, sequence: int, action: str
    ) -> Path:
        """Retain the exact manual copy/install instructions for one native step."""
        from .workflow_v2_cli import _verify_output_release

        release_manifest = _verify_output_release(self.release_root)
        request_raw = _read(request_path)
        request = _parse(request_raw)
        release_manifest_sha256 = _hash(_read(release_manifest))
        _require(
            request["context"] == self.context
            and request["sequence"] == sequence
            and request["action"] == action
            and request["releaseManifestSha256"] == release_manifest_sha256
            and request["release"]["sha256"] == self.context["installedReleaseSha256"],
            "native handoff differs from the reviewed request/release",
        )
        handoff: Json = {
            "schemaVersion": "qualification-output-native-operator-handoff/v1",
            "lane": LANE,
            "context": self.context,
            "sequence": sequence,
            "action": action,
            "hostRequest": {
                "path": str(request_path),
                "sha256": _hash(request_raw),
            },
            "reviewedReleaseSource": {
                "root": str(self.release_root),
                "rootMeaning": "prepared reviewed output-release bundle to install",
                "manifestPath": str(release_manifest),
                "releaseManifestSha256": release_manifest_sha256,
                "normalizedContentSha256": self.context["installedReleaseSha256"],
            },
            "installedRequestRelativePath": "vera-delivery-v2/request.json",
            "manualFlow": {
                "sourceInstallRequiredForThisStage": sequence == 0,
                "initialSourceInstall": (
                    "Before sequence 0 only, quit Resolve and install the full "
                    "reviewed bundle through the accepted #109 manual flow. "
                    "Archive prior installed v2 entries together outside the "
                    "plugin root, then verify the installed inventory against "
                    "the raw and normalized release hashes above."
                ),
                "requestReplacement": [
                    "After the preceding integration invocation returns (after "
                    "initial source installation for sequence 0), archive the "
                    "prior installed request outside the plugin root if present.",
                    "Copy the exact host request bytes to the installed reviewed "
                    "release's vera-delivery-v2/request.json.",
                    "Make the installed request regular, single-link, mode "
                    "0400, and owned/readable by the Resolve user; compare its "
                    "SHA256 with hostRequest.sha256.",
                ],
                "launch": (
                    "After initial source installation and request copy, restart "
                    "Resolve, open the same saved target and launch once."
                    if sequence == 0
                    else "Keep Resolve running and the same saved target open. "
                    "Do not restart Resolve or change the reviewed source between "
                    "request-only stages, especially queue/start/poll/post. After "
                    "copying this request, launch the integration once."
                ),
                "manualFlowReference": "docs/resolve-workflow-integration-v1.md"
                "#manual-installation-and-update",
            },
        }
        if action == "observe_edited":
            handoff["manualFlow"]["beforeObservation"] = (
                "Perform and save the intended bounded edit on this same "
                "disposable target through Resolve's editor before launching "
                "observe_edited. This action only reads the actual edit; it "
                "does not construct clips or apply a planned geometry. Keep "
                "the original package and both original input files unchanged."
            )
        handoff_raw = _canonical(handoff)
        handoff_path = self.native_operator_handoff_path(request_path)
        _publish(handoff_path, handoff_raw)
        return handoff_path

    def native_operator_handoff_path(self, request_path: Path) -> Path:
        """Return the private host-artifact path without adding native slot files."""
        raw = _read(request_path)
        request = _parse(raw)
        _require(
            request["context"] == self.context and type(request["sequence"]) is int,
            "owned native request required for operator handoff path",
        )
        return self.journal.artifacts / (
            f"native-operator-handoff-{request['sequence']:08d}-{_hash(raw)}.json"
        )

    def ingest_native_result(self, result_path: Path, result_sha256: str) -> Json:
        """Authenticate one actual fixed-slot result and advance its host stage."""
        from .qualification_output_native_v2 import (
            native_request_paths,
            verify_native_result,
        )

        result = verify_native_result(result_path, result_sha256)
        sequence = result["sequence"]
        expected_path = native_request_paths(self.context, sequence)[0]
        _require(
            result_path.absolute() == expected_path
            and result["context"] == self.context,
            "native result belongs to another fixed session slot",
        )
        host_stage = "native_result_authenticated"
        if result["status"] != "complete":
            attempt = self._latest_attempt()
            if attempt is not None and attempt["state"] == "reserved_by_render_intent":
                if (
                    result["action"] == "poll_render"
                    and result["status"] == "partial"
                    and (result.get("renderStatus") or {}).get("JobStatus")
                    in {"Failed", "Cancelled"}
                ):
                    self.record_native_failure((result_path, result_sha256))
                    host_stage = "render_failure_retained"
                else:
                    self.record_uncertain((result_path, result_sha256))
                    host_stage = "attempt_marked_uncertain"
            return {
                "sequence": sequence,
                "action": result["action"],
                "status": result["status"],
                "resultSha256": result_sha256,
                "hostStage": host_stage,
            }

        if result["action"] in {"capture_pre", "retry_capture"}:
            self._ensure_prediction(self._pre_capture_inputs())
            host_stage = "prediction_committed"
        elif result["action"] == "poll_render":
            self._render_lineage()
            host_stage = "render_lineage_retained"
        elif result["action"] == "capture_post":
            host_stage = "post_capture_ready_to_finalize"
        return {
            "sequence": sequence,
            "action": result["action"],
            "status": result["status"],
            "resultSha256": result_sha256,
            "hostStage": host_stage,
        }

    def _retain_finalize_refusal(
        self, *, result_sha256: str, stage: str, error: Exception
    ) -> None:
        """Retain a post-capture refusal and close the attempt as uncertain."""
        value = {
            "schemaVersion": FINALIZE_REFUSAL_SCHEMA,
            "lane": LANE,
            "context": self.context,
            "capturePostResultSha256": result_sha256,
            "stage": stage,
            "errorType": type(error).__name__,
            "reason": str(error)[:1024],
        }
        raw = _canonical(value)
        digest = self.journal._retain(raw)
        marker = self.journal.directory / f"finalize-refusal-{digest}.json"
        if not marker.exists():
            _publish(marker, raw)
        rows = self.journal.history()
        prior = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        if prior is not None and prior["state"] == "reserved_by_render_intent":
            self.journal.transition(
                self.context,
                "uncertain",
                expected_head=rows[-1]["entrySha256"],
            )

    def inspect_recovery(self) -> Json:
        """Report fixed-chain recovery evidence without changing or retrying it."""
        from .qualification_output_native_v2 import (
            native_action,
            next_native_operation,
        )

        host_error = None
        try:
            rows = self.journal.history()
        except (OutputConsistencyError, OSError) as error:
            rows = []
            host_error = str(error)
        pending = [
            _recovery_file_record(path)
            for path in sorted(self.journal.directory.glob("pending-*.json"))[:4096]
        ]
        attempts = [
            row for row in rows if _binding(row["context"]) == _binding(self.context)
        ]
        latest = attempts[-1] if attempts else None
        if latest is not None and latest["context"] != self.context:
            host_error = "host attempt belongs to another invocation"
        native = _recovery_native_operations(self.context)
        finalize_refusals = _recovery_finalize_refusals(self.journal.directory)
        next_operation = None
        native_error = None
        exhausted = False
        sequence = None
        try:
            sequence, prior = (
                next_native_operation(self.context, retry=True)
                if latest is not None and latest["state"] == "render_failed"
                else next_native_operation(self.context)
            )
            next_operation = {
                "sequence": sequence,
                "action": native_action(self.context, sequence),
                "priorResultSha256": prior,
            }
        except (OutputConsistencyError, OSError) as error:
            exhausted = str(error) == "reviewed native action plan is exhausted"
            native_error = None if exhausted else str(error)
        host_history = [
            {"sequence": row["sequence"], "state": row["state"]} for row in rows
        ]
        records = pending + [
            record
            for slot in native
            for record in [
                slot[name] for name in ("request", "start", "intent", "result")
            ]
            + slot["effects"]
        ]
        records.extend(finalize_refusals)
        inventory_error = next(
            (record["error"] for record in records if "error" in record), None
        )
        any_native_file = any(
            record.get("sha256") or record.get("error") for record in records
        )
        status = "incomplete"
        if not host_error and not inventory_error:
            if not rows and not any_native_file and sequence == 0:
                status = "empty"
            elif latest is not None and latest["state"] == "uncertain":
                status = "uncertain"
            elif latest is not None and latest["state"] == "render_failed":
                status = "render_failed"
                if next_operation is not None:
                    next_operation["requiresExplicitRetryApproval"] = True
            elif (
                exhausted
                and latest is not None
                and latest["state"].startswith("compared_")
            ):
                status = "complete"
            elif next_operation is not None:
                status = "in_progress"
        refusal_reason = next(
            (
                record.get("reason")
                for record in reversed(finalize_refusals)
                if record.get("reason")
            ),
            None,
        )
        return {
            "reportType": "inventory_only_not_qualified_receipts",
            "status": status,
            "reason": host_error or inventory_error or native_error or refusal_reason,
            "hostJournal": {
                "authenticated": host_error is None,
                "history": host_history,
                "pending": pending,
                "finalizeRefusals": finalize_refusals,
            },
            "nativeOperations": native,
            "nextOperation": next_operation,
        }

    def _verified_final_capture(self, result_path: Path, result_sha256: str) -> int:
        """Authenticate this session's complete post-capture; return completion."""
        from .qualification_output_native_v2 import (
            native_request_paths,
            verify_native_result,
        )

        result = verify_native_result(result_path, result_sha256)
        _, _, _, completion_sequence, post_sequence = self._render_sequences()
        expected_path = native_request_paths(self.context, post_sequence)[0]
        _require(
            result_path.absolute() == expected_path
            and result["context"] == self.context
            and result["sequence"] == post_sequence
            and result["action"] == "capture_post"
            and result["status"] == "complete",
            "complete final native capture for this session required",
        )
        return completion_sequence

    def _retain_finalize_clock_record(
        self,
        *,
        result_sha256: str,
        stage: str,
        diagnostics: Json,
        outcome: str,
    ) -> None:
        """Retain private measured clock diagnostics for one finalize refusal."""
        raw = _canonical(
            {
                "schemaVersion": FINALIZE_CLOCK_SCHEMA,
                "lane": LANE,
                "context": self.context,
                "capturePostResultSha256": result_sha256,
                "stage": stage,
                "outcome": outcome,
                "diagnostics": diagnostics,
            }
        )
        digest = self.journal._retain(raw)
        marker = self.journal.directory / f"finalize-clock-{digest}.json"
        if not marker.exists():
            _publish(marker, raw)

    def _retain_request_clock_record(
        self, action: str, diagnostics: Json, outcome: str
    ) -> None:
        raw = _canonical(
            {
                "schemaVersion": "qualification-output-request-clock/v1",
                "lane": LANE,
                "context": self.context,
                "action": action,
                "outcome": outcome,
                "diagnostics": diagnostics,
            }
        )
        digest = self.journal._retain(raw)
        marker = self.journal.directory / f"request-clock-{digest}.json"
        if not marker.exists():
            _publish(marker, raw)

    def _prepare_clock_recheck(
        self,
        error: HostClockRegression,
        *,
        stage: str,
        result_sha256: str | None = None,
        action: str | None = None,
    ) -> bool:
        """Permit one full recheck after a bounded measured OS wall step.

        No later trusted reading may precede one already trusted, so expiry
        and chronology are never judged at an earlier wall time than before.
        The controller's own clock lag is bounded too before it is replaced.
        """
        diagnostics = dict(error.diagnostics)
        high_water = max(
            datetime.fromisoformat(diagnostics["priorWall"]), self.trust.wall
        )
        sample = _REQUEST_CLOCK_SAMPLE.get()
        if sample:
            high_water = max(high_water, sample[0][0])
        permitted = error.recheckable
        wall, monotonic = self.trust.wall, self.trust.monotonic
        if permitted:
            deadline = time.monotonic() + FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS
            while datetime.now(UTC) < high_water and time.monotonic() < deadline:
                time.sleep(0.01)
            # Wall before monotonic, as in _ControllerTrust.__init__.
            wall = datetime.now(UTC)
            monotonic = time.monotonic()
            controller_lag = (monotonic - self.trust.monotonic) - (
                wall - self.trust.wall
            ).total_seconds()
            diagnostics["controllerLagSeconds"] = controller_lag
            # Monotonic behind the controller's own anchor is a regression no
            # bounded wall step can explain, whatever another controller saw.
            permitted = (
                wall >= high_water
                and monotonic >= self.trust.monotonic
                and (not sample or monotonic >= sample[0][1])
                and controller_lag <= FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS
            )
        outcome = "recheck" if permitted else "terminal"
        if action is not None:
            self._retain_request_clock_record(action, diagnostics, outcome)
        else:
            assert result_sha256 is not None
            self._retain_finalize_clock_record(
                result_sha256=result_sha256,
                stage=stage,
                diagnostics=diagnostics,
                outcome=outcome,
            )
        if permitted:
            # Anchor to the validated readings, so a rollback during the
            # bookkeeping above is still caught by the next checked_now.
            trust = _ControllerTrust(self.vault, self.admission)
            trust.wall, trust.monotonic = wall, monotonic
            self.trust = trust
            if sample is not None:
                sample[:] = [(wall, monotonic)]
        return permitted

    def finalize_output(self, result_path: Path, result_sha256: str) -> Path:
        """Decode the delivered MOV and append the terminal comparison receipt.

        A bounded host wall-clock step permits exactly one complete recheck;
        every other refusal, or a second one, retains the slot as uncertain.
        """
        completion_sequence = self._verified_final_capture(result_path, result_sha256)
        path = self._finalize_attempt(
            result_path, result_sha256, completion_sequence, recheck=False
        )
        if path is None:
            path = self._finalize_attempt(
                result_path, result_sha256, completion_sequence, recheck=True
            )
            assert path is not None
        return path

    def _finalize_attempt(
        self,
        result_path: Path,
        result_sha256: str,
        completion_sequence: int,
        *,
        recheck: bool,
    ) -> Path | None:
        stage = "post_capture_authentication"
        try:
            if recheck:
                _require(
                    self._verified_final_capture(result_path, result_sha256)
                    == completion_sequence,
                    "complete final native capture for this session required",
                )
            self._environment_current()
            # A valid reservation permits historical pre-capture comparison
            # after the approval/geometry live window. Environment, source and
            # input bytes remain currentness-checked by these helpers.
            inputs = self._pre_capture_inputs(validate_prediction=False)
            attempt = self._latest_attempt()
            _require(
                attempt is not None and attempt["state"] == "reserved_by_render_intent",
                "reserved output attempt required for final comparison",
            )
            assert attempt is not None
            materials = self._attempt_materials(attempt)
            lineage = self._render_lineage()
            stage = "post_capture_geometry"
            post_capture = self.capture_inputs(
                inputs.input_binding,
                result_path,
                result_sha256,
                lineage=lineage,
                validate_prediction=False,
            )
            _require(
                isinstance(post_capture, tuple),
                "post-render capture receipt required",
            )
            assert isinstance(post_capture, tuple)
            post_geometry, post_geometry_receipt = post_capture
            completion = self._native_result(completion_sequence)
            stage = "decode"
            decode_record, decode_receipt, decoded_samples = self.decode_output(
                lineage=lineage,
                completion=(completion[0], completion[1]),
                commitment=materials["commitment"],
            )
            completed = output.CommittedOutput(
                inputs=inputs,
                commitment=materials["commitment"],
                commitment_receipt=materials["commitment_receipt"],
                prediction=materials["prediction"],
                reservation=materials["reservation"],
                reservation_receipt=materials["reservation_receipt"],
                post_geometry=post_geometry,
                post_geometry_receipt=post_geometry_receipt,
                decode_record=decode_record,
                decode_receipt=decode_receipt,
                decoded_samples=decoded_samples,
                lineage=lineage,
                ledger=self.journal.history(),
            )
            stage = "comparison"
            comparison, _ = self.compare(completed)
            return self.journal.artifacts / _hash(comparison)
        except (OutputConsistencyError, OSError, ValueError) as error:
            if isinstance(error, HostClockRegression):
                with suppress(OutputConsistencyError, OSError, ValueError):
                    if recheck:
                        self._retain_finalize_clock_record(
                            result_sha256=result_sha256,
                            stage=stage,
                            diagnostics=error.diagnostics,
                            outcome="terminal",
                        )
                    elif self._prepare_clock_recheck(
                        error, result_sha256=result_sha256, stage=stage
                    ):
                        return None
            # The complete post-capture result has already been authenticated;
            # preserve the refusal and prevent a retry from the reserved slot.
            with suppress(OutputConsistencyError, OSError, ValueError):
                self._retain_finalize_refusal(
                    result_sha256=result_sha256, stage=stage, error=error
                )
            raise

    def prepare_operator_plan(self, plan_path: Path, *, retry: bool = False) -> Path:
        """Prepare a reviewable exact plan; this does not issue authority."""
        from .qualification_output_native_v2 import (
            APPROVAL_SCHEMA,
            CONFIRMATIONS,
            MAX_POLL_COUNT,
            RETRY_ACTION_PLAN,
            _settings_for_timeline,
            action_plan_for_context,
            render_parent,
        )
        from .workflow_v2_cli import RELEASE_NAME, _verify_output_release

        self.admission.assert_current()
        release_manifest = _verify_output_release(self.release_root)
        _require(
            release_manifest == self.release_root / RELEASE_NAME / "release.json",
            "release root differs",
        )
        output_parent = render_parent(self.context)
        _safe(output_parent)
        output_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require(
            output_parent.stat().st_uid == os.getuid()
            and output_parent.stat().st_mode & 0o077 == 0,
            "private output parent required",
        )
        issued = self.trust.checked_now()
        plan = {
            "schemaVersion": APPROVAL_SCHEMA,
            "lane": LANE,
            "approvalId": str(uuid.uuid4()),
            "operator": pwd.getpwuid(os.getuid()).pw_name,
            "issuedAt": issued.isoformat().replace("+00:00", "Z"),
            "expiresAt": (issued + timedelta(minutes=30))
            .isoformat()
            .replace("+00:00", "Z"),
            "invocationId": self.context["invocationId"],
            "context": self.context,
            "target": self.context["target"],
            "profile": self.admission.profile,
            "releaseManifestSha256": _hash(_read(release_manifest)),
            "installedReleaseSha256": self.context["installedReleaseSha256"],
            "packageRoot": str(self.admission.package_root),
            "packageSha256": self.context["packageSha256"],
            "admissionSha256": _hash(_read(self.admission.admission_path)),
            "sourceGraphSha256": self.context["nativeSourceGraphSha256"],
            "outputPath": str(
                output_parent
                / (
                    self.context["binding"]["bindingSha256"]
                    + ("-retry-1.mov" if retry else ".mov")
                )
            ),
            "settings": _settings_for_timeline(self.admission.manifest["timeline"]),
            "actionPlan": list(
                RETRY_ACTION_PLAN if retry else action_plan_for_context(self.context)
            ),
            "maxPolls": MAX_POLL_COUNT,
            "confirmations": CONFIRMATIONS,
            "oneUse": True,
        }
        # Keep the prepared artifact a proposal with a distinct schema/status.
        # Only the explicit attended/agent-mediated issuer creates approval bytes.
        proposal = {
            **plan,
            "schemaVersion": OPERATOR_PROPOSAL_SCHEMA,
            "proposalStatus": OPERATOR_PLAN_STATUS,
        }
        raw = _canonical(
            {
                "schemaVersion": OPERATOR_PLAN_SCHEMA,
                "lane": LANE,
                "authorityStatus": OPERATOR_PLAN_STATUS,
                "proposal": proposal,
            }
        )
        _publish(plan_path, raw)
        return plan_path

    def prepare_render_retry_plan(self, plan_path: Path) -> Path:
        """Propose one fresh authority after a confirmed terminal render failure."""
        from .qualification_output_native_v2 import (
            next_native_operation,
            verified_render_failure,
        )

        self._environment_current()
        sequence, _ = next_native_operation(self.context, retry=True)
        _require(sequence == 6, "only the first failed render may be retried")
        _, digest, _ = verified_render_failure(self.context)
        latest = self._latest_attempt()
        _require(
            latest is not None
            and latest["state"] == "render_failed"
            and latest["resultRawSha256"] == digest,
            "authenticated render failure must be ingested before retry",
        )
        return self.prepare_operator_plan(plan_path, retry=True)

    def prepare_render_retry_request(self, approval_path: Path) -> Path:
        """Consume the fresh retry approval for a read-only saved-target check."""
        from .qualification_output_native_v2 import RETRY_ACTION_PLAN

        _require(
            _parse(_read(approval_path))["actionPlan"] == list(RETRY_ACTION_PLAN),
            "fresh bounded retry approval required",
        )
        latest = self._latest_attempt()
        _require(
            latest is not None and latest["state"] == "render_failed",
            "confirmed render failure required",
        )
        binding, path = self._input_binding()
        request = self.prepare_native_request(
            "retry_capture",
            {"inputBindingPath": str(path), "inputBindingSha256": _hash(binding)},
            approval_path=approval_path,
        )
        self._publish_native_operator_handoff(request, 6, "retry_capture")
        return request

    def prepare_operator_replan(self, plan_path: Path) -> Path:
        """Prepare a fresh review-only proposal for this exact existing session."""
        from .qualification_output_native_v2 import (
            APPROVAL_ACTION_PLAN,
            next_native_operation,
        )

        rows = self.journal.history()
        latest = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        _require(
            latest is None
            or latest["state"] in {"committed", "reserved_by_render_intent"},
            "only an unfinished nonterminal session may be replanned",
        )
        sequence, _ = next_native_operation(self.context)
        _require(
            sequence < len(APPROVAL_ACTION_PLAN),
            "completed output session cannot be replanned",
        )
        self._environment_current()
        return self.prepare_operator_plan(plan_path)

    @classmethod
    def from_revised(
        cls,
        root: Path,
        *,
        admission: Any,
        release_root: Path,
        target: Json,
        case_id: str,
        invocation_id: str,
        revised_preflight_path: Path,
        revised_preflight_sha256: str,
    ) -> QualificationOutputController:
        return cls(
            root,
            admission=admission,
            release_root=release_root,
            target=target,
            case_id=case_id,
            phase="rebuild",
            invocation_id=invocation_id,
            revised_preflight=(revised_preflight_path, revised_preflight_sha256),
        )

    def input_binding_from_native(self, result_path: Path, result_sha256: str) -> bytes:
        """Derive native UID mappings only from the audited complete readback."""
        from .qualification_output_native_v2 import verify_native_result

        result = verify_native_result(result_path, result_sha256)
        _require(
            result["context"] == self.context and result["status"] == "complete",
            "complete native readback for this context required",
        )
        geometry = result["nativeGeometry"]
        _require(geometry["context"] == self.context, "native geometry context differs")
        view = self.admission.view
        binding = {
            "schemaVersion": "qualification-output-inputs/v1",
            "lane": LANE,
            "context": self.context,
            "delivery": sorted(
                [
                    {
                        "eventId": row["id"],
                        "kind": row["kind"],
                        "recordRange": row["recordRange"],
                        "sourceRange": row["sourceRange"],
                    }
                    for row in view["events"]
                ],
                key=lambda row: row["eventId"],
            ),
            "sourceEntries": self.admission.source_entries,
            "tracks": geometry["tracks"],
            "itemMappings": sorted(
                [
                    {
                        key: item[key]
                        for key in ("itemUid", "eventId", "sourceId", "mediaUid")
                    }
                    for item in geometry["items"]
                ],
                key=lambda row: row["itemUid"],
            ),
            "nativeSources": sorted(
                [
                    {
                        "sourceId": row["id"],
                        "nativeSourceSha256": row["contentHash"].removeprefix(
                            "sha256:"
                        ),
                    }
                    for row in view["sources"]
                ],
                key=lambda row: row["sourceId"],
            ),
        }
        raw = _canonical(binding)
        self.journal._retain(raw)
        return raw

    def capture_inputs(
        self,
        input_binding: bytes,
        result_path: Path,
        result_sha256: str,
        *,
        lineage: bytes | None = None,
        validate_prediction: bool = True,
    ) -> output.PredictionInputs | tuple[bytes, bytes]:
        from .qualification_output_native_v2 import verify_native_result

        result = verify_native_result(result_path, result_sha256)
        binding = _parse(input_binding)
        _require(
            binding["context"] == result["context"] == self.context
            and result["status"] == "complete",
            "native capture context/status differs",
        )
        envelope = result["geometryEnvelope"]
        _require(
            envelope["inputBindingSha256"] == _hash(input_binding)
            and envelope["geometry"]["context"] == self.context,
            "native capture input binding differs",
        )
        payload = {**envelope, "inputBinding": binding}
        evidence: tuple[bytes, ...] = (_read(result_path), input_binding)
        if lineage is not None:
            payload["renderLineage"] = _parse(lineage)
            evidence = (*evidence, lineage)
        else:
            _require(
                envelope["capturePhase"] == "pre_render", "pre-render capture required"
            )
            self.admission.assert_current()
        receipt = self.vault._issue("output_geometry_snapshot", payload, evidence)
        raw = _canonical({**envelope, "receiptSha256": _hash(receipt)})
        if lineage is not None:
            return raw, receipt
        inputs = output.PredictionInputs(
            input_binding,
            raw,
            receipt,
            self.blobs,
            self.admission.source_wavs,
            self.admission.source_proofs,
        )
        if validate_prediction:
            output.validate_prediction_intent(inputs, trust=self.trust)
        return inputs

    def publish_prediction(
        self, inputs: output.PredictionInputs
    ) -> tuple[bytes, bytes, bytes]:
        self._current(inputs)
        prediction = output.create_prediction(
            inputs, trust=self.trust, ledger=self.journal.history()
        )
        payload = _parse(prediction.payload)
        receipt = self.vault._issue(
            "output_prediction_commitment",
            payload,
            (
                inputs.input_binding,
                inputs.geometry,
                inputs.geometry_receipt,
                prediction.payload,
                prediction.pcm,
            ),
        )
        commitment = _canonical({**payload, "commitmentReceiptSha256": _hash(receipt)})
        output.verify_prediction_commitment(
            inputs, commitment, receipt, prediction.pcm, trust=self.trust
        )
        self.journal.commit(self.context, commitment, prediction.pcm)
        return commitment, receipt, prediction.pcm

    def reserve(
        self,
        inputs: output.PredictionInputs,
        *,
        commitment: bytes,
        commitment_receipt: bytes,
        prediction: bytes,
        render_intent: bytes,
    ) -> tuple[bytes, bytes]:
        """Reserve once after a current authenticated pre-capture and exact intent."""
        self._current(inputs)
        checked = output.verify_prediction_commitment(
            inputs, commitment, commitment_receipt, prediction, trust=self.trust
        )
        from .qualification_output_native_v2 import verify_render_intent

        intent = verify_render_intent(
            render_intent, context=self.context, commitment_sha256=_hash(commitment)
        )
        output_path = Path(intent["outputPath"])
        _safe(output_path)
        _require(not output_path.exists(), "output exists before render reservation")
        rows = self.journal.history()
        _require(bool(rows), "persisted commitment required")
        prior = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        _require(
            prior is not None
            and prior["state"] == "committed"
            and prior["commitmentRawSha256"] == _hash(commitment),
            "attempt already reserved",
        )
        payload = {
            "schemaVersion": "qualification-output-reservation/v1",
            "lane": LANE,
            "context": self.context,
            "commitmentRawSha256": _hash(commitment),
            "commitmentPayloadSha256": _json_hash(
                {k: v for k, v in checked.items() if k != "commitmentReceiptSha256"}
            ),
            "renderIntentSha256": _hash(render_intent),
            "reservationId": _json_hash(
                {
                    "binding": _binding(self.context),
                    "chain": self.journal.chain,
                    "commitmentRawSha256": _hash(commitment),
                    "renderIntentSha256": _hash(render_intent),
                }
            ),
            "reservedAt": self.trust.checked_now().isoformat().replace("+00:00", "Z"),
        }
        receipt = self.vault._issue(
            "output_render_reservation",
            payload,
            (commitment, commitment_receipt, render_intent),
        )
        raw = _canonical({**payload, "reservationReceiptSha256": _hash(receipt)})
        self.journal.transition(
            self.context,
            "reserved_by_render_intent",
            expected_head=rows[-1]["entrySha256"],
            reservation=raw,
        )
        return raw, receipt

    def render_lineage(
        self,
        *,
        queued: tuple[Path, str],
        started: tuple[Path, str],
        completed: tuple[Path, str],
    ) -> bytes:
        """Bind the exact job and the authenticated complete native attempt chain."""
        from .qualification_output_native_v2 import (
            _verification_scope,
            verify_native_result,
        )

        with _verification_scope():
            queue, start, completion = [
                verify_native_result(path, digest)
                for path, digest in (queued, started, completed)
            ]
        for result, action in (
            (queue, "queue_render"),
            (start, "start_render"),
            (completion, "poll_render"),
        ):
            _require(
                result["context"] == self.context
                and result["action"] == action
                and result["status"] == "complete",
                "actual native render stage required",
            )
        for field in (
            "jobId",
            "outputPath",
            "settings",
            "commitmentRawSha256",
            "reservationSha256",
            "renderIntentSha256",
        ):
            _require(
                queue[field] == start[field] == completion[field],
                "native render job/settings/output lineage differs",
            )
        _require(
            start["queuedResultSha256"] == queued[1],
            "native start belongs to another queue",
        )
        _require(
            completion["queuedResultSha256"] == queued[1]
            and completion["startedResultSha256"] == started[1],
            "native completion belongs to another queue/start pair",
        )
        _require(
            datetime.fromisoformat(start["startedAt"])
            <= datetime.fromisoformat(completion["completedAt"]),
            "native completion precedes start",
        )
        rows = self.journal.history()
        prior = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        _require(
            prior is not None
            and prior["state"] == "reserved_by_render_intent"
            and prior["reservationRawSha256"] == queue["reservationSha256"]
            and prior["commitmentRawSha256"] == queue["commitmentRawSha256"],
            "native render has no complete owned reservation",
        )
        lineage = {
            "schemaVersion": "qualification-output-lineage/v1",
            "lane": LANE,
            "context": self.context,
            "commitmentRawSha256": queue["commitmentRawSha256"],
            "reservationRawSha256": queue["reservationSha256"],
            "renderIntentSha256": queue["renderIntentSha256"],
            "effectReceiptSha256": queued[1],
            "startReceiptSha256": started[1],
            "completionReceiptSha256": completed[1],
            "jobId": queue["jobId"],
            "sourceOutputRawSha256": completion["sourceOutputRawSha256"],
        }
        raw = _canonical(lineage)
        self.journal._retain(raw)
        return raw

    def decode_output(
        self, *, lineage: bytes, completion: tuple[Path, str], commitment: bytes
    ) -> tuple[bytes, bytes, bytes]:
        """Run the fixed decoder against the actual job's same delivered MOV."""
        from .qualification_output_decode_v2 import (
            VerifiedRenderLineage,
            decode_delivered_mov,
        )
        from .qualification_output_native_v2 import verify_native_result

        native = verify_native_result(*completion)
        value = _parse(lineage)
        _require(
            value["context"] == self.context
            and native["context"] == self.context
            and value["completionReceiptSha256"] == completion[1]
            and native["status"] == "complete"
            and native["action"] == "poll_render"
            and native["sourceOutputRawSha256"] == value["sourceOutputRawSha256"]
            and native["jobId"] == value["jobId"],
            "actual native completion differs",
        )
        # Lineage must be one previously constructed and retained by this owner.
        _require(
            _read(self.journal.artifacts / _hash(lineage)) == lineage,
            "unowned native lineage",
        )
        # The committed extent: the admitted interval, or the shorter extent of
        # an authenticated linked ripple trim. Never padded to the package.
        committed = _parse(commitment)
        _require(
            _hash(commitment) == value["commitmentRawSha256"]
            and committed["context"] == self.context
            and type(committed["extentFrames"]) is int
            and 0
            < committed["extentFrames"]
            <= self.admission.manifest["timeline"]["durationFrames"],
            "decode extent is not this attempt's committed extent",
        )
        timeline = self.admission.manifest["timeline"]
        decoded = decode_delivered_mov(
            Path(native["outputPath"]),
            context=self.context,
            expected_output_sha256=value["sourceOutputRawSha256"],
            expected_extent_frames=committed["extentFrames"],
            expected_width=timeline["width"],
            expected_height=timeline["height"],
            render_lineage=VerifiedRenderLineage(value),
        )
        receipt = self.vault._issue(
            "output_decode_record",
            {**decoded.record, "renderLineage": value},
            (
                _read(completion[0]),
                lineage,
                decoded.decoded_samples,
                _canonical(decoded.record),
            ),
        )
        raw = _canonical({**decoded.record, "decodeReceiptSha256": _hash(receipt)})
        self.journal._retain(raw)
        self.journal._retain(decoded.decoded_samples)
        return raw, receipt, decoded.decoded_samples

    def compare(self, completed: output.CommittedOutput) -> tuple[bytes, bytes]:
        self._environment_current()
        _require(
            _parse(completed.inputs.input_binding)["context"] == self.context,
            "completed context differs",
        )
        # Always use the complete persistent history, never the supplied prefix.
        from dataclasses import replace

        completed = replace(completed, ledger=self.journal.history())
        payload = output.compare_committed_output(completed, trust=self.trust)
        receipt = self.vault._issue(
            "output_residual_comparison",
            payload,
            (
                completed.commitment,
                completed.reservation,
                completed.lineage,
                completed.decode_record,
                completed.post_geometry,
                _canonical(payload),
            ),
        )
        raw = _canonical({**payload, "comparisonReceiptSha256": _hash(receipt)})
        self.journal.transition(
            self.context,
            payload["status"],
            expected_head=payload["priorLedgerHeadSha256"],
            result=raw,
        )
        return raw, receipt

    def expire_unused(self) -> Json:
        """Only a never-reserved expired commitment can be recommitted."""
        rows = self.journal.history()
        prior = next(
            (
                row
                for row in reversed(rows)
                if _binding(row["context"]) == _binding(self.context)
            ),
            None,
        )
        _require(
            prior is not None and prior["state"] == "committed",
            "only unused commitment may expire",
        )
        assert prior is not None
        raw = _read(self.journal.artifacts / prior["commitmentRawSha256"])
        value = _parse(raw)
        receipt = _read(self.vault.root / value["commitmentReceiptSha256"])
        self.trust.authenticate(
            "output_prediction_commitment",
            receipt,
            {k: v for k, v in value.items() if k != "commitmentReceiptSha256"},
        )
        _require(
            datetime.fromisoformat(value["expiresAt"]) < self.trust.checked_now(),
            "unused commitment has not expired",
        )
        return self.journal.transition(
            self.context, "expired_unused", expected_head=rows[-1]["entrySha256"]
        )

    def record_uncertain(self, native_result: tuple[Path, str]) -> Json:
        """Retain the actual failed/partial effect; never authorize a retry."""
        from .qualification_output_native_v2 import verify_native_result

        value = verify_native_result(*native_result)
        _require(
            value["context"] == self.context
            and value["status"] in {"refused", "partial", "uncertain"},
            "actual failed native result required",
        )
        self.journal._retain(_read(native_result[0]))
        rows = self.journal.history()
        _require(bool(rows), "owned attempt required")
        return self.journal.transition(
            self.context, "uncertain", expected_head=rows[-1]["entrySha256"]
        )

    def record_native_failure(self, native_result: tuple[Path, str]) -> Json:
        """Retain a confirmed failed job; a fresh approval still gates retry."""
        from .qualification_output_native_v2 import verify_native_result

        value = verify_native_result(*native_result)
        raw = _read(native_result[0])
        _require(
            _hash(raw) == native_result[1], "native failure changed after verification"
        )
        _require(
            value["context"] == self.context
            and value["status"] == "partial"
            and value["action"] == "poll_render"
            and (value.get("renderStatus") or {}).get("JobStatus")
            in {"Failed", "Cancelled"},
            "actual terminal render failure required",
        )
        rows = self.journal.history()
        _require(bool(rows), "owned attempt required")
        return self.journal.transition(
            self.context,
            "render_failed",
            expected_head=rows[-1]["entrySha256"],
            result=raw,
        )
