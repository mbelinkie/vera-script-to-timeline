"""Independent, source-pinned M4 verification of #473's immutable edited receipt.

The existing reviewed native host was sealed under the original 3ea32582
Python/source graph. The M4 checker since then fixed a read-only native-rate
format mismatch (rational object, not a display string). Import only that
exact SHA-locked corrected M4 *verifier module* while preserving all old
admission/native/session modules and the actual one-use terminal output.

No Resolve SDK, external editor, retouching, native launch, or approval occurs.
First run `inspect` to authenticate original provenance, PCM and the exact
same-target +24-frame boundary. Run `submit` only after inspect has passed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path.home() / ".local/state/vera/issue-473-studio-05"
PINNED = ROOT / "pinned-code"
NEW_M4 = (
    Path.home()
    / ".local/state/vera/issue-473-studio-01/checkout/python"
    / "vera_timeline_agent/resolve_test_queue_m4.py"
)
EXPECTED_M4_SHA = "fd1239e3dcaf175a073a44db45c15194da79e7b05d9cca044ccad8d89ef2b325"
OLD_GIT_SHA = "3ea32582a6761ead588762ba2df2f95bf80bd8e9"
OLD_SOURCE_SHA = "1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc"
PRISTINE_SESSION_SHA = (
    "59919054ae9080c63f50263a931b17a6e21486359a21c8c1d086a15955f590e2"
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError("#473 edited M4 verifier refused: " + reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def corrected_m4() -> ModuleType:
    require(NEW_M4.is_file() and not NEW_M4.is_symlink(), "M4 source unavailable")
    require(sha(NEW_M4.read_bytes()) == EXPECTED_M4_SHA, "corrected M4 source differs")
    spec = importlib.util.spec_from_file_location(
        "vera_timeline_agent.issue473_external_m4", NEW_M4
    )
    require(
        spec is not None and spec.loader is not None, "M4 module loader unavailable"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    require(isinstance(module, ModuleType), "corrected M4 module not loaded")
    return module


def inspect(*, verify_host: bool = True) -> tuple[Any, Any, str, dict[str, Any]]:
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue

    require(Path.cwd().resolve() == PINNED.resolve(), "not source-pinned checkout")
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    require(rev == OLD_GIT_SHA, "signed native source commit differs")
    require(
        package._sha(package._admission_code_source_graph_raw()) == OLD_SOURCE_SHA,
        "signed native source graph differs",
    )
    m4 = corrected_m4()
    store = queue.Store(ROOT / "queue")
    plan_path = ROOT / "run/m4-plan.json"
    job_id = runner._find_job(store, sha(plan_path.read_bytes()))
    require(job_id is not None, "original M4 job missing")
    assert isinstance(job_id, str)
    plan = m4._load_plan(store, job_id)
    report = m4.publish(store, job_id)
    require(
        report["state"] == "awaiting_operator"
        and report["stage"] == "edited"
        and [stage["state"] for stage in report["stages"]]
        == ["verified", "awaiting_operator", "pending", "pending"],
        "M4 edited stage not pending first signed submission",
    )
    first = m4._stage_receipt(store, job_id, 0)
    require(
        first["session"] == plan["baselineSession"]
        and first["session"]["sha256"] == PRISTINE_SESSION_SHA,
        "original baseline receipt differs",
    )
    receipt_file = store.root / job_id / "receipt-edited.json"
    require(
        receipt_file.is_file() and not receipt_file.is_symlink(),
        "original terminal edited receipt missing",
    )
    receipt = m4._parse_receipt(
        receipt_file.read_bytes(), "edited", report["stages"][1]["operation_id"]
    )
    prepared = ROOT / "run/edited/session.json"
    require(
        receipt["session"]
        == {"path": str(prepared), "sha256": sha(prepared.read_bytes())},
        "edited source-pinned host session differs",
    )
    if verify_host:
        intent_time = m4._intent(store, job_id, 1)
        # Existing M4 acceptance verifies current v2 session and admission,
        # independently authenticated native operations, same-target IDs,
        # exact signed +24 frame roll, and terminal MOV/PCM. Pure check.
        m4._verify_stage(store, job_id, 1, receipt, intent_time)
    print(
        json.dumps(
            {
                "state": (
                    "edited_m4_independently_verified_read_only"
                    if verify_host
                    else "edited_m4_original_receipt_preflight_only"
                ),
                "jobId": job_id,
                "sourcePinnedNativeCommit": OLD_GIT_SHA,
                "correctedM4SourceSha256": EXPECTED_M4_SHA,
                "originalReceipt": {
                    "path": str(receipt_file),
                    "sha256": sha(receipt_file.read_bytes()),
                },
                "nativeCapture": receipt["capture"],
                "queueMutated": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return m4, store, job_id, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "submit"))
    action = parser.parse_args().action
    # A separately executed inspect has already run the complete comparison.
    # M4.submit *itself* reruns the complete stage verifier, so do not double
    # that expensive independent readback before pinning its one-use receipt.
    m4, store, job_id, _receipt = inspect(verify_host=action == "inspect")
    if action == "submit":
        m4.submit(store, job_id)
        report = m4.publish(store, job_id)
        require(
            report["state"] == "queued"
            and [row["state"] for row in report["stages"]]
            == ["verified", "verified", "pending", "pending"],
            "edited M4 verification did not accept the original receipt",
        )
        print(
            json.dumps(
                {"state": "edited_m4_verified", "jobId": job_id, "next": "revision"},
                sort_keys=True,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
