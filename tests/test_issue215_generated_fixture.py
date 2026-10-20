"""#215 W4: generated-narration (Polly campaign) fixtures."""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import pytest
from issue215_generated_fixture import (
    B_CLIPS,
    BASELINE_DOCUMENT,
    BOUNDARY_TOKEN_INDEX,
    FRAME_SAMPLES,
    build_b_trimmed_package,
    clip_slice_frames,
    derive_clip_pcm,
    extended_baseline_document,
    load_campaign,
    prepare_b_linked_av_case,
    prepare_b_selected_67,
    prepare_narration_case,
    read_mono_pcm24,
    write_stereo_wav,
)

CAMPAIGN = (
    Path.home() / "Library/Application Support/VERA/polly-campaign/issue182-20261020"
)
needs_campaign = pytest.mark.skipif(
    not CAMPAIGN.is_dir(), reason="#182 campaign evidence absent"
)


def _mono(samples: int) -> bytes:
    return b"".join(
        ((index * 7) % 8000 - 4000).to_bytes(3, "little", signed=True)
        for index in range(samples)
    )


def test_clip_slices_sit_on_the_frame_grid_and_differ() -> None:
    needed = sum(clip[2] for clip in B_CLIPS) * FRAME_SAMPLES + 4096
    samples = needed + 3 * FRAME_SAMPLES
    starts = clip_slice_frames(samples)
    assert starts[0] == 0 and starts[1] > 0
    mono = _mono(samples)
    first = derive_clip_pcm(mono, starts[0], B_CLIPS[0][2])
    second = derive_clip_pcm(mono, starts[1], B_CLIPS[1][2])
    assert len(first) == (B_CLIPS[0][2] * FRAME_SAMPLES + 2048) * 6
    assert len(second) == (B_CLIPS[1][2] * FRAME_SAMPLES + 2048) * 6
    assert first[:6] != second[:6] or first[6:12] != second[6:12]
    # Right channel is the halved left channel: channels differ, both derive from
    # the generated speech.
    left = int.from_bytes(first[6:9], "little", signed=True)
    right = int.from_bytes(first[9:12], "little", signed=True)
    assert right == left // 2


def test_clip_slices_refuse_a_too_short_narration() -> None:
    with pytest.raises(ValueError, match="too short"):
        clip_slice_frames(FRAME_SAMPLES)
    with pytest.raises(ValueError, match="too short"):
        derive_clip_pcm(_mono(100), 0, 91)


def test_stereo_wav_round_trip(tmp_path: Path) -> None:
    pcm = derive_clip_pcm(_mono(FRAME_SAMPLES * 4), 0, 1)
    path = tmp_path / "x.wav"
    write_stereo_wav(path, pcm)
    with wave.open(io.BytesIO(path.read_bytes())) as stream:
        assert (stream.getnchannels(), stream.getsampwidth()) == (2, 3)
        assert stream.getframerate() == 48_000
        assert stream.getnframes() == len(pcm) // 6


def test_mono_reader_refuses_wrong_format(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(b"\0" * 12)
    with pytest.raises(ValueError, match="PCM24 mono"):
        read_mono_pcm24(path)


@needs_campaign
def test_campaign_loads_read_only_and_document_gains_a_movable_boundary() -> None:
    campaign = load_campaign(CAMPAIGN)
    assert campaign.evidence["verification"]["method"] == "measured_audio_boundaries/v1"
    document = extended_baseline_document(campaign)
    row = document["activeDraft"]["blocks"][0]
    slots = row["primaryVisualSequence"]["slots"]
    assert len(slots) == 2
    assert all(
        slot["payload"]["pictureKind"] == "intentional_placeholder"
        and slot["payload"]["audioPolicy"] == "mute"
        for slot in slots
    )
    boundary = slots[1]["boundaryBefore"]
    assert boundary["kind"] == "spoken_word"
    assert boundary["anchor"]["tokenId"] == row["tokens"][BOUNDARY_TOKEN_INDEX]["id"]
    # The checked-in baseline document is not modified in place.
    assert BASELINE_DOCUMENT.is_file()


@needs_campaign
def test_campaign_tamper_is_refused(tmp_path: Path) -> None:
    campaign = load_campaign(CAMPAIGN)
    changed = tmp_path / "campaign"
    (changed / "out/baseline/narration-measurements").mkdir(parents=True)
    source = campaign.evidence_path
    (changed / "out/baseline/narration-measurements" / source.name).write_bytes(
        source.read_bytes()
    )
    with pytest.raises(ValueError, match="campaign input missing"):
        load_campaign(changed)


@needs_campaign
def test_a_c_package_admits_measured_narration(tmp_path: Path) -> None:
    campaign = load_campaign(CAMPAIGN)
    result = prepare_narration_case(
        campaign, tmp_path, label="C", output_name="C-generated"
    )
    assert result["admitted"] is True
    assert result["evidenceMethod"] == "measured_audio_boundaries/v1"
    assert result["slateEventCount"] == 2
    assert result["omission"]["quotedText"] == "slowly"


@pytest.mark.slow
@needs_campaign
def test_b_generated_linked_av_admits_and_b67_has_its_own_honest_key(
    tmp_path: Path,
) -> None:
    campaign = load_campaign(CAMPAIGN)
    baseline = prepare_b_linked_av_case(campaign, tmp_path)
    assert baseline["admitted"] is True
    assert baseline["selectedSourceFrameCounts"] == [91, 48]
    assert baseline["sourceAudioEventCount"] == 2
    trim = prepare_b_selected_67(tmp_path)
    dependencies_key = json.loads(
        (tmp_path / "B-generated/inputs/compiler-dependencies-v2.json").read_bytes()
    )["preparedMedia"][0]["requirementKey"]
    assert trim["requirementKey"] != dependencies_key
    assert trim["baselineRequirementKey"] == dependencies_key
    trimmed = build_b_trimmed_package(tmp_path)
    assert trimmed["timelineFrames"] == 67 + 48
    assert trimmed["requirementKey"] == trim["requirementKey"]
    # Matrix admission recomputes key == identity_hash(inputs); the honest key passes.
    assert trimmed["keyEqualsIdentityOfInputs"] is True
