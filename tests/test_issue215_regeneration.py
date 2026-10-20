"""#215 whole-row regeneration: machine omission support, ledger-guarded fake synthesis.

Fake providers only: no AWS, no Resolve, nothing outside tmp_path.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue182_fixture import burst_pcm, pcm_bytes, wav_bytes
from issue182_fixture import normalize as hold_normalize
from test_issue191_narration import FakeProvider, setup_case
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.narration.campaign import (
    STATUS_ATTEMPTED,
    STATUS_CHARGED,
    Ledger,
)
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
from vera_timeline_agent.roundtrip_v2_narration import ProviderCallRefused

CAMPAIGN_EVIDENCE = (
    ROOT / "packages/contracts/test/data/issue182-baseline.boundary-evidence.json"
)
CAMPAIGN_DOCUMENT = (
    ROOT / "tests/data/issue182/campaign/baseline.v2.script-document.json"
)


# ------------------------------------------------------------ derived support


def _geometry(
    cut: tuple[int, int], origins: tuple[int, int] = (0, 0)
) -> dict[str, Any]:
    document = json.loads(CAMPAIGN_DOCUMENT.read_text())
    evidence = json.loads(CAMPAIGN_EVIDENCE.read_text())
    row = document["activeDraft"]["blocks"][0]
    frames = -(-evidence["audio"]["durationSamples"] // 2002)

    def item(uid: str, start: int, duration: int, source_start: int) -> dict[str, Any]:
        return {
            "itemUid": uid,
            "eventId": "event-narration",
            "sourceId": "source-pcm",
            "recordStart": start,
            "recordDuration": duration,
            "sourceStart": source_start,
            "sourceDuration": duration,
        }

    before = {"geometry": {"items": [item("whole", 0, frames, 0)]}}
    after = {
        "geometry": {
            "items": [
                item("left", 0, cut[0], 0),
                item("right", cut[1], frames - cut[1], cut[1]),
            ]
        }
    }
    entry = {
        "sourceId": "source-pcm",
        "nativeFrameOrigin": origins[0],
        "pcmSampleOrigin": origins[1],
        "sampleRate": 48000,
        "durationSamples": evidence["audio"]["durationSamples"],
        "pcmMode": "prepared-audio",
        "pcmFileSha256": "0" * 64,
    }
    return {
        "case_id": "C",
        "document": document,
        "dependencies": {"narrationBoundaryEvidence": [evidence]},
        "manifest": {
            "events": [
                {
                    "kind": "narration",
                    "eventId": "event-narration",
                    "provenance": {"blockId": row["id"]},
                }
            ]
        },
        "document_hash": "sha256:" + "a" * 64,
        "dependencies_hash": "sha256:" + "b" * 64,
        "pristine_geometry": _canonical(before),
        "edited_geometry": _canonical(after),
        "pristine_binding": _canonical({"sourceEntries": [entry]}),
        "edited_binding": _canonical({"sourceEntries": [entry]}),
        "pristine_comparison": b"pristine-comparison",
        "edited_comparison": b"edited-comparison",
        "pair_json": b"pair",
        "_row": row,
    }


def _derive(cut: tuple[int, int], origins: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    inputs = _geometry(cut, origins)
    row = inputs.pop("_row")
    support = proof.derive_omission_support_v2(**inputs)
    assert support["blockId"] == row["id"]
    return support


def test_support_is_derived_from_measured_evidence_without_review_or_token_index() -> (
    None
):
    support = _derive((55, 72))
    row = json.loads(CAMPAIGN_DOCUMENT.read_text())["activeDraft"]["blocks"][0]
    # Campaign "slowly" (token 8) with the TS bridge's envelopes for this cut.
    assert support["selectedTokenId"] == row["tokens"][8]["id"]
    assert support["leftNeighborTokenId"] == row["tokens"][7]["id"]
    assert support["rightNeighborTokenId"] == row["tokens"][9]["id"]
    assert support["cutStartEnvelope"] == {"minSample": 106555, "maxSample": 112795}
    assert support["cutEndEnvelope"] == {"minSample": 140635, "maxSample": 146971}
    assert support["cutSamples"] == {"startSample": 110110, "endSample": 144144}
    assert support["schemaVersion"] == "qualification-output-omission-support/v2"
    assert "reviewReceiptSha256" not in support


def test_sample_origins_come_from_the_bound_pcm_entry() -> None:
    support = _derive((58, 75), origins=(3, 37))
    assert support["cutSamples"] == {"startSample": 110147, "endSample": 144181}
    assert support["nativeFrameOrigin"] == 3 and support["pcmSampleOrigin"] == 37


@pytest.mark.parametrize(
    ("cut", "message"),
    [
        ((40, 72), "neighbour-straddling"),
        ((55, 90), "neighbour-straddling"),
        ((59, 72), "neighbour-straddling"),
    ],
)
def test_partial_or_straddling_cut_refuses(cut: tuple[int, int], message: str) -> None:
    with pytest.raises(OutputConsistencyError, match=message):
        _derive(cut)


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
        self, *, confirm: bool, service: NarrationService | None = None
    ) -> Any:
        return self.object.regenerate_row(
            service=service or self.service,
            ledger=self.ledger,
            confirm_provider_call=confirm,
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
    with pytest.raises(ProofBuildError):
        lane.regenerate(confirm=True)
    assert lane.provider.calls == 1
    assert [row["status"] for row in lane.ledger.rows()] == [STATUS_ATTEMPTED]
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
