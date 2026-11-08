"""Prepare a NEW #473 M4 one-start config from authenticated source-only inputs.

This cannot start Resolve, change projects, sign an M4 receipt or reuse an
expired campaign. It only adopts the two *already* created and independently
verified one-use disposable provision receipts; their exact project/timeline
UIDs must differ from the original M4 campaign. Approval is copied from the
caller's new, explicit actual Producer instruction, not from the old config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_m4_runner as runner
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from . import resolve_test_queue_m4_provision as provision


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise queue.QueueError("fresh Test Bench setup refused: " + message)


def prepare(
    template_path: Path,
    root: Path,
    *,
    consent_reference: str,
    consent_instruction: str,
    name: str,
) -> dict[str, Any]:
    """Durably write one new config, with zero native effects or old authority."""
    original = runner.validate_config(json.loads(carrier._read(template_path, 16384)))
    old_root = Path(original["root"])
    _require(
        template_path == old_root.parent / "config.json"
        and root.is_absolute()
        and root != old_root
        and root not in old_root.parents
        and old_root not in root.parents
        and root != Path(original["queueRoot"])
        and root != Path(original["packageRoot"])
        and root != Path(original["narrationEvidenceRoot"]),
        "old/new roots and original config provenance must be distinct",
    )
    carrier._private(root)
    old_plan_path = old_root / "m4-plan.json"
    old_raw = carrier._read(old_plan_path, 131072)
    old_plan = m4.validate_plan(json.loads(old_raw))
    _require(
        old_raw == queue.canonical(old_plan)
        and old_plan["caseId"] == "synthetic-312"
        and old_plan["initialTarget"] != old_plan["freshTarget"],
        "original source M4 plan not authenticated",
    )
    targets = provision.completed(root / "provision")
    old_names = {
        old_plan[stage]["projectName"] for stage in ("initialTarget", "freshTarget")
    }
    old_uids = {
        old_plan[stage][field]
        for stage in ("initialTarget", "freshTarget")
        for field in ("projectUid", "timelineUid")
    }
    new_names = {target["projectName"] for target in targets.values()}
    new_uids = {
        target[field]
        for target in targets.values()
        for field in ("projectUid", "timelineUid")
    }
    _require(
        len(new_names) == 2
        and len(new_uids) == 4
        and not old_names.intersection(new_names)
        and not old_uids.intersection(new_uids),
        "new provision receipts share historical M4 identity",
    )
    _require(
        not any(
            (root / key).exists() or (root / key).is_symlink()
            for key in (
                "config.json",
                "queue",
                "m4-plan.json",
                "source-preflight",
                "pristine",
                "pristine-stage",
                "edit-capability",
                "f1-gui-edit",
            )
        ),
        "new one-use M4 config/stages already exist; inspect without resetting",
    )
    _require(
        type(consent_reference) is str
        and type(consent_instruction) is str
        and bool(consent_reference.strip())
        and bool(consent_instruction.strip())
        and consent_reference != original["consentReference"]
        and consent_instruction != original["consentInstruction"],
        "new case-specific Producer instruction must replace historical authority",
    )
    value = runner.validate_config(
        {
            **original,
            "root": str(root),
            "queueRoot": str(root / "queue"),
            "name": name,
            "consentReference": consent_reference,
            "consentInstruction": consent_instruction,
        }
    )
    _require(
        all(
            value[key] == original[key]
            for key in (
                "caseId",
                "packageRoot",
                "narrationEvidenceRoot",
                "profile",
                "merged472Commit",
                "maxDiskBytes",
                "maxElapsedSeconds",
            )
        ),
        "approved original synthetic source and bounds changed",
    )
    raw = queue.canonical(value)
    carrier._once(root / "config.json", raw)
    return {
        "state": "fresh_config_prepared_no_native_effect",
        "nativeEffects": False,
        "newRoot": str(root),
        "configSha256": hashlib.sha256(raw).hexdigest(),
        "initialUid": targets["initial"]["projectUid"],
        "freshUid": targets["fresh"]["projectUid"],
        "oldTargetsReused": False,
    }


def audit_sources(config_path: Path) -> dict[str, Any]:
    """Read-only source authenticity check; does not prepare/dispatch a run."""
    value = runner.validate_config(json.loads(carrier._read(config_path, 16384)))
    runner._merged_472(value["merged472Commit"])
    runner._require_pinned_node()
    package_root = Path(value["packageRoot"])
    preparations = runner._matrix_preparation_paths(
        package_root, case_id=value["caseId"]
    )
    narration = runner._matrix_narration_paths(
        package_root,
        Path(value["narrationEvidenceRoot"]),
        case_id=value["caseId"],
    )
    return {
        "state": "source_ready_for_one_start_preflight_no_native_effect",
        "nativeEffects": False,
        "preparationReceipts": len(preparations),
        "narrationSources": len(narration),
        "initialAndFreshNotReenrolled": True,
    }


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("prepare", "audit-sources"))
    cli.add_argument("--template", type=Path)
    cli.add_argument("--root", type=Path, required=True)
    cli.add_argument("--name")
    cli.add_argument("--consent-reference")
    cli.add_argument("--consent-instruction")
    args = cli.parse_args()
    try:
        if args.action == "prepare":
            _require(
                args.template is not None
                and args.name is not None
                and args.consent_reference is not None
                and args.consent_instruction is not None,
                "new template, name and Producer authority required",
            )
            outcome = prepare(
                args.template,
                args.root,
                name=args.name,
                consent_reference=args.consent_reference,
                consent_instruction=args.consent_instruction,
            )
        else:
            outcome = audit_sources(args.root / "config.json")
        print(json.dumps(outcome, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(
            json.dumps(
                {"state": "refused", "nativeEffects": False, "detail": str(error)}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
