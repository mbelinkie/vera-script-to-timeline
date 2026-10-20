from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from issue182_fixture import (
    BLOCK_ID,
    MARK_MS,
    TEXT,
    TOKEN_IDS,
    build_cache,
    frozen_block,
    timing_bytes,
    wav_bytes,
    wav_samples,
)
from vera_timeline_agent.narration.measure import (
    DEFAULT_PARAMETERS,
    MeasurementError,
    decide_audible_end,
    load_asset,
    measure_asset,
    parameters_hash,
)
from vera_timeline_agent.narration.models import sha256_bytes

LOCATOR = "narration-measurements/x.measurement.json"
QUIET = 6


def measured(tmp_path: Path, **kwargs: Any) -> Any:
    cache, _asset, key = build_cache(tmp_path / "cache", **kwargs)
    return measure_asset(
        load_asset(cache, key), frozen_block(), artifact_locator=LOCATOR
    )


def test_pauses_connected_speech_and_row_final(tmp_path: Path) -> None:
    result = measured(tmp_path)
    rows = {row["quotedText"]: row for row in result.artifact["tokens"]}
    # Onsets are provider marks (no lag here) at 48 kHz samples.
    for word, mark in zip(("alpha", "beta", "gamma", "delta"), MARK_MS, strict=True):
        assert abs(rows[word]["onsetSamples"] - mark * 48) <= 12
    # Pause after alpha: end is the 300 ms burst length after its onset.
    assert (
        rows["alpha"]["audibleEndSamples"] == rows["alpha"]["onsetSamples"] + 300 * 48
    )
    assert rows["alpha"]["endDecision"] == "measured"
    # beta runs straight into gamma: onset only, end absent (fail closed).
    assert rows["beta"]["audibleEndSamples"] is None
    assert rows["beta"]["endDecision"] == "absent"
    assert "connected speech" in rows["beta"]["endReason"]
    assert (
        rows["gamma"]["audibleEndSamples"] == rows["gamma"]["onsetSamples"] + 300 * 48
    )
    # Row-final word is measured against the end of the audio.
    delta = rows["delta"]
    assert delta["rowFinal"] is True
    assert delta["audibleEndSamples"] == delta["onsetSamples"] + 250 * 48

    evidence_tokens = {t["quotedText"]: t for t in result.evidence["tokens"]}
    assert "audibleEnd" not in evidence_tokens["beta"]
    assert all("onset" in t for t in result.evidence["tokens"])


def test_evidence_json_has_the_spec_shape(tmp_path: Path) -> None:
    result = measured(tmp_path)
    evidence = result.evidence
    assert evidence["schemaVersion"] == "narration-boundary-evidence/v1"
    assert evidence["tokenizationVersion"] == "script-document/v2-frozen-tokens"
    assert evidence["blockId"] == BLOCK_ID
    assert evidence["textHash"] == sha256_bytes(TEXT.encode())
    assert set(evidence) == {
        "schemaVersion",
        "blockId",
        "blockRevision",
        "textHash",
        "tokenizationVersion",
        "narrationAssetId",
        "audioHash",
        "timingHash",
        "alignmentVersion",
        "audio",
        "tokens",
        "verification",
    }
    assert set(evidence["audio"]) == {
        "narrationAssetId",
        "audioHash",
        "timingHash",
        "cacheAssetId",
        "locator",
        "durationSamples",
        "sampleRate",
        "channels",
    }
    verification = evidence["verification"]
    assert set(verification) == {
        "method",
        "algorithm",
        "measurementArtifactLocator",
        "measurementArtifactHash",
        "onsetBasis",
        "onsetUncertainty",
        "audibleEndUncertainty",
    }
    assert verification["method"] == "measured_audio_boundaries/v1"
    assert verification["onsetBasis"] == "provider_word_marks_lag_verified"
    assert verification["onsetUncertainty"] == {"numerator": 1, "denominator": 40}
    assert verification["audibleEndUncertainty"] == {"numerator": 3, "denominator": 100}
    algorithm = verification["algorithm"]
    assert algorithm["id"] == "vera-polly-marks-energy-ends"
    assert algorithm["version"] == "1"
    assert algorithm["parameters"] == DEFAULT_PARAMETERS
    assert algorithm["parametersHash"] == parameters_hash(DEFAULT_PARAMETERS)
    assert verification["measurementArtifactLocator"] == LOCATOR
    assert verification["measurementArtifactHash"] == sha256_bytes(
        result.artifact_bytes
    )
    for token, frozen in zip(evidence["tokens"], frozen_block()["tokens"], strict=True):
        assert token["tokenId"] == frozen["id"]
        assert token["quotedText"] == frozen["value"]
        for key in ("onset", "audibleEnd"):
            if key in token:
                value = Fraction(token[key]["numerator"], token[key]["denominator"])
                assert value.denominator == token[key]["denominator"]  # reduced


@pytest.mark.parametrize("lag", [-48, 0, 48, 96])
def test_lag_is_found_and_applied_to_onsets(tmp_path: Path, lag: int) -> None:
    result = measured(tmp_path, lag_samples=lag)
    found = result.artifact["lag"]["samples"]
    assert abs(found - lag) <= 12  # quarter millisecond
    first = result.artifact["tokens"][1]
    assert first["onsetSamples"] == MARK_MS[1] * 48 + found


def test_lag_beyond_two_milliseconds_is_refused(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache", lag_samples=240)  # 5 ms
    with pytest.raises(MeasurementError) as caught:
        measure_asset(load_asset(cache, key), frozen_block(), artifact_locator=LOCATOR)
    assert "normalization timing not verified" in str(caught.value)


def test_stale_or_wrong_audio_and_timing_are_refused(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    loaded = load_asset(cache, key)
    wrong_wav = wav_bytes([0] * len(wav_samples(loaded.wav_bytes)))
    with pytest.raises(MeasurementError) as audio:
        measure_asset(
            replace(loaded, wav_bytes=wrong_wav),
            frozen_block(),
            artifact_locator=LOCATOR,
        )
    assert "normalized audio hash differs" in str(audio.value)
    with pytest.raises(MeasurementError) as timing:
        measure_asset(
            replace(loaded, timing_bytes=timing_bytes((101, 520, 820, 1270))),
            frozen_block(),
            artifact_locator=LOCATOR,
        )
    assert "timing hash differs" in str(timing.value)
    with pytest.raises(MeasurementError) as raw:
        measure_asset(
            replace(loaded, raw_pcm=loaded.raw_pcm[:-2] + b"\x01\x00"),
            frozen_block(),
            artifact_locator=LOCATOR,
        )
    assert "raw provider PCM hash differs" in str(raw.value)


def test_all_refusals_are_listed_together(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    loaded = replace(
        load_asset(cache, key),
        wav_bytes=wav_bytes([1] * 100),
        timing_bytes=b"{}",
    )
    with pytest.raises(MeasurementError) as caught:
        measure_asset(loaded, frozen_block(), artifact_locator=LOCATOR)
    assert len(caught.value.reasons) >= 2


def test_text_and_token_mark_mismatches_are_refused(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    loaded = load_asset(cache, key)
    changed_text = frozen_block("alpha beta gamma omega")
    with pytest.raises(MeasurementError) as text:
        measure_asset(loaded, changed_text, artifact_locator=LOCATOR)
    assert any("text" in reason for reason in text.value.reasons)

    shifted = frozen_block()
    shifted["tokens"][1]["startOffset"] = 7  # token no longer matches its mark
    with pytest.raises(MeasurementError) as mapping:
        measure_asset(loaded, shifted, artifact_locator=LOCATOR)
    assert mapping.value.reasons

    short = frozen_block()
    short["tokens"] = short["tokens"][:3]  # mark maps to no frozen token
    with pytest.raises(MeasurementError) as extra:
        measure_asset(loaded, short, artifact_locator=LOCATOR)
    assert any("maps to no frozen token" in r for r in extra.value.reasons)

    wrong_revision = frozen_block()
    wrong_revision["version"] = 2
    with pytest.raises(MeasurementError):
        measure_asset(loaded, wrong_revision, artifact_locator=LOCATOR)


def test_duplicate_and_out_of_order_marks_are_refused(tmp_path: Path) -> None:
    for marks in ((100, 100, 820, 1270), (100, 820, 520, 1270)):
        cache, _asset, key = build_cache(tmp_path / f"c{marks[1]}", mark_ms=marks)
        with pytest.raises(MeasurementError) as caught:
            measure_asset(
                load_asset(cache, key), frozen_block(), artifact_locator=LOCATOR
            )
        assert "out of order" in str(caught.value)


def test_missing_raw_audio_is_refused(tmp_path: Path) -> None:
    from vera_timeline_agent.narration.cache import NarrationCache

    _cache, asset, _key = build_cache(tmp_path / "a")
    other = NarrationCache(tmp_path / "empty")
    other.publish(
        "assets",
        f"{BLOCK_ID}/{asset.asset_id}",
        {"narration.wav": b"x", "timing.json": b"y"},
        "asset.json",
        {"recordVersion": "asset-cache/v1", "asset": asset.as_json()},
    )
    with pytest.raises(MeasurementError) as caught:
        load_asset(other, f"{BLOCK_ID}/{asset.asset_id}")
    assert "synthesis cache" in str(caught.value)


def _levels(peak: float, tail: list[float]) -> list[float]:
    return [peak, peak, *tail]


def test_threshold_edges() -> None:
    def decide(levels: list[float]) -> Any:
        return decide_audible_end(
            levels, relative_drop_db=18, quiet_dbfs=-50, quiet_windows=QUIET
        )

    # Exactly six quiet windows run to the end of the span: end is measured.
    ok = decide(_levels(-20.0, [-60.0] * 6))
    assert ok.end_sample == 2 and ok.quiet_windows_after == 6
    # Five quiet windows is connected speech: no end.
    assert decide(_levels(-20.0, [-60.0] * 5)).end_sample is None
    # A window exactly at the quiet threshold (-50) is quiet.
    edge = decide(_levels(-20.0, [-50.0, *[-60.0] * 5]))
    assert edge.end_sample == 2 and edge.threshold_db == -50.0
    # Just above the quiet threshold is audible.
    above = decide(_levels(-20.0, [-49.99, *[-60.0] * 6]))
    assert above.end_sample == 3
    # The relative drop is an additional requirement: for a quiet peak (-55)
    # the threshold is peak - 18 = -73, so -60 tails are NOT quiet.
    assert decide(_levels(-55.0, [-60.0] * 8)).end_sample is None
    assert decide(_levels(-55.0, [-80.0] * 6)).end_sample == 2
    # A quiet run must reach the span end: a later loud window moves the end.
    late = decide([-20.0, *[-70.0] * 8, -25.0, *[-70.0] * 6])
    assert late.end_sample == 10
    # A loud tail after the silence leaves no trailing quiet run.
    assert decide([-20.0, *[-70.0] * 8, -25.0]).end_sample is None
    # Empty span.
    assert decide([]).end_sample is None


def test_quiet_fricative_after_a_loud_vowel_is_not_a_gap(tmp_path: Path) -> None:
    # alpha: loud vowel (-10 dBFS) 100-390 ms, then a 100 ms -32 dBFS fricative.
    vowel = round(32768 * 10 ** (-10 / 20) * math.sqrt(2))
    fricative = round(32768 * 10 ** (-32 / 20) * math.sqrt(2))
    bursts = (
        (100, 390, 400, vowel),
        (390, 490, 5000, fricative),
        (520, 820, 600),
        (820, 1120, 800),
        (1270, 1520, 1000),
    )
    result = measured(tmp_path, bursts=bursts)
    alpha = result.artifact["tokens"][0]
    assert alpha["endMeasuredOn"] == "raw_provider_pcm"
    assert alpha["audibleEndSamples"] != alpha["onsetSamples"] + 290 * 48
    # The end is the fricative's end (490 ms), not the vowel's end (390 ms).
    assert alpha["audibleEndSamples"] == alpha["onsetSamples"] + 390 * 48


def test_negative_onset_is_refused_not_clamped(tmp_path: Path) -> None:
    # A 1 ms-early mark with a +1 ms normalization lead would land before zero.
    cache, _asset, key = build_cache(
        tmp_path / "cache", lag_samples=-96, mark_ms=(1, 520, 820, 1270)
    )
    with pytest.raises(MeasurementError) as caught:
        measure_asset(load_asset(cache, key), frozen_block(), artifact_locator=LOCATOR)
    assert any("negative" in reason for reason in caught.value.reasons)


def test_last_loud_window_in_token_ids_matches_fixture(tmp_path: Path) -> None:
    result = measured(tmp_path)
    assert [t["tokenId"] for t in result.evidence["tokens"]] == list(TOKEN_IDS)


def test_evidence_validates_against_the_v2_contract_schema(tmp_path: Path) -> None:
    import json

    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
    from referencing import Registry, Resource

    root = Path(__file__).resolve().parents[1] / "contracts"
    dependency = json.loads((root / "compiler-dependencies-v2.schema.json").read_text())
    document = json.loads((root / "script-document-v2.schema.json").read_text())
    registry = Registry().with_resources(
        [
            (dependency["$id"], Resource.from_contents(dependency)),
            (document["$id"], Resource.from_contents(document)),
        ]
    )
    validator = Draft202012Validator(
        {"$ref": f"{dependency['$id']}#/$defs/NarrationBoundaryEvidenceV1"},
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    validator.validate(measured(tmp_path).evidence)


def test_parameters_hash_cross_language_vectors() -> None:
    # The same vectors are asserted in
    # packages/contracts/test/measured-boundary-evidence-v2.test.ts against
    # sha256CanonicalJson, so Python and TypeScript hash parameters identically.
    assert parameters_hash({"b": [1, {"z": "é", "a": 0}], "a": "x"}) == (
        "sha256:3a92e85a00e73199bcec8c5f6f98aaed74efcfb435a8e785198c59742e3610c1"
    )
    assert parameters_hash(DEFAULT_PARAMETERS) == (
        "sha256:628c4c9e17822d9ed812b9cdbf31062eb71e1768d6946cc333f522a2b878ded4"
    )
    with pytest.raises(MeasurementError):
        parameters_hash({"ratio": 0.9})
