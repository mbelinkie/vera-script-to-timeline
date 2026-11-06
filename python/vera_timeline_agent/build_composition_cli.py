"""Read-only local job status and explicitly marked disposable simulation.

Live effects MUST be injected by a trusted paired agent through
``BuildComposition``; this CLI intentionally has no generic real-write command
and cannot silently grant provider/Resolve/Drive authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .build_composition import (
    BuildComposition,
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    SnapshotRepository,
    StageEvidence,
)
from .build_jobs import (
    ALL_STAGES,
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    StageContext,
    publish_immutable_output,
)


class _SimulationPort:
    """Private, zero-provider disposable effects; never a live adapter."""

    def __init__(self, stage: str) -> None:
        self.stage = stage

    def _file(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        return snapshot.write_root / context.job_id / self.stage / "simulation-only.txt"

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        path = self._file(context, snapshot)
        if not path.exists():
            return Inspection(EffectState.ABSENT)
        if path.read_bytes() != context.stage_key.encode():
            return Inspection(
                EffectState.UNCERTAIN, reason="simulation artifact changed"
            )
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="simulation",
                adapter_version="simulation-only/v1",
                inputs={"document": snapshot.file("document")},
                outputs={"simulation": path},
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        publish_immutable_output(
            self._file(context, snapshot), context.stage_key.encode()
        )


def simulate(mode: str) -> dict[str, Any]:
    if mode not in {"free", "studio"}:
        raise ValueError("simulation mode must be Free or Studio")
    with tempfile.TemporaryDirectory(prefix="vera157-simulation-") as directory:
        root = Path(directory)
        sources = root / "inputs"
        sources.mkdir()
        (sources / "document.json").write_bytes(b"{}\n")
        (sources / "dependencies.json").write_bytes(b"{}\n")
        repository = SnapshotRepository(
            root / "snapshots",
            read_roots=(sources,),
            write_root=root / "built",
            live_head=lambda _: (
                1,
                hashlib.sha256(b"simulation-only-head").hexdigest(),
                "simulation-only",
            ),
            live_settings=lambda _: hashlib.sha256(b"simulation-settings").hexdigest(),
        )
        snapshot = repository.freeze(
            project_id="simulation-project",
            build_id="simulation-build",
            build_class="preview",
            mode=mode,
            settings_hash=hashlib.sha256(b"simulation-settings").hexdigest(),
            inputs={
                "document": sources / "document.json",
                "dependencies": sources / "dependencies.json",
            },
            adapter_versions={"simulation": "simulation-only/v1"},
        )
        stages = ALL_STAGES[:5] if mode == "free" else ALL_STAGES[:7]
        composition = BuildComposition(
            repository, {stage: _SimulationPort(stage) for stage in stages}
        )
        store = BuildJobStore(root / "jobs")
        job = composition.submit(
            store,
            BuildRequest(
                "simulation-project", snapshot.snapshot_id, "simulation-request", mode
            ),
        )
        for _ in range(len(stages)):
            if not store.run_one(
                "simulation-project", job, "simulation-worker", composition
            ):
                break
        result = store.status("simulation-project", job)
        return {
            "simulationOnly": True,
            "actualApplicationEvidence": False,
            "realProviderCalls": 0,
            "nativeMutations": 0,
            "uploadedFiles": 0,
            "mode": mode,
            "status": result["status"],
            "stages": {row["name"]: row["status"] for row in result["stages"]},
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="VERA v2 local composition inspection/simulation"
    )
    sub = parser.add_subparsers(dest="operation", required=True)
    status = sub.add_parser("status", help="Read status; never start an effect")
    status.add_argument("--store", type=Path, required=True)
    status.add_argument("--project-id", required=True)
    status.add_argument("--job-id", required=True)
    fake = sub.add_parser(
        "simulate", help="Disposable synthetic proof, NOT a delivered build"
    )
    fake.add_argument("--mode", choices=("free", "studio"), default="free")
    args = parser.parse_args(argv)
    try:
        if args.operation == "status":
            # Read-only mode never constructs an execution adapter.
            if not (args.store / "build-jobs.sqlite3").is_file():
                raise BuildJobError("existing local build store is required")
            result = BuildJobStore(args.store).status(args.project_id, args.job_id)
            print(json.dumps({"readOnly": True, "job": result}, sort_keys=True))
        else:
            print(json.dumps(simulate(args.mode), sort_keys=True))
    except (BuildJobError, ValueError, OSError) as error:
        parser.exit(2, f"VERA composition: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
