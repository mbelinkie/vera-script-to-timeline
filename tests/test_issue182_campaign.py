from __future__ import annotations

import io
import json
import math
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from issue182_fixture import BLOCK_ID, TOKEN_IDS, build_cache, frozen_block
from vera_timeline_agent.narration.campaign import (
    CapExceeded,
    Ledger,
    LedgerError,
    run_campaign,
    run_generate,
)
from vera_timeline_agent.narration.configuration import (
    MATTHEW_PROFILE_ID,
    voice_profile,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    sha256_bytes,
)
from vera_timeline_agent.narration.service import BlockPlan

PRICE_PER_CHAR = 32.0 / 1_000_000


class FakeService:
    """Stands in for NarrationService: counts real provider calls."""

    def __init__(
        self,
        fail_texts: tuple[str, ...] = (),
        fail_after_audio_texts: tuple[str, ...] = (),
        delay: float = 0.0,
    ) -> None:
        self.cache: set[str] = set()
        self.calls: list[str] = []
        self.fail_texts = fail_texts
        # Provider audio arrived (cache filled) but a later step failed.
        self.fail_after_audio_texts = fail_after_audio_texts
        self.delay = delay

    def _hash(self, block: dict[str, Any]) -> str:
        return sha256_bytes(block["text"].encode())

    def plan_block(self, block: dict[str, Any]) -> BlockPlan:
        return BlockPlan(
            block_id=block["id"],
            request_hash=self._hash(block),
            characters=len(block["text"]),
            estimated_cost_usd=len(block["text"]) * PRICE_PER_CHAR,
            cached=self._hash(block) in self.cache,
        )

    def process_block(self, block: dict[str, Any]) -> NarrationAudioAsset:
        request_hash = self._hash(block)
        failed = block["text"] in self.fail_texts and request_hash not in self.cache
        late = (
            block["text"] in self.fail_after_audio_texts
            and request_hash not in self.cache
        )
        disposition = "reused"
        ids: tuple[str, ...] = ()
        if self.delay:
            time.sleep(self.delay)
        if late:
            self.cache.add(request_hash)
            self.calls.append(block["id"])
            failed = True
            disposition = "failed"
        elif failed:
            disposition = "failed"
        elif request_hash not in self.cache:
            self.cache.add(request_hash)
            self.calls.append(block["id"])
            disposition = "generated"
            ids = (f"req-{len(self.calls)}",)
        else:
            ids = ("req-cached",)
        base = build_asset()
        return NarrationAudioAsset(
            **{
                **base.__dict__,
                "block_id": block["id"],
                "request_hash": request_hash,
                "status": "failed" if failed else "ready",
                "failure_reason": "provider: outage" if failed else None,
                "synthesis_disposition": disposition,
                "request_ids": ids,
            }
        )


_ASSET: list[NarrationAudioAsset] = []


def build_asset() -> NarrationAudioAsset:
    if not _ASSET:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            _ASSET.append(build_cache(Path(directory))[1])
    return _ASSET[0]


def document(*texts: str) -> dict[str, Any]:
    return {
        "activeDraft": {
            "blocks": [
                {
                    "type": "narration",
                    "state": "active",
                    "id": f"block-{index}",
                    "orderKey": f"{index:03d}",
                    "version": 1,
                    "text": text,
                }
                for index, text in enumerate(texts)
            ]
        }
    }


def ledger_at(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "vera" / "ledger.json")


def test_real_calls_are_recorded_and_cache_hits_are_not(tmp_path: Path) -> None:
    service = FakeService()
    ledger = ledger_at(tmp_path)
    doc = document("Every morning the ferry crosses.", "Second row.")
    first = run_generate(service, doc, ledger)
    assert len(first.generated) == 2 and not first.reused
    rows = ledger.rows()
    assert [row["blockId"] for row in rows] == ["block-0", "block-1"]
    assert set(rows[0]) == {
        "reservationId",
        "status",
        "settledAt",
        "requestHash",
        "blockId",
        "characters",
        "estimatedCostUsd",
        "requestIds",
        "at",
    }
    assert rows[0]["characters"] == len("Every morning the ferry crosses.")
    assert rows[0]["requestIds"] == ["req-1"]
    assert [row["status"] for row in rows] == ["charged", "charged"]
    # Re-running is an idempotent retry: every request is a cache hit.
    second = run_generate(service, doc, ledger)
    assert len(second.reused) == 2 and not second.generated
    assert len(ledger.rows()) == 2
    assert service.calls == ["block-0", "block-1"]


def test_ledger_directory_is_private_and_path_is_injectable(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    run_generate(FakeService(), document("hello"), ledger)
    assert stat.S_IMODE(os.stat(ledger.path.parent).st_mode) == 0o700
    value = json.loads(ledger.path.read_text())
    assert value["schemaVersion"] == "polly-campaign-ledger/v1"


def test_cap_refuses_before_any_call(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    ledger.append(
        request_hash="sha256:" + "a" * 64,
        block_id="earlier",
        characters=31_000,
        estimated_cost_usd=0.992,
        request_ids=("old",),
    )
    service = FakeService()
    # 500 chars = $0.016: 0.992 + 0.016 > 1.00.
    with pytest.raises(CapExceeded):
        run_generate(service, document("x" * 500), ledger)
    assert service.calls == [] and len(ledger.rows()) == 1
    # A cached request still passes at the cap because it costs nothing.
    service.cache.add(sha256_bytes(("x" * 500).encode()))
    report = run_generate(service, document("x" * 500), ledger)
    assert len(report.reused) == 1 and len(ledger.rows()) == 1


def test_cap_counts_the_whole_batch_before_the_first_call(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    service = FakeService()
    # Two distinct 20,000-character rows = $1.28 together, each alone $0.64.
    with pytest.raises(CapExceeded):
        run_generate(service, document("a" * 20_000, "b" * 20_000), ledger)
    assert service.calls == [] and ledger.rows() == []


def test_identical_requests_are_estimated_once(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    service = FakeService()
    # Each is $0.64; identical requests share one provider call and one row.
    report = run_generate(service, document("a" * 20_000, "a" * 20_000), ledger)
    assert len(report.generated) == 1 and len(report.reused) == 1
    assert len(ledger.rows()) == 1


def test_failed_call_keeps_its_reservation_and_retry_bills_again(
    tmp_path: Path,
) -> None:
    ledger = ledger_at(tmp_path)
    service = FakeService(fail_texts=("second",))
    doc = document("first", "second")
    report = run_generate(service, doc, ledger)
    assert len(report.generated) == 1 and len(report.failed) == 1
    # No refund: the failed attempt stays in the total as "attempted".
    assert [row["status"] for row in ledger.rows()] == ["charged", "attempted"]
    service.fail_texts = ()
    retry = run_generate(service, doc, ledger)
    assert len(retry.reused) == 1 and len(retry.generated) == 1
    assert [row["status"] for row in ledger.rows()] == [
        "charged",
        "attempted",
        "charged",
    ]


def test_failure_after_audio_success_is_still_counted(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    service = FakeService(fail_after_audio_texts=("second",))
    doc = document("second")
    report = run_generate(service, doc, ledger)
    assert len(report.failed) == 1
    expected = _micro_of("second")
    assert ledger.cumulative_micro_usd() == expected
    assert [row["status"] for row in ledger.rows()] == ["attempted"]
    # Retry: the synthesis cache is filled, so it is a hit - no second charge,
    # and the original charge is not lost.
    retry = run_generate(service, doc, ledger)
    assert len(retry.reused) == 1 and not retry.generated
    assert service.calls == ["block-0"]
    assert ledger.cumulative_micro_usd() == expected
    assert len(ledger.rows()) == 1


def test_exception_during_processing_keeps_the_reservation(tmp_path: Path) -> None:
    class Exploding(FakeService):
        def process_block(self, block: dict[str, Any]) -> NarrationAudioAsset:
            raise RuntimeError("cache corrupt")

    ledger = ledger_at(tmp_path)
    with pytest.raises(RuntimeError):
        run_generate(Exploding(), document("hello"), ledger)
    assert [row["status"] for row in ledger.rows()] == ["attempted"]
    assert ledger.cumulative_micro_usd() == _micro_of("hello")


def _micro_of(text: str) -> int:
    return math.ceil(round(len(text) * PRICE_PER_CHAR * 1_000_000, 6))


def test_concurrent_runs_cannot_exceed_the_cap(tmp_path: Path) -> None:
    path = tmp_path / "vera" / "ledger.json"
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def worker(letter: str) -> None:
        # Own Ledger instance and own service/cache: two independent processes.
        service = FakeService(delay=0.15)
        ledger = Ledger(path)
        barrier.wait()
        try:
            # $0.64 each; only one fits under the $1.00 cap.
            run_generate(service, document(letter * 20_000), ledger)
            outcomes.append("ran")
        except CapExceeded:
            outcomes.append("refused")

    threads = [threading.Thread(target=worker, args=(c,)) for c in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["ran", "refused"]
    assert Ledger(path).cumulative_micro_usd() <= 1_000_000


def test_unreadable_ledger_refuses_rather_than_resetting(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    ledger.path.parent.mkdir(parents=True)
    ledger.path.write_text("not json")
    with pytest.raises(LedgerError):
        run_generate(FakeService(), document("hello"), ledger)


def test_legacy_rows_without_status_read_as_charged(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    ledger.path.parent.mkdir(parents=True)
    legacy = {
        "at": "2026-10-20T02:10:36+00:00",
        "blockId": "b",
        "characters": 112,
        "estimatedCostUsd": 0.003584,
        "requestHash": "sha256:x",
        "requestIds": ["r1"],
    }
    ledger.path.write_text(
        json.dumps({"schemaVersion": "polly-campaign-ledger/v1", "rows": [legacy]})
    )
    rows = ledger.rows()
    assert rows[0]["status"] == "charged"
    assert rows[0]["estimatedCostUsd"] == 0.003584
    assert ledger.cumulative_micro_usd() == 3584
    for bad in (
        {**legacy, "estimatedCostUsd": "1"},
        {**legacy, "estimatedCostUsd": True},
        {**legacy, "status": "bogus"},
        {k: v for k, v in legacy.items() if k != "requestIds"},
    ):
        ledger.path.write_text(
            json.dumps({"schemaVersion": "polly-campaign-ledger/v1", "rows": [bad]})
        )
        with pytest.raises(LedgerError):
            ledger.rows()


class RecordingProvider:
    adapter_version = "recording/v1"

    def __init__(self) -> None:
        self.calls = 0

    def prepare_input(self, request: Any) -> bytes:
        return bytes(request.text.encode())

    def synthesize(self, request: Any) -> Any:
        self.calls += 1
        raise AssertionError("no provider call is allowed in this test")


def test_cli_generate_requires_confirmation_and_makes_no_call(tmp_path: Path) -> None:
    script = tmp_path / "script.json"
    script.write_text(json.dumps(document("hello world")))
    provider = RecordingProvider()
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_campaign(
        [
            "generate",
            "--doc",
            str(script),
            "--cache",
            str(tmp_path / "cache"),
            "--aws-data-policy",
            "provider_terms_accepted",
        ],
        stdout=stdout,
        stderr=stderr,
        provider=provider,
        ledger_path=tmp_path / "ledger" / "ledger.json",
        validator=lambda path: (json.loads(path.read_text()), "ok"),
    )
    assert code == 64
    assert "--confirm-provider-call" in stderr.getvalue()
    assert provider.calls == 0


def test_cli_generate_refuses_at_the_cap(tmp_path: Path) -> None:
    script = tmp_path / "script.json"
    script.write_text(json.dumps(document("hello world")))
    ledger = Ledger(tmp_path / "ledger" / "ledger.json")
    ledger.append(
        request_hash="sha256:" + "b" * 64,
        block_id="earlier",
        characters=1,
        estimated_cost_usd=1.0,
        request_ids=(),
    )
    provider = RecordingProvider()
    stderr = io.StringIO()
    code = run_campaign(
        [
            "generate",
            "--doc",
            str(script),
            "--cache",
            str(tmp_path / "cache"),
            "--aws-data-policy",
            "provider_terms_accepted",
            "--confirm-provider-call",
        ],
        stdout=io.StringIO(),
        stderr=stderr,
        provider=provider,
        ledger_path=ledger.path,
        validator=lambda path: (json.loads(path.read_text()), "ok"),
    )
    assert code == 5 and "cap" in stderr.getvalue()
    assert provider.calls == 0


def test_cli_measure_then_omission_round_trip(tmp_path: Path) -> None:
    _cache, asset, key = build_cache(tmp_path / "cache")
    block_file = tmp_path / "block.json"
    block_file.write_text(json.dumps(frozen_block()))
    out = tmp_path / "project"
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_campaign(
        [
            "measure",
            "--cache",
            str(tmp_path / "cache"),
            "--asset",
            key,
            "--block",
            str(block_file),
            "--out",
            str(out),
        ],
        stdout=stdout,
        stderr=stderr,
    )
    assert code == 0, stderr.getvalue()
    artifact = out / f"narration-measurements/{asset.asset_id}.measurement.json"
    evidence_path = (
        out / f"narration-measurements/{asset.asset_id}.boundary-evidence.json"
    )
    evidence = json.loads(evidence_path.read_text())
    assert evidence["verification"]["measurementArtifactHash"] == sha256_bytes(
        artifact.read_bytes()
    )
    # The recorded locator is project-relative (project root defaults to the
    # parent of --out), never an absolute path.
    locator = evidence["verification"]["measurementArtifactLocator"]
    assert (
        locator == f"project/narration-measurements/{asset.asset_id}.measurement.json"
    )
    assert (tmp_path / locator).read_bytes() == artifact.read_bytes()
    assert "absent (connected speech" in stdout.getvalue()
    report_out = tmp_path / "report.json"
    code = run_campaign(
        [
            "omission",
            "--evidence",
            str(evidence_path),
            "--block",
            str(block_file),
            "--token",
            TOKEN_IDS[0],
            "--out",
            str(report_out),
        ],
        stdout=io.StringIO(),
        stderr=stderr,
    )
    assert code == 0
    assert json.loads(report_out.read_text())["uniquelySafe"] is True
    # Connected-speech target refuses with a non-zero exit.
    code = run_campaign(
        [
            "omission",
            "--evidence",
            str(evidence_path),
            "--block",
            str(block_file),
            "--token",
            TOKEN_IDS[2],
        ],
        stdout=io.StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert BLOCK_ID in key


def test_real_service_normalization_failure_is_still_counted(tmp_path: Path) -> None:
    import struct

    from vera_timeline_agent.narration.cache import NarrationCache
    from vera_timeline_agent.narration.models import ProviderResult
    from vera_timeline_agent.narration.normalize import MediaToolError, Normalizer
    from vera_timeline_agent.narration.service import NarrationService, ServiceConfig

    class Provider:
        adapter_version = "t/v1"
        calls = 0

        def prepare_input(self, request: Any) -> bytes:
            return bytes(request.text.encode())

        def synthesize(self, request: Any) -> ProviderResult:
            self.calls += 1
            return ProviderResult(
                audio_bytes=struct.pack("<4h", 1, 2, 3, 4),
                audio_format="pcm_s16le",
                sample_rate=16000,
                channels=1,
                provider_input=request.text.encode(),
                timing_marks=(),
                provenance={"provider": "t"},
                request_ids=("req-real",),
            )

    class BrokenNormalizer(Normalizer):
        def normalize_pcm(self, *args: Any, **kwargs: Any) -> Any:
            raise MediaToolError("ffmpeg exploded")

        def placeholder(self, block_id: str) -> Any:
            return build_asset_normalization()

    def build_asset_normalization() -> Any:
        from vera_timeline_agent.narration.normalize import NormalizationResult

        return NormalizationResult(
            wav_bytes=b"RIFF",
            profile_id="p",
            normalizer_version="v",
            tool_fingerprint="sha256:" + "0" * 64,
            sample_rate=48000,
            channels=1,
            sample_format="s16",
            duration_samples=0,
            duration_ms=0,
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.0,
            loudness_range_lu=1.0,
        )

    provider = Provider()
    service = NarrationService(
        cache=NarrationCache(tmp_path / "cache"),
        provider=provider,
        normalizer=BrokenNormalizer(),
        config=ServiceConfig(
            profile=voice_profile(MATTHEW_PROFILE_ID),
            data_policy_attestation="provider_terms_accepted",
        ),
    )
    ledger = ledger_at(tmp_path)
    doc = document("hello there")
    report = run_generate(service, doc, ledger)
    assert len(report.failed) == 1 and provider.calls == 1
    assert [row["status"] for row in ledger.rows()] == ["attempted"]
    spent = ledger.cumulative_micro_usd()
    assert spent == _micro_of("hello there")
    # The synthesis cache is filled, so the retry makes no second call/charge.
    run_generate(service, doc, ledger)
    assert provider.calls == 1 and ledger.cumulative_micro_usd() == spent


def test_cli_measure_locator_follows_an_explicit_project_root(tmp_path: Path) -> None:
    _cache, asset, key = build_cache(tmp_path / "cache")
    block_file = tmp_path / "block.json"
    block_file.write_text(json.dumps(frozen_block()))
    base = [
        "measure",
        "--cache",
        str(tmp_path / "cache"),
        "--asset",
        key,
        "--block",
        str(block_file),
    ]
    stderr = io.StringIO()
    code = run_campaign(
        [
            *base,
            "--out",
            str(tmp_path / "a/b/out"),
            "--project-root",
            str(tmp_path / "a"),
        ],
        stdout=io.StringIO(),
        stderr=stderr,
    )
    assert code == 0, stderr.getvalue()
    evidence = json.loads(
        (
            tmp_path / f"a/b/out/narration-measurements/{asset.asset_id}"
            ".boundary-evidence.json"
        ).read_text()
    )
    assert evidence["verification"]["measurementArtifactLocator"] == (
        f"b/out/narration-measurements/{asset.asset_id}.measurement.json"
    )
    # An output directory outside the project root is refused.
    stderr = io.StringIO()
    code = run_campaign(
        [
            *base,
            "--out",
            str(tmp_path / "elsewhere"),
            "--project-root",
            str(tmp_path / "a"),
        ],
        stdout=io.StringIO(),
        stderr=stderr,
    )
    assert code == 2 and "not inside the project root" in stderr.getvalue()


def test_driver_script_parses_real_generate_output_portably(tmp_path: Path) -> None:
    import re
    import struct
    import subprocess

    from vera_timeline_agent.narration.models import ProviderResult
    from vera_timeline_agent.narration.normalize import (
        NormalizationResult,
        Normalizer,
    )

    script = Path(__file__).resolve().parents[1] / "scripts/word-timing"
    text = (script / "issue182_campaign.sh").read_text()
    assert "\\|" not in text, "GNU-only sed alternation"
    expression = re.search(r"sed -En '([^']+)'", text)
    assert expression is not None

    class Provider:
        adapter_version = "t/v1"

        def prepare_input(self, request: Any) -> bytes:
            return bytes(request.text.encode())

        def synthesize(self, request: Any) -> ProviderResult:
            return ProviderResult(
                audio_bytes=struct.pack("<4h", 1, 2, 3, 4),
                audio_format="pcm_s16le",
                sample_rate=16000,
                channels=1,
                provider_input=request.text.encode(),
                timing_marks=(),
                provenance={"provider": "t"},
                request_ids=("req-driver",),
            )

    class StubNormalizer(Normalizer):
        def normalize_pcm(self, *args: Any, **kwargs: Any) -> NormalizationResult:
            from issue182_fixture import wav_bytes

            return NormalizationResult(
                wav_bytes=wav_bytes([0, 1, 2, 3]),
                profile_id="p",
                normalizer_version="v",
                tool_fingerprint="sha256:" + "0" * 64,
                sample_rate=48000,
                channels=1,
                sample_format="s16",
                duration_samples=4,
                duration_ms=0,
                padding_samples=0,
                integrated_lufs=-16.0,
                true_peak_dbtp=-1.0,
                loudness_range_lu=1.0,
            )

    doc = tmp_path / "doc.json"
    doc.write_text(json.dumps(document("hello there")))
    stdout = io.StringIO()
    code = run_campaign(
        [
            "generate",
            "--doc",
            str(doc),
            "--cache",
            str(tmp_path / "cache"),
            "--aws-data-policy",
            "provider_terms_accepted",
            "--confirm-provider-call",
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        provider=Provider(),
        ledger_path=tmp_path / "ledger" / "ledger.json",
        validator=lambda path: (json.loads(path.read_text()), "ok"),
        normalizer=StubNormalizer(),
    )
    assert code == 0
    parsed = subprocess.run(
        ["sed", "-En", expression.group(1)],
        input=stdout.getvalue(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    block_id, _, asset_id = parsed.partition("/")
    assert block_id == "block-0" and len(asset_id) == 64
    # The driver reads narration.wav from the cache's real layout.
    assert '"$CACHE/v1/assets/$key/narration.wav"' in text
    assert (tmp_path / "cache/v1/assets" / parsed / "narration.wav").is_file()
