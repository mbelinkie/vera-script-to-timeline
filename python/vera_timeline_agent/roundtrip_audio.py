"""Bounded source-support/mix evidence; no transcript, synthesis or native calls.

Positive qualification is currently injected synthetic closed routing only.
Retained W1 can establish consistency, never independent live qualification.
File receipts attest internal consistency, not authentic observation/rendering.
"""

from __future__ import annotations

import io
import math
import wave
from array import array
from pathlib import Path
from typing import Any

from vera_timeline_agent.roundtrip_build import (
    JsonObject,
    ProofBuildError,
    _digest,
    _file_hash,
    _operator_bytes,
    _parse,
    _receipt_bytes,
    _regular,
)

FRAME = 1920
MAX_SAMPLES = 3_000_000
LIMITATIONS = [
    "Numeric tolerances are not an absence classifier: arbitrarily quiet/short "
    "out-of-model residue can pass. Full support excision and independently "
    "qualified closed routing are indispensable.",
    "File hashes and receipt fields establish internal consistency, not live "
    "native capture/render authenticity or clip ancestry.",
    "Fixture-generator supports are synthetic declarations, not independently "
    "verified real speech alignments. Real qualification remains #145 work.",
]
CONTROL_KEYS = {
    "enabled",
    "mute",
    "solo",
    "effects",
    "sends",
    "destination",
    "gainDb",
    "pan",
}
SEGMENT_KEYS = {
    "uid",
    "recordStart",
    "recordEnd",
    "sourceStart",
    "sourceEnd",
    "speed",
    "enabled",
    "online",
}


def _shape(value: Any, keys: set[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProofBuildError(f"unsupported {label} shape")
    return value


def _int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ProofBuildError(f"invalid {label} integer")
    return value


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ProofBuildError(f"invalid {label} identity")
    return value


class _Files:
    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        self.hashes: dict[str, str] = {}

    def read(self, name: str, *, json_file: bool = False) -> bytes:
        path = Path(name)
        if (
            path.is_absolute()
            or not path.parts
            or any(p in {"..", "."} for p in path.parts)
        ):
            raise ProofBuildError("independent local path required")
        full = _regular(self.root / path)
        if full.stat().st_size > 32 * 1024 * 1024:
            raise ProofBuildError("bounded audio input exceeds 32 MiB")
        raw = _operator_bytes(full) if json_file else full.read_bytes()
        digest = _digest(raw)
        if name in self.hashes and self.hashes[name] != digest:
            raise ProofBuildError("audio evidence changed during reading")
        self.hashes[name] = digest
        return raw

    def json(self, name: str) -> JsonObject:
        return _parse(self.read(name, json_file=True))

    def current(self) -> None:
        for name, digest in self.hashes.items():
            if _file_hash(self.root / name) != digest:
                raise ProofBuildError(f"audio evidence changed: {name}")


def _pcm(
    raw: bytes, channels: int, expected_samples: int | None = None
) -> list[array[float]]:
    with wave.open(io.BytesIO(raw), "rb") as stream:
        width = stream.getsampwidth()
        count = stream.getnframes()
        if (stream.getframerate(), stream.getnchannels(), stream.getcomptype()) != (
            48000,
            channels,
            "NONE",
        ) or width not in {2, 3}:
            raise ProofBuildError("expected complete PCM16/24 WAV at 48k")
        if (
            count < 960
            or count > MAX_SAMPLES
            or (expected_samples is not None and count != expected_samples)
        ):
            raise ProofBuildError("decoded extent differs from complete program")
        pcm = stream.readframes(count)
        if len(pcm) != count * channels * width:
            raise ProofBuildError("truncated PCM data")
    scale = 2 ** (width * 8 - 1)
    values = array(
        "d",
        (
            int.from_bytes(pcm[i : i + width], "little", signed=True) / scale
            for i in range(0, len(pcm), width)
        ),
    )
    return [values[channel::channels] for channel in range(channels)]


def _supports(source: JsonObject, size: int) -> list[JsonObject]:
    supports = source["supports"]
    if not isinstance(supports, list) or len(supports) > 64:
        raise ProofBuildError("bounded support inventory required")
    seen: set[str] = set()
    previous = 0
    for support in supports:
        _shape(support, {"tokenId", "startSample", "endSample"}, "support")
        identity = _id(support["tokenId"], "token")
        start = _int(support["startSample"], "support start")
        end = _int(support["endSample"], "support end", start + 1)
        if identity in seen or start < previous or end > size:
            raise ProofBuildError("ambiguous/out-of-order support inventory")
        seen.add(identity)
        previous = end
    return supports


def _observation(
    value: JsonObject,
    sources: dict[str, JsonObject],
    target: JsonObject,
    extent: int,
    *,
    retained: bool,
) -> list[JsonObject]:
    _shape(
        value,
        {"schemaVersion", "target", "extentFrames", "programControls", "routes"},
        "observation",
    )
    if (
        value["schemaVersion"] != "issue-144-audio-observation/v1"
        or value["target"] != target
    ):
        raise ProofBuildError("audio observation target differs")
    if type(value["extentFrames"]) is not int or value["extentFrames"] != extent:
        raise ProofBuildError("audio observation extent differs")
    program = value["programControls"]
    if retained and program == {"qualification": "unobserved"}:
        pass
    elif program != {"gainDb": 0, "effects": [], "limiter": False} or (
        not isinstance(program, dict)
        or type(program.get("gainDb")) not in {int, float}
        or program.get("limiter") is not False
    ):
        raise ProofBuildError("unknown/non-neutral program controls")
    routes = value["routes"]
    if not isinstance(routes, list) or len(routes) != len(sources):
        raise ProofBuildError("complete unique route inventory required")
    ids: set[str] = set()
    source_ids: set[str] = set()
    uids: set[str] = set()
    for route in routes:
        _shape(route, {"id", "sourceId", "controls", "segments"}, "route")
        identity = _id(route["id"], "route")
        source_id = _id(route["sourceId"], "source")
        if identity in ids or source_id in source_ids or source_id not in sources:
            raise ProofBuildError("ambiguous route inventory/source binding")
        ids.add(identity)
        source_ids.add(source_id)
        controls = route["controls"]
        # Retained captures cannot fill unobserved Solo/bus/sends/FX facts.
        if retained and controls == {"qualification": "unobserved"}:
            pass
        else:
            _shape(controls, CONTROL_KEYS, "controls")
            if (
                any(
                    controls[key] is not wanted
                    for key, wanted in (
                        ("enabled", True),
                        ("mute", False),
                        ("solo", False),
                    )
                )
                or controls["effects"] != []
                or controls["sends"] != []
                or controls["destination"] != "stereo-program"
                or type(controls["gainDb"]) not in {int, float}
                or controls["gainDb"] != 0
                or type(controls["pan"]) not in {int, float}
                or controls["pan"] != 0
            ):
                raise ProofBuildError("unknown or non-neutral controls")
        segments = route["segments"]
        if not isinstance(segments, list) or not segments or len(segments) > 65:
            raise ProofBuildError("complete route removal or unbounded segments")
        record_end = source_end = 0
        for segment in segments:
            _shape(segment, SEGMENT_KEYS, "segment")
            uid = _id(segment["uid"], "occurrence")
            start = _int(segment["recordStart"], "record start")
            end = _int(segment["recordEnd"], "record end", start + 1)
            source_start = _int(segment["sourceStart"], "source start")
            end_source = _int(segment["sourceEnd"], "source end", source_start + 1)
            if type(segment["speed"]) not in {int, float} or segment["speed"] != 100:
                raise ProofBuildError("unsupported speed")
            if segment["enabled"] is not True or segment["online"] is not True:
                raise ProofBuildError("disabled/offline occurrence")
            if uid in uids or start < record_end or source_start < source_end:
                raise ProofBuildError("ambiguous occurrence/source order")
            if (
                end > extent
                or end_source * FRAME > sources[source_id]["samples"]
                or end - start != end_source - source_start
            ):
                raise ProofBuildError("source/record geometry or extent differs")
            uids.add(uid)
            record_end, source_end = end, end_source
    return routes


def _route_samples(
    routes: list[JsonObject], samples: dict[str, array[float]], extent: int
) -> list[array[float]]:
    results = []
    for route in routes:
        result = array("d", [0.0]) * (extent * FRAME)
        source = samples[route["sourceId"]]
        for segment in route["segments"]:
            start, end = segment["recordStart"] * FRAME, segment["recordEnd"] * FRAME
            result[start:end] = source[
                segment["sourceStart"] * FRAME : segment["sourceEnd"] * FRAME
            ]
        results.append(result)
    return results


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    augmented = [[*row, value] for row, value in zip(matrix, rhs, strict=True)]
    for column in range(len(rhs)):
        pivot = max(
            range(column, len(rhs)), key=lambda row: abs(augmented[row][column])
        )
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            raise ProofBuildError("singular calibration/source attribution")
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(len(rhs)):
            if row != column:
                factor = augmented[row][column]
                augmented[row] = [
                    value - factor * basis
                    for value, basis in zip(
                        augmented[row], augmented[column], strict=True
                    )
                ]
    return [row[-1] for row in augmented]


def _gains(
    routes: list[array[float]], program: list[array[float]]
) -> list[list[float]]:
    # Independent unchanged reference only. Never fit an edited program.
    gram = [
        [math.fsum(x * y for x, y in zip(left, right, strict=True)) for right in routes]
        for left in routes
    ]
    results = []
    for channel in program:
        rhs = [
            math.fsum(x * y for x, y in zip(route, channel, strict=True))
            for route in routes
        ]
        gains = _solve(gram, rhs)
        if any(not math.isfinite(gain) or not 0.25 <= gain <= 1.5 for gain in gains):
            raise ProofBuildError("fixed gain qualification outside [0.25,1.5]")
        results.append(gains)
    return results


def _metrics(
    routes: list[array[float]], program: list[array[float]], gains: list[list[float]]
) -> list[JsonObject]:
    results = []
    for actual, channel_gains in zip(program, gains, strict=True):
        residual = array(
            "d",
            (
                value
                - math.fsum(
                    gain * route[index]
                    for gain, route in zip(channel_gains, routes, strict=True)
                )
                for index, value in enumerate(actual)
            ),
        )
        window = 960
        energy = math.fsum(x * x for x in residual[:window])
        peak = energy
        for index in range(window, len(residual)):
            energy += residual[index] ** 2 - residual[index - window] ** 2
            peak = max(peak, energy)
        rms = math.sqrt(math.fsum(x * x for x in residual) / len(residual))
        maximum = math.sqrt(max(0.0, peak) / window)
        results.append(
            {
                "residualRms": rms,
                "maximumSliding20msResidualRms": maximum,
                "consistent": rms <= 0.0004 and maximum <= 0.006,
            }
        )
    return results


def _render(
    files: _Files,
    name: str,
    *,
    baseline_hash: str,
    observation_hash: str,
    profile_hash: str,
    target: JsonObject,
    extent: int,
) -> list[array[float]]:
    receipt = files.json(name)
    _shape(
        receipt,
        {
            "schemaVersion",
            "target",
            "baselineHash",
            "observationHash",
            "profileHash",
            "jobId",
            "queuedJobId",
            "polledJobId",
            "status",
            "settings",
            "output",
        },
        "render receipt",
    )
    if (
        receipt["schemaVersion"] != "issue-144-audio-render/v1"
        or receipt["target"] != target
        or receipt["baselineHash"] != baseline_hash
        or receipt["observationHash"] != observation_hash
        or receipt["profileHash"] != profile_hash
    ):
        raise ProofBuildError("render receipt binding differs")
    job = _id(receipt["jobId"], "render job")
    if (
        receipt["queuedJobId"] != job
        or receipt["polledJobId"] != job
        or receipt["status"] != "complete"
    ):
        raise ProofBuildError("render job polling/queue differs")
    settings = _shape(
        receipt["settings"],
        {
            "startFrame",
            "endFrame",
            "frameRate",
            "sampleRate",
            "channels",
            "codec",
            "sampleWidth",
        },
        "render settings",
    )
    if (
        any(
            type(settings[key]) is not int
            for key in (
                "startFrame",
                "endFrame",
                "sampleRate",
                "channels",
                "sampleWidth",
            )
        )
        or settings
        != {
            "startFrame": 0,
            "endFrame": extent,
            "frameRate": "25/1",
            "sampleRate": 48000,
            "channels": 2,
            "codec": "pcm",
            "sampleWidth": settings["sampleWidth"],
        }
        or settings["sampleWidth"] not in {2, 3}
    ):
        raise ProofBuildError("render settings/extent differs")
    output = _shape(receipt["output"], {"path", "sha256"}, "render output")
    raw = files.read(_id(output["path"], "render path"))
    if _digest(raw) != output["sha256"]:
        raise ProofBuildError("render output hash differs")
    with wave.open(io.BytesIO(raw), "rb") as stream:
        if stream.getsampwidth() != settings["sampleWidth"]:
            raise ProofBuildError("render PCM/settings differ")
    return _pcm(raw, 2, extent * FRAME)


def verify_omission_evidence(
    root: Path,
    *,
    baseline_hash: str,
    target: JsonObject,
    row_id: str,
    primary_source_id: str,
    evidence_level: str,
) -> JsonObject:
    """Verify immutable files against caller's verified baseline/target/row.

    The caller must bind these expected identities to the actual proof baseline,
    deriving primary_source_id from its actual compiled narration event. Auxiliary
    sources may share a row; profile JSON never supplies the primary selector.
    No operator boolean enables a live lane. Split geometry establishes a unique
    source-support decomposition; it does not establish native clip ancestry.
    """
    files = _Files(root)
    report: JsonObject = {
        "schemaVersion": "issue-144-audio-evidence/v1",
        "status": "refused",
        "evidenceLevel": evidence_level,
        "baselineHash": baseline_hash,
        "target": target,
        "rowId": row_id,
        "primarySourceId": primary_source_id,
        "limitations": LIMITATIONS,
        "channels": [],
        "codeHash": _file_hash(Path(__file__)),
    }
    try:
        if evidence_level not in {"synthetic_injected", "retained_consistency"}:
            raise ProofBuildError(
                "#145 independent route/support/observer/renderer "
                "qualification required"
            )
        _shape(target, {"projectUid", "timelineUid"}, "target")
        for value in target.values():
            _id(value, "target")
        _id(row_id, "row")
        _id(primary_source_id, "primary source")
        profile = files.json("profile.json")
        _shape(
            profile,
            {
                "schemaVersion",
                "evidenceLevel",
                "supportProvenance",
                "baselineHash",
                "extentFrames",
                "sources",
            },
            "profile",
        )
        if (
            profile["schemaVersion"] != "issue-144-audio-profile/v1"
            or profile["evidenceLevel"] != evidence_level
            or profile["baselineHash"] != baseline_hash
        ):
            raise ProofBuildError("audio profile binding differs")
        if profile["supportProvenance"] != "fixture_generator":
            raise ProofBuildError(
                "independent support provenance required; "
                "provider word ends unsupported"
            )
        extent = _int(profile["extentFrames"], "extent", 1)
        if extent * FRAME > MAX_SAMPLES:
            raise ProofBuildError("bounded complete extent exceeded")
        hashes: set[str] = set()
        decoded_hashes: set[str] = set()
        samples: dict[str, array[float]] = {}
        sources: dict[str, JsonObject] = {}
        entries = profile["sources"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
            raise ProofBuildError("bounded source inventory required")
        for source in entries:
            _shape(source, {"id", "rowId", "path", "sha256", "supports"}, "source")
            identity = _id(source["id"], "source")
            _id(source["rowId"], "row")
            if identity in sources:
                raise ProofBuildError("duplicate source inventory")
            if source["sha256"] in hashes:
                raise ProofBuildError("ambiguous row/source binding or alias")
            raw = files.read(_id(source["path"], "source path"))
            if _digest(raw) != source["sha256"]:
                raise ProofBuildError("source hash differs")
            channel = _pcm(raw, 1)[0]
            decoded_hash = _digest(channel.tobytes())
            if decoded_hash in decoded_hashes:
                raise ProofBuildError("ambiguous decoded source alias")
            decoded_hashes.add(decoded_hash)
            _supports(source, len(channel))
            hashes.add(source["sha256"])
            samples[identity] = channel
            sources[identity] = {**source, "samples": len(channel)}
        selected = sources.get(primary_source_id)
        if selected is None:
            raise ProofBuildError("caller-bound primary source is unknown")
        if selected["rowId"] != row_id or len(selected["supports"]) < 3:
            raise ProofBuildError("caller-bound row/source support binding differs")
        baseline = files.json("baseline.json")
        if files.hashes["baseline.json"] != baseline_hash:
            raise ProofBuildError("verified baseline hash differs")
        a, b = files.json("observation-a.json"), files.json("observation-b.json")
        if _receipt_bytes(a) != _receipt_bytes(b):
            raise ProofBuildError("adjacent audio observations differ")
        retained = evidence_level == "retained_consistency"
        baseline_routes = _observation(
            baseline, sources, target, extent, retained=retained
        )
        routes = _observation(a, sources, target, extent, retained=retained)
        if [(r["id"], r["sourceId"], r["controls"]) for r in routes] != [
            (r["id"], r["sourceId"], r["controls"]) for r in baseline_routes
        ]:
            raise ProofBuildError("route inventory/source binding or controls changed")
        omitted: list[str] = []
        retained_ids: list[str] = []
        decomposition: list[JsonObject] = []
        for old, new in zip(baseline_routes, routes, strict=True):
            source = sources[old["sourceId"]]
            if source["id"] != selected["id"] and old != new:
                raise ProofBuildError("untouched route changed")
            for support in source["supports"]:
                start, end = support["startSample"], support["endSample"]

                def intersections(
                    route: JsonObject, start: int = start, end: int = end
                ) -> list[tuple[int, int]]:
                    return [
                        (
                            max(start, s["sourceStart"] * FRAME),
                            min(end, s["sourceEnd"] * FRAME),
                        )
                        for s in route["segments"]
                        if s["sourceStart"] * FRAME < end
                        and s["sourceEnd"] * FRAME > start
                    ]

                if intersections(old) != [(start, end)]:
                    raise ProofBuildError("baseline support is incomplete/ambiguous")
                hits = intersections(new)
                if hits and hits != [(start, end)]:
                    raise ProofBuildError("partial support or duplicate token")
                if source["id"] == selected["id"]:
                    (retained_ids if hits else omitted).append(support["tokenId"])
                    decomposition.append(
                        {
                            "tokenId": support["tokenId"],
                            "supportSamples": [start, end],
                            "retained": bool(hits),
                        }
                    )
                elif not hits:
                    raise ProofBuildError("untouched route token removed")
        order = [s["tokenId"] for s in selected["supports"]]
        positions = [order.index(token) for token in omitted]
        if (
            not positions
            or positions[0] == 0
            or positions[-1] == len(order) - 1
            or positions != list(range(positions[0], positions[-1] + 1))
        ):
            raise ProofBuildError("no interior omission or noncontiguous omission")
        report.update(
            omittedTokenIds=omitted,
            retainedTokenIds=retained_ids,
            decomposition=decomposition,
        )
        profile_hash = files.hashes["profile.json"]
        reference = _render(
            files,
            "calibration.json",
            baseline_hash=baseline_hash,
            observation_hash=baseline_hash,
            profile_hash=profile_hash,
            target=target,
            extent=extent,
        )
        output = _render(
            files,
            "render.json",
            baseline_hash=baseline_hash,
            observation_hash=files.hashes["observation-a.json"],
            profile_hash=profile_hash,
            target=target,
            extent=extent,
        )
        if (
            files.json("calibration.json")["jobId"]
            == files.json("render.json")["jobId"]
        ):
            raise ProofBuildError("calibration/edited render job identity reused")
        full = _route_samples(baseline_routes, samples, extent)
        gains = _gains(full, reference)
        reference_metrics = _metrics(full, reference, gains)
        if not all(c["consistent"] for c in reference_metrics):
            raise ProofBuildError("unchanged calibration consistency differs")
        channels = _metrics(_route_samples(routes, samples, extent), output, gains)
        report.update(
            channels=channels,
            calibrationChannels=reference_metrics,
            gains=gains,
            sourceId=selected["id"],
            extentFrames=extent,
            sourceSegments=next(
                r["segments"] for r in routes if r["sourceId"] == selected["id"]
            ),
        )
        if not all(c["consistent"] for c in channels):
            raise ProofBuildError("complete render consistency failed")
        files.current()
        report["status"] = "consistent_unqualified" if retained else "supported"
    except (ProofBuildError, OSError, ValueError, TypeError, wave.Error) as error:
        report["reason"] = str(error)
    report["inputs"] = dict(files.hashes)
    report["reportHash"] = _digest(_receipt_bytes(report))
    return report
