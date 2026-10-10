"""Proposed take-rule refinements on top of the accepted #53 `discover()` output.

Producer direction (2026-10-10, after the recording B row-3 playback): trust
how the presenter delivered a line. Presenters usually redo a line only when
unhappy with it, so a read they did not redo is a keeper candidate as
delivered, including moved words and rewordings. Never restore script order.
Instead, flag keepers that are not word-for-word.

Rules (a post-processing layer; `discover()` itself is unchanged):

1. **Continuous delivery.** Within a row that has no complete read, adjacent
   partial candidates merge into one *delivery run* when the speech gap
   between them is at most PAUSE_SPLIT_S (the #53 pause rule) and the later
   piece repeats none of the script tokens the run already covers (repetition
   = restart). A run covering every row token is a complete read; the last
   such run becomes the default.
2. **Moved words are differences.** A token matched out of script order stays
   in the read and is reported as moved.
3. **Assembly from runs.** Otherwise the row is assembled from the latest run
   covering each still-needed token, taking the contiguous span of that run's
   pieces, so a continuous partial read stays one piece.
4. **Script-difference flag.** Every selected take or piece lists moved,
   substituted, added and omitted words, and `differs_from_script` is true
   when any exist. Informational only: it never blocks a default.

Usage: imported by rerun_53.py / b_playback.py (`refine(report)`).
"""

from __future__ import annotations

import copy
from typing import Any

PAUSE_SPLIT_S = 1.4
Record = dict[str, Any]


def _row_tokens(row: Record) -> list[str]:
    from experiments.issue53.takes import tokens  # the same tokeniser discover() used

    return tokens(row["text"])


def _pairs(c: Record) -> list[tuple[int, int, str]]:
    """(source word index, script token index, op) for equal/substitute ops."""
    base = c["word_range"][0]
    return [
        (base + o["actual"], o["expected"], o["op"])
        for o in c["diff"]
        if o["op"] in ("equal", "substitute")
        and o["actual"] is not None
        and o["expected"] is not None
    ]


def _covered(c: Record) -> set[int]:
    return {e for _, e, _ in _pairs(c)}


def _span_s(c: Record) -> tuple[float, float] | None:
    r = c.get("speech_range")
    return (r[0], r[1]) if r else None


def _runs(cands: list[Record]) -> list[list[Record]]:
    runs: list[list[Record]] = []
    for c in sorted(cands, key=lambda c: c["word_range"][0]):
        if runs:
            run = runs[-1]
            prev, cur = _span_s(run[-1]), _span_s(c)
            seen = set().union(*(_covered(x) for x in run))
            gap_ok = (
                prev is not None
                and cur is not None
                and 0 <= cur[0] - prev[1] <= PAUSE_SPLIT_S
            )
            near = c["word_range"][0] - run[-1]["word_range"][1] <= 2
            if gap_ok and near and not (_covered(c) & seen):
                run.append(c)
                continue
        runs.append([c])
    return runs


def differences(
    pieces: list[Record],
    row_tok: list[str],
    words: list[Record],
    needed: set[int] | None,
) -> Record:
    """Moved / substituted / added / omitted words for one selected take."""
    pairs = sorted(p for c in pieces for p in _pairs(c))
    if not pairs:
        return {"differs_from_script": False}
    lo, hi = pairs[0][0], pairs[-1][0]
    matched_src = {s for s, _, _ in pairs}
    # Words outside the longest in-script-order subsequence are the moved ones.
    seq = [e for _, e, _ in pairs]
    tails: list[int] = []
    prev = [-1] * len(seq)
    idx_at: list[int] = []
    for i, e in enumerate(seq):
        lo_, hi_ = 0, len(tails)
        while lo_ < hi_:
            mid = (lo_ + hi_) // 2
            if tails[mid] < e:
                lo_ = mid + 1
            else:
                hi_ = mid
        if lo_ == len(tails):
            tails.append(e)
            idx_at.append(i)
        else:
            tails[lo_] = e
            idx_at[lo_] = i
        prev[i] = idx_at[lo_ - 1] if lo_ else -1
    keep, k = set(), idx_at[-1] if idx_at else -1
    while k != -1:
        keep.add(k)
        k = prev[k]
    moved = [
        {"word": words[pairs[i][0]]["token"], "script_position": pairs[i][1]}
        for i in range(len(pairs))
        if i not in keep
    ]
    from textnorm import normalise_token

    # A numeral read aloud ("99" -> "ninety nine") is not a difference.
    spoken_ok: set[int] = set()
    for s_, e, op in pairs:
        spelled = normalise_token(row_tok[e])
        if (op == "substitute" and len(spelled) > 1) or (
            op == "substitute" and spelled != [row_tok[e]]
        ):
            if words[s_]["token"] in spelled:
                spoken_ok.add(s_)
                for k in range(s_ - len(spelled) + 1, s_ + len(spelled)):
                    if (
                        k not in matched_src
                        and 0 <= k < len(words)
                        and words[k]["token"] in spelled
                    ):
                        spoken_ok.add(k)
    subs = [
        {"script": row_tok[e], "said": words[s_]["token"]}
        for s_, e, op in pairs
        if op == "substitute" and s_ not in spoken_ok
    ]
    added = [
        words[k]["token"]
        for k in range(lo, hi + 1)
        if k not in matched_src and k not in spoken_ok
    ]
    covered = {e for _, e, _ in pairs}
    omitted = [
        row_tok[e]
        for e in sorted(
            (needed if needed is not None else set(range(len(row_tok)))) - covered
        )
    ]
    out = {"moved": moved, "substituted": subs, "added": added, "omitted": omitted}
    out["differs_from_script"] = any(out.values())
    return out


def _run_record(
    run: list[Record], row_tok: list[str], words: list[Record], tokens: set[int]
) -> Record:
    pairs = sorted(p for c in run for p in _pairs(c) if p[1] in tokens)
    return {
        "members": [c["id"] for c in run],
        "source_word_range": [pairs[0][0], pairs[-1][0] + 1],
        "differences": differences(run, row_tok, words, tokens),
    }


def _alternates(
    runs: list[list[Record]],
    chosen: list[Record],
    tokens: set[int],
    row_tok: list[str],
    words: list[Record],
) -> list[Record]:
    """Earlier delivery runs that fully cover `tokens`, newest first (usable alternates).

    Abandoned attempts (cut off and restarted) never cover the whole span, so
    they are not offered. The chosen (last) delivery stays the default.
    """
    out = []
    first = min(c["word_range"][0] for c in chosen)
    for run in reversed(runs):
        if run[-1]["word_range"][1] > first:
            continue
        if set().union(*(_covered(c) for c in run)) >= tokens:
            out.append(_run_record(run, row_tok, words, tokens))
    return out


def refine(report: Record) -> Record:
    r = copy.deepcopy(report)
    words = r["words"]
    by_id = {c["id"]: c for c in r["candidates"]}
    r["take_rules_v2"] = {"rows": []}
    for row, g in zip(r["rows"], r["groups"], strict=True):
        row_tok = _row_tokens(row)
        info: Record = {"row": row["id"]}
        partials_all = [c for c in r["candidates"] if c["row"] == row["id"]]
        runs_all = _runs([c for c in partials_all if not c["complete"]]) + [
            [c] for c in partials_all if c["complete"]
        ]
        runs_all.sort(key=lambda run: run[0]["word_range"][0])
        everything = set(range(len(row_tok)))
        if g["suggested_last_complete"]:
            c = by_id[g["suggested_last_complete"]]
            info.update(
                selected="last complete read (discover)",
                differences=differences([c], row_tok, words, None),
                alternates=_alternates(runs_all, [c], everything, row_tok, words),
            )
            r["take_rules_v2"]["rows"].append(info)
            continue
        partials = [
            c for c in r["candidates"] if c["row"] == row["id"] and not c["complete"]
        ]
        runs = _runs(partials)
        complete_runs = [
            run
            for run in runs
            if set().union(*(_covered(c) for c in run)) >= set(range(len(row_tok)))
        ]
        if complete_runs:
            run = complete_runs[-1]
            synthetic = {
                "id": f"run-{row['id']}",
                "row": row["id"],
                "kind": "delivery_run",
                "complete": True,
                "word_range": [run[0]["word_range"][0], run[-1]["word_range"][1]],
                "members": [c["id"] for c in run],
                "diff": [],
                "match": "approximate",
            }
            r["candidates"].append(synthetic)
            g["suggested_last_complete"] = synthetic["id"]
            g["assembly"] = None
            info.update(
                selected="continuous delivery run (complete)",
                members=synthetic["members"],
                differences=differences(run, row_tok, words, None),
                alternates=_alternates(runs_all, run, everything, row_tok, words),
            )
            r["take_rules_v2"]["rows"].append(info)
            continue
        needed, pieces = set(range(len(row_tok))), []
        for run in reversed(runs):
            hits = [i for i, c in enumerate(run) if _covered(c) & needed]
            if not hits:
                continue
            chunk = run[hits[0] : hits[-1] + 1]
            cov = set().union(*(_covered(c) for c in chunk)) & needed
            pairs = sorted(p for c in chunk for p in _pairs(c))
            pieces.append(
                {
                    "members": [c["id"] for c in chunk],
                    "row_token_indices": sorted(cov),
                    "source_word_range": [pairs[0][0], pairs[-1][0] + 1],
                    "differences": differences(chunk, row_tok, words, cov),
                    "alternates": _alternates(runs_all, chunk, cov, row_tok, words),
                }
            )
            needed -= cov
            if not needed:
                break
        pieces.sort(key=lambda p: p["row_token_indices"][0])
        if g.get("assembly") is not None or pieces:
            g["assembly"] = {
                "status": "review_needed",
                "pieces": pieces,
                "missing_row_tokens": sorted(needed),
            }
        info.update(
            selected="assembly from delivery runs",
            pieces=len(pieces),
            missing=len(needed),
        )
        r["take_rules_v2"]["rows"].append(info)
    return r
