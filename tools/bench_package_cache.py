"""Opt-in, offline pre-cache baseline for #521 (no Resolve or private media).

Run: uv run --frozen python tools/bench_package_cache.py --size-mib 256
Each run creates a fresh, valid v2 package in an isolated temporary directory.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from time import perf_counter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

from issue177_package_fixture import make_package_case  # noqa: E402
from vera_timeline_agent.v2_package import (  # noqa: E402
    build_v2_package,
    verify_v2_package,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size-mib",
        type=int,
        choices=range(256, 385),
        default=256,
        metavar="256..384",
        help="size of one synthetic prepared source in MiB",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="vera-521-benchmark-") as directory:
        root = Path(directory)
        started = perf_counter()
        case = make_package_case(root / "inputs", large_media_mib=args.size_mib)
        print(f"fixture: {args.size_mib} MiB valid synthetic media")
        print(f"fixture generation: {perf_counter() - started:.3f}s")

        def emit(label: str, seconds: float, passed: bool) -> None:
            print(f"package/{label}: {'PASS' if passed else 'FAIL'} ({seconds:.3f}s)")

        started = perf_counter()
        built = build_v2_package(
            case.manifest_path,
            case.report_path,
            case.document_path,
            case.dependencies_path,
            root / "published",
            media_paths=case.media_paths,
            preparation_paths=case.preparation_paths,
            stage_observer=emit,
        )
        print(f"package total: {perf_counter() - started:.3f}s")
        started = perf_counter()
        checked = verify_v2_package(built.project_root)
        print(f"package/outer verification: PASS ({perf_counter() - started:.3f}s)")
        assert checked.build_id == built.build_id
        print(f"package identity: PASS ({built.build_id})")
        print("cache: disabled (baseline)")


if __name__ == "__main__":
    main()
