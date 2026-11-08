"""One-use, static-only recovery from interrupted #473 source admission.

Never moves, deletes or adopts the interrupted source-preflight. A distinct
immutable recovery admission must complete and authenticate before the original
M4 runner may proceed. No native owner, project edit, queue or host request is
issued by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_m4_runner as runner
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4_provision as provision

SCHEMA = "vera.test-bench-source-recovery/v1"
RECOVERY = "source-preflight-recovery-1"
RECEIPT = "source-preflight-recovery-receipt.json"
INTENT = "source-preflight-recovery-intent.json"
PROHIBITED = (
    "queue",
    "m4-plan.json",
    "pristine",
    "pristine-stage",
    "edit-capability",
    "f1-gui-edit",
    "rebuild",
)


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise queue.QueueError("source-only recovery refused: " + reason)


def _path(root: Path, name: str) -> Path:
    path = root / name
    _need(not path.is_symlink(), "recovery record is a symbolic link")
    return path


def _pre_native(root: Path) -> None:
    """Only a source-only attempt may be recovered. Never reset live M4."""
    primary = _path(root, "source-preflight")
    _need(primary.is_dir(), "no interrupted static admission")
    _need(
        not (primary / "qualification-output-package-admission.json").exists(),
        "a primary admission exists; inspect it rather than rerun",
    )
    for part in PROHIBITED:
        item = _path(root, part)
        _need(not item.exists(), "M4 or native state already enrolled")


def _reference(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "configSha256": hashlib.sha256(queue.canonical(config)).hexdigest(),
        "recovery": RECOVERY,
        "originalPreflight": str(root / "source-preflight"),
        "initialProjectUid": provision.completed(root / "provision")["initial"][
            "projectUid"
        ],
        "freshProjectUid": provision.completed(root / "provision")["fresh"][
            "projectUid"
        ],
        "nativeEffects": False,
    }


def verify(root: Path, config: dict[str, Any]) -> None:
    """Authenticate the immutable recovery and its original source snapshot."""
    from .qualification_output_package_v2 import load_qualification_package_v2

    _pre_native(root)
    expected = _reference(root, config)
    intent = json.loads(carrier._read(_path(root, INTENT), 16384))
    receipt = json.loads(carrier._read(_path(root, RECEIPT), 16384))
    _need(
        set(intent) == set(expected) and intent == expected,
        "source recovery intent or provision target differs",
    )
    _need(
        set(receipt) == {*expected.keys(), "admissionPath", "admissionSha256"}
        and all(receipt[key] == expected[key] for key in expected),
        "source recovery receipt differs from original authority",
    )
    admission_path = root / RECOVERY / "qualification-output-package-admission.json"
    _need(
        receipt["admissionPath"] == str(admission_path)
        and isinstance(receipt["admissionSha256"], str)
        and len(receipt["admissionSha256"]) == 64,
        "not the single recovered static package admission",
    )
    reopened = load_qualification_package_v2(admission_path, receipt["admissionSha256"])
    _need(
        reopened.profile == config["profile"]
        and reopened.package_root == root / RECOVERY / "package",
        "recovered static profile or source root differs",
    )
    reopened.assert_current()


def recover(config_path: Path) -> dict[str, Any]:
    """Spend one static-only recovery; unknown/partial cannot be retried."""
    from .qualification_output_package_v2 import admit_qualification_package_v2

    config = runner.validate_config(json.loads(carrier._read(config_path, 16384)))
    root = Path(config["root"])
    _need(config_path == root / "config.json", "not the original fresh M4 config")
    runner._merged_472(config["merged472Commit"])
    runner._require_pinned_node()
    if sys.platform == "darwin":
        from .qualification_output_controller_v2 import output_runtime_snapshot

        output_runtime_snapshot()
    _need(
        shutil.disk_usage(root).free >= config["maxDiskBytes"],
        "original disk reserve unavailable",
    )
    carrier._private(root)
    with carrier._lock(root):
        _pre_native(root)
        for part in (INTENT, RECEIPT, RECOVERY):
            item = _path(root, part)
            _need(not item.exists(), "recovery already attempted; no replay")
        original = _reference(root, config)
        package_root = Path(config["packageRoot"])
        preparations = runner._matrix_preparation_paths(
            package_root, case_id=config["caseId"]
        )
        narrations = runner._matrix_narration_paths(
            package_root,
            Path(config["narrationEvidenceRoot"]),
            case_id=config["caseId"],
        )
        carrier._once(root / INTENT, queue.canonical(original))
        admission = admit_qualification_package_v2(
            root / RECOVERY,
            profile=config["profile"],
            package_root=package_root,
            preparation_paths=preparations,
            narration_evidence_paths=narrations,
        )
        admission.assert_current()
        path, digest = admission.serialize_native_admission()
        carrier._once(
            root / RECEIPT,
            queue.canonical(
                {**original, "admissionPath": str(path), "admissionSha256": digest}
            ),
        )
        verify(root, config)
        return {
            "state": "authenticated_static_recovery_no_native_effect",
            "nativeEffects": False,
            "admissionSha256": digest,
            "recovery": RECOVERY,
        }


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("recover", "inspect"))
    cli.add_argument("--config", type=Path, required=True)
    args = cli.parse_args()
    try:
        if args.action == "recover":
            output = recover(args.config)
        else:
            value = runner.validate_config(
                json.loads(carrier._read(args.config, 16384))
            )
            verify(Path(value["root"]), value)
            output = {"state": "authenticated_static_recovery_no_native_effect"}
        print(json.dumps(output, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as error:
        print(
            json.dumps(
                {"state": "refused", "nativeEffects": False, "detail": str(error)}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
