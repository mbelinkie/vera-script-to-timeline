"""#191 selected-window consistency proof; authentication belongs to #190/#145.

The required receipt verifier is a trusted integration port, never an operator
flag. Local/fake tests do not qualify acoustic review or native rendering.
Rejected receipts must raise ProofBuildError through the trusted port.
"""

from __future__ import annotations

import io
import json
import math
import re
import wave
from array import array
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.narration.compiler_dependencies_v2 import _validated_tokens
from vera_timeline_agent.narration.measure import (
    ALGORITHM_ID as MEASURE_ALGORITHM_ID,
)
from vera_timeline_agent.narration.measure import (
    ALGORITHM_VERSION as MEASURE_ALGORITHM_VERSION,
)
from vera_timeline_agent.narration.measure import (
    ARTIFACT_VERSION as MEASURE_ARTIFACT_VERSION,
)
from vera_timeline_agent.narration.measure import (
    DEFAULT_PARAMETERS,
    MeasurementError,
    parameters_hash,
)
from vera_timeline_agent.narration.measure import (
    ONSET_BASIS as MEASURE_ONSET_BASIS,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes
from vera_timeline_agent.narration.normalize import NORMALIZER_VERSION
from vera_timeline_agent.roundtrip_audio import _Files, _metrics, _pcm
from vera_timeline_agent.roundtrip_build import (
    JsonObject,
    ProofBuildError,
    _parse,
    _regular,
)

FRAME = 2002
RATE = {"numerator": 24000, "denominator": 1001}
ReceiptVerifier = Callable[[str, bytes, JsonObject], None]


def _source_pcm(
    files: _Files, name: str, channels: int, count: int, expected_hash: str
) -> list[array[float]]:
    # Source offsets can exceed programme duration; #189 uses source frame 2756.
    path = Path(name)
    fact(
        not path.is_absolute()
        and bool(path.parts)
        and not {"..", "."}.intersection(path.parts),
        "independent local source path required",
    )
    full = _regular(files.root / path)
    fact(full.stat().st_size <= 128 * 1024 * 1024, "bounded source PCM exceeds 128 MiB")
    raw = full.read_bytes()
    digest = sha256_bytes(raw)
    fact(digest == expected_hash, "stale source bytes")
    fact(
        name not in files.hashes or files.hashes[name] == digest,
        "source changed during reading",
    )
    files.hashes[name] = digest
    with wave.open(io.BytesIO(raw), "rb") as stream:
        width = stream.getsampwidth()
        fact(
            (stream.getframerate(), stream.getnchannels(), stream.getcomptype())
            == (48000, channels, "NONE")
            and width in {2, 3},
            "expected complete source PCM16/24 WAV at 48k",
        )
        fact(
            960 <= count <= 16_000_000 and stream.getnframes() == count,
            "complete source extent differs",
        )
        pcm = stream.readframes(count + 1)
        fact(len(pcm) == count * channels * width, "truncated source PCM")
    scale = 2 ** (width * 8 - 1)
    values = array(
        "d",
        (
            int.from_bytes(pcm[i : i + width], "little", signed=True) / scale
            for i in range(0, len(pcm), width)
        ),
    )
    return [values[channel::channels] for channel in range(channels)]


def fact(condition: bool, message: str) -> None:
    if not condition:
        raise ProofBuildError(message)


def reviewed_artifact_hash(row: Any) -> str:
    """Review artifact hash of reviewed boundary evidence; refuse measured evidence.

    These proof paths bind a human-review receipt.  Measured evidence (#182) has
    a measurement artifact instead and is not accepted here.
    """

    verification = row.get("verification") if isinstance(row, dict) else None
    method = verification.get("method") if isinstance(verification, dict) else None
    # Legacy reviewed records carry no method field; only measured/unknown
    # methods and records without a review artifact are refused.
    fact(
        isinstance(verification, dict)
        and method in (None, "reviewed_audio_boundaries/v1")
        and "reviewArtifactHash" in verification,
        f"boundary evidence method {method!r} is not supported by this "
        "reviewed-only proof path (measured evidence has no review artifact)",
    )
    return str(verification["reviewArtifactHash"])  # type: ignore[index]


MEASURED_NARRATION_METHOD = "measured_audio_boundaries/v1"
REVIEWED_NARRATION_METHOD = "reviewed_audio_boundaries/v1"
_VERIFICATION_KEYS = {
    "method",
    "algorithm",
    "measurementArtifactLocator",
    "measurementArtifactHash",
    "onsetBasis",
    "onsetUncertainty",
    "audibleEndUncertainty",
}
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def narration_evidence_method(row: Any) -> str:
    """Return ``reviewed`` or ``measured``; every other method is refused."""

    verification = row.get("verification") if isinstance(row, dict) else None
    method = verification.get("method") if isinstance(verification, dict) else None
    fact(isinstance(verification, dict), "narration evidence verification required")
    if method in (None, REVIEWED_NARRATION_METHOD):
        return "reviewed"
    fact(
        method == MEASURED_NARRATION_METHOD,
        f"boundary evidence method {method!r} is unknown and refused",
    )
    return "measured"


def _ms_rational(value: Any) -> JsonObject:
    fact(type(value) is int and value > 0, "uncertainty milliseconds required")
    return {"numerator": value, "denominator": 1000}


def _reduced(value: Any) -> tuple[int, int]:
    fact(
        isinstance(value, dict)
        and set(value) == {"numerator", "denominator"}
        and type(value["numerator"]) is int
        and type(value["denominator"]) is int
        and value["denominator"] > 0,
        "rational shape",
    )
    ratio = Fraction(value["numerator"], value["denominator"])
    return ratio.numerator, ratio.denominator


def _same_rational(left: Any, right: Any) -> bool:
    return _reduced(left) == _reduced(right)


def shape_set(value: Any, keys: set[str], label: str) -> JsonObject:
    fact(isinstance(value, dict) and set(value) == keys, f"{label} shape")
    return value  # type: ignore[no-any-return]


def verify_measured_narration_evidence(
    row: Any,
    *,
    timing: bytes,
    artifact: bytes,
    audio_sha256: str | None = None,
) -> str:
    """Check measured (#182) evidence against every byte it pins.

    Returns the measurement artifact hash (``sha256:...``).  The evidence must
    be self-consistent: its method, algorithm parameters and parametersHash,
    the measurement artifact bytes, the provider timing bytes, the narration
    audio hash and every token interval must agree.  Anything else refuses.
    """

    fact(narration_evidence_method(row) == "measured", "measured evidence required")
    verification = shape_set(row["verification"], _VERIFICATION_KEYS, "verification")
    algorithm = verification["algorithm"]
    fact(
        isinstance(algorithm, dict)
        and set(algorithm) == {"id", "version", "parametersHash", "parameters"}
        and algorithm["id"] == MEASURE_ALGORITHM_ID
        and algorithm["version"] == MEASURE_ALGORITHM_VERSION
        and isinstance(algorithm["parameters"], dict),
        "measured algorithm identity differs",
    )
    parameters = algorithm["parameters"]
    try:
        derived_parameters_hash = parameters_hash(parameters)
    except MeasurementError as error:
        raise ProofBuildError(
            f"measured algorithm parameters invalid: {error}"
        ) from error
    fact(
        set(parameters) == set(DEFAULT_PARAMETERS)
        and algorithm["parametersHash"] == derived_parameters_hash,
        "measured algorithm parametersHash differs from its parameters",
    )
    fact(
        verification["onsetBasis"] == MEASURE_ONSET_BASIS
        and _same_rational(
            verification["onsetUncertainty"],
            _ms_rational(parameters["onsetUncertaintyMs"]),
        )
        and _same_rational(
            verification["audibleEndUncertainty"],
            _ms_rational(parameters["audibleEndUncertaintyMs"]),
        ),
        "measured uncertainty declarations differ from the algorithm parameters",
    )
    locator = verification["measurementArtifactLocator"]
    fact(
        isinstance(locator, str)
        and bool(locator)
        and "\\" not in locator
        and "\0" not in locator
        and not locator.startswith("/")
        and all(part not in {"", ".", ".."} for part in locator.split("/")),
        "measurement artifact locator must be a clean relative path",
    )
    artifact_hash = verification["measurementArtifactHash"]
    fact(
        isinstance(artifact_hash, str)
        and _SHA256.fullmatch(artifact_hash) is not None
        and sha256_bytes(artifact) == artifact_hash,
        "measurement artifact bytes differ from the pinned hash",
    )
    try:
        parsed = json.loads(artifact)
    except ValueError as error:
        raise ProofBuildError(f"measurement artifact is not JSON: {error}") from error
    fact(
        isinstance(parsed, dict) and canonical_json_bytes(parsed) == artifact,
        "measurement artifact must be canonical JSON",
    )
    fact(
        parsed.get("schemaVersion") == MEASURE_ARTIFACT_VERSION
        and parsed.get("algorithm") == algorithm
        and parsed.get("refusals") == []
        and isinstance(parsed.get("lag"), dict)
        and parsed["lag"].get("verified") is True,
        "measurement artifact is not a verified measurement of this algorithm",
    )
    asset = parsed.get("asset")
    audio = row.get("audio")
    fact(isinstance(asset, dict) and isinstance(audio, dict), "asset binding shape")
    lag = parsed["lag"]
    raw_rate = lag.get("rawSampleRate")
    sample_verified = (
        type(raw_rate) is int
        and raw_rate == 48_000
        and lag.get("method") == "sample_correlation"
        and lag.get("uncertaintySamples") == 0
        and type(lag.get("windowsVerified")) is int
        and lag["windowsVerified"] >= 3
        and lag.get("transformVerification")
        == {
            "method": "reproduced_pcm",
            "normalizerVersion": NORMALIZER_VERSION,
            "toolFingerprint": asset.get("toolFingerprint"),
        }
        and isinstance(asset.get("toolFingerprint"), str)
        and _SHA256.fullmatch(asset["toolFingerprint"]) is not None
    )
    envelope_verified = (
        type(raw_rate) is int
        and raw_rate > 0
        and raw_rate != 48_000
        and (raw_rate == 44_100 or (48_000 % raw_rate == 0 and raw_rate % 1000 == 0))
        and lag.get("method") == "rms_envelope"
        and lag.get("transformVerification") == {"method": "rms_envelope"}
    )
    fact(
        sample_verified or envelope_verified,
        "measurement lag is missing supported transform verification",
    )
    try:
        provider_timing = json.loads(timing)
    except ValueError as error:
        raise ProofBuildError("provider timing is not JSON") from error
    if isinstance(provider_timing, dict):
        marks = provider_timing.get("marks", [])
        fact(isinstance(marks, list), "provider timing marks shape")
        for mark in marks:
            if isinstance(mark, dict) and mark.get("kind") == "word":
                native_rate = mark.get("sample_rate")
                if native_rate is not None:
                    fact(
                        type(native_rate) is int and native_rate == raw_rate,
                        "measurement raw rate differs from native provider timing",
                    )
    timing_hash = sha256_bytes(timing)
    fact(
        row.get("timingHash") == audio.get("timingHash") == timing_hash
        and asset.get("timingHash") == timing_hash,
        "provider timing bytes differ from the evidence and measurement pins",
    )
    audio_hash = row.get("audioHash")
    fact(
        isinstance(audio_hash, str)
        and _SHA256.fullmatch(audio_hash) is not None
        and audio.get("audioHash") == audio_hash
        and asset.get("audioHash") == audio_hash
        and (
            audio_sha256 is None
            or "sha256:" + audio_sha256.removeprefix("sha256:") == audio_hash
        ),
        "narration audio bytes differ from the evidence and measurement pins",
    )
    fact(
        row.get("blockId") == asset.get("blockId")
        and row.get("blockRevision") == asset.get("blockRevision")
        and row.get("textHash") == asset.get("textHash")
        and row.get("narrationAssetId") == asset.get("narrationAssetId")
        and audio.get("narrationAssetId") == asset.get("narrationAssetId")
        and audio.get("cacheAssetId") == asset.get("cacheAssetId")
        and audio.get("durationSamples") == asset.get("durationSamples")
        and audio.get("sampleRate") == asset.get("sampleRate")
        and audio.get("channels") == asset.get("channels"),
        "measurement artifact asset differs from the evidence",
    )
    measured = parsed.get("tokens")
    claimed = row.get("tokens")
    fact(
        isinstance(measured, list)
        and isinstance(claimed, list)
        and len(measured) == len(claimed)
        and bool(claimed),
        "measurement artifact tokens differ from the evidence",
    )
    rate = asset.get("sampleRate")
    for token, mark in zip(claimed, measured, strict=True):
        fact(isinstance(token, dict) and isinstance(mark, dict), "token shape")
        end = mark.get("audibleEndSamples")
        onset = mark.get("onsetSamples")
        fact(
            token.get("tokenId") == mark.get("tokenId")
            and token.get("startOffset") == mark.get("startOffset")
            and token.get("endOffset") == mark.get("endOffset")
            and token.get("quotedText") == mark.get("quotedText")
            and type(onset) is int
            and _same_rational(
                token.get("onset"), {"numerator": onset, "denominator": rate}
            )
            and (("audibleEnd" in token) == (type(end) is int))
            and (
                "audibleEnd" not in token
                or _same_rational(
                    token["audibleEnd"], {"numerator": end, "denominator": rate}
                )
            ),
            "evidence token differs from the measurement artifact",
        )
    return str(artifact_hash)


def narration_review_pin(
    row: Any,
    *,
    timing: bytes | None = None,
    artifact: bytes | None = None,
    audio_sha256: str | None = None,
) -> str:
    """Hash the review/measurement artifact a narration row must be proven by.

    Reviewed rows keep their existing ``reviewArtifactHash`` pin.  Measured rows
    are fully cross-checked and pinned by their measurement artifact hash.  The
    method stays visible on the row itself; measured evidence is never reviewed.
    """

    if narration_evidence_method(row) == "reviewed":
        return reviewed_artifact_hash(row)
    fact(
        timing is not None and artifact is not None,
        "measured evidence requires its timing and measurement artifact bytes",
    )
    assert timing is not None and artifact is not None
    return verify_measured_narration_evidence(
        row, timing=timing, artifact=artifact, audio_sha256=audio_sha256
    )


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
        and all(type(v) is int for v in value["frameRate"].values())
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
        fact(isinstance(row["text"], str), "narration text required")
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
            and profile["frameRate"] == RATE
            and all(type(v) is int for v in profile["frameRate"].values()),
            "profile identity/rate differs",
        )
        extent = integer(profile["extentFrames"], 1)
        fact(extent * FRAME <= 3_000_000, "bounded full programme exceeded")
        sources: JsonObject = {}
        hashes: set[str] = set()
        decoded: set[str] = set()
        source_cells = 0
        fact(
            isinstance(profile["sources"], list) and 1 <= len(profile["sources"]) <= 16,
            "complete source inventory required",
        )
        for source in profile["sources"]:
            shape(source, "id path sha256 channels durationSamples", "source")
            sid = identity(source["id"])
            fact(sid not in sources and source["sha256"] not in hashes, "source alias")
            channels = integer(source["channels"], 1)
            fact(channels in {1, 2}, "unsupported source channels")
            count = integer(source["durationSamples"], 960)
            source_cells += count * channels
            fact(source_cells <= 32_000_000, "bounded aggregate source PCM exceeded")
            name = identity(source["path"])
            pcm = _source_pcm(files, name, channels, count, source["sha256"])
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
            and files.hashes["current-a.json"] == files.hashes["current-b.json"],
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
