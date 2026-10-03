"""Local status and fake-stage demonstration for durable build jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from vera_timeline_agent.build_jobs import (
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    StageContext,
    publish_immutable_output,
)


class DemoStages:
    """Deterministic local receipts, including resumable fake speech blocks."""

    def __init__(self, delay_speech_block: float = 0) -> None:
        self.delay_speech_block = delay_speech_block

    def reconcile(self, context: StageContext) -> bool:
        output = context.output_path
        return output.is_file() and output.read_bytes() == context.stage_key.encode()

    def execute(self, context: StageContext) -> None:
        if context.stage == "generating_speech":
            for number in range(1, 4):
                block = context.output_path.parent / f"speech-block-{number}"
                payload = f"{context.stage_key}:{number}".encode()
                publish_immutable_output(block, payload)
                digest = hashlib.sha256(payload).hexdigest()
                context.report_progress(f"speech block {number} verified: {digest}")
                print(f"speech block {number} verified: {digest}", flush=True)
                if self.delay_speech_block:
                    time.sleep(self.delay_speech_block)
        publish_immutable_output(context.output_path, context.stage_key.encode())


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "--root", required=True, type=Path, help="local test job directory"
    )
    commands = value.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("--project", required=True)
    submit.add_argument("--snapshot", required=True)
    submit.add_argument("--key", required=True)
    submit.add_argument("--mode", required=True, choices=("free", "studio"))
    submit.add_argument("--render", action="store_true")
    submit.add_argument("--delivery", action="store_true")
    for name in ("status", "run", "resume", "cancel", "confirm-import"):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--job", required=True)
        if name == "run":
            command.add_argument("--worker", default=f"local-{os.getpid()}")
            command.add_argument("--lease-seconds", type=float, default=300)
            command.add_argument("--delay-speech-block", type=float, default=0)
            command.add_argument("--wait-for-lease", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        store = BuildJobStore(args.root)
        if args.command == "submit":
            job_id = store.submit(
                BuildRequest(
                    project_id=args.project,
                    snapshot_id=args.snapshot,
                    idempotency_key=args.key,
                    mode=args.mode,
                    render=args.render,
                    delivery=args.delivery,
                )
            )
            print(json.dumps({"jobId": job_id}, sort_keys=True))
            return 0
        if args.command == "run":
            if args.delay_speech_block < 0:
                raise BuildJobError("speech block delay must be nonnegative")
            adapter = DemoStages(args.delay_speech_block)
            while True:
                if store.run_one(
                    args.project,
                    args.job,
                    args.worker,
                    adapter,
                    lease_seconds=args.lease_seconds,
                ):
                    continue
                current = store.status(args.project, args.job)
                lease_until = current["leaseUntil"]
                if (
                    args.wait_for_lease
                    and current["status"] == "running"
                    and isinstance(lease_until, (int, float))
                    and lease_until > time.time()
                ):
                    time.sleep(max(0, min(1, lease_until - time.time())))
                    continue
                break
        elif args.command == "resume":
            store.resume(args.project, args.job)
        elif args.command == "cancel":
            store.cancel(args.project, args.job)
        elif args.command == "confirm-import":
            store.confirm_import(args.project, args.job)
        print(
            json.dumps(store.status(args.project, args.job), indent=2, sort_keys=True)
        )
        return 0
    except (BuildJobError, OSError, ValueError) as error:
        print(f"build job error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
