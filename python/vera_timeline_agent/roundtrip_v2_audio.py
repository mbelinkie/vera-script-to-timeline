"""#191 selected-window consistency proof; authentication belongs to #190/#145.

The required receipt verifier is a trusted integration port, never an operator
flag. Local/fake tests do not qualify acoustic review or native rendering.
"""

from __future__ import annotations

import math
import wave
from array import array
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vera_timeline_agent.narration.compiler_dependencies_v2 import _validated_tokens
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.roundtrip_audio import _Files, _metrics, _pcm
from vera_timeline_agent.roundtrip_build import JsonObject, ProofBuildError, _parse

FRAME = 2002
RATE = {"numerator": 24000, "denominator": 1001}
ReceiptVerifier = Callable[[str, bytes, JsonObject], None]


def fact(condition: bool, message: str) -> None:
    if not condition:
        raise ProofBuildError(message)


def shape(value: Any, keys: str, label: str) -> JsonObject:
    fact(isinstance(value, dict) and set(value) == set(keys.split()), f"{label} shape")
    return value  # type: ignore[no-any-return]


def integer(value: Any, minimum: int = 0) -> int:
    fact(
        type(value) is int and minimum <= value <= 9_007_199_254_740_991,
        "exact nonnegative safe integer required",
    )
    return value  # type: ignore[no-any-return]


def identity(value: Any) -> str:
    fact(isinstance(value, str) and 0 < len(value) <= 256, "identity required")
    return value  # type: ignore[no-any-return]


def _observation(
    value: JsonObject, sources: JsonObject, extent: int, target: JsonObject
) -> list[JsonObject]:
    shape(
        value,
        "schemaVersion target extentFrames frameRate programControls routes",
        "observation",
    )
    fact(
        value["schemaVersion"] == "issue-189-v2-audio-observation/v1"
        and value["target"] == target
        and value["frameRate"] == RATE
        and integer(value["extentFrames"], 1) == extent,
        "observation identity/rate/extent",
    )
    fact(
        value["programControls"]
        == {
            "gainDb": 0,
            "effects": [],
            "limiter": False,
            "automation": [],
            "destination": "stereo-program",
        },
        "unknown programme controls",
    )
    fact(
        type(value["programControls"]["gainDb"]) in {int, float}
        and value["programControls"]["limiter"] is False,
        "programme control types differ",
    )
    routes = value["routes"]
    fact(
        isinstance(routes, list) and len(routes) == len(sources),
        "complete route inventory required",
    )
    seen: set[str] = set()
    source_ids: set[str] = set()
    uids: set[str] = set()
    for route in routes:
        shape(route, "id sourceId controls segments", "route")
        rid, sid = identity(route["id"]), identity(route["sourceId"])
        fact(
            rid not in seen and sid not in source_ids and sid in sources,
            "unknown/duplicate route or source",
        )
        seen.add(rid)
        source_ids.add(sid)
        controls = shape(
            route["controls"],
            "enabled mute solo gainDb pan effects sends automation "
            "destination channelMap",
            "controls",
        )
        gain = controls["gainDb"]
        fact(
            controls["enabled"] is True
            and controls["mute"] is False
            and controls["solo"] is False
            and controls["pan"] == 0
            and type(controls["pan"]) in {int, float}
            and controls["effects"] == controls["sends"] == controls["automation"] == []
            and controls["destination"] == "stereo-program"
            and controls["channelMap"]
            == ("mono-dual" if len(sources[sid]) == 1 else "stereo-direct")
            and type(gain) in {float, int}
            and math.isfinite(gain)
            and -60 <= gain <= 6,
            "unknown/unsupported route controls",
        )
        segments = route["segments"]
        fact(isinstance(segments, list) and bool(segments), "partial/removed route")
        previous_record = previous_source = 0
        for segment in segments:
            shape(
                segment,
                "uid recordStart recordEnd sourceStart sourceEnd speed enabled online",
                "segment",
            )
            uid = identity(segment["uid"])
            start, end = (
                integer(segment["recordStart"]),
                integer(segment["recordEnd"], 1),
            )
            sin, sout = (
                integer(segment["sourceStart"]),
                integer(segment["sourceEnd"], 1),
            )
            fact(
                uid not in uids
                and start >= previous_record
                and sin >= previous_source
                and end > start
                and sout > sin
                and end - start == sout - sin
                and end <= extent
                and sout * FRAME <= len(sources[sid][0])
                and segment["speed"] == {"numerator": 1, "denominator": 1}
                and all(type(v) is int for v in segment["speed"].values())
                and segment["enabled"] is True
                and segment["online"] is True,
                "aliased/offline/unsupported source geometry",
            )
            uids.add(uid)
            previous_record, previous_source = end, sout
    return routes  # type: ignore[no-any-return]


def _mix(
    routes: list[JsonObject], sources: JsonObject, extent: int
) -> list[array[float]]:
    mix = [array("d", [0.0]) * (extent * FRAME) for _ in range(2)]
    for route in routes:
        pcm = sources[route["sourceId"]]
        gain = 10 ** (route["controls"]["gainDb"] / 20)
        for segment in route["segments"]:
            count = (segment["recordEnd"] - segment["recordStart"]) * FRAME
            record, source = (
                segment["recordStart"] * FRAME,
                segment["sourceStart"] * FRAME,
            )
            for ch in range(2):
                samples = pcm[0 if len(pcm) == 1 else ch]
                for offset in range(count):
                    mix[ch][record + offset] += samples[source + offset] * gain
    return mix


def verify_selected_omission_v2(
    root: Path,
    *,
    canonical_document_json: bytes,
    expected_document_hash: str,
    baseline_hash: str,
    current_hash: str,
    profile_hash: str,
    row_id: str,
    primary_source_id: str,
    target: JsonObject,
    authenticate: ReceiptVerifier,
) -> JsonObject:
    """Verify complete files, strict supports and one non-ripple audio lift.

    Caller pins derive from a frozen document/compiler and authenticated native
    inventory, not from profile JSON. The receipt port must independently verify
    review provenance and actual native intent/effect/completion; job IDs alone
    cannot satisfy it. The result proves consistency, not real qualification.
    """
    files = _Files(root)
    report: JsonObject = {
        "schemaVersion": "issue-189-v2-omission-evidence/v1",
        "status": "refused",
        "evidenceLevel": "local_consistency_only",
        "documentHash": expected_document_hash,
        "baselineHash": baseline_hash,
        "currentHash": current_hash,
        "profileHash": profile_hash,
        "blockId": row_id,
        "channels": [],
        "limitations": [
            "Receipt authenticity and acoustic review require the trusted "
            "integration port; fake tests are not native/speech qualification.",
            "Residual gates are consistency checks, not speech-absence "
            "classifiers; #145 must qualify frame-safe cuts, source/mix "
            "listening and #190/#178 renders.",
        ],
    }
    try:
        fact(
            sha256_bytes(canonical_document_json) == expected_document_hash,
            "stale document",
        )
        # Preserve compiler canonical bytes; the narration cache serializer differs.
        document = _parse(canonical_document_json)
        shape(target, "projectUid timelineUid", "target")
        for value in target.values():
            identity(value)
        rows = [r for r in document["activeDraft"]["blocks"] if r["id"] == row_id]
        fact(
            len(rows) == 1
            and rows[0]["type"] == "narration"
            and rows[0]["state"] == "active",
            "current active row required",
        )
        row = rows[0]
        integer(row["version"], 1)
        tokens = _validated_tokens(row["text"].encode("utf-16-le"), row["tokens"])
        profile = files.json("profile.json")
        fact(
            files.hashes["profile.json"] == profile_hash,
            "profile/source inventory pin differs",
        )
        shape(
            profile,
            "schemaVersion documentHash blockId blockRevision primarySourceId "
            "extentFrames frameRate sources selectedTokenIds",
            "profile",
        )
        fact(
            profile["schemaVersion"] == "issue-189-v2-selected-audio-profile/v1"
            and profile["documentHash"] == expected_document_hash
            and profile["blockId"] == row_id
            and integer(profile["blockRevision"], 1) == row["version"]
            and profile["primarySourceId"] == primary_source_id
            and profile["frameRate"] == RATE,
            "profile identity/rate differs",
        )
        extent = integer(profile["extentFrames"], 1)
        fact(extent * FRAME <= 3_000_000, "bounded full programme exceeded")
        sources: JsonObject = {}
        hashes: set[str] = set()
        decoded: set[str] = set()
        fact(
            isinstance(profile["sources"], list) and 1 <= len(profile["sources"]) <= 16,
            "complete source inventory required",
        )
        for source in profile["sources"]:
            shape(source, "id path sha256 channels durationSamples", "source")
            sid = identity(source["id"])
            fact(sid not in sources and source["sha256"] not in hashes, "source alias")
            raw = files.read(identity(source["path"]))
            fact(sha256_bytes(raw) == source["sha256"], "stale source bytes")
            channels = integer(source["channels"], 1)
            fact(channels in {1, 2}, "unsupported source channels")
            pcm = _pcm(raw, channels, integer(source["durationSamples"], 960))
            pcm_hashes = {sha256_bytes(ch.tobytes()) for ch in pcm}
            fact(not pcm_hashes.intersection(decoded), "decoded source alias")
            hashes.add(source["sha256"])
            decoded.update(pcm_hashes)
            sources[sid] = pcm
        fact(primary_source_id in sources, "unknown primary source")
        selected = profile["selectedTokenIds"]
        fact(
            isinstance(selected, list)
            and bool(selected)
            and len(set(selected)) == len(selected),
            "unique selection required",
        )
        positions = [
            next((i for i, token in enumerate(tokens) if token["id"] == tid), -1)
            for tid in selected
        ]
        first, last = positions[0], positions[-1]
        fact(
            first > 0
            and last < len(tokens) - 1
            and positions == list(range(first, last + 1)),
            "ordered contiguous interior phrase required",
        )
        review = files.json("review.json")
        shape(
            review,
            "schemaVersion method reviewerReference reviewId reviewRevision "
            "documentHash blockId blockRevision textHash sourceHash supports",
            "review",
        )
        source_hash = next(
            s["sha256"] for s in profile["sources"] if s["id"] == primary_source_id
        )
        fact(
            review["schemaVersion"] == "issue-189-v2-selected-review/v1"
            and review["method"] == "independent_source_listening_waveform/v1"
            and review["documentHash"] == expected_document_hash
            and review["blockId"] == row_id
            and integer(review["blockRevision"], 1) == row["version"]
            and review["textHash"] == sha256_bytes(row["text"].encode())
            and review["sourceHash"] == source_hash,
            "review receipt identity/method differs",
        )
        identity(review["reviewerReference"])
        identity(review["reviewId"])
        integer(review["reviewRevision"], 1)
        supports = review["supports"]
        fact(
            isinstance(supports, list) and len(supports) == len(selected) + 2,
            "selected tokens and immediate neighbors required",
        )
        prior_end = 0
        for support, token in zip(supports, tokens[first - 1 : last + 2], strict=True):
            shape(
                support,
                "tokenId startOffset endOffset quotedText onsetSample endSample",
                "support",
            )
            fact(
                (
                    support["tokenId"],
                    support["startOffset"],
                    support["endOffset"],
                    support["quotedText"],
                )
                == (
                    token["id"],
                    token["startOffset"],
                    token["endOffset"],
                    token["value"],
                ),
                "review token/UTF16/quote differs",
            )
            integer(support["startOffset"])
            integer(support["endOffset"], 1)
            onset, end = (
                integer(support["onsetSample"]),
                integer(support["endSample"], 1),
            )
            fact(
                prior_end <= onset < end <= len(sources[primary_source_id][0]),
                "overlapping/out-of-range reviewed supports",
            )
            prior_end = end
        authenticate(
            "selected_review", files.read("review.json", json_file=True), review
        )
        baseline, current = files.json("baseline.json"), files.json("current-a.json")
        second = files.json("current-b.json")
        fact(
            files.hashes["baseline.json"] == baseline_hash
            and files.hashes["current-a.json"] == current_hash
            and current == second,
            "stale/inconsistent adjacent observations",
        )
        old_routes = _observation(baseline, sources, extent, target)
        new_routes = _observation(current, sources, extent, target)
        for name, _observation_value, pin in (
            ("baseline", baseline, baseline_hash),
            ("current-a", current, current_hash),
            ("current-b", second, files.hashes["current-b.json"]),
        ):
            receipt = files.read(f"{name}-receipt.json", json_file=True)
            authenticate(
                "native_observation",
                receipt,
                {"target": target, "observationHash": pin, "profileHash": profile_hash},
            )
        fact(
            [(r["id"], r["sourceId"], r["controls"]) for r in old_routes]
            == [(r["id"], r["sourceId"], r["controls"]) for r in new_routes],
            "routes/controls changed",
        )
        for old, new in zip(old_routes, new_routes, strict=True):
            if old["sourceId"] != primary_source_id:
                fact(old == new, "unrelated audio changed")
        old = next(r for r in old_routes if r["sourceId"] == primary_source_id)
        new = next(r for r in new_routes if r["sourceId"] == primary_source_id)
        fact(
            len(old["segments"]) == 1 and len(new["segments"]) == 2,
            "exactly one interior lift required (picture-only/extra cuts refused)",
        )
        whole, left, right = old["segments"][0], new["segments"][0], new["segments"][1]
        fact(
            left["uid"] != right["uid"]
            and whole["uid"] not in {left["uid"], right["uid"]},
            "split identities alias",
        )
        fact(
            left["recordStart"] == whole["recordStart"]
            and left["sourceStart"] == whole["sourceStart"]
            and right["recordEnd"] == whole["recordEnd"]
            and right["sourceEnd"] == whole["sourceEnd"]
            and left["recordEnd"] < right["recordStart"]
            and left["sourceEnd"] < right["sourceStart"]
            and left["recordEnd"] - whole["recordStart"]
            == left["sourceEnd"] - whole["sourceStart"]
            and right["recordStart"] - whole["recordStart"]
            == right["sourceStart"] - whole["sourceStart"],
            "baseline-minus-one-interval/no-ripple geometry differs",
        )
        cut_in, cut_out = left["sourceEnd"] * FRAME, right["sourceStart"] * FRAME
        fact(
            whole["sourceStart"] * FRAME <= supports[0]["onsetSample"]
            and supports[0]["endSample"] <= cut_in <= supports[1]["onsetSample"]
            and supports[-2]["endSample"] <= cut_out <= supports[-1]["onsetSample"]
            and supports[-1]["endSample"] <= whole["sourceEnd"] * FRAME,
            "cut clips neighbors or incompletely removes phrase",
        )
        authenticate(
            "native_audio_lift",
            files.read("lift-receipt.json", json_file=True),
            {
                "target": target,
                "baselineHash": baseline_hash,
                "currentHash": current_hash,
                "primarySourceId": primary_source_id,
                "sourceHash": source_hash,
                "originalSegment": whole,
                "retainedSegments": [left, right],
                "sourceIntervalSamples": {"start": cut_in, "end": cut_out},
                "recordIntervalFrames": {
                    "start": left["recordEnd"],
                    "end": right["recordStart"],
                },
                "operation": "lift_audio_without_ripple",
            },
        )
        metrics: list[JsonObject] = []
        for name, routes, pin in (
            ("pristine", old_routes, baseline_hash),
            ("edited", new_routes, current_hash),
        ):
            raw = files.read(f"{name}.wav")
            binding = {
                "target": target,
                "observationHash": pin,
                "outputHash": sha256_bytes(raw),
                "profileHash": profile_hash,
                "settings": {
                    "startFrame": 0,
                    "endFrame": extent,
                    "frameRate": RATE,
                    "sampleRate": 48000,
                    "channels": 2,
                    "codec": "pcm",
                },
            }
            authenticate(
                "native_render",
                files.read(f"{name}-receipt.json", json_file=True),
                binding,
            )
            rendered = _pcm(raw, 2, extent * FRAME)
            predicted = _mix(routes, sources, extent)
            channel_metrics = [
                _metrics([predicted[ch]], [rendered[ch]], [[1.0]])[0] for ch in range(2)
            ]
            metrics.append({"programme": name, "channels": channel_metrics})
        report["channels"] = metrics
        fact(
            all(ch["consistent"] for entry in metrics for ch in entry["channels"]),
            "complete-channel residual gates failed",
        )
        # Independent listening must resolve contamination; residuals cannot.
        authenticate(
            "edited_mix_listening",
            files.read("listening-receipt.json", json_file=True),
            {
                "documentHash": expected_document_hash,
                "reviewHash": files.hashes["review.json"],
                "editedRenderHash": files.hashes["edited.wav"],
                "selectedTokenIds": selected,
                "neighborTokenIds": [supports[0]["tokenId"], supports[-1]["tokenId"]],
            },
        )
        files.current()
        report.update(
            status="verified",
            blockRevision=row["version"],
            tokenIds=selected,
            sourceIntervalSamples={"start": cut_in, "end": cut_out},
            recordIntervalFrames={
                "start": left["recordEnd"],
                "end": right["recordStart"],
            },
        )
    except (
        ProofBuildError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        wave.Error,
        EOFError,
    ) as error:
        report["reason"] = str(error)
    report["inputHashes"] = dict(files.hashes)
    return report
