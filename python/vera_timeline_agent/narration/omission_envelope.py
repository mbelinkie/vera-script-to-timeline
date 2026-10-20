"""Frame-snapped safe-edit envelopes around one word of measured evidence (#182).

For a selected token the cut may start anywhere between the previous word's
audible end and the selected onset, and may end anywhere between the selected
audible end and the next word's onset.  Each bound moves inward by the declared
uncertainty.  The target is *uniquely safe* only when a whole frame boundary of
the 23.976 grid lies inside both envelopes; otherwise the report refuses and
says why.  Frame boundaries are relative to the start of the narration row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

from vera_timeline_agent.narration.measure import parameters_hash
from vera_timeline_agent.narration.models import sha256_bytes

SAMPLE_RATE = 48_000
FRAME_SAMPLES = 2002  # 1001/24000 s at 48 kHz: one 23.976 fps frame
MEASURED_METHOD = "measured_audio_boundaries/v1"


class EnvelopeRefused(ValueError):
    """The target has no uniquely safe frame-snapped envelope."""


def _samples(value: Mapping[str, int], rate: int) -> Fraction:
    return Fraction(value["numerator"], value["denominator"]) * rate


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def _frame_view(low: Fraction, high: Fraction) -> dict[str, Any]:
    first = _ceil(low / FRAME_SAMPLES)
    last = _floor(high / FRAME_SAMPLES)
    return {
        "firstFrame": first,
        "lastFrame": last,
        "frameCount": max(0, last - first + 1),
        "firstBoundarySamples": first * FRAME_SAMPLES,
        "lastBoundarySamples": last * FRAME_SAMPLES,
    }


def _envelope(
    name: str,
    low: Fraction,
    high: Fraction,
    *,
    low_basis: str,
    high_basis: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "rawLowSamples": _floor(low) if low.denominator == 1 else str(low),
        "rawHighSamples": _floor(high) if high.denominator == 1 else str(high),
        "lowBasis": low_basis,
        "highBasis": high_basis,
    }
    return result


def verify_evidence_binding(
    evidence: Mapping[str, Any], block: Mapping[str, Any]
) -> None:
    """Refuse unless the evidence covers exactly the frozen block's tokens.

    The neighbours of a selected token are only trustworthy when the evidence
    lists every frozen token in order with no gap, so the whole token list is
    compared, not just the selected token.
    """

    verification = evidence.get("verification")
    if (
        not isinstance(verification, Mapping)
        or verification.get("method") != MEASURED_METHOD
    ):
        raise EnvelopeRefused(
            "envelope requires measured evidence; reviewed or derived timing "
            "is not relabelled"
        )
    algorithm = verification.get("algorithm")
    if not isinstance(algorithm, Mapping) or not isinstance(
        algorithm.get("parameters"), Mapping
    ):
        raise EnvelopeRefused("measured evidence has no algorithm parameters")
    try:
        expected_hash = parameters_hash(algorithm["parameters"])
    except ValueError as error:
        raise EnvelopeRefused(
            f"algorithm.parameters are not hashable: {error}"
        ) from error
    if algorithm.get("parametersHash") != expected_hash:
        raise EnvelopeRefused(
            "algorithm.parametersHash is not the canonical hash of its parameters"
        )
    if evidence.get("blockId") != block.get("id") or evidence.get(
        "blockRevision"
    ) != block.get("version"):
        raise EnvelopeRefused("evidence block id/revision differs from the block")
    text = block.get("text")
    if not isinstance(text, str) or evidence.get("textHash") != sha256_bytes(
        text.encode("utf-8")
    ):
        raise EnvelopeRefused("evidence textHash differs from the block text")
    frozen = block.get("tokens")
    measured = evidence.get("tokens")
    if not isinstance(frozen, list) or not isinstance(measured, list):
        raise EnvelopeRefused("block or evidence has no token list")
    if len(frozen) != len(measured):
        raise EnvelopeRefused(
            f"evidence covers {len(measured)} tokens but the block has "
            f"{len(frozen)}; every frozen token must be present with no gap"
        )
    for position, (token, row) in enumerate(zip(frozen, measured, strict=True)):
        if not isinstance(token, Mapping) or not isinstance(row, Mapping):
            raise EnvelopeRefused(f"token {position} is malformed")
        if (
            row.get("tokenId") != token.get("id")
            or row.get("startOffset") != token.get("startOffset")
            or row.get("endOffset") != token.get("endOffset")
            or row.get("quotedText") != token.get("value")
        ):
            raise EnvelopeRefused(
                f"evidence token {position} ({row.get('tokenId')!r}) is not the "
                f"block's token {token.get('id')!r} at that position"
            )


def omission_envelope(
    evidence: Mapping[str, Any], token_id: str, block: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the report for ``token_id``; raise ``EnvelopeRefused`` if unsafe."""

    report = omission_envelope_report(evidence, token_id, block)
    if not report["uniquelySafe"]:
        raise EnvelopeRefused("; ".join(report["refusalReasons"]))
    return report


def omission_envelope_report(
    evidence: Mapping[str, Any], token_id: str, block: Mapping[str, Any]
) -> dict[str, Any]:
    """Full report, including the refusal reasons when the target is not safe.

    ``block`` is the frozen v2 narration block the evidence was measured for.
    """

    verify_evidence_binding(evidence, block)
    verification = evidence["verification"]
    audio = evidence["audio"]
    rate = int(audio["sampleRate"])
    duration = Fraction(int(audio["durationSamples"]))
    onset_unc = _samples(verification["onsetUncertainty"], rate)
    end_unc = _samples(verification["audibleEndUncertainty"], rate)
    tokens: Sequence[Mapping[str, Any]] = evidence["tokens"]
    ids = [token["tokenId"] for token in tokens]
    if token_id not in ids:
        raise EnvelopeRefused(f"token {token_id} is not in the measured evidence")
    index = ids.index(token_id)
    selected = tokens[index]
    left = tokens[index - 1] if index > 0 else None
    right = tokens[index + 1] if index + 1 < len(tokens) else None
    reasons: list[str] = []

    if "onset" not in selected:
        raise EnvelopeRefused("selected token has no measured onset")
    onset = _samples(selected["onset"], rate)

    # Cut-start envelope: previous audible end -> selected onset.
    if left is None:
        start_low, start_low_basis = Fraction(0), "row_start"
    elif "audibleEnd" in left:
        start_low = _samples(left["audibleEnd"], rate) + end_unc
        start_low_basis = "left_audible_end_plus_uncertainty"
    else:
        reasons.append(
            f"left neighbour {left['quotedText']!r} has no measured audible end "
            "(connected speech)"
        )
        start_low, start_low_basis = Fraction(0), "missing"
    start_high = onset - onset_unc

    # Cut-end envelope: selected audible end -> next onset.
    if "audibleEnd" in selected:
        end_low = _samples(selected["audibleEnd"], rate) + end_unc
        end_low_basis = "selected_audible_end_plus_uncertainty"
    else:
        reasons.append(
            f"selected token {selected['quotedText']!r} has no measured audible end"
        )
        end_low, end_low_basis = Fraction(0), "missing"
    if right is None:
        end_high, end_high_basis = duration, "row_end"
    elif "onset" in right:
        end_high = _samples(right["onset"], rate) - onset_unc
        end_high_basis = "right_onset_minus_uncertainty"
    else:
        reasons.append(f"right neighbour {right['quotedText']!r} has no onset")
        end_high, end_high_basis = Fraction(0), "missing"

    start_env = _envelope(
        "cutStart",
        start_low,
        start_high,
        low_basis=start_low_basis,
        high_basis="selected_onset_minus_uncertainty",
    )
    end_env = _envelope(
        "cutEnd",
        end_low,
        end_high,
        low_basis=end_low_basis,
        high_basis=end_high_basis,
    )
    if not reasons:
        for env, low, high in (
            (start_env, start_low, start_high),
            (end_env, end_low, end_high),
        ):
            if high <= low:
                reasons.append(
                    f"{env['name']} envelope collapses under the declared "
                    f"uncertainty ({_floor(low)}..{_floor(high)} samples)"
                )
            else:
                env.update(_frame_view(low, high))
                if env["frameCount"] < 1:
                    reasons.append(
                        f"{env['name']} envelope contains no 23.976 frame boundary"
                    )
    report: dict[str, Any] = {
        "schemaVersion": "narration-omission-envelope/v1",
        "tokenId": token_id,
        "quotedText": selected["quotedText"],
        "leftNeighbour": left["quotedText"] if left else None,
        "rightNeighbour": right["quotedText"] if right else None,
        "sampleRate": rate,
        "frameSamples": FRAME_SAMPLES,
        "frameRate": "24000/1001",
        "frameOrigin": "narration row start",
        "onsetUncertaintySamples": _floor(onset_unc),
        "audibleEndUncertaintySamples": _floor(end_unc),
        "cutStart": start_env,
        "cutEnd": end_env,
        "uniquelySafe": not reasons,
        "refusalReasons": reasons,
    }
    return report
