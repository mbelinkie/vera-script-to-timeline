"""Explicit, local-only presenter approval commands; analysis never approves."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vera_timeline_agent.presenter_approvals import (
    ApprovalError,
    approved_performance,
    available_choices,
    choose_approval,
    load_approvals,
    load_takes,
    observed_video,
    undo_approval,
    write_performance_reports,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="presenter_approvals",
        description=(
            "Review and explicitly approve presenter takes without "
            "modifying takes.json."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("choices", "choose", "undo", "list"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--takes", type=Path, required=True)
        if name != "choices":
            cmd.add_argument("--video", type=Path, required=True)
        if name in ("choose", "undo"):
            cmd.add_argument("--row", required=True, help="passage ID, e.g. row-1")
        if name == "choose":
            cmd.add_argument(
                "--state",
                required=True,
                choices=("take", "temp-voice", "needs-pickup", "no-spoken-line"),
            )
            cmd.add_argument(
                "--take", help="printed read key or any constituent take ID"
            )
            cmd.add_argument("--alternate", action="append", default=[])
            cmd.add_argument("--start-frame", type=int)
            cmd.add_argument("--end-frame", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "choices":
            result = {
                "note": "Unapproved candidates only; suggested reads are not decisions",
                "rows": available_choices(load_takes(args.takes)),
            }
        elif args.command == "choose":
            state: str = args.state.replace("-", "_")
            document = choose_approval(
                args.takes,
                args.video,
                args.row,
                state,
                take=args.take,
                alternates=args.alternate,
                start_frame=args.start_frame,
                end_frame=args.end_frame,
            )
            result = {
                "revision": document["revision"],
                "rowId": args.row,
                "decision": document["decisions"][args.row],
            }
        elif args.command == "undo":
            document = undo_approval(args.takes, args.video, args.row)
            result = {
                "revision": document["revision"],
                "rowId": args.row,
                "decision": document["decisions"].get(args.row),
            }
        else:
            takes = load_takes(args.takes)
            document = load_approvals(args.takes.with_name("approvals.json"))
            sha = observed_video(args.video)
            result = approved_performance(takes, document, sha)
            write_performance_reports(args.takes, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except ApprovalError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
