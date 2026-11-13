"""Opt-in, offline package cache comparison for #521 (no Resolve or private media).

Run: uv run --frozen python tools/bench_package_cache.py --size-mib 256 --compare-cache
Each run creates a fresh, valid v2 package in an isolated temporary directory.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from functools import partial
from pathlib import Path
from time import perf_counter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

from issue177_package_fixture import make_package_case  # noqa: E402
from vera_timeline_agent.v2_package import (  # noqa: E402
    build_v2_package,
    verify_v2_package,
)


def _emit_phase(
    phases: dict[str, float], label: str, seconds: float, passed: bool
) -> None:
    assert passed, f"failed package substep {label}"
    phases[label] = seconds
    print(f"package/{label}: PASS ({seconds:.3f}s)")


def _record_cache(counts: list[tuple[int, int]], reused: int, processed: int) -> None:
    counts.append((reused, processed))


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
    parser.add_argument(
        "--compare-cache",
        action="store_true",
        help="measure uncached, cold, warm and single-source-stamp edit",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="vera-521-benchmark-") as directory:
        root = Path(directory)
        started = perf_counter()
        case = make_package_case(root / "inputs", large_media_mib=args.size_mib)
        print(f"fixture: {args.size_mib} MiB valid synthetic media")
        print(f"fixture generation: {perf_counter() - started:.3f}s")

        baseline: object | None = None
        baseline_receipt: bytes | None = None
        cache_root = root / "disposable-cache"
        scenarios = (
            (
                ("uncached", None),
                ("cold", cache_root),
                ("warm", cache_root),
                ("one-source-stamp-edited", cache_root),
            )
            if args.compare_cache
            else (("uncached", None),)
        )
        unique_inputs = len(set(case.media_paths.values()))

        for name, cache in scenarios:
            if name == "one-source-stamp-edited":
                # Force a single cache miss without changing the expected
                # manifest or the finished package bytes. Content edits with
                # changed hashes are tested separately by focused tests.
                original = next(
                    source
                    for key, source in case.media_paths.items()
                    if key.startswith("original:")
                )
                stamp = original.stat()
                os.utime(
                    original,
                    ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000),
                )

            print(f"--- {name} ---")
            phases: dict[str, float] = {}
            counts: list[tuple[int, int]] = []

            started = perf_counter()
            built = build_v2_package(
                case.manifest_path,
                case.report_path,
                case.document_path,
                case.dependencies_path,
                root / name,
                media_paths=case.media_paths,
                preparation_paths=case.preparation_paths,
                stage_observer=partial(_emit_phase, phases),
                package_cache=cache,
                cache_observer=partial(_record_cache, counts),
            )
            total = perf_counter() - started
            print(f"package total: {total:.3f}s")
            started = perf_counter()
            checked = verify_v2_package(built.project_root)
            print(f"package/outer verification: PASS ({perf_counter() - started:.3f}s)")
            assert checked.build_id == built.build_id
            receipt = next(
                (built.project_root / "Builds").glob("*/package-verification.json")
            )
            receipt_bytes = receipt.read_bytes()
            if baseline is None:
                baseline, baseline_receipt = checked, receipt_bytes
            else:
                assert checked == baseline, f"verification differs: {name}"
                assert receipt_bytes == baseline_receipt, f"receipt differs: {name}"
            reused, processed = counts[-1] if counts else (0, 0)
            if cache:
                assert reused + processed == unique_inputs
            else:
                assert (reused, processed) == (0, 0)
            if name == "cold":
                assert (reused, processed) == (0, unique_inputs)
            if name == "warm":
                assert (reused, processed) == (unique_inputs, 0)
            if name == "one-source-stamp-edited":
                assert (reused, processed) == (unique_inputs - 1, 1)
            print(f"package cache: reused={reused} processed={processed}")
            print(f"package identity: PASS ({built.build_id})")
            print(f"package substep total: {sum(phases.values()):.3f}s (diagnostic)")


if __name__ == "__main__":
    main()
