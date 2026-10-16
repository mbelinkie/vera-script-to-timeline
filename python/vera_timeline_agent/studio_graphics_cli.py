"""Prepare, verify, preflight or assemble a compiled EV24 Studio package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .studio_graphics import (
    build_studio_graphic_package,
    run_studio_graphics,
    verify_studio_graphic_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "preflight", "build"))
    parser.add_argument("package", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--compiler-report", type=Path)
    parser.add_argument("--media-plan", type=Path)
    parser.add_argument("--registered-template", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        if args.result is not None and args.result.exists():
            raise ValueError("result already exists; refusing to overwrite")
        if args.action == "prepare":
            if any(
                value is None
                for value in (
                    args.manifest,
                    args.compiler_report,
                    args.media_plan,
                    args.registered_template,
                )
            ):
                parser.error("prepare requires all four input paths")
            package = build_studio_graphic_package(
                args.manifest,
                args.compiler_report,
                args.media_plan,
                args.registered_template,
                args.package,
            )
            text = (
                json.dumps(
                    {
                        "status": "ready_for_studio",
                        "buildId": package.manifest["buildId"],
                    }
                )
                + "\n"
            )
            passed = True
        elif args.action == "verify":
            package = verify_studio_graphic_package(args.package)
            text = (
                json.dumps(
                    {
                        "status": "ready_for_studio",
                        "buildId": package.manifest["buildId"],
                    }
                )
                + "\n"
            )
            passed = True
        else:
            result = run_studio_graphics(args.package, action=args.action)
            text = result.to_json()
            passed = result.status in {"verified", "preflight_passed"}
        if args.result is not None:
            with args.result.open("x") as stream:
                stream.write(text)
        print(text, end="")
        return 0 if passed else 1
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "message": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
