"""Intentionally incorrect baseline: isinstance accepts bool as int."""

from typing import TypedDict


class ValidationInput(TypedDict):
    start_frame: int
    duration_frames: int
    track: int


KEY_ORDER = ("start_frame", "duration_frames", "track")
RANGES = {
    "start_frame": (0, 1_000_000),
    "duration_frames": (1, 180_000),
    "track": (1, 16),
}


def solve(payload):
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["object"]}
    if set(payload) != set(KEY_ORDER):
        return {"valid": False, "errors": ["keys"]}
    errors = []
    for key in KEY_ORDER:
        value = payload[key]
        if not isinstance(value, int):
            errors.append(key + ":type")
        elif not RANGES[key][0] <= value <= RANGES[key][1]:
            errors.append(key + ":range")
    return {"valid": not errors, "errors": errors}
