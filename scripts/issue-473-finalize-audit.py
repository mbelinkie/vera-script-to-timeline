"""Read-only #473 edited native/host finalize evidence inspection.

Run from the original source-pinned 3ea32582 checkout using its Python env.
Does not retry or finalize any operation, and never writes to host journals.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path.home() / ".local/state/vera/issue-473-studio-05"


def main() -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    session = ROOT / "run/edited/session.json"
    source = ROOT / "pinned-code"
    if Path.cwd().resolve() != source.resolve():
        raise RuntimeError("must inspect original signed source")
    session_sha = hashlib.sha256(session.read_bytes()).hexdigest()
    controller = load_output_session(session, session_sha)
    history = controller.journal.history()
    same = [row for row in history if row.get("context") == controller.context]
    steps = ROOT / "run/edited-actions"
    effects = []
    for sequence, action in enumerate(
        native.action_plan_for_context(controller.context)
    ):
        result, _authority, _intent, request = native.native_request_paths(
            controller.context, sequence
        )
        step = steps / f"native-{sequence:02d}"
        effects.append(
            {
                "sequence": sequence,
                "action": action,
                "resultExists": result.is_file(),
                "requestExists": request.is_file(),
                "hostIngested": (step / "host-ingested.json").is_file(),
                "nativeStartExists": (request.parent / "native-start.json").is_file(),
            }
        )
    print(
        json.dumps(
            {
                "phase": controller.context["phase"],
                "target": controller.context["target"],
                "finalizeIntent": (steps / "finalize-intent.json").is_file(),
                "historyTail": [
                    {
                        "sequence": row.get("sequence"),
                        "state": row.get("state"),
                        "resultRawSha256": row.get("resultRawSha256"),
                    }
                    for row in same[-12:]
                ],
                "nativeActions": effects,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
