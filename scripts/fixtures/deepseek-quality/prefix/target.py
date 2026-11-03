"""Intentionally incorrect baseline: it ignores the current covered-row order."""


def solve(payload):
    covered = list(payload["covered_ids"])
    return {
        "retained_ids": covered,
        "review": payload["review"],
        "settings": payload["settings"],
    }
