from __future__ import annotations

import io
import json
import os
import stat
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
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    sha256_bytes,
)
from vera_timeline_agent.narration.service import BlockPlan

PRICE_PER_CHAR = 32.0 / 1_000_000


class FakeService:
    """Stands in for NarrationService: counts real provider calls."""

    def __init__(self, fail_texts: tuple[str, ...] = ()) -> None:
        self.cache: set[str] = set()
        self.calls: list[str] = []
        self.fail_texts = fail_texts

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
        disposition = "reused"
        ids: tuple[str, ...] = ()
        if failed:
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
        "requestHash",
        "blockId",
        "characters",
        "estimatedCostUsd",
        "requestIds",
        "at",
    }
    assert rows[0]["characters"] == len("Every morning the ferry crosses.")
    assert rows[0]["requestIds"] == ["req-1"]
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


def test_failed_call_is_not_billed_and_retry_bills_only_the_new_call(
    tmp_path: Path,
) -> None:
    ledger = ledger_at(tmp_path)
    service = FakeService(fail_texts=("second",))
    doc = document("first", "second")
    report = run_generate(service, doc, ledger)
    assert len(report.generated) == 1 and len(report.failed) == 1
    assert len(ledger.rows()) == 1
    service.fail_texts = ()
    retry = run_generate(service, doc, ledger)
    assert len(retry.reused) == 1 and len(retry.generated) == 1
    assert [row["blockId"] for row in ledger.rows()] == ["block-0", "block-1"]


def test_unreadable_ledger_refuses_rather_than_resetting(tmp_path: Path) -> None:
    ledger = ledger_at(tmp_path)
    ledger.path.parent.mkdir(parents=True)
    ledger.path.write_text("not json")
    with pytest.raises(LedgerError):
        run_generate(FakeService(), document("hello"), ledger)


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
    assert "absent (connected speech" in stdout.getvalue()
    report_out = tmp_path / "report.json"
    code = run_campaign(
        [
            "omission",
            "--evidence",
            str(evidence_path),
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
        ["omission", "--evidence", str(evidence_path), "--token", TOKEN_IDS[2]],
        stdout=io.StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert BLOCK_ID in key
