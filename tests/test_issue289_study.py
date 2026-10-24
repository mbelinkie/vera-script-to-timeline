from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "word-timing"))
import issue289_study as study
from vera_timeline_agent.narration.configuration import (
    FISH_PROFILE_ID,
    JOANNA_PROFILE_ID,
)
from vera_timeline_agent.narration.fish import FishError
from vera_timeline_agent.narration.models import ProviderResult, SynthesisSettings


def test_frozen_corpus_has_three_paired_and_seven_fish_only_texts() -> None:
    corpus = study.load_corpus()
    paired, extras = corpus["pairedTexts"], corpus["fishOnlyTexts"]

    assert [len(row["text"].split()) for row in paired] == [14, 60, 109]
    assert len(paired[-1]["text"]) > 300
    assert len(extras) == 7
    assert all(10 <= len(row["text"].split()) <= 120 for row in extras)
    assert len({row["id"] for row in paired + extras}) == 10
    assert "we\u2019re" in paired[0]["text"]
    assert "12 steps, 12 steps" in paired[0]["text"]


def test_plan_has_25_unique_takes_and_reserves_under_one_dollar() -> None:
    plan = study._plan(
        study.load_corpus(),
        "unit-study",
        FISH_PROFILE_ID,
        JOANNA_PROFILE_ID,
        SynthesisSettings(),
        1.0,
        None,
        None,
    )
    ids = [
        study.identity_hash(
            {
                "providerRequest": row["request"].identity(
                    row["input"],
                    study._provider(row["provider"], Path("unused")).adapter_version,
                ),
                "studyTakeId": row["takeId"],
            }
        )
        for row in plan
    ]

    assert len(plan) == len(set(ids)) == 25
    assert sum(row["provider"] == "fish" for row in plan) == 16
    assert sum(row["provider"] == "polly" for row in plan) == 9
    assert sum(row["reserve"] for row in plan) <= 1.0
    assert all(
        row["reserve"] == 0 and row["request"].max_cost_usd == 0
        for row in plan
        if row["provider"] == "fish"
    )
    with pytest.raises(ValueError, match="exceeds"):
        study._plan(
            study.load_corpus(),
            "small-budget",
            FISH_PROFILE_ID,
            JOANNA_PROFILE_ID,
            SynthesisSettings(),
            0.001,
            None,
            None,
        )


def test_invalid_fish_sse_is_retained_verbatim(tmp_path: Path) -> None:
    row = study.load_corpus()["pairedTexts"][0]
    request = study._request(
        "capture-test",
        "fish",
        row,
        1,
        FISH_PROFILE_ID,
        SynthesisSettings(),
        "fish_terms_accepted",
        0.0,
    )
    raw, path = b"data: {not valid json}\n\n", tmp_path / "fish.sse"
    provider = study.CapturingFishProvider(path, transport=lambda *_: [raw])

    with pytest.raises(FishError):
        provider.synthesize(request)
    assert path.read_bytes() == raw


def test_paid_reservation_precedes_each_call_and_errors_are_redacted(
    tmp_path: Path,
) -> None:
    class FakeProvider:
        adapter_version = "test/v1"

        def __init__(self, name: str, take_dir: Path) -> None:
            self.name, self.take_dir = name, take_dir

        def prepare_input(self, request: object) -> bytes:
            return b"test-provider-input"

        def synthesize(self, request: object) -> ProviderResult:
            if self.name == "polly":
                ledger = json.loads((self.take_dir.parent / "ledger.json").read_text())
                assert any(
                    row["takeId"] == self.take_dir.name
                    for row in ledger["reservations"]
                )
                value = "unit" + "-" + "secret"
                raise RuntimeError(f"credential token={value}")
            return ProviderResult(
                b"\x00\x00",
                "pcm_s16le",
                16000,
                1,
                b"test-provider-input",
                (),
                {"provider": "fish_audio"},
                provider_input_format="json",
            )

    calls = {"fish": 0, "polly": 0}

    def factory(name: str, raw_path: Path) -> FakeProvider:
        calls[name] += 1
        return FakeProvider(name, raw_path.parent)

    root = tmp_path / "study"
    summary = study.run_study(
        root,
        run_id="test-run",
        fish_attestation="fish_terms_accepted",
        aws_attestation="provider_terms_accepted",
        provider_factory=factory,
    )

    assert calls == {"fish": 16, "polly": 9}
    assert summary["takeCount"] == 25
    assert summary["succeeded"] == 16 and summary["failed"] == 9
    assert summary["denominators"] == {
        "perText": {"fish": 10, "polly": 3, "paired": 3, "fishOnly": 7},
        "perTake": {"fish": 16, "polly": 9, "total": 25},
    }
    failed = list(root.glob("*-polly-*/take.json"))
    assert len(failed) == 9
    for path in failed:
        record = json.loads(path.read_text())
        assert record["cost"]["actualUsd"] is None
        assert record["cost"]["upperBoundUsd"] == record["cost"]["reservedUsd"]
        assert "[REDACTED]" in record["failure"]["message"]
        assert "unit-secret" not in record["failure"]["message"]
