"""Pure precommitted PCM prediction and fixed residual comparison for #214.

No filesystem/media tool/native calls. The controller supplies immutable bounded
byte snapshots and a statically selected trusted authenticator. It must persist
commitments/reservations/complete attempt chains before effects (#209). These
functions cannot attest native effect ordering or continuous hidden state.
"""

from __future__ import annotations

import io
import itertools
import math
import platform
import sys
import wave
from array import array
from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Any, cast

from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    COMMITMENT_FIELDS,
    DECODE_FIELDS,
    ITEM_FIELDS,
    LANE,
    MAX_JSON,
    PREFIX,
    RESERVATION_FIELDS,
    TRACK_FIELDS,
    Json,
    OutputConsistencyError,
    OutputTrust,
    _append_ledger,
    _attempt,
    _authenticate,
    _blobs,
    _canonical,
    _context,
    _digest,
    _hash,
    _identity,
    _integer,
    _json_hash,
    _ledger_head,
    _legacy_digest,
    _list,
    _now,
    _ordered,
    _parse,
    _projection,
    _record,
    _refusal,
    _render_retry_used,
    _require,
    _shape,
    _sources,
    _timestamp,
)
from vera_timeline_agent.source_audio_endpoint import endpoint_plan, endpoint_wav

FRAME = 2002
SOFT_FADE_SAMPLES = 72
SOFT_FADE_MODEL = "resolve-studio-21.1.1-linear-72-sample-clip-edges/v1"


def _reviewed_artifact_hash(record: Any) -> str:
    """Review artifact hash of reviewed evidence; measured evidence is refused."""

    verification = record.get("verification") if isinstance(record, dict) else None
    method = verification.get("method") if isinstance(verification, dict) else None
    # Legacy reviewed records carry no method field; only measured/unknown
    # methods and records without a review artifact are refused.
    _require(
        isinstance(verification, dict)
        and method in (None, "reviewed_audio_boundaries/v1")
        and "reviewArtifactHash" in verification,
        f"boundary evidence method {method!r} is not supported by this "
        "reviewed-only output path (measured evidence has no review artifact)",
    )
    return cast(str, verification["reviewArtifactHash"])  # type: ignore[index]


_MEASURED_METHOD = "measured_audio_boundaries/v1"


def _narration_review_pin(record: Any, proof: Any) -> str:
    """Review pin of reviewed evidence, or the measurement artifact hash.

    This host module stays stdlib-only, so it cannot re-run the (#182) measured
    verifier.  That full cross-check (algorithm, timing, audio, tokens) happens
    in the authenticated package/proof builders before a receipt exists; here
    the measured row must only pin exactly the measurement artifact bytes the
    receipt retained.  Unknown methods refuse.
    """

    verification = record.get("verification") if isinstance(record, dict) else None
    method = verification.get("method") if isinstance(verification, dict) else None
    if method == _MEASURED_METHOD:
        assert isinstance(verification, dict)
        _require(
            "measurementArtifactHash" in verification and proof.review is not None,
            "measured evidence requires its measurement artifact",
        )
        _require(
            _legacy_digest(verification["measurementArtifactHash"])
            == _hash(proof.review),
            "measurement artifact bytes differ from the pinned hash",
        )
        return cast(str, verification["measurementArtifactHash"])
    return _reviewed_artifact_hash(record)


RATE = {"numerator": 24000, "denominator": 1001}
ENCODING = "float64le-interleaved-stereo"
ALGORITHM = {
    "version": "qualification-output-fixed-pcm/v2",
    "runtime": "CPython-3.12.14",
    "renderer": {
        "product": "DaVinci Resolve Studio",
        "version": [21, 1, 1, 10, ""],
        "softFades": {
            "model": SOFT_FADE_MODEL,
            "controlState": "not_attested",
            "samplesPerEdge": SOFT_FADE_SAMPLES,
            "shape": "linear",
            "fadeInGain": "sampleOffset/72",
            "fadeOutGain": "samplesToExclusiveActiveEnd/72",
            "activeEnd": "segmentSampleCount; frame-ceiled EOF padding stays zero",
            "shortClips": "refuse when 72-sample edges overlap",
        },
    },
    "frameRate": RATE,
    "sampleRate": 48000,
    "samplesPerFrame": FRAME,
    "sourceEncoding": "signed24-domain-int32le-interleaved",
    "predictionEncoding": ENCODING,
    "order": "sourceId-codepoint/recordStart-itemUid-codepoint/sample-ascending",
    "gain": "10**(manifestGainDb/20)",
    "comparisonGain": 1,
    "lagSamples": 0,
    "pairDiscrimination": "exclude union of committed active clip-edge fade zones; "
    "each complete render remains fully compared",
    "programmeRmsLimit": 0.0004,
    "slidingSamples": 960,
    "slidingRmsLimit": 0.006,
}
ALGORITHM_SHA256 = _json_hash(ALGORITHM)


@dataclass(frozen=True)
class SourceProof:
    """Accepted row/preparation bytes and independent original receipt pins."""

    record: bytes
    receipt: bytes
    timing: bytes | None = None
    review: bytes | None = None
    origin_record: bytes | None = None
    origin_receipt: bytes | None = None


@dataclass(frozen=True)
class PredictionInputs:
    """Authenticated package projection plus a complete native capture.

    input_binding is a closed delivery projection from the verified package,
    never operator-selected route intent. Its hash is authenticated by geometry.
    blobs supplies every context hash's original current bytes, including BOTH
    document/dependency sets. Source paths are deliberately outside this API.
    """

    input_binding: bytes
    geometry: bytes
    geometry_receipt: bytes
    blobs: Mapping[str, bytes]
    source_wavs: Mapping[str, bytes]
    source_proofs: Mapping[str, SourceProof]


@dataclass(frozen=True)
class Prediction:
    """Unsigned commitment payload and PCM. #209 seals/persists before render."""

    payload: bytes
    pcm: bytes


@dataclass(frozen=True)
class CommittedOutput:
    inputs: PredictionInputs
    commitment: bytes
    commitment_receipt: bytes
    prediction: bytes
    reservation: bytes
    reservation_receipt: bytes
    post_geometry: bytes
    post_geometry_receipt: bytes
    decode_record: bytes
    decode_receipt: bytes
    decoded_samples: bytes
    lineage: bytes
    ledger: list[Json]


@dataclass(frozen=True)
class TerminalOutput:
    output: CommittedOutput
    comparison: bytes
    comparison_receipt: bytes
    ledger: list[Json]


def _runtime() -> None:
    _require(
        platform.python_implementation() == "CPython"
        and platform.python_version() == "3.12.14",
        "locked CPython 3.12.14 required",
    )


def _range(value: Any) -> tuple[int, int]:
    row = _shape(value, "startFrame endFrame", "manifest range")
    start, end = _integer(row["startFrame"]), _integer(row["endFrame"], 1)
    _require(end > start, "empty/reversed range")
    return start, end


def _native_range(value: Any) -> tuple[int, int]:
    row = _shape(value, "startFrame durationFrames", "package range")
    return _integer(row["startFrame"]), _integer(row["durationFrames"], 1)


def _delivery_source(event: Json) -> str:
    # Accepted package view creates separate audio/placeholder media per event.
    return _identity(
        event["eventId"]
        if event["kind"] in {"source_audio", "placeholder"}
        else event["provenance"]["sourceId"]
    )


def _pcm(raw: bytes, source: Json) -> tuple[array[int], list[array[float]]]:
    _require(
        type(raw) is bytes and len(raw) <= 128 * 1024 * 1024,
        "bounded source bytes required",
    )
    _require(_hash(raw) == source["pcmFileSha256"], "source file hash differs")
    try:
        with wave.open(io.BytesIO(raw), "rb") as stream:
            width = stream.getsampwidth()
            _require(
                (
                    stream.getframerate(),
                    stream.getnchannels(),
                    width * 8,
                    stream.getnframes(),
                    stream.getcomptype(),
                )
                == (
                    48000,
                    source["channels"],
                    source["originalBitDepth"],
                    source["durationSamples"],
                    "NONE",
                ),
                "source PCM profile/extent differs",
            )
            data = stream.readframes(source["durationSamples"] + 1)
            _require(
                len(data) == source["durationSamples"] * source["channels"] * width,
                "truncated source PCM",
            )
    except (wave.Error, EOFError) as error:
        raise OutputConsistencyError("unsupported source WAV") from error
    values = array(
        "i",
        (
            int.from_bytes(data[i : i + width], "little", signed=True)
            * (256 if width == 2 else 1)
            for i in range(0, len(data), width)
        ),
    )
    _require(values.itemsize == 4, "int32 host encoding required")
    canonical = _little_endian(values)
    _require(
        _hash(canonical) == source["decodedSamplesSha256"],
        "canonical decoded source hash differs",
    )
    channels = [
        array("d", (x / 2**23 for x in values[ch :: source["channels"]]))
        for ch in range(source["channels"])
    ]
    return values, channels


def _little_endian(values: array[Any]) -> bytes:
    if sys.byteorder == "little":
        return values.tobytes()
    copy = values[:]
    copy.byteswap()
    return copy.tobytes()


def _geometry(
    raw: bytes,
    receipt: bytes,
    binding: Json,
    trust: OutputTrust,
    *,
    capture_phase: str,
    require_live: bool,
    render_lineage: Json | None = None,
) -> Json:
    envelope = _record(
        raw,
        "geometry",
        (
            "schemaVersion lane geometry inputBindingSha256 capturePhase capturedAt "
            "expiresAt receiptSha256"
        ),
    )
    semantic = _shape(
        envelope["geometry"],
        "context extentFrames rate tracks items sourceMappings",
        "semantic geometry",
    )
    _require(
        _context(semantic["context"]) == binding["context"], "geometry context differs"
    )
    _require(
        envelope["inputBindingSha256"] == _json_hash(binding),
        "geometry input binding differs",
    )
    captured, expiry, now = (
        _timestamp(envelope["capturedAt"]),
        _timestamp(envelope["expiresAt"]),
        _now(trust),
    )
    _require(
        envelope["capturePhase"] == capture_phase
        and captured <= now
        and captured <= expiry
        and (not require_live or now <= expiry),
        "geometry phase/clock/expiry refused",
    )
    additional: Json = {"inputBinding": binding}
    if capture_phase == "post_render":
        _require(render_lineage is not None, "post-render completion lineage required")
        additional["renderLineage"] = render_lineage
    _authenticate(
        trust,
        "output_geometry_snapshot",
        envelope,
        "receiptSha256",
        receipt,
        **additional,
    )
    extent = _integer(semantic["extentFrames"], 1, 1498)
    _require(extent * FRAME <= 3_000_000, "programme sample bound exceeded")
    rate = _shape(semantic["rate"], "numerator denominator", "rate")
    _require(
        all(type(v) is int for v in rate.values()) and rate == RATE,
        "unsupported frame rate",
    )
    _require(
        semantic["tracks"] == binding["tracks"], "complete track inventory differs"
    )
    tracks: dict[str, Json] = {}
    indices: set[tuple[str, int]] = set()
    for track in _list(semantic["tracks"], 64):
        _shape(track, TRACK_FIELDS, "track")
        tid = _identity(track["trackId"])
        index = _integer(track["index"], 1, 32)
        _identity(track["name"])
        _require(
            track["kind"] in {"video", "audio"}
            and track["enabled"] is True
            and type(track["locked"]) is bool,
            "unsupported track state",
        )
        _require((track["kind"], index) not in indices, "duplicate track index")
        indices.add((track["kind"], index))
        tracks[tid] = track
    _ordered(semantic["tracks"], "trackId")
    for kind in ("video", "audio"):
        values = sorted(index for k, index in indices if k == kind)
        _require(values == list(range(1, len(values) + 1)), "partial track inventory")
    mappings = _list(binding["itemMappings"], 2048)
    for mapping in mappings:
        _shape(mapping, "itemUid eventId sourceId mediaUid", "native item mapping")
        for value in mapping.values():
            _identity(value)
    _ordered(mappings, "itemUid")
    expected = {row["itemUid"]: row for row in mappings}
    native = {
        row["sourceId"]: row["nativeSourceSha256"] for row in binding["nativeSources"]
    }
    source_entries = {source["sourceId"]: source for source in binding["sourceEntries"]}
    wanted_sources = [
        {
            "sourceId": s["sourceId"],
            "nativeSourceSha256": s["nativeSourceSha256"],
            "sourceEntrySha256": _json_hash(s),
        }
        for s in binding["sourceEntries"]
    ]
    _require(
        semantic["sourceMappings"] == wanted_sources, "source mapping inventory differs"
    )
    items = _list(semantic["items"], 2048)
    uids: set[str] = set()
    for item in items:
        _shape(item, ITEM_FIELDS, "item")
        uid = _identity(item["itemUid"])
        _require(uid not in uids and uid in expected, "unknown/duplicate item")
        uids.add(uid)
        _require(
            all(item[key] == expected[uid][key] for key in expected[uid]),
            "native item mapping differs",
        )
        _require(
            item["trackId"] in tracks and item["sourceId"] in native,
            "unknown item track/source",
        )
        kind = tracks[item["trackId"]]["kind"]
        _require(
            item["kind"] == kind and item["online"] is True and item["enabled"] is True,
            "offline/disabled item",
        )
        speed = _shape(item["speed"], "numerator denominator", "speed")
        _require(
            speed == {"numerator": 1, "denominator": 1}
            and all(type(v) is int for v in speed.values()),
            "unit speed required",
        )
        start = _integer(item["recordStart"])
        duration = _integer(item["recordDuration"], 1, extent)
        _integer(item["sourceStart"])
        _require(
            _integer(item["sourceDuration"], 1) == duration
            and start + duration <= extent,
            "item range/extent differs",
        )
        links = _list(item["linkedItemUids"], 2048)
        _require(
            all(type(x) is str for x in links)
            and links == sorted(set(links))
            and uid not in links,
            "duplicate/self/unordered links",
        )
        for link in links:
            _identity(link)
        if kind == "audio":
            _require(
                item["sourceId"] in source_entries
                and item["sourceMappingSha256"]
                == source_entries[item["sourceId"]]["pcmMappingSha256"],
                "audio mapping differs",
            )
        else:
            _require(
                item["sourceMappingSha256"] == native[item["sourceId"]],
                "video source mapping differs",
            )
    _require(uids == expected.keys(), "incomplete native item inventory")
    _require(
        items == sorted(items, key=lambda row: (row["recordStart"], row["itemUid"])),
        "noncanonical item order",
    )
    by_uid = {item["itemUid"]: item for item in items}
    for item in items:
        _require(
            all(
                uid in by_uid and item["itemUid"] in by_uid[uid]["linkedItemUids"]
                for uid in item["linkedItemUids"]
            ),
            "incomplete/asymmetric links",
        )
    return envelope


def _source_endpoint(event: Json, audio: Json) -> tuple[int, int, int] | None:
    try:
        return endpoint_plan(event, audio, Fraction(24000, 1001))
    except ValueError as error:
        raise OutputConsistencyError(
            f"off-grid/unit-speed source mapping: {error}"
        ) from error


def _provenance(
    source: Json,
    event: Json,
    manifest_source: Json,
    delivery: Json,
    proof: SourceProof,
    context: Json,
    trust: OutputTrust,
    dependencies: Json,
) -> tuple[int, int]:
    _require(
        proof.origin_record is None and proof.origin_receipt is None,
        "external origin unsupported; exact package-derived origin required",
    )
    for raw in (proof.record, proof.receipt):
        _require(
            type(raw) is bytes and 0 < len(raw) <= MAX_JSON,
            "bounded provenance required",
        )
    record = _parse(proof.record)
    _require(
        source["provenanceReceiptSha256"] == _hash(proof.receipt),
        "provenance receipt differs",
    )
    rs, re = _range(event["recordRange"])
    _require(
        delivery["recordRange"] == {"startFrame": rs, "durationFrames": re - rs},
        "package record derivation differs",
    )
    _require(
        source["deliveryDerivationSha256"] == _json_hash(delivery),
        "delivery derivation differs",
    )
    provenance = event["provenance"]
    rate, q = 48000, 0
    origin_frame = origin_sample = 0
    if event["kind"] == "narration":
        rows = _list(dependencies["narrationTimingMaps"], 2048)
        boundaries = _list(dependencies.get("narrationBoundaryEvidence", []), 2048)
        block_id = _identity(provenance["blockId"])
        matches = [
            (row, boundary)
            for records, boundary in ((rows, False), (boundaries, True))
            for row in records
            if _identity(row["blockId"]) == block_id
        ]
        _require(
            len(matches) == 1 and _canonical(record) == _canonical(matches[0][0]),
            "narration row differs from authenticated dependencies",
        )
        boundary = matches[0][1]
        _require(
            source["pcmMode"] == "wav-direct" and source["originalBitDepth"] == 24,
            "narration requires original PCM24 WAV",
        )
        _require(
            provenance["sourceId"] == source["sourceId"]
            and _legacy_digest(provenance["deliveredSourceHash"])
            == source["nativeSourceSha256"],
            "narration native source differs",
        )
        _require(
            proof.timing is not None and proof.review is not None,
            "narration raw pins required",
        )
        assert proof.timing is not None and proof.review is not None
        _require(
            len(proof.timing) <= MAX_JSON and len(proof.review) <= MAX_JSON,
            "narration pin bound",
        )
        pins = {
            "timing": _hash(proof.timing),
            "review": _hash(proof.review),
            "receipt": _hash(proof.receipt),
        }
        _require(
            source["provenancePinsSha256"] == _json_hash(pins), "narration pins differ"
        )
        audio = record["audio"]
        _require(
            record["blockId"] == provenance["blockId"]
            and record["narrationAssetId"] == source["sourceId"]
            and _legacy_digest(record["audioHash"])
            == source["pcmFileSha256"]
            == source["nativeSourceSha256"]
            and _legacy_digest(record["timingHash"])
            == pins["timing"]
            == _legacy_digest(provenance["timingMapHash"])
            and manifest_source["narrationAudio"] == audio
            and audio["narrationAssetId"] == source["sourceId"]
            and _legacy_digest(audio["audioHash"]) == source["pcmFileSha256"]
            and _integer(audio["sampleRate"]) == 48000
            and _integer(audio["channels"], 1, 2) == source["channels"]
            and _integer(audio["durationSamples"], 960) == source["durationSamples"],
            "narration receipt/manifest row differs",
        )
        _require(
            ("boundaryEvidenceHash" in provenance) == boundary,
            "boundary evidence presence differs",
        )
        if boundary:
            # The authenticated TS compiler hash is not a Python row hash.
            _legacy_digest(provenance["boundaryEvidenceHash"])
            _require(
                _legacy_digest(_narration_review_pin(record, proof)) == pins["review"],
                "boundary review differs",
            )
        trust.authenticate(
            "narration_preparation",
            proof.receipt,
            _parse(
                _canonical(
                    {
                        "row": record,
                        "timingHash": "sha256:" + pins["timing"],
                        "reviewHash": "sha256:" + pins["review"],
                        "audioHash": record["audioHash"],
                    }
                )
            ),
        )
        _require(
            delivery["sourceRange"] == {"startFrame": 0, "durationFrames": re - rs},
            "authenticated WAV-first-sample package rule missing",
        )
        _require(
            proof.origin_record is None and proof.origin_receipt is None,
            "narration origin cannot be overridden",
        )
        # D-0014 ceiling framing: the event may extend past the asset by less
        # than one frame; that tail is explicit silence, never padded audio.
        full = (re - rs) * FRAME
        _require(
            source["durationSamples"] > 0 and full - source["durationSamples"] < FRAME,
            "narration event exceeds exact source samples by a frame or more",
        )
        start, end = 0, min(full, source["durationSamples"])
    else:
        _require(
            event["kind"] == "source_audio" and source["pcmMode"] == "prepared-audio",
            "unsupported source provenance kind",
        )
        _require(
            proof.timing is None
            and proof.review is None
            and proof.record == proof.receipt,
            "prepared source uses exact authenticated preparation receipt",
        )
        _require(
            record.get("recordVersion") == "authoring-media-preparation/v1",
            "accepted preparation required",
        )
        binding, audio = record["binding"], record["audio"]
        requirement = _identity(manifest_source["preparationRequirementKey"])
        prepared = _list(dependencies["preparedMedia"], 64)
        matches_prepared = [
            row for row in prepared if _identity(row["requirementKey"]) == requirement
        ]
        _require(
            _identity(record["requirementKey"]) == requirement
            and len(matches_prepared) == 1
            and _canonical(binding) == _canonical(matches_prepared[0])
            and binding["timeMapping"] == event["sourceTimeMapping"],
            "preparation binding differs from authenticated dependencies",
        )
        _require(
            source["provenancePinsSha256"] == _json_hash(binding),
            "preparation binding pins differ",
        )
        _require(
            _legacy_digest(binding["verification"]["deliveredHash"])
            == _legacy_digest(provenance["deliveredSourceHash"])
            and source["sourceId"] == event["eventId"]
            and _legacy_digest(audio["contentHash"]) == source["pcmFileSha256"]
            and _legacy_digest(audio["sourceAudioHash"])
            == _legacy_digest(event["audio"]["audioHash"])
            and _integer(audio["decodedSamples"], 960) == source["durationSamples"]
            and _integer(audio["channels"], 1, 2) == source["channels"]
            and source["originalBitDepth"] == 24,
            "prepared source/hash domain differs",
        )
        trust.authenticate(
            "private_preparation",
            proof.receipt,
            _parse(
                _canonical(
                    {
                        "context": context,
                        "preparationBindingHash": event["preparationBindingHash"],
                        "recordSha256": _hash(proof.record),
                        "binding": binding,
                    }
                )
            ),
        )
        streams = _list(
            event["sourceTimeMapping"]["sourceFrameMap"]["sourceAudioStreamMappings"],
            1,
            1,
        )
        stream = streams[0]
        rate = _integer(stream["sampleRate"], 1, 768000)
        _require(
            _integer(stream["streamIndex"]) == _integer(event["audio"]["streamIndex"]),
            "selected stream differs",
        )
        q = _integer(audio["resampledFirstSample"])
        selected = _shape(
            event["audio"]["sampleRange"], "startFrame endFrame", "source samples"
        )
        a, b = _integer(selected["startFrame"]), _integer(selected["endFrame"], 1)
        start_fraction, end_fraction = (
            Fraction(a * 48000, rate) - q,
            Fraction(b * 48000, rate) - q,
        )
        _require(
            start_fraction.denominator == end_fraction.denominator == 1,
            "fractional PCM mapping",
        )
        start, end = int(start_fraction), int(end_fraction)
        plan = _source_endpoint(event, audio)
        _require(
            plan is not None
            or (start % FRAME == end % FRAME == 0 and end - start == (re - rs) * FRAME),
            "off-grid/unit-speed source mapping",
        )
        _require(
            plan is not None or source["nativeSourceSha256"] == source["pcmFileSha256"],
            "prepared native WAV differs",
        )
        native_start = (
            Fraction(0)
            if plan is not None
            else Fraction(start - origin_sample, FRAME) + origin_frame
        )
        _require(
            native_start.denominator == 1 and native_start >= 0,
            "unsupported native origin conversion",
        )
        _require(
            delivery["sourceRange"]
            == {"startFrame": int(native_start), "durationFrames": re - rs},
            "prepared package source derivation differs",
        )
    _require(
        0 <= start < end <= source["durationSamples"],
        "event exceeds exact source samples; no padding",
    )
    _require(
        (source["nativeFrameOrigin"], source["pcmSampleOrigin"])
        == (origin_frame, origin_sample),
        "source origins lack authenticated derivation",
    )
    mapping = {
        "sourceId": source["sourceId"],
        "nativeFrameOrigin": origin_frame,
        "pcmSampleOrigin": origin_sample,
        "sourceSampleRate": rate,
        "sampleRate": 48000,
        "resampledFirstSample": q,
        "startSample": start,
        "endSample": end,
        "provenanceRecordSha256": _hash(proof.record),
    }
    _require(
        source["pcmMappingSha256"] == _json_hash(mapping),
        "exact PCM mapping digest differs",
    )
    return start, end


def _shortened_edit(geometry: Json) -> bool:
    """An edited capture may end early only where its items end (no tail)."""
    items = _list(geometry["items"], 2048)
    return (
        geometry["context"].get("phase") == "edited"
        and bool(items)
        and max(item["recordStart"] + item["recordDuration"] for item in items)
        == geometry["extentFrames"]
    )


def _package_view(
    binding: Json,
    manifest: Json,
    dependencies: Json,
    raw: bytes,
    extent: int,
    *,
    shortened_edit: bool = False,
) -> None:
    view = _shape(
        _parse(raw),
        "schemaVersion timeline tracks sources events markers composition",
        "verified package delivery view",
    )
    _require(
        view["schemaVersion"] == "resolve-native-view/v2"
        and _canonical(view["timeline"]) == _canonical(manifest["timeline"])
        and _canonical(view["tracks"]) == _canonical(manifest["tracks"])
        and _canonical(view["composition"]) == _canonical(manifest["composition"]),
        "verified package/manifest projection differs",
    )
    duration = _integer(view["timeline"]["durationFrames"], 1, 1498)
    # Shorter only for an edited capture whose native authentication derived
    # the extent from one linked AV ripple trim; never longer than the package.
    _require(
        (extent == duration or (shortened_edit and 0 < extent < duration))
        and view["timeline"]["frameRate"] == RATE
        and all(type(x) is int for x in view["timeline"]["frameRate"].values()),
        "package extent/rate differs",
    )
    manifest_tracks = _list(manifest["tracks"], 64)
    _require(
        _canonical(manifest_tracks) == _canonical(dependencies["tracks"]),
        "manifest/dependency tracks differ",
    )
    track_map = {_identity(track["id"]): track for track in manifest_tracks}
    _require(
        len(track_map) == len(manifest_tracks)
        and {track["trackId"] for track in binding["tracks"]} == track_map.keys(),
        "complete manifest track inventory differs",
    )
    for track in binding["tracks"]:
        expected = track_map[track["trackId"]]
        _require(
            track["kind"] == expected["kind"]
            and track["name"] == expected["name"]
            and track["index"] == _integer(expected["index"], 1, 32),
            "track identity/index differs from manifest",
        )
    package_sources = _list(view["sources"], 64)
    source_map: dict[str, Json] = {}
    for source in package_sources:
        _shape(source, "id kind path contentHash", "package source")
        sid = _identity(source["id"])
        _require(
            sid not in source_map and source["kind"] in {"audio", "video", "still"},
            "duplicate/unsupported package source",
        )
        path = _identity(source["path"])
        _require(
            not PurePosixPath(path).is_absolute()
            and "\\" not in path
            and ":" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            "unsafe package source path",
        )
        _legacy_digest(source["contentHash"])
        source_map[sid] = source
    expected_sources = [
        {
            "sourceId": sid,
            "nativeSourceSha256": _legacy_digest(source_map[sid]["contentHash"]),
        }
        for sid in sorted(source_map)
    ]
    _require(
        binding["nativeSources"] == expected_sources,
        "native hashes differ from authenticated package files",
    )
    manifest_events = _list(manifest["events"], 2048)
    expected_events = {
        event["eventId"]: event
        for event in manifest_events
        if event["kind"] != "script_marker"
    }
    rows = _list(view["events"], 2048)
    seen: set[str] = set()
    delivery: list[Json] = []
    for row in rows:
        _shape(
            row,
            "id kind sourceId trackId trackKind recordRange sourceRange "
            "v2Event gainDb pictureTreatment",
            "package event",
        )
        eid = _identity(row["id"])
        _require(
            eid in expected_events and eid not in seen,
            "unknown/duplicate package event",
        )
        seen.add(eid)
        event = expected_events[eid]
        _require(
            _canonical(row["v2Event"]) == _canonical(event)
            and row["sourceId"] == _delivery_source(event)
            and row["kind"] == event["kind"]
            and row["trackId"] == event["trackId"]
            and row["trackKind"] == track_map[event["trackId"]]["kind"]
            and row["gainDb"]
            == (
                event["audio"]["gainDb"]
                if isinstance(event.get("audio"), dict)
                else None
            )
            and row["pictureTreatment"] == event.get("pictureTreatment"),
            "package event/manifest intent differs",
        )
        start, end = _range(event["recordRange"])
        _require(
            row["recordRange"] == {"startFrame": start, "durationFrames": end - start},
            "package record derivation differs",
        )
        if event["kind"] in {"narration", "placeholder"}:
            expected_range = {"startFrame": 0, "durationFrames": end - start}
        elif event["kind"] in {"primary_visual", "overlay_visual"}:
            a, b = _range(event["sourceRange"])
            expected_range = {
                "startFrame": a,
                "durationFrames": end - start
                if isinstance(event.get("pictureTreatment"), dict)
                and event["pictureTreatment"].get("kind") == "still_frame"
                else b - a,
            }
            _require(
                _legacy_digest(event["provenance"]["deliveredSourceHash"])
                == _legacy_digest(source_map[row["sourceId"]]["contentHash"]),
                "visual native source differs from manifest",
            )
        else:
            _require(event["kind"] == "source_audio", "unsupported manifest event")
            expected_range = row["sourceRange"]
        _native_range(row["sourceRange"])
        _require(
            row["sourceRange"] == expected_range, "package source derivation differs"
        )
        delivery.append(
            {
                "eventId": eid,
                "kind": row["kind"],
                "recordRange": row["recordRange"],
                "sourceRange": row["sourceRange"],
            }
        )
    _require(
        seen == expected_events.keys()
        and binding["delivery"] == sorted(delivery, key=lambda row: row["eventId"]),
        "complete package delivery inventory differs",
    )


def _host_identity(blobs: Mapping[str, bytes], manifest: Json) -> None:
    runtime = _record(
        blobs["runtimeSha256"],
        "runtime",
        "schemaVersion lane implementation pythonVersion nodeVersion "
        "npmVersion uvVersion system release machine",
    )
    _require(
        (
            runtime["implementation"],
            runtime["pythonVersion"],
            runtime["nodeVersion"],
            runtime["npmVersion"],
            runtime["uvVersion"],
        )
        == ("CPython", "3.12.14", "24.19.0", "11.17.0", "0.12.5"),
        "qualified locked host runtime required",
    )
    for key in ("system", "release", "machine"):
        _identity(runtime[key])
    release = _record(
        blobs["installedReleaseSha256"], "release", "schemaVersion lane files"
    )
    files = release["files"]
    _require(
        type(files) is dict and 1 <= len(files) <= 2048,
        "bounded installed inventory required",
    )
    for name, digest in files.items():
        _identity(name)
        _require(
            not PurePosixPath(name).is_absolute()
            and "\\" not in name
            and ":" not in name
            and all(part not in {"", ".", ".."} for part in name.split("/")),
            "unsafe installed inventory path",
        )
        _digest(digest)
    profile = _record(
        blobs["profileSha256"],
        "profile",
        "schemaVersion lane container videoCodec audioCodec audioBitDepth "
        "sampleRate channels rate width height",
    )
    _require(
        (profile["container"], profile["videoCodec"], profile["audioCodec"])
        == ("mov", "prores422", "lpcm")
        and _integer(profile["audioBitDepth"]) == 24
        and _integer(profile["sampleRate"]) == 48000
        and _integer(profile["channels"]) == 2
        and profile["rate"] == RATE
        and all(type(value) is int for value in profile["rate"].values()),
        "fixed delivered MOV profile required",
    )
    for key in ("width", "height"):
        _require(
            _integer(profile[key], 1, 16384)
            == _integer(manifest["timeline"][key], 1, 16384),
            "profile picture dimensions differ from manifest",
        )


@_refusal
def _validated(
    inputs: PredictionInputs, trust: OutputTrust, *, require_live: bool
) -> tuple[Json, Json, list[Json], dict[str, list[array[float]]]]:
    # Snapshot immutable byte values before the trusted port is called. A
    # caller's mutable maps must not replace blobs after their hashes pass.
    inputs = replace(
        inputs,
        blobs=dict(inputs.blobs),
        source_wavs=dict(inputs.source_wavs),
        source_proofs=dict(inputs.source_proofs),
    )
    _runtime()
    binding = _record(
        inputs.input_binding,
        "inputs",
        (
            "schemaVersion lane context delivery sourceEntries tracks "
            "itemMappings nativeSources"
        ),
    )
    context = binding["context"]
    _blobs(inputs.blobs, context)
    entries = _sources(binding["sourceEntries"])
    source_ids = {source["sourceId"] for source in entries}
    _require(
        inputs.source_wavs.keys() == inputs.source_proofs.keys() == source_ids,
        "complete source/provenance inventory required",
    )
    _require(
        all(
            proof.origin_record is None and proof.origin_receipt is None
            for proof in inputs.source_proofs.values()
        ),
        "external origin unsupported; exact package-derived origin required",
    )
    native_sources = _list(binding["nativeSources"], 64)
    for source in native_sources:
        _shape(source, "sourceId nativeSourceSha256", "native source")
        _identity(source["sourceId"])
        _digest(source["nativeSourceSha256"])
    _ordered(native_sources, "sourceId")
    native = {
        source["sourceId"]: source["nativeSourceSha256"] for source in native_sources
    }
    _require(
        all(
            native.get(source["sourceId"]) == source["nativeSourceSha256"]
            for source in entries
        ),
        "native/PCM source binding differs",
    )
    snapshot = _geometry(
        inputs.geometry,
        inputs.geometry_receipt,
        binding,
        trust,
        capture_phase="pre_render",
        require_live=require_live,
    )
    geometry = snapshot["geometry"]
    manifest = _parse(inputs.blobs["manifestSha256"])
    _require(
        manifest.get("schemaVersion") == "timeline-manifest/v2",
        "verified v2 manifest required",
    )
    dependencies = _parse(inputs.blobs["executionDependenciesSha256"])
    _require(
        dependencies.get("schemaVersion") == "compiler-dependencies/v2",
        "authenticated v2 execution dependencies required",
    )
    _package_view(
        binding,
        manifest,
        dependencies,
        inputs.blobs["packageSha256"],
        geometry["extentFrames"],
        shortened_edit=_shortened_edit(geometry),
    )
    _host_identity(inputs.blobs, manifest)
    # The trusted capture authenticator verifies full accepted manifest/package
    # schemas. This module derives intent from their raw pinned manifest bytes.
    manifest_sources = _list(manifest["sources"], 64)
    source_map = {source["id"]: source for source in manifest_sources}
    _require(
        len(source_map) == len(manifest_sources),
        "duplicate manifest source inventory",
    )
    events = _list(manifest["events"], 2048)
    event_map = {
        event["eventId"]: event for event in events if event["kind"] != "script_marker"
    }
    _require(
        len({event["eventId"] for event in events}) == len(events),
        "duplicate manifest event",
    )
    _require(
        {_delivery_source(event) for event in event_map.values()} == native.keys(),
        "complete package source inventory differs",
    )
    deliveries = _list(binding["delivery"], 2048)
    for delivery in deliveries:
        _shape(
            delivery,
            "eventId kind recordRange sourceRange",
            "package delivery derivation",
        )
        _identity(delivery["eventId"])
        _native_range(delivery["recordRange"])
        _native_range(delivery["sourceRange"])
    _ordered(deliveries, "eventId")
    delivery_map = {entry["eventId"]: entry for entry in deliveries}
    _require(
        delivery_map.keys() == event_map.keys(),
        "complete package event inventory differs",
    )
    for item in geometry["items"]:
        _require(item["eventId"] in event_map, "native item has no manifest event")
        event = event_map[item["eventId"]]
        expected_kind = (
            "audio" if event["kind"] in {"source_audio", "narration"} else "video"
        )
        _require(
            item["sourceId"] == _delivery_source(event)
            and item["trackId"] == event["trackId"]
            and item["kind"] == expected_kind,
            "unknown/No-policy native audio",
        )
        delivery = delivery_map[item["eventId"]]
        _require(delivery["kind"] == event["kind"], "delivery event kind differs")
        source_start, source_duration = _native_range(delivery["sourceRange"])
        held_picture = event["kind"] == "placeholder" or (
            event["kind"] in {"primary_visual", "overlay_visual"}
            and isinstance(event.get("pictureTreatment"), dict)
            and event["pictureTreatment"].get("kind") == "still_frame"
        )
        # A held picture has no advancing source clock. Its authenticated
        # single frame can remain on screen past the authored hold duration;
        # the observed native route and semantic bridge bound the actual edit.
        edited_hold = (
            context["phase"] == "edited"
            and held_picture
            and item["kind"] == "video"
            and item["sourceStart"] == source_start
            and item["sourceDuration"] == item["recordDuration"]
            and item["sourceDuration"] <= geometry["extentFrames"]
        )
        _require(
            edited_hold
            or (
                source_start
                <= item["sourceStart"]
                < item["sourceStart"] + item["sourceDuration"]
                <= source_start + source_duration
            ),
            "native segment outside authenticated event",
        )
    for event_id, delivery in delivery_map.items():
        items = [item for item in geometry["items"] if item["eventId"] == event_id]
        if context["phase"] != "edited":
            rs, duration = _native_range(delivery["recordRange"])
            ss, sd = _native_range(delivery["sourceRange"])
            # Exact original/rebuilt union; edited permits bounded trims/splits.
            cursor, source_cursor = rs, ss
            for item in items:
                _require(
                    item["recordStart"] == cursor
                    and item["sourceStart"] == source_cursor,
                    "pristine/rebuild event coverage differs",
                )
                cursor += item["recordDuration"]
                source_cursor += item["sourceDuration"]
            _require(
                cursor == rs + duration and source_cursor == ss + sd,
                "pristine/rebuild event coverage differs",
            )
    pcm: dict[str, list[array[float]]] = {}
    channel_owners: dict[str, str] = {}
    audio_events = [
        event for event in events if event["kind"] in {"narration", "source_audio"}
    ]
    _require(
        {_delivery_source(event) for event in audio_events} == source_ids
        and len(audio_events) == len(entries),
        "unique complete audible source inventory required",
    )
    intent: list[Json] = []
    for source in entries:
        sid = source["sourceId"]
        event = next(event for event in audio_events if _delivery_source(event) == sid)
        delivery = delivery_map[event["eventId"]]
        start, end = _provenance(
            source,
            event,
            source_map[event["provenance"]["sourceId"]],
            delivery,
            inputs.source_proofs[sid],
            context,
            trust,
            dependencies,
        )
        values, pcm[sid] = _pcm(inputs.source_wavs[sid], source)
        for ch in range(source["channels"]):
            digest = _hash(_little_endian(values[ch :: source["channels"]]))
            _require(
                digest not in channel_owners or channel_owners[digest] == sid,
                "decoded-channel source alias",
            )
            channel_owners[digest] = sid
        if event["kind"] == "source_audio":
            audio_record = _parse(inputs.source_proofs[sid].record)["audio"]
            plan = _source_endpoint(event, audio_record)
            if plan is not None:
                try:
                    native_wav = endpoint_wav(
                        inputs.source_wavs[sid], plan, audio_record
                    )
                except ValueError as error:
                    raise OutputConsistencyError(
                        f"endpoint native WAV refused: {error}"
                    ) from error
                _require(
                    _hash(native_wav) == source["nativeSourceSha256"],
                    "endpoint native WAV derivation differs",
                )
                first, exclusive, envelope = plan
                pcm[sid] = [
                    channel[first:exclusive]
                    + array("d", [0.0]) * (envelope - (exclusive - first))
                    for channel in pcm[sid]
                ]
                start, end = 0, envelope
        gain: int | float = 0
        if event["kind"] == "source_audio":
            gain = event["audio"]["gainDb"]
            _require(
                type(gain) in {int, float}
                and math.isfinite(gain)
                and (event["audio"]["audioPolicy"], gain)
                in {("full", 0), ("full", -0.1), ("quiet", -18)},
                "unapproved manifest gain/No policy",
            )
        segments: list[Json] = []
        source_intervals: list[tuple[int, int]] = []
        for item in geometry["items"]:
            if item["sourceId"] != sid or item["kind"] != "audio":
                continue
            local = (
                item["sourceStart"] - source["nativeFrameOrigin"]
            ) * FRAME + source["pcmSampleOrigin"]
            count = item["recordDuration"] * FRAME
            if event["kind"] == "narration":
                # Only the asset's own samples are mapped; the sub-frame tail of
                # a ceiling-framed event stays silent in the prediction.
                count = min(count, end - local)
            _require(
                start <= local < local + count <= end <= len(pcm[sid][0]),
                "mapped segment outside exact event/source",
            )
            source_intervals.append((local, local + count))
            segments.append(
                {
                    "itemUid": item["itemUid"],
                    "recordStart": item["recordStart"],
                    "sampleStart": local,
                    "sampleCount": count,
                    "edgeFadeModel": SOFT_FADE_MODEL,
                }
            )
        ordered = sorted(source_intervals)
        _require(
            all(a[1] <= b[0] for a, b in itertools.pairwise(ordered)),
            "overlapping/aliased source ranges",
        )
        intent.append(
            {
                "sourceId": sid,
                "eventId": event["eventId"],
                "gainDb": gain,
                "channelMap": "mono-dual"
                if source["channels"] == 1
                else "stereo-direct",
                "segments": segments,
            }
        )
    return binding, snapshot, intent, pcm


@_refusal
def validate_prediction_intent(inputs: PredictionInputs, *, trust: OutputTrust) -> Json:
    """Independently authenticate input bytes and derive the only permitted intent."""
    binding, snapshot, intent, _ = _validated(inputs, trust, require_live=True)
    return _parse(
        _canonical(
            {
                "context": binding["context"],
                "geometrySha256": _json_hash(snapshot["geometry"]),
                "sources": intent,
            }
        )
    )


def _mix(intent: list[Json], pcm: dict[str, list[array[float]]], extent: int) -> bytes:
    mix = [array("d", [0.0]) * (extent * FRAME) for _ in range(2)]
    for source in intent:
        gain = 10 ** (source["gainDb"] / 20)
        channels = pcm[source["sourceId"]]
        for segment in source["segments"]:
            record, start = segment["recordStart"] * FRAME, segment["sampleStart"]
            count = segment["sampleCount"]
            _require(
                count >= 2 * SOFT_FADE_SAMPLES,
                "native soft-fade model does not cover overlapping clip-edge ramps",
            )
            for offset in range(count):
                fade = min(
                    1.0,
                    offset / SOFT_FADE_SAMPLES,
                    (count - offset) / SOFT_FADE_SAMPLES,
                )
                for ch in range(2):
                    samples = channels[0 if len(channels) == 1 else ch]
                    mix[ch][record + offset] += samples[start + offset] * gain * fade
    _require(
        all(math.isfinite(x) and abs(x) < 1.0 for channel in mix for x in channel),
        "predicted clipping/nonfinite samples",
    )
    interleaved = array(
        "d", (sample for pair in zip(*mix, strict=True) for sample in pair)
    )
    _require(interleaved.itemsize == 8, "float64 host encoding required")
    raw = _little_endian(interleaved)
    _require(len(raw) <= 48_000_000, "predicted byte bound exceeded")
    return raw


def _candidate(
    inputs: PredictionInputs, trust: OutputTrust, created_at: str, *, require_live: bool
) -> Prediction:
    binding, snapshot, intent, pcm = _validated(
        inputs, trust, require_live=require_live
    )
    geometry = snapshot["geometry"]
    predicted = _mix(intent, pcm, geometry["extentFrames"])
    _nonvacuity(predicted, geometry["extentFrames"] * FRAME)
    payload = {
        "schemaVersion": f"{PREFIX}commitment/v1",
        "lane": LANE,
        "context": binding["context"],
        "geometrySha256": _json_hash(geometry),
        "geometryCaptureRawSha256": _hash(inputs.geometry),
        "geometryReceiptSha256": _hash(inputs.geometry_receipt),
        "derivedIntentSha256": _json_hash(intent),
        "sourceEntries": binding["sourceEntries"],
        "algorithmSha256": ALGORITHM_SHA256,
        "predictionEncoding": ENCODING,
        "predictionBytesSha256": _hash(predicted),
        "predictionByteLength": len(predicted),
        "extentFrames": geometry["extentFrames"],
        "sampleRate": 48000,
        "channels": 2,
        "createdAt": created_at,
        "expiresAt": snapshot["expiresAt"],
    }
    return Prediction(_canonical(payload), predicted)


@_refusal
def create_prediction(
    inputs: PredictionInputs, *, trust: OutputTrust, ledger: list[Json]
) -> Prediction:
    """Create deterministic unsigned payload; refuses an already attempted binding."""
    context = _record(
        inputs.input_binding,
        "inputs",
        (
            "schemaVersion lane context delivery sourceEntries tracks "
            "itemMappings nativeSources"
        ),
    )["context"]
    prior = _attempt(ledger, context)
    _require(
        prior is None
        or prior["state"] == "expired_unused"
        or prior["state"] == "render_failed",
        "binding already committed/reserved/terminal",
    )
    candidate = _candidate(
        inputs, trust, _now(trust).isoformat().replace("+00:00", "Z"), require_live=True
    )
    if prior is not None:
        if prior["state"] == "render_failed":
            _require(
                not _render_retry_used(ledger, context) and prior["context"] == context,
                "binding already attempted or render retry unavailable",
            )
        _require(
            _hash(candidate.pcm) == prior["predictionBytesSha256"],
            "retry prediction changed",
        )
    return candidate


@_refusal
def verify_prediction_commitment(
    inputs: PredictionInputs,
    commitment: bytes,
    receipt: bytes,
    prediction: bytes,
    *,
    trust: OutputTrust,
) -> Json:
    """Authenticate and recompute prediction bytes without observing output."""
    return _verified_commitment(
        inputs, commitment, receipt, prediction, trust=trust, require_live=True
    )


def _verified_commitment(
    inputs: PredictionInputs,
    commitment: bytes,
    receipt: bytes,
    prediction: bytes,
    *,
    trust: OutputTrust,
    require_live: bool,
) -> Json:
    record = _record(commitment, "commitment", COMMITMENT_FIELDS)
    _sources(record["sourceEntries"])
    for key in record:
        if key.endswith("Sha256"):
            _digest(record[key])
    _require(
        _timestamp(record["createdAt"]) <= _now(trust)
        and _timestamp(record["createdAt"]) <= _timestamp(record["expiresAt"])
        and (not require_live or _now(trust) <= _timestamp(record["expiresAt"])),
        "commitment chronology/expiry refused",
    )
    _authenticate(
        trust,
        "output_prediction_commitment",
        record,
        "commitmentReceiptSha256",
        receipt,
    )
    candidate = _candidate(
        inputs, trust, record["createdAt"], require_live=require_live
    )
    snapshot = _parse(inputs.geometry)
    _require(
        _timestamp(snapshot["capturedAt"]) <= _timestamp(record["createdAt"]),
        "commitment predates geometry",
    )
    _require(
        _canonical(_projection(record, "commitmentReceiptSha256")) == candidate.payload,
        "committed inputs/algorithm/prediction differ",
    )
    _require(
        type(prediction) is bytes
        and len(prediction) <= 48_000_000
        and prediction == candidate.pcm,
        "prediction bytes differ from independent recomputation",
    )
    return record


def _channels(raw: bytes, count: int, *, prediction: bool) -> list[array[float]]:
    width, encoding = (8, "d") if prediction else (4, "i")
    _require(
        type(raw) is bytes and len(raw) == count * 2 * width,
        "decoded byte count differs",
    )
    values: array[Any] = array(encoding)
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if prediction:
        _require(
            all(math.isfinite(x) and abs(x) < 1 for x in values),
            "invalid prediction samples",
        )
        return [values[ch::2] for ch in range(2)]
    _require(
        all(type(x) is int and -(2**23) < x < 2**23 - 1 for x in values),
        "rendered clipping/invalid signed24 samples",
    )
    return [array("d", (x / 2**23 for x in values[ch::2])) for ch in range(2)]


def _metrics(expected: list[array[float]], actual: list[array[float]]) -> list[Json]:
    results: list[Json] = []
    for reference, output in zip(expected, actual, strict=True):
        _require(len(reference) == len(output) >= 960, "metric extent differs")
        residual = array("d", (a - b for a, b in zip(output, reference, strict=True)))
        energy = math.fsum(x * x for x in residual[:960])
        peak = energy
        for index in range(960, len(residual)):
            energy += residual[index] ** 2 - residual[index - 960] ** 2
            peak = max(peak, energy)
        rms = math.sqrt(math.fsum(x * x for x in residual) / len(residual))
        sliding = math.sqrt(max(0.0, peak) / 960)
        results.append(
            {
                "residualRms": rms,
                "maximumSliding20msResidualRms": sliding,
                "consistent": rms <= 0.0004 and sliding <= 0.006,
            }
        )
    return results


def _clip_edge_exclusion_mask(inputs: list[PredictionInputs], count: int) -> bytearray:
    """Mark committed audio clip-edge fade zones in a common pair interval."""
    mask = bytearray(count)
    for prediction_inputs in inputs:
        capture = _parse(prediction_inputs.geometry)
        geometry = _shape(
            capture["geometry"],
            "context extentFrames rate tracks items sourceMappings",
            "semantic geometry",
        )
        extent = _integer(geometry["extentFrames"], 1, 1498) * FRAME
        _require(extent >= count, "pair geometry is shorter than its common interval")
        binding = _record(
            prediction_inputs.input_binding,
            "inputs",
            "schemaVersion lane context delivery sourceEntries tracks "
            "itemMappings nativeSources",
        )
        sources = {row["sourceId"]: row for row in _sources(binding["sourceEntries"])}
        deliveries = {row["eventId"]: row for row in _list(binding["delivery"], 2048)}
        for item in _list(geometry["items"], 2048):
            if item["kind"] != "audio":
                continue
            record_start = _integer(item["recordStart"]) * FRAME
            record_end = (
                record_start + _integer(item["recordDuration"], 1, 1498) * FRAME
            )
            _require(record_end <= extent, "pair audio edge exceeds committed geometry")
            delivery = deliveries[item["eventId"]]
            active_count = record_end - record_start
            if delivery["kind"] == "narration":
                source = sources[item["sourceId"]]
                local = (
                    _integer(item["sourceStart"])
                    - _integer(source["nativeFrameOrigin"])
                ) * FRAME + _integer(source["pcmSampleOrigin"], 0)
                active_count = min(
                    active_count, _integer(source["durationSamples"], 1) - local
                )
            _require(active_count > 0, "pair audio active extent is empty")
            active_end = record_start + active_count
            for edge_start, edge_end in (
                (record_start, record_start + SOFT_FADE_SAMPLES),
                (active_end - SOFT_FADE_SAMPLES, active_end),
            ):
                low, high = max(0, edge_start), min(count, edge_end)
                if low < high:
                    mask[low:high] = b"\x01" * (high - low)
    return mask


def _exclude_clip_edge_zones(channels: list[array[float]], mask: bytearray) -> None:
    for channel in channels:
        _require(len(channel) == len(mask), "pair edge mask extent differs")
        for index, excluded in enumerate(mask):
            if excluded:
                channel[index] = 0.0


def _nonvacuity(prediction: bytes, count: int) -> list[Json]:
    predicted = _channels(prediction, count, prediction=True)
    signal = _metrics(predicted, [array("d", [0.0]) * count for _ in range(2)])
    _require(
        all(not channel["consistent"] for channel in signal),
        "vacuous prediction in expected channel",
    )
    return signal


@_refusal
def compare_committed_output(output: CommittedOutput, *, trust: OutputTrust) -> Json:
    """Recompute commitment then compare delivered MOV's authenticated PCM at zero lag.

    Returns an unsigned terminal payload, including numeric refusals. #209 seals
    this result then atomically appends its raw hash using prior-terminal-head.
    Invalid/partial inputs raise; their controller attempt must also be retained.
    """
    commitment = _verified_commitment(
        output.inputs,
        output.commitment,
        output.commitment_receipt,
        output.prediction,
        trust=trust,
        require_live=False,
    )
    context = commitment["context"]
    reservation = _record(output.reservation, "reservation", RESERVATION_FIELDS)
    _require(
        reservation["context"] == context
        and reservation["commitmentRawSha256"] == _hash(output.commitment)
        and reservation["commitmentPayloadSha256"]
        == _json_hash(_projection(commitment, "commitmentReceiptSha256")),
        "reservation commitment/context differs",
    )
    _digest(reservation["renderIntentSha256"])
    _identity(reservation["reservationId"])
    _require(
        _timestamp(commitment["createdAt"])
        <= _timestamp(reservation["reservedAt"])
        <= _timestamp(commitment["expiresAt"])
        and _timestamp(reservation["reservedAt"]) <= _now(trust),
        "reservation chronology differs",
    )
    _authenticate(
        trust,
        "output_render_reservation",
        reservation,
        "reservationReceiptSha256",
        output.reservation_receipt,
    )
    prior = _attempt(output.ledger, context)
    _require(
        prior is not None
        and prior["state"] == "reserved_by_render_intent"
        and prior["context"] == context
        and prior["commitmentRawSha256"] == _hash(output.commitment)
        and prior["commitmentPayloadSha256"] == reservation["commitmentPayloadSha256"]
        and prior["predictionBytesSha256"] == commitment["predictionBytesSha256"]
        and prior["reservationRawSha256"] == _hash(output.reservation),
        "complete live reserved attempt required",
    )
    lineage = _record(
        output.lineage,
        "lineage",
        (
            "schemaVersion lane context commitmentRawSha256 "
            "reservationRawSha256 renderIntentSha256 "
            "effectReceiptSha256 startReceiptSha256 "
            "completionReceiptSha256 jobId sourceOutputRawSha256"
        ),
    )
    _require(
        lineage["context"] == context
        and lineage["commitmentRawSha256"] == _hash(output.commitment)
        and lineage["reservationRawSha256"] == _hash(output.reservation)
        and lineage["renderIntentSha256"] == reservation["renderIntentSha256"],
        "native render lineage differs",
    )
    _identity(lineage["jobId"])
    for key in lineage:
        if key.endswith("Sha256"):
            _digest(lineage[key])
    binding = _parse(output.inputs.input_binding)
    _require(
        _hash(output.post_geometry) != _hash(output.inputs.geometry),
        "pre-render capture replayed as post-render",
    )
    post = _geometry(
        output.post_geometry,
        output.post_geometry_receipt,
        binding,
        trust,
        capture_phase="post_render",
        require_live=False,
        render_lineage=lineage,
    )
    _require(
        _json_hash(post["geometry"]) == commitment["geometrySha256"],
        "post-render semantic geometry changed",
    )
    _require(
        _timestamp(reservation["reservedAt"]) <= _timestamp(post["capturedAt"]),
        "post-render snapshot precedes reservation",
    )
    decode = _record(output.decode_record, "decode", DECODE_FIELDS)
    count = commitment["extentFrames"] * FRAME
    _require(
        decode["context"] == context
        and decode["sourceOutputRawSha256"] == lineage["sourceOutputRawSha256"]
        and (decode["container"], decode["videoCodec"], decode["audioCodec"])
        == ("mov", "prores422", "lpcm")
        and _integer(decode["audioBitDepth"]) == 24
        and _integer(decode["audioSampleRate"]) == 48000
        and _integer(decode["audioChannels"]) == 2
        and _integer(decode["sampleCount"]) == count,
        "same delivered MOV/profile/context/extent required",
    )
    for key in decode:
        if key.endswith("Sha256"):
            _digest(decode[key])
    _require(
        len(output.decoded_samples) <= 24_000_000
        and decode["decodedSamplesSha256"] == _hash(output.decoded_samples),
        "decoded sample hash/bounds differ",
    )
    _authenticate(
        trust,
        "output_decode_record",
        decode,
        "decodeReceiptSha256",
        output.decode_receipt,
        renderLineage=lineage,
    )
    predicted = _channels(output.prediction, count, prediction=True)
    actual = _channels(output.decoded_samples, count, prediction=False)
    signal = _nonvacuity(output.prediction, count)
    metrics = _metrics(predicted, actual)
    return {
        "schemaVersion": f"{PREFIX}comparison/v1",
        "lane": LANE,
        "context": context,
        "status": "compared_consistent"
        if all(ch["consistent"] for ch in metrics)
        else "compared_refused",
        "commitmentRawSha256": _hash(output.commitment),
        "commitmentPayloadSha256": reservation["commitmentPayloadSha256"],
        "reservationRawSha256": _hash(output.reservation),
        "renderLineage": lineage,
        "decodeRecordRawSha256": _hash(output.decode_record),
        "preGeometryRawSha256": _hash(output.inputs.geometry),
        "postGeometryRawSha256": _hash(output.post_geometry),
        "geometrySha256": commitment["geometrySha256"],
        "algorithmSha256": ALGORITHM_SHA256,
        "metrics": metrics,
        "signalMetrics": signal,
        "priorLedgerHeadSha256": _ledger_head(output.ledger),
        "internalControls": "unverified",
        "geometryStability": "not_claimed",
        "controlStability": "not_claimed",
        "futureAuthority": False,
    }


@_refusal
def _terminal_append(
    output: CommittedOutput,
    result_raw: bytes,
    receipt: bytes,
    current_ledger: list[Json],
    trust: OutputTrust,
) -> list[Json]:
    result = _record(
        result_raw,
        "comparison",
        (
            "schemaVersion lane context status commitmentRawSha256 "
            "commitmentPayloadSha256 reservationRawSha256 renderLineage"
            " decodeRecordRawSha256 preGeometryRawSha256 "
            "postGeometryRawSha256 geometrySha256 algorithmSha256 "
            "metrics signalMetrics priorLedgerHeadSha256 "
            "internalControls geometryStability controlStability "
            "futureAuthority comparisonReceiptSha256"
        ),
    )
    _authenticate(
        trust, "output_residual_comparison", result, "comparisonReceiptSha256", receipt
    )
    expected = compare_committed_output(output, trust=trust)
    _require(
        _canonical(_projection(result, "comparisonReceiptSha256"))
        == _canonical(expected),
        "terminal result differs from recomputation",
    )
    event = {
        "context": result["context"],
        "state": result["status"],
        "commitmentRawSha256": result["commitmentRawSha256"],
        "commitmentPayloadSha256": result["commitmentPayloadSha256"],
        "predictionBytesSha256": _hash(output.prediction),
        "reservationRawSha256": result["reservationRawSha256"],
        "resultRawSha256": _hash(result_raw),
    }
    return _append_ledger(current_ledger, event, result["priorLedgerHeadSha256"])


def _terminal_comparison(terminal: TerminalOutput, trust: OutputTrust) -> Json:
    result = _record(
        terminal.comparison,
        "comparison",
        "schemaVersion lane context status commitmentRawSha256 commitmentPayloadSha256 "
        "reservationRawSha256 renderLineage decodeRecordRawSha256 preGeometryRawSha256 "
        "postGeometryRawSha256 geometrySha256 algorithmSha256 metrics signalMetrics "
        "priorLedgerHeadSha256 internalControls geometryStability controlStability "
        "futureAuthority comparisonReceiptSha256",
    )
    _ledger_head(terminal.ledger)
    _authenticate(
        trust,
        "output_residual_comparison",
        result,
        "comparisonReceiptSha256",
        terminal.comparison_receipt,
    )
    raw_hash = _hash(terminal.comparison)
    entries = [
        entry for entry in terminal.ledger if entry["resultRawSha256"] == raw_hash
    ]
    _require(len(entries) == 1, "sealed terminal result absent from complete history")
    entry = entries[0]
    _require(
        entry["context"] == result["context"]
        and entry["state"] == result["status"]
        and entry["commitmentRawSha256"] == result["commitmentRawSha256"]
        and entry["commitmentPayloadSha256"] == result["commitmentPayloadSha256"]
        and entry["reservationRawSha256"] == result["reservationRawSha256"]
        and entry["predictionBytesSha256"] == _hash(terminal.output.prediction)
        and entry["priorHeadSha256"] == result["priorLedgerHeadSha256"],
        "terminal lineage differs",
    )
    # Only the authenticated prior-terminal-head is projected internally;
    # callers supply the complete current chain, including the terminal entry.
    past = replace(terminal.output, ledger=terminal.ledger[: entry["sequence"]])
    expected = compare_committed_output(past, trust=trust)
    _require(
        _canonical(_projection(result, "comparisonReceiptSha256"))
        == _canonical(expected),
        "sealed terminal result differs from recomputation",
    )
    return result


@_refusal
def _compare_prediction_pair_from_verified(
    pristine: TerminalOutput,
    edited: TerminalOutput,
    left: Json,
    right: Json,
) -> Json:
    """Run pair checks only after both terminals were verified in this call."""
    a, b = left["context"], right["context"]
    _require(
        left["status"] == right["status"] == "compared_consistent",
        "each output must already qualify",
    )
    _require(
        a["phase"] == "pristine"
        and b["phase"] == "edited"
        and a["target"] == b["target"]
        and a["caseId"] == b["caseId"],
        "pair target/case/phase differs",
    )
    _require(
        all(
            a[key] == b[key]
            for key in a
            if key
            not in AUTHORITY_REFERENCE_FIELDS | {"phase", "invocationId", "binding"}
        ),
        "pair authenticated input identity differs",
    )
    # Each complete output already matched its own full-extent prediction.
    # Unequal extents are compared at zero lag over their authenticated common
    # prefix, with committed clip-edge fade zones excluded from discrimination.
    # A duration-only edge ramp therefore cannot establish an audio change.
    pristine_count = len(pristine.output.prediction) // 16
    edited_count = len(edited.output.prediction) // 16
    _require(
        edited_count <= pristine_count
        and len(pristine.output.decoded_samples) == pristine_count * 8
        and len(edited.output.decoded_samples) == edited_count * 8,
        "pair extents are not the committed complete outputs",
    )
    count = edited_count
    lp, rp = (
        _channels(pristine.output.prediction[: count * 16], count, prediction=True),
        _channels(edited.output.prediction, count, prediction=True),
    )
    lo, ro = (
        _channels(
            pristine.output.decoded_samples[: count * 8], count, prediction=False
        ),
        _channels(edited.output.decoded_samples, count, prediction=False),
    )
    edge_mask = _clip_edge_exclusion_mask(
        [pristine.output.inputs, edited.output.inputs], count
    )
    for channels in (lp, rp, lo, ro):
        _exclude_clip_edge_zones(channels, edge_mask)
    cross = {
        "predictionDifference": _metrics(lp, rp),
        "editedAgainstPristine": _metrics(lp, ro),
        "pristineAgainstEdited": _metrics(rp, lo),
    }
    _require(
        all(
            any(not channel["consistent"] for channel in metrics)
            for metrics in cross.values()
        ),
        "audio pair indistinguishable under fixed gates",
    )
    return {
        "schemaVersion": f"{PREFIX}pair/v1",
        "lane": LANE,
        "pristineComparisonRawSha256": _hash(pristine.comparison),
        "editedComparisonRawSha256": _hash(edited.comparison),
        "pristineLedgerHeadSha256": _ledger_head(pristine.ledger),
        "editedLedgerHeadSha256": _ledger_head(edited.ledger),
        "pristineSampleCount": pristine_count,
        "editedSampleCount": edited_count,
        "commonInterval": {"startSample": 0, "endSample": count},
        "crossMetrics": cross,
        "internalControls": "unverified",
        "geometryStability": "not_claimed",
        "controlStability": "not_claimed",
        "futureAuthority": False,
    }


@_refusal
def compare_prediction_pair(
    pristine: TerminalOutput, edited: TerminalOutput, *, trust: OutputTrust
) -> Json:
    """Pure audio-changing pair test. Video-only A uses per-output consistency."""
    left, right = (
        _terminal_comparison(pristine, trust),
        _terminal_comparison(edited, trust),
    )
    return _compare_prediction_pair_from_verified(pristine, edited, left, right)
