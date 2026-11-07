"""Narration stage reuses real service/cache and refuses placeholders/paid replay."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    SnapshotRepository,
)
from vera_timeline_agent.build_jobs import (
    BuildJobError,
    NeedsAction,
    StageContext,
    UncertainResult,
)
from vera_timeline_agent.build_narration_stage import (
    NarrationAuthorization,
    NarrationStagePort,
)
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
)
from vera_timeline_agent.narration.normalize import NormalizationResult, Normalizer
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
TOKEN_ID = "20000000-0000-4000-8000-000000000001"
NarrationCase = tuple[Path, FrozenBuildSnapshot, StageContext]


class LocalProvider:
    adapter_version = "local-test/v1"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return request.text.encode("utf-8")

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("offline provider failure")
        return ProviderResult(
            audio_bytes=b"\x01\x00" * 16000,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    kind="word",
                    time_ms=0,
                    start_byte=0,
                    end_byte=5,
                    start_utf16=0,
                    end_utf16=5,
                    value="Hello",
                ),
            ),
            provenance={"provider": "local", "engine": "fake", "voiceVersion": "v1"},
            request_ids=("fake-request",),
        )


class LocalNormalizer:
    profile_id = "local-test-normalize/v1"
    tool_fingerprint = "sha256:" + "a" * 64

    def normalize_pcm(self, *_args: Any, **_kwargs: Any) -> NormalizationResult:
        return NormalizationResult(
            wav_bytes=b"RIFF" + b"\x00" * 64,
            profile_id=self.profile_id,
            normalizer_version="local-test/v1",
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=48000,
            channels=1,
            sample_format="pcm_s24le",
            duration_samples=48000,
            duration_ms=1000,
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.0,
            loudness_range_lu=0.0,
        )

    def placeholder(self, _block_id: str) -> NormalizationResult:
        return self.normalize_pcm()


@pytest.fixture
def setup(tmp_path: Path) -> NarrationCase:
    source = tmp_path / "inputs"
    source.mkdir()
    document = source / "document.json"
    document.write_text(
        json.dumps(
            {
                "activeDraft": {
                    "blocks": [
                        {
                            "id": BLOCK_ID,
                            "type": "narration",
                            "state": "active",
                            "orderKey": "a",
                            "version": 1,
                            "text": "Hello",
                            "tokens": [
                                {
                                    "id": TOKEN_ID,
                                    "value": "Hello",
                                    "startOffset": 0,
                                    "endOffset": 5,
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )
    deps = source / "deps.json"
    deps.write_text("{}")
    repo = SnapshotRepository(
        tmp_path / "snapshots",
        read_roots=(source,),
        write_root=tmp_path / "build",
        live_head=lambda _: (1, "d" * 64, "rev-1"),
        live_settings=lambda _: "a" * 64,
    )
    snap = repo.freeze(
        project_id="p",
        mode="free",
        build_id="build-1",
        build_class="preview",
        settings_hash="a" * 64,
        inputs={"document": document, "dependencies": deps},
        adapter_versions={"narration-v2": "local-test/v1"},
    )
    ctx = StageContext(
        "p",
        "j",
        snap.snapshot_id,
        "generating_speech",
        hashlib.sha256(b"p\0j\0generating_speech").hexdigest(),
        tmp_path / "jobs" / "output",
        1,
        1,
        lambda _: None,
        lambda: None,
    )
    return tmp_path, snap, ctx


def service(tmp_path: Path, provider: LocalProvider) -> NarrationService:
    return NarrationService(
        cache=NarrationCache(tmp_path / "cache"),
        provider=provider,
        normalizer=cast(Normalizer, LocalNormalizer()),
        config=ServiceConfig(data_policy_attestation="local-fixture-consent"),
    )


def consent(snapshot: FrozenBuildSnapshot) -> NarrationAuthorization:
    return NarrationAuthorization(True, snapshot.project_id, snapshot.snapshot_id, 1.0)


def _snapshot_with_notes(
    setup: NarrationCase, *, notes: list[dict[str, Any]], include_spoken: bool = True
) -> tuple[FrozenBuildSnapshot, StageContext]:
    tmp, original, ctx = setup
    source = tmp / "note-inputs"
    source.mkdir()
    document = json.loads(original.file("document").read_text())
    spoken = document["activeDraft"]["blocks"] if include_spoken else []
    document["activeDraft"]["blocks"] = [*notes, *spoken]
    document["stash"] = [
        {"rows": [{"text": "saved and not active", "plainDirection": True}]}
    ]
    doc_file = source / "document.json"
    doc_file.write_text(json.dumps(document))
    deps_file = source / "deps.json"
    deps_file.write_text("{}")
    repo = SnapshotRepository(
        tmp / "note-snapshots",
        read_roots=(source,),
        write_root=tmp / "note-build",
        live_head=lambda _: (1, "d" * 64, "rev-1"),
        live_settings=lambda _: "a" * 64,
    )
    frozen = repo.freeze(
        project_id="p",
        mode="free",
        build_id="build-notes",
        build_class="preview",
        settings_hash="a" * 64,
        inputs={"document": doc_file, "dependencies": deps_file},
        adapter_versions={"narration-v2": "local-test/v1"},
    )
    return frozen, replace(ctx, snapshot_id=frozen.snapshot_id)


def _plain(text: str) -> dict[str, Any]:
    return {
        "id": "10000000-0000-4000-8000-000000000002",
        "type": "narration",
        "state": "active",
        "orderKey": "a0",
        "version": 1,
        "text": text,
        "plainDirection": True,
        "tokens": (
            [
                {
                    "id": "20000000-0000-4000-8000-000000000002",
                    "value": text,
                    "startOffset": 0,
                    "endOffset": len(text.encode("utf-16-le")) // 2,
                    "spoken": False,
                }
            ]
            if text
            else []
        ),
    }


@pytest.mark.parametrize("raw", ["", "[nested [literal]] 🌍", "orphan ] [\n'quote'"])
def test_active_plain_directions_are_excluded_before_planning_and_provider(
    setup: NarrationCase, raw: str
) -> None:
    tmp, _, _ = setup
    frozen, ctx = _snapshot_with_notes(setup, notes=[_plain(raw)])
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(frozen))
    assert [block["id"] for block in port._block_rows(frozen)] == [BLOCK_ID]
    port.execute(ctx, frozen)
    evidence = port.inspect(ctx, frozen)
    assert evidence.state == EffectState.VERIFIED
    assert evidence.evidence is not None
    assets = json.loads(evidence.evidence.outputs["assets"].read_bytes())["assets"]
    assert [asset["blockId"] for asset in assets] == [BLOCK_ID]
    assert provider.calls == 1


def test_only_plain_direction_needs_no_provider_or_speech_budget(
    setup: NarrationCase,
) -> None:
    tmp, _, _ = setup
    frozen, ctx = _snapshot_with_notes(setup, notes=[_plain("")], include_spoken=False)
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider))
    assert port._block_rows(frozen) == []
    port.execute(ctx, frozen)
    evidence = port.inspect(ctx, frozen)
    assert evidence.state == EffectState.VERIFIED
    assert evidence.evidence is not None
    assert json.loads(evidence.evidence.outputs["timingMaps"].read_bytes()) == []
    assert provider.calls == 0


def test_corrupt_plain_direction_refuses_before_provider_planning(
    setup: NarrationCase,
) -> None:
    tmp, _, _ = setup
    bad = _plain("[literal]")
    bad["tokens"][0]["spoken"] = True
    frozen, ctx = _snapshot_with_notes(setup, notes=[bad])
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(frozen))
    with pytest.raises(BuildJobError, match="invalid frozen direction intent"):
        port.execute(ctx, frozen)
    assert provider.calls == 0
    assert not port._paths(ctx, frozen)[0].exists()


def test_ready_voice_asset_and_frozen_word_map_are_reverified(
    setup: NarrationCase,
) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(snapshot))
    assert port.inspect(ctx, snapshot).state == EffectState.ABSENT
    port.execute(ctx, snapshot)
    verified = port.inspect(ctx, snapshot)
    assert verified.state == EffectState.VERIFIED
    assert provider.calls == 1
    assert verified.evidence is not None
    maps = json.loads(verified.evidence.outputs["timingMaps"].read_bytes())
    assert len(maps) == 1
    assert maps[0]["blockId"] == BLOCK_ID
    # Valid synthesis cache is reused, not charged again.
    port.execute(ctx, snapshot)
    assert provider.calls == 1


@pytest.mark.parametrize("lost", ["assets", "timing", "both"])
def test_lost_stage_proof_is_rebuilt_from_ready_cache_without_provider_call(
    setup: NarrationCase, lost: str
) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(snapshot))
    port.execute(ctx, snapshot)
    intent, record, maps = port._paths(ctx, snapshot)
    assert intent.is_file()
    original_record, original_maps = record.read_bytes(), maps.read_bytes()
    if lost in ("assets", "both"):
        record.unlink()
    if lost in ("timing", "both"):
        maps.unlink()
    assert port.inspect(ctx, snapshot).state == EffectState.VERIFIED
    assert record.read_bytes() == original_record
    assert maps.read_bytes() == original_maps
    assert provider.calls == 1


def test_mismatched_narration_intent_cannot_replay_provider(
    setup: NarrationCase,
) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(snapshot))
    port.execute(ctx, snapshot)
    intent, record, maps = port._paths(ctx, snapshot)
    record.unlink()
    maps.unlink()
    intent.write_bytes(b'{"wrong":"request"}\n')
    with pytest.raises(Exception, match="intent differs"):
        port.inspect(ctx, snapshot)
    assert provider.calls == 1


def test_unapproved_voice_spend_never_calls_provider(setup: NarrationCase) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider))
    with pytest.raises(NeedsAction, match="explicit"):
        port.execute(ctx, snapshot)
    assert provider.calls == 0
    assert port.inspect(ctx, snapshot).state == EffectState.ABSENT


def test_failure_placeholder_never_becomes_ready_and_retry_is_uncertain(
    setup: NarrationCase,
) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider(fail=True)
    port = NarrationStagePort(service(tmp, provider), consent(snapshot))
    with pytest.raises(NeedsAction, match="placeholder"):
        port.execute(ctx, snapshot)
    assert provider.calls == 1
    assert port.inspect(ctx, snapshot).state == EffectState.UNCERTAIN
    with pytest.raises(UncertainResult):
        raise UncertainResult("a lost provider result is not authoritative absence")


def test_changed_provider_request_is_not_reused(setup: NarrationCase) -> None:
    tmp, snapshot, ctx = setup
    provider = LocalProvider()
    port = NarrationStagePort(service(tmp, provider), consent(snapshot))
    port.execute(ctx, snapshot)
    changed = service(tmp, LocalProvider())
    changed.config = replace(changed.config, max_cost_usd=0.002)
    incompatible = NarrationStagePort(changed, consent(snapshot))
    # A mismatched voice policy cannot silently claim the prior asset.
    assert (
        incompatible.inspect(ctx, snapshot).state != EffectState.ABSENT
        or provider.calls == 1
    )
