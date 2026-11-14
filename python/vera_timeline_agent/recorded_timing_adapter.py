"""Deterministic preview-only audio duration bindings and impact geometry.

This produces ordinary V2 compiler maps, not a second timeline compiler.
Silence WAVs are conspicuously NOT_DELIVERABLE and must be replaced for #48.
"""

from __future__ import annotations

import copy
import hashlib
import math
import struct
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.recorded_conform import (
    ConformRefused,
    ceil_frames,
    rational,
)
from vera_timeline_agent.recorded_word_evidence import canonical_json

Json = dict[str, Any]
_ZERO_CHUNK = bytes(1024 * 1024)


def wire(value: Json) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise ConformRefused("malformed reduced rational time")
    n, d = value["numerator"], value["denominator"]
    if (
        type(n) is not int
        or type(d) is not int
        or n < 0
        or d <= 0
        or math.gcd(n, d) != 1
    ):
        raise ConformRefused("non-reduced or negative rational time")
    return Fraction(n, d)


def frames_for_audio(audio: Json, rate: list[int]) -> int:
    count, sample_rate = audio.get("durationSamples"), audio.get("sampleRate")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count <= 0
        or not isinstance(sample_rate, int)
        or isinstance(sample_rate, bool)
        or sample_rate <= 0
    ):
        raise ConformRefused("narration audio duration/sample-rate missing")
    return ceil_frames(Fraction(count, sample_rate), rate)


def _wav_header(sample_rate: int, samples: int) -> bytes:
    # No date, encoder version, RIFF extra chunk or platform-native padding.
    if (
        type(sample_rate) is not int
        or type(samples) is not int
        or sample_rate <= 0
        or samples <= 0
        or samples > (2**32 - 36) // 2
    ):
        raise ConformRefused("preview carrier duration exceeds safe PCM16 WAV limit")
    size = samples * 2
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        size,
    )


def silent_carrier(sample_rate: int, samples: int) -> Json:
    """Compute the digest for bytes which will actually be published."""
    header = _wav_header(sample_rate, samples)
    digest = hashlib.sha256(header)
    remaining = samples * 2
    while remaining:
        size = min(remaining, len(_ZERO_CHUNK))
        digest.update(memoryview(_ZERO_CHUNK)[:size])
        remaining -= size
    sha = digest.hexdigest()
    return {
        "name": f"preview-only-{sha}.wav",
        "sha256": sha,
        "sampleRate": sample_rate,
        "durationSamples": samples,
        "channels": 1,
        "previewOnly": True,
        "notDeliverable": True,
    }


def write_silent_carrier(carrier: Json, output: Path) -> None:
    """Materialize and independently verify a pure silent timing carrier."""
    target = output / carrier["name"]
    if target.exists() or target.is_symlink():
        raise ConformRefused("preview audio target already exists")
    remaining = carrier["durationSamples"] * 2
    digest = hashlib.sha256()
    with target.open("xb") as stream:
        header = _wav_header(carrier["sampleRate"], carrier["durationSamples"])
        stream.write(header)
        digest.update(header)
        while remaining:
            size = min(remaining, len(_ZERO_CHUNK))
            chunk = memoryview(_ZERO_CHUNK)[:size]
            stream.write(chunk)
            digest.update(chunk)
            remaining -= size
    if digest.hexdigest() != carrier["sha256"]:
        raise ConformRefused("preview WAV written bytes differ from pinned audio hash")


def _preview_id(snapshot_id: str, row_id: str) -> str:
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#47:{snapshot_id}:{row_id}:preview-only")
    )


def derived_dependencies(snapshot: Json, dependencies: Json) -> tuple[Json, list[Json]]:
    """Replace audio AND timing pins; retaining old sample duration is invalid."""
    rate = dependencies["timeline"]["frameRate"]
    if any(
        type(rate.get(k)) is not int or rate[k] <= 0
        for k in ("numerator", "denominator")
    ):
        raise ConformRefused("invalid target timeline frame rate")
    result = copy.deepcopy(dependencies)
    by_id = {m["blockId"]: m for m in result["narrationTimingMaps"]}
    if len(by_id) != len(result["narrationTimingMaps"]):
        raise ConformRefused("duplicated original V2 timing map")
    carriers: dict[str, Json] = {}
    for row in snapshot["rows"]:
        if row["state"] == "temp_voice":
            continue  # the approved locked temporary voice is unchanged
        old = by_id[row["blockId"]]
        if row["state"] == "take":
            source_rate = Fraction(*row["sourceRate"])
            cut = row["effectiveCut"]
            exact_duration = (
                Fraction(cut["endFrame"] - cut["startFrame"], 1) / source_rate
            )
            # Choose the exact LCM: 30000/1001 source and 48 kHz timeline
            # require 240 kHz for a sample-exact integer-frame duration.
            sample_rate = math.lcm(48000, row["sourceRate"][0])
            if sample_rate > 384000:
                raise ConformRefused(
                    f"{row['rowId']}: no safe sample-exact preview audio rate"
                )
            samples = exact_duration * sample_rate
            if samples.denominator != 1:
                raise ConformRefused(f"{row['rowId']}: source cut is not sample-exact")
            sample_count = samples.numerator
        else:
            sample_rate = old["audio"]["sampleRate"]
            sample_count = old["audio"]["durationSamples"]
        carrier = silent_carrier(sample_rate, sample_count)
        carriers[carrier["name"]] = carrier
        unique_id = _preview_id(snapshot["snapshotSha256"], row["rowId"])
        if row["state"] == "take":
            aligned = []
            for token, measured in zip(
                row["frozenTokens"], row["wordTiming"], strict=True
            ):
                onset, end = wire(measured["onset"]), wire(measured["audibleEnd"])
                if (
                    onset < 0
                    or end <= onset
                    or end > Fraction(sample_count, sample_rate)
                ):
                    raise ConformRefused(
                        f"{row['rowId']}: word time exceeds verified preview duration"
                    )
                aligned.append(
                    {
                        "tokenId": token["id"],
                        "startOffset": token["startOffset"],
                        "endOffset": token["endOffset"],
                        "quotedText": token["value"],
                        "startTime": rational(onset),
                        "audibleEnd": rational(end),
                        "endBasis": "evidenced_audible_end",
                    }
                )
            old["tokens"] = aligned
            old["alignmentVersion"] = "recorded-conform/1"
            old["precision"] = "audible_word_marks"
        else:
            # For explicitly silent passages, the old frozen map remains a
            # syntactic V2 token projection. No word anchor may use it as
            # acoustic evidence; the caller checks for such anchors.
            old["alignmentVersion"] = "recorded-conform-silence/1"
        old["narrationAssetId"] = unique_id
        old["audioHash"] = f"sha256:{carrier['sha256']}"
        old["timingHash"] = (
            "sha256:"
            + hashlib.sha256(
                canonical_json(
                    {
                        "rowId": row["rowId"],
                        "assetId": unique_id,
                        "audioHash": old["audioHash"],
                        "tokens": old["tokens"],
                        "alignmentVersion": old["alignmentVersion"],
                    }
                )
            ).hexdigest()
        )
        old["audio"] = {
            "narrationAssetId": unique_id,
            "audioHash": old["audioHash"],
            "timingHash": old["timingHash"],
            "cacheAssetId": carrier["sha256"],
            "locator": f"RecordedConform/preview-only/{carrier['name']}",
            "durationSamples": sample_count,
            "sampleRate": sample_rate,
            "channels": 1,
        }
    return result, sorted(carriers.values(), key=lambda carrier: carrier["name"])


def _timeline_rows(document: Json, deps: Json) -> list[Json]:
    """Use compiler's documented audio sample/visual-only duration rules."""
    rate_obj = deps["timeline"]["frameRate"]
    rate = [rate_obj["numerator"], rate_obj["denominator"]]
    maps = {item["blockId"]: item for item in deps["narrationTimingMaps"]}
    descriptors = {
        item["payloadId"]: item for item in deps.get("occurrenceResolutions", [])
    }
    cursor = 0
    rows = []
    for block in document["activeDraft"]["blocks"]:
        if block["type"] == "narration" and block.get("state") == "active":
            duration = frames_for_audio(maps[block["id"]]["audio"], rate)
        elif block["type"] == "visual_only":
            timing = block["visualOnlyTiming"]
            if "selectedSourceRange" in timing:
                d = descriptors[block["payload"]["payloadId"]]
                source_rate = d["logicalSourceBounds"]["frameRate"]
                seconds = Fraction(
                    timing["selectedSourceRange"]["durationFrames"]
                    * source_rate["denominator"],
                    source_rate["numerator"],
                )
            else:
                seconds = Fraction(
                    timing.get(
                        "durationOverrideMs",
                        deps["authoringDefaults"]["visualOnlyStillDurationMs"],
                    ),
                    1000,
                )
            duration = ceil_frames(seconds, rate)
        else:
            continue
        if duration <= 0:
            raise ConformRefused(f"{block['id']}: zero row duration")
        rows.append(
            {"blockId": block["id"], "startFrame": cursor, "durationFrames": duration}
        )
        cursor += duration
    return rows


def _word_frame(point: Json, map_: Json, start: int, rate: list[int]) -> int:
    token = next(
        (t for t in map_["tokens"] if t["tokenId"] == point.get("tokenId")), None
    )
    if token is None:
        raise ConformRefused(
            f"word anchor targets missing frozen token {point.get('tokenId')}"
        )
    basis = point.get("affinity")
    if basis == "before":
        timed = token["startTime"]
    elif basis == "after":
        timed = token.get("audibleEnd")
        if timed is None or token.get("endBasis") != "evidenced_audible_end":
            raise ConformRefused(
                f"word anchor requires evidenced audible end: {point['tokenId']}"
            )
    else:
        raise ConformRefused("unsupported word anchor affinity")
    return start + ceil_frames(wire(timed), rate)


def impact_report(snapshot: Json, document: Json, old: Json, new: Json) -> Json:
    """Compare exact timing geometry and report conservative source shortages.

    The existing compiler performs final media/transition validity. We do
    *not* call incomplete visual source coverage compiler-ready here.
    """
    target = new["timeline"]["frameRate"]
    rate = [target["numerator"], target["denominator"]]
    prior = {r["blockId"]: r for r in _timeline_rows(document, old)}
    after = {r["blockId"]: r for r in _timeline_rows(document, new)}
    old_maps = {m["blockId"]: m for m in old["narrationTimingMaps"]}
    new_maps = {m["blockId"]: m for m in new["narrationTimingMaps"]}
    blocks = {b["id"]: b for b in document["activeDraft"]["blocks"]}
    descriptors = {d["payloadId"]: d for d in new.get("occurrenceResolutions", [])}
    changes: list[Json] = []
    moved: list[Json] = []
    short: list[Json] = []
    needs_manual: list[str] = []
    for row in snapshot["rows"]:
        block_id = row["blockId"]
        prev, next_ = prior[block_id], after[block_id]
        old_start, new_start = prev["startFrame"], next_["startFrame"]
        old_len, new_len = prev["durationFrames"], next_["durationFrames"]
        changes.append(
            {
                "rowId": row["rowId"],
                "blockId": block_id,
                "source": row["state"],
                "framing": row["framing"],
                "oldStartFrame": old_start,
                "newStartFrame": new_start,
                "oldDurationFrames": old_len,
                "newDurationFrames": new_len,
                "deltaFrames": new_len - old_len,
                "shiftBeforeFrames": new_start - old_start,
                "shiftAfterFrames": new_start + new_len - old_start - old_len,
            }
        )
        block = blocks[block_id]
        seq = block.get("primaryVisualSequence") or {}
        slots = [s for s in seq.get("slots", []) if s.get("kind") == "content"]
        for slot in slots:
            boundary = slot.get("boundaryBefore", {})
            if boundary.get("kind") in ("spoken_word", "audible_word_end"):
                token = boundary["anchor"]
                if row["state"] == "no_spoken_line":
                    raise ConformRefused(
                        f"{row['rowId']}: silent passage has word-anchored picture"
                    )
                was = _word_frame(token, old_maps[block_id], old_start, rate)
                now = _word_frame(token, new_maps[block_id], new_start, rate)
                moved.append(
                    {
                        "rowId": row["rowId"],
                        "ownerId": slot["id"],
                        "kind": "primary_visual_word_anchor",
                        "tokenId": token["tokenId"],
                        "oldFrame": was,
                        "newFrame": now,
                        "deltaFrames": now - was,
                    }
                )
        for event in block.get("overlayEvents", []):
            for edge in ("start", "end"):
                point = event.get("timing", {}).get(edge, {})
                if point.get("kind") not in ("word", "audible_word_end"):
                    continue
                if row["state"] == "no_spoken_line":
                    raise ConformRefused(
                        f"{row['rowId']}: silent passage has word-anchored overlay"
                    )
                anchor = point["anchor"]
                was = _word_frame(anchor, old_maps[block_id], old_start, rate)
                now = _word_frame(anchor, new_maps[block_id], new_start, rate)
                moved.append(
                    {
                        "rowId": row["rowId"],
                        "ownerId": event["id"],
                        "kind": f"overlay_{edge}",
                        "tokenId": anchor["tokenId"],
                        "oldFrame": was,
                        "newFrame": now,
                        "deltaFrames": now - was,
                    }
                )
        # A single match-interval clip spans the whole row, a provable
        # sufficient/insufficient source bound without guessing multi-slot
        # or transition geometry (which the v2 compiler resolves later).
        if len(slots) == 1:
            slot = slots[0]
            payload = slot.get("payload", {})
            if (
                payload.get("kind") == "visual"
                and payload.get("pictureKind") == "clip"
                and slot.get("playoutPolicy") == "match_structural_interval"
            ):
                d = descriptors.get(payload["payloadId"])
                if d is None:
                    raise ConformRefused(f"{row['rowId']}: missing source descriptor")
                bounds = d["logicalSourceBounds"]
                fs = Fraction(
                    bounds["frameRate"]["numerator"], bounds["frameRate"]["denominator"]
                )
                offset = d["occurrenceSourceInFrame"]
                origin = d["sourceFrameMap"]["packageFrameZeroLogicalFrame"]
                source_start = Fraction(offset - origin, 1) / fs
                required = origin + ceil_frames(
                    source_start + Fraction(new_len, 1) / Fraction(*rate),
                    [
                        bounds["frameRate"]["numerator"],
                        bounds["frameRate"]["denominator"],
                    ],
                )
                authored = payload.get("selectedSourceRange")
                available_end = min(
                    bounds["endFrame"],
                    authored["startFrame"] + authored["durationFrames"]
                    if authored
                    else bounds["endFrame"],
                )
                if required > available_end:
                    short.append(
                        {
                            "rowId": row["rowId"],
                            "ownerId": slot["id"],
                            "payloadId": payload["payloadId"],
                            "sourceId": d["mediaReferenceId"],
                            "requiredRange": {
                                "startFrame": offset,
                                "endFrame": required,
                            },
                            "availableRange": {
                                "startFrame": bounds["startFrame"],
                                "endFrame": available_end,
                            },
                            "code": "SOURCE_INSUFFICIENT",
                        }
                    )
        elif slots:
            needs_manual.append(
                f"{row['rowId']}: multi-slot geometry needs compiler media requirements"
            )
    return {
        "schemaVersion": "recorded-conform-impact/1",
        "rows": changes,
        "movedPictureAnchors": moved,
        "shortSources": short,
        "needsCompilerReview": needs_manual,
        "requires_reconciliation": bool(short or needs_manual),
        "compilerReady": False,  # only the actual compiler can affirm ready
        "previewOnly": True,
        "notDeliverable": True,
    }


def impact_text(impact: Json) -> str:
    lines = [
        "Recorded conform preview (NOT DELIVERABLE to Resolve)",
        "Frame counts are at the frozen target timeline rate.",
    ]
    for row in impact["rows"]:
        lines.append(
            f"{row['rowId']} [{row['source']}, {row['framing']}]: "
            f"old {row['oldDurationFrames']}f -> new {row['newDurationFrames']}f "
            f"(delta {row['deltaFrames']:+}f; after moves {row['shiftAfterFrames']:+}f)"
        )
    for item in impact["movedPictureAnchors"]:
        lines.append(
            f"Picture {item['ownerId']} / word {item['tokenId']}: "
            f"{item['oldFrame']}f -> {item['newFrame']}f ({item['deltaFrames']:+}f)"
        )
    for item in impact["shortSources"]:
        lines.append(
            f"SHORT SOURCE {item['sourceId']} / {item['ownerId']}: "
            f"required {item['requiredRange']}, available {item['availableRange']}; "
            "requires reconciliation; no looping/stretching"
        )
    lines.extend(impact["needsCompilerReview"])
    lines.append(
        "Requires reconciliation"
        if impact["requires_reconciliation"]
        else "Geometry preview only; compile with verified prepared media "
        "before delivery"
    )
    return "\n".join(lines) + "\n"
