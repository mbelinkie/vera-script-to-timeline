"""#215 whole-row regeneration: machine omission support, ledger-guarded fake synthesis.

Fake providers only: no AWS, no Resolve, nothing outside tmp_path.
"""

from __future__ import annotations

import copy
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue182_fixture import burst_pcm, pcm_bytes, wav_bytes
from issue182_fixture import normalize as hold_normalize
from test_issue191_narration import FakeProvider, setup_case
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.narration.campaign import (
    CAP_MICRO_USD,
    STATUS_ATTEMPTED,
    STATUS_CHARGED,
    Ledger,
    default_ledger_path,
)
from vera_timeline_agent.narration.configuration import default_profile
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
)
from vera_timeline_agent.narration.normalize import (
    NORMALIZER_VERSION,
    NormalizationResult,
    Normalizer,
)
from vera_timeline_agent.narration.polly import PollyProvider
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.qualification_output_controller_v2 import (
    _publish,
    _ReceiptVault,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    LANE,
    OutputConsistencyError,
    _canonical,
)
from vera_timeline_agent.roundtrip_build import ROOT, ProofBuildError
from vera_timeline_agent.roundtrip_v2_narration import (
    TEST_LEDGER_ENV,
    ProviderCallRefused,
    campaign_ledger,
)

CAMPAIGN_EVIDENCE = (
    ROOT / "packages/contracts/test/data/issue182-baseline.boundary-evidence.json"
)
CAMPAIGN_DOCUMENT = (
    ROOT / "tests/data/issue182/campaign/baseline.v2.script-document.json"
)


# ------------------------------------------------------------ derived support

GOLDEN = ROOT / "tests/data/issue215/omission-derive-case.json"


def _stub_proof(tmp_path: Path, golden: dict[str, Any]) -> Any:
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    session.root = tmp_path
    session._current = lambda: None
    session.baseline = SimpleNamespace(
        blobs={
            "executionDocumentSha256": _canonical(golden["document"]),
            "executionDependenciesSha256": _canonical(golden["dependencies"]),
        }
    )
    return session


@pytest.mark.slow
def test_python_derives_support_through_the_ts_bridge_and_ts_infer_accepts_it(
    tmp_path: Path,
) -> None:
    golden = json.loads(GOLDEN.read_text())
    session = _stub_proof(tmp_path, golden)
    support = session.derive_omission_support(golden["evidence"])
    assert support == golden["expectedSupport"]
    assert support["schemaVersion"] == "qualification-output-omission-support/v2"
    assert "reviewReceiptSha256" not in support
    evidence = copy.deepcopy(golden["evidence"])
    evidence["cases"][0]["omissionSupport"] = support
    inference = session._pure({"mode": "infer", "evidence": evidence})
    assert inference["omission"]["tokenIds"] == [support["selectedTokenId"]]
    tampered = copy.deepcopy(evidence)
    tampered["cases"][0]["omissionSupport"]["selectedTokenId"] = support[
        "leftNeighborTokenId"
    ]
    with pytest.raises(OutputConsistencyError, match="differs from the record derived"):
        session._pure({"mode": "infer", "evidence": tampered})


# ------------------------------------------------------- fake regeneration lane


class WordProvider(FakeProvider):
    """Fake Polly: word marks at known times over burst audio (measurable)."""

    adapter_version = "issue215-word-provider/v1"

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("uncertain fake provider response")
        words, offset = [], 0
        for word in request.text.split():
            words.append((word, offset))
            offset += len(word) + 1
        bursts = tuple(
            (100 + 400 * i, 400 + 400 * i, 400 + 100 * i) for i in range(len(words))
        )
        raw = pcm_bytes(burst_pcm(bursts, total_ms=200 + 400 * len(words)))
        marks = tuple(
            ProviderTimingMark(
                "word",
                100 + 400 * i,
                start,
                start + len(word),
                start,
                start + len(word),
                word,
            )
            for i, (word, start) in enumerate(words)
        )
        return ProviderResult(
            audio_bytes=raw,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=marks,
            provenance={
                "provider": "issue191_fake",
                "region": "local-test",
                "engine": "fake",
                "voiceId": "fake",
                "voiceVersion": "1",
                "adapterVersion": self.adapter_version,
            },
            request_ids=(f"fake-{self.calls}",),
        )


class HoldNormalizer(Normalizer):
    def __init__(self) -> None:
        super().__init__(profile_id="issue215-fake-normalization")
        self._fingerprint = "sha256:" + "5" * 64

    def _result(self, samples: list[int]) -> NormalizationResult:
        return NormalizationResult(
            wav_bytes(samples),
            self.profile_id,
            NORMALIZER_VERSION,
            self.tool_fingerprint,
            48000,
            1,
            "s16",
            len(samples),
            round(len(samples) / 48),
            0,
            -16.0,
            -6.0,
            1.0,
        )

    def normalize_pcm(
        self, audio_bytes: bytes, *, sample_rate: int, channels: int
    ) -> NormalizationResult:
        raw = [value for (value,) in struct.iter_unpack("<h", audio_bytes)]
        return self._result(hold_normalize(raw))

    def placeholder(self, block_id: str) -> NormalizationResult:
        return self._result([0] * 48000)


@pytest.fixture(autouse=True)
def _allow_tmp_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TEST_LEDGER_ENV, "1")


class Lane:
    object: Any

    def __init__(self, tmp_path: Path, *, fail: bool = False) -> None:
        case, _ = setup_case(tmp_path / "setup")
        self.request = case["request"]
        self.document = case["document"]
        self.prior = case["prior_dependencies"]
        self.provider = WordProvider(fail=fail)
        self.service = self.make_service(tmp_path / "cache")
        self.ledger = Ledger(tmp_path / "ledger" / "ledger.json")
        self.root = tmp_path / "proof"
        self.root.mkdir(mode=0o700)
        vault = tmp_path / "vault"
        session: Any = object.__new__(proof.QualificationOutputProofV2)
        self.object = session
        session.root = self.root
        session.session_pin = {
            "path": str(self.root / "session.json"),
            "sha256": "c" * 64,
        }
        session.baseline = SimpleNamespace(vault=_ReceiptVault(vault))
        stage = {
            "regeneration": {
                "schemaVersion": "qualification-output-regeneration-request/v1",
                "lane": LANE,
                **{k: v for k, v in self.request.items() if k != "schemaVersion"},
            },
            "document": self.document,
            "dependencies": self.prior,
        }
        _publish(self.root / "stage.json", _canonical(stage))
        _publish(
            self.root / "inference-decision.json", _canonical({"outcome": "accept"})
        )
        self.accepted = True
        session._accepted_inference = self._accepted

    def make_service(self, cache: Path) -> NarrationService:
        base = setup_case(cache.parent / "cfg")[0]["service"]
        return NarrationService(
            cache=type(base.cache)(cache),
            provider=self.provider,
            normalizer=HoldNormalizer(),
            config=base.config,
        )

    def _accepted(self) -> dict[str, Any]:
        if not self.accepted:
            raise OutputConsistencyError("inference was rejected or is undecided")
        return {"outcome": "accept"}

    def regenerate(
        self,
        *,
        confirm: bool,
        service: NarrationService | None = None,
        cap_micro_usd: int = CAP_MICRO_USD,
    ) -> Any:
        return self.object.regenerate_row(
            service=service or self.service,
            ledger=self.ledger,
            confirm_provider_call=confirm,
            cap_micro_usd=cap_micro_usd,
        )


def test_unconfirmed_real_call_stops_with_clear_message_and_no_state(
    tmp_path: Path,
) -> None:
    lane = Lane(tmp_path)
    with pytest.raises(ProviderCallRefused, match="--confirm-provider-call"):
        lane.regenerate(confirm=False)
    assert lane.provider.calls == 0
    assert lane.ledger.rows() == []
    assert not (lane.root / "regeneration").exists()


def test_missing_aws_credentials_refuse_before_intent_or_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MissingCredentialsSession:
        def get_credentials(self) -> None:
            return None

        def client(self, *_args: Any, **_kwargs: Any) -> Any:
            pytest.fail("Polly client must not be created without credentials")

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(Session=lambda **_kwargs: MissingCredentialsSession()),
    )
    lane = Lane(tmp_path)
    lane.service.provider = PollyProvider()
    lane.service.config = replace(
        lane.service.config,
        profile=default_profile(),
        pricing_policy=None,
        data_policy_attestation="provider_terms_accepted",
    )

    with pytest.raises(ProviderCallRefused, match="credentials are unavailable"):
        lane.regenerate(confirm=True)

    assert lane.ledger.rows() == []
    assert not (lane.root / "regeneration").exists()
    assert not (lane.service.cache.root / "issue-191-call-intents").exists()


def test_reservation_cap_race_removes_only_the_unsent_intent_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = Lane(tmp_path)
    lane.ledger.append(
        request_hash="sha256:" + "a" * 64,
        block_id="other-block",
        characters=10,
        estimated_cost_usd=2.0,
        request_ids=("prior-call",),
    )
    check = lane.ledger.check
    checks = 0

    def fail_reservation_after_preflight(
        additional_micro_usd: int, cap_micro_usd: int = CAP_MICRO_USD
    ) -> None:
        nonlocal checks
        checks += 1
        if checks == 1:
            return
        check(additional_micro_usd, cap_micro_usd)

    monkeypatch.setattr(lane.ledger, "check", fail_reservation_after_preflight)
    row = next(
        b
        for b in lane.document["activeDraft"]["blocks"]
        if b["id"] == lane.request["blockId"]
    )
    request_hash = lane.service.plan_block(row).request_hash
    intent = (
        lane.service.cache.root
        / "issue-191-call-intents"
        / request_hash[7:]
        / "intent.json"
    )

    with pytest.raises(ProofBuildError):
        lane.regenerate(confirm=True)

    assert checks == 2
    assert lane.provider.calls == 0
    assert len(lane.ledger.rows()) == 1
    assert not intent.exists()

    monkeypatch.setattr(lane.ledger, "check", check)
    retry = Lane(tmp_path / "retry")
    retry.service.cache = lane.service.cache
    retry.ledger = lane.ledger
    handoff = retry.regenerate(confirm=True, cap_micro_usd=10_000_000)
    assert handoff is not None and retry.provider.calls == 1
    assert [row["status"] for row in lane.ledger.rows()] == ["charged", STATUS_CHARGED]


def test_rejected_or_undecided_inference_never_synthesizes(tmp_path: Path) -> None:
    lane = Lane(tmp_path)
    lane.accepted = False
    with pytest.raises(OutputConsistencyError, match="rejected"):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 0 and lane.ledger.rows() == []


def test_manual_handoff_is_still_refused() -> None:
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    with pytest.raises(OutputConsistencyError, match="manual replacement handoff"):
        session.proposal(handoff={"schemaVersion": "issue-189-v2-row-handoff/v1"})


@pytest.mark.slow
def test_accepted_omission_regenerates_whole_row_measures_and_hands_off(
    tmp_path: Path,
) -> None:
    lane = Lane(tmp_path)
    handoff = lane.regenerate(confirm=True)
    assert lane.provider.calls == 1
    rows = lane.ledger.rows()
    assert [row["status"] for row in rows] == [STATUS_CHARGED] and rows[0][
        "requestIds"
    ] == ["fake-1"]
    evidence = handoff["boundaryEvidence"]
    assert evidence["verification"]["method"] == "measured_audio_boundaries/v1"
    assert (
        handoff["reviewArtifactHash"]
        == evidence["verification"]["measurementArtifactHash"]
    )
    assert evidence["audio"]["locator"].startswith("v1/assets/")
    assert [t["quotedText"] for t in evidence["tokens"]] == lane.request["text"].split()
    stage = lane.object._stage()
    assert lane.object._regenerated_handoff(stage) == handoff
    # Replay reuses the retained generation: no second call, no second charge.
    again = lane.regenerate(confirm=False)
    assert (
        again == handoff and lane.provider.calls == 1 and len(lane.ledger.rows()) == 1
    )


@pytest.mark.slow
def test_identical_text_cache_hit_makes_no_call_and_no_charge(tmp_path: Path) -> None:
    lane = Lane(tmp_path)
    # The same request already synthesized (for instance by the #182 campaign).
    row = next(
        b
        for b in lane.document["activeDraft"]["blocks"]
        if b["id"] == lane.request["blockId"]
    )
    lane.service.process_block(row)
    assert lane.provider.calls == 1
    handoff = lane.regenerate(confirm=False)
    assert handoff is not None
    assert lane.provider.calls == 1
    assert lane.ledger.rows() == []


@pytest.mark.slow
def test_uncertain_attempt_is_preserved_and_never_resent(tmp_path: Path) -> None:
    lane = Lane(tmp_path, fail=True)
    row = next(
        b
        for b in lane.document["activeDraft"]["blocks"]
        if b["id"] == lane.request["blockId"]
    )
    request_hash = lane.service.plan_block(row).request_hash
    intent = (
        lane.service.cache.root
        / "issue-191-call-intents"
        / request_hash[7:]
        / "intent.json"
    )
    with pytest.raises(ProofBuildError):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 1
    assert [row["status"] for row in lane.ledger.rows()] == [STATUS_ATTEMPTED]
    assert intent.is_file()
    lane.provider.fail = False
    with pytest.raises(ProviderCallRefused, match="will not be resynthesized"):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 1 and len(lane.ledger.rows()) == 1


@pytest.mark.slow
def test_forged_handoff_without_the_vault_seal_is_refused(tmp_path: Path) -> None:
    lane = Lane(tmp_path)
    lane.regenerate(confirm=True)
    receipt = lane.root / "regeneration" / "handoff-receipt.json"
    receipt.chmod(0o600)
    receipt.write_bytes(receipt.read_bytes().replace(b"stageSha256", b"stageSha257"))
    with pytest.raises(OutputConsistencyError):
        lane.object._regenerated_handoff(lane.object._stage())


@pytest.mark.parametrize("status", ["reserved", STATUS_ATTEMPTED])
def test_uncertain_ledger_row_without_cached_synthesis_is_never_resent(
    tmp_path: Path, status: str
) -> None:
    lane = Lane(tmp_path)
    row = next(
        b
        for b in lane.document["activeDraft"]["blocks"]
        if b["id"] == lane.request["blockId"]
    )
    plan = lane.service.plan_block(row)
    assert not plan.cached
    reservation = lane.ledger.reserve(
        request_hash=plan.request_hash,
        block_id=lane.request["blockId"],
        characters=plan.characters,
        estimated_cost_usd=plan.estimated_cost_usd,
        cap_micro_usd=10**9,
    )
    if status == STATUS_ATTEMPTED:
        lane.ledger.settle(reservation["reservationId"], STATUS_ATTEMPTED)
    with pytest.raises(ProviderCallRefused, match="uncertain earlier attempt"):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 0 and len(lane.ledger.rows()) == 1


def test_only_the_approved_campaign_ledger_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TEST_LEDGER_ENV)
    lane = Lane(tmp_path)
    with pytest.raises(ProviderCallRefused, match="approved campaign ledger"):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 0 and not lane.ledger.path.exists()
    assert campaign_ledger().path == default_ledger_path()
