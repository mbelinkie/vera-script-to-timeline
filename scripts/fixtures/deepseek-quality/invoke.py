"""Strict JSON shim for the two standalone Python quality fixtures."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path


def _reject_constant(_value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _emit(value: object, status: int = 0) -> int:
    sys.stdout.write(
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return status


def _fail(code: str) -> int:
    return _emit({"error": code}, 2)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        return _fail("invalid_arguments")
    inputs_path, target_path = Path(argv[1]), Path(argv[2])
    try:
        inputs = json.loads(
            inputs_path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, ValueError):
        return _fail("invalid_input_json")
    if type(inputs) is not list:
        return _fail("inputs_must_be_array")

    try:
        spec = importlib.util.spec_from_file_location(
            "_deepseek_quality_target", target_path
        )
        if spec is None or spec.loader is None:
            return _fail("target_load_failed")
        module = importlib.util.module_from_spec(spec)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            spec.loader.exec_module(module)
        solve = module.solve
    except BaseException:
        return _fail("target_load_failed")
    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            outputs = [solve(payload) for payload in inputs]
    except BaseException:
        return _fail("solve_failed")
    try:
        encoded = json.dumps(
            outputs, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError, OverflowError):
        return _fail("output_not_json")
    sys.stdout.write(encoded + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
