"""Pure, verified binding of human-approved reads to frozen v2 narration.

No take selection, application I/O or timeline mutation occurs here. In
particular `row-N` is a #45 *passage*, not a v2 narration block UUID or a
#37 prompter beat. We bind only unambiguous complete spoken-token projections.
"""

from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

from experiments.issue53.takes import tokens as normalize_words
from vera_timeline_agent.narration.stage_directions import spoken_tokens
from vera_timeline_agent.presenter_approvals import (
    approved_performance,
    frame_rate,
    match_frozen_read,
    source_identity,
    validate_approvals,
    validate_takes,
)
from vera_timeline_agent.presenter_takes import script_passages
from vera_timeline_agent.recorded_word_evidence import (
    WordEvidenceError,
    canonical_json,
    sha256,
    validated_marks,
)

Json = dict[str, Any]
SCHEMA = "recorded-conform-snapshot/1"
BLOCKED = {"undecided", "needs_pickup", "needs_another_look"}


class ConformRefused(ValueError):
    def __init__(self, problems: str | list[str]):
        self.problems = [problems] if isinstance(problems, str) else problems
        super().__init__("; ".join(self.problems))


def fraction(value: Any, label: str) -> Fraction:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("expected exact rational")
        return Fraction(value)
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ConformRefused(f"invalid exact {label}") from exc


def rational(number: Fraction) -> Json:
    return {"numerator": number.numerator, "denominator": number.denominator}


def approved_interval(row: Json, fps: list[int]) -> tuple[Fraction, Fraction]:
    if (
        not isinstance(fps, list)
        or len(fps) != 2
        or any(type(n) is not int or n <= 0 for n in fps)
    ):
        raise ConformRefused("invalid source frame rate")
    if row.get("state") != "take" or not isinstance(row.get("active"), dict):
        raise ConformRefused("missing verified active approved cut")
    cut = row["active"]
    start, end = cut.get("startFrame"), cut.get("endFrame")
    if any(type(n) is not int for n in (start, end)) or start < 0 or end <= start:
        raise ConformRefused("invalid effective approved source cut")
    rate = Fraction(*fps)
    left, right = Fraction(start, 1) / rate, Fraction(end, 1) / rate
    if cut.get("startS") != str(left) or cut.get("endS") != str(right):
        raise ConformRefused("approved frames disagree with rational seconds")
    return left, right


def local_onset(source_seconds: str, start: Fraction, end: Fraction) -> Fraction:
    onset = fraction(source_seconds, "word onset")
    if onset < start or onset >= end:
        raise ConformRefused("recorded word onset is outside the approved trim")
    return onset - start


def ceil_frames(seconds: Fraction, rate: list[int]) -> int:
    if seconds < 0 or len(rate) != 2 or any(type(n) is not int or n <= 0 for n in rate):
        raise ConformRefused("invalid frame rate or time")
    frames = seconds * Fraction(*rate)
    return -(-frames.numerator // frames.denominator)


def row_impact(rows: list[tuple[str, int, int]]) -> list[Json]:
    old_cursor = new_cursor = 0
    result: list[Json] = []
    for row_id, old_duration, new_duration in rows:
        if any(type(n) is not int or n <= 0 for n in (old_duration, new_duration)):
            raise ConformRefused(f"{row_id}: nonpositive frame duration")
        result.append(
            {
                "rowId": row_id,
                "oldStartFrame": old_cursor,
                "newStartFrame": new_cursor,
                "oldDurationFrames": old_duration,
                "newDurationFrames": new_duration,
                "deltaFrames": new_duration - old_duration,
                "shiftBeforeFrames": new_cursor - old_cursor,
                "shiftAfterFrames": new_cursor
                + new_duration
                - old_cursor
                - old_duration,
            }
        )
        old_cursor += old_duration
        new_cursor += new_duration
    return result


def _spoken_token_binding(block: Json, expected: list[str]) -> list[Json]:
    try:
        tokens = spoken_tokens(block)
    except (ValueError, TypeError) as exc:
        raise ConformRefused(
            f"{block.get('id')}: broken frozen spoken-token projection"
        ) from exc
    if len(tokens) != len(expected):
        raise ConformRefused(
            f"{block.get('id')}: prompter passage spans different token/beat boundaries"
        )
    text = block.get("text")
    if not isinstance(text, str):
        raise ConformRefused("frozen narration has no exact text")
    try:
        encoded = text.encode("utf-16-le")
    except UnicodeError as exc:
        raise ConformRefused("invalid frozen narration UTF-16") from exc
    previous_end = 0
    ids: set[str] = set()
    for token, word in zip(tokens, expected, strict=True):
        tid, left, right, value = (
            token.get("id"),
            token.get("startOffset"),
            token.get("endOffset"),
            token.get("value"),
        )
        if (
            not isinstance(tid, str)
            or tid in ids
            or type(left) is not int
            or type(right) is not int
            or left < previous_end
            or right <= left
            or right > len(encoded) // 2
            or not isinstance(value, str)
        ):
            raise ConformRefused(
                f"{block.get('id')}: invalid frozen token identity/offset"
            )
        try:
            quote = encoded[left * 2 : right * 2].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise ConformRefused("frozen token splits UTF-16 character") from exc
        if quote != value or normalize_words(value) != [word]:
            raise ConformRefused(
                f"{block.get('id')}: script word differs from frozen token"
            )
        previous_end = right
        ids.add(tid)
    return [
        dict(
            id=t["id"],
            value=t["value"],
            startOffset=t["startOffset"],
            endOffset=t["endOffset"],
        )
        for t in tokens
    ]


def _block_binding(
    takes: Json, evidence: Json, doc: Json
) -> dict[str, tuple[Json, list[Json]]]:
    """Reject reordered, duplicated and multi-beat/section-derived ambiguities."""
    blocks = [
        b
        for b in doc.get("activeDraft", {}).get("blocks", [])
        if b.get("type") == "narration"
        and b.get("state") == "active"
        and spoken_tokens(b)
    ]
    rows = takes["rows"]
    if len(blocks) != len(rows):
        raise ConformRefused(
            "prompter passages do not match one frozen active spoken block each"
        )
    by_signature: dict[tuple[str, ...], list[Json]] = {}
    for block in blocks:
        signature = tuple(
            word for t in spoken_tokens(block) for word in normalize_words(t["value"])
        )
        by_signature.setdefault(signature, []).append(block)
    bindings: dict[str, tuple[Json, list[Json]]] = {}
    used: set[str] = set()
    for row, row_evidence in zip(rows, evidence["rows"], strict=True):
        if (
            row_evidence.get("rowId") != row["id"]
            or row_evidence.get("script") != row["script"]
        ):
            raise ConformRefused(f"{row['id']}: sidecar passage/context differs")
        expected = row_evidence.get("scriptWords")
        if (
            not isinstance(expected, list)
            or not expected
            or any(not isinstance(s, str) for s in expected)
        ):
            raise ConformRefused(f"{row['id']}: missing script-word identities")
        candidates = by_signature.get(tuple(expected), [])
        if len(candidates) != 1:
            raise ConformRefused(
                f"{row['id']}: ambiguous or absent exact V2 block for prompter passage"
            )
        block = candidates[0]
        if block["id"] in used:
            raise ConformRefused("V2 narration block reused by multiple passages")
        used.add(block["id"])
        bindings[row["id"]] = block, _spoken_token_binding(block, expected)
    if used != {b["id"] for b in blocks}:
        raise ConformRefused("V2 spoken block is missing a matching #45 passage")
    if [bindings[row["id"]][0]["id"] for row in rows] != [b["id"] for b in blocks]:
        raise ConformRefused("frozen V2 narration row order differs from #45 prompter")
    return bindings


def approval_blockers(report: Json) -> list[str]:
    if report.get("schemaVersion") != "approved-performance/1":
        raise ConformRefused("wrong approved-performance schema")
    rows = report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ConformRefused("missing ordered approval rows")
    issues = []
    for index, row in enumerate(rows, 1):
        if row.get("rowId") != f"row-{index}" or row.get("rowNumber") != index:
            raise ConformRefused("missing/reordered approval passage")
        state = row.get("state")
        if state in BLOCKED:
            issues.append(
                f"{row['rowId']}: {state}: "
                f"{row.get('reason', 'requires a human choice')}"
            )
        elif state == "take" and not isinstance(row.get("active"), dict):
            issues.append(f"{row['rowId']}: verified approved take missing")
        elif state not in {"take", "temp_voice", "no_spoken_line"}:
            issues.append(f"{row['rowId']}: unsupported approval state {state}")
    for orphan in report.get("orphanedDecisions", []):
        issues.append(f"{orphan.get('rowId', '?')}: orphaned approval cannot be built")
    return issues


def conform_snapshot(
    takes: Json,
    approvals: Json,
    video_sha256: str,
    evidence: Json,
    analyzed_script: bytes,
    analyzed_text: str,
    document: Json,
    dependencies: Json,
    *,
    framing: Json | None = None,
) -> Json:
    """Build a deterministic snapshot only after every source and approval check."""
    validate_takes(takes)
    validate_approvals(approvals)
    report = approved_performance(takes, approvals, video_sha256)
    issues = approval_blockers(report)
    if issues:
        raise ConformRefused(issues)
    if evidence.get("schemaVersion") != "take-word-marks/1":
        raise ConformRefused("re-run #45: take-word-marks/1 evidence is missing")
    source_script = evidence.get("sourceScript", {})
    if (
        source_script.get("sha256") != sha256(analyzed_script)
        or source_script.get("textSha256") != sha256(analyzed_text.encode("utf-8"))
        or source_script.get("file") != takes["script"]["file"]
    ):
        raise ConformRefused("#45 analyzed script changed; rerun take analysis")
    passages = script_passages(analyzed_text, set())
    if [p.script for p in passages] != [r["script"] for r in takes["rows"]] or len(
        passages
    ) != len(takes["rows"]):
        raise ConformRefused("take passages differ from exact analyzed prompter script")
    video = evidence.get("video", {})
    if (
        video.get("file") != takes["video"].get("file")
        or video.get("fps") != takes["video"].get("fps")
        or fraction(video.get("durationS"), "video duration")
        != fraction(str(takes["video"]["durationS"]), "video duration")
    ):
        raise ConformRefused("source frame rate or duration differs from word evidence")
    if not isinstance(evidence.get("rows"), list) or len(evidence["rows"]) != len(
        takes["rows"]
    ):
        raise ConformRefused("incomplete take-word-marks passage roster")
    if [row.get("scriptWords") for row in evidence["rows"]] != [
        normalize_words(passage.text) for passage in passages
    ]:
        raise ConformRefused("take-word-marks words differ from analyzed script tokens")
    if video.get("sha256") != video_sha256:
        raise ConformRefused("take-word-marks original camera SHA-256 differs")
    if (
        document.get("schemaVersion") != "script-document/v2"
        or dependencies.get("schemaVersion") != "compiler-dependencies/v2"
    ):
        raise ConformRefused(
            "recorded conform needs a frozen v2 script and compiler dependencies"
        )
    metadata = dependencies.get("document", {})
    for a, b in (
        ("documentId", "id"),
        ("projectId", "projectId"),
        ("liveHeadSequence", "liveHeadSequence"),
        ("contentHash", "liveContentHash"),
    ):
        if metadata.get(a) != document.get(b):
            raise ConformRefused(
                f"V2 frozen script {a} does not match compiler dependencies"
            )
    text = "\n".join(
        b["text"] for b in document["activeDraft"]["blocks"] if b["type"] == "narration"
    )
    if metadata.get("textHash") != "sha256:" + sha256(text.encode("utf-8")):
        raise ConformRefused(
            "V2 document text hash differs from prepared compiler input"
        )
    bindings = _block_binding(takes, evidence, document)
    timing = dependencies.get("narrationTimingMaps")
    if not isinstance(timing, list):
        raise ConformRefused("missing frozen V2 narration timing maps")
    frame_rate_source = takes["video"]["fps"]
    rate = frame_rate(takes["video"])
    framing = framing or {}
    if not isinstance(framing, dict) or set(framing) - {r["id"] for r in takes["rows"]}:
        raise ConformRefused("unknown framing-map row identifier")
    entries: list[Json] = []
    for approved, source_row, sidecar in zip(
        report["rows"], takes["rows"], evidence["rows"], strict=True
    ):
        row_id, state = approved["rowId"], approved["state"]
        block, frozen_tokens = bindings[row_id]
        matching_maps = [m for m in timing if m.get("blockId") == block["id"]]
        if len(matching_maps) != 1:
            raise ConformRefused(
                f"{row_id}: missing or duplicate V2 narration timing map"
            )
        old_map = matching_maps[0]
        if (
            old_map.get("blockRevision") != block.get("version")
            or old_map.get("textHash")
            != "sha256:" + sha256(block["text"].encode("utf-8"))
            or old_map.get("tokenizationVersion") != "script-document/v2-frozen-tokens"
            or old_map.get("audio", {}).get("audioHash") != old_map.get("audioHash")
            or old_map.get("audio", {}).get("narrationAssetId")
            != old_map.get("narrationAssetId")
        ):
            raise ConformRefused(
                f"{row_id}: old V2 timing identity/audio binding is stale"
            )
        if [
            (
                m.get("tokenId"),
                m.get("startOffset"),
                m.get("endOffset"),
                m.get("quotedText"),
            )
            for m in old_map.get("tokens", [])
        ] != [
            (t["id"], t["startOffset"], t["endOffset"], t["value"])
            for t in frozen_tokens
        ]:
            raise ConformRefused(
                f"{row_id}: old V2 token IDs/offsets do not match frozen script"
            )
        picture = framing.get(row_id, "wide")
        if picture not in ("wide", "tight"):
            raise ConformRefused(f"{row_id}: framing must be wide or tight")
        item: Json = {
            "rowId": row_id,
            "blockId": block["id"],
            "blockRevision": block["version"],
            "script": source_row["script"],
            "state": state,
            "framing": picture,
            "frozenTokens": frozen_tokens,
            "oldNarrationAssetId": old_map["narrationAssetId"],
            "oldTimingHash": old_map["timingHash"],
        }
        if state == "take":
            decision = approvals["decisions"][row_id]["active"]
            fresh, reason = match_frozen_read(takes, decision, video_sha256)
            if reason or fresh is None or fresh.get("cut") is None:
                raise ConformRefused(f"{row_id}: saved read is stale: {reason}")
            candidate = {
                "rowId": row_id,
                "takes": fresh["takes"],
                "sourceCut": {
                    "startFrame": fresh["cut"]["startFrame"],
                    "endFrame": fresh["cut"]["endFrame"],
                },
                "said": fresh["said"],
            }
            try:
                marks = validated_marks(sidecar, candidate, sidecar["scriptWords"])
            except WordEvidenceError as exc:
                raise ConformRefused(str(exc)) from exc
            start, end = approved_interval(approved, frame_rate_source)
            measured: list[Json] = []
            for mark, token in zip(marks, frozen_tokens, strict=True):
                onset = local_onset(mark["startS"], start, end)
                absolute_end = fraction(mark["endS"], "audible word end")
                if absolute_end <= start + onset or absolute_end > end:
                    raise ConformRefused(
                        f"{row_id}: measured word end outside approved source cut"
                    )
                measured.append(
                    {
                        "tokenId": token["id"],
                        "sourceWordIndex": mark["recordedWordIndex"],
                        "onset": rational(onset),
                        "audibleEnd": rational(absolute_end - start),
                        "precision": "acoustic",
                    }
                )
            item.update(
                {
                    "sourceFile": approved["active"]["file"],
                    "sourceCut": copy.deepcopy(candidate["sourceCut"]),
                    "effectiveCut": {
                        "startFrame": approved["active"]["startFrame"],
                        "endFrame": approved["active"]["endFrame"],
                    },
                    "sourceRate": [rate.numerator, rate.denominator],
                    "duration": rational(end - start),
                    "wordTiming": measured,
                }
            )
        else:
            item["durationPolicy"] = (
                "retain_verified_original_as_silence"
                if state == "no_spoken_line"
                else "retain_locked_temp_voice"
            )
        entries.append(item)
    raw: Json = {
        "schemaVersion": SCHEMA,
        "document": {
            k: metadata[k]
            for k in (
                "documentId",
                "projectId",
                "revision",
                "liveHeadSequence",
                "contentHash",
                "textHash",
                "settingsHash",
            )
        },
        "source": source_identity(takes["video"], video_sha256),
        "approvalRevision": report["approvalRevision"],
        "analyzedScriptSha256": sha256(analyzed_script),
        "takeEvidenceSha256": sha256(canonical_json(evidence)),
        "compilerDependenciesSha256": sha256(canonical_json(dependencies)),
        "possibleAbruptJoins": report.get("possibleAbruptJoins", []),
        "rows": entries,
        "previewOnly": True,
        "notDeliverable": True,
    }
    return {**raw, "snapshotSha256": sha256(canonical_json(raw))}
