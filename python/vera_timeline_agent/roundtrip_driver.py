"""Issue144 CLI over ProofSession, with an explicit hash-pinned boundary file.

No boundary is discovered or connected by default. Real qualifications remain
#145 gates in the existing host; a boundary file cannot turn an evidence flag
into live acceptance. Its code is an explicitly trusted operator input.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_build import (
    ProofBuildError,
    _digest,
    _file_hash,
    _operator_bytes,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_native import NativeStages
from vera_timeline_agent.roundtrip_proof import (
    ProofProcessFault,
    ProofSession,
    publish_immutable_output,
)

Json = dict[str, Any]
ACTIONS = (
    "preflight",
    "build",
    "resume-build",
    "bind-baseline",
    "propose",
    "decide",
    "bind-omission-evidence",
    "propose-omission",
    "decide-omission",
    "generate-omission",
    "rebuild",
    "resume-rebuild",
    "promote",
    "status",
    "compare",
)


def session_with_boundary(
    root: Path,
    *,
    node: str | None = None,
    boundary_file: Path | None = None,
    boundary_hash: str | None = None,
) -> tuple[ProofSession, Callable[[], None]]:
    base = ProofSession(root, node_executable=node)
    if boundary_file is None:
        if boundary_hash is not None:
            raise ProofBuildError("boundary hash requires an explicit file")
        return base, base.build._assert_current
    if not isinstance(boundary_hash, str) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", boundary_hash
    ):
        raise ProofBuildError("explicit valid boundary hash required")
    path = boundary_file.absolute()
    raw = _operator_bytes(path)
    if _digest(raw) != boundary_hash:
        raise ProofBuildError("boundary source hash differs; code was not loaded")
    binding_path = base.root / "operator-boundary.json"
    if binding_path.exists():
        retained = load_operator_json(binding_path)
        if (
            set(retained) != {"schemaVersion", "filePins"}
            or retained["schemaVersion"] != "issue-144-operator-boundary/v1"
            or not isinstance(retained["filePins"], dict)
            or retained["filePins"].get(str(path)) != boundary_hash
            or any(
                _file_hash(Path(name)) != digest
                for name, digest in retained["filePins"].items()
            )
        ):
            raise ProofBuildError(
                "retained operator boundary changed; code was not loaded"
            )
    module = types.ModuleType("issue144_explicit_operator_boundary")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    extra = getattr(module, "FILE_PINS", None)
    if not isinstance(extra, dict) or len(extra) > 128:
        raise ProofBuildError("boundary FILE_PINS inventory required (at most128)")
    pins = {str(path): boundary_hash}
    for name, digest in extra.items():
        if (
            not isinstance(name, str)
            or not Path(name).is_absolute()
            or ".." in Path(name).parts
            or not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)
        ):
            raise ProofBuildError("invalid explicit boundary source pin")
        if name in pins and pins[name] != digest:
            raise ProofBuildError("conflicting boundary source pin")
        pins[name] = digest

    def guard() -> None:
        base.build._assert_current()
        if any(_file_hash(Path(name)) != digest for name, digest in pins.items()):
            raise ProofBuildError("operator boundary source changed")

    guard()
    binding = {"schemaVersion": "issue-144-operator-boundary/v1", "filePins": pins}
    publish_immutable_output(binding_path, _receipt_bytes(binding))
    factory = getattr(module, "make_boundary", None)
    if not callable(factory):
        raise ProofBuildError("explicit make_boundary(proof_root) required")
    kwargs = factory(base.root)
    guard()
    if not isinstance(kwargs, dict) or set(kwargs) - {
        "native_provider",
        "capture",
        "omission_evidence",
        "narration_service",
    }:
        raise ProofBuildError("unknown ProofSession boundary arguments")
    kwargs = dict(kwargs)
    if (
        kwargs.get("narration_service") is not None
        and type(kwargs["narration_service"]) is not NarrationService
    ):
        raise ProofBuildError("existing NarrationService required")
    for name in ("native_provider", "capture", "omission_evidence"):
        callback = kwargs.get(name)
        if callback is None:
            continue
        if not callable(callback):
            raise ProofBuildError("callable boundary required")

        def checked(*args: Any, callback: Any = callback, name: str = name) -> Any:
            guard()
            result = callback(*args)
            guard()
            if name == "native_provider":
                if type(result) is not NativeStages or result.build is not args[0]:
                    raise ProofBuildError(
                        "existing NativeStages for the exact build required"
                    )
                previous = result.preflight

                def preflight() -> None:
                    guard()
                    if previous is not None:
                        previous()
                    guard()

                result.preflight = preflight
            return result

        kwargs[name] = checked
    session = ProofSession(base.root, node_executable=base.build.node, **kwargs)
    guard()
    return session, guard


def _cell(value: Any) -> str:
    return (
        html.escape(str(value), quote=True).replace("|", "&#124;").replace("\n", "<br>")
    )


def comparison(session: ProofSession, key: str | None) -> Json:
    if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key):
        raise ProofBuildError("explicit valid comparison decision key required")
    directory = session.root / "decisions" / key
    operator = load_operator_json(directory / "operator-decisions.json")
    if operator["schemaVersion"] in (
        "issue-144-omission-decisions/v1",
        "issue-144-composed-decisions/v1",
    ):
        from vera_timeline_agent.roundtrip_generation import OmissionGeneration

        generation = OmissionGeneration(session, key)
        old, receipt = generation.prior, generation.decision
    else:
        receipt = session._retained_decision(key)
        _, old = session._baseline(receipt["baselineHash"])
    if receipt["status"] not in ("revised", "prepared_revision"):
        raise ProofBuildError("comparison requires an accepted canonical revision")
    path = Path(receipt["revisionRoot"]) / "script-document.json"
    new = load_operator_json(path)
    text = (
        "# Canonical script comparison\n\n"
        f"Evidence: `{old.request['evidenceLevel']}`. "
        "This formats the retained accepted revision; it does not approve "
        "execution or prove current native state.\n\n"
        f"Decision: `{key}`\n\n"
        f"Original script: `{old.input_hashes['script-document.json']}`\n\n"
        f"Revised script: `{_file_hash(path)}`\n"
    )
    for label, doc in (("Before", old.document), ("After", new)):
        text += (
            f"\n## {label}\n\n"
            "| Spoken wording | Visual / anchor instruction |\n| --- | --- |\n"
        )
        for row in doc["activeDraft"]["blocks"]:
            if row["type"] != "narration":
                if row["type"] == "section":
                    text += f"| {_cell(row['title'])} | Section heading (unspoken) |\n"
                continue
            visuals = [
                f"{v['source'].get('label', v['id'])}: "
                f"{v['range']['quotedText']} ({v['audioPolicy']})"
                for v in row["visualEvents"]
            ]
            visibility = [
                f"{span['state']}: {span['range']['quotedText']}"
                for span in row["hostVisibilitySpans"]
            ]
            visuals = visibility + visuals
            text += f"| {_cell(row['text'])} | {_cell('; '.join(visuals))} |\n"
    output = directory / "canonical-comparison.md"
    publish_immutable_output(output, text.encode())
    return {
        "status": "compared",
        "evidenceLevel": old.request["evidenceLevel"],
        "path": str(output),
        "sha256": _file_hash(output),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--node-executable")
    parser.add_argument("--decision-key")
    parser.add_argument("--boundary-file", type=Path)
    parser.add_argument("--boundary-sha256")
    args = parser.parse_args(argv)
    try:
        if args.action == "preflight" and (
            args.boundary_file is not None or args.boundary_sha256 is not None
        ):
            raise ProofBuildError("local preflight does not load an operator boundary")
        session, guard = session_with_boundary(
            args.proof_root,
            node=args.node_executable,
            boundary_file=args.boundary_file,
            boundary_hash=args.boundary_sha256,
        )
        guard()
        result = (
            comparison(session, args.decision_key)
            if args.action == "compare"
            else session.run(args.action, decision_key=args.decision_key)
        )
        guard()
        print(json.dumps(result, sort_keys=True))
        return (
            2
            if result["status"]
            in ("waiting", "needs_action", "failed", "refused", "recovery_blocked")
            else 0
        )
    except NeedsAction as error:
        print(json.dumps({"status": "needs_action", "reason": str(error)}))
        return 2
    except (
        ProofProcessFault,
        OSError,
        subprocess.TimeoutExpired,
        ImportError,
        SyntaxError,
    ) as error:
        print(json.dumps({"status": "fault", "reason": str(error)}))
        return 70
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
