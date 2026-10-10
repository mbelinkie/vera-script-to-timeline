"""#45 prototype: shared recognizer/aligner ports and conformance (draft #168)."""

from __future__ import annotations

import json
import wave
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import pytest

from experiments.issue45.adapters.local_engines import (
    EngineConfig,
    MfaAligner,
    ParakeetRecognizer,
)
from experiments.issue45.adapters.youtube_captions import (
    YouTubeCaptionRecognizer,
    caption_tokens,
)
from experiments.issue45.artifacts import (
    AudioRef,
    Json,
    RecognizerInfo,
    Token,
    agreement_block,
    content_hash,
    file_hash,
    recognition_artifact,
    schema_errors,
)
from experiments.issue45.conformance import check_alignment, check_pair
from experiments.issue45.fake import FakeAligner, FakeRecognizer
from experiments.issue45.normalize import cardinal, normalise_token, units
from experiments.issue45.ports import (
    Capabilities,
    PortRefusal,
    ProjectPolicy,
    require_cloud_consent,
)
from experiments.issue45.segmentation import assign_units, group_regions

POLICY = ProjectPolicy()


def silent_wav(path: Path, seconds: float = 10.0) -> AudioRef:
    frames = int(16000 * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * frames)
    return AudioRef(path, file_hash(path), 16000, frames)


@pytest.fixture
def audio(tmp_path: Path) -> AudioRef:
    return silent_wav(tmp_path / "a.wav")


@pytest.mark.parametrize(
    ("display", "spoken"),
    [
        ("99", ["ninety", "nine"]),
        ("1998.", ["nineteen", "ninety", "eight"]),
        ("2005", ["two", "thousand", "five"]),
        ("1905", ["nineteen", "oh", "five"]),
        ("1900", ["nineteen", "hundred"]),
        ("105", ["one", "hundred", "five"]),
        ("4", ["four"]),
        ("quote-unquote", ["quote", "unquote"]),
        ("Windows95Man", ["windows", "ninety", "five", "man"]),
        ("\u201cIt\u2019s", ["it's"]),
        ("—", []),
    ],
)
def test_normalise_token(display: str, spoken: list[str]) -> None:
    assert normalise_token(display) == spoken


def test_cardinal_scales() -> None:
    assert cardinal(1_204_013) == [
        "one",
        "million",
        "two",
        "hundred",
        "four",
        "thousand",
        "thirteen",
    ]
    assert cardinal(0) == ["zero"]


def test_units_keep_token_identity() -> None:
    got = [(u.token_index, u.sub, u.text) for u in units(["In", "1998", "—", "yes"])]
    assert got == [
        (0, 0, "in"),
        (1, 0, "nineteen"),
        (1, 1, "ninety"),
        (1, 2, "eight"),
        (3, 0, "yes"),
    ]


def test_fake_pair_is_conformant(audio: AudioRef) -> None:
    rec, ali = FakeRecognizer(["So", "in", "1998", "we", "sang"]), FakeAligner()
    assert check_pair(rec, ali, audio, language="en", policy=POLICY) == []


def test_unaligned_words_keep_null_bounds(audio: AudioRef) -> None:
    rec = FakeRecognizer(["a", "b", "c"]).recognise(audio, language="en", policy=POLICY)
    ali = FakeAligner(unaligned=frozenset({1})).align(audio, rec, policy=POLICY)
    assert check_alignment(audio, rec, ali) == []
    middle = [w for w in ali["words"] if w["tokenIndex"] == 1]
    assert middle == [
        {
            "tokenIndex": 1,
            "sub": 0,
            "text": "b",
            "startMs": None,
            "endMs": None,
            "status": "unaligned",
            "alignerScore": None,
        }
    ]


def test_identity_change_makes_a_new_artifact(audio: AudioRef) -> None:
    a = FakeRecognizer(["a", "b"]).recognise(audio, language="en", policy=POLICY)
    b = FakeRecognizer(["a", "b"], start=0.6).recognise(
        audio, language="en", policy=POLICY
    )
    assert a["artifactId"] != b["artifactId"]
    body = {k: v for k, v in a.items() if k != "artifactId"}
    assert a["artifactId"] == content_hash(body)


class FakeCloudRecognizer(FakeRecognizer):
    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "cloud", "word")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        policy_id = require_cloud_consent(policy, "fake-cloud")
        local = super().recognise(audio, language=language, policy=policy)
        tokens = [
            Token(
                t["display"],
                "word",
                t["anchorStartMs"] / 1000,
                t["anchorEndMs"] / 1000,
                "word",
            )
            for t in local["tokens"]
        ]
        return recognition_artifact(
            audio,
            RecognizerInfo("asr-cloud", "fake-cloud", "m", None),
            tokens,
            language=language,
            consent_policy=policy_id,
        )


def test_cloud_requires_stored_consent(audio: AudioRef) -> None:
    rec = FakeCloudRecognizer(["hello", "there"])
    with pytest.raises(PortRefusal) as refused:
        rec.recognise(audio, language="en", policy=POLICY)
    assert refused.value.code == "consent-missing"
    assert schema_errors(refused.value.record()) == []
    assert (
        check_pair(
            rec,
            FakeAligner(),
            audio,
            language="en",
            policy=ProjectPolicy(cloud_consent_policy_id="project-7/cloud-ok"),
        )
        == []
    )


def test_schema_rejects_cloud_artifact_without_policy(audio: AudioRef) -> None:
    doc = recognition_artifact(
        audio,
        RecognizerInfo("asr-cloud", "p", "m", None),
        [Token("x", "word", 0.1, 0.2, "word")],
        language="en",
        consent_policy=None,
    )
    assert any("policyId" in e for e in schema_errors(doc))


def test_unsupported_language_is_refused(audio: AudioRef) -> None:
    with pytest.raises(PortRefusal) as refused:
        FakeRecognizer(["x"]).recognise(audio, language="ja", policy=POLICY)
    assert refused.value.code == "capability-missing"


JSON3: Json = {
    "events": [
        {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "[Music]"}]},
        {
            "tStartMs": 2000,
            "dDurationMs": 3000,
            "segs": [
                {"utf8": "hi"},
                {"utf8": " I'm", "tOffsetMs": 160},
                {"utf8": " Jo", "tOffsetMs": 400},
            ],
        },
        {"tStartMs": 5000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 6000, "dDurationMs": 1000, "segs": [{"utf8": "bye"}]},
    ]
}


def test_caption_tokens_are_starts_with_derived_ends() -> None:
    toks = caption_tokens(JSON3)
    assert [(t.display, t.kind) for t in toks] == [
        ("[Music]", "event"),
        ("hi", "word"),
        ("I'm", "word"),
        ("Jo", "word"),
        ("bye", "word"),
    ]
    assert (toks[1].start, toks[1].end) == (2.0, 2.16)
    assert (toks[3].start, toks[3].end) == (2.4, 2.9)  # capped at start + 0.5 s
    assert all(t.precision == "word_start_with_derived_end" for t in toks)


def test_caption_recognizer_pairs_conformantly(tmp_path: Path, audio: AudioRef) -> None:
    import json

    path = tmp_path / "x.en.json3"
    path.write_text(json.dumps(JSON3))
    assert (
        check_pair(
            YouTubeCaptionRecognizer(path),
            FakeAligner(),
            audio,
            language="en",
            policy=POLICY,
        )
        == []
    )


def test_group_regions_splits_long_groups_at_widest_gap() -> None:
    regions = [(float(s), float(s) + 4.0) for s in range(0, 40, 5)] + [(41.5, 45.0)]
    segs = group_regions(regions, 50.0)
    assert all(e - s <= 30.0 for s, e in segs)
    assert segs[0][0] == 0.0 and segs[-1][1] <= 50.0
    assert all(a[1] <= b[0] for a, b in pairwise(segs))


def test_assign_units_never_moves_backwards() -> None:
    us = units(["a", "b", "c"])
    segs = assign_units(
        us, [(1.0, 1.2), (12.0, 12.2), (1.5, 1.6)], [(0.0, 10.0), (10.0, 20.0)]
    )
    assert [[u.text for u in s.units] for s in segs] == [["a"], ["b", "c"]]


def test_local_engines_refuse_when_runtime_missing(audio: AudioRef) -> None:
    empty = EngineConfig()
    rec = FakeRecognizer(["a"]).recognise(audio, language="en", policy=POLICY)
    calls: list[Callable[[], Json]] = [
        lambda: ParakeetRecognizer(empty).recognise(
            audio, language="en", policy=POLICY
        ),
        lambda: MfaAligner(empty).align(audio, rec, policy=POLICY),
    ]
    for call in calls:
        with pytest.raises(PortRefusal) as refused:
            call()
        assert refused.value.code == "runtime-missing"
        assert schema_errors(refused.value.record()) == []


def test_agreement_block_flags_disagreement(audio: AudioRef) -> None:
    rec = FakeRecognizer(["a", "b"]).recognise(audio, language="en", policy=POLICY)
    ali = FakeAligner().align(audio, rec, policy=POLICY)
    w0, w1 = ali["words"]
    block = agreement_block(
        ali["words"],
        {(0, 0): (w0["startMs"] + 20, w0["endMs"]), (1, 0): (None, None)},
        {"name": "partner", "version": "1", "parametersHash": content_hash({})},
    )
    verdicts = [(b["tokenIndex"], b["side"], b["verdict"]) for b in block["boundaries"]]
    assert verdicts == [
        (0, "onset", "accepted"),
        (0, "offset", "accepted"),
        (1, "onset", "needs_review"),
        (1, "offset", "needs_review"),
    ]
    assert w1["status"] == "acoustic"


SCRIBE_RAW: Json = {
    "model": "elevenlabs/scribe-v2",
    "words": [
        {"word": "So", "start": 0.6, "end": 0.8, "type": "word", "logprob": -0.1},
        {"word": " ", "start": 0.8, "end": 0.85, "type": "spacing"},
        {"word": "(laughs)", "start": 0.85, "end": 1.2, "type": "audio_event"},
        {"word": "1998", "start": 1.3, "end": 2.0, "type": "word"},
    ],
}


def test_cloud_scribe_needs_consent_and_parses(
    audio: AudioRef, monkeypatch: pytest.MonkeyPatch
) -> None:
    from experiments.issue45.adapters.elevenlabs_cloud import ElevenLabsCloudRecognizer

    sent: list[bytes] = []

    def transport(
        url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> Json:
        sent.append(body)
        return SCRIBE_RAW

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    rec = ElevenLabsCloudRecognizer(transport=transport, keyterms=("Joost",))
    with pytest.raises(PortRefusal) as refused:
        rec.recognise(audio, language="en", policy=POLICY)
    assert refused.value.code == "consent-missing" and not sent
    consented = ProjectPolicy(cloud_consent_policy_id="project-7/cloud-ok")
    assert check_pair(rec, FakeAligner(), audio, language="en", policy=consented) == []
    doc = rec.recognise(audio, language="en", policy=consented)
    assert [(t["display"], t["kind"]) for t in doc["tokens"]] == [
        ("So", "word"),
        ("(laughs)", "event"),
        ("1998", "word"),
    ]
    assert doc["consent"] == {
        "processing": "cloud",
        "policyId": "project-7/cloud-ok",
        "cloudProvider": "elevenlabs",
    }
    assert doc["identity"]["recognizer"]["keytermsHash"] is not None
    assert b"test-key-not-real" not in json.dumps(doc).encode()


def test_cloud_scribe_refuses_without_key(
    audio: AudioRef, monkeypatch: pytest.MonkeyPatch
) -> None:
    from experiments.issue45.adapters.elevenlabs_cloud import ElevenLabsCloudRecognizer

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(PortRefusal) as refused:
        ElevenLabsCloudRecognizer(transport=lambda *a: SCRIBE_RAW).recognise(
            audio, language="en", policy=ProjectPolicy(cloud_consent_policy_id="p")
        )
    assert refused.value.code == "runtime-missing"


SCRIPT = (
    "(on) KAJ [kai] is three Finns, playing up what Swedes think. (off) Ask Tommy Cash."
)
DICTIONARY = "\n".join(
    f"{w} X"
    for w in [
        "is",
        "three",
        "finns",
        "playing",
        "up",
        "what",
        "swedes",
        "swede",
        "fins",
        "think",
        "ask",
        "tommy",
        "cash",
    ]
)


def test_parse_prompter_restart_points_guides_keyterms() -> None:
    from experiments.issue45.script_reconcile import (
        load_dictionary_words,
        parse_prompter,
    )

    p = parse_prompter(SCRIPT, load_dictionary_words(DICTIONARY))
    assert p.restart_points == [0, 9]
    assert [w["display"] for w in p.words if "guide" in w] == ["KAJ"]
    assert "KAJ" in p.keyterms and "Tommy Cash" in p.keyterms
    assert [u.name for u in p.units()][:2] == [True, False]


def test_reconcile_respells_names_only(audio: AudioRef) -> None:
    from experiments.issue45.script_reconcile import reconcile

    heard = [
        "kai",
        "kai",
        "is",
        "three",
        "fins",
        "playing",
        "up",
        "what",
        "swede",
        "think",
    ]
    rec = FakeRecognizer(heard).recognise(audio, language="en", policy=POLICY)
    doc = reconcile(rec, SCRIPT, DICTIONARY)
    assert schema_errors(doc) == []
    by = [(u["heard"], u["text"], u["scriptSpelling"]) for u in doc["units"]]
    assert by[0] == ("kai", "kaj", "KAJ") and by[1] == (
        "kai",
        "kaj",
        "KAJ",
    )  # false start too
    assert ("swede", "swede", None) in by  # real dictionary word: a misreading stays
    assert ("fins", "fins", None) in by  # not a name: never respelled
    assert doc["units"][3]["scriptIndex"] == 2  # "three"
    ali = FakeAligner().align(audio, rec, policy=POLICY, reconciliation=doc)
    assert check_alignment(audio, rec, ali, doc) == []
    assert ali["words"][0]["text"] == "kaj"
    assert ali["identity"]["reconcileArtifactId"] == doc["artifactId"]
    plain = FakeAligner().align(audio, rec, policy=POLICY)
    assert check_alignment(audio, rec, plain, doc)  # wrong pairing is reported
