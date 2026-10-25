"""Invocation-scoped, in-memory performance records for v2 operations."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from functools import wraps
from time import perf_counter_ns
from typing import Any, ParamSpec, TypeVar

VERA = "vera"
OPAQUE_NATIVE = "opaque_native"
P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class _SpanFrame:
    recorder: Recorder
    name: str
    classification: str
    started_ns: int
    child_ns: int = 0


_RECORDERS: ContextVar[tuple[Recorder, ...]] = ContextVar(
    "vera_performance_recorders", default=()
)
_SPAN_STACK: ContextVar[tuple[_SpanFrame, ...]] = ContextVar(
    "vera_performance_span_stack", default=()
)


class Recorder:
    """Small per-invocation collector with an injectable monotonic clock."""

    def __init__(self, clock_ns: Callable[[], int] = perf_counter_ns) -> None:
        self._clock_ns = clock_ns
        self._spans: dict[tuple[str, str], dict[str, int]] = {}
        self._counters: dict[str, int] = {}

    def snapshot(self) -> dict[str, Any]:
        return {
            "schemaVersion": "vera-performance/v1",
            "timeUnit": "ns",
            "spans": [
                {
                    "name": name,
                    "classification": classification,
                    "calls": values["calls"],
                    "exclusiveNs": values["exclusiveNs"],
                }
                for (name, classification), values in sorted(self._spans.items())
            ],
            "counters": dict(sorted(self._counters.items())),
        }

    def _record_span(self, name: str, classification: str, exclusive_ns: int) -> None:
        values = self._spans.setdefault(
            (name, classification), {"calls": 0, "exclusiveNs": 0}
        )
        values["calls"] += 1
        values["exclusiveNs"] += exclusive_ns


@contextmanager
def recording_context(recorder: Recorder | None = None) -> Iterator[Recorder]:
    """Record nested work in this collector and any enclosing collector."""
    selected = recorder or Recorder()
    current = _RECORDERS.get()
    token: Token[tuple[Recorder, ...]] | None = None
    if selected not in current:
        token = _RECORDERS.set((*current, selected))
    try:
        yield selected
    finally:
        if token is not None:
            _RECORDERS.reset(token)


def increment(name: str, amount: int = 1) -> None:
    """Add a deterministic work counter to each active collector."""
    if amount == 0:
        return
    for recorder in _RECORDERS.get():
        recorder._counters[name] = recorder._counters.get(name, 0) + amount


@contextmanager
def span(name: str, classification: str = VERA) -> Iterator[None]:
    """Record a nested span as exclusive time in each active collector."""
    if classification not in {VERA, OPAQUE_NATIVE}:
        raise ValueError("unsupported performance classification")
    recorders = _RECORDERS.get()
    if not recorders:
        yield
        return

    parents = _SPAN_STACK.get()
    frames = tuple(
        _SpanFrame(recorder, name, classification, recorder._clock_ns())
        for recorder in recorders
    )
    token = _SPAN_STACK.set((*parents, *frames))
    try:
        yield
    finally:
        _SPAN_STACK.reset(token)
        for frame in frames:
            elapsed_ns = max(0, frame.recorder._clock_ns() - frame.started_ns)
            exclusive_ns = max(0, elapsed_ns - frame.child_ns)
            frame.recorder._record_span(frame.name, frame.classification, exclusive_ns)
            for parent in reversed(parents):
                if parent.recorder is frame.recorder:
                    parent.child_ns += elapsed_ns
                    break


def measured(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Time an existing boundary without changing its arguments or outcome."""

    def decorate(function: Callable[P, T]) -> Callable[P, T]:
        @wraps(function)
        def call(*args: P.args, **kwargs: P.kwargs) -> T:
            with span(name):
                return function(*args, **kwargs)

        return call

    return decorate


def delivery_record(  # noqa: UP047 - shipped into Resolve's older Python runtime
    function: Callable[P, dict[str, Any]],
) -> Callable[P, dict[str, Any]]:
    """Retain child-process diagnostics outside attested package bytes."""

    @wraps(function)
    def call(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        with recording_context() as recorder, span("delivery.total"):
            result = function(*args, **kwargs)
        result["performance"] = recorder.snapshot()
        return result

    return call
