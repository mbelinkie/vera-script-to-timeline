"""Real-media preparation refusals and restart behavior for Issue 178."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from issue174_media_fixture import generate_synthetic_media
from issue178_qualification_fixture import (
    _COMPILER_CLI,
    _NODE,
    QualificationCase,
)
from test_issue174_real_media import issue174_descriptor
from vera_timeline_agent.media_preparation import (
    TARGET,
    MediaPreparationError,
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    file_hash,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.v2_package import (
    MEDIA_DIRECTORY,
    V2PackageError,
    verify_v2_package,
)

Json = dict[str, Any]
_SOURCE_ORIGIN_FRAME = 3000


class _InjectedInterruption(RuntimeError):
    pass


def _context(
    source: Path,
    write_root: Path,
    *,
    descriptor_source: Path | None = None,
    rate: Fraction = Fraction(25),
) -> tuple[Json, PreparationAuthorization, MediaTools]:
    tools = MediaTools()
    inspected = inspect_media(
        descriptor_source or source,
        video_stream_index=0,
        audio_stream_index=None,
        tools=tools,
    )
    descriptor = issue174_descriptor(
        inspected, rate=rate, audio=False, in_frame=_SOURCE_ORIGIN_FRAME + 10
    )
    authorization = PreparationAuthorization(
        reference="issue-178-refusal-recovery",
        read_roots=(source.parent.resolve(),),
        write_root=write_root.resolve(),
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    return descriptor, authorization, tools


def _request(
    *,
    source_in_frame: int = _SOURCE_ORIGIN_FRAME + 10,
    duration: Fraction = Fraction(1),
) -> Json:
    return {
        "sourceInFrame": source_in_frame,
        "duration": wire(duration),
        "preHandle": wire(Fraction(0)),
        "postHandle": wire(Fraction(0)),
    }


def _prepare(
    source: Path,
    descriptor: Json,
    authorization: PreparationAuthorization,
    tools: MediaTools,
    *,
    request: Json | None = None,
    checkpoint: Callable[[str, Path], None] | None = None,
) -> PreparedMedia:
    return prepare_media(
        source,
        cast(Any, descriptor),
        cast(Any, request or _request()),
        cast(Any, wire(TARGET)),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=None,
        tools=tools,
        checkpoint=checkpoint,
    )


def _expect_refusal(operation: Callable[[], object], expected_code: str) -> Json:
    try:
        operation()
    except MediaPreparationError as error:
        if error.code != expected_code:
            raise AssertionError(
                f"expected {expected_code}, received {error.code}"
            ) from error
        return {"status": "refused", "code": error.code}
    raise AssertionError(f"expected preparation refusal: {expected_code}")


def _has_video_encode(tools: MediaTools) -> bool:
    return any("-c:v" in command and "libx264" in command for command in tools.commands)


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _write_result(path: Path, result: Json) -> None:
    temporary = path.with_suffix(".tmp")
    raw = json.dumps(
        result, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
    )
    with temporary.open("wb") as stream:
        stream.write((raw + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _no_attempts(authorization: PreparationAuthorization) -> bool:
    attempts = authorization.write_root / "attempts"
    return not attempts.exists() or not any(attempts.iterdir())


def _compile(
    document_path: Path, dependencies_path: Path
) -> tuple[subprocess.CompletedProcess[bytes], Json]:
    environment = {"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)}
    compiled = subprocess.run(
        [str(_NODE), str(_COMPILER_CLI), str(document_path), str(dependencies_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env=environment,
    )
    if compiled.stderr:
        raise AssertionError(
            "semantic refusal check emitted compiler stderr: "
            + compiled.stderr.decode("utf-8", errors="replace")
        )
    envelope = cast(Json, json.loads(compiled.stdout))
    return compiled, cast(Json, envelope["result"])


def run_package_refusals(case: QualificationCase, root: Path) -> Json:
    """Check package-byte and semantic-anchor refusals against one accepted case."""
    if not isinstance(case, QualificationCase):
        raise ValueError("an existing issue 178 qualification case is required")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("absolute package refusal root required")
    if root.is_symlink():
        raise ValueError("package refusal root must not be a symlink")
    root = root.resolve(strict=False)
    output_root = root / "issue178-package-refusals"
    output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    result_path = output_root / "result.json"
    result: Json = {
        "schemaVersion": "issue178-package-refusals/v1",
        "status": "running",
        "cases": {},
        "resultPath": str(result_path),
    }
    _write_result(result_path, result)

    # Tamper a copy so the accepted QualificationCase remains reusable.
    source = next(
        item
        for item in case.manifest["sources"]
        if item.get("preparationRequirementKey") is not None
    )
    requirement_key = source["preparationRequirementKey"]
    prepared = next(
        item
        for item in case.preparations.values()
        if item.binding["requirementKey"] == requirement_key
    )
    if prepared.binding["mode"] != "derived_cfr":
        raise AssertionError("wrong-derived-bytes case requires derived CFR media")
    source_path = (
        case.package_root
        / MEDIA_DIRECTORY
        / "Resolved"
        / f"{source['id']}{prepared.video_path.suffix}"
    )
    package_copy = output_root / "wrong-derived-bytes-package"
    shutil.copytree(case.package_root, package_copy)
    tampered_path = (
        package_copy
        / MEDIA_DIRECTORY
        / "Resolved"
        / f"{source['id']}{prepared.video_path.suffix}"
    )
    original_hash = file_hash(source_path)
    tampered_bytes = bytearray(tampered_path.read_bytes())
    if not tampered_bytes:
        raise AssertionError("packaged derived video is unexpectedly empty")
    tampered_bytes[0] ^= 1
    tampered_path.write_bytes(tampered_bytes)
    tampered_hash = file_hash(tampered_path)
    try:
        verify_v2_package(package_copy)
    except V2PackageError as error:
        detail = str(error)
        if "package file hash mismatch" not in detail:
            raise AssertionError(
                f"expected derived-byte hash refusal, received: {detail}"
            ) from error
    else:
        raise AssertionError("tampered derived package bytes were accepted")
    if tampered_hash == original_hash or file_hash(source_path) != original_hash:
        raise AssertionError(
            "derived-byte tampering changed or matched the source case"
        )

    # Keep hashes and media untouched; change only the dependency's semantic
    # source selection so the compiler must reject the stale occurrence anchor.
    anchor_root = output_root / "stale-occurrence-anchor"
    anchor_root.mkdir(mode=0o700)
    document_path = anchor_root / "script-document-v2.json"
    dependencies_path = anchor_root / "compiler-dependencies-v2.json"
    shutil.copyfile(case.document_path, document_path)
    dependencies = cast(Json, json.loads(case.dependencies_path.read_bytes()))
    occurrence = next(
        item
        for item in dependencies["occurrenceResolutions"]
        if isinstance(item.get("selectedSourceRange"), dict)
    )
    occurrence["selectedSourceRange"]["startFrame"] += 1
    dependencies_path.write_bytes(canonical_json_bytes(dependencies))
    compiled, compile_result = _compile(document_path, dependencies_path)
    diagnostics = compile_result.get("diagnostics", [])
    stale_occurrence = next(
        (
            item
            for item in diagnostics
            if item.get("code") == "MISSING_OCCURRENCE_BINDING"
        ),
        None,
    )
    if (
        compiled.returncode == 0
        or compile_result.get("ok") is not False
        or not stale_occurrence
    ):
        raise AssertionError(
            "compiler did not report the stale selected-occurrence binding"
        )

    # Use the existing compiler golden to exercise word-anchor semantics without
    # generating another media fixture. The unknown token ID makes the authored
    # word anchor stale while leaving its timing evidence untouched.
    word_anchor_root = output_root / "stale-word-anchor"
    word_anchor_root.mkdir(mode=0o700)
    word_anchor_golden = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "tests/data/authoring_v2/issue_173/compiler"
            / "root-child-overlay-return.input.golden.json"
        ).read_bytes()
    )
    word_anchor_document = cast(Json, word_anchor_golden["document"])
    word_anchor_dependencies = cast(Json, word_anchor_golden["dependencies"])
    returned = next(
        slot
        for slot in word_anchor_document["activeDraft"]["blocks"][0][
            "primaryVisualSequence"
        ]["slots"]
        if slot.get("kind") == "return"
    )
    returned["inpoint"]["tokenId"] = "00000000-0000-4000-8000-0000000000ff"
    word_document_path = word_anchor_root / "script-document-v2.json"
    word_dependencies_path = word_anchor_root / "compiler-dependencies-v2.json"
    word_document_path.write_bytes(canonical_json_bytes(word_anchor_document))
    word_dependencies_path.write_bytes(canonical_json_bytes(word_anchor_dependencies))
    word_compiled, word_compile_result = _compile(
        word_document_path, word_dependencies_path
    )
    word_diagnostics = word_compile_result.get("diagnostics", [])
    stale_word = next(
        (item for item in word_diagnostics if item.get("code") == "STALE_WORD_ANCHOR"),
        None,
    )
    if (
        word_compiled.returncode == 0
        or word_compile_result.get("ok") is not False
        or not stale_word
    ):
        raise AssertionError("compiler did not report STALE_WORD_ANCHOR")

    cases = cast(Json, result["cases"])
    cases["wrongDerivedBytes"] = {
        "status": "refused",
        "code": "package_file_hash_mismatch",
        "detail": detail,
        "tamperedSha256": tampered_hash,
        "acceptedSha256Preserved": original_hash,
    }
    cases["staleOccurrenceSelection"] = {
        "status": "refused",
        "code": "MISSING_OCCURRENCE_BINDING",
        "stage": "compiler_semantics",
        "message": stale_occurrence.get("message"),
    }
    cases["staleWordAnchor"] = {
        "status": "refused",
        "code": "STALE_WORD_ANCHOR",
        "stage": "compiler_semantics",
        "message": stale_word.get("message"),
    }
    result["status"] = "passed"
    _write_result(result_path, result)
    return result


def run_refusal_recovery(root: Path) -> Json:
    """Run real 24000/1001 preparation refusals and immutable recovery checks.

    Writes only below the caller-provided fresh root and retains a compact JSON
    receipt alongside generated inputs and preparation artifacts.
    """
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("absolute refusal/recovery root required")
    if root.is_symlink():
        raise ValueError("refusal/recovery root must not be a symlink")
    root = root.resolve(strict=False)
    output_root = root / "issue178-refusal-recovery"
    output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    result_path = output_root / "result.json"
    result: Json = {
        "schemaVersion": "issue178-media-refusal-recovery/v1",
        "status": "running",
        "targetRate": wire(TARGET),
        "cases": {},
        "resultPath": str(result_path),
    }
    _write_result(result_path, result)

    media_root = output_root / "media"
    source_25 = generate_synthetic_media(
        media_root / "source-25fps",
        rate=Fraction(25),
        frame_count=60,
        flash_frames=(0, 30, 59),
    )
    source_50 = generate_synthetic_media(
        media_root / "source-50fps",
        rate=Fraction(50),
        frame_count=120,
        flash_frames=(0, 60, 119),
    )
    result["sources"] = {
        "25fps": {
            "path": _relative(output_root, source_25.path),
            "sha256": file_hash(source_25.path),
        },
        "50fps": {
            "path": _relative(output_root, source_50.path),
            "sha256": file_hash(source_50.path),
        },
    }
    _write_result(result_path, result)

    # Keep the container's nominal CFR labels while introducing a real PTS gap.
    vfr_path = media_root / "source-vfr.mkv"
    vfr_tools = MediaTools()
    vfr_tools.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(source_25.path),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "settb=1/1000,setpts=PTS+if(eq(N\\,17)\\,20\\,0)",
            "-enc_time_base",
            "1:1000",
            "-fps_mode",
            "passthrough",
            str(vfr_path),
        ]
    )

    cases = cast(Json, result["cases"])
    vfr_descriptor, vfr_auth, vfr_prepare_tools = _context(
        vfr_path,
        output_root / "prepared-vfr",
        descriptor_source=source_25.path,
        rate=Fraction(25),
    )
    cases["vfr"] = _expect_refusal(
        lambda: _prepare(vfr_path, vfr_descriptor, vfr_auth, vfr_prepare_tools),
        "unsupported_vfr_or_timebase",
    )
    cases["vfr"]["noAttemptPublished"] = _no_attempts(vfr_auth)
    if not cases["vfr"]["noAttemptPublished"]:
        raise AssertionError("VFR refusal left a preparation attempt")

    unsupported_descriptor, unsupported_auth, unsupported_tools = _context(
        source_50.path,
        output_root / "prepared-50fps",
        rate=Fraction(50),
    )
    cases["unhandled50fps"] = _expect_refusal(
        lambda: _prepare(
            source_50.path, unsupported_descriptor, unsupported_auth, unsupported_tools
        ),
        "unsupported_conversion",
    )
    cases["unhandled50fps"]["noAttemptPublished"] = _no_attempts(unsupported_auth)
    if not cases["unhandled50fps"]["noAttemptPublished"]:
        raise AssertionError("unsupported conversion left a preparation attempt")

    short_descriptor, short_auth, short_tools = _context(
        source_25.path, output_root / "prepared-short", rate=Fraction(25)
    )
    cases["shortSource"] = _expect_refusal(
        lambda: _prepare(
            source_25.path,
            short_descriptor,
            short_auth,
            short_tools,
            request=_request(source_in_frame=_SOURCE_ORIGIN_FRAME + 59),
        ),
        "source_shortage",
    )
    cases["shortSource"]["noAttemptPublished"] = _no_attempts(short_auth)
    if not cases["shortSource"]["noAttemptPublished"]:
        raise AssertionError("short-source refusal left a preparation attempt")

    wrong_descriptor, wrong_auth, wrong_tools = _context(
        source_50.path,
        output_root / "prepared-wrong-original",
        descriptor_source=source_25.path,
        rate=Fraction(25),
    )
    cases["wrongOriginalBytes"] = _expect_refusal(
        lambda: _prepare(source_50.path, wrong_descriptor, wrong_auth, wrong_tools),
        "source_hash_mismatch",
    )
    cases["wrongOriginalBytes"]["noAttemptPublished"] = _no_attempts(wrong_auth)
    if not cases["wrongOriginalBytes"]["noAttemptPublished"]:
        raise AssertionError("source mismatch left a preparation attempt")
    _write_result(result_path, result)

    recovery_descriptor, recovery_auth, first_tools = _context(
        source_25.path, output_root / "prepared-recovery-before", rate=Fraction(25)
    )
    partial_attempt: list[Path] = []

    def stop_with_partial_picture(stage: str, attempt: Path) -> None:
        if stage == "staged":
            partial = attempt / "picture.mp4"
            partial.write_bytes(b"incomplete media output")
            partial_attempt.append(partial)
            raise _InjectedInterruption(stage)

    source_hash_before = file_hash(source_25.path)
    try:
        _prepare(
            source_25.path,
            recovery_descriptor,
            recovery_auth,
            first_tools,
            checkpoint=stop_with_partial_picture,
        )
    except _InjectedInterruption:
        pass
    else:
        raise AssertionError("staged interruption did not stop preparation")
    if len(partial_attempt) != 1 or not partial_attempt[0].is_file():
        raise AssertionError("staged partial output was not retained")
    partial_hash = file_hash(partial_attempt[0])
    recovery_tools = MediaTools()
    recovered_before = _prepare(
        source_25.path, recovery_descriptor, recovery_auth, recovery_tools
    )
    if recovered_before.reused or not _has_video_encode(recovery_tools):
        raise AssertionError("staged partial output was adopted without re-encoding")
    if file_hash(partial_attempt[0]) != partial_hash:
        raise AssertionError("staged partial output changed during recovery")
    before_publish_hash = file_hash(recovered_before.video_path)
    if file_hash(source_25.path) != source_hash_before:
        raise AssertionError("source changed during staged recovery")
    cases["stagedRecovery"] = {
        "interruptedAt": "staged",
        "partialPath": _relative(output_root, partial_attempt[0]),
        "partialSha256": partial_hash,
        "recoveryReencoded": _has_video_encode(recovery_tools),
        "recoveryReused": recovered_before.reused,
        "publishedPath": _relative(output_root, recovered_before.video_path),
        "publishedSha256": before_publish_hash,
        "sourceSha256BeforeAfter": source_hash_before,
    }
    _write_result(result_path, result)

    post_descriptor, post_auth, post_tools = _context(
        source_25.path, output_root / "prepared-recovery-after", rate=Fraction(25)
    )
    post_request = _request(source_in_frame=_SOURCE_ORIGIN_FRAME + 11)
    published_path: list[Path] = []

    def stop_after_publication(stage: str, path: Path) -> None:
        if stage == "published":
            published_path.append(path / "picture.mp4")
            raise _InjectedInterruption(stage)

    try:
        _prepare(
            source_25.path,
            post_descriptor,
            post_auth,
            post_tools,
            request=post_request,
            checkpoint=stop_after_publication,
        )
    except _InjectedInterruption:
        pass
    else:
        raise AssertionError("post-publication interruption did not stop preparation")
    if len(published_path) != 1 or not published_path[0].is_file():
        raise AssertionError("published output was not retained")
    post_hash_before = file_hash(published_path[0])
    restart_tools = MediaTools()
    recovered_after = _prepare(
        source_25.path,
        post_descriptor,
        post_auth,
        restart_tools,
        request=post_request,
    )
    if not recovered_after.reused or _has_video_encode(restart_tools):
        raise AssertionError("published output was not verified and reused")
    if file_hash(recovered_after.video_path) != post_hash_before:
        raise AssertionError("published output changed during restart")
    if file_hash(recovered_before.video_path) != before_publish_hash:
        raise AssertionError("prior prepared output changed during restart")
    if file_hash(source_25.path) != source_hash_before:
        raise AssertionError("source changed during published recovery")
    cases["publishedRecovery"] = {
        "interruptedAt": "published",
        "publishedPath": _relative(output_root, published_path[0]),
        "publishedSha256": post_hash_before,
        "restartReused": recovered_after.reused,
        "restartEncoded": _has_video_encode(restart_tools),
        "priorPreparedSha256BeforeAfter": before_publish_hash,
        "sourceSha256BeforeAfter": source_hash_before,
    }

    # Corrupt a retained derivative and ask the public preparation path to reuse it.
    published_path[0].write_bytes(b"corrupt derivative")
    corrupted_hash = file_hash(published_path[0])
    tamper_tools = MediaTools()
    cases["preparationTamper"] = _expect_refusal(
        lambda: _prepare(
            source_25.path,
            post_descriptor,
            post_auth,
            tamper_tools,
            request=post_request,
        ),
        "published_conflict",
    )
    if file_hash(published_path[0]) != corrupted_hash:
        raise AssertionError("tampered derivative was modified during refusal")
    if file_hash(recovered_before.video_path) != before_publish_hash:
        raise AssertionError("separate prepared artifact changed after tamper refusal")
    if file_hash(source_25.path) != source_hash_before:
        raise AssertionError("source changed during tamper refusal")
    cases["preparationTamper"].update(
        {
            "corruptedPathPreserved": _relative(output_root, published_path[0]),
            "corruptedSha256": corrupted_hash,
            "priorPreparedSha256Preserved": before_publish_hash,
            "sourceSha256Preserved": source_hash_before,
        }
    )

    result["status"] = "passed"
    _write_result(result_path, result)
    return result
