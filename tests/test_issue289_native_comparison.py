from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "word-timing"))
import issue289_native_comparison as native  # type: ignore[import-not-found]


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _make_take(
    tmp_path: Path,
    *,
    provider: str,
    text: str,
    token_values: list[str],
    response: dict[str, Any],
    duration: float = 2.0,
) -> Path:
    take = tmp_path / f"{provider}-g1-r1"
    take.mkdir()
    tokens = []
    cursor = 0
    for index, value in enumerate(token_values):
        start = text.index(value, cursor)
        end = start + len(value)
        tokens.append(
            {
                "id": f"token-{index}",
                "value": value,
                "startOffset": _utf16_length(text[:start]),
                "endOffset": _utf16_length(text[:end]),
            }
        )
        cursor = end
    request = {
        "provider": provider,
        "takeId": "g1-r1",
        "row": {"text": text, "tokens": tokens},
        "audio": {"durationSeconds": duration},
    }
    (take / "request.private.json").write_text(json.dumps(request), encoding="utf-8")
    (take / "response.raw.json").write_text(json.dumps(response), encoding="utf-8")
    with wave.open(str(take / "audio.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(1000)
        output.writeframes(b"\0\0" * round(duration * 1000))
    return take


def _eleven_response(text: str) -> dict[str, Any]:
    chars = list(text)
    starts = [index / 100 for index in range(len(chars))]
    ends = [value + 0.005 for value in starts]
    return {
        "alignment": {
            "characters": chars,
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends,
        },
        "normalized_alignment": {
            "characters": chars,
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends,
        },
    }


def test_elevenlabs_maps_utf16_offsets_and_keeps_punctuation_overrun_separate(
    tmp_path: Path,
) -> None:
    text = "go 🌍 can\u2019t!"
    response = _eleven_response(text)
    response["alignment"]["character_end_times_seconds"][-1] = 2.2
    take = _make_take(
        tmp_path,
        provider="elevenlabs",
        text=text,
        token_values=["go", "can\u2019t"],
        response=response,
        duration=2.0,
    )

    result = native.analyze_take(take)

    assert [token["startOffset"] for token in result["tokens"]] == [0, 6]
    assert [token["nativeStart"] for token in result["tokens"]] == [0.0, 0.05]
    assert result["outOfBounds"] == 0
    assert result["punctuationOutOfBounds"] == 1
    assert result["structuralPass"] is True
    point_file = (take / native.CSV_NAME).read_bytes()
    assert point_file.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in point_file
    assert point_file.count(b"NOT HUMAN VERIFIED") == 2


def test_inworld_preserves_tied_word_starts(tmp_path: Path) -> None:
    text = "one two"
    response = {
        "timestampInfo": {
            "wordAlignment": {
                "words": ["one", " ", "two"],
                "wordStartTimeSeconds": [0.1, 0.15, 0.1],
                "wordEndTimeSeconds": [0.3, 0.16, 0.4],
            }
        }
    }
    take = _make_take(
        tmp_path,
        provider="inworld",
        text=text,
        token_values=["one", "two"],
        response=response,
    )

    result = native.analyze_take(take)

    assert [token["nativeStart"] for token in result["tokens"]] == [0.1, 0.1]
    assert result["ties"] == 1
    assert result["strictlyIncreasingStarts"] is False
    assert result["structuralPass"] is False


def test_inworld_allows_apostrophe_punctuation_difference_without_rewriting_words(
    tmp_path: Path,
) -> None:
    text = "can\u2019t go"
    response = {
        "timestampInfo": {
            "wordAlignment": {
                "words": ["can't", " ", "go"],
                "wordStartTimeSeconds": [0.1, 0.3, 0.4],
                "wordEndTimeSeconds": [0.3, 0.31, 0.6],
            }
        }
    }
    take = _make_take(
        tmp_path,
        provider="inworld",
        text=text,
        token_values=["can\u2019t", "go"],
        response=response,
    )

    result = native.analyze_take(take)

    assert [token["mappingStatus"] for token in result["tokens"]] == ["exact", "exact"]
    assert result["textMismatchCounts"]["inworld"] == 1
    assert result["coverage"]["exactTokens"] == 2


def test_phrase_alignment_is_not_split_across_canonical_tokens(tmp_path: Path) -> None:
    text = "one two"
    response = {
        "timestampInfo": {
            "wordAlignment": {
                "words": ["one two"],
                "wordStartTimeSeconds": [0.1],
                "wordEndTimeSeconds": [0.8],
            }
        }
    }
    take = _make_take(
        tmp_path,
        provider="inworld",
        text=text,
        token_values=["one", "two"],
        response=response,
    )

    result = native.analyze_take(take)

    assert [token["mappingStatus"] for token in result["tokens"]] == [
        "ambiguous",
        "ambiguous",
    ]
    assert result["coverage"]["exactTokens"] == 0


def test_hash_binding_accepts_prefixed_hashes_and_rejects_changed_audio(
    tmp_path: Path,
) -> None:
    take = _make_take(
        tmp_path,
        provider="elevenlabs",
        text="one two",
        token_values=["one", "two"],
        response=_eleven_response("one two"),
    )
    path = take / "request.private.json"
    request = json.loads(path.read_text())
    request["row"]["textHash"] = "sha256:" + hashlib.sha256(b"one two").hexdigest()
    request["audio"]["sha256"] = (
        "sha256:" + hashlib.sha256((take / "audio.wav").read_bytes()).hexdigest()
    )
    path.write_text(json.dumps(request))
    assert native.analyze_take(take)["structuralPass"] is True
    request["audio"]["sha256"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(request))
    result = native.analyze_take(take)
    assert result["audioHashValid"] is False
    assert result["structuralPass"] is False


def test_reversed_lexical_interval_fails(tmp_path: Path) -> None:
    response = _eleven_response("one two")
    response["alignment"]["character_end_times_seconds"][1] = 0.0
    take = _make_take(
        tmp_path,
        provider="elevenlabs",
        text="one two",
        token_values=["one", "two"],
        response=response,
    )
    result = native.analyze_take(take)
    assert result["invalidIntervals"] > 0
    assert result["structuralPass"] is False


def test_rejected_fish_snapshots_keep_ties_and_chunk_offsets(tmp_path: Path) -> None:
    take = _make_take(
        tmp_path,
        provider="fish",
        text="We can\u2019t. Go now.",
        token_values=["We", "can\u2019t", "Go", "now"],
        response={
            "adapterRejected": True,
            "alignmentSnapshots": [
                {
                    "seq": 0,
                    "content": "We can\u2019t.",
                    "offset": 0,
                    "alignment": {
                        "segments": [
                            {"text": "We", "start": 0.1, "end": 0.2},
                            {"text": "can't", "start": 0.2, "end": 0.4},
                        ]
                    },
                },
                {
                    "seq": 1,
                    "content": "Go now.",
                    "offset": 1,
                    "alignment": {
                        "segments": [
                            {"text": "Go", "start": 0.1, "end": 0.1},
                            {"text": "now", "start": 0.1, "end": 0.4},
                        ]
                    },
                },
            ],
        },
    )
    result = native.analyze_take(take)
    assert result["coverage"]["exactTokens"] == 4
    assert result["tokens"][2]["nativeStart"] == 1.1
    assert result["ties"] == 1
    assert result["collapsed"] == 1
    assert result["structuralPass"] is False


@pytest.mark.parametrize(
    "problem", ["mismatched_text", "array_length", "invalid_times"]
)
def test_elevenlabs_rejects_untrustworthy_alignment_vectors(
    tmp_path: Path, problem: str
) -> None:
    text = "one two"
    response = _eleven_response(text)
    if problem == "mismatched_text":
        response["alignment"]["characters"] = list("one too")
        response["normalized_alignment"]["characters"] = list("one too")
    elif problem == "array_length":
        response["alignment"]["character_start_times_seconds"].pop()
    else:
        response["alignment"]["character_start_times_seconds"][1] = float("nan")
        response["alignment"]["character_end_times_seconds"][2] = float("inf")
    take = _make_take(
        tmp_path,
        provider="elevenlabs",
        text=text,
        token_values=["one", "two"],
        response=response,
    )

    result = native.analyze_take(take)

    assert result["structuralPass"] is False
    if problem == "mismatched_text":
        assert result["textMismatchCounts"] == {"original": 1, "normalized": 1}
        assert result["coverage"]["exactTokens"] == 0
    elif problem == "array_length":
        assert {token["mappingStatus"] for token in result["tokens"]} == {
            "array_length_mismatch"
        }
        assert result["textMismatchCounts"]["original"] == 0
    else:
        assert result["nonFinite"] == 2
        assert result["lexicalNonFinite"] == 2
        saved = json.loads((take / native.OUTPUT_NAME).read_text(encoding="utf-8"))
        assert saved["tokens"][0]["nativeEnd"] is None
        assert saved["tokens"][1]["nativeStart"] is not None
