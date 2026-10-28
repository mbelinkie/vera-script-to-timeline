#!/usr/bin/env python3
"""Run the verified review-ingest pipeline on an Issue 44 synthetic fixture."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import threading
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_jobs import BuildJobStore
from vera_timeline_agent.media_preparation import file_hash
from vera_timeline_agent.review_ingest import (
    RegisteredMaster,
    ReviewIngestAdapter,
)

PROJECT_ID = "issue44-fixture"
SOURCE_ID = "numbered-master"
IDEMPOTENCY_KEY = "issue44-fixture-ingest-v1"
LEASE_SECONDS = 300.0
RENEW_INTERVAL_SECONDS = 30.0
PAGE_TITLE = "Issue 44 local proxy playback check"


class FixtureError(RuntimeError):
    """The selected directory is not a safe generated fixture."""


class LeaseHeartbeat:
    """Keep a long local FFmpeg stage from losing its durable worker lease."""

    def __init__(self, adapter: ReviewIngestAdapter) -> None:
        self.adapter = adapter

    def _call(self, callback: Callable[[Any], Any], context: Any) -> Any:
        stop = threading.Event()
        renewal_errors: list[Exception] = []

        def renew() -> None:
            while not stop.wait(RENEW_INTERVAL_SECONDS):
                try:
                    context.renew_lease()
                except Exception as error:
                    renewal_errors.append(error)
                    stop.set()
                    return

        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            result = callback(context)
        finally:
            stop.set()
            heartbeat.join()
        if renewal_errors:
            raise RuntimeError(f"could not renew ingest lease: {renewal_errors[0]}")
        return result

    def reconcile(self, context: Any) -> bool:
        result = self._call(self.adapter.reconcile, context)
        if not isinstance(result, bool):
            raise TypeError("review ingest reconcile must return a boolean")
        return result

    def execute(self, context: Any) -> None:
        self._call(self.adapter.execute, context)


def fixture_directory(value: Path) -> Path:
    if not value.is_absolute():
        raise FixtureError("--fixture-dir must be an absolute path")
    if value.is_symlink():
        raise FixtureError("fixture directory must not be a symbolic link")
    try:
        fixture = value.resolve(strict=True)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    except OSError as error:
        raise FixtureError(f"cannot resolve fixture directory: {error}") from error
    if fixture.parent != temp_root:
        raise FixtureError(
            "fixture directory must be a direct child of the system temp directory"
        )
    if not fixture.is_dir():
        raise FixtureError("fixture path must be a directory")

    master = fixture / "numbered-master.mov"
    page = fixture / "review.html"
    if master.is_symlink() or not master.is_file():
        raise FixtureError("fixture must contain a regular numbered-master.mov")
    if page.is_symlink() or not page.is_file():
        raise FixtureError("fixture must contain a regular review.html")
    try:
        page_text = page.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise FixtureError(f"cannot read fixture review page: {error}") from error
    if PAGE_TITLE not in page_text:
        raise FixtureError("review.html is not the Issue 44 synthetic fixture page")
    return fixture


def _ensure_owned_directory(path: Path, parent: Path) -> Path:
    if path.is_symlink():
        raise FixtureError(
            f"persistent fixture directory must not be a symlink: {path}"
        )
    try:
        path.mkdir(exist_ok=True)
        resolved = path.resolve(strict=True)
        expected_parent = parent.resolve(strict=True)
    except OSError as error:
        raise FixtureError(
            f"cannot prepare fixture state directory {path}: {error}"
        ) from error
    if not resolved.is_dir() or resolved.parent != expected_parent:
        raise FixtureError(f"fixture state directory escaped its parent: {path}")
    return resolved


def json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: json_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def next_stage(status: dict[str, Any]) -> str | None:
    for stage in status.get("stages", []):
        if isinstance(stage, dict) and stage.get("status") != "complete":
            return str(stage.get("name", "unknown"))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        required=True,
        help=("absolute temp-directory child created by issue44_fixture.py"),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "resume this fixture's existing waiting or failed job with its "
            "same idempotency key"
        ),
    )
    args = parser.parse_args()

    fixture: Path | None = None
    master_hash_before: str | None = None
    store: BuildJobStore | None = None
    job_id: str | None = None
    try:
        fixture = fixture_directory(args.fixture_dir)
        master = fixture / "numbered-master.mov"
        master_hash_before = file_hash(master)
        state_root = _ensure_owned_directory(fixture / ".issue44-ingest", fixture)
        cache_root = _ensure_owned_directory(state_root / "review-cache", state_root)
        artifacts_path = state_root / "artifacts"
        database_path = state_root / "build-jobs.sqlite3"
        if artifacts_path.is_symlink() or database_path.is_symlink():
            raise FixtureError(
                "persisted job database and artifacts must not be symlinks"
            )

        def resolve_master(project_id: str, source_id: str) -> RegisteredMaster | None:
            if (project_id, source_id) != (PROJECT_ID, SOURCE_ID):
                return None
            return RegisteredMaster(
                project_id=PROJECT_ID,
                source_id=SOURCE_ID,
                path=master,
                content_hash=file_hash(master),
            )

        store = BuildJobStore(state_root)
        adapter = LeaseHeartbeat(
            ReviewIngestAdapter(
                store,
                cache_root=cache_root,
                resolve_master=resolve_master,
            )
        )
        job_id = adapter.adapter.submit_ingest(
            PROJECT_ID,
            SOURCE_ID,
            IDEMPOTENCY_KEY,
        )
        status = store.status(PROJECT_ID, job_id)
        if status["status"] in ("waiting", "failed"):
            if not args.resume:
                raise FixtureError(
                    f"job {job_id} is {status['status']}; rerun with --resume "
                    "to retry it"
                )
            store.resume(PROJECT_ID, job_id)
            status = store.status(PROJECT_ID, job_id)

        while status["status"] != "complete":
            if status["status"] not in ("queued", "running"):
                raise FixtureError(
                    "job cannot run now; current durable status is "
                    f"{status['status']} (active stage: {status.get('activeStage')}, "
                    f"lease until: {status.get('leaseUntil')})"
                )
            stage = next_stage(status)
            print(
                f"Running Issue 44 ingest stage: {stage or 'unknown'}", file=sys.stderr
            )
            ran_stage = store.run_one(
                PROJECT_ID,
                job_id,
                "issue44-fixture-cli",
                adapter,
                lease_seconds=LEASE_SECONDS,
            )
            status = store.status(PROJECT_ID, job_id)
            if status["status"] == "complete":
                break
            if status["status"] in ("waiting", "failed"):
                raise FixtureError(
                    f"stage ended with {status['status']}: {status.get('lastError')}"
                )
            if not ran_stage:
                raise FixtureError(
                    "worker did not complete a stage; inspect the reported status and "
                    "retry with --resume after any active lease expires"
                )
            print(
                f"Completed Issue 44 ingest stage: {stage or 'unknown'}",
                file=sys.stderr,
            )

        handoff = adapter.adapter.verified_handoff(PROJECT_ID, job_id)
        master_hash_after = file_hash(master)
        if master_hash_after != master_hash_before:
            raise FixtureError(
                "synthetic master changed during ingest; refusing handoff"
            )
        result = json_value(handoff)
        result["job_id"] = job_id
        result["state_root"] = str(state_root)
        result["review_page"] = str(fixture / "review.html")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        failure: dict[str, Any] = {
            "error": str(error),
            "fixture_dir": str(fixture) if fixture else str(args.fixture_dir),
            "job_id": job_id,
        }
        if store is not None and job_id is not None:
            try:
                failure["status"] = store.status(PROJECT_ID, job_id)
            except Exception as status_error:
                failure["status_error"] = str(status_error)
        if fixture is not None and master_hash_before is not None:
            try:
                failure["master_hash_unchanged"] = (
                    file_hash(fixture / "numbered-master.mov") == master_hash_before
                )
            except Exception as hash_error:
                failure["master_hash_error"] = str(hash_error)
        print(
            json.dumps(failure, indent=2, sort_keys=True, default=str), file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
