"""Exclusive timing never adds native child time to VERA overhead."""

from collections.abc import Iterator

import pytest
from vera_timeline_agent.performance_v2 import (
    OPAQUE_NATIVE,
    Recorder,
    delivery_record,
    increment,
    measured,
    native_handle,
    recording_context,
    span,
)


def clock(values: list[int]) -> Iterator[int]:
    yield from values


def test_exclusive_nested_native_time_and_work() -> None:
    ticks = clock([0, 10, 30, 50])
    recorder = Recorder(lambda: next(ticks))
    with recording_context(recorder), span("outer"):
        increment("hash.bytes", 17)
        with span("native", OPAQUE_NATIVE):
            increment("native.calls")
    result = recorder.snapshot()
    assert result["spans"] == [
        {
            "name": "native",
            "classification": OPAQUE_NATIVE,
            "calls": 1,
            "exclusiveNs": 20,
        },
        {"name": "outer", "classification": "vera", "calls": 1, "exclusiveNs": 30},
    ]
    assert result["counters"] == {"hash.bytes": 17, "native.calls": 1}


def test_exception_restores_context_and_records_work() -> None:
    ticks = clock([0, 9])
    recorder = Recorder(lambda: next(ticks))
    with (
        pytest.raises(ValueError, match="refused"),
        recording_context(recorder),
        span("validation"),
    ):
        increment("hash.files")
        raise ValueError("refused")
    increment("hash.files", 100)
    assert recorder.snapshot()["counters"] == {"hash.files": 1}
    assert recorder.snapshot()["spans"][0]["exclusiveNs"] == 9


def test_nested_collectors_get_work_without_duplicates() -> None:
    outer = Recorder()
    inner = Recorder()
    with recording_context(outer), recording_context(inner), recording_context(inner):
        increment("native.calls")
        with span("work"):
            pass
    for recorder in (outer, inner):
        assert recorder.snapshot()["counters"] == {"native.calls": 1}
        assert recorder.snapshot()["spans"][0]["calls"] == 1


def test_delivery_records_are_separate_per_invocation() -> None:
    @delivery_record
    def deliver() -> dict[str, object]:
        increment("native.calls")
        return {"verified": False}

    one, two = deliver(), deliver()
    assert (
        one["performance"]["counters"]
        == two["performance"]["counters"]
        == {"native.calls": 1}
    )
    assert one["performance"] is not two["performance"]


def test_measured_preserves_result_and_signature() -> None:
    @measured("compile")
    def compile_value(value: int, *, extra: int) -> int:
        return value + extra

    with recording_context() as recorder:
        assert compile_value(3, extra=4) == 7
    assert recorder.snapshot()["spans"][0]["name"] == "compile"
    assert compile_value.__name__ == "compile_value"


def test_native_forwarding_preserves_handles_containers_and_failures() -> None:
    class Handle:
        def Name(self) -> str:
            return "original"

        def Child(self) -> dict[str, object]:
            return {"children": [self], "flag": True}

        def Accept(self, handles: list[object]) -> bool:
            assert handles == [self]
            return True

        def Fail(self) -> None:
            raise ValueError("native refusal")

    raw = Handle()
    assert native_handle(raw) is raw
    with recording_context() as recorder:
        handle = native_handle(raw)
        assert handle.Name() == "original"
        child = handle.Child()["children"][0]
        assert handle.Accept([child]) is True
        with pytest.raises(ValueError, match="native refusal"):
            child.Fail()
    assert recorder.snapshot()["counters"]["native.apiCalls"] == 4
