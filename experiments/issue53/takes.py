"""Provider-neutral, local-only row take experiment. No media I/O or providers.

Discovery has no reference parameter. Evaluation is a separate, read-only pass.
All ranges are half open. Transcript array order is retained even without time.
"""

from __future__ import annotations

import math
import re
import unicodedata
from copy import deepcopy
from fractions import Fraction
from itertools import pairwise
from typing import Any, TypeGuard

from experiments.issue53.review_rules import editorial_signals, sentence_spans

Record = dict[str, Any]


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold().replace("\u2019", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text, re.UNICODE)


def _number(value: Any) -> TypeGuard[float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _diff(expected: list[str], actual: list[str]) -> list[Record]:
    """Unit-cost edit distance with fixed equal/substitution/deletion/insertion ties."""
    d = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    for i in range(len(expected) + 1):
        d[i][0] = i
    for j in range(len(actual) + 1):
        d[0][j] = j
    for i, a in enumerate(expected, 1):
        for j, b in enumerate(actual, 1):
            d[i][j] = min(d[i - 1][j - 1] + (a != b), d[i - 1][j] + 1, d[i][j - 1] + 1)
    result: list[Record] = []
    i, j = len(expected), len(actual)
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (expected[i - 1] != actual[j - 1]):
            result.append(
                {
                    "op": "equal" if expected[i - 1] == actual[j - 1] else "substitute",
                    "expected": i - 1,
                    "actual": j - 1,
                }
            )
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            result.append({"op": "delete", "expected": i - 1, "actual": None})
            i -= 1
        else:
            result.append({"op": "insert", "expected": None, "actual": j - 1})
            j -= 1
    return list(reversed(result))


def _local(expected: list[str], actual: list[str]) -> tuple[int, int, int]:
    """Local lexical seed: +3 equal, -3 substitution/gap; latest endpoint wins ties."""
    d = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    best = (0, 0, 0)
    for i, a in enumerate(expected, 1):
        for j, b in enumerate(actual, 1):
            d[i][j] = max(
                0,
                d[i - 1][j - 1] + (3 if a == b else -3),
                d[i - 1][j] - 3,
                d[i][j - 1] - 3,
            )
            if (d[i][j], j, i) > best:
                best = (d[i][j], j, i)
    score, end, i = best
    j = end
    while i and j and d[i][j]:
        if d[i][j] == d[i - 1][j - 1] + (3 if expected[i - 1] == actual[j - 1] else -3):
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] - 3:
            i -= 1
        else:
            j -= 1
    return j, end, score


def _blocks(indices: list[int], words: list[Record]) -> list[tuple[int, int]]:
    """Never bridge a recognized pause over 1.4 s or an already assigned word."""
    blocks: list[tuple[int, int]] = []
    for i in indices:
        gap = (
            i > 0
            and _number(words[i]["start"])
            and _number(words[i - 1]["end"])
            and words[i]["start"] - words[i - 1]["end"] > 1.4
        )
        if not blocks or blocks[-1][1] != i or gap:
            blocks.append((i, i + 1))
        else:
            blocks[-1] = (blocks[-1][0], i + 1)
    return blocks


def _proposal(row: Record, actual: list[str], start: int, end: int) -> Record:
    diff = _diff(row["tokens"], actual[start:end])
    equals = sum(x["op"] == "equal" for x in diff)
    edits = len(diff) - equals
    deleted = sum(x["op"] == "delete" for x in diff)
    added = sum(x["op"] == "insert" for x in diff)
    replaced = sum(x["op"] == "substitute" for x in diff)
    complete = (
        deleted == 0
        and replaced <= math.floor(len(row["tokens"]) * 0.15)
        and added <= math.floor(len(row["tokens"]) * 0.1)
        and diff[0]["op"] in {"equal", "substitute"}
        and diff[-1]["op"] in {"equal", "substitute"}
    )
    return {
        "row": row["id"],
        "word_range": [start, end],
        "diff": diff,
        "equals": equals,
        "edits": edits,
        "complete": complete,
        "row_options": [row["id"]],
    }


def _validate(packet: Record) -> tuple[list[Record], list[Record]]:
    allowed = {
        "version",
        "source",
        "rows",
        "words",
        "provenance",
        "audio_activity",
        "decisions",
        "options",
    }
    if set(packet) - allowed:
        raise ValueError(
            "Unknown discovery fields; reference labels/times are forbidden"
        )
    if packet["version"] != "take-experiment/1":
        raise ValueError("Unsupported experimental version")
    options = packet.get("options", {})
    if (
        set(options) - {"include_partial_alternates"}
        or type(options.get("include_partial_alternates", True)) is not bool
    ):
        raise ValueError("include_partial_alternates must be a boolean")
    source = packet["source"]
    if not _number(source["duration"]) or source["duration"] <= 0:
        raise ValueError("Invalid source duration")
    fps = source["fps"]
    if len(fps) != 2 or any(type(x) is not int or x <= 0 for x in fps):
        raise ValueError("Frame rate must be a positive rational pair")
    rows = [{**deepcopy(r), "tokens": tokens(r["text"])} for r in packet["rows"]]
    if any(not r["tokens"] for r in rows) or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Rows need unique IDs and nonempty text")
    words: list[Record] = []
    for i, w in enumerate(packet["words"]):
        if set(w) - {
            "text",
            "start",
            "end",
            "precision",
            "provenance",
            "confidence",
            "interval",
        }:
            raise ValueError("Unknown word fields; reference annotations are forbidden")
        normalized = tokens(w["text"]) or [""]
        for t in normalized:
            words.append(
                {
                    **deepcopy(w),
                    "token": t,
                    "input_index": i,
                    "precision": w["precision"]
                    if len(normalized) == 1
                    else "shared_interval",
                }
            )
    for activity in packet.get("audio_activity", []):
        a, b = activity["start"], activity["end"]
        if not (_number(a) and _number(b) and 0 <= a < b <= source["duration"]):
            raise ValueError("Invalid source-relative audio activity")
    return rows, words


def _timing(
    words: list[Record], duration: float
) -> tuple[list[str], list[float] | None]:
    problems: set[str] = set()
    previous = -1.0
    previous_input = -1
    for w in words:
        a, b = w["start"], w["end"]
        if a is None or b is None:
            problems.add("missing_timing")
        elif not (_number(a) and _number(b) and 0 <= a < b <= duration):
            problems.add("invalid_timing")
        else:
            if a < previous and w["input_index"] != previous_input:
                problems.add("overlapping_or_reversed_timing")
            previous = b
            previous_input = w["input_index"]
    valid = not problems
    return sorted(problems), [words[0]["start"], words[-1]["end"]] if valid else None


def _handles(
    start: int,
    end: int,
    words: list[Record],
    source: Record,
    activity: list[Record],
    speech: list[float] | None,
) -> Record:
    reasons = ["producer_playback_required"]
    if any(w["precision"] != "acoustic" for w in words[start:end]) or speech is None:
        reasons.append("unproven_word_timing")
    result: Record = {
        "requested_frames": 10,
        "status": "review_needed",
        "range": None,
        "frame_range": None,
        "reasons": reasons,
        "safe": False,
    }
    if speech is None:
        return result
    fps = Fraction(*source["fps"])
    a = math.floor(Fraction(str(speech[0])) * fps) - 10
    b = math.ceil(Fraction(str(speech[1])) * fps) + 10
    lo, hi = float(a / fps), float(b / fps)
    if lo < 0 or hi > source["duration"]:
        reasons.append("source_limit")
    for w in words[:start] + words[end:]:
        if not (_number(w["start"]) and _number(w["end"]) and w["start"] < w["end"]):
            # Untimed material cannot establish a safe adjacent boundary.
            reasons.append("unlocated_speech")
            break
        if w["start"] < hi and w["end"] > lo:
            reasons.append("adjacent_speech")
            break
    for x in activity:
        if (x["start"] < speech[0] and x["end"] > lo) or (
            x["start"] < hi and x["end"] > speech[1]
        ):
            reasons.append("audio_activity_in_handle")
            break
    if not activity:
        reasons.append("audio_boundary_unverified")
    # Activity or absent playback never becomes a safe pass. Only structurally
    # feasible proposals get playable handles; all others retain source context.
    if not set(reasons) & {
        "source_limit",
        "adjacent_speech",
        "unlocated_speech",
        "unproven_word_timing",
        "audio_activity_in_handle",
    }:
        result.update(range=[lo, hi], frame_range=[a, b])
    return result


def _context(start: int, end: int, words: list[Record], duration: float) -> list[float]:
    """Broad playback context, explicitly never a cut proposal."""
    before = [w["start"] for w in words[: start + 1] if _number(w["start"])]
    after = [w["end"] for w in words[end - 1 :] if _number(w["end"])]
    a, b = (
        max(0, (before[-1] if before else 0) - 2),
        min(duration, (after[0] if after else duration) + 2),
    )
    return [a, b] if a < b else [0, duration]


def discover(packet: Record) -> Record:
    """Consume a completed normalized transcript; propose rows without approving."""
    rows, words = _validate(packet)
    actual = [w["token"] for w in words]
    ordered_starts = [w["start"] for w in words if _number(w["start"])]
    source_order_conflict = any(a > b for a, b in pairwise(ordered_starts))
    proposals: list[Record] = []
    # Search complete rows from the transcript end toward the beginning.
    for row in rows:
        expected = row["tokens"]
        for lo, hi in _blocks(list(range(len(words))), words):
            for end in range(hi, lo, -1):
                if actual[end - 1] != expected[-1] and not (
                    len(expected) >= 7
                    and actual[max(lo, end - 3) : end - 1] == expected[-3:-1]
                ):
                    continue
                for start in range(
                    end - 1, max(lo - 1, end - math.ceil(len(expected) * 1.3) - 1), -1
                ):
                    if actual[start] != expected[0] and not (
                        len(expected) >= 7
                        and actual[start + 1 : start + 3] == expected[1:3]
                    ):
                        continue
                    # A fresh first-three-word prefix inside this span is a restart.
                    prefix = expected[: min(3, len(expected))]
                    observed_prefixes = sum(
                        actual[k : k + len(prefix)] == prefix
                        for k in range(start, end - len(prefix) + 1)
                    )
                    expected_prefixes = sum(
                        expected[k : k + len(prefix)] == prefix
                        for k in range(len(expected) - len(prefix) + 1)
                    )
                    if observed_prefixes > expected_prefixes:
                        continue
                    p = _proposal(row, actual, start, end)
                    if p["complete"]:
                        proposals.append(p)
    occupied: set[int] = set()
    selected: list[Record] = []
    proposals.sort(
        key=lambda p: (p["equals"], -p["edits"], p["word_range"][0]), reverse=True
    )
    for p in proposals:
        start, end = p["word_range"]
        if occupied.intersection(range(start, end)):
            for chosen in selected:
                if (
                    chosen["word_range"] == p["word_range"]
                    and chosen["equals"] == p["equals"]
                    and chosen["edits"] == p["edits"]
                    and p["row"] not in chosen["row_options"]
                ):
                    chosen["row_options"].append(p["row"])
            continue
        selected.append(p)
        occupied.update(range(start, end))
    # Recover partials and pickups from remaining speech without consuming a
    # complete candidate's words. The reference is unavailable to this pass.
    # Seed script sentences before local alignment can merge a restarted sentence.
    sentence_proposals = []
    for row in rows:
        spans = sentence_spans(row["text"], tokens)
        if len(spans) < 2:
            continue
        for offset, limit in spans:
            expected = row["tokens"][offset:limit]
            if len(expected) < 3:
                continue
            for lo, hi in _blocks(
                [i for i in range(len(words)) if i not in occupied], words
            ):
                for end in range(hi, lo, -1):
                    if actual[end - 1] != expected[-1]:
                        continue
                    for start in range(max(lo, end - len(expected) - 2), end):
                        if actual[start] != expected[0]:
                            continue
                        diff = _diff(expected, actual[start:end])
                        equals = sum(op["op"] == "equal" for op in diff)
                        if equals / max(len(expected), end - start) < 0.7:
                            continue
                        prefix = expected[: min(3, len(expected))]
                        if sum(
                            actual[k : k + len(prefix)] == prefix
                            for k in range(start, end - len(prefix) + 1)
                        ) > sum(
                            expected[k : k + len(prefix)] == prefix
                            for k in range(len(expected) - len(prefix) + 1)
                        ):
                            continue
                        p = _proposal(row, actual, start, end)
                        p["complete"] = False
                        p["sentence_span"] = [offset, limit]
                        sentence_proposals.append(p)
    sentence_proposals.sort(
        key=lambda p: (p["equals"], -p["edits"], p["word_range"][0]), reverse=True
    )
    for p in sentence_proposals:
        start, end = p["word_range"]
        if occupied.intersection(range(start, end)):
            for chosen in selected:
                if (
                    chosen["word_range"] == p["word_range"]
                    and chosen["equals"] == p["equals"]
                    and chosen["edits"] == p["edits"]
                    and p["row"] not in chosen["row_options"]
                ):
                    chosen["row_options"].append(p["row"])
            continue
        selected.append(p)
        occupied.update(range(start, end))
    while True:
        partials: list[Record] = []
        for lo, hi in _blocks(
            [i for i in range(len(words)) if i not in occupied], words
        ):
            for row in rows:
                a, b, score = _local(row["tokens"], actual[lo:hi])
                if score <= 0:
                    continue
                p = _proposal(row, actual, lo + a, lo + b)
                if (
                    p["equals"] >= min(3, len(row["tokens"]))
                    and p["equals"] / (b - a) >= 0.5
                ):
                    partials.append(p)
        if not partials:
            break
        partials.sort(
            key=lambda p: (p["equals"], -p["edits"], p["word_range"][0]), reverse=True
        )
        p = partials[0]
        p["complete"] = False  # Only the whole-row pass can establish completeness.
        p["row_options"] = sorted(
            {
                q["row"]
                for q in partials
                if q["word_range"] == p["word_range"]
                and q["equals"] == p["equals"]
                and q["edits"] == p["edits"]
            }
        )
        selected.append(p)
        occupied.update(range(*p["word_range"]))
    # Do not turn an exact row substring inside an ad-lib into an exact take.
    for lo, hi in _blocks([i for i in range(len(words)) if i not in occupied], words):
        if any(
            actual[i] in {"first", "earlier", "previous", "last"}
            and actual[i + 1] == "take"
            for i in range(lo, hi - 1)
        ):
            # Off-script edit-note speech remains separate even without a pause.
            continue
        neighbors = []
        for c in selected:
            a, b = c["word_range"]
            if b == lo and _number(words[lo]["start"]) and _number(words[b - 1]["end"]):
                gap = words[lo]["start"] - words[b - 1]["end"]
            elif (
                a == hi and _number(words[a]["start"]) and _number(words[hi - 1]["end"])
            ):
                gap = words[a]["start"] - words[hi - 1]["end"]
            else:
                continue
            if 0 <= gap < 0.6:
                neighbors.append((gap, c))
        neighbors.sort(key=lambda item: item[0])
        if neighbors and (
            len(neighbors) == 1 or neighbors[0][0] + 0.05 < neighbors[1][0]
        ):
            c = neighbors[0][1]
            row = next(row for row in rows if row["id"] == c["row"])
            options = c["row_options"]
            c.update(
                _proposal(
                    row,
                    actual,
                    min(lo, c["word_range"][0]),
                    max(hi, c["word_range"][1]),
                )
            )
            c["row_options"] = options
            c["adjacent_material_attached"] = True
            occupied.update(range(lo, hi))
    for lo, hi in _blocks([i for i in range(len(words)) if i not in occupied], words):
        selected.append(
            {
                "row": None,
                "row_options": [],
                "word_range": [lo, hi],
                "diff": [],
                "complete": False,
                "equals": 0,
                "edits": hi - lo,
            }
        )
    selected.sort(key=lambda p: p["word_range"][0])
    candidates = []
    for index, p in enumerate(selected, 1):
        start, end = p["word_range"]
        timing_issues, speech = _timing(words[start:end], packet["source"]["duration"])
        if source_order_conflict:
            timing_issues.append("source_order_conflict")
        ambiguous = len(p["row_options"]) > 1
        kind = (
            "complete"
            if p["complete"]
            else "modified_read"
            if p["row"] and all(op["op"] != "delete" for op in p["diff"])
            else "partial"
            if p["row"]
            else "unmatched"
        )
        match = (
            "exact"
            if p["complete"] and not p["edits"]
            else "approximate"
            if p["row"]
            else "unmatched"
        )
        candidate = {
            **p,
            "id": f"candidate-{index:03}",
            "kind": kind,
            "match": match,
            "recognized": " ".join(actual[start:end]),
            "speech_range": speech,
            "context_range": _context(start, end, words, packet["source"]["duration"]),
            "timing_issues": timing_issues,
            "eligible": p["complete"]
            and not ambiguous
            and not (set(timing_issues) - {"missing_timing"}),
            "evidence": {
                "equal_tokens": p["equals"],
                "edit_operations": p["edits"],
                "alignment": "lexical_only",
                "acting_quality": "not_scored",
            },
            "uncertainty": (["ambiguous_row"] if ambiguous else [])
            + (["recognition_diff_requires_review"] if match == "approximate" else [])
            + timing_issues,
            "handles": _handles(
                start,
                end,
                words,
                packet["source"],
                packet.get("audio_activity", []),
                speech,
            ),
        }
        candidates.append(candidate)
    groups = []
    for row in rows:
        members = [c for c in candidates if row["id"] in c["row_options"]]
        usable = [c for c in reversed(members) if c["eligible"]]
        suggested = usable[0]["id"] if usable else None
        covered: set[int] = set()
        pieces = []
        complete = [c for c in members if c["complete"] and len(c["row_options"]) == 1]
        partials = []
        for c in members:
            if c["complete"] or len(c["row_options"]) != 1:
                continue
            covered_indices = {
                op["expected"]
                for op in c["diff"]
                if op["op"] in {"equal", "substitute"}
            }
            partials.append(
                {
                    "candidate": c["id"],
                    "covered_token_indices": sorted(covered_indices),
                    "missing_token_indices": sorted(
                        set(range(len(row["tokens"]))) - covered_indices
                    ),
                    "status": "partial_review_needed",
                }
            )
        if not complete:
            # Greedy backward coverage; never materialize edits or label this a take.
            for c in reversed(members):
                if len(c["row_options"]) != 1:
                    continue
                indices = {
                    op["expected"]
                    for op in c["diff"]
                    if op["op"] in {"equal", "substitute"}
                }
                new = indices - covered
                if new:
                    runs: list[list[Record]] = []
                    for op in c["diff"]:
                        if (
                            op["op"] not in {"equal", "substitute"}
                            or op["expected"] not in new
                        ):
                            continue
                        if (
                            not runs
                            or runs[-1][-1]["expected"] + 1 != op["expected"]
                            or runs[-1][-1]["actual"] + 1 != op["actual"]
                        ):
                            runs.append([op])
                        else:
                            runs[-1].append(op)
                    for run in runs:
                        lo = c["word_range"][0] + run[0]["actual"]
                        hi = c["word_range"][0] + run[-1]["actual"] + 1
                        issues, speech = _timing(
                            words[lo:hi], packet["source"]["duration"]
                        )
                        pieces.append(
                            {
                                "candidate": c["id"],
                                "row_token_indices": [op["expected"] for op in run],
                                "source_word_range": [lo, hi],
                                "speech_range": speech,
                                "context_range": _context(
                                    lo, hi, words, packet["source"]["duration"]
                                ),
                                "timing_issues": issues,
                                "transcript_diff": [
                                    op for op in run if op["op"] != "equal"
                                ],
                                "handles": _handles(
                                    lo,
                                    hi,
                                    words,
                                    packet["source"],
                                    packet.get("audio_activity", []),
                                    speech,
                                ),
                                "join_status": "review_needed",
                            }
                        )
                    covered |= new
            pieces.sort(key=lambda piece: piece["row_token_indices"][0])
        ambiguous = any(len(c["row_options"]) > 1 for c in members)
        decision = packet.get("decisions", {}).get(row["id"])
        groups.append(
            {
                "id": f"group-{row['id']}",
                "row": row["id"],
                "candidates": [c["id"] for c in members],
                "default": suggested if decision is None else None,
                "suggested_last_complete": suggested,
                "default_requires_review": True,
                "alternatives": [c["id"] for c in reversed(usable[1:])],
                "partial_alternatives": partials
                if packet.get("options", {}).get("include_partial_alternates", True)
                else [],
                "hidden_partial_count": 0
                if packet.get("options", {}).get("include_partial_alternates", True)
                else len(partials),
                "state": "complete_available"
                if usable
                else "complete_needs_timing"
                if complete
                else "ambiguous"
                if ambiguous
                else "partial_only"
                if members
                else "uncovered",
                "assembly": None
                if usable or not pieces
                else {
                    "status": "review_needed",
                    "pieces": pieces,
                    "uncovered_token_indices": sorted(
                        set(range(len(row["tokens"]))) - covered
                    ),
                    "rendered": False,
                    "reason": "No eligible complete row; all joins require review",
                },
            }
        )
    signals = editorial_signals(words, candidates)
    for group in groups:
        group["editorial_signal_ids"] = [
            s["id"] for s in signals if group["row"] in s["row_options"]
        ]
        if group["editorial_signal_ids"]:
            group["default"] = None
            group["selection_status"] = "producer_choice_required"
            if group["assembly"]:
                group["assembly"]["editorial_signal_ids"] = group[
                    "editorial_signal_ids"
                ]
        else:
            group["selection_status"] = "suggestion_only"
    accounted = [i for c in candidates for i in range(*c["word_range"])]
    spans = sorted(
        [c["speech_range"] for c in candidates if c["speech_range"] is not None]
    )
    source_coverage = []
    cursor = 0.0
    for a, b in spans:
        if a > cursor:
            source_coverage.append(
                {"range": [cursor, a], "state": "unassigned_audio_review"}
            )
        if b > cursor:
            source_coverage.append(
                {"range": [max(cursor, a), b], "state": "recognized_candidate_review"}
            )
            cursor = b
    if cursor < packet["source"]["duration"]:
        source_coverage.append(
            {
                "range": [cursor, packet["source"]["duration"]],
                "state": "unassigned_audio_review",
            }
        )
    return {
        "version": "take-report/1",
        "algorithm_version": "row-review-2",
        "options": {
            "include_partial_alternates": packet.get("options", {}).get(
                "include_partial_alternates", True
            )
        },
        "editorial_signals": signals,
        "source": deepcopy(packet["source"]),
        "provenance": deepcopy(packet["provenance"]),
        "rows": rows,
        "words": words,
        "candidates": candidates,
        "groups": groups,
        "decisions": deepcopy(packet.get("decisions", {})),
        "keeper_approved": False,
        "coverage": {
            "source_intervals": source_coverage,
            "input_words": len(packet["words"]),
            "normalized_tokens": len(words),
            "word_accounting_complete": sorted(accounted) == list(range(len(words))),
            "unmatched_candidates": [
                c["id"] for c in candidates if c["kind"] == "unmatched"
            ],
            "uncovered_rows": [g["row"] for g in groups if g["state"] == "uncovered"],
            "untimed_tokens": [
                i for i, w in enumerate(words) if w["start"] is None or w["end"] is None
            ],
        },
        "limits": [
            "Lexical completeness is not acoustic or performance approval",
            "Pauses over 1.4 seconds split reads conservatively",
            "Unrecognized speech must be found by full-source playback",
            "All proposed handles require producer playback",
        ],
    }


def evaluate(report: Record, references: list[Record]) -> Record:
    """Post-discovery temporal overlap accounting; coarse references imply uncertainty.

    Overlap links are review leads, not verified exact matches or true error counts.
    Unknown outer edges stay unscored. Reference labels never alter candidates.
    """
    links: list[Record] = []
    missed, uncertain = [], []
    for ref in references:
        a, b = ref.get("start"), ref.get("end")
        if not (_number(a) and _number(b) and a < b):
            uncertain.append(ref["id"])
            continue
        matches = [
            c["id"]
            for c in report["candidates"]
            if c["speech_range"] is not None
            and c["speech_range"][0] < b
            and c["speech_range"][1] > a
        ]
        links.append(
            {
                "reference": ref["id"],
                "candidates": matches,
                "status": "overlap_requires_review",
                "coarse": ref.get("coarse", True),
            }
        )
        if not matches:
            missed.append(ref["id"])
    linked = {c for link in links for c in link["candidates"]}
    counts = {
        c["id"]: sum(c["id"] in link["candidates"] for link in links)
        for c in report["candidates"]
    }
    return {
        "reference_cases": len(references),
        "links": links,
        "missed": missed,
        "uncertain": uncertain,
        "possible_false_splits": [x for x in links if len(x["candidates"]) > 1],
        "possible_merges": [c for c, n in counts.items() if n > 1],
        "extras_to_review": [
            c["id"] for c in report["candidates"] if c["id"] not in linked
        ],
        "recognition_errors": "Evaluated separately against frozen verbatim reference",
        "precision": "Temporal overlaps, not proven split/merge judgments",
    }


def evaluate_words(
    report: Record, reference_words: list[str], cases: list[Record]
) -> Record:
    """Separate full-recording recognition errors from per-case segmentation leads."""
    actual = [w["token"] for w in report["words"]]
    operations = _diff(reference_words, actual)
    owner = {i: c["id"] for c in report["candidates"] for i in range(*c["word_range"])}
    mapping = {op["expected"]: op for op in operations if op["expected"] is not None}
    results = []
    for case in cases:
        ops = [mapping[i] for i in case["indices"] if i in mapping]
        candidates = sorted(
            {owner[op["actual"]] for op in ops if op["actual"] is not None}
        )
        results.append(
            {
                "id": case["id"],
                "reference_tokens": len(case["indices"]),
                "equal_tokens": sum(op["op"] == "equal" for op in ops),
                "recognition_missing": sum(op["op"] == "delete" for op in ops),
                "recognition_substitutions": sum(
                    op["op"] == "substitute" for op in ops
                ),
                "candidates": candidates,
                "review_needed": True,
                "segmentation": "possible_split_or_multi_take_label"
                if len(candidates) > 1
                else "unrecovered"
                if not candidates
                else "linked_not_verified",
            }
        )
    return {
        "reference_tokens": len(reference_words),
        "recognized_tokens": len(actual),
        "operation_counts": {
            op: sum(x["op"] == op for x in operations)
            for op in ["equal", "substitute", "delete", "insert"]
        },
        "cases": results,
        "operations": operations,
        "limitation": (
            "Repeated words admit multiple optimal mappings; "
            "all links require independent review"
        ),
    }
