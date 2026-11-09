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
# A second, separately invoked static-only slot after the first *incomplete*
# source admission is preserved. No third slot or automatic retry is allowed.
RETRY_RECOVERY = "source-preflight-recovery-2"
RETRY_RECEIPT = "source-preflight-recovery-2-receipt.json"
RETRY_INTENT = "source-preflight-recovery-2-intent.json"
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


def _reference(
    root: Path, config: dict[str, Any], *, second: bool = False
) -> dict[str, Any]:
    targets = provision.completed(root / "provision")
    value: dict[str, Any] = {
        "schema": SCHEMA,
        "configSha256": hashlib.sha256(queue.canonical(config)).hexdigest(),
        "recovery": RETRY_RECOVERY if second else RECOVERY,
        "originalPreflight": str(root / "source-preflight"),
        "initialProjectUid": targets["initial"]["projectUid"],
        "freshProjectUid": targets["fresh"]["projectUid"],
        "nativeEffects": False,
    }
    if second:
        prior = _path(root, INTENT)
        prior_raw = carrier._read(prior, 16384)
        _need(
            json.loads(prior_raw) == _reference(root, config),
            "first source-only intent changed",
        )
        _need(
            not _path(root, RECEIPT).exists(),
            "first recovery was completed; second attempt forbidden",
        )
        incomplete = _path(root, RECOVERY)
        _need(
            incomplete.is_dir()
            and not (
                incomplete / "qualification-output-package-admission.json"
            ).exists(),
            "first source admission not incomplete",
        )
        value["priorAttemptSha256"] = hashlib.sha256(prior_raw).hexdigest()
    return value


def verify(root: Path, config: dict[str, Any]) -> None:
    """Authenticate exact immutable recovery; never accept a partial retry."""
    from .qualification_output_package_v2 import load_qualification_package_v2

    _pre_native(root)
    second = any(
        _path(root, part).exists()
        for part in (RETRY_RECOVERY, RETRY_INTENT, RETRY_RECEIPT)
    )
    recovery = RETRY_RECOVERY if second else RECOVERY
    intent_name = RETRY_INTENT if second else INTENT
    receipt_name = RETRY_RECEIPT if second else RECEIPT
    expected = _reference(root, config, second=second)
    intent = json.loads(carrier._read(_path(root, intent_name), 16384))
    receipt = json.loads(carrier._read(_path(root, receipt_name), 16384))
    _need(
        set(intent) == set(expected) and intent == expected,
        "source recovery intent or provision target differs",
    )
    _need(
        set(receipt) == {*expected.keys(), "admissionPath", "admissionSha256"}
        and all(receipt[key] == expected[key] for key in expected),
        "source recovery receipt differs from original authority",
    )
    admission_path = root / recovery / "qualification-output-package-admission.json"
    _need(
        receipt["admissionPath"] == str(admission_path)
        and isinstance(receipt["admissionSha256"], str)
        and len(receipt["admissionSha256"]) == 64,
        "not the single recovered static package admission",
    )
    reopened = load_qualification_package_v2(admission_path, receipt["admissionSha256"])
    _need(
        reopened.profile == config["profile"]
        and reopened.package_root == root / recovery / "package",
        "recovered static profile or source root differs",
    )
    reopened.assert_current()


def recover(config_path: Path, *, slot: int = 1) -> dict[str, Any]:
    """Spend only the operator-selected static slot; never replay a native effect."""
    from .qualification_output_package_v2 import admit_qualification_package_v2

    _need(type(slot) is int and slot in (1, 2), "unsupported recovery slot")
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
        second = slot == 2
        recovery = RETRY_RECOVERY if second else RECOVERY
        intent_name = RETRY_INTENT if second else INTENT
        receipt_name = RETRY_RECEIPT if second else RECEIPT
        original = _reference(root, config, second=second)
        if not second:
            _need(
                not any(
                    _path(root, item).exists()
                    for item in (RETRY_RECOVERY, RETRY_INTENT, RETRY_RECEIPT)
                ),
                "second static recovery already attempted",
            )
        for part in (intent_name, receipt_name, recovery):
            item = _path(root, part)
            _need(not item.exists(), "recovery already attempted; no replay")
        package_root = Path(config["packageRoot"])
        preparations = runner._matrix_preparation_paths(
            package_root, case_id=config["caseId"]
        )
        narrations = runner._matrix_narration_paths(
            package_root,
            Path(config["narrationEvidenceRoot"]),
            case_id=config["caseId"],
        )
        carrier._once(root / intent_name, queue.canonical(original))
        admission = admit_qualification_package_v2(
            root / recovery,
            profile=config["profile"],
            package_root=package_root,
            preparation_paths=preparations,
            narration_evidence_paths=narrations,
        )
        admission.assert_current()
        path, digest = admission.serialize_native_admission()
        carrier._once(
            root / receipt_name,
            queue.canonical(
                {**original, "admissionPath": str(path), "admissionSha256": digest}
            ),
        )
        verify(root, config)
        return {
            "state": "authenticated_static_recovery_no_native_effect",
            "nativeEffects": False,
            "admissionSha256": digest,
            "recovery": recovery,
        }


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("recover", "inspect"))
    cli.add_argument("--config", type=Path, required=True)
    cli.add_argument("--slot", type=int, choices=(1, 2), default=1)
    args = cli.parse_args()
    try:
        if args.action == "recover":
            output = recover(args.config, slot=args.slot)
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
