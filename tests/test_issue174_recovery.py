"""Real-source refusal and immutable-publication recovery for #174."""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from issue174_media_fixture import generate_synthetic_media
from test_issue174_real_media import issue174_descriptor
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    file_hash,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import identity_hash

pytestmark = pytest.mark.slow


@pytest.fixture
def source_case(
    tmp_path: Path,
) -> tuple[Path, dict[str, Any], PreparationAuthorization]:
    source = generate_synthetic_media(tmp_path / "source", frame_count=60).path
    tools = MediaTools()
    inspection = inspect_media(
        source, video_stream_index=0, audio_stream_index=None, tools=tools
    )
    descriptor = issue174_descriptor(inspection, rate=Fraction(25), audio=False)
    authorization = PreparationAuthorization(
        reference="issue-174-recovery",
        read_roots=(source.parent,),
        write_root=tmp_path.resolve() / "prepared",
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    return source, descriptor, authorization


def prepare_case(
    case: tuple[Path, dict[str, Any], PreparationAuthorization],
    *,
    tools: MediaTools | None = None,
    checkpoint: Any = None,
) -> PreparedMedia:
    source, descriptor, authorization = case
    return prepare_media(
        source,
        cast(Any, descriptor),
        cast(
            Any,
            {
                "sourceInFrame": 3010,
                "duration": wire(Fraction(1)),
                "preHandle": wire(Fraction(0)),
                "postHandle": wire(Fraction(0)),
            },
        ),
        cast(Any, wire(Fraction(24000, 1001))),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=None,
        tools=tools,
        checkpoint=checkpoint,
    )


@pytest.mark.parametrize("boundary", ["staged", "verified", "published"])
def test_interruption_reconciliation(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
    boundary: str,
) -> None:
    class Interruption(RuntimeError):
        pass

    retained: list[Path] = []

    def interrupt(stage: str, path: Path) -> None:
        if stage == boundary:
            retained.append(path)
            raise Interruption(stage)

    with pytest.raises(Interruption):
        prepare_case(source_case, checkpoint=interrupt)
    root = source_case[2].write_root
    assert len(list((root / "published").iterdir())) == (
        1 if boundary == "published" else 0
    )
    tools = MediaTools()
    recovered = prepare_case(source_case, tools=tools)
    encoding = [c for c in tools.commands if "libx264" in c and "-c:v" in c]
    assert bool(encoding) == (boundary == "staged")
    assert recovered.reused == (boundary != "staged")
    again = prepare_case(source_case)
    assert again.reused
    assert recovered.binding == again.binding
    assert file_hash(recovered.video_path) == file_hash(again.video_path)


def test_cancel_before_promotion_and_retry(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
) -> None:
    cancel = threading.Event()

    def stop(stage: str, _path: Path) -> None:
        if stage == "verified":
            cancel.set()

    with pytest.raises(MediaPreparationError, match="cancelled"):
        prepare_case(source_case, tools=MediaTools(cancel=cancel), checkpoint=stop)
    assert not list((source_case[2].write_root / "published").iterdir())
    tools = MediaTools()
    result = prepare_case(source_case, tools=tools)
    assert result.reused
    assert not any("-c:v" in c and "libx264" in c for c in tools.commands)


def test_cancel_during_real_ffmpeg_attempt_and_retry(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
) -> None:
    cancel = threading.Event()

    class SlowInputTools(MediaTools):
        def run(self, command: list[str], *, timeout: float = 600) -> bytes:
            if "-c:v" in command and "libx264" in command:
                position = command.index("-i")
                command = [*command[:position], "-readrate", "0.1", *command[position:]]
            return super().run(command, timeout=timeout)

    timer = threading.Timer(0.3, cancel.set)

    def start_timer(stage: str, _path: Path) -> None:
        if stage == "staged":
            timer.start()

    try:
        with pytest.raises(MediaPreparationError, match="cancelled"):
            prepare_case(
                source_case, tools=SlowInputTools(cancel=cancel), checkpoint=start_timer
            )
    finally:
        timer.cancel()
    root = source_case[2].write_root
    assert not list((root / "published").iterdir())
    assert len(list((root / "attempts").iterdir())) == 1
    retried = prepare_case(source_case)
    assert not retried.reused
    assert retried.receipt_path.exists()


def test_receipt_without_verification_marker_is_incomplete(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
) -> None:
    class Interruption(RuntimeError):
        pass

    def interrupt(stage: str, path: Path) -> None:
        if stage == "staged":
            (path / "receipt.json").write_text("{}")
            raise Interruption

    with pytest.raises(Interruption):
        prepare_case(source_case, checkpoint=interrupt)
    assert prepare_case(source_case).receipt_path.exists()


@pytest.mark.parametrize("filename", ["picture.mp4", "receipt.json"])
def test_corruption_preserved_and_refused(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
    filename: str,
) -> None:
    result = prepare_case(source_case)
    damaged = result.receipt_path.parent / filename
    damaged.write_bytes(b"corrupt artifact")
    with pytest.raises(MediaPreparationError):
        prepare_case(source_case)
    assert damaged.read_bytes() == b"corrupt artifact"
    assert len(list((source_case[2].write_root / "published").iterdir())) == 1


def test_busy_requirement_does_not_compete_or_publish(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
) -> None:
    def compete(stage: str, _path: Path) -> None:
        if stage == "staged":
            with pytest.raises(MediaPreparationError, match="preparation_busy"):
                prepare_case(source_case)

    result = prepare_case(source_case, checkpoint=compete)
    assert result.receipt_path.exists()
    assert len(list((source_case[2].write_root / "published").iterdir())) == 1


@pytest.mark.parametrize(
    "changed", ["content", "probe", "origin", "bounds", "rate", "schema"]
)
def test_stale_descriptor_refused_before_attempt(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
    changed: str,
) -> None:
    source, original, auth = source_case
    descriptor = copy.deepcopy(original)
    if changed == "content":
        descriptor["sourceSnapshot"]["contentHash"] = "sha256:" + "0" * 64
    elif changed == "probe":
        descriptor["sourceSnapshot"]["probeHash"] = "sha256:" + "0" * 64
    elif changed == "origin":
        descriptor["sourceFrameMap"]["packageVideoPtsOrigin"] = wire(Fraction(2))
    elif changed == "bounds":
        descriptor["logicalSourceBounds"]["endFrame"] += 100
    elif changed == "rate":
        descriptor["sourceFrameMap"]["decodedPackageFrameRate"] = wire(Fraction(30))
    else:
        descriptor["unrecognized"] = True
    with pytest.raises(MediaPreparationError):
        prepare_case((source, descriptor, auth))
    assert not (auth.write_root / "attempts").exists()


@pytest.mark.parametrize(
    "changed", ["tools", "profile", "policy", "disk", "reuse_only", "read_root"]
)
def test_authorization_preflight_refusals(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
    changed: str,
) -> None:
    source, descriptor, auth = source_case
    if changed == "tools":
        auth = replace(auth, tool_hash="sha256:" + "0" * 64)
    elif changed == "profile":
        auth = replace(auth, profile_hash="sha256:" + "0" * 64)
    elif changed == "policy":
        auth = replace(auth, policy_hash="sha256:" + "0" * 64)
    elif changed == "disk":
        auth = replace(auth, minimum_free_bytes=2**63)
    elif changed == "reuse_only":
        auth = replace(auth, allow_conversion=False)
    else:
        auth = replace(auth, read_roots=(source.parent / "wrong",))
    with pytest.raises(MediaPreparationError):
        prepare_case((source, descriptor, auth))
    assert not (auth.write_root / "attempts").exists() or not list(
        (auth.write_root / "attempts").iterdir()
    )


def test_reuse_only_and_level_build_authorization_reuse_exact_key(
    source_case: tuple[Path, dict[str, Any], PreparationAuthorization],
) -> None:
    first = prepare_case(source_case)
    source, descriptor, auth = source_case
    next_auth = replace(
        auth, reference="different-build-level-only", allow_conversion=False
    )
    next_result = prepare_case((source, descriptor, next_auth))
    assert next_result.reused
    assert next_result.binding["requirementKey"] == first.binding["requirementKey"]
    assert next_result.binding["authorizationReference"] == next_auth.reference
    record = json.loads(first.receipt_path.read_bytes())
    assert record["binding"]["authorizationReference"] == auth.reference
