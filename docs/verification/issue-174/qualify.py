"""Create new, hash-pinned synthetic qualification artifacts; never read originals."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(REPOSITORY / "tests"))

from issue174_media_fixture import (  # noqa: E402
    decode_frame_ordinals,
    generate_synthetic_media,
)
from test_issue174_real_media import (  # noqa: E402
    _decoded_audio_samples,
    _decoded_flash_indices,
    assert_compiler_binding,
    issue174_descriptor,
    measure_issue174_sync,
)
from vera_timeline_agent.media_preparation import (  # noqa: E402
    TARGET,
    MediaTools,
    PreparationAuthorization,
    file_hash,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import identity_hash  # noqa: E402


def make_case(
    root: Path,
    name: str,
    *,
    rate: Fraction,
    count: int = 100,
    in_frame: int = 3,
    duration: Fraction = Fraction(1001, 400),
    markers: tuple[int, ...] = (),
    audio_rate: int | None = None,
    audio_codec: Literal["aac", "pcm_s24le"] = "pcm_s24le",
    audio_channels: int = 1,
    target: Fraction = TARGET,
) -> dict[str, Any]:
    case = root / name
    case.mkdir()
    with tempfile.TemporaryDirectory(prefix="issue174-synthetic-") as scratch:
        generated = generate_synthetic_media(
            Path(scratch),
            extension=".mov" if audio_rate and audio_codec == "pcm_s24le" else ".mp4",
            rate=rate,
            frame_count=count,
            start_pts=Fraction(2),
            flash_frames=markers,
            audio_sample_rate=audio_rate or 48000,
            audio_channels=audio_channels,
            mux_audio=audio_codec if audio_rate else None,
        )
        generated_path = generated.muxed_path or generated.path
        source = case / ("source" + generated_path.suffix)
        tools = MediaTools()
        shutil.copyfile(generated_path, source)
        generation = {
            "commands": [list(command) for command in generated.commands]
            + tools.commands,
            "generatorHashes": generated.hashes,
            "flashFrames": list(markers),
            "clickSamples": list(generated.click_samples),
        }
    inspection = inspect_media(
        source,
        video_stream_index=0,
        audio_stream_index=1 if audio_rate else None,
        tools=tools,
    )
    descriptor = cast(
        Any,
        issue174_descriptor(
            inspection,
            rate=rate,
            audio=audio_rate is not None,
            in_frame=3000 + in_frame,
        ),
    )
    request = cast(
        Any,
        {
            "sourceInFrame": 3000 + in_frame,
            "duration": wire(duration),
            "preHandle": wire(Fraction(0)),
            "postHandle": wire(Fraction(0)),
        },
    )
    tool_hash = identity_hash(tools.fingerprint())
    authorization = PreparationAuthorization(
        reference="issue-174-synthetic-qualification",
        read_roots=(case,),
        write_root=case / "prepared",
        tool_hash=tool_hash,
        minimum_free_bytes=64 * 1024 * 1024,
    )
    prepared = prepare_media(
        source,
        descriptor,
        request,
        cast(Any, wire(target)),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=1 if audio_rate else None,
        tools=tools,
    )
    observed = decode_frame_ordinals(prepared.video_path)
    frame_count = math.ceil(duration * target)
    expected = tuple(
        in_frame
        + (j * rate.numerator * target.denominator)
        // (rate.denominator * target.numerator)
        for j in range(frame_count)
    )
    if rate == target:
        assert observed == tuple(range(count))
    else:
        assert observed == expected
    assert all(Fraction(index - in_frame, 1) / rate < duration for index in expected)
    repeated = prepare_media(
        source,
        descriptor,
        request,
        cast(Any, wire(target)),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=1 if audio_rate else None,
    )
    assert repeated.reused and repeated.binding == prepared.binding
    with tempfile.TemporaryDirectory(prefix="issue174-independent-repeat-") as repeat:
        independent = prepare_media(
            source,
            descriptor,
            request,
            cast(Any, wire(target)),
            authorization=PreparationAuthorization(
                reference=authorization.reference,
                read_roots=authorization.read_roots,
                write_root=Path(repeat).resolve(),
                tool_hash=tool_hash,
                minimum_free_bytes=authorization.minimum_free_bytes,
            ),
            video_stream_index=0,
            audio_stream_index=1 if audio_rate else None,
        )
        assert file_hash(independent.video_path) == file_hash(prepared.video_path)
        repeat_video_hash = file_hash(independent.video_path)
        repeat_audio_hash = (
            file_hash(independent.audio_path) if independent.audio_path else None
        )
        assert repeat_audio_hash == (
            file_hash(prepared.audio_path) if prepared.audio_path else None
        )
    record = json.loads(prepared.receipt_path.read_bytes())
    result: dict[str, Any] = {
        "case": name,
        "source": str(source.relative_to(root)),
        "sourceHash": file_hash(source),
        "generation": generation,
        "toolHash": tool_hash,
        "descriptor": descriptor,
        "requestedRange": request,
        "receipt": str(prepared.receipt_path.relative_to(root)),
        "receiptHash": file_hash(prepared.receipt_path),
        "video": str(prepared.video_path.relative_to(root)),
        "videoHash": file_hash(prepared.video_path),
        "expectedSelectedOrdinals": list(expected),
        "decodedOrdinals": list(observed),
        "exactReusePassed": True,
        "independentRepeatVideoHash": repeat_video_hash,
        "independentRepeatAudioHash": repeat_audio_hash,
        "geometry": record["geometry"],
        "audio": record["audio"],
    }
    if prepared.audio_path:
        assert audio_rate and inspection.audio_origin is not None
        if markers:
            measurements = measure_issue174_sync(
                source_samples=_decoded_audio_samples(
                    source, stream_index=1, sample_rate=audio_rate
                ),
                source_sample_rate=audio_rate,
                source_audio_origin=inspection.audio_origin,
                output_start=inspection.pts_origin + Fraction(in_frame, 1) / rate,
                output_audio_path=prepared.audio_path,
                click_samples=generated.click_samples,
                source_path=source,
            )
            assert measurements["maxResidualMilliseconds"] <= 1
            assert measurements["driftMilliseconds"] <= 1
            result["syncMeasurements"] = measurements
            flashes = _decoded_flash_indices(prepared.video_path)
            assert flashes == tuple(expected.index(marker) for marker in markers)
            result["decodedFlashIndices"] = flashes
        result["audioPath"] = str(prepared.audio_path.relative_to(root))
        result["audioHash"] = file_hash(prepared.audio_path)
        if (duration * rate).denominator == 1:
            result["compilerBindingProbe"] = assert_compiler_binding(
                descriptor, cast(dict[str, Any], prepared.binding)
            )
        preview = case / "operator-pair.mkv"
        # Stream-copy a synthetic viewing container; the canonical pair stays unchanged.
        preview_command = [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(prepared.video_path),
            "-i",
            str(prepared.audio_path),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c",
            "copy",
            str(preview),
        ]
        tools.run(preview_command)
        result["operatorPair"] = str(preview.relative_to(root))
        result["operatorPairHash"] = file_hash(preview)
        result["operatorPairCommand"] = preview_command
    with (case / "case.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, type=Path, help="new directory; must not exist"
    )
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = [
        make_case(output, name, rate=rate)
        for name, rate in (
            ("23976-reuse", TARGET),
            ("24-convert", Fraction(24)),
            ("25-convert", Fraction(25)),
            ("2997-convert", Fraction(30000, 1001)),
            ("30-convert", Fraction(30)),
        )
    ]
    cases.append(
        make_case(
            output,
            "50-reuse",
            rate=Fraction(50),
            target=Fraction(50),
            duration=Fraction(1),
        )
    )
    for codec in ("aac", "pcm_s24le"):
        for sample_rate, channels in ((44100, 1), (44100, 2), (48000, 1), (48000, 2)):
            cases.append(
                make_case(
                    output,
                    f"{codec}-{sample_rate}-{channels}-convert",
                    rate=Fraction(25),
                    count=330,
                    in_frame=10,
                    duration=Fraction(10),
                    markers=(10, 135, 259),
                    audio_rate=sample_rate,
                    audio_codec=cast(Literal["aac", "pcm_s24le"], codec),
                    audio_channels=channels,
                )
            )
    cases.append(
        make_case(
            output,
            "sync-grid",
            rate=Fraction(25),
            count=2003,
            in_frame=0,
            duration=Fraction(2003, 25),
            markers=(0, 1001, 2002),
            audio_rate=48000,
        )
    )
    with (output / "qualification.json").open("x") as stream:
        json.dump(
            {
                "recordVersion": "issue-174-installed-tool-qualification/v1",
                "cases": cases,
                "caseRecordHashes": {
                    case["case"]: file_hash(output / case["case"] / "case.json")
                    for case in cases
                },
                "implementationSourceHash": file_hash(
                    REPOSITORY / "python/vera_timeline_agent/media_preparation.py"
                ),
                "fixtureSourceHash": file_hash(
                    REPOSITORY / "tests/issue174_media_fixture.py"
                ),
                "qualifierSourceHash": file_hash(Path(__file__)),
                "matrixSourceHash": file_hash(
                    REPOSITORY / "tests/test_issue174_real_media.py"
                ),
                "compilerProbeHash": file_hash(
                    Path(__file__).with_name("compiler-binding-probe.mjs")
                ),
                "humanVisualAudibleAcceptance": "pending",
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(
        f"Measured {len(cases)} synthetic cases in {output}; "
        "visual/audible operator review pending."
    )


if __name__ == "__main__":
    main()
