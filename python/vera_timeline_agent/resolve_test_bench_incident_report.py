"""Read-only, non-authoritative Test Bench incident and evidence inventory.

No Resolve/SDK imports, carrier calls, repair, replay, native-result verifier or
filesystem writes. Diagnostic claims remain separate from signed native proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from . import resolve_test_bench_diagnostic_journal as journal
from . import resolve_test_bench_diagnostics as contract

REPORT_SCHEMA = "vera.test-bench-incident-report/v1"
STAGES = ("pristine", "edited", "revision", "rebuild")
MAX_ROOTS = 8
MAX_MAP_BYTES = 65536
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


class IncidentReadError(ValueError):
    """Malformed, over-quota, private or conflicting evidence; never repair."""


def _require(condition: bool, explanation: str) -> None:
    if not condition:
        raise IncidentReadError(explanation)


def _directory(fd: int) -> None:
    info = os.fstat(fd)
    _require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and not info.st_mode & 0o077,
        "diagnostic directories must be private and owner-only",
    )


def _open_directory(name: str | Path, *, parent: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(name, flags, dir_fd=parent)
    try:
        _directory(fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_regular(
    name: str | Path, limit: int, *, parent: int | None = None, private: bool
) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_NOATIME", 0)
    fd = os.open(name, flags, dir_fd=parent)
    try:
        info = os.fstat(fd)
        _require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and (
                not private or (info.st_uid == os.getuid() and not info.st_mode & 0o077)
            )
            and 0 <= info.st_size <= limit,
            "unsafe or oversized incident input",
        )
        raw = os.read(fd, limit + 1)
        _require(len(raw) <= limit and not os.read(fd, 1), "input exceeds quota")
        _require(os.fstat(fd).st_size == len(raw), "file changed during read")
        return raw
    finally:
        os.close(fd)


def _read_chain(
    root: Path, case_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _require(root.is_absolute() and ".." not in root.parts, "unsafe case root")
    _require(
        not any(p.is_symlink() for p in (root, *root.parents)), "symlink case root"
    )
    root_fd = _open_directory(root)
    try:
        diag_fd = _open_directory("diagnostics-v1", parent=root_fd)
        try:
            records_fd = _open_directory("records", parent=diag_fd)
            try:
                names = sorted(os.listdir(records_fd))
                _require(len(names) <= journal.MAX_RECORDS, "record-count quota")
                records: list[dict[str, Any]] = []
                inventory: list[dict[str, Any]] = []
                previous: str | None = None
                anchor: tuple[object, ...] | None = None
                for index, name in enumerate(names):
                    _require(
                        name == f"record-{index:06d}.json",
                        "record gap or unexpected file",
                    )
                    raw = _read_regular(
                        name, contract.MAX_RECORD_BYTES, parent=records_fd, private=True
                    )
                    try:
                        obj = json.loads(raw)
                        _require(
                            contract.canonical_bytes(obj) == raw, "noncanonical record"
                        )
                    except (ValueError, TypeError, KeyError) as error:
                        raise IncidentReadError(
                            "malformed diagnostic record"
                        ) from error
                    _require(
                        obj["recordIndex"] == index
                        and obj["previousRecordSha256"] == previous,
                        "diagnostic hash chain broken",
                    )
                    ident = obj["identity"]
                    _require(ident["caseId"] == case_id, "unrelated case in records")
                    fixed = (
                        ident["caseId"],
                        ident["jobId"],
                        ident["operationId"],
                        ident["phase"],
                        ident["stage"],
                        obj["pins"],
                    )
                    if anchor is not None:
                        _require(
                            fixed == anchor, "record chain identity or pins changed"
                        )
                    anchor = fixed
                    previous = hashlib.sha256(raw).hexdigest()
                    records.append(obj)
                    inventory.append(
                        {
                            "role": "diagnostic_record",
                            "sha256": previous,
                            "sizeBytes": len(raw),
                            "relativeName": name,
                            "verifiedByReader": True,
                        }
                    )
                return records, inventory
            finally:
                os.close(records_fd)
        finally:
            os.close(diag_fd)
    finally:
        os.close(root_fd)


def _timeline(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    timeline: list[dict[str, Any]] = []
    warnings: list[str] = []
    earlier: dict[str, Any] | None = None
    elapsed_ns = 0
    comparable = bool(records)
    for record in records:
        clock = record["clock"]
        delta: int | None = None
        if earlier is not None:
            if datetime.fromisoformat(
                clock["utc"].replace("Z", "+00:00")
            ) < datetime.fromisoformat(earlier["utc"].replace("Z", "+00:00")):
                warnings.append(
                    "Wall clock moved backwards; UTC does not establish duration"
                )
            if (
                clock["pid"] == earlier["pid"]
                and clock["monotonicNs"] >= earlier["monotonicNs"]
            ):
                delta = clock["monotonicNs"] - earlier["monotonicNs"]
                elapsed_ns += delta
            else:
                comparable = False
                warnings.append(
                    "Process/monotonic clock boundary prevents elapsed-time inference"
                )
        timeline.append(
            {
                "recordIndex": record["recordIndex"],
                "stage": record["identity"]["stage"],
                "event": record["event"],
                "boundary": record["boundary"],
                "status": record["status"],
                "proofLayerClaim": record["proofLayer"],
                "utc": clock["utc"],
                "pid": clock["pid"],
                "monotonicNs": clock["monotonicNs"],
                "deltaFromPriorNs": delta,
            }
        )
        earlier = clock
    return (
        timeline,
        {
            "monotonicNs": elapsed_ns if comparable else None,
            "basis": "single-process monotonic deltas; boot identity unproven"
            if comparable
            else "unknown across process/clock boundary",
        },
        list(dict.fromkeys(warnings)),
    )


def report_from_diagnostics(roots: Sequence[Path], *, case_id: str) -> dict[str, Any]:
    """Inspect private case roots without following media pointers."""
    _require(bool(_ID.fullmatch(case_id)), "unsafe case identifier")
    _require(1 <= len(roots) <= MAX_ROOTS, "case-root quota")
    _require(len({str(root) for root in roots}) == len(roots), "duplicate case root")
    inventory: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    source_pin: str | None = None
    actor_pin: str | None = None
    seen_stages: set[str] = set()
    warnings = [
        "Diagnostic events are claims, not independent signed native authentication",
        "No Resolve, native verifier, or signed M4 receipt is opened by this reader",
    ]
    for root in roots:
        records, record_inventory = _read_chain(root, case_id)
        _require(bool(records), "empty diagnostic chain: missing incident identity")
        first = records[0]
        stage = first["identity"]["stage"] or first["identity"]["phase"]
        _require(stage not in seen_stages, "duplicate stage root")
        seen_stages.add(stage)
        for key, prior in (
            ("frozenSourceSha256", source_pin),
            ("actorSha256", actor_pin),
        ):
            current = first["pins"][key]
            _require(
                prior is None or current is None or prior == current,
                "cross-stage source/actor mismatch",
            )
        source_pin = source_pin or first["pins"]["frozenSourceSha256"]
        actor_pin = actor_pin or first["pins"]["actorSha256"]
        inventory.extend({"stage": stage, **item} for item in record_inventory)
        for record in records:
            for ref in record["evidence"]:
                inventory.append(
                    {
                        "stage": stage,
                        **ref,
                        "verifiedByReader": False,
                        "note": "declared SHA-256/locator only; artifact never opened",
                    }
                )
        carrier_claims = {
            (r["identity"]["nativeSequence"], r["identity"]["action"], r["proofSha256"])
            for r in records
            if r["event"] == "carrier_result"
            and r["proofLayer"] == "authenticated_native_result"
            and r["status"] == "observed"
        }
        ingested_claims = {
            (
                r["lastVerified"]["nativeSequence"],
                r["lastVerified"]["action"],
                r["lastVerified"]["resultSha256"],
            )
            for r in records
            if r["event"] == "ingestion"
            and r["boundary"] == "after_ingest"
            and r["lastVerified"] is not None
        }
        signed_claims = sum(
            r["event"] == "m4_receipt" and r["proofLayer"] == "signed_m4_receipt"
            for r in records
        )
        cursor = next(
            (
                r["lastVerified"]
                for r in reversed(records)
                if r["lastVerified"] is not None
            ),
            None,
        )
        # The final null cursor clears earlier pending actions; never elevate
        # a stale historical cursor into a false missing native request.
        pending = records[-1]["nextPending"]
        timeline, duration, clock_warnings = _timeline(records)
        warnings.extend(clock_warnings)
        stages.append(
            {
                "name": stage,
                "diagnosticRecords": len(records),
                "authenticatedNativeResultClaims": len(carrier_claims),
                "hostIngestedActionClaims": len(ingested_claims),
                "signedM4ReceiptClaims": signed_claims,
                "signedM4ReceiptsVerifiedByReader": 0,
                "lastVerifiedClaim": cursor,
                "firstMissingBoundary": {
                    "stage": stage,
                    "event": "next_pending_native_action_unverified",
                    "action": pending["action"],
                    "nativeSequence": pending["nativeSequence"],
                }
                if pending is not None
                else {
                    "stage": stage,
                    "event": "m4_receipt",
                    "reason": "no independently verified stage receipt",
                },
                "elapsed": duration,
                "timeline": timeline,
            }
        )
    order = {name: index for index, name in enumerate(("launch", *STAGES, "handoff"))}
    stages.sort(key=lambda stage: order.get(stage["name"], len(order)))
    total_native = sum(stage["hostIngestedActionClaims"] for stage in stages)
    latest = next(
        (
            stage["lastVerifiedClaim"]
            for stage in reversed(stages)
            if stage["lastVerifiedClaim"]
        ),
        None,
    )
    first_missing = next(
        (stage["firstMissingBoundary"] for stage in stages if stage["name"] in STAGES),
        {
            "stage": "pristine",
            "event": "stage_start",
            "reason": "no M4 stage inspected",
        },
    )
    return {
        "schema": REPORT_SCHEMA,
        "source": "private-diagnostic-records",
        "caseId": case_id,
        "sourcePins": {"frozenSourceSha256": source_pin, "actorSha256": actor_pin},
        "m4": {
            "signedReceiptsVerifiedByReader": 0,
            "required": 4,
            "verdict": "UNPROVEN: 0/4 independently verified by this reader",
        },
        "stageCounts": {
            "stagesWithDiagnostics": len(stages),
            "stagesRequired": 4,
            "hostIngestedActionClaims": total_native,
        },
        "stages": stages,
        "lastVerifiedActionClaim": latest,
        "firstMissingBoundary": first_missing,
        "evidenceInventory": inventory,
        "uncertainties": list(dict.fromkeys(warnings)),
        "nativeRetryPermitted": False,
    }


def report_from_seventh_map(path: Path) -> dict[str, Any]:
    """Show historical seventh-case audit without re-verifying Mac files."""
    _require(path.is_absolute() and ".." not in path.parts, "unsafe source-map path")
    _require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink map")
    try:
        raw_map = _read_regular(path, MAX_MAP_BYTES, private=False)
        record = json.loads(raw_map)
    except (ValueError, UnicodeError) as error:
        raise IncidentReadError("invalid seventh-case source map") from error
    _require(
        type(record) is dict
        and record.get("schema") == "vera.issue512.seventh-case-source-map/v1",
        "source-map schema",
    )
    _require(
        record.get("caseId") == "vera499phase26h2426ee095c73443d",
        "seventh-case identity",
    )
    _require(record.get("macEvidenceNotMountedHere") is True, "unattested map")
    _require(type(record.get("conductor")) is dict, "missing Conductor evidence")
    _require(
        record.get("conductor", {}).get("launchResult") == "unknown-after-claim",
        "incorrect seventh launch",
    )
    _require(
        record["conductor"].get("nativeRetryPermitted") is False,
        "unsafe replay declaration",
    )
    _require(
        record.get("signedM4ReceiptsPresent") == 0
        and record.get("signedM4ReceiptsRequired") == 4,
        "M4 count inconsistent",
    )
    _require(record.get("strict312Acceptance") == "not_run", "strict #312 inconsistent")
    _require(
        type(record.get("stages")) is list
        and all(type(s) is dict for s in record["stages"])
        and [s.get("name") for s in record["stages"]] == list(STAGES),
        "stage map inconsistent",
    )
    first = record["stages"][0]
    actions = first.get("authenticatedNativeResults")
    _require(
        type(actions) is list
        and all(type(a) is dict for a in actions)
        and [
            (a.get("nativeSequence"), a.get("action"), a.get("status")) for a in actions
        ]
        == [
            (0, "construct", "complete"),
            (1, "save_reopen", "complete"),
            (2, "capture_pre", "complete"),
            (3, "queue_render", "complete"),
            (4, "start_render", "complete"),
        ],
        "seventh host sequence inconsistent",
    )
    _require(
        first.get("firstAbsentNativeRequest")
        == {"nativeSequence": 5, "action": "poll_render"},
        "missing boundary inconsistent",
    )
    _require(
        all(s.get("signedM4Receipt") is False for s in record["stages"]),
        "unsigned seventh stages",
    )
    _require(
        first.get("state") == "unknown"
        and all(s.get("state") == "not_started" for s in record["stages"][1:]),
        "stage states inconsistent",
    )
    for key in (
        "sourceGraphSha256",
        "helperActorPinSha256",
        "helperSourceManifestSha256",
        "helperBinarySha256",
    ):
        _require(
            type(record.get(key)) is str and _HEX.fullmatch(record[key]) is not None,
            "invalid frozen pin",
        )
    _require(
        type(record.get("frozenCommit")) is str
        and _COMMIT.fullmatch(record["frozenCommit"]) is not None,
        "frozen commit",
    )
    origin = record.get("origin")
    _require(type(origin) is dict, "missing audit origin")
    refs = [
        {
            "role": "prior_audit_source_map",
            "sha256": hashlib.sha256(raw_map).hexdigest(),
            "sizeBytes": len(raw_map),
            "locatorSha256": None,
            "verifiedByReader": True,
        }
    ]
    for role, field in (
        ("launch_pointer", "pointerSha256"),
        ("bootstrap", "bootstrapSha256"),
    ):
        digest = origin.get(field)
        _require(
            type(digest) is str and _HEX.fullmatch(digest) is not None,
            "invalid audit pointer",
        )
        refs.append(
            {
                "role": role,
                "sha256": digest,
                "sizeBytes": None,
                "locatorSha256": None,
                "verifiedByReader": False,
            }
        )
    return {
        "schema": REPORT_SCHEMA,
        "source": "historical-seventh-case-audit-map",
        "caseId": record["caseId"],
        "sourcePins": {
            "frozenCommit": record["frozenCommit"],
            "frozenSourceSha256": record["sourceGraphSha256"],
            "actorSha256": record["helperActorPinSha256"],
            "helperSourceManifestSha256": record["helperSourceManifestSha256"],
            "helperBinarySha256": record["helperBinarySha256"],
        },
        "m4": {
            "signedReceiptsPresentInPriorAudit": 0,
            "required": 4,
            "verdict": (
                "0/4 M4 receipts in retained seventh-case Mac audit; "
                "not reauthenticated here"
            ),
        },
        "stageCounts": {
            "stagesRequired": 4,
            "stagesWithSignedM4Receipt": 0,
            "authenticatedNativeResultsInPriorAudit": 5,
        },
        "stages": [
            {
                "name": s["name"],
                "state": s["state"],
                "signedM4Receipt": False,
                "historicalAuthenticatedNativeResults": actions
                if s["name"] == "pristine"
                else [],
                "firstMissingBoundary": {
                    "event": "native_dispatch",
                    "nativeSequence": 5,
                    "action": "poll_render",
                    "requestPresent": False,
                }
                if s["name"] == "pristine"
                else {"event": "stage_start", "reason": "not started"},
            }
            for s in record["stages"]
        ],
        "lastVerifiedActionClaim": {
            "stage": "pristine",
            "nativeSequence": 4,
            "action": "start_render",
            "source": "prior Mac read-only audit",
        },
        "firstMissingBoundary": {
            "stage": "pristine",
            "event": "native_dispatch",
            "nativeSequence": 5,
            "action": "poll_render",
            "requestPresent": False,
        },
        "elapsed": {"monotonicNs": None, "basis": "not available in historical map"},
        "evidenceInventory": refs,
        "uncertainties": [
            "Original private Mac operation files and hashes are unavailable; "
            "five host authentications are prior findings, not freshly verified",
            "Root exception was swallowed; root cause is unknown, "
            "not proven to be poll_render",
            "MOV/PCM contents or hashes unavailable; no artifacts opened or invented",
            "No signed M4 receipts in four stages; strict #312 not run",
            "No native replay permitted; the original one-use launch is spent",
        ],
        "nativeRetryPermitted": False,
    }


def as_markdown(report: dict[str, Any]) -> str:
    """Render only validated, closed-field report values; no raw paths or secrets."""
    lines = [
        "# Test Bench incident report",
        "",
        f"Case: `{report['caseId']}`",
        f"Evidence source: `{report['source']}`",
        "",
        f"**M4 verdict:** {report['m4']['verdict']}",
        "**Last host action (reported, not native reverified):** "
        f"`{json.dumps(report['lastVerifiedActionClaim'], sort_keys=True)}`",
        "**First absent boundary:** "
        f"`{json.dumps(report['firstMissingBoundary'], sort_keys=True)}`",
        "",
        "## Stage evidence",
        "",
    ]
    for stage in report["stages"]:
        count = stage.get(
            "hostIngestedActionClaims",
            len(stage.get("historicalAuthenticatedNativeResults", [])),
        )
        lines.append(
            f"- **{stage['name']}**: {count} claimed/prior-audited host ingestions; "
            "signed M4 not reverified"
        )
        duration = stage.get("elapsed", report.get("elapsed", {}))
        lines.append(
            f"  - Elapsed monotonic nanoseconds: `{duration.get('monotonicNs')}`; "
            f"basis: {duration.get('basis', 'unknown')}"
        )
        for event in stage.get("timeline", []):
            lines.append(
                f"  - Record {event['recordIndex']}: `{event['event']}` "
                f"at `{event['boundary']}` (`{event['status']}`), "
                f"UTC `{event['utc']}`; delta ns `{event['deltaFromPriorNs']}`"
            )
        if not stage.get("timeline"):
            lines.append("  - Detailed timestamps unavailable in supplied evidence")
    lines += ["", "## Frozen identity pins", ""]
    for name, digest in report["sourcePins"].items():
        lines.append(f"- `{name}`: `{digest or 'unavailable'}`")
    lines += ["", "## Evidence inventory (never reads MOV/PCM)", ""]
    for item in report["evidenceInventory"]:
        lines.append(
            f"- `{item['role']}` SHA-256 `{item['sha256']}`, "
            f"size `{item['sizeBytes']}`; "
            f"reader verified: `{item['verifiedByReader']}`; "
            f"locator SHA-256 `{item.get('locatorSha256') or 'unavailable'}`"
        )
    lines += ["", "## Uncertainty and boundaries", ""]
    lines.extend(f"- {contract.redact(entry)}" for entry in report["uncertainties"])
    lines.append("- No GUI, SDK, host effects, signed receipts or replay authorized")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument(
        "--case-root", type=Path, action="append", metavar="PRIVATE_ROOT"
    )
    sources.add_argument("--seventh-map", type=Path, metavar="MAP_JSON")
    parser.add_argument(
        "--case-id", help="Exact case identifier (required for --case-root)"
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        if args.case_root is not None:
            _require(args.case_id is not None, "--case-id required for --case-root")
            report = report_from_diagnostics(args.case_root, case_id=args.case_id)
        else:
            _require(args.case_id is None, "--case-id cannot override source map")
            report = report_from_seventh_map(args.seventh_map)
    except (IncidentReadError, OSError) as error:
        print(f"Incident report refused: {contract.redact(error)}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(as_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
