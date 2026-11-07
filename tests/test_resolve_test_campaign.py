"""M3 offline campaign contract and additive M1/M2 SQLite migration tests."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_campaign as campaign
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_native as native

SHA = "a" * 64
COMMIT = "b" * 40


def example_trial(
    tmp_path: Path, index: int, case_id: str, variant: str = "single", round_: int = 1
) -> dict[str, Any]:
    request_dir = tmp_path / f"request-{index}" / native.RELEASE_NAME
    request_dir.mkdir(parents=True, exist_ok=True)
    path = request_dir / "request.json"
    project = f"VERA-test-{index}"
    request = {
        "schemaVersion": native.REQUEST_SCHEMA,
        "releaseSha256": "b" * 64,
        "attestationPath": str(tmp_path / f"attestation-{index}.json"),
        "attestationSha256": "c" * 64,
        "packageDir": str(tmp_path / f"package-{index}"),
        "projectName": project,
        "timelineName": project,
        "action": "build",
        "authorizeNewNonproduction": True,
        "externalScripting": "Local",
        "evidenceDir": str(tmp_path / f"evidence-{index}"),
    }
    raw = queue.canonical(request)
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(raw)
    path.chmod(0o400)
    request_sha = hashlib.sha256(raw).hexdigest()
    now = queue.now_utc()
    start = queue.iso(now - timedelta(minutes=1))
    end = queue.iso(now + timedelta(minutes=45))
    child = native.validate_native_plan(
        {
            "schema": native.NATIVE_SCHEMA,
            "name": f"native-{index}",
            "fixtureId": f"synthetic-{index}",
            "fixtureSha256": "c" * 64,
            "targetId": f"disposable-{index}",
            "targetPolicy": "new_disposable_native",
            "category": "native-save-reopen",
            "sourceCommit": COMMIT,
            "maxElapsedSeconds": 600,
            "maxDiskBytes": 1048576,
            "runAt": start,
            "deadlineAt": end,
            "cases": [
                {
                    "id": "build",
                    "adapter": native.NATIVE_ADAPTER,
                    "iterations": 1,
                    "delayMs": 0,
                }
            ],
            "native": {
                "requestPath": str(path),
                "requestSha256": request_sha,
                "releaseSha256": "b" * 64,
                "attestationSha256": "c" * 64,
                "projectName": project,
                "timelineName": project,
                "expected": {
                    "viewSha256": SHA,
                    "eventsSha256": SHA,
                    "settingsSha256": SHA,
                    "mediaSha256": SHA,
                    "eventCount": 1,
                    "markerCount": 0,
                    "mediaCount": 1,
                },
            },
        }
    )
    return {
        "id": f"trial-{index}",
        "caseId": case_id,
        "variant": variant,
        "round": round_,
        "cacheMode": "warm",
        "sourceCommit": COMMIT,
        "planSha256": hashlib.sha256(queue.canonical(child)).hexdigest(),
        "plan": child,
    }


def example_campaign(
    tmp_path: Path, count: int = 1, paired: bool = False
) -> dict[str, Any]:
    now = queue.now_utc()
    cases = [
        {"id": f"case-{i}", "comparisonKey": f"comparison-{i}"} for i in range(count)
    ]
    trials = [
        example_trial(
            tmp_path, i * (2 if paired else 1) + variant_index, f"case-{i}", variant, 1
        )
        for i in range(count)
        for variant_index, variant in enumerate(
            ("baseline", "candidate") if paired else ("single",)
        )
    ]
    return {
        "schema": campaign.CAMPAIGN_SCHEMA,
        "name": "nightly-native",
        "order": "alternating" if paired else "fixed",
        "runAt": queue.iso(now - timedelta(minutes=5)),
        "deadlineAt": queue.iso(now + timedelta(minutes=55)),
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": 2 * 1024**3,
        "cases": cases,
        "trials": trials,
    }


def write_campaign(tmp_path: Path, value: dict[str, Any]) -> Path:
    location = tmp_path / "campaign.json"
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_bytes(queue.canonical(value))
    return location


def test_one_case_is_normal_and_100_cases_200_trials_is_only_ceiling(
    tmp_path: Path,
) -> None:
    one = example_campaign(tmp_path / "one")
    assert len(campaign.validate_campaign_plan(one)["trials"]) == 1
    many = example_campaign(tmp_path / "many", 100, paired=True)
    validated = campaign.validate_campaign_plan(many)
    assert len(validated["cases"]) == 100
    assert len(validated["trials"]) == 200
    assert len({item["planSha256"] for item in validated["trials"]}) == 200
    bigger = copy.deepcopy(many)
    bigger["trials"].append(copy.deepcopy(bigger["trials"][0]))
    with pytest.raises(queue.QueueError, match=r"1\.\.200"):
        campaign.validate_campaign_plan(bigger)
    bigger = copy.deepcopy(many)
    bigger["cases"].append({"id": "case-100", "comparisonKey": "comparison-100"})
    with pytest.raises(queue.QueueError, match=r"1\.\.100"):
        campaign.validate_campaign_plan(bigger)


def test_alternating_sorts_rounds_and_reverses_even_round(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 1, paired=True)
    value["trials"] += [
        example_trial(tmp_path, 2, "case-0", "baseline", 2),
        example_trial(tmp_path, 3, "case-0", "candidate", 2),
    ]
    value["trials"] = list(reversed(value["trials"]))
    outcome = campaign.validate_campaign_plan(value)
    assert [(item["round"], item["variant"]) for item in outcome["trials"]] == [
        (1, "baseline"),
        (1, "candidate"),
        (2, "candidate"),
        (2, "baseline"),
    ]
    assert (
        len({item["plan"]["native"]["requestSha256"] for item in outcome["trials"]})
        == 4
    )


def test_fixed_order_preserves_author_order(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 2)
    value["trials"].reverse()
    assert [i["id"] for i in campaign.validate_campaign_plan(value)["trials"]] == [
        "trial-1",
        "trial-0",
    ]


def test_alternating_incomplete_pair_and_skipped_round_refused(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 1, paired=True)
    value["trials"].pop()
    with pytest.raises(queue.QueueError, match="incomplete"):
        campaign.validate_campaign_plan(value)
    value = example_campaign(tmp_path, 1, paired=True)
    value["trials"] += [
        example_trial(tmp_path, 2, "case-0", "baseline", 3),
        example_trial(tmp_path, 3, "case-0", "candidate", 3),
    ]
    with pytest.raises(queue.QueueError, match="nonconsecutive"):
        campaign.validate_campaign_plan(value)


@pytest.mark.parametrize(
    "change,expected",
    [
        ("request", "duplicate"),
        ("target", "duplicate"),
        ("evidence", "duplicate"),
        ("child-digest", "SHA-256 mismatch"),
        ("child-keys", "native plan"),
        ("child-missing-schedule", "explicit immutable"),
        ("invalid-cache", "cache mode"),
        ("variant", "variant"),
        ("trial-key", "trial keys"),
        ("request-tamper", "request bytes"),
        ("expired", "deadline"),
        ("unknown-case", "unknown case"),
    ],
)
def test_invalid_native_contract_refused(
    tmp_path: Path, change: str, expected: str
) -> None:
    value = example_campaign(tmp_path, 2)
    rows = value["trials"]
    if change == "request":
        rows[1]["plan"]["native"] = copy.deepcopy(rows[0]["plan"]["native"])
        rows[1]["planSha256"] = hashlib.sha256(
            queue.canonical(rows[1]["plan"])
        ).hexdigest()
    elif change == "target":
        rows[1]["plan"]["targetId"] = rows[0]["plan"]["targetId"]
        rows[1]["planSha256"] = hashlib.sha256(
            queue.canonical(rows[1]["plan"])
        ).hexdigest()
    elif change == "evidence":
        target_request = Path(rows[1]["plan"]["native"]["requestPath"])
        first_request = Path(rows[0]["plan"]["native"]["requestPath"])
        original = json.loads(target_request.read_bytes())
        original["evidenceDir"] = json.loads(first_request.read_bytes())["evidenceDir"]
        target_request.chmod(0o600)
        target_request.write_bytes(queue.canonical(original))
        target_request.chmod(0o400)
        rows[1]["plan"]["native"]["requestSha256"] = hashlib.sha256(
            queue.canonical(original)
        ).hexdigest()
        rows[1]["planSha256"] = hashlib.sha256(
            queue.canonical(rows[1]["plan"])
        ).hexdigest()
    elif change == "child-digest":
        rows[1]["planSha256"] = SHA
    elif change == "child-keys":
        rows[1]["plan"]["native"]["command"] = "rm -rf /"
    elif change == "child-missing-schedule":
        del rows[1]["plan"]["runAt"]
    elif change == "invalid-cache":
        rows[1]["cacheMode"] = "clear-global-cache"
    elif change == "variant":
        rows[1]["variant"] = "native.shell"
    elif change == "trial-key":
        rows[1]["execute"] = "sh"
    elif change == "request-tamper":
        target_request = Path(rows[1]["plan"]["native"]["requestPath"])
        target_request.chmod(0o600)
        target_request.write_bytes(b"altered")
        target_request.chmod(0o400)
    elif change == "expired":
        value["deadlineAt"] = value["runAt"]
    elif change == "unknown-case":
        rows[1]["caseId"] = "nonexistent"
    with pytest.raises(queue.QueueError, match=expected):
        campaign.validate_campaign_plan(value)


def test_duplicate_trial_id_and_unknown_nested_fields_refused(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 2)
    value["trials"][1]["id"] = value["trials"][0]["id"]
    with pytest.raises(queue.QueueError, match="duplicate"):
        campaign.validate_campaign_plan(value)
    value = example_campaign(tmp_path, 2)
    value["cases"][0]["untrusted"] = "extra"
    with pytest.raises(queue.QueueError, match="case keys"):
        campaign.validate_campaign_plan(value)


def test_rejects_mixed_source_commits_within_a_case_variant(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 1, paired=True)
    extra = example_trial(tmp_path, 100, "case-0", "baseline", 2)
    extra["sourceCommit"] = "c" * 40
    extra["plan"]["sourceCommit"] = extra["sourceCommit"]
    extra["planSha256"] = hashlib.sha256(queue.canonical(extra["plan"])).hexdigest()
    value["trials"].append(extra)
    with pytest.raises(queue.QueueError, match="mix source commits"):
        campaign.validate_campaign_plan(value)


def test_rejects_cross_trial_nested_evidence_directory(tmp_path: Path) -> None:
    value = example_campaign(tmp_path, 2)
    first = value["trials"][0]
    second = value["trials"][1]
    original_request = json.loads(
        Path(first["plan"]["native"]["requestPath"]).read_bytes()
    )
    nested = Path(original_request["evidenceDir"]) / "nested"
    request_path = Path(second["plan"]["native"]["requestPath"])
    request = json.loads(request_path.read_bytes())
    request["evidenceDir"] = str(nested)
    request_path.chmod(0o600)
    request_path.write_bytes(queue.canonical(request))
    request_path.chmod(0o400)
    second["plan"]["native"]["requestSha256"] = hashlib.sha256(
        request_path.read_bytes()
    ).hexdigest()
    second["planSha256"] = hashlib.sha256(queue.canonical(second["plan"])).hexdigest()
    with pytest.raises(queue.QueueError, match="evidence overlaps"):
        campaign.validate_campaign_plan(value)


def test_reader_rejects_symlinks_fifos_oversize_duplicate_json_and_keeps_m2_limit(
    tmp_path: Path,
) -> None:
    file = tmp_path / "plan.json"
    file.write_text('{"schema":"x","schema":"y"}')
    with pytest.raises(queue.QueueError, match="duplicate"):
        campaign.read_campaign_file(file)
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(file)
    with pytest.raises(queue.QueueError):
        campaign.read_campaign_file(symlink)
    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo)
    with pytest.raises(queue.QueueError, match="regular"):
        campaign.read_campaign_file(fifo)
    file.write_bytes(b"x" * (campaign.MAX_FILE_BYTES + 1))
    with pytest.raises(queue.QueueError, match="2 MiB"):
        campaign.read_campaign_file(file)
    file.write_bytes(b"x" * 131073)
    with pytest.raises(queue.QueueError, match="128 KiB"):
        queue.read_plan_file(file)


def test_frozen_parent_and_child_identity_and_reopened_m1_m2_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "preflight", lambda child: {})
    store = queue.Store(tmp_path / "store")
    old_m1 = {
        "schema": queue.PLAN_SCHEMA,
        "name": "mock",
        "fixtureId": "synthetic-one",
        "fixtureSha256": SHA,
        "targetId": "disposable-one",
        "targetPolicy": "synthetic_only",
        "category": "old",
        "maxElapsedSeconds": 2,
        "maxDiskBytes": 1048576,
        "cases": [
            {"id": "first", "adapter": "mock.pass", "iterations": 1, "delayMs": 0}
        ],
    }
    old_id = queue.enqueue(store, write_campaign(tmp_path, old_m1))
    val = example_campaign(tmp_path / "inputs", 1)
    legacy_native = example_campaign(tmp_path / "legacy-native-inputs", 1)
    native_id = queue.enqueue(
        store, write_campaign(tmp_path / "native", legacy_native["trials"][0]["plan"])
    )
    record = campaign.enqueue_campaign(store, write_campaign(tmp_path, val))
    reopened = queue.Store(store.root)
    with reopened.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM native_attempts").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 1
    assert reopened.get(old_id)["state"] == "queued"
    assert reopened.get(native_id)["state"] == "queued"
    assert len(campaign.load_frozen_campaign(reopened, record)["trials"]) == 1
    with reopened.connect() as db:
        db.execute(
            "UPDATE campaign_trials SET plan_sha=? WHERE campaign_id=?", (SHA, record)
        )
    with pytest.raises(queue.QueueError, match="step identity"):
        campaign.load_frozen_campaign(reopened, record)
    with reopened.connect() as db:
        db.execute(
            "UPDATE campaign_trials SET plan_sha=? WHERE campaign_id=?",
            (val["trials"][0]["planSha256"], record),
        )
    frozen = reopened.root / record / "plan.json"
    frozen.chmod(0o600)
    frozen.write_bytes(frozen.read_bytes() + b" ")
    frozen.chmod(0o400)
    with pytest.raises(queue.QueueError, match="plan changed"):
        campaign.load_frozen_campaign(reopened, record)


def test_request_already_reserved_by_m2_cannot_enter_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "preflight", lambda child: {})
    store = queue.Store(tmp_path / "store")
    value = example_campaign(tmp_path / "inputs", 1)
    path = write_campaign(tmp_path, value)
    queue.enqueue(store, write_campaign(tmp_path / "m2", value["trials"][0]["plan"]))
    with pytest.raises(queue.QueueError, match="already reserved"):
        campaign.enqueue_campaign(store, path)
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 0


def test_m2_cannot_reserve_request_already_frozen_in_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "preflight", lambda child: {})
    store = queue.Store(tmp_path / "store")
    value = example_campaign(tmp_path / "inputs")
    campaign.enqueue_campaign(store, write_campaign(tmp_path, value))
    with pytest.raises(queue.QueueError, match="reserved by campaign"):
        queue.enqueue(
            store, write_campaign(tmp_path / "m2", value["trials"][0]["plan"])
        )
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_preflight_is_required_before_campaign_has_any_db_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def refuse(child: dict[str, Any]) -> None:
        calls.append(child["targetId"])
        raise ValueError("release attestation is unverified")

    monkeypatch.setattr(native, "preflight", refuse)
    store = queue.Store(tmp_path / "store")
    plan = example_campaign(tmp_path / "inputs")
    with pytest.raises(queue.QueueError, match="preflight refused"):
        campaign.enqueue_campaign(store, write_campaign(tmp_path, plan))
    assert calls == ["disposable-0"]
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 0


def test_migration_from_real_legacy_m1_m2_tables_preserves_original_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy-queue"
    root.mkdir()
    job_ids = [f"resolve-test-{i:032x}" for i in (1, 2)]
    with sqlite3.connect(root / "queue.sqlite3") as db:
        db.executescript("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL,
                submitted_at TEXT NOT NULL, run_at REAL NOT NULL,
                deadline_at REAL NOT NULL, started_at TEXT, ended_at TEXT,
                plan_sha TEXT NOT NULL, worker_id TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                cancel_requested INTEGER NOT NULL DEFAULT 0, reason TEXT
            );
            CREATE TABLE native_attempts (
                job_id TEXT PRIMARY KEY, request_sha TEXT NOT NULL UNIQUE,
                locator TEXT NOT NULL, intent_at TEXT, invocation_id TEXT,
                parent_state TEXT, native_verified INTEGER NOT NULL DEFAULT 0
            );
        """)
        for job_id in job_ids:
            db.execute(
                "INSERT INTO jobs(id,state,submitted_at,run_at,deadline_at,plan_sha) "
                "VALUES(?,?,?,?,?,?)",
                (job_id, "queued", "2026-11-06T00:00:00+00:00", 0, 1, SHA),
            )
        db.execute(
            "INSERT INTO native_attempts(job_id,request_sha,locator) VALUES(?,?,?)",
            (job_ids[1], "c" * 64, "{}"),
        )
    store = queue.Store(root)
    with store.connect() as db:
        assert [
            row[0] for row in db.execute("SELECT id FROM jobs ORDER BY id")
        ] == job_ids
        assert (
            db.execute("SELECT request_sha FROM native_attempts").fetchone()[0]
            == "c" * 64
        )
        assert db.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM campaign_trials").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("maxElapsedSeconds", True),
        ("maxElapsedSeconds", 21601),
        ("maxDiskBytes", 4 * 1024**3 + 1),
        ("order", []),
        ("deadlineAt", "2026-11-06T00:00:00"),
    ],
)
def test_aggregate_limits_are_closed_and_finite(
    tmp_path: Path,
    field: str,
    invalid: object,
) -> None:
    value = example_campaign(tmp_path)
    value[field] = invalid
    with pytest.raises(queue.QueueError):
        campaign.validate_campaign_plan(value)


def test_native_evidence_cannot_overlap_private_request_or_package(
    tmp_path: Path,
) -> None:
    value = example_campaign(tmp_path)
    row = value["trials"][0]
    path = Path(row["plan"]["native"]["requestPath"])
    request = json.loads(path.read_bytes())
    request["evidenceDir"] = request["packageDir"]
    path.chmod(0o600)
    path.write_bytes(queue.canonical(request))
    path.chmod(0o400)
    row["plan"]["native"]["requestSha256"] = hashlib.sha256(
        queue.canonical(request)
    ).hexdigest()
    row["planSha256"] = hashlib.sha256(queue.canonical(row["plan"])).hexdigest()
    with pytest.raises(queue.QueueError, match="overlaps"):
        campaign.validate_campaign_plan(value)
