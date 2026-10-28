"""Audio-bound measured word boundaries for a generated narration asset (#182).

Onsets come from the provider's word marks, shifted by a *verified* lag between
the raw provider PCM and the normalized WAV.  Audible ends are measured on the
raw provider PCM (before compression can lift quiet tails) and mapped onto the
normalized timeline through that same verified lag.  They exist only where a
real quiet gap follows the word.  Connected speech therefore yields an onset
but no audible end; consumers fail closed on it exactly as they do for missing
reviewed ends.

Lag estimation uses ``wave``/``array``/``math``. Same-rate qualification also
replays the existing local normalizer: correlation alone cannot exclude tiny
insertions/deletions that resemble a momentary gain change.
"""

from __future__ import annotations

import io
import json
import math
import re
import sys
import uuid
import wave
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import accumulate
from typing import Any, Never, cast

from vera_timeline_agent.narration.cache import CacheError, NarrationCache
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    canonical_json_bytes,
    identity_hash,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import (
    NORMALIZER_VERSION,
    ClockQualificationError,
    MediaToolError,
    Normalizer,
)
from vera_timeline_agent.narration.stage_directions import (
    masked_text as mask_stage_directions,
)

ALGORITHM_ID = "vera-polly-marks-energy-ends"
ALGORITHM_VERSION = "3"
METHOD = "measured_audio_boundaries/v1"
ONSET_BASIS = "provider_word_marks_lag_verified"
EVIDENCE_VERSION = "narration-boundary-evidence/v1"
ARTIFACT_VERSION = "narration-measurement/v1"
TOKENIZATION_VERSION = "script-document/v2-frozen-tokens"
SAMPLE_RATE = 48_000
_ASSET_ID_PREFIX = "vera:narration-cache-asset:"
_FLOOR_DB = -120.0

DEFAULT_PARAMETERS: dict[str, Any] = {
    "sampleRateHz": SAMPLE_RATE,
    "lagEnvelopeWindowMs": 5,
    "lagEnvelopeHopMs": 1,
    "lagSearchMs": 20,
    "lagToleranceMs": 2,
    "minLagCorrelationPermille": 900,
    "lagSampleAnchorMs": 20,
    "lagSampleProbeStride": 8,
    "lagSamplePeakMarginPpm": 1000,
    "lagSampleCheckMs": 5,
    "endWindowMs": 5,
    "endRelativeDropDb": 18,
    "endQuietDbfs": -42,
    "endQuietRunMs": 30,
    "onsetUncertaintyMs": 25,
    "audibleEndUncertaintyMs": 30,
}


class MeasurementError(ValueError):
    """Measurement was refused; ``reasons`` lists every problem found."""

    def __init__(self, reasons: Sequence[str]) -> None:
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass(frozen=True)
class Lag:
    samples: int
    milliseconds: float
    correlation: float
    integer_ms: int
    method: str = "rms_envelope"
    uncertainty_samples: int = 48
    windows_verified: int = 0
    clock: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class EndDecision:
    end_sample: int | None
    reason: str
    window_count: int
    peak_db: float | None
    threshold_db: float | None
    last_loud_window: int | None
    quiet_windows_after: int


@dataclass(frozen=True)
class MeasurementResult:
    artifact: dict[str, Any]
    artifact_bytes: bytes
    evidence: dict[str, Any]


@dataclass(frozen=True)
class LoadedAsset:
    asset: NarrationAudioAsset
    wav_bytes: bytes
    timing_bytes: bytes
    raw_pcm: bytes
    raw_sample_rate: int


def parameters_hash(parameters: Mapping[str, Any]) -> str:
    """Hash in the compiler's canonical form (``sha256CanonicalJson`` in
    ``packages/contracts/src/compiler-core.ts``): sorted keys, two-space indent,
    trailing newline.  Parameters are integer-only so Python and JavaScript
    serialize them identically.
    """

    def check(value: object) -> None:
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return
        if isinstance(value, int):
            if abs(value) > 2**53 - 1:
                raise MeasurementError(["algorithm parameters must be safe integers"])
            return
        if isinstance(value, Mapping):
            for key, nested in value.items():
                # JavaScript orders integer-like keys numerically, Python
                # sorts lexically, so such keys would hash differently.
                if isinstance(key, str) and re.fullmatch(r"(0|[1-9][0-9]*)", key):
                    raise MeasurementError(
                        [
                            "algorithm parameters must not contain integer-like "
                            f"object keys (found {key!r}); JavaScript and Python "
                            "order them differently"
                        ]
                    )
                check(nested)
            return
        if isinstance(value, list):
            for nested in value:
                check(nested)
            return
        raise MeasurementError(["algorithm parameters must be integer-only JSON"])

    check(parameters)
    text = (
        json.dumps(dict(parameters), sort_keys=True, ensure_ascii=False, indent=2)
        + "\n"
    )
    return sha256_bytes(text.encode("utf-8"))


def rational(samples: int | Fraction, rate: int = SAMPLE_RATE) -> dict[str, int]:
    value = Fraction(samples) / rate
    return {"numerator": value.numerator, "denominator": value.denominator}


def _ms_rational(milliseconds: int) -> dict[str, int]:
    value = Fraction(milliseconds, 1000)
    return {"numerator": value.numerator, "denominator": value.denominator}


# ---------------------------------------------------------------- audio helpers


def read_wav(wav_bytes: bytes) -> tuple[array[int], int, int, int]:
    """Return (samples, rate, channels, frames) at 16-bit scale (PCM-16/24)."""

    try:
        with wave.open(io.BytesIO(wav_bytes)) as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.getnframes()
            raw = handle.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise MeasurementError(
            [f"normalized audio is not a readable WAV: {error}"]
        ) from error
    if width == 3:
        # VERA's normalized assets are PCM-24; keep the 16-bit level scale.
        samples = array(
            "h",
            (
                int.from_bytes(raw[i : i + 3], "little", signed=True) >> 8
                for i in range(0, len(raw) - len(raw) % 3, 3)
            ),
        )
        return samples, rate, channels, frames
    if width != 2:
        raise MeasurementError(["normalized audio must be 16-bit or 24-bit PCM"])
    samples = array("h")
    samples.frombytes(raw)
    if samples.itemsize != 2:  # pragma: no cover - platform guard
        raise MeasurementError(["unsupported platform short size"])
    if sys.byteorder == "big":  # pragma: no cover
        samples.byteswap()
    return samples, rate, channels, frames


def _pcm_s16le(data: bytes) -> array[int]:
    samples = array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if sys.byteorder == "big":  # pragma: no cover
        samples.byteswap()
    return samples


def _prefix_square_sums(samples: Sequence[int]) -> array[float]:
    prefix = array("d", [0.0])
    prefix.extend(accumulate(float(x) * x for x in samples))
    return prefix


def _envelope(
    samples: Sequence[int], rate: int, window_ms: int, hop_ms: int
) -> list[float]:
    prefix = _prefix_square_sums(samples)
    count = (len(samples) * 1000 - window_ms * rate) // (hop_ms * rate) + 1
    if count < 1:
        return []
    envelope: list[float] = []
    for k in range(count):
        start = k * hop_ms * rate // 1000
        end = (k * hop_ms + window_ms) * rate // 1000
        envelope.append(math.sqrt((prefix[end] - prefix[start]) / (end - start)))
    return envelope


def _pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = len(a)
    if n < 2:
        return None
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = var_a = var_b = 0.0
    for x, y in zip(a, b, strict=True):
        dx = x - mean_a
        dy = y - mean_b
        cov += dx * dy
        var_a += dx * dx
        var_b += dy * dy
    if var_a <= 0.0 or var_b <= 0.0:
        return None
    return cov / math.sqrt(var_a * var_b)


def _sample_lag(
    raw: Sequence[int], normalized: Sequence[int], parameters: Mapping[str, Any]
) -> Lag:
    """Estimate one integer lag, without fitting or rounding a correlation peak.

    Three disjoint regions must independently identify the same unique peak.
    Sparse probes keep the exhaustive search cheap; every overlapping sample
    is then checked in short dense windows, including single-sample neighbours.
    Exact continuity is qualified separately by reproducing the transform.
    """

    def refuse(reason: str) -> Never:
        raise MeasurementError([f"normalization timing not verified: {reason}"])

    search = int(parameters["lagSearchMs"]) * SAMPLE_RATE // 1000
    anchor = int(parameters["lagSampleAnchorMs"]) * SAMPLE_RATE // 1000
    stride = int(parameters["lagSampleProbeStride"])
    check = int(parameters["lagSampleCheckMs"]) * SAMPLE_RATE // 1000
    margin = int(parameters["lagSamplePeakMarginPpm"]) / 1_000_000
    minimum = int(parameters["minLagCorrelationPermille"]) / 1000
    if min(search, anchor, stride, check) <= 0 or margin <= 0:
        refuse("invalid sample verification parameters")
    extent = min(len(raw), len(normalized))
    third = extent // 3
    if third < anchor + 2 * search:
        refuse("audio too short for independent sample windows")
    lags: list[int] = []
    correlations: list[float] = []
    for region in range(3):
        anchor_starts = range(
            region * third + search, (region + 1) * third - search - anchor + 1, anchor
        )
        start = max(
            anchor_starts, key=lambda pos: sum(x * x for x in raw[pos : pos + anchor])
        )
        probe = raw[start : start + anchor : stride]
        scores: dict[int, float] = {}
        for candidate in range(-search, search + 1):
            score = _pearson(
                probe,
                normalized[start + candidate : start + candidate + anchor : stride],
            )
            if score is not None:
                scores[candidate] = score
        if not scores:
            refuse("sample windows have no audible variation")
        best = max(scores, key=lambda candidate: scores[candidate])
        peak = scores[best]
        if abs(best) == search or peak < minimum:
            refuse("sample correlation below threshold or at search boundary")
        if any(peak - score < margin for lag, score in scores.items() if lag != best):
            refuse("ambiguous sample correlation peak")
        lags.append(best)
        correlations.append(peak)
    if len(set(lags)) != 1:
        refuse(
            "independent sample windows disagree (local drift or insertion/deletion)"
        )
    lag = lags[0]
    if abs(lag) * 1000 > int(parameters["lagToleranceMs"]) * SAMPLE_RATE:
        refuse("sample lag exceeds tolerance")

    lo, hi = max(0, -lag), min(len(raw), len(normalized) - lag)
    # Any unmatched material must be genuine silence, never deleted speech.
    if (
        any(raw[:lo])
        or any(raw[hi:])
        or any(normalized[: lo + lag])
        or any(normalized[hi + lag :])
    ):
        refuse("unmatched non-silent samples outside the verified overlap")
    windows = 0
    # Half-overlapping windows also straddle the original grid's boundaries.
    width = check
    starts = sorted(
        set(range(lo, hi - width + 1, max(1, width // 2))) | {max(lo, hi - width)}
    )
    for start in starts:
        stop = min(start + width, hi)
        source = raw[start:stop]
        target = normalized[start + lag : stop + lag]
        if not any(source) and not any(target):
            continue
        score = _pearson(source, target)
        if score is None or score < minimum:
            refuse(
                "local sample correlation failed "
                "(silence, mismatch or unsupported transform)"
            )
        # One changed sample of clock must not hide inside a broad peak.
        for neighbour in (lag - 1, lag + 1):
            if start + neighbour < 0 or stop + neighbour > len(normalized):
                continue
            other = _pearson(source, normalized[start + neighbour : stop + neighbour])
            if other is not None and score - other <= 0.000001:
                refuse("local sample lag is ambiguous or differs from global lag")
        correlations.append(score)
        windows += 1
    if windows < 3:
        refuse("insufficient independent audible sample windows")
    return Lag(
        lag,
        lag * 1000 / SAMPLE_RATE,
        min(correlations),
        round(lag * 1000 / SAMPLE_RATE),
        method="sample_correlation",
        uncertainty_samples=0,
        windows_verified=windows,
    )


def estimate_lag(
    raw_pcm: bytes,
    raw_rate: int,
    normalized: Sequence[int],
    parameters: Mapping[str, Any],
) -> Lag:
    """Lag (normalized minus raw), verified at the native rate.

    Same-rate 48 kHz PCM uses independent sample peaks and dense local checks.
    Other supported rates retain 5 ms RMS envelopes on a shared 1 ms grid,
    with a parabolic fit refining the lag below 1 ms.
    """

    if raw_rate == SAMPLE_RATE:
        if len(raw_pcm) % 2:
            raise MeasurementError(["raw provider PCM has incomplete samples"])
        return _sample_lag(_pcm_s16le(raw_pcm), normalized, parameters)

    window_ms = int(parameters["lagEnvelopeWindowMs"])
    hop_ms = int(parameters["lagEnvelopeHopMs"])
    search = int(parameters["lagSearchMs"]) // hop_ms
    raw_samples = _pcm_s16le(raw_pcm)
    if raw_rate <= 0 or (raw_rate % 1000 != 0 and raw_rate != 44_100):
        raise MeasurementError(
            [
                f"raw provider sample rate {raw_rate} is not supported for "
                "lag verification"
            ]
        )
    raw_env = _envelope(raw_samples, raw_rate, window_ms, hop_ms)
    norm_env = _envelope(normalized, SAMPLE_RATE, window_ms, hop_ms)
    if len(raw_env) < 4 or len(norm_env) < 4:
        raise MeasurementError(["audio too short to verify normalization timing"])
    if not any(raw_env):
        raise MeasurementError(["raw provider PCM has no audible support"])
    if not any(norm_env):
        raise MeasurementError(["normalized audio has no audible support"])

    def correlation_at(lag: int) -> float | None:
        # normalized[k] corresponds to raw[k - lag]
        lo = max(0, lag)
        hi = min(len(norm_env), len(raw_env) + lag)
        if hi - lo < 4:
            return None
        return _pearson(norm_env[lo:hi], raw_env[lo - lag : hi - lag])

    scores: dict[int, float] = {}
    for candidate in range(-search, search + 1):
        score = correlation_at(candidate)
        if score is not None:
            scores[candidate] = score
    if not scores:
        raise MeasurementError(
            ["normalization timing not verified: envelopes have no variation"]
        )
    best = max(scores, key=lambda item: (scores[item], -abs(item)))
    if abs(best) == search:
        raise MeasurementError(
            [
                "normalization timing not verified: best lag sits at the search "
                f"boundary ({best * hop_ms} ms)"
            ]
        )
    refined = float(best)
    if best - 1 in scores and best + 1 in scores:
        left, mid, right = scores[best - 1], scores[best], scores[best + 1]
        denominator = left - 2.0 * mid + right
        if denominator < 0.0:
            refined += max(-0.5, min(0.5, 0.5 * (left - right) / denominator))
    milliseconds = refined * hop_ms
    lag = Lag(
        samples=round(milliseconds * SAMPLE_RATE / 1000),
        milliseconds=milliseconds,
        correlation=scores[best],
        integer_ms=best * hop_ms,
    )
    if lag.correlation < int(parameters["minLagCorrelationPermille"]) / 1000:
        raise MeasurementError(
            [
                "normalization timing not verified: envelope correlation "
                f"{lag.correlation:.3f} is below "
                f"{int(parameters['minLagCorrelationPermille']) / 1000}"
            ]
        )
    if abs(lag.milliseconds) > float(parameters["lagToleranceMs"]):
        raise MeasurementError(
            [
                "normalization timing not verified: measured lag "
                f"{lag.milliseconds:.2f} ms exceeds {parameters['lagToleranceMs']} ms"
            ]
        )
    return lag


def _verify_normalization_transform(
    loaded: LoadedAsset,
    lag: Lag | None,
    parameters: Mapping[str, Any] = DEFAULT_PARAMETERS,
) -> Lag:
    """Require sample-identical output from the supported local transform.

    A correlation score cannot distinguish arbitrary short edits from gain
    changes. Reproduction qualifies the transform without trusting that score
    as proof of continuity. Only the already verified global offset is applied.
    """
    try:
        normalizer = Normalizer(profile_id=loaded.asset.normalization_profile)
        if normalizer.tool_fingerprint != loaded.asset.tool_fingerprint:
            raise MeasurementError(
                [
                    "normalization timing not verified: media tool changed since "
                    "normalization; re-normalize the cached PCM"
                ]
            )
        try:
            expected = normalizer.normalize_pcm(
                loaded.raw_pcm,
                sample_rate=SAMPLE_RATE,
                channels=1,
                **({"audit_clock": True} if lag is None else {}),
            )
        except ClockQualificationError:
            expected = normalizer.normalize_pcm(
                loaded.raw_pcm,
                sample_rate=SAMPLE_RATE,
                channels=1,
            )
    except MediaToolError as error:
        raise MeasurementError(
            [
                "normalization timing not verified: "
                "current transform cannot be reproduced"
            ]
        ) from error
    if lag is None:
        clock = getattr(expected, "clock", None)
        if clock is None:
            # Alternate normalizers still need the original independent lag
            # qualification as well as exact replay.
            samples, _rate, _channels, _frames = read_wav(loaded.wav_bytes)
            lag = estimate_lag(loaded.raw_pcm, SAMPLE_RATE, samples, parameters)
        else:
            identity = {
                "recordVersion": "normalization-key/v1",
                "rawAudioHash": loaded.asset.raw_audio_hash,
                "rawTimingHash": loaded.asset.raw_timing_hash,
                "profileId": loaded.asset.normalization_profile,
                "toolFingerprint": loaded.asset.tool_fingerprint,
                "normalizerVersion": NORMALIZER_VERSION,
            }
            if identity_hash(identity) != loaded.asset.normalization_hash:
                raise MeasurementError(
                    [
                        "normalization timing not verified: "
                        "normalization identity differs"
                    ]
                )
            lag = Lag(
                0,
                0.0,
                1.0,
                0,
                method="qualified_linear_transform",
                uncertainty_samples=0,
                windows_verified=clock["framesVerified"],
                clock=clock,
            )
    with (
        wave.open(io.BytesIO(expected.wav_bytes)) as source,
        wave.open(io.BytesIO(loaded.wav_bytes)) as target,
    ):
        source_format = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        target_format = (
            target.getnchannels(),
            target.getsampwidth(),
            target.getframerate(),
        )
        if source_format != target_format:
            raise MeasurementError(
                ["normalization timing not verified: unsupported PCM transformation"]
            )
        width = source.getsampwidth()
        source_frames, target_frames = source.getnframes(), target.getnframes()
        original = source.readframes(source_frames)
        observed = target.readframes(target_frames)
    lo = max(0, -lag.samples)
    hi = min(source_frames, target_frames - lag.samples)
    a, b = lo * width, hi * width
    x, y = (lo + lag.samples) * width, (hi + lag.samples) * width
    if (
        original[a:b] != observed[x:y]
        or any(original[:a])
        or any(original[b:])
        or any(observed[:x])
        or any(observed[y:])
    ):
        raise MeasurementError(
            [
                "normalization timing not verified: PCM differs from the reproduced "
                "normalization transform (local edits or unsupported transform)"
            ]
        )
    if lag.clock is not None:
        # This route proves the raw clock and replay clock separately. No
        # offset search or matching prefix/suffix may hide a delivered edit.
        if source_frames != target_frames or original != observed:
            raise MeasurementError(
                ["normalization timing not verified: PCM differs from exact replay"]
            )
        padding = lag.clock["tailPaddingSamples"]
        if padding and any(observed[-padding * width :]):
            raise MeasurementError(
                ["normalization timing not verified: non-silent tail padding"]
            )
    return lag


# ------------------------------------------------------------------- end rule


def window_levels_db(
    prefix: Sequence[float], start: int, stop: int, window: int
) -> list[float]:
    """RMS level (dBFS) of consecutive full windows inside [start, stop)."""

    count = (stop - start) // window
    levels: list[float] = []
    for k in range(count):
        a = start + k * window
        mean_square = (prefix[a + window] - prefix[a]) / window
        if mean_square <= 0.0:
            levels.append(_FLOOR_DB)
        else:
            levels.append(max(_FLOOR_DB, 10.0 * math.log10(mean_square / 32768.0**2)))
    return levels


def decide_audible_end(
    levels: Sequence[float],
    *,
    relative_drop_db: float,
    quiet_dbfs: float,
    quiet_windows: int,
) -> EndDecision:
    """Apply the energy rule to one word span's raw-PCM window levels.

    A window is *quiet* when its level is at or below the absolute
    ``quiet_dbfs`` threshold and also at least ``relative_drop_db`` below the
    word's peak window.  The audible end is the end of the last non-quiet
    window, provided the quiet windows after it run unbroken to the end of the
    span and number at least ``quiet_windows``.
    """

    count = len(levels)
    if count == 0:
        return EndDecision(None, "span shorter than one window", 0, None, None, None, 0)
    peak = max(levels)
    threshold = min(quiet_dbfs, peak - relative_drop_db)
    quiet_after = 0
    for level in reversed(levels):
        if level > threshold:
            break
        quiet_after += 1
    last = count - 1 - quiet_after
    if quiet_after < quiet_windows:
        return EndDecision(
            None,
            f"connected speech: {quiet_after} quiet windows follow, "
            f"{quiet_windows} required",
            count,
            peak,
            threshold,
            last,
            quiet_after,
        )
    return EndDecision(
        last + 1, "measured quiet gap", count, peak, threshold, last, quiet_after
    )


# ------------------------------------------------------------------- loading


def _bare(value: str) -> str:
    return value.removeprefix("sha256:")


def load_asset(cache: NarrationCache, asset_key: str) -> LoadedAsset:
    """Load an asset (``<block-id>/<asset-id>``) with its raw provider PCM."""

    try:
        entry = cache.read("assets", asset_key, "asset.json")
    except CacheError as error:
        raise MeasurementError([f"asset cache entry unusable: {error}"]) from error
    if entry is None:
        raise MeasurementError([f"asset not found in cache: {asset_key}"])
    stored = entry.metadata.get("asset")
    if not isinstance(stored, dict):
        raise MeasurementError(["asset record is missing"])
    stored = dict(stored)
    stored["request_ids"] = tuple(stored.get("request_ids", ()))
    try:
        asset = NarrationAudioAsset(**stored)
    except TypeError as error:
        raise MeasurementError([f"asset record is malformed: {error}"]) from error
    if asset.status != "ready" or asset.raw_audio_hash is None:
        raise MeasurementError(["asset is not a ready synthesized asset"])
    wav_bytes = entry.files.get("narration.wav", b"")
    timing_bytes = entry.files.get("timing.json", b"")
    try:
        synthesis = cache.read("synthesis", _bare(asset.request_hash), "synthesis.json")
    except CacheError as error:
        raise MeasurementError([f"synthesis cache entry unusable: {error}"]) from error
    if synthesis is None:
        raise MeasurementError(
            ["raw provider audio is missing from the synthesis cache"]
        )
    metadata = synthesis.metadata
    if (
        metadata.get("audioFormat") != "pcm_s16le"
        or int(metadata.get("channels", 0)) != 1
    ):
        raise MeasurementError(["raw provider audio must be mono pcm_s16le"])
    return LoadedAsset(
        asset=asset,
        wav_bytes=wav_bytes,
        timing_bytes=timing_bytes,
        raw_pcm=synthesis.files.get("provider-audio.pcm", b""),
        raw_sample_rate=int(metadata["sampleRate"]),
    )


def _utf16_slice(text: str, start: int, end: int) -> str | None:
    data = text.encode("utf-16-le")
    if not 0 <= start < end <= len(data) // 2:
        return None
    try:
        return data[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None


def _frozen_tokens(
    block: Mapping[str, Any], reasons: list[str]
) -> list[dict[str, Any]]:
    tokens = block.get("tokens")
    text = block.get("text")
    if not isinstance(text, str) or not isinstance(tokens, list) or not tokens:
        reasons.append("frozen narration block needs text and tokens")
        return []
    if any(
        isinstance(token, Mapping) and token.get("spoken") is False for token in tokens
    ):
        try:
            mask_stage_directions(block)
        except ValueError as error:
            reasons.append(str(error))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_end = 0
    for token in tokens:
        if not isinstance(token, Mapping):
            reasons.append("frozen token is not an object")
            continue
        token_id = token.get("id")
        start = token.get("startOffset")
        end = token.get("endOffset")
        value = token.get("value")
        if not isinstance(token_id, str) or token_id in seen:
            reasons.append(f"frozen token id invalid or duplicated: {token_id!r}")
            continue
        seen.add(token_id)
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not isinstance(value, str)
            or start < previous_end
            or _utf16_slice(text, start, end) != value
        ):
            reasons.append(f"frozen token {token_id} range/text is inconsistent")
            continue
        previous_end = end
        if token.get("spoken") is False:
            continue
        rows.append(
            {"id": token_id, "startOffset": start, "endOffset": end, "value": value}
        )
    if not rows and not reasons:
        reasons.append("direction-only narration has no spoken tokens to measure")
    return rows


def _check_bindings(
    loaded: LoadedAsset, block: Mapping[str, Any], reasons: list[str]
) -> None:
    asset = loaded.asset
    if sha256_bytes(loaded.wav_bytes) != asset.normalized_audio_hash:
        reasons.append("stale or wrong audio: normalized audio hash differs from asset")
    if sha256_bytes(loaded.timing_bytes) != asset.raw_timing_hash:
        reasons.append("stale or wrong timing: timing hash differs from asset")
    if sha256_bytes(loaded.raw_pcm) != asset.raw_audio_hash:
        reasons.append("stale or wrong audio: raw provider PCM hash differs from asset")
    text = block.get("text")
    if (
        not isinstance(text, str)
        or sha256_bytes(text.encode("utf-8")) != asset.text_hash
    ):
        reasons.append("text mismatch: frozen block text hash differs from asset")
    if (
        block.get("id") != asset.block_id
        or block.get("version") != asset.block_revision
    ):
        reasons.append("frozen block id/revision differs from asset")


def _word_marks(
    timing_bytes: bytes, reasons: list[str]
) -> tuple[str, list[dict[str, Any]]]:
    try:
        timing = json.loads(timing_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        reasons.append("timing JSON is unreadable")
        return "", []
    if not isinstance(timing, dict) or not isinstance(timing.get("marks"), list):
        reasons.append("timing JSON has no marks")
        return "", []
    marks = [
        mark
        for mark in timing["marks"]
        if isinstance(mark, dict) and mark.get("kind") == "word"
    ]
    return str(timing.get("recordVersion", "")), marks


# --------------------------------------------------------------- measurement


def measure_asset(
    loaded: LoadedAsset,
    frozen_block: Mapping[str, Any],
    *,
    artifact_locator: str,
    parameters: Mapping[str, Any] | None = None,
) -> MeasurementResult:
    """Measure a loaded asset against its frozen v2 block, or raise refusals."""

    params = dict(DEFAULT_PARAMETERS)
    if parameters:
        params.update(parameters)
    asset = loaded.asset
    reasons: list[str] = []
    _check_bindings(loaded, frozen_block, reasons)
    tokens = _frozen_tokens(frozen_block, reasons)
    record_version, marks = _word_marks(loaded.timing_bytes, reasons)

    by_range: dict[tuple[int, int], dict[str, Any]] = {}
    mark_times: dict[tuple[int, int], Fraction] = {}
    for mark in marks:
        key = (mark.get("start_utf16"), mark.get("end_utf16"))
        time_ms = mark.get("time_ms")
        if (
            not isinstance(key[0], int)
            or not isinstance(key[1], int)
            or not isinstance(time_ms, int)
            or time_ms < 0
        ):
            reasons.append("provider word mark is malformed")
            continue
        native_sample = mark.get("time_sample")
        if native_sample is not None:
            native_rate = mark.get("sample_rate")
            if (
                not isinstance(native_sample, int)
                or native_sample < 0
                or not isinstance(native_rate, int)
                or native_rate <= 0
            ):
                reasons.append("provider word mark native sample timing is malformed")
                continue
            if native_rate != loaded.raw_sample_rate:
                reasons.append(
                    "provider word mark sample rate differs from raw PCM sample rate"
                )
                continue
            mark_time = Fraction(native_sample, native_rate)
            if round(mark_time * 1000) != time_ms:
                reasons.append(
                    "provider word mark native sample differs from milliseconds"
                )
                continue
        else:
            mark_time = Fraction(time_ms, 1000)
        if key in by_range:
            reasons.append(f"duplicate provider word mark for range {key}")
            continue
        valid_key = cast(tuple[int, int], key)
        by_range[valid_key] = mark
        mark_times[valid_key] = mark_time
    if tokens and not reasons:
        token_ranges = {(t["startOffset"], t["endOffset"]) for t in tokens}
        for token in tokens:
            if (token["startOffset"], token["endOffset"]) not in by_range:
                reasons.append(f"no provider word mark for token {token['id']}")
        for key in by_range:
            if key not in token_ranges:
                reasons.append(f"provider word mark {key} maps to no frozen token")
    if len(by_range) != len(marks) and not reasons:  # pragma: no cover
        reasons.append("ambiguous token mapping")

    samples, rate, channels, frames = read_wav(loaded.wav_bytes)
    if rate != SAMPLE_RATE or channels != 1:
        reasons.append("normalized audio must be 48 kHz mono")
    if (
        frames != asset.duration_samples
        or rate != asset.sample_rate
        or channels != asset.channels
    ):
        reasons.append("normalized audio format/duration differs from asset record")
    if reasons:
        raise MeasurementError(reasons)

    ordered: list[tuple[dict[str, Any], dict[str, Any]]] = [
        (token, by_range[(token["startOffset"], token["endOffset"])])
        for token in tokens
    ]
    previous = Fraction(-1)
    for token, _mark in ordered:
        key = (token["startOffset"], token["endOffset"])
        if mark_times[key] <= previous:
            reasons.append(f"provider word marks out of order at token {token['id']}")
        previous = mark_times[key]
    if reasons:
        raise MeasurementError(reasons)

    if loaded.raw_sample_rate == SAMPLE_RATE:
        lag = _verify_normalization_transform(loaded, None, params)
    else:
        lag = estimate_lag(loaded.raw_pcm, loaded.raw_sample_rate, samples, params)

    raw_rate = loaded.raw_sample_rate
    if raw_rate <= 0 or (
        raw_rate != 44_100 and (SAMPLE_RATE % raw_rate != 0 or raw_rate % 1000 != 0)
    ):
        raise MeasurementError(
            [f"raw provider sample rate {raw_rate} does not map onto 48 kHz"]
        )
    raw_samples = _pcm_s16le(loaded.raw_pcm)
    raw_frames = len(raw_samples)

    onsets: list[int] = []
    raw_starts: list[int] = []
    for index, (_token, mark) in enumerate(ordered):
        if mark.get("time_sample") is not None:
            onset = mark["time_sample"] * SAMPLE_RATE // mark["sample_rate"]
            raw_start = mark["time_sample"]
        else:
            onset = mark["time_ms"] * SAMPLE_RATE // 1000
            raw_start = mark["time_ms"] * raw_rate // 1000
        onset += lag.samples
        if onset < 0:
            # Refuse rather than silently clamp: a clamped onset is not measured.
            reasons.append(
                f"onset of token {ordered[index][0]['id']} would be negative "
                f"({onset} samples) after lag correction"
            )
        onsets.append(onset)
        raw_starts.append(raw_start)
    for index, onset in enumerate(onsets):
        if onset >= frames or raw_starts[index] >= raw_frames:
            reasons.append(
                f"onset of token {ordered[index][0]['id']} is beyond the audio"
            )
        if index and onset <= onsets[index - 1]:
            reasons.append(
                f"onsets of tokens {ordered[index - 1][0]['id']} and "
                f"{ordered[index][0]['id']} collapse after lag correction"
            )
    if reasons:
        raise MeasurementError(reasons)

    # Ends are measured on the raw provider PCM, then mapped through the lag.
    window = int(params["endWindowMs"]) * raw_rate // 1000
    quiet_windows = -(-int(params["endQuietRunMs"]) // int(params["endWindowMs"]))
    prefix = _prefix_square_sums(raw_samples)

    token_rows: list[dict[str, Any]] = []
    evidence_tokens: list[dict[str, Any]] = []
    for index, (token, mark) in enumerate(ordered):
        span_start = onsets[index]
        span_stop = onsets[index + 1] if index + 1 < len(onsets) else frames
        raw_start = raw_starts[index]
        raw_stop = raw_starts[index + 1] if index + 1 < len(onsets) else raw_frames
        levels = window_levels_db(prefix, raw_start, raw_stop, window)
        decision = decide_audible_end(
            levels,
            relative_drop_db=float(params["endRelativeDropDb"]),
            quiet_dbfs=float(params["endQuietDbfs"]),
            quiet_windows=quiet_windows,
        )
        end_sample = None
        if decision.end_sample is not None:
            raw_end = raw_start + decision.end_sample * window
            end_sample = raw_end * SAMPLE_RATE // raw_rate + lag.samples
        token_rows.append(
            {
                "tokenId": token["id"],
                "quotedText": token["value"],
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
                "providerMarkMs": mark["time_ms"],
                "onsetSamples": span_start,
                "spanEndSamples": span_stop,
                "rawSpanStartSamples": raw_start,
                "rawSpanStopSamples": raw_stop,
                "endMeasuredOn": "raw_provider_pcm",
                "rowFinal": index + 1 == len(ordered),
                "windowCount": decision.window_count,
                "peakDb": _round(decision.peak_db),
                "thresholdDb": _round(decision.threshold_db),
                "lastLoudWindow": decision.last_loud_window,
                "quietWindowsAfter": decision.quiet_windows_after,
                "audibleEndSamples": end_sample,
                "endDecision": "measured" if end_sample is not None else "absent",
                "endReason": decision.reason,
                "windowLevelsDb": [round(level, 2) for level in levels],
            }
        )
        evidence_token: dict[str, Any] = {
            "tokenId": token["id"],
            "startOffset": token["startOffset"],
            "endOffset": token["endOffset"],
            "quotedText": token["value"],
            "onset": rational(span_start),
        }
        if end_sample is not None:
            evidence_token["audibleEnd"] = rational(end_sample)
        evidence_tokens.append(evidence_token)

    narration_asset_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, _ASSET_ID_PREFIX + asset.asset_id)
    )
    algorithm = {
        "id": ALGORITHM_ID,
        "version": ALGORITHM_VERSION,
        "parametersHash": parameters_hash(params),
        "parameters": params,
    }
    artifact: dict[str, Any] = {
        "schemaVersion": ARTIFACT_VERSION,
        "algorithm": algorithm,
        "asset": {
            "cacheAssetId": asset.asset_id,
            "narrationAssetId": narration_asset_id,
            "blockId": asset.block_id,
            "blockRevision": asset.block_revision,
            "textHash": asset.text_hash,
            "audioHash": asset.normalized_audio_hash,
            "rawAudioHash": asset.raw_audio_hash,
            "timingHash": asset.raw_timing_hash,
            "requestHash": asset.request_hash,
            "requestIds": list(asset.request_ids),
            "voiceId": asset.voice_id,
            "model": asset.model,
            "durationSamples": asset.duration_samples,
            "sampleRate": asset.sample_rate,
            "channels": asset.channels,
            "toolFingerprint": asset.tool_fingerprint,
            "normalizationProfile": asset.normalization_profile,
            "normalizationHash": asset.normalization_hash,
        },
        "lag": {
            "rawSampleRate": loaded.raw_sample_rate,
            "method": lag.method,
            "uncertaintySamples": lag.uncertainty_samples,
            "windowsVerified": lag.windows_verified,
            "transformVerification": (
                {
                    "method": "reproduced_pcm",
                    "normalizerVersion": NORMALIZER_VERSION,
                    "toolFingerprint": asset.tool_fingerprint,
                    **({"clock": dict(lag.clock)} if lag.clock is not None else {}),
                }
                if loaded.raw_sample_rate == SAMPLE_RATE
                else {"method": "rms_envelope"}
            ),
            "samples": lag.samples,
            "milliseconds": round(lag.milliseconds, 4),
            "integerMilliseconds": lag.integer_ms,
            "correlation": None if lag.clock is not None else round(lag.correlation, 6),
            "toleranceMs": params["lagToleranceMs"],
            "verified": True,
        },
        "tokens": token_rows,
        "refusals": [],
    }
    artifact_bytes = canonical_json_bytes(artifact)
    evidence: dict[str, Any] = {
        "schemaVersion": EVIDENCE_VERSION,
        "blockId": asset.block_id,
        "blockRevision": asset.block_revision,
        "textHash": asset.text_hash,
        "tokenizationVersion": TOKENIZATION_VERSION,
        "narrationAssetId": narration_asset_id,
        "audioHash": asset.normalized_audio_hash,
        "timingHash": cast(str, asset.raw_timing_hash),
        "alignmentVersion": record_version,
        "audio": {
            "narrationAssetId": narration_asset_id,
            "audioHash": asset.normalized_audio_hash,
            "timingHash": cast(str, asset.raw_timing_hash),
            "cacheAssetId": asset.asset_id,
            "locator": asset.locators["audio"],
            "durationSamples": asset.duration_samples,
            "sampleRate": asset.sample_rate,
            "channels": asset.channels,
        },
        "tokens": evidence_tokens,
        "verification": {
            "method": METHOD,
            "algorithm": algorithm,
            "measurementArtifactLocator": artifact_locator,
            "measurementArtifactHash": sha256_bytes(artifact_bytes),
            "onsetBasis": ONSET_BASIS,
            "onsetUncertainty": _ms_rational(int(params["onsetUncertaintyMs"])),
            "audibleEndUncertainty": _ms_rational(
                int(params["audibleEndUncertaintyMs"])
            ),
        },
    }
    _self_check(evidence)
    return MeasurementResult(artifact, artifact_bytes, evidence)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _self_check(evidence: Mapping[str, Any]) -> None:
    """Mirror the consumer's ordering rules so we never emit evidence it refuses."""

    audio = evidence["audio"]
    if not evidence["tokens"]:
        raise MeasurementError(
            ["measured narration evidence needs at least one spoken token"]
        )
    duration = Fraction(audio["durationSamples"], audio["sampleRate"])
    prior_onset: Fraction | None = None
    prior_end: Fraction | None = None
    problems: list[str] = []
    for token in evidence["tokens"]:
        onset = _fraction(token["onset"])
        end = _fraction(token["audibleEnd"]) if "audibleEnd" in token else None
        if (
            onset >= duration
            or (prior_onset is not None and onset <= prior_onset)
            or (prior_end is not None and prior_end > onset)
        ):
            problems.append(f"onset of {token['tokenId']} violates ordering")
        if end is not None and (
            end == 0
            or end > duration
            or (prior_end is not None and end <= prior_end)
            or onset >= end
        ):
            problems.append(f"audible end of {token['tokenId']} violates ordering")
        prior_onset = onset
        if end is not None:
            prior_end = end
    if problems:
        raise MeasurementError(problems)


def _fraction(value: Mapping[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])
