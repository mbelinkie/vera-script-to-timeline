"""Build and independently verify immutable, verified v2 OTIO packages.

This is deliberately separate from the v1 ``otio_package`` boundary.  V2
packages preserve the compiler's original inputs and project v2 event intent
into a small Resolve-facing delivery view without rewriting the manifest.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise
from json import encoder as json_encoder
from json.encoder import encode_basestring, encode_basestring_ascii
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
import opentimelineio as otio  # type: ignore[import-untyped]
from referencing import Registry, Resource

from vera_timeline_agent import cropdetect, native_image_motion
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.music_input import inspect_music, music_event_id
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.package_cache import (
    CacheEntry,
    FileStamp,
    PackageCache,
    SourceChangedError,
    clone_or_copy,
    source_stamp,
)
from vera_timeline_agent.placeholder_slate import (
    render_placeholder_slate,
    transparent_graphic_carrier,
)
from vera_timeline_agent.presenter_warning_validation import (
    _MUSIC_WARNING_CODES,
    OutputConsistencyError,
    _stable_compiler_id,
    validate_temporary_presenter_report,
)
from vera_timeline_agent.source_audio_endpoint import endpoint_plan, endpoint_wav
from vera_timeline_agent.still_credit import (
    TRACK_ID as STILL_CREDIT_TRACK_ID,
)
from vera_timeline_agent.still_credit import (
    credit_text,
    render_credit,
)
from vera_timeline_agent.transition_delivery_v2 import (
    TransitionRefusal,
    validate_signed_transitions,
)

BUILD_DIRECTORY = "Builds"
MEDIA_DIRECTORY = "Media"
MANIFEST_FILENAME = "timeline-manifest.json"
REPORT_FILENAME = "build-report.json"
DOCUMENT_FILENAME = "script-document.json"
DEPENDENCIES_FILENAME = "compiler-dependencies.json"
DELIVERY_VIEW_FILENAME = "delivery-view.json"
OTIO_FILENAME = "timeline.otio"
VERIFICATION_FILENAME = "package-verification.json"
ENCODED_BARS_FILENAME = "encoded-bars.json"
ENCODED_BARS_SCHEMA_VERSION = "encoded-bars-evidence/v1"
VIEW_SCHEMA_VERSION = "resolve-native-view/v2"
VERIFICATION_SCHEMA_VERSION = "v2-package-verification/v1"
_HASH_PREFIX = "sha256:"
_MAX_SAFE = 2**53 - 1
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CONTRACTS_DIRECTORY = _REPOSITORY_ROOT / "contracts"
_V2_SCHEMA_FILES = (
    "script-document-v2.schema.json",
    "timeline-manifest-v2.schema.json",
    "build-report-v2.schema.json",
    "compiler-dependencies-v2.schema.json",
)

JsonObject = dict[str, Any]

_TEMPORARY_PRESENTER_EVENT_MESSAGE = (
    "Temporary presenter still requires manual replacement when an accepted "
    "presenter source is available."
)


class V2PackageError(RuntimeError):
    """An actionable failure that prevents v2 package publication or import."""


class _SuppliedHashMismatch(V2PackageError):
    """Stale supplied media must not leave a possibly huge partial staging copy."""


@dataclass(frozen=True)
class V2PackageResult:
    """Published v2 package identity and whether this was an exact retry."""

    project_root: Path
    build_id: str
    reused: bool


@dataclass(frozen=True)
class V2PackageVerification:
    """Counts independently recovered from the published delivery view."""

    build_id: str
    event_count: int
    marker_count: int
    media_count: int


_PACKAGE_STAGES = (
    "source hash",
    "copy + streamed hash",
    "slates",
    "audio",
    "receipt hash",
    "verification",
)


class _PackageSubtimings:
    """Opt-in, additive wall-clock measurements; never change package bytes."""

    def __init__(self, observer: Callable[[str, float, bool], None]) -> None:
        self.observer = observer
        self.seconds = dict.fromkeys(_PACKAGE_STAGES, 0.0)
        self.failed: set[str] = set()

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        self.seconds.setdefault(stage, 0.0)
        started = perf_counter()
        try:
            yield
        except BaseException:
            self.failed.add(stage)
            raise
        finally:
            self.seconds[stage] += max(0.0, perf_counter() - started)

    def report(self) -> None:
        for stage, seconds in self.seconds.items():
            self.observer(stage, seconds, stage not in self.failed)


@contextmanager
def _measure(timing: _PackageSubtimings | None, stage: str) -> Iterator[None]:
    if timing is None:
        yield
    else:
        with timing.measure(stage):
            yield


def _error(message: str) -> V2PackageError:
    return V2PackageError(message)


def _render_slate(text: str, width: int, height: int) -> bytes:
    try:
        return render_placeholder_slate(text, width, height)
    except (OverflowError, TypeError, ValueError) as error:
        raise _error(f"placeholder slate cannot be rendered: {error}") from error


def _hash_bytes(data: bytes) -> str:
    return _HASH_PREFIX + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise _error(f"could not hash file {path}: {error}") from error
    return _HASH_PREFIX + digest.hexdigest()


def _require_hash(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith(_HASH_PREFIX)
    ):
        raise _error(f"{label} is not a sha256 content hash")
    try:
        int(value[len(_HASH_PREFIX) :], 16)
    except ValueError as error:
        raise _error(f"{label} is not a lowercase sha256 content hash") from error
    if value != value.lower():
        raise _error(f"{label} is not a lowercase sha256 content hash")
    return value


def _canonical_json(value: object) -> bytes:
    return canonical_json_bytes(value)


def _compiler_hash(value: object) -> str:
    """Match compiler-core JSON for safe integers and schema-approved decimals."""
    text = (
        json.dumps(
            _compiler_json_values(value),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            cls=_CompilerJSONEncoder,
        )
        + "\n"
    )
    # JSON.stringify preserves valid Unicode and escapes lone surrogate units.
    text = "".join(
        f"\\u{ord(char):04x}" if 0xD800 <= ord(char) <= 0xDFFF else char
        for char in text
    )
    return _hash_bytes(text.encode("utf-8"))


class _CompilerJSONEncoder(json.JSONEncoder):
    """Use JS Number-to-string for frozen compiler decimal hashes.

    Python repr emits `5e-05` where JSON.stringify emits `0.00005`, and
    `1e-07` where JavaScript emits `1e-7`. The normal JSON token encoder is
    reused with a narrowly replaced float formatter; strings are untouched.
    """

    def iterencode(self, o: Any, _one_shot: bool = False) -> Any:
        def js_float(value: float) -> str:
            if not math.isfinite(value):
                raise ValueError("non-finite number in compiler JSON")
            if value == 0:
                return "0"
            shortest = repr(value)
            if "e" not in shortest:
                return shortest
            mantissa, exponent_text = shortest.split("e")
            exponent = int(exponent_text)
            if -6 <= exponent < 21:
                return format(Decimal(shortest), "f")
            return f"{mantissa}e{exponent:+d}"

        # Typeshed intentionally omits this stdlib private helper; use getattr
        # to keep the pinned runtime implementation while retaining strict mypy.
        return getattr(json_encoder, "_make_iterencode")(  # noqa: B009
            {} if self.check_circular else None,
            self.default,
            encode_basestring_ascii if self.ensure_ascii else encode_basestring,
            self.indent,
            js_float,
            self.key_separator,
            self.item_separator,
            self.sort_keys,
            self.skipkeys,
            _one_shot,
        )(o, 0)


def _compiler_json_values(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        return {
            name: _compiler_json_values(nested, key=name)
            for name, nested in value.items()
        }
    if isinstance(value, list):
        return [_compiler_json_values(nested) for nested in value]
    if isinstance(value, float):
        if key in {"fullGainDb", "gainDb"} and value == -0.1:
            return value
        if key in {"focusX", "focusY", "scale"} and math.isfinite(value):
            # ImageMotionV1 admits finite fractions.  JS canonicalJson writes
            # integral 1.0 as 1, and other finite decimals unchanged.
            return int(value) if value.is_integer() and abs(value) < 1e21 else value
        if not math.isfinite(value) or not value.is_integer() or abs(value) > _MAX_SAFE:
            raise _error("compiler hash input is not a schema-supported safe integer")
        return int(value)
    if type(value) is int and abs(value) > _MAX_SAFE:
        raise _error("compiler hash input is not a schema-supported safe integer")
    return value


def _load_json(path: Path, label: str) -> tuple[JsonObject, bytes]:
    _require_path_components_no_symlink(path, label)
    _require_regular(path, label)
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_keys,
            parse_constant=_invalid_json_number,
            parse_float=_finite_json_float,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise _error(f"could not read {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise _error(f"{label} must contain one JSON object: {path}")
    return cast(JsonObject, value), raw


def _unique_json_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _invalid_json_number(value: str) -> Any:
    raise ValueError(f"non-finite JSON number {value}")


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number {value}")
    return number


def _require_regular(path: Path, label: str) -> os.stat_result:
    try:
        if path.is_symlink():
            raise _error(f"{label} is a symbolic link: {path}")
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise _error(f"could not inspect {label} {path}: {error}") from error
    if not stat.S_ISREG(info.st_mode):
        raise _error(f"{label} must be a regular file: {path}")
    return info


def _require_path_components_no_symlink(path: Path, label: str) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        try:
            if component.is_symlink():
                raise _error(f"{label} contains a symbolic link: {component}")
        except OSError as error:
            raise _error(f"could not inspect {label} {component}: {error}") from error


def _copy_input_file(
    source: Path, destination: Path, expected_hash: str | None = None
) -> str:
    """Copy bytes with O_NOFOLLOW and detect a source changed during the read."""
    _require_path_components_no_symlink(source, "supplied media path")
    before = _require_regular(source, "supplied media")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(source, flags)
    except OSError as error:
        raise _error(f"could not open supplied media {source}: {error}") from error
    try:
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise _error(f"supplied media changed before copying: {source}")
        with (
            os.fdopen(source_fd, "rb", closefd=False) as reader,
            destination.open("xb") as writer,
        ):
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        after = os.fstat(source_fd)
    except V2PackageError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as error:
        destination.unlink(missing_ok=True)
        raise _error(f"could not copy supplied media {source}: {error}") from error
    finally:
        os.close(source_fd)
    final = source.stat(follow_symlinks=False)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        destination.unlink(missing_ok=True)
        raise _error(f"supplied media changed while copying: {source}")
    actual = _HASH_PREFIX + digest.hexdigest()
    if expected_hash is not None and actual != expected_hash:
        destination.unlink(missing_ok=True)
        raise _SuppliedHashMismatch(
            f"media hash mismatch for {source}: {expected_hash} != {actual}"
        )
    return actual


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise _error(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise _error(f"unsafe {label}: {value}")
    return path


def _schema_registry() -> tuple[dict[str, JsonObject], Registry[Any]]:
    schemas: dict[str, JsonObject] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for filename in _V2_SCHEMA_FILES:
        path = _CONTRACTS_DIRECTORY / filename
        schema, _ = _load_json(path, "v2 contract schema")
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise _error(f"v2 contract schema has no string $id: {path}")
        schemas[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return schemas, Registry().with_resources(resources)


def _validate_schema(value: object, schema_key: str, label: str) -> None:
    schemas, registry = _schema_registry()
    schema = next(
        (
            candidate
            for schema_id, candidate in schemas.items()
            if schema_key in schema_id
        ),
        None,
    )
    if schema is None:
        raise _error(f"missing accepted schema for {label}")
    errors = sorted(
        jsonschema.Draft202012Validator(
            schema, registry=registry, format_checker=jsonschema.FormatChecker()
        ).iter_errors(value),
        key=lambda item: item.json_path,
    )
    if errors:
        first = errors[0]
        raise _error(
            f"{label} schema validation failed at {first.json_path}: {first.message}"
        )


def _walk_rationals(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        if set(value) == {"numerator", "denominator"}:
            numerator, denominator = value["numerator"], value["denominator"]
            if (
                type(numerator) is not int
                or type(denominator) is not int
                or abs(numerator) > _MAX_SAFE
                or not 0 < denominator <= _MAX_SAFE
                or math.gcd(abs(numerator), denominator) != 1
            ):
                raise _error(f"rational at {path} is not reduced safe-integer geometry")
        for key, item in value.items():
            _walk_rationals(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_rationals(item, f"{path}[{index}]")


def _fraction(value: object, label: str, *, positive: bool = False) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise _error(f"{label} is not a rational pair")
    numerator, denominator = value["numerator"], value["denominator"]
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or abs(numerator) > _MAX_SAFE
        or not 0 < denominator <= _MAX_SAFE
        or math.gcd(abs(numerator), denominator) != 1
        or (positive and numerator <= 0)
    ):
        raise _error(f"{label} is not a reduced safe rational")
    return Fraction(numerator, denominator)


def _safe_frame(value: object, label: str, *, positive: bool = False) -> int:
    if (
        type(value) is not int
        or not 0 <= value <= _MAX_SAFE
        or (positive and value == 0)
    ):
        raise _error(f"{label} is not a safe nonnegative frame counter")
    return value


def _range(
    value: object, label: str, *, allow_zero_duration: bool = False
) -> tuple[int, int]:
    if not isinstance(value, dict) or set(value) != {"startFrame", "endFrame"}:
        raise _error(f"{label} is not a v2 half-open frame range")
    start = _safe_frame(value["startFrame"], f"{label}.startFrame")
    end = _safe_frame(value["endFrame"], f"{label}.endFrame")
    if end < start or (end == start and not allow_zero_duration):
        raise _error(f"{label} is empty or reversed")
    return start, end


def _unique_by_id(values: object, label: str, key: str = "id") -> dict[str, JsonObject]:
    if not isinstance(values, list):
        raise _error(f"{label} collection is not an array")
    result: dict[str, JsonObject] = {}
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise _error(f"{label} has a missing or invalid {key}")
        identity = item[key]
        if identity in result:
            raise _error(f"duplicate {label} id {identity}")
        result[identity] = cast(JsonObject, item)
    return result


def _id_component(value: str, label: str) -> str:
    if not value or value in {".", ".."} or any(char in value for char in "/\\\0"):
        raise _error(f"unsafe {label}: {value!r}")
    return value


def _suffix(path: Path) -> str:
    suffix = path.suffix
    if (
        not suffix
        or len(suffix) > 17
        or any(
            character
            not in ".abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            for character in suffix
        )
    ):
        return ".media"
    return suffix.lower()


def _validate_inputs(
    document: JsonObject,
    dependencies: JsonObject,
    manifest: JsonObject,
    report: JsonObject,
) -> None:
    # The pure provenance resolver does not grant evidence-export permission.
    if (
        dependencies.get("graphicProvenanceSnapshots")
        or dependencies.get("resolvedGraphicContents")
        or any(
            isinstance(item, dict)
            and (
                item.get("graphicContentClass") in ("manual", "derived")
                or item.get("graphicContentBinding") is not None
            )
            for item in dependencies.get("occurrenceResolutions", [])
        )
        or any(
            isinstance(event, dict)
            and isinstance(event.get("provenance"), dict)
            and event["provenance"].get("graphicProvenanceHash") is not None
            for event in manifest.get("events", [])
        )
    ):
        raise _error(
            "new-format graphic provenance requires a verified evidence-package adapter"
        )
    for value in (document, dependencies, manifest, report):
        _walk_rationals(value)
    _validate_schema(document, "script-document-v2", "script document v2")
    _validate_schema(
        dependencies, "compiler-dependencies-v2", "compiler dependencies v2"
    )
    _validate_schema(manifest, "timeline-manifest-v2", "timeline manifest v2")
    _validate_schema(report, "build-report-v2", "build report v2")

    document_id = document.get("id")
    project_id = document.get("projectId")
    live_hash = _require_hash(
        cast(JsonObject, document.get("liveContentHash")), "document liveContentHash"
    )
    if live_hash != _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    ):
        raise _error("document liveContentHash does not match its actual saved content")
    dep_identity = cast(JsonObject, dependencies.get("document"))
    manifest_identity = cast(JsonObject, manifest.get("document"))
    report_identity = cast(JsonObject, report.get("document"))
    for identity, label in (
        (dep_identity, "dependencies document"),
        (manifest_identity, "manifest document"),
        (report_identity, "report document"),
    ):
        if (
            identity.get("documentId") != document_id
            or identity.get("projectId") != project_id
        ):
            raise _error(f"{label} identity does not match the saved script document")
        if identity.get("contentHash") != live_hash:
            raise _error(f"{label} live content hash does not match the saved document")
    if (
        dep_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
        or manifest_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
        or report_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
    ):
        raise _error("document head sequence differs across frozen package inputs")
    for identity, label in (
        (manifest_identity, "manifest"),
        (report_identity, "report"),
    ):
        if (
            identity.get("revision") != dep_identity.get("revision")
            or identity.get("textHash") != dep_identity.get("textHash")
            or identity.get("settingsHash") != dep_identity.get("settingsHash")
        ):
            raise _error(
                f"{label} document revision/hash identity differs from dependencies"
            )
    narration = [
        block["text"]
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    ]
    try:
        text_hash = _hash_bytes("\n".join(narration).encode("utf-8"))
    except UnicodeError as error:
        raise _error("narration text is not valid scalar Unicode") from error
    if dep_identity.get("textHash") != text_hash:
        raise _error("document textHash does not match the exact saved narration text")
    if (
        dep_identity.get("settingsHash")
        != dependencies["authoringDefaults"]["settingsHash"]
    ):
        raise _error(
            "document settingsHash differs from its accepted authoring defaults"
        )

    build = cast(JsonObject, dependencies.get("build"))
    if (
        manifest.get("buildId") != build.get("buildId")
        or manifest.get("id") != build.get("manifestId")
        or report.get("buildId") != build.get("buildId")
        or report.get("id") != build.get("reportId")
        or cast(JsonObject, report.get("manifest")).get("id") != manifest.get("id")
    ):
        raise _error("manifest, report, and dependencies build identities do not close")
    if manifest.get("buildClass") != build.get("buildClass") or report.get(
        "buildClass"
    ) != build.get("buildClass"):
        raise _error("manifest, report, and dependencies build classes differ")
    if document_id != dep_identity.get("documentId"):
        raise _error(
            "dependencies document identity differs from the supplied document"
        )
    if report.get("dependenciesHash") != _compiler_hash(dependencies):
        raise _error(
            "build report dependenciesHash does not match canonical dependencies"
        )
    manifest_identity_hash = _compiler_hash(manifest)
    if (
        cast(JsonObject, report.get("manifest")).get("contentHash")
        != manifest_identity_hash
    ):
        raise _error(
            "build report manifest hash does not match canonical manifest JSON"
        )
    compiler = dependencies["compiler"]
    if manifest["compiler"] != compiler or report["compiler"] != compiler:
        raise _error(
            "compiler source/profile/version identity differs across package inputs"
        )
    for event in manifest["events"]:
        provenance = event["provenance"]
        if (
            provenance["documentId"] != document_id
            or provenance["compilerVersion"] != compiler["version"]
        ):
            raise _error(
                "event document/compiler provenance differs from the frozen inputs"
            )

    timeline = manifest.get("timeline")
    if timeline != dependencies.get("timeline") or timeline != report.get("timeline"):
        raise _error(
            "timeline settings differ across manifest, report, and dependencies"
        )
    if manifest.get("tracks") != dependencies.get("tracks"):
        raise _error("manifest tracks differ from compiler dependencies")
    if manifest.get("roles") != dependencies.get("roles"):
        raise _error("manifest roles differ from compiler dependencies")
    if manifest.get("authoringDefaults") != dependencies.get("authoringDefaults"):
        raise _error("manifest authoring defaults differ from compiler dependencies")

    temporary_presenter_events = _validate_temporary_presenter_report(
        document, manifest, report
    )
    readiness = cast(JsonObject, report.get("readiness"))
    if (
        report.get("status") != "ready"
        or readiness.get("preview") != "ready"
        or readiness.get("release") != "ready"
        or readiness.get("blockingIssueIds") != []
        or report.get("migrationIssues") != []
    ):
        raise _error("only a fully ready v2 report can be packaged")

    _validate_manifest_semantics(document, dependencies, manifest)
    try:
        validate_signed_transitions(document, dependencies, manifest, report)
    except TransitionRefusal as error:
        raise _error(f"signed picture transition refused: {error}") from error
    _validate_report_semantics(
        manifest, report, dependencies, temporary_presenter_events
    )


def _validate_temporary_presenter_report(
    document: JsonObject, manifest: JsonObject, report: JsonObject
) -> set[str]:
    """Translate the shared stdlib warning check into a package refusal."""
    try:
        return validate_temporary_presenter_report(document, manifest, report)
    except OutputConsistencyError as error:
        raise _error(str(error)) from error


def narration_ceiling_frames(samples: int, sample_rate: int, rate: Fraction) -> int:
    """Longest narration event, in frames, an audio asset may back.

    D-0014: the compiler frames narration at exact rational ceiling frame
    boundaries, so an event may extend to ceil(audio duration in frames). The
    sub-frame remainder is silence past the asset end, never audio.
    """
    return -((-samples * rate) // sample_rate)


def _validate_manifest_semantics(
    document: JsonObject, dependencies: JsonObject, manifest: JsonObject
) -> None:
    # Reconstruct the motion resolution independently of the compiler output.
    # A self-consistent manifest/report hash alone must not authorize dropping
    # an explicit None override or substituting an unrequested native zoom.
    authored_visuals: dict[str, JsonObject] = {}

    def collect_visuals(value: object) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "visual" and isinstance(
                value.get("payloadId"), str
            ):
                payload_id = cast(str, value["payloadId"])
                previous = authored_visuals.get(payload_id)
                if previous is not None and previous != value:
                    raise _error(f"conflicting authored visual payload {payload_id}")
                authored_visuals[payload_id] = value
            for nested in value.values():
                collect_visuals(nested)
        elif isinstance(value, list):
            for nested in value:
                collect_visuals(nested)

    collect_visuals(cast(JsonObject, document["activeDraft"])["blocks"])
    frozen_default = cast(JsonObject, dependencies["authoringDefaults"]).get(
        "imageMotionDefault"
    )
    hide_encoded_bars = (
        cast(JsonObject, dependencies.get("authoringDefaults", {})).get(
            "hideEncodedBars"
        )
        is True
    )
    timeline = cast(JsonObject, manifest["timeline"])
    rate = _fraction(timeline.get("frameRate"), "timeline frame rate", positive=True)
    start = _safe_frame(timeline.get("startFrame"), "timeline startFrame")
    duration = _safe_frame(
        timeline.get("durationFrames"), "timeline durationFrames", positive=True
    )
    end = start + duration
    if end > _MAX_SAFE:
        raise _error("timeline endpoint exceeds the safe integer range")

    tracks = _unique_by_id(manifest.get("tracks"), "track")
    dependency_tracks = _unique_by_id(dependencies.get("tracks"), "dependency track")
    if tracks != dependency_tracks:
        raise _error("manifest and dependencies track maps differ")
    slots: set[tuple[str, int]] = set()
    for track_record in tracks.values():
        index = _safe_frame(
            track_record.get("index"),
            f"track {track_record['id']} index",
            positive=True,
        )
        slot = (cast(str, track_record.get("kind")), index)
        if slot in slots:
            raise _error(f"duplicate {slot[0]} track index {slot[1]}")
        slots.add(slot)

    roles = cast(JsonObject, dependencies.get("roles"))
    composition = cast(JsonObject, manifest.get("composition"))
    if (
        composition.get("topology") != "primary_root_child_overlay"
        or composition.get("primaryRootTrackId") != roles.get("primaryRootTrackId")
        or composition.get("childTrackIds") != roles.get("childTrackIds")
        or composition.get("overlayTrackIds") != roles.get("overlayTrackIds")
    ):
        raise _error(
            "manifest composition topology differs from configured track roles"
        )
    root_id = cast(str, composition["primaryRootTrackId"])
    child_ids = cast(list[str], roles.get("childTrackIds", []))
    overlay_ids = cast(list[str], roles.get("overlayTrackIds", []))
    root = tracks.get(root_id)
    if root is None or root.get("kind") != "video":
        raise _error("primary root composition track is missing or not video")
    if (
        len(set(child_ids)) != len(child_ids)
        or len(set(overlay_ids)) != len(overlay_ids)
        or root_id in child_ids
        or root_id in overlay_ids
        or set(child_ids) & set(overlay_ids)
    ):
        raise _error("primary root, child, and overlay tracks must be disjoint")
    for role_key, expected_kind in (
        ("narrationTrackId", "audio"),
        ("sourceAudioTrackIds", "audio"),
        ("musicTrackId", "audio"),
        ("presenterTrackId", "video"),
        ("placeholderTrackId", "video"),
        ("markerTrackId", "video"),
    ):
        raw = roles.get(role_key)
        ids = raw if isinstance(raw, list) else [raw]
        for track_id in ids:
            if track_id is None:
                continue
            role_track = tracks.get(cast(str, track_id))
            if role_track is None or role_track.get("kind") != expected_kind:
                raise _error(
                    f"configured {role_key} refers to a missing or wrong-kind track"
                )
    for track_id in child_ids:
        if track_id not in tracks or tracks[track_id].get("kind") != "video":
            raise _error(f"configured child track {track_id} is missing or not video")
    for track_id in overlay_ids:
        if track_id not in tracks or tracks[track_id].get("kind") != "video":
            raise _error(f"configured overlay track {track_id} is missing or not video")
    role_indices = {
        track_id: _safe_frame(
            tracks[track_id].get("index"), f"track {track_id} index", positive=True
        )
        for track_id in (root_id, *child_ids, *overlay_ids)
    }
    if (
        (
            child_ids
            and role_indices[root_id] >= min(role_indices[item] for item in child_ids)
        )
        or (
            overlay_ids
            and role_indices[root_id] >= min(role_indices[item] for item in overlay_ids)
        )
        or (
            child_ids
            and overlay_ids
            and max(role_indices[item] for item in child_ids)
            >= min(role_indices[item] for item in overlay_ids)
        )
    ):
        raise _error("primary root, child, and overlay tracks are not layered by index")

    events = _unique_by_id(manifest.get("events"), "event", "eventId")
    sources = _unique_by_id(manifest.get("sources"), "source")
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    dependency_bindings = _unique_by_id(
        dependencies.get("preparedMedia"), "prepared media", "requirementKey"
    )
    if bindings != dependency_bindings:
        raise _error("manifest preparation bindings differ from compiler dependencies")
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    root_events: list[JsonObject] = []
    visual_source_ids: set[str] = set()
    authored_quotes = {
        (block["id"], overlay["id"]): overlay["quoteBox"]
        for block in document["activeDraft"]["blocks"]
        if block.get("type") == "narration" and block.get("state") == "active"
        for overlay in block.get("overlayEvents", [])
        if "quoteBox" in overlay
    }
    music_matches: dict[str, tuple[str, str]] = {}
    for block in document["activeDraft"]["blocks"]:
        if block["type"] != "visual_only":
            continue
        for visual in (block, *block.get("additionalVisuals", [])):
            match = visual["visualOnlyTiming"].get("matchAudioDuration")
            if match is not None:
                cue_id = match["cueId"]
                if cue_id in music_matches:
                    raise _error("a music cue can match only one visual")
                music_matches[cue_id] = (block["id"], visual["payload"]["payloadId"])
    for event in events.values():
        event_id = cast(str, event["eventId"])
        event_kind = cast(str, event["kind"])
        track_id = cast(str, event["trackId"])
        event_track = tracks.get(track_id)
        if event_track is None:
            raise _error(f"event {event_id} references missing track {track_id}")
        track_kind = cast(str, event_track["kind"])
        if (event_kind in {"narration", "source_audio", "music"}) != (
            track_kind == "audio"
        ):
            raise _error(f"event {event_id} kind and track media type disagree")
        record_start, record_end = _range(
            event.get("recordRange"), f"event {event_id} recordRange"
        )
        if record_start < start or record_end > end:
            raise _error(f"event {event_id} falls outside the timeline range")
        role = event.get("trackRole")
        if event_kind == "primary_visual":
            if track_id == root_id and role == "primary_root":
                root_events.append(event)
            elif track_id in child_ids and role == "child":
                pass
            else:
                raise _error(
                    f"primary visual event {event_id} is outside a root or child track"
                )
        elif event_kind in {"overlay_visual", "quote_box", "still_credit"}:
            if track_id not in roles.get("overlayTrackIds", []) or role != "overlay":
                raise _error(
                    f"overlay event {event_id} is outside a configured overlay track"
                )
            if event_kind == "quote_box" and (
                event_track["index"] != 4
                or any(
                    event.get(key) is not None
                    for key in (
                        "pictureTreatment",
                        "sourceRange",
                        "sourceTimeMapping",
                        "preparationBindingHash",
                        "audio",
                    )
                )
            ):
                raise _error(f"quote box {event_id} must be a generated V4 graphic")
            if event_kind == "quote_box":
                owner = event["provenance"]
                quote = authored_quotes.pop(
                    (owner["blockId"], owner["overlayEventId"]), None
                )
                if quote is None or quote != event.get("quoteBox"):
                    raise _error(
                        f"quote box {event_id} differs from its authored overlay"
                    )
        elif event_kind == "placeholder":
            allowed = {
                root_id,
                roles.get("placeholderTrackId"),
                roles.get("presenterTrackId"),
                *child_ids,
            }
            valid_placeholder_role = (
                (track_id == root_id and role == "primary_root")
                or (
                    track_id == roles.get("placeholderTrackId")
                    and role == "placeholder"
                )
                or (track_id == roles.get("presenterTrackId") and role == "presenter")
                or (track_id in child_ids and role == "child")
            )
            if track_id not in allowed or not valid_placeholder_role:
                raise _error(
                    f"placeholder event {event_id} is outside a supported picture track"
                )
            treatment = event.get("pictureTreatment")
            if not isinstance(treatment, dict) or treatment.get("kind") not in {
                "still",
                "slate",
            }:
                raise _error(
                    f"placeholder event {event_id} is not a static still or slate"
                )
            if treatment["kind"] == "still":
                reference = treatment.get("reference")
                if (
                    not isinstance(reference, dict)
                    or treatment.get("composition", {}).get("motionPreset") != "none"
                ):
                    raise _error(
                        f"placeholder {event_id} needs a bound still with no motion"
                    )
            elif not isinstance(treatment.get("text"), str):
                raise _error(f"placeholder slate {event_id} has no authored text")
            if track_id == root_id:
                root_events.append(event)
        elif event_kind == "narration":
            if track_id != roles.get("narrationTrackId") or role != "narration":
                raise _error(
                    f"narration event {event_id} is outside the narration track"
                )
        elif event_kind == "source_audio":
            if (
                track_id not in roles.get("sourceAudioTrackIds", [])
                or role != "source_audio"
            ):
                raise _error(f"source audio {event_id} is outside a configured track")
        elif event_kind == "music":
            if (
                track_id != roles.get("musicTrackId")
                or role != "music"
                or event_track.get("index") != 5
            ):
                raise _error(f"music event {event_id} must use dedicated audio A5")
            if track_id == roles.get("narrationTrackId") or track_id in roles.get(
                "sourceAudioTrackIds", []
            ):
                raise _error(
                    "music A5 must be distinct from narration and source audio"
                )
        elif event_kind == "script_marker":
            if track_id != roles.get("markerTrackId") or role != "marker":
                raise _error(f"script marker {event_id} is outside the marker track")
        else:
            raise _error(f"unsupported v2 event kind {event_kind!r}")

        source_id = cast(JsonObject, event.get("provenance"))["sourceId"]
        if event_kind in {
            "primary_visual",
            "overlay_visual",
            "narration",
            "source_audio",
            "music",
        }:
            if not isinstance(source_id, str) or source_id not in sources:
                raise _error(
                    f"event {event_id} references missing source {source_id!r}"
                )
            if event_kind in {"primary_visual", "overlay_visual"}:
                visual_source_ids.add(source_id)
        elif (
            event_kind in {"placeholder", "quote_box", "still_credit"}
            and source_id is not None
        ):
            raise _error(
                f"{event_kind} event {event_id} must use its explicit event media"
            )

        if event_kind in {"primary_visual", "overlay_visual"}:
            provenance = cast(JsonObject, event.get("provenance"))
            payload = authored_visuals.get(cast(str, provenance.get("payloadId")))
            expected_bars_intent: JsonObject | None = None
            if hide_encoded_bars and payload is not None:
                picture_kind = payload.get("pictureKind")
                framing = payload.get("framingPolicy")
                if framing is not None:
                    expected_bars_intent = {
                        "mode": "keep",
                        "reason": (
                            "framing_ambiguous"
                            if picture_kind == "clip" and framing == "contain"
                            else "explicit_framing"
                        ),
                    }
                elif picture_kind == "clip":
                    expected_bars_intent = {"mode": "detect_and_fill"}
                elif picture_kind == "image":
                    treatment = event.get("pictureTreatment")
                    motion = (
                        treatment.get("imageMotion")
                        if isinstance(treatment, dict)
                        else None
                    )
                    moving = (
                        isinstance(motion, dict)
                        and motion.get("mode") == "native_dynamic_zoom"
                    )
                    expected_bars_intent = {
                        "mode": "keep",
                        "reason": (
                            "motion_route_unproven"
                            if moving
                            else "still_route_unproven"
                        ),
                    }
                elif picture_kind in {"capture", "graphic"}:
                    expected_bars_intent = {
                        "mode": "keep",
                        "reason": "unsupported_picture_kind",
                    }
            if event.get("encodedBars") != expected_bars_intent:
                raise _error(
                    f"visual event {event_id} bar-removal intent differs from "
                    "the authored payload and frozen setting"
                )
            source_range = event.get("sourceRange")
            source_start, source_end = _range(
                source_range, f"event {event_id} sourceRange"
            )
            treatment = event.get("pictureTreatment")
            if isinstance(treatment, dict) and treatment.get("kind") == "still_frame":
                provenance = cast(JsonObject, event["provenance"])
                payload = authored_visuals.get(cast(str, provenance["payloadId"]))
                default_image_framing = (
                    payload is not None
                    and payload.get("pictureKind") == "image"
                    and "framingPolicy" not in payload
                )
                if payload is not None and treatment.get("framingPolicy") != (
                    "cover" if default_image_framing else payload.get("framingPolicy")
                ):
                    raise _error(
                        f"still event {event_id} framing differs from authored policy"
                    )
                project_motion = (
                    native_image_motion.DEFAULT_IMAGE_MOTION
                    if default_image_framing and frozen_default is None
                    else frozen_default
                )
                expected_motion = (
                    payload.get("imageMotion", project_motion)
                    if payload is not None
                    else project_motion
                )
                if (expected_motion is not None or "imageMotion" in treatment) and (
                    payload is None or treatment.get("imageMotion") != expected_motion
                ):
                    raise _error(
                        f"still event {event_id} motion differs from frozen "
                        "authored override/default"
                    )
                if source_end - source_start != 1:
                    raise _error(
                        f"still event {event_id} must retain its one-frame range"
                    )
            elif source_end - source_start != record_end - record_start:
                raise _error(
                    f"dynamic visual event {event_id} requires unsupported retiming"
                )
            requirement_key = sources[source_id].get("preparationRequirementKey")
            binding = (
                bindings.get(cast(str, requirement_key))
                if requirement_key is not None
                else None
            )
            if binding is None or event.get("preparationBindingHash") != _compiler_hash(
                binding
            ):
                raise _error(
                    f"visual event {event_id} preparation binding is missing or stale"
                )
            if event.get("sourceTimeMapping") != binding.get("timeMapping"):
                raise _error(
                    f"visual event {event_id} mapping differs from preparation"
                )
        elif event_kind == "narration":
            source_record = sources[source_id]
            audio = source_record.get("narrationAudio")
            if not isinstance(audio, dict):
                raise _error(
                    f"narration event {event_id} has no compiler-pinned narration audio"
                )
            _require_hash(audio.get("audioHash"), f"narration {source_id} audioHash")
            sample_rate = _safe_frame(
                audio.get("sampleRate"),
                f"narration {source_id} sampleRate",
                positive=True,
            )
            samples = _safe_frame(
                audio.get("durationSamples"),
                f"narration {source_id} durationSamples",
                positive=True,
            )
            if record_end - record_start > narration_ceiling_frames(
                samples, sample_rate, rate
            ):
                raise _error(
                    f"narration event {event_id} exceeds its verified audio asset"
                )
        elif event_kind == "source_audio":
            if (
                event.get("preparationBindingHash") is None
                or event.get("sourceTimeMapping") is None
            ):
                raise _error(
                    f"source audio event {event_id} lacks its #174 preparation mapping"
                )
            binding = next(
                (
                    candidate
                    for candidate in bindings.values()
                    if _compiler_hash(candidate) == event["preparationBindingHash"]
                ),
                None,
            )
            if binding is None or event.get("sourceTimeMapping") != binding.get(
                "timeMapping"
            ):
                raise _error(
                    f"source audio event {event_id} preparation mapping is stale"
                )
        elif event_kind == "music":
            match = music_matches.pop(event["music"]["spanId"], None)
            _validate_music_event(
                document, dependencies, manifest, event, sources[source_id], rate, match
            )

        events_by_track[track_id].append(event)

    # Reconstruct all topmost credited picture intervals independently from the
    # frozen authored occurrence and the verified picture inventory.
    credit_events = [
        event for event in events.values() if event["kind"] == "still_credit"
    ]
    pictures = [
        event
        for event in events.values()
        if event["kind"] in {"primary_visual", "overlay_visual", "placeholder"}
    ]
    expected_credits = {}
    for picture in pictures:
        text = credit_text(authored_visuals.get(picture["provenance"]["payloadId"], {}))
        if not text:
            continue
        lane = tracks.get(STILL_CREDIT_TRACK_ID)
        if (
            not lane
            or lane["kind"] != "video"
            or STILL_CREDIT_TRACK_ID not in overlay_ids
            or any(
                track["kind"] == "video" and track["index"] > lane["index"]
                for track in tracks.values()
            )
            or any(event["trackId"] == STILL_CREDIT_TRACK_ID for event in pictures)
        ):
            raise _error("still credit requires a dedicated topmost video track")
        ranges = [_range(picture["recordRange"], "credited picture range")]
        for above in pictures:
            if tracks[above["trackId"]]["index"] <= tracks[picture["trackId"]]["index"]:
                continue
            left, right = _range(above["recordRange"], "covering picture range")
            remaining = []
            for start_frame, end_frame in ranges:
                if right <= start_frame or left >= end_frame:
                    remaining.append((start_frame, end_frame))
                else:
                    if start_frame < left:
                        remaining.append((start_frame, left))
                    if right < end_frame:
                        remaining.append((right, end_frame))
            ranges = remaining
        for start_frame, end_frame in ranges:
            identity = _stable_compiler_id(
                f"still-credit:{picture['eventId']}:{start_frame}:{end_frame}"
            )
            expected_credits[identity] = (picture, text, start_frame, end_frame)
    for event in credit_events:
        expected = expected_credits.pop(event["eventId"], None)
        if expected is None:
            raise _error("unexpected still credit event")
        picture, text, start_frame, end_frame = expected
        provenance = {
            **picture["provenance"],
            "payloadId": None,
            "sourceId": None,
            "originalSourceHash": None,
            "deliveredSourceHash": None,
        }
        if (
            event["trackId"] != STILL_CREDIT_TRACK_ID
            or event["recordRange"]
            != {"startFrame": start_frame, "endFrame": end_frame}
            or event["stillCredit"]
            != {"pictureEventId": picture["eventId"], "text": text}
            or event["provenance"] != provenance
            or any(
                event.get(key) is not None
                for key in (
                    "sourceRange",
                    "sourceTimeMapping",
                    "preparationBindingHash",
                    "audio",
                    "pictureTreatment",
                )
            )
        ):
            raise _error(
                "still credit differs from its authored occurrence or visible range"
            )
    if expected_credits:
        raise _error("an authored visible still credit is absent from the build")

    if authored_quotes:
        raise _error("an authored quote box is absent from the build")
    if music_matches:
        raise _error("an authored matched music cue is absent from the build")

    source_audio_events = sorted(
        (
            event
            for event in events.values()
            if event["kind"] == "source_audio" and event.get("audio") is not None
        ),
        key=lambda event: event["recordRange"]["startFrame"],
    )
    furthest_source_audio_end = -1
    for event in source_audio_events:
        begin, finish = _range(
            event["recordRange"], f"source audio event {event['eventId']} recordRange"
        )
        if begin < furthest_source_audio_end:
            raise _error("enabled source-audio events overlap in record time")
        furthest_source_audio_end = max(furthest_source_audio_end, finish)

    for track_id, track_events in events_by_track.items():
        ordered = sorted(
            track_events, key=lambda event: event["recordRange"]["startFrame"]
        )
        previous_end: int | None = None
        previous_id: str | None = None
        for event in ordered:
            if event["kind"] == "script_marker":
                continue
            begin, finish = _range(
                event["recordRange"], f"event {event['eventId']} recordRange"
            )
            if previous_end is not None and begin < previous_end:
                raise _error(
                    f"events {previous_id} and {event['eventId']} overlap on {track_id}"
                )
            previous_end, previous_id = finish, cast(str, event["eventId"])

    if composition.get("rootContinuous"):
        ordered_root = sorted(
            root_events, key=lambda event: event["recordRange"]["startFrame"]
        )
        cursor = start
        if not ordered_root:
            raise _error("continuous primary root contains no visual events")
        for event in ordered_root:
            begin, finish = _range(
                event["recordRange"], f"root event {event['eventId']} range"
            )
            if begin != cursor:
                raise _error(
                    "primary root events do not form continuous timeline coverage"
                )
            cursor = finish
        if cursor != end:
            raise _error("primary root does not reach the exclusive timeline end")

    root_events_by_id = {event["eventId"]: event for event in root_events}
    for returned in composition.get("returns", []):
        root_event = root_events_by_id.get(returned.get("rootEventId"))
        frame = _safe_frame(
            returned.get("recordFrame"), "composition return recordFrame"
        )
        if root_event is None:
            raise _error("composition return references a missing primary-root event")
        root_start, root_end = _range(
            root_event["recordRange"], "return root event range"
        )
        if (
            not root_start < frame < root_end
            or returned.get("emitsNewSourceEvent") is not False
        ):
            raise _error(
                "composition return is outside its root event or emits a source event"
            )

    for source_id, source in sources.items():
        if "narrationAudio" in source:
            continue
        if "musicAudio" in source:
            if {
                event["kind"]
                for event in events.values()
                if cast(JsonObject, event["provenance"]).get("sourceId") == source_id
            } != {"music"}:
                raise _error(f"music source {source_id} has no exclusive music event")
            continue
        _require_hash(source.get("originalHash"), f"source {source_id} originalHash")
        _require_hash(source.get("deliveredHash"), f"source {source_id} deliveredHash")
        _require_hash(
            source.get("originalProbeHash"), f"source {source_id} originalProbeHash"
        )
        _require_hash(
            source.get("deliveredProbeHash"), f"source {source_id} deliveredProbeHash"
        )
        if source.get("preparationRequirementKey") not in bindings:
            raise _error(
                f"source {source_id} references a missing preparation requirement"
            )
        if source.get("sourceTimeMapping") != bindings[
            source["preparationRequirementKey"]
        ].get("timeMapping"):
            raise _error(
                f"source {source_id} time mapping differs from its preparation"
            )
        if source.get("sourceFrameMap") != source["sourceTimeMapping"].get(
            "sourceFrameMap"
        ):
            raise _error(
                f"source {source_id} source frame map differs from its mapping"
            )

    # Compiler dependencies must describe the exact same primary/child/overlay roles.
    occurrence_by_key: dict[str, JsonObject] = {}
    for item in cast(list[JsonObject], dependencies.get("occurrenceResolutions", [])):
        requirement_key = item.get("preparedMediaRequirementKey")
        if requirement_key is not None:
            occurrence_by_key[cast(str, requirement_key)] = item
    if set(bindings) != set(occurrence_by_key):
        raise _error(
            "preparation requirements do not exactly cover occurrence resolutions"
        )
    del visual_source_ids  # kept explicit above for media-input classification.


def _music_pin_frame(
    point: JsonObject,
    document: JsonObject,
    dependencies: JsonObject,
    rows: list[tuple[str, str | None, int, int]],
    rate: Fraction,
) -> int:
    if point["kind"] == "frame":
        return _safe_frame(point["frame"], "music timeline pin")
    anchor = point.get("anchor")
    block_id = point["blockId"] if anchor is None else anchor["blockId"]
    row = next((row for row in rows if row[0] == block_id), None)
    if row is None:
        raise _error("music timeline pin refers to a row without compiled timing")
    if anchor is None:
        return row[2] if point["edge"] == "start" else row[3]

    block = next(
        block for block in document["activeDraft"]["blocks"] if block["id"] == block_id
    )
    token = next(
        (
            token
            for token in block.get("tokens", [])
            if token["id"] == anchor["tokenId"]
        ),
        None,
    )
    maps = [
        timing
        for key in ("narrationTimingMaps", "narrationBoundaryEvidence")
        for timing in dependencies.get(key, [])
        if timing["blockId"] == block_id
    ]
    if (
        block["type"] != "narration"
        or token is None
        or token.get("spoken") is False
        or token["value"] != anchor["quotedWord"]
        or len(maps) != 1
        or maps[0]["blockRevision"] != block["version"]
        or maps[0].get("precision") in {"sentence_only", "estimated"}
    ):
        raise _error("music timeline pin lacks current word timing")
    timing = maps[0]
    word: JsonObject = next(
        (mark for mark in timing["tokens"] if mark["tokenId"] == anchor["tokenId"]), {}
    )
    if anchor["affinity"] == "before":
        time = word.get("onset" if "verification" in timing else "startTime")
    else:
        time = word.get("audibleEnd")
        if (
            "verification" not in timing
            and word.get("endBasis") != "evidenced_audible_end"
        ):
            time = None
    if time is None:
        raise _error("music timeline pin lacks evidence for the selected word edge")
    frame = row[2] + math.ceil(_fraction(time, "music word time") * rate)
    if not row[2] <= frame <= row[3]:
        raise _error("music word pin falls outside its narration row")
    return frame


def _validate_music_event(
    document: JsonObject,
    dependencies: JsonObject,
    manifest: JsonObject,
    event: JsonObject,
    source: JsonObject,
    rate: Fraction,
    matched_visual: tuple[str, str] | None,
) -> None:
    """Derive signed music placement and treatment from the saved span and PCM pin."""
    event_id = cast(str, event["eventId"])
    music = cast(JsonObject, event["music"])
    binding = source.get("musicAudio")
    spans = _unique_by_id(document.get("rowAudioSpans", []), "music span")
    bindings = _unique_by_id(
        dependencies.get("musicBindings", []), "music binding", "spanId"
    )
    span = spans.get(music["spanId"])
    frozen = bindings.get(music["spanId"])
    if (
        span is None
        or frozen is None
        or not isinstance(binding, dict)
        or binding != frozen
        or binding.get("status") != "ready"
        or span.get("source") != frozen.get("source")
        or music["startRowId"] != span["startRowId"]
        or music["endRowId"] != span["endRowId"]
        or event_id
        != music_event_id(document["id"], span["id"], span["source"]["artifactId"])
    ):
        raise _error(f"music event {event_id} is not bound to its frozen saved span")
    source_hash = hashlib.sha256(
        f"music-source:{span['id']}:{span['source']['artifactId']}".encode()
    ).hexdigest()[:32]
    expected_source_id = (
        f"{source_hash[:8]}-{source_hash[8:12]}-5{source_hash[13:16]}"
        f"-8{source_hash[17:20]}-{source_hash[20:]}"
    )
    content_hash = _require_hash(span["source"]["contentHash"], "music source hash")
    provenance = cast(JsonObject, event["provenance"])
    if (
        music["audioHash"] != content_hash
        or provenance.get("originalSourceHash") != content_hash
        or provenance.get("deliveredSourceHash") != content_hash
        or provenance.get("blockId")
        != (matched_visual[0] if matched_visual else span["startRowId"])
        or provenance.get("sourceId") != expected_source_id
        or event.get("audio") is not None
        or event.get("sourceTimeMapping") is not None
        or event.get("preparationBindingHash") is not None
    ):
        raise _error(f"music event {event_id} differs from its verified PCM identity")

    # Recover anchor positions from the ordinary program events and frozen inputs.
    timing = span.get("timing")
    rows: list[tuple[str, str | None, int, int]] = []
    section: str | None = None
    for block in document["activeDraft"]["blocks"]:
        if block["type"] == "section":
            section = block["id"]
            continue
        if (
            block["type"] not in {"narration", "visual_only"}
            or block.get("state", "active") != "active"
        ):
            continue
        possible = [
            other
            for other in manifest["events"]
            if other["kind"]
            == ("narration" if block["type"] == "narration" else "primary_visual")
            and other["provenance"].get("blockId") == block["id"]
        ]
        if block["type"] == "visual_only" and (timing is not None or not possible):
            possible.extend(
                other
                for other in manifest["events"]
                if other["kind"] == "placeholder"
                and other.get("trackRole") == "primary_root"
                and other["provenance"].get("blockId") == block["id"]
            )
        if not possible:
            raise _error(f"music row {block['id']} lacks compiled timing")
        ranges = [
            _range(other["recordRange"], "music row timing") for other in possible
        ]
        rows.append(
            (
                block["id"],
                section,
                min(pair[0] for pair in ranges),
                max(pair[1] for pair in ranges),
            )
        )
    record_start, record_end = _range(event["recordRange"], "music recordRange")
    source_start, source_end = _range(event["sourceRange"], "music sourceRange")
    samples = _safe_frame(binding["durationSamples"], "music samples", positive=True)
    available = (samples * rate.numerator) // (48000 * rate.denominator)
    requested = _safe_frame(
        music["requestedEndFrame"], "music requestedEndFrame", positive=True
    )
    if matched_visual is not None:
        pictures = [
            other
            for other in manifest["events"]
            if other["kind"] in {"primary_visual", "placeholder"}
            and other.get("trackRole") == "primary_root"
            and (
                other["provenance"].get("blockId"),
                other["provenance"].get("payloadId"),
            )
            == matched_visual
        ]
        if (
            len(pictures) != 1
            or _range(pictures[0]["recordRange"], "matched visual timing")
            != (record_start, record_end)
            or timing is None
            or not {"sourceInFrame", "sourceOutFrame"}.issubset(timing)
        ):
            raise _error(f"music event {event_id} differs from its signed visual match")
        timing = {
            "sourceInFrame": timing["sourceInFrame"],
            "sourceOutFrame": timing["sourceOutFrame"],
            "timelineIn": {"kind": "frame", "frame": record_start},
        }
    if timing is not None:
        fixed = {
            key: _music_pin_frame(value, document, dependencies, rows, rate)
            if key in {"timelineIn", "timelineOut"}
            else _safe_frame(value, "music source trim")
            for key, value in timing.items()
        }
        delivered = {
            "sourceInFrame": source_start,
            "sourceOutFrame": source_end,
            "timelineIn": record_start,
            "timelineOut": record_end,
        }
        # Equal positive durations make the fourth point unique.
        if (
            len(fixed) != 3
            or any(delivered[key] != value for key, value in fixed.items())
            or source_end - source_start != record_end - record_start
            or source_end > available
            or record_end > manifest["timeline"]["durationFrames"]
            or requested != record_end
        ):
            raise _error(
                f"music event {event_id} differs from its three signed timing pins"
            )
    else:
        row_ids = [row[0] for row in rows]
        if span["startRowId"] not in row_ids or span["endRowId"] not in row_ids:
            raise _error(f"music event {event_id} references uncompiled row endpoints")
        run = rows[
            row_ids.index(span["startRowId"]) : row_ids.index(span["endRowId"]) + 1
        ]
        if (
            not run
            or any(row[1] != run[0][1] for row in run)
            or any(previous[3] != following[2] for previous, following in pairwise(run))
        ):
            raise _error(f"music event {event_id} spans disconnected program rows")
        if (
            record_start != run[0][2]
            or requested != run[-1][3]
            or source_start != 0
            or source_end != record_end - record_start
            or record_end != min(requested, record_start + available)
        ):
            raise _error(f"music event {event_id} duration differs from signed span")
    settings = span.get("settings", {})
    supported = all(
        (
            key == "gainDb"
            and type(value) in {int, float}
            and math.isfinite(value)
            and -60 <= value <= 0
        )
        or (key == "trimStartFrames" and value == 0)
        or (key == "endpointMode" and value == "row_end")
        or (key == "loop" and value is False)
        or (key in {"fadeInFrames", "fadeOutFrames"} and value == 6)
        for key, value in settings.items()
    )
    if (
        not supported
        or not isinstance(music["gainDb"], (int, float))
        or isinstance(music["gainDb"], bool)
        or not math.isfinite(music["gainDb"])
        or music["gainDb"] != settings.get("gainDb", -12)
        or music["fadeInFrames"] != min(6, (record_end - record_start) // 2)
        or music["fadeOutFrames"] != min(6, (record_end - record_start) // 2)
    ):
        raise _error(
            f"music event {event_id} duration, gain or fades differ from signed span"
        )


def _validate_report_semantics(
    manifest: JsonObject,
    report: JsonObject,
    dependencies: JsonObject,
    temporary_presenter_events: set[str],
) -> None:
    events = _unique_by_id(manifest.get("events"), "manifest event", "eventId")
    results = _unique_by_id(report.get("eventResults"), "report event", "eventId")
    if set(results) != set(events):
        raise _error(
            "build report event results do not cover the exact manifest event set"
        )
    diagnostics = cast(list[JsonObject], report.get("diagnostics"))
    manual_completion_count = len(temporary_presenter_events)
    for event_id, event in events.items():
        result = results[event_id]
        provenance = cast(JsonObject, event["provenance"])
        temporary_presenter = event_id in temporary_presenter_events
        if (
            result.get("kind") != event.get("kind")
            or result.get("trackId") != event.get("trackId")
            or result.get("recordRange") != event.get("recordRange")
            or result.get("sourceId") != provenance.get("sourceId")
            or result.get("disposition")
            != ("manual_completion" if temporary_presenter else "placed")
            or (
                temporary_presenter
                and result.get("message") != _TEMPORARY_PRESENTER_EVENT_MESSAGE
            )
        ):
            raise _error(
                f"build report event result does not exactly cover event {event_id}"
            )

    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "manifest preparation", "requirementKey"
    )
    report_prep = cast(JsonObject, report.get("mediaPreparation"))
    requirements = _unique_by_id(
        report_prep.get("requirements"), "report media requirement", "requirementKey"
    )
    expected_prep_status = "complete" if bindings else "not_required"
    if (
        set(requirements) != set(bindings)
        or report_prep.get("status") != expected_prep_status
    ):
        raise _error(
            "build report media preparation does not cover the exact binding set"
        )
    for key, binding in bindings.items():
        item = requirements[key]
        original = cast(JsonObject, binding["originalSource"])
        verification = cast(JsonObject, binding["verification"])
        expected_status = (
            "reused" if binding.get("mode") == "verified_reuse" else "prepared"
        )
        if (
            item.get("status") != expected_status
            or item.get("bindingHash") != _compiler_hash(binding)
            or item.get("originalHash") != original.get("contentHash")
            or item.get("deliveredHash") != verification.get("deliveredHash")
            or item.get("diagnosticIds") != []
        ):
            raise _error(
                f"build report preparation result differs for requirement {key}"
            )

    summary = cast(JsonObject, report.get("summary"))
    if (
        summary.get("eventCount") != len(events)
        or summary.get("placedCount") != len(events) - manual_completion_count
        or summary.get("blockedCount") != 0
        or summary.get("diagnosticCount") != len(diagnostics)
        or summary.get("manualCompletionCount") != manual_completion_count
        or summary.get("recoveryActionCount") != len(report["recoveryActions"])
    ):
        raise _error("build report summary does not describe every event as placed")


@dataclass(frozen=True)
class _InputArtifact:
    key: str
    origin: Path
    relative_path: str
    content_hash: str
    kind: str
    generated: bytes | None = None


class _CachedIntegrityFailure(V2PackageError):
    """Cached bytes failed independent checks; a fresh-source retry is safe."""


class _MediaCacheSession:
    """One package's unique source identities, not one entry per event."""

    def __init__(self, root: Path, *, force_source: bool = False) -> None:
        self.store = PackageCache(root)
        self.force_source = force_source
        self.entries: dict[tuple[Path, str], tuple[FileStamp, CacheEntry | None]] = {}
        self.staged: dict[tuple[Path, str], Path] = {}
        self.cached_used: dict[str, CacheEntry] = {}
        self.reused = 0
        self.processed = 0
        self.used_cached_audio = False

    @staticmethod
    def _identity(source: Path, expected: str) -> tuple[Path, str]:
        return source.absolute(), expected

    def _stamp(self, source: Path) -> FileStamp:
        try:
            return source_stamp(source)
        except SourceChangedError as error:
            raise _error(str(error)) from error

    def _checked(
        self, source: Path, expected: str
    ) -> tuple[FileStamp, CacheEntry | None]:
        identity = self._identity(source, expected)
        if identity not in self.entries:
            stamp = self._stamp(source)
            try:
                entry = (
                    None
                    if self.force_source
                    else self.store.lookup(source, expected, stamp=stamp)
                )
            except SourceChangedError as error:
                raise _error(str(error)) from error
            self.entries[identity] = stamp, entry
        stamp, entry = self.entries[identity]
        if self._stamp(source) != stamp:
            raise _error(f"supplied media changed during package: {source}")
        return stamp, entry

    def checked_hash(self, source: Path, expected: str) -> str:
        # The cold source is streamed and hash-checked at the first stage copy.
        self._checked(source, expected)
        return expected

    def audio_bytes(self, source: Path, expected: str) -> bytes:
        stamp, entry = self._checked(source, expected)
        if entry is not None:
            try:
                raw = self.store.read_bytes(entry)
            except SourceChangedError as error:
                raise _error(str(error)) from error
            if raw is not None:
                self.used_cached_audio = True
                self.cached_used[entry.key] = entry
                return raw
        raw = source.read_bytes()
        if self._stamp(source) != stamp:
            raise _error(f"supplied media changed while reading audio: {source}")
        return raw

    def stage(self, artifact: _InputArtifact, destination: Path) -> None:
        source, expected = artifact.origin, artifact.content_hash
        stamp, entry = self._checked(source, expected)
        destination.parent.mkdir(parents=True, exist_ok=True)
        identity = self._identity(source, expected)
        previous = self.staged.get(identity)
        if previous is not None:
            # Repeated original:/source: entries share verified input identity,
            # but every published destination must be an independent inode.
            clone_or_copy(previous, destination)
        elif entry is not None:
            try:
                reused = self.store.materialize(entry, destination)
            except SourceChangedError as error:
                raise _error(str(error)) from error
            if reused:
                self.reused += 1
                self.cached_used[entry.key] = entry
            else:
                _copy_input_file(source, destination, expected)
                self.processed += 1
                self.store.publish(source, expected, destination, stamp=stamp)
        else:
            _copy_input_file(source, destination, expected)
            self.processed += 1
            try:
                self.store.publish(source, expected, destination, stamp=stamp)
            except SourceChangedError as error:
                raise _error(str(error)) from error
        if self._stamp(source) != stamp:
            destination.unlink(missing_ok=True)
            raise _error(f"supplied media changed while staging: {source}")
        self.staged[identity] = destination

    def discard_used(self) -> None:
        for entry in self.cached_used.values():
            self.store.discard(entry)


@dataclass(frozen=True)
class _Preparation:
    requirement_key: str
    record: JsonObject
    raw: bytes
    content_hash: str
    relative_path: str


def _validate_still_preparation(
    requirement_key: str,
    record: JsonObject,
    binding: JsonObject,
    source: JsonObject,
    delivered: JsonObject,
) -> None:
    original = binding["originalSource"]
    verification = binding["verification"]
    inputs = record["inputs"]
    evidence = record.get("stillEvidence")
    if not isinstance(evidence, dict):
        raise _error(f"prep {requirement_key} lacks verified PNG evidence")
    version = evidence.get("version")
    width, height = source.get("width"), source.get("height")
    if (
        source.get("kind") != "image"
        or source.get("demuxer") != "image2pipe"
        or type(source.get("frames")) is not int
        or source["frames"] != 1
        or type(width) is not int
        or type(height) is not int
        or min(width, height) <= 0
        or inputs.get("stillInterpretation") != version
        or evidence.get("sourceProbeHash") != original.get("probeHash")
    ):
        raise _error(f"prep {requirement_key} lacks verified PNG evidence")

    if version == "one_png_frame_held_at_timeline_rate/v1":
        if binding.get("mode") != "verified_reuse" or source != delivered:
            raise _error(f"prep {requirement_key} lacks verified PNG reuse evidence")
    elif version == "one_normalized_png_frame_held_at_timeline_rate/v1":
        orientation = evidence.get("orientation")
        if (
            binding.get("mode") != "derived_cfr"
            or source.get("codec") not in {"png", "mjpeg"}
            or type(orientation) is not int
            or not 1 <= orientation <= 8
            or identity_hash(inputs) != requirement_key
        ):
            raise _error(f"prep {requirement_key} has invalid still normalization")
        if orientation >= 5:
            width, height = height, width
    else:
        raise _error(f"prep {requirement_key} has an unsupported still receipt")

    strict = evidence.get("strictPng")
    if (
        type(delivered.get("frames")) is not int
        or delivered
        != {
            "kind": "image",
            "demuxer": "image2pipe",
            "codec": "png",
            "width": width,
            "height": height,
            "frames": 1,
        }
        or not isinstance(strict, dict)
        or type(strict.get("decodedFrameCount")) is not int
        or strict
        != {
            "sourceHash": verification.get("deliveredHash"),
            "width": width,
            "height": height,
            "decodedFrameCount": 1,
        }
    ):
        raise _error(f"prep {requirement_key} lacks verified PNG evidence")
    rate = _fraction(binding.get("targetRate"), "still target rate", positive=True)
    if (
        type(verification.get("decodedFrameCount")) is not int
        or verification["decodedFrameCount"] != 1
        or _fraction(
            verification.get("decodedFrameRate"), "still decoded rate", positive=True
        )
        != rate
        or _fraction(
            verification.get("videoTimeBase"), "still time base", positive=True
        )
        * rate
        != 1
    ):
        raise _error(f"prep {requirement_key} has invalid PNG logical timing")


def _validate_preparations(
    document: JsonObject,
    dependencies: JsonObject,
    manifest: JsonObject,
    report: JsonObject,
    preparation_paths: Mapping[str, Path],
) -> dict[str, _Preparation]:
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    if set(preparation_paths) != set(bindings):
        missing = sorted(set(bindings) - set(preparation_paths))
        extra = sorted(set(preparation_paths) - set(bindings))
        raise _error(
            f"preparation_paths key mismatch; missing={missing}, extra={extra}"
        )
    occurrences: dict[str, list[JsonObject]] = {}
    for occurrence in cast(
        list[JsonObject], dependencies.get("occurrenceResolutions", [])
    ):
        key = occurrence.get("preparedMediaRequirementKey")
        if key is not None:
            occurrences.setdefault(cast(str, key), []).append(occurrence)
    prepared: dict[str, _Preparation] = {}
    for requirement_key, binding in bindings.items():
        source_path = preparation_paths[requirement_key]
        if not isinstance(source_path, Path):
            raise _error(
                f"preparation path for {requirement_key} must be a pathlib.Path"
            )
        record, raw = _load_json(
            source_path, f"#174 preparation receipt {requirement_key}"
        )
        digest = _hash_bytes(raw)
        descriptors = occurrences.get(requirement_key, [])
        if not descriptors:
            raise _error(
                f"preparation receipt {requirement_key} has no compiler occurrence"
            )
        descriptor = descriptors[0]
        if record.get("recordVersion") != "authoring-media-preparation/v1":
            raise _error(f"prep {requirement_key} has an unsupported record version")
        if (
            record.get("requirementKey") != requirement_key
            or record.get("binding") != binding
        ):
            raise _error(f"prep {requirement_key} differs from its manifest binding")
        inputs = cast(JsonObject, record.get("inputs"))
        original = cast(JsonObject, binding["originalSource"])
        mapping = cast(JsonObject, binding["timeMapping"])
        if any(
            inputs.get("mediaReferenceId") != occurrence.get("mediaReferenceId")
            or inputs.get("sourceSnapshot") != occurrence.get("sourceSnapshot")
            or inputs.get("sourceFrameMap") != occurrence.get("sourceFrameMap")
            or original.get("mediaReferenceId") != occurrence.get("mediaReferenceId")
            or original.get("contentHash")
            != cast(JsonObject, occurrence["sourceSnapshot"]).get("contentHash")
            or original.get("probeHash")
            != cast(JsonObject, occurrence["sourceSnapshot"]).get("probeHash")
            or mapping.get("sourceFrameMap") != occurrence.get("sourceFrameMap")
            for occurrence in descriptors
        ) or (
            inputs.get("requestedRange") != binding.get("requestedRange")
            or inputs.get("targetRate") != binding.get("targetRate")
            or inputs.get("profile") != binding.get("profile")
        ):
            raise _error(
                f"preparation receipt {requirement_key} input mapping is stale"
            )
        if (
            type(inputs.get("videoStreamIndex")) is not int
            or inputs["videoStreamIndex"] < 0
        ):
            raise _error(f"prep {requirement_key} has an invalid video stream index")
        audio_stream_index = inputs.get("audioStreamIndex")
        if audio_stream_index is not None and (
            type(audio_stream_index) is not int or audio_stream_index < 0
        ):
            raise _error(f"prep {requirement_key} has an invalid audio stream index")

        source_probe = record.get("sourceProbe")
        delivered_probe = record.get("deliveredProbe")
        tools = record.get("tools")
        profile = record.get("profile")
        policy = record.get("policy")
        commands = record.get("commands")
        geometry = record.get("geometry")
        if (
            not isinstance(source_probe, dict)
            or not isinstance(delivered_probe, dict)
            or not isinstance(tools, dict)
        ):
            raise _error(
                f"preparation receipt {requirement_key} lacks probe/tool evidence"
            )
        if (
            not isinstance(profile, dict)
            or not isinstance(policy, dict)
            or not isinstance(commands, list)
            or not isinstance(geometry, dict)
        ):
            raise _error(
                f"prep {requirement_key} lacks profile/command/geometry evidence"
            )
        verification = cast(JsonObject, binding["verification"])
        binding_profile = cast(JsonObject, binding["profile"])
        if (
            identity_hash(source_probe) != original.get("probeHash")
            or identity_hash(delivered_probe) != verification.get("probeHash")
            or identity_hash(profile) != binding_profile.get("profileHash")
            or identity_hash(policy) != binding_profile.get("policyHash")
            or identity_hash(tools) != binding_profile.get("toolHash")
        ):
            raise _error(
                f"prep {requirement_key} probe/profile/tool hashes do not bind"
            )
        if "image" in (source_probe.get("kind"), delivered_probe.get("kind")):
            _validate_still_preparation(
                requirement_key, record, binding, source_probe, delivered_probe
            )
        if mapping.get("sourceFrameMap") != descriptor.get(
            "sourceFrameMap"
        ) or mapping.get("mappingHash") != identity_hash(
            {key: value for key, value in mapping.items() if key != "mappingHash"}
        ):
            raise _error(
                f"prep {requirement_key} mapping hash or source map is invalid"
            )
        if binding.get("mode") not in {"verified_reuse", "derived_cfr"}:
            raise _error(f"preparation receipt {requirement_key} mode is unsupported")
        if binding.get("mode") == "derived_cfr":
            derivation = binding.get("derivation")
            if not isinstance(derivation, dict) or (
                derivation.get("sourceHash") != original.get("contentHash")
                or derivation.get("outputHash") != verification.get("deliveredHash")
                or derivation.get("profileHash") != binding_profile.get("profileHash")
                or derivation.get("toolHash") != binding_profile.get("toolHash")
                or derivation.get("commandHash") != identity_hash(commands)
            ):
                raise _error(
                    f"prep {requirement_key} derived output evidence is invalid"
                )
        elif (
            original.get("contentHash") != verification.get("deliveredHash")
            or "derivation" in binding
        ):
            raise _error(f"prep {requirement_key} verified-reuse identity is invalid")
        _fraction(
            geometry.get("packageStart"), f"preparation {requirement_key} packageStart"
        )
        package_end = _fraction(
            geometry.get("packageEnd"), f"preparation {requirement_key} packageEnd"
        )
        package_start = _fraction(
            geometry.get("packageStart"), f"preparation {requirement_key} packageStart"
        )
        if package_end <= package_start or not isinstance(
            geometry.get("selectedPackageFrames"), list
        ):
            raise _error(
                f"preparation receipt {requirement_key} geometry is empty or incomplete"
            )
        for index, frame in enumerate(geometry["selectedPackageFrames"]):
            _safe_frame(
                frame, f"preparation {requirement_key} selectedPackageFrames[{index}]"
            )
        for field in ("sourceCoverSurplus", "terminalQuantization"):
            _fraction(geometry.get(field), f"preparation {requirement_key} {field}")
        _safe_frame(
            geometry.get("requiredExclusiveLogicalFrame"),
            f"preparation {requirement_key} requiredExclusiveLogicalFrame",
        )
        expected_mapping_origin = _fraction(
            cast(JsonObject, descriptor["sourceFrameMap"]).get(
                "loggedTimeAtPackageFrameZero"
            ),
            f"preparation {requirement_key} logged package origin",
        )
        if binding["mode"] == "derived_cfr":
            expected_mapping_origin += package_start
        if (
            mapping.get("sourceOrigin")
            != {
                "numerator": expected_mapping_origin.numerator,
                "denominator": expected_mapping_origin.denominator,
            }
            or mapping.get("deliveredOrigin") != {"numerator": 0, "denominator": 1}
            or mapping.get("deliveredRate") != binding.get("targetRate")
        ):
            raise _error(
                f"prep {requirement_key} source/delivered time mapping is invalid"
            )
        audio_record = record.get("audio")
        source_audio_mappings = cast(JsonObject, descriptor["sourceFrameMap"]).get(
            "sourceAudioStreamMappings"
        )
        if audio_record is not None:
            if (
                not isinstance(audio_record, dict)
                or not isinstance(source_audio_mappings, list)
                or len(source_audio_mappings) != 1
            ):
                raise _error(
                    f"preparation receipt {requirement_key} has unbound audio evidence"
                )
            audio_map = cast(JsonObject, source_audio_mappings[0])
            audio_probe = audio_record.get("probe")
            audio_streams = (
                audio_probe.get("streams") if isinstance(audio_probe, dict) else None
            )
            if (
                not isinstance(audio_streams, list)
                or len(audio_streams) != 1
                or not isinstance(audio_streams[0], dict)
            ):
                raise _error(
                    f"prep {requirement_key} has an invalid prepared-audio probe"
                )
            audio_stream = cast(JsonObject, audio_streams[0])
            source_rate = audio_map.get("sampleRate")
            source_first = audio_record.get("sourceFirstSample")
            source_exclusive = audio_record.get("sourceExclusiveSample")
            resampled_first = audio_record.get("resampledFirstSample")
            resampled_exclusive = audio_record.get("resampledExclusiveSample")
            decoded_samples = audio_record.get("decodedSamples")
            if (
                audio_record.get("sourceAudioHash") != audio_map.get("audioHash")
                or type(source_rate) is not int
                or source_rate not in {44100, 48000}
                or type(source_first) is not int
                or type(source_exclusive) is not int
                or type(resampled_first) is not int
                or type(resampled_exclusive) is not int
                or type(decoded_samples) is not int
                or source_first < 0
                or source_exclusive <= source_first
                or resampled_first < 0
                or resampled_exclusive <= resampled_first
                or decoded_samples <= 0
                or abs(decoded_samples - (resampled_exclusive - resampled_first)) > 1
                or audio_stream.get("codec_name") != "pcm_s24le"
                or str(audio_stream.get("sample_rate")) != "48000"
                or audio_stream.get("channels") != audio_record.get("channels")
                or identity_hash(audio_record.get("probe"))
                != audio_record.get("probeHash")
            ):
                raise _error(
                    f"prep {requirement_key} source-audio probe/range is invalid"
                )
            for field in (
                "sourcePtsOrigin",
                "deliveredTimeAtFirstSample",
                "boundaryOffset",
                "endpointError",
                "decodedSourceTimestampResidual",
                "decodedSourceTimestampDrift",
            ):
                _fraction(
                    audio_record.get(field),
                    f"preparation {requirement_key} audio {field}",
                )
            endpoint_error = _fraction(
                audio_record.get("endpointError"),
                f"preparation {requirement_key} audio endpointError",
            )
            video_frame_map = cast(JsonObject, descriptor["sourceFrameMap"])
            audio_pts_origin = _fraction(
                audio_map.get("packagePtsOrigin"),
                f"prep {requirement_key} source-audio PTS origin",
            )
            audio_record_pts_origin = _fraction(
                audio_record.get("sourcePtsOrigin"),
                f"prep {requirement_key} prepared-audio PTS origin",
            )
            audio_logged_origin = _fraction(
                audio_map.get("loggedTimeAtPackageOrigin"),
                f"prep {requirement_key} source-audio logged origin",
            )
            video_pts_origin = _fraction(
                video_frame_map.get("packageVideoPtsOrigin"),
                f"prep {requirement_key} package-video PTS origin",
            )
            video_logged_origin = _fraction(
                video_frame_map.get("loggedTimeAtPackageFrameZero"),
                f"prep {requirement_key} package-video logged origin",
            )
            package_audio_start = video_pts_origin + package_start - audio_pts_origin
            package_audio_end = video_pts_origin + package_end - audio_pts_origin
            expected_audio_logged_origin = (
                video_logged_origin + audio_pts_origin - video_pts_origin
            )
            expected_source_first = _ceil_fraction(package_audio_start * source_rate)
            expected_source_end = _ceil_fraction(package_audio_end * source_rate)
            expected_resampled_first = _ceil_fraction(package_audio_start * 48000)
            expected_resampled_end = _ceil_fraction(package_audio_end * 48000)
            expected_offset = (
                Fraction(expected_resampled_first, 48000) - package_audio_start
            )
            expected_delivered_first = (
                package_start + expected_offset
                if binding["mode"] == "verified_reuse"
                else expected_offset
            )
            actual_offset = _fraction(
                audio_record.get("boundaryOffset"),
                f"prep {requirement_key} source-audio boundary offset",
            )
            actual_delivered_first = _fraction(
                audio_record.get("deliveredTimeAtFirstSample"),
                f"prep {requirement_key} source-audio first-sample time",
            )
            if (
                audio_map.get("probeHash") != original.get("probeHash")
                or audio_map.get("sampleRate") != source_rate
                or audio_record_pts_origin != audio_pts_origin
                or audio_logged_origin != expected_audio_logged_origin
                or source_first != expected_source_first
                or source_exclusive != expected_source_end
                or resampled_first != expected_resampled_first
                or resampled_exclusive != expected_resampled_end
                or actual_offset != expected_offset
                or actual_delivered_first != expected_delivered_first
            ):
                raise _error(
                    f"prep {requirement_key} audio coordinates do not bind to P2"
                )
            if endpoint_error > Fraction(1, 48000):
                raise _error(
                    f"prep {requirement_key} audio endpoint exceeds one sample"
                )
        if (
            record.get("audio") is None
            and binding["verification"]["sourceAudio"].get("status") == "aligned"
        ):
            raise _error(f"prep {requirement_key} omits aligned source-audio bytes")
        rel = (
            f"{BUILD_DIRECTORY}/"
            f"{_id_component(cast(str, manifest['buildId']), 'build id')}"
            f"/Preparation/receipts/{hashlib.sha256(requirement_key.encode('utf-8')).hexdigest()}/receipt.json"
        )
        prepared[requirement_key] = _Preparation(
            requirement_key, record, raw, digest, rel
        )

    del document, report
    return prepared


def _quote_carrier(event_id: str, timeline: JsonObject) -> _InputArtifact:
    try:
        name = native_image_motion.native_still_stem(event_id)
        raw = transparent_graphic_carrier(timeline["width"], timeline["height"])
    except ValueError as error:
        raise _error(f"invalid quote carrier: {error}") from error
    return _InputArtifact(
        f"event:{event_id}",
        Path("."),
        f"Media/Resolved/{name}.png",
        _hash_bytes(raw),
        "still",
        raw,
    )


def _still_credit_artifact(event: JsonObject, timeline: JsonObject) -> _InputArtifact:
    try:
        raw = render_credit(
            event["stillCredit"]["text"], timeline["width"], timeline["height"]
        )
        stem = native_image_motion.native_still_stem(event["eventId"])
    except (ValueError, OSError, UnicodeError) as error:
        raise _error(f"still credit graphic cannot be rendered: {error}") from error
    return _InputArtifact(
        f"event:{event['eventId']}",
        Path("."),
        f"Media/Resolved/{stem}.png",
        _hash_bytes(raw),
        "still",
        raw,
    )


def _media_artifacts(
    manifest: JsonObject,
    prepared: Mapping[str, _Preparation],
    media_paths: Mapping[str, Path],
    timing: _PackageSubtimings | None = None,
    cache: _MediaCacheSession | None = None,
) -> dict[str, _InputArtifact]:
    sources = _unique_by_id(manifest.get("sources"), "source")
    events = _unique_by_id(manifest.get("events"), "event", "eventId")
    # Resolve's native OTIO import can resolve an image reference by basename
    # when the OTIO URL is relative.  Keeping two files named <source-id>.png
    # lets its media search bind an authored event to the archived *original*
    # rather than the verified delivery source.  New motion-bearing packages
    # give the immutable original a distinct basename; legacy packages remain
    # byte-identical, and both copies retain their independent hashes.
    motion_source_ids = {
        cast(str, cast(JsonObject, event["provenance"])["sourceId"])
        for event in events.values()
        if event["kind"] in {"primary_visual", "overlay_visual"}
        and isinstance(event.get("pictureTreatment"), dict)
        and "imageMotion" in event["pictureTreatment"]
    }
    expected_hashes: dict[str, tuple[str, str, str]] = {}
    source_usage: dict[str, set[str]] = defaultdict(set)
    for event in events.values():
        kind = cast(str, event["kind"])
        source_id = cast(JsonObject, event["provenance"]).get("sourceId")
        if kind in {
            "primary_visual",
            "overlay_visual",
            "narration",
            "source_audio",
            "music",
        }:
            if not isinstance(source_id, str):
                raise _error(f"event {event['eventId']} has no source identity")
            source_usage[source_id].add(kind)
    for source_id, source in sources.items():
        narration = source.get("narrationAudio")
        if isinstance(narration, dict):
            expected = _require_hash(
                narration.get("audioHash"), f"narration {source_id} audio hash"
            )
            kinds = source_usage.get(source_id, set())
            if kinds and kinds != {"narration"}:
                raise _error(
                    f"narration source {source_id} is assigned to a non-narration event"
                )
            expected_hashes[f"source:{source_id}"] = (expected, "Narration", "audio")
            continue
        music = source.get("musicAudio")
        if isinstance(music, dict):
            expected = _require_hash(
                cast(JsonObject, music["source"])["contentHash"],
                f"music source {source_id} hash",
            )
            if source_usage.get(source_id) != {"music"}:
                raise _error(
                    f"music source {source_id} is not used exclusively for music"
                )
            expected_hashes[f"source:{source_id}"] = (expected, "Narration", "audio")
            expected_hashes[f"original:{source_id}"] = (
                expected,
                "Preparation",
                "original",
            )
            continue
        expected = _require_hash(
            source.get("deliveredHash"), f"source {source_id} delivered hash"
        )
        kinds = source_usage.get(source_id, set())
        if "narration" in kinds or not kinds:
            raise _error(f"prepared source {source_id} has no matching visual event")
        event_treatments = {
            cast(JsonObject, event.get("pictureTreatment") or {}).get("kind")
            for event in events.values()
            if cast(JsonObject, event["provenance"]).get("sourceId") == source_id
            and event["kind"] in {"primary_visual", "overlay_visual"}
        }
        native_kind = "still" if event_treatments == {"still_frame"} else "video"
        expected_hashes[f"source:{source_id}"] = (expected, "Resolved", native_kind)
        original_hash = _require_hash(
            source.get("originalHash"), f"source {source_id} original hash"
        )
        expected_hashes[f"original:{source_id}"] = (
            original_hash,
            "Preparation",
            "original",
        )

    for event in events.values():
        kind = cast(str, event["kind"])
        event_id = cast(str, event["eventId"])
        if kind == "placeholder":
            treatment = cast(JsonObject, event["pictureTreatment"])
            if treatment["kind"] == "slate":
                timeline = cast(JsonObject, manifest["timeline"])
                with _measure(timing, "slates"):
                    generated = _render_slate(
                        cast(str, treatment["text"]),
                        _safe_frame(
                            timeline.get("width"), "timeline width", positive=True
                        ),
                        _safe_frame(
                            timeline.get("height"), "timeline height", positive=True
                        ),
                    )
                expected = _hash_bytes(generated)
            else:
                reference = cast(JsonObject, treatment["reference"])
                expected = _require_hash(
                    reference.get("contentHash"),
                    f"placeholder {event_id} reference hash",
                )
            expected_hashes[f"event:{event_id}"] = (expected, "Resolved", "still")
        elif kind == "source_audio":
            binding_hash = event.get("preparationBindingHash")
            preparation = next(
                (
                    item
                    for item in prepared.values()
                    if _compiler_hash(item.record.get("binding")) == binding_hash
                ),
                None,
            )
            if preparation is None or not isinstance(
                preparation.record.get("audio"), dict
            ):
                raise _error(
                    f"source audio event {event_id} has no hash-bound #174 WAV"
                )
            audio = cast(JsonObject, preparation.record["audio"])
            expected = _require_hash(
                audio.get("contentHash"), f"source audio event {event_id} contentHash"
            )
            audio_info = cast(JsonObject, event["audio"])
            if audio_info.get("audioHash") != audio.get("sourceAudioHash"):
                raise _error(f"source audio {event_id} is not bound to its #174 stream")
            source_map = cast(
                JsonObject,
                cast(JsonObject, event["sourceTimeMapping"])["sourceFrameMap"],
            )
            audio_maps = source_map.get("sourceAudioStreamMappings")
            if (
                not isinstance(audio_maps, list)
                or len(audio_maps) != 1
                or audio_maps[0].get("audioHash") != audio_info.get("audioHash")
            ):
                raise _error(
                    f"source audio {event_id} is not bound to one verified stream"
                )
            sample_range = cast(JsonObject, audio_info.get("sampleRange"))
            sample_start, sample_end = _range(
                sample_range, f"source audio event {event_id} sampleRange"
            )
            if (
                sample_start < audio["sourceFirstSample"]
                or sample_end > audio["sourceExclusiveSample"]
            ):
                raise _error(
                    f"source audio {event_id} exceeds the prepared sample interval"
                )
            if (
                media_paths.get(f"event:{event_id}") is not None
                and media_paths[f"event:{event_id}"].suffix.lower() != ".wav"
            ):
                raise _error(f"source audio {event_id} must use the #174 WAV sidecar")
            expected_hashes[f"event:{event_id}"] = (expected, "Narration", "audio")

    if set(media_paths) != set(expected_hashes):
        missing = sorted(set(expected_hashes) - set(media_paths))
        extra = sorted(set(media_paths) - set(expected_hashes))
        raise _error(f"media_paths key mismatch; missing={missing}, extra={extra}")
    build_id = _id_component(cast(str, manifest["buildId"]), "build id")
    artifacts: dict[str, _InputArtifact] = {}
    for key, (expected_hash, area, kind) in expected_hashes.items():
        source_path = media_paths[key]
        if not isinstance(source_path, Path):
            raise _error(f"media path for {key} must be a pathlib.Path")
        _require_path_components_no_symlink(source_path, f"media path {key}")
        _require_regular(source_path, f"media path {key}")
        with _measure(timing, "source hash"):
            actual = (
                _file_hash(source_path)
                if cache is None
                else cache.checked_hash(source_path, expected_hash)
            )
        if actual != expected_hash:
            raise _error(f"media hash mismatch for {key}: {expected_hash} != {actual}")
        suffix = _suffix(source_path)
        if key.startswith(("source:", "original:")):
            identity = key.split(":", 1)[1]
            if identity in sources and "musicAudio" in sources[identity]:
                if suffix.lower() != ".wav":
                    raise _error(f"music source {identity} must be a PCM WAV")
                suffix = ".wav"
        if key.startswith("source:"):
            identity = _id_component(key.removeprefix("source:"), "source id")
            # Studio 21.1.1.10 parses numeric runs anywhere in PNG filenames
            # as image sequences, even when followed by "-still". Give new
            # authored-motion stills a reversible alphabet-only UUID basename.
            # Preserve byte-identical legacy package filenames.
            delivered_name = (
                native_image_motion.native_still_stem(identity)
                if identity in motion_source_ids and kind == "still"
                else identity
            )
            relative = f"{MEDIA_DIRECTORY}/{area}/{delivered_name}{suffix}"
        elif key.startswith("original:"):
            identity = _id_component(key.removeprefix("original:"), "source id")
            unique_original_suffix = (
                ".original" if identity in motion_source_ids else ""
            )
            relative = (
                f"{BUILD_DIRECTORY}/{build_id}/Preparation/original/"
                f"{identity}{unique_original_suffix}{suffix}"
            )
        else:
            identity = _id_component(key.removeprefix("event:"), "event id")
            event = events[identity]
            if event["kind"] == "placeholder":
                treatment = cast(JsonObject, event["pictureTreatment"])
                if (
                    treatment.get("kind") == "slate"
                    and source_path.suffix.lower() != ".png"
                ):
                    raise _error(f"placeholder slate {identity} must use PNG bytes")
            relative = f"{MEDIA_DIRECTORY}/{area}/{identity}{suffix}"
        if (
            key.startswith(("source:", "original:"))
            and identity in sources
            and "musicAudio" in sources[identity]
        ):
            if suffix.lower() != ".wav":
                raise _error(f"music source {identity} must be a PCM WAV")
            try:
                samples = inspect_music(source_path, expected_hash)
            except BuildJobError as error:
                raise _error(f"music source {identity}: {error}") from error
            if samples != sources[identity]["musicAudio"]["durationSamples"]:
                raise _error(
                    f"music source {identity} duration differs from frozen samples"
                )
        _safe_relative(relative, f"package path for {key}")
        artifacts[key] = _InputArtifact(key, source_path, relative, actual, kind)
    for event in events.values():
        if event["kind"] == "quote_box":
            carrier = _quote_carrier(event["eventId"], manifest["timeline"])
            artifacts[carrier.key] = carrier
        elif event["kind"] == "still_credit":
            credit = _still_credit_artifact(event, manifest["timeline"])
            artifacts[credit.key] = credit
    by_binding = {
        _compiler_hash(item.record["binding"]): item for item in prepared.values()
    }
    rate = _fraction(manifest["timeline"]["frameRate"], "timeline rate", positive=True)
    for event in events.values():
        if event["kind"] != "source_audio":
            continue
        event_id = event["eventId"]
        audio = by_binding[event["preparationBindingHash"]].record["audio"]
        try:
            plan = endpoint_plan(event, audio, rate)
            if plan is None:
                continue
            artifact = artifacts[f"event:{event_id}"]
            with _measure(timing, "audio"):
                input_bytes = (
                    artifact.origin.read_bytes()
                    if cache is None
                    else cache.audio_bytes(artifact.origin, artifact.content_hash)
                )
                raw = endpoint_wav(input_bytes, plan, audio)
        except (OSError, ValueError) as error:
            if cache is not None and cache.used_cached_audio:
                raise _CachedIntegrityFailure(
                    f"cached source audio {event_id} could not be processed"
                ) from error
            raise _error(f"source audio {event_id}: {error}") from error
        original_key = f"original-audio:{event_id}"
        artifacts[original_key] = _InputArtifact(
            original_key,
            artifact.origin,
            _original_audio_path(manifest, event_id),
            artifact.content_hash,
            "audio",
        )
        artifacts[artifact.key] = _InputArtifact(
            artifact.key,
            artifact.origin,
            artifact.relative_path,
            _hash_bytes(raw),
            artifact.kind,
            raw,
        )
    return artifacts


def _original_audio_path(manifest: JsonObject, event_id: str) -> str:
    return f"{BUILD_DIRECTORY}/{manifest['buildId']}/Preparation/audio/{event_id}.wav"


def _ceil_fraction(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _source_audio_range(
    event: JsonObject,
    preparation: _Preparation,
    timeline_rate: Fraction,
) -> dict[str, int]:
    event_id = cast(str, event["eventId"])
    audio_record = cast(JsonObject, preparation.record["audio"])
    try:
        plan = endpoint_plan(event, audio_record, timeline_rate)
    except ValueError as error:
        raise _error(
            f"source audio {event_id} does not map to exact timeline frames: {error}"
        ) from error
    audio = cast(JsonObject, event["audio"])
    mapping = cast(JsonObject, event["sourceTimeMapping"])
    source_frame_map = cast(JsonObject, mapping["sourceFrameMap"])
    stream_mappings = source_frame_map.get("sourceAudioStreamMappings")
    if not isinstance(stream_mappings, list) or len(stream_mappings) != 1:
        raise _error(
            f"source audio event {event_id} has no unique verified source stream"
        )
    stream = cast(JsonObject, stream_mappings[0])
    source_sample_rate = _safe_frame(
        stream.get("sampleRate"), f"source audio {event_id} sampleRate", positive=True
    )
    audio_range = cast(JsonObject, audio["sampleRange"])
    sample_start, sample_end = _range(
        audio_range, f"source audio {event_id} sampleRange"
    )
    audio_probe = cast(JsonObject, audio_record.get("probe"))
    audio_streams = audio_probe.get("streams")
    if (
        not isinstance(audio_streams, list)
        or len(audio_streams) != 1
        or not isinstance(audio_streams[0], dict)
    ):
        raise _error(f"source audio event {event_id} has no unique prepared PCM stream")
    audio_stream = cast(JsonObject, audio_streams[0])
    if (
        audio_stream.get("codec_name") != "pcm_s24le"
        or str(audio_stream.get("sample_rate")) != "48000"
    ):
        raise _error(
            f"source audio event {event_id} is not the verified 48 kHz PCM sidecar"
        )
    if plan is not None:
        record_start, record_end = _range(
            event["recordRange"], "source audio record range"
        )
        return {"startFrame": 0, "durationFrames": record_end - record_start}
    # The accepted #174 receipt pins PCM rate in its independently hashed probe;
    # it intentionally has no redundant top-level audio.sampleRate field.
    output_sample_rate = 48000
    resampled_first = _safe_frame(
        audio_record.get("resampledFirstSample"),
        f"source audio {event_id} resampledFirstSample",
    )
    # P2's verified binding maps the original source sample edge to the prepared
    # 48 kHz sidecar by subtracting its absolute first PCM sample. Keeping this
    # in exact rational seconds avoids mixing package PTS and delivered origins.
    local_start = Fraction(sample_start, source_sample_rate) - Fraction(
        resampled_first, output_sample_rate
    )
    local_end = Fraction(sample_end, source_sample_rate) - Fraction(
        resampled_first, output_sample_rate
    )
    if local_end <= local_start:
        raise _error(
            f"source audio event {event_id} maps to an empty or reversed WAV interval"
        )
    start_frames = local_start * timeline_rate
    end_frames = local_end * timeline_rate
    if start_frames.denominator != 1 or end_frames.denominator != 1:
        raise _error(f"source audio {event_id} does not map to exact timeline frames")
    start_counter, end_counter = start_frames.numerator, end_frames.numerator
    record_start, record_end = _range(
        event["recordRange"], f"source audio event {event_id} recordRange"
    )
    if (
        start_counter < 0
        or end_counter <= start_counter
        or end_counter - start_counter != record_end - record_start
    ):
        raise _error(
            f"source audio {event_id} native range differs from record duration"
        )
    first_sample = (
        _ceil_fraction(Fraction(sample_start * output_sample_rate, source_sample_rate))
        - resampled_first
    )
    exclusive_sample = (
        _ceil_fraction(Fraction(sample_end * output_sample_rate, source_sample_rate))
        - resampled_first
    )
    decoded_samples = _safe_frame(
        audio_record.get("decodedSamples"),
        f"source audio {event_id} decodedSamples",
        positive=True,
    )
    if not 0 <= first_sample < exclusive_sample <= decoded_samples:
        raise _error(
            f"source audio event {event_id} maps outside its verified WAV sidecar"
        )
    available_frames = Fraction(decoded_samples, output_sample_rate) * timeline_rate
    if Fraction(end_counter, 1) > available_frames:
        raise _error(f"source audio {event_id} frame range exceeds WAV duration")
    return {"startFrame": start_counter, "durationFrames": end_counter - start_counter}


def _delivery_view(
    manifest: JsonObject,
    dependencies: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    *,
    source_paths: Mapping[str, str] | None = None,
    validate: bool = True,
    cache: _MediaCacheSession | None = None,
    encoded_bars_evidence: JsonObject | None = None,
) -> JsonObject:
    encoded_bars_evidence = _validate_encoded_bars_evidence(
        manifest, dependencies, prepared, encoded_bars_evidence
    )
    events = cast(list[JsonObject], manifest["events"])
    source_records = _unique_by_id(manifest.get("sources"), "source")
    binding_by_hash = {
        _compiler_hash(item.record["binding"]): item for item in prepared.values()
    }
    timeline_rate = _fraction(
        cast(JsonObject, manifest["timeline"]).get("frameRate"),
        "timeline frame rate",
        positive=True,
    )

    source_specs: dict[str, tuple[str, str, str]] = {}
    event_sources: dict[str, str] = {}
    for event in events:
        kind = cast(str, event["kind"])
        event_id = cast(str, event["eventId"])
        provenance = cast(JsonObject, event["provenance"])
        if kind == "script_marker":
            continue
        if kind in {"placeholder", "quote_box", "still_credit"}:
            source_id = event_id
            key = f"event:{event_id}"
            native_kind = "still"
        elif kind == "source_audio":
            source_id = event_id
            key = f"event:{event_id}"
            native_kind = "audio"
        else:
            source_id = cast(str, provenance["sourceId"])
            key = f"source:{source_id}"
            source = source_records[source_id]
            if isinstance(source.get("narrationAudio"), dict) or isinstance(
                source.get("musicAudio"), dict
            ):
                native_kind = "audio"
            else:
                treatment = event.get("pictureTreatment")
                native_kind = (
                    "still"
                    if isinstance(treatment, dict)
                    and treatment.get("kind") == "still_frame"
                    else "video"
                )
        artifact = artifacts.get(key)
        if artifact is None:
            raise _error(
                f"delivery view event {event_id} has no explicit media bytes for {key}"
            )
        expected_kind = artifact.kind
        if expected_kind != native_kind and not (
            expected_kind == "video" and native_kind == "still"
        ):
            raise _error(f"delivery view source {source_id} has conflicting media kind")
        if source_paths is not None:
            package_path = source_paths.get(source_id)
            if package_path is None:
                raise _error(
                    f"delivery view source {source_id} has no verified package path"
                )
        else:
            package_path = artifact.relative_path
        spec = (native_kind, package_path, artifact.content_hash)
        previous = source_specs.get(source_id)
        if previous is not None and previous != spec:
            raise _error(f"delivery source {source_id} has conflicting reuse")
        source_specs[source_id] = spec
        event_sources[event_id] = source_id

    sources_view = [
        {"id": source_id, "kind": kind, "path": path, "contentHash": content_hash}
        for source_id, (kind, path, content_hash) in source_specs.items()
    ]
    tracks = _unique_by_id(manifest.get("tracks"), "track")
    encoded_bars_rows = {
        cast(str, row["eventId"]): row
        for row in cast(
            list[JsonObject], (encoded_bars_evidence or {}).get("events", [])
        )
    }
    events_view: list[JsonObject] = []
    markers: list[JsonObject] = []
    for event in events:
        event_id = cast(str, event["eventId"])
        kind = cast(str, event["kind"])
        record_start, record_end = _range(
            event["recordRange"], f"event {event_id} recordRange"
        )
        record_range = {
            "startFrame": record_start,
            "durationFrames": record_end - record_start,
        }
        if kind == "script_marker":
            marker = cast(JsonObject, event["marker"])
            marker_prefix = (
                f"music-warning:{manifest['document']['documentId']}:"
                f"{marker['supportingItemId']}:"
            )
            music_warning = any(
                event_id == _stable_compiler_id(marker_prefix + code)
                for code in _MUSIC_WARNING_CODES
            )
            markers.append(
                {
                    "id": event_id,
                    "frame": record_start,
                    "color": "YELLOW",
                    "name": "Music warning" if music_warning else marker["text"],
                    "note": marker["text"],
                    "provenance": event,
                }
            )
            continue
        source_range: JsonObject | None
        if kind in {"primary_visual", "overlay_visual"}:
            selected_start, selected_end = _range(
                event.get("sourceRange"), f"event {event_id} sourceRange"
            )
            if (
                isinstance(event.get("pictureTreatment"), dict)
                and event["pictureTreatment"].get("kind") == "still_frame"
            ):
                source_range = {
                    "startFrame": selected_start,
                    "durationFrames": record_end - record_start,
                }
            else:
                source_range = {
                    "startFrame": selected_start,
                    "durationFrames": selected_end - selected_start,
                }
        elif kind in {"placeholder", "quote_box", "still_credit", "narration"}:
            source_range = {
                "startFrame": 0,
                "durationFrames": record_end - record_start,
            }
        elif kind == "source_audio":
            binding_hash = cast(str, event["preparationBindingHash"])
            prep = binding_by_hash.get(binding_hash)
            if prep is None or prep.record.get("audio") is None:
                raise _error(
                    f"source audio event {event_id} has no validated #174 sidecar"
                )
            source_range = _source_audio_range(event, prep, timeline_rate)
        elif kind == "music":
            music_start, music_end = _range(
                event["sourceRange"], f"music {event_id} sourceRange"
            )
            source_range = {
                "startFrame": music_start,
                "durationFrames": music_end - music_start,
            }
        else:
            raise _error(f"unsupported delivery event kind {kind!r}")
        if source_range is not None:
            _safe_frame(
                source_range.get("startFrame"), f"event {event_id} native source start"
            )
            _safe_frame(
                source_range.get("durationFrames"),
                f"event {event_id} native source duration",
                positive=True,
            )
        track = tracks[cast(str, event["trackId"])]
        projected: JsonObject = {
            "id": event_id,
            "kind": kind,
            "sourceId": event_sources[event_id],
            "trackId": event["trackId"],
            "trackKind": track["kind"],
            "recordRange": record_range,
            "sourceRange": source_range,
            "v2Event": event,
            "gainDb": event["audio"]["gainDb"]
            if isinstance(event.get("audio"), dict)
            else event["music"]["gainDb"]
            if kind == "music"
            else None,
            "pictureTreatment": event.get("pictureTreatment"),
        }
        if "encodedBars" in event:
            row = encoded_bars_rows.get(event_id)
            if row is None or not isinstance(row.get("decision"), dict):
                raise _error(f"bar-removal event {event_id} has no frozen evidence")
            decision = cast(JsonObject, row["decision"])
            if decision.get("decision") == "apply":
                projected["barRemoval"] = {
                    "decision": "apply",
                    "zoom": decision["zoom"],
                    "pan": 0.0,
                    "tilt": 0.0,
                    "detectionHash": row["recordHash"],
                }
            else:
                projected["barRemoval"] = {
                    "decision": "skip",
                    "reason": decision["reason"],
                    "detectionHash": row["recordHash"],
                }
        if kind == "music":
            projected["musicTreatment"] = event["music"]
        events_view.append(projected)
    view = {
        "schemaVersion": VIEW_SCHEMA_VERSION,
        "timeline": manifest["timeline"],
        "tracks": manifest["tracks"],
        "sources": sources_view,
        "events": events_view,
        "markers": markers,
        "composition": manifest["composition"],
    }
    if validate:
        _validate_delivery_view(
            manifest,
            dependencies,
            view,
            prepared,
            artifacts,
            cache=cache,
            encoded_bars_evidence=encoded_bars_evidence,
        )
        source_map = _unique_by_id(sources_view, "delivery source")
        for event in events_view:
            _native_motion_for_event(
                event,
                manifest,
                source_map[event["sourceId"]],
                prepared=prepared,
                artifacts=artifacts,
            )
    return view


def _validate_delivery_view(
    manifest: JsonObject,
    dependencies: JsonObject,
    view: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    *,
    cache: _MediaCacheSession | None = None,
    encoded_bars_evidence: JsonObject | None = None,
) -> None:
    if set(view) != {
        "schemaVersion",
        "timeline",
        "tracks",
        "sources",
        "events",
        "markers",
        "composition",
    }:
        raise _error("delivery view has missing or unexpected top-level fields")
    if view.get("schemaVersion") != VIEW_SCHEMA_VERSION:
        raise _error("delivery view is not explicitly resolve-native-view/v2")
    sources = _unique_by_id(view.get("sources"), "delivery source")
    expected_source_ids = {
        event["eventId"]
        if event["kind"] in {"placeholder", "quote_box", "still_credit", "source_audio"}
        else cast(JsonObject, event["provenance"])["sourceId"]
        for event in cast(list[JsonObject], manifest["events"])
        if event["kind"] != "script_marker"
    }
    if set(sources) != expected_source_ids:
        raise _error("delivery view source set differs from its media events")
    motion_still_source_ids = {
        cast(str, cast(JsonObject, event["provenance"])["sourceId"])
        for event in cast(list[JsonObject], manifest["events"])
        if event["kind"] in {"primary_visual", "overlay_visual"}
        and isinstance(event.get("pictureTreatment"), dict)
        and "imageMotion" in event["pictureTreatment"]
    }
    quote_ids = {
        event["eventId"]
        for event in manifest["events"]
        if event["kind"] in {"quote_box", "still_credit"}
    }
    source_paths: dict[str, str] = {}
    for source_id, source in sources.items():
        if set(source) != {"id", "kind", "path", "contentHash"}:
            raise _error(f"delivery source {source_id} has unexpected fields")
        relative = _safe_relative(
            source.get("path"), f"delivery source {source_id} path"
        )
        if len(relative.parts) != 3 or relative.parts[0] != MEDIA_DIRECTORY:
            raise _error(
                f"delivery source {source_id} path is outside the package Media tree"
            )
        expected_area = "Narration" if source.get("kind") == "audio" else "Resolved"
        if source_id in quote_ids:
            named_as_expected = (
                relative.name
                == f"{native_image_motion.native_still_stem(source_id)}.png"
            )
        elif source_id in motion_still_source_ids:
            named_as_expected = source.get("kind") == "still" and (
                relative.name.startswith(
                    f"{native_image_motion.native_still_stem(source_id)}."
                )
                or relative.name.startswith(f"{source_id}-still.")
                or relative.name.startswith(f"{source_id}.")
            )
        else:
            named_as_expected = relative.name.startswith(f"{source_id}.")
        if relative.parts[1] != expected_area or not named_as_expected:
            raise _error(f"delivery source {source_id} has a mismatched package path")
        if source.get("kind") not in {"video", "audio", "still"}:
            raise _error(f"delivery source {source_id} has unsupported native kind")
        _require_hash(
            source.get("contentHash"), f"delivery source {source_id} contentHash"
        )
        source_paths[source_id] = relative.as_posix()

    artifact_map: dict[str, _InputArtifact] = {}
    manifest_sources = _unique_by_id(manifest.get("sources"), "manifest source")
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            item = cast(JsonObject, source["narrationAudio"])
            content_hash = _require_hash(
                item.get("audioHash"), f"narration {source_id} audioHash"
            )
            view_source_id = source_id
        elif "musicAudio" in source:
            content_hash = _require_hash(
                cast(JsonObject, source["musicAudio"])["source"]["contentHash"],
                f"music source {source_id} contentHash",
            )
            view_source_id = source_id
        else:
            content_hash = _require_hash(
                source.get("deliveredHash"), f"source {source_id} deliveredHash"
            )
            view_source_id = source_id
        package_source = sources.get(view_source_id)
        if package_source is None or package_source.get("contentHash") != content_hash:
            raise _error(
                f"delivery source {source_id} content hash differs from the manifest"
            )
        artifact_map[f"source:{source_id}"] = _InputArtifact(
            f"source:{source_id}",
            Path("."),
            package_source["path"],
            content_hash,
            package_source["kind"],
        )
        if "narrationAudio" not in source:
            artifact_map[f"original:{source_id}"] = _InputArtifact(
                f"original:{source_id}",
                Path("."),
                "",
                content_hash if "musicAudio" in source else source["originalHash"],
                "original",
            )

    binding_by_hash = {
        _compiler_hash(item.record["binding"]): item for item in prepared.values()
    }
    for event in cast(list[JsonObject], manifest["events"]):
        event_id = cast(str, event["eventId"])
        if event["kind"] == "still_credit":
            credit = _still_credit_artifact(event, manifest["timeline"])
            source = sources[event_id]
            if (
                source["contentHash"] != credit.content_hash
                or source["kind"] != "still"
            ):
                raise _error(
                    f"still credit {event_id} has different generated graphic bytes"
                )
            artifact_map[credit.key] = credit
            continue
        if event["kind"] == "quote_box":
            carrier = _quote_carrier(event_id, manifest["timeline"])
            source = sources[event_id]
            if (
                source["contentHash"] != carrier.content_hash
                or source["kind"] != "still"
            ):
                raise _error(
                    f"quote box {event_id} has a different transparent carrier"
                )
            artifact_map[carrier.key] = carrier
            continue
        if event["kind"] == "placeholder":
            treatment = cast(JsonObject, event["pictureTreatment"])
            if treatment["kind"] == "slate":
                timeline = cast(JsonObject, manifest["timeline"])
                content_hash = _hash_bytes(
                    _render_slate(
                        cast(str, treatment["text"]),
                        _safe_frame(
                            timeline.get("width"), "timeline width", positive=True
                        ),
                        _safe_frame(
                            timeline.get("height"), "timeline height", positive=True
                        ),
                    )
                )
            else:
                content_hash = _require_hash(
                    cast(JsonObject, treatment["reference"]).get("contentHash"),
                    f"placeholder {event_id} reference hash",
                )
            package_source = sources[event_id]
            if package_source.get("contentHash") != content_hash:
                raise _error(
                    f"placeholder {event_id} does not retain its reference bytes"
                )
            artifact_map[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                Path("."),
                package_source["path"],
                content_hash,
                "still",
            )
        elif event["kind"] == "source_audio":
            binding_hash = cast(str, event["preparationBindingHash"])
            prep = binding_by_hash.get(binding_hash)
            if prep is None or not isinstance(prep.record.get("audio"), dict):
                raise _error(
                    f"source audio event {event_id} has no validated preparation WAV"
                )
            content_hash = _require_hash(
                cast(JsonObject, prep.record["audio"]).get("contentHash"),
                f"source audio {event_id} content hash",
            )
            try:
                plan = endpoint_plan(
                    event,
                    prep.record["audio"],
                    _fraction(
                        manifest["timeline"]["frameRate"],
                        "timeline rate",
                        positive=True,
                    ),
                )
                if plan is not None:
                    original = artifacts.get(f"original-audio:{event_id}")
                    if original is None:
                        raise _error(
                            f"source audio {event_id} lacks its original #174 WAV"
                        )
                    actual_original = (
                        _file_hash(original.origin)
                        if cache is None
                        else cache.checked_hash(original.origin, content_hash)
                    )
                    if actual_original != content_hash:
                        raise _error(
                            f"source audio {event_id} lacks its original #174 WAV"
                        )
                    content_hash = _hash_bytes(
                        endpoint_wav(
                            (
                                original.origin.read_bytes()
                                if cache is None
                                else cache.audio_bytes(original.origin, content_hash)
                            ),
                            plan,
                            prep.record["audio"],
                        )
                    )
            except (OSError, ValueError) as error:
                if cache is not None and cache.used_cached_audio:
                    raise _CachedIntegrityFailure(
                        f"cached source audio {event_id} could not be projected"
                    ) from error
                raise _error(f"source audio {event_id}: {error}") from error
            package_source = sources[event_id]
            if package_source.get("contentHash") != content_hash:
                if cache is not None and cache.used_cached_audio:
                    raise _CachedIntegrityFailure(
                        f"cached source audio {event_id} does not match its frozen WAV"
                    )
                raise _error(f"source audio {event_id} does not retain its #174 WAV")
            artifact_map[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                Path("."),
                package_source["path"],
                content_hash,
                "audio",
            )

    expected = _delivery_view(
        manifest,
        dependencies,
        prepared,
        artifact_map,
        source_paths=source_paths,
        validate=False,
        encoded_bars_evidence=encoded_bars_evidence,
    )
    if view != expected:
        raise _error("delivery view differs from the exact v2 manifest projection")


def _otio_rate(value: Fraction) -> float:
    return value.numerator / value.denominator


def _otio_time(frames: int, rate: Fraction) -> Any:
    return otio.opentime.RationalTime(frames, _otio_rate(rate))


def _otio_range(start: int, duration: int, rate: Fraction) -> Any:
    return otio.opentime.TimeRange(_otio_time(start, rate), _otio_time(duration, rate))


def _otio_track_kind(kind: str) -> str:
    if kind == "video":
        return cast(str, otio.schema.Track.Kind.Video)
    if kind == "audio":
        return cast(str, otio.schema.Track.Kind.Audio)
    if kind == "subtitle":
        # OTIO accepts custom track-kind labels and round-trips them in its JSON
        # adapter; the accepted v2 contract has subtitle tracks but no subtitle
        # event kind yet.
        return "Subtitle"
    raise _error(f"unsupported OTIO track kind {kind!r}")


def _otio_track_order(tracks: list[JsonObject]) -> list[JsonObject]:
    kind_order = {"video": 0, "audio": 1, "subtitle": 2}
    for track in tracks:
        if track.get("kind") not in kind_order:
            _otio_track_kind(cast(str, track.get("kind")))
    return sorted(
        tracks,
        key=lambda item: (
            kind_order[cast(str, item["kind"])],
            _safe_frame(
                item.get("index"), f"track {item.get('id')} index", positive=True
            ),
        ),
    )


def _otio_transport_tracks(view: JsonObject) -> list[JsonObject]:
    """Pad sparse native lanes so OTIO imports quote boxes on V4 and music on A5."""
    tracks = cast(list[JsonObject], view["tracks"])
    kinds = {event["kind"] for event in view["events"]}
    ids = {track["id"] for track in tracks}
    padding = []
    for event_kind, kind, prefix, target in (
        ("music", "audio", "A", 5),
        ("quote_box", "video", "V", 4),
        (
            "still_credit",
            "video",
            "V",
            max(
                (track["index"] for track in tracks if track["kind"] == "video"),
                default=0,
            ),
        ),
    ):
        if event_kind not in kinds:
            continue
        occupied = {
            track["index"] for track in [*tracks, *padding] if track["kind"] == kind
        }
        for index in range(1, target):
            if index in occupied:
                continue
            track_id = f"vera-native-{prefix.lower()}{index}-pad"
            if track_id in ids:
                raise _error(
                    f"native {prefix}{target} padding collides with a signed track ID"
                )
            padding.append(
                {
                    "id": track_id,
                    "kind": kind,
                    "index": index,
                    "name": f"VERA Empty {prefix}{index}",
                }
            )
    return _otio_track_order([*tracks, *padding])


def _native_motion_for_event(
    event: JsonObject,
    manifest: JsonObject,
    source: JsonObject,
    *,
    prepared: Mapping[str, _Preparation] | None = None,
    artifacts: Mapping[str, _InputArtifact] | None = None,
) -> tuple[list[JsonObject], str | None]:
    """Close the frozen event/source/profile chain before projecting native effects.

    Legacy image events have no new motion field and retain byte-identical OTIO.
    Qualification is trusted code-side evidence, never inferred from the
    authored manifest, an arbitrary user profile or an imported effect.
    """
    treatment = event.get("pictureTreatment")
    if not isinstance(treatment, dict) or "imageMotion" not in treatment:
        return [], None
    event_id = cast(str, event["id"])
    original = cast(JsonObject, event["v2Event"])
    if treatment.get("kind") != "still_frame" or original.get("kind") not in {
        "primary_visual",
        "overlay_visual",
    }:
        raise _error(f"image motion {event_id} requires a source-backed image still")
    motion = cast(JsonObject, treatment["imageMotion"])
    source_id = source["id"]
    manifest_source = _unique_by_id(manifest["sources"], "source").get(source_id)
    if not isinstance(manifest_source, dict):
        raise _error(f"image motion {event_id} has no frozen source identity")
    provenance = cast(JsonObject, original["provenance"])
    if (
        original.get("pictureTreatment") != treatment
        or source["kind"] != "still"
        or manifest_source.get("deliveredHash") != source["contentHash"]
        or provenance.get("deliveredSourceHash") != source["contentHash"]
        or provenance.get("originalSourceHash") != manifest_source.get("originalHash")
    ):
        raise _error(f"image motion {event_id} has stale source bytes or provenance")
    requirement_key = manifest_source.get("preparationRequirementKey")
    prep = next(
        (
            binding
            for binding in manifest["preparationBindings"]
            if binding["requirementKey"] == requirement_key
        ),
        None,
    )
    if not isinstance(prep, dict) or original.get(
        "preparationBindingHash"
    ) != _compiler_hash(prep):
        raise _error(f"image motion {event_id} has stale preparation binding")
    profile = cast(JsonObject, prep["profile"])
    v2_source = cast(JsonObject, original["sourceRange"])
    v2_record = cast(JsonObject, original["recordRange"])
    source_range = cast(JsonObject, event["sourceRange"])
    record = cast(JsonObject, event["recordRange"])
    if (
        source_range["startFrame"] != v2_source["startFrame"]
        or v2_source["endFrame"] != v2_source["startFrame"] + 1
        or record["startFrame"] != v2_record["startFrame"]
        or record["durationFrames"] != v2_record["endFrame"] - v2_record["startFrame"]
        or source_range["durationFrames"] != record["durationFrames"]
    ):
        raise _error(
            f"image motion {event_id} has stale or invalid duration/source range"
        )
    timeline = cast(JsonObject, manifest["timeline"])
    binding = native_image_motion.MotionBinding(
        source_hash=cast(str, source["contentHash"]),
        original_hash=cast(str, manifest_source["originalHash"]),
        source_probe_hash=cast(str, manifest_source["originalProbeHash"]),
        delivered_probe_hash=cast(str, manifest_source["deliveredProbeHash"]),
        compiler_profile_hash=cast(
            str, cast(JsonObject, manifest["compiler"])["profileHash"]
        ),
        preparation_profile_hash=cast(str, profile["profileHash"]),
        tool_hash=cast(str, profile["toolHash"]),
        settings_hash=cast(
            str, cast(JsonObject, manifest["authoringDefaults"])["settingsHash"]
        ),
        preparation_binding_hash=cast(str, original["preparationBindingHash"]),
        record_start=cast(int, record["startFrame"]),
        record_end=cast(int, record["startFrame"] + record["durationFrames"]),
        source_start=cast(int, v2_source["startFrame"]),
        source_end=cast(int, v2_source["endFrame"]),
        timeline_width=cast(int, timeline["width"]),
        timeline_height=cast(int, timeline["height"]),
    )
    framing = cast(str, treatment["framingPolicy"])
    try:
        source_artifact = (
            artifacts.get(f"source:{source_id}") if artifacts is not None else None
        )
        preparation = (
            prepared.get(cast(str, requirement_key)) if prepared is not None else None
        )
        if source_artifact is None or preparation is None:
            proof = native_image_motion.production_qualification(
                motion, binding, framing
            )
        else:
            proof = native_image_motion.production_qualification(
                motion,
                binding,
                framing,
                verified_asset=source_artifact.origin,
                delivered_probe=cast(JsonObject, preparation.record["deliveredProbe"]),
                frame_rate=(
                    cast(int, timeline["frameRate"]["numerator"]),
                    cast(int, timeline["frameRate"]["denominator"]),
                ),
            )
        qualified = native_image_motion.admit_motion(
            motion,
            binding,
            proof,
            framing=framing,
            version=proof.version if proof is not None else "21.1.1.10",
        )
        return native_image_motion.native_effect_records(
            motion, qualified
        ), native_image_motion.qualification_hash(qualified)
    except (native_image_motion.MotionRefusal, TypeError, ValueError) as error:
        raise _error(f"image motion {event_id} refused: {error}") from error


def _plain_otio(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: _plain_otio(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [_plain_otio(item) for item in value]
    return value


def _time_frames(value: Any, rate: Fraction, label: str) -> int:
    try:
        frames = value.rescaled_to(_otio_rate(rate)).to_frames()
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        raise _error(f"OTIO {label} is not valid frame time: {error}") from error
    rounded = round(frames)
    if not math.isfinite(frames) or abs(frames - rounded) > 1e-6:
        raise _error(f"OTIO {label} does not land on an exact frame boundary")
    return int(rounded)


def _event_source_rate(event: JsonObject, timeline_rate: Fraction) -> Fraction:
    if event.get("kind") in {"primary_visual", "overlay_visual"}:
        treatment = event.get("pictureTreatment")
        if isinstance(treatment, dict) and treatment.get("kind") == "still_frame":
            return timeline_rate
        original = cast(JsonObject, event.get("v2Event", event))
        mapping = cast(JsonObject, original.get("sourceTimeMapping"))
        return _fraction(
            mapping.get("deliveredRate"),
            f"event {original.get('eventId', event.get('id'))} delivered rate",
            positive=True,
        )
    return timeline_rate


def _delivered_probe_video(preparation: _Preparation) -> JsonObject:
    """Return the selected delivered video stream from the frozen prep receipt."""
    inputs = cast(JsonObject, preparation.record["inputs"])
    stream_index = inputs["videoStreamIndex"]
    streams = cast(JsonObject, preparation.record["deliveredProbe"])["streams"]
    if not isinstance(streams, list):
        raise _error("preparation delivered probe has no stream list")
    for stream in streams:
        if isinstance(stream, dict) and stream.get("index") == stream_index:
            return stream
    raise _error("preparation delivered probe lacks its selected video stream")


def _encoded_bars_color_range(
    intent: JsonObject, preparation: _Preparation
) -> str | None:
    if intent.get("mode") == "detect_and_fill":
        value = _delivered_probe_video(preparation).get("color_range")
        if value in ("tv", "pc"):
            return cast(str, value)
    return None


def _make_encoded_bars_evidence(
    manifest: JsonObject,
    dependencies: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    *,
    timing: _PackageSubtimings | None = None,
) -> JsonObject | None:
    """Analyze eligible clips once, before the view is frozen and Resolve runs."""
    defaults = cast(JsonObject, dependencies["authoringDefaults"])
    if defaults.get("hideEncodedBars") is not True:
        return None

    timeline = cast(JsonObject, manifest["timeline"])
    timeline_size = (
        _safe_frame(timeline.get("width"), "timeline width", positive=True),
        _safe_frame(timeline.get("height"), "timeline height", positive=True),
    )
    timeline_rate = _fraction(
        timeline.get("frameRate"), "timeline frame rate", positive=True
    )
    source_records = _unique_by_id(manifest.get("sources"), "source")
    manifest_events = cast(list[JsonObject], manifest["events"])
    has_native_otio_route = any(
        event.get("kind") == "music"
        or (
            isinstance(event.get("pictureTreatment"), dict)
            and "imageMotion" in event["pictureTreatment"]
        )
        for event in manifest_events
    )
    eligible_events = [
        event
        for event in manifest_events
        if isinstance(event.get("encodedBars"), dict)
        and event["encodedBars"].get("mode") == "detect_and_fill"
    ]

    analyzer_tool = None
    analyzer_tool_hash: str | None = None
    analyzer_tool_available = False
    if eligible_events and not has_native_otio_route:
        try:
            from vera_timeline_agent.media_preparation import (
                MediaPreparationError,
                MediaTools,
            )

            analyzer_tool = MediaTools()
            analyzer_tool_hash = identity_hash(analyzer_tool.fingerprint())
            analyzer_tool_available = True
        except MediaPreparationError as error:
            if error.code not in {"tool_unavailable", "unsupported_tools"}:
                raise _error("bar-removal tool fingerprint did not complete") from error

    rows: list[JsonObject] = []
    for event in manifest_events:
        intent = event.get("encodedBars")
        if not isinstance(intent, dict):
            continue
        event_id = cast(str, event["eventId"])
        provenance = cast(JsonObject, event["provenance"])
        source_id = cast(str, provenance["sourceId"])
        source = source_records[source_id]
        source_range = cast(JsonObject, event["sourceRange"])
        source_start, source_end = _range(source_range, f"event {event_id} sourceRange")
        source_range_record = {
            "startFrame": source_start,
            "durationFrames": source_end - source_start,
        }
        rate = _event_source_rate(event, timeline_rate)
        requirement_key = cast(str, source["preparationRequirementKey"])
        preparation = prepared.get(requirement_key)
        if preparation is None:
            raise _error(f"bar-removal event {event_id} has no preparation receipt")
        binding = cast(JsonObject, preparation.record["binding"])
        profile = cast(JsonObject, binding["profile"])
        verification = cast(JsonObject, binding["verification"])
        tool_hash = cast(str, profile["toolHash"])
        delivered_probe_hash = cast(str, verification["probeHash"])
        source_artifact = artifacts.get(f"source:{source_id}")
        if source_artifact is None:
            raise _error(
                f"bar-removal event {event_id} has no delivered media artifact"
            )
        delivered_hash = cast(str, source["deliveredHash"])
        if source_artifact.content_hash != delivered_hash:
            raise _error(f"bar-removal event {event_id} does not use delivered bytes")
        color_range = _encoded_bars_color_range(intent, preparation)

        analysis: JsonObject | None = None
        decision: JsonObject
        analysis_tool_hash: str | None = None
        if intent.get("mode") == "keep":
            decision = {"decision": "skip", "reason": intent["reason"]}
        elif has_native_otio_route:
            decision = {
                "decision": "skip",
                "reason": "native_otio_route_unproven",
            }
        elif not analyzer_tool_available or analyzer_tool is None:
            decision = {"decision": "skip", "reason": "analysis_failed"}
        elif analyzer_tool_hash != tool_hash:
            analysis_tool_hash = analyzer_tool_hash
            decision = {"decision": "skip", "reason": "tool_identity_mismatch"}
        else:
            analysis_tool_hash = analyzer_tool_hash
            used_range = (
                float(Fraction(source_start, 1) / rate),
                float(Fraction(source_end, 1) / rate),
            )
            try:
                # Recheck the exact delivered derivative immediately before
                # decoding it; a stale preparation or mutable source must fail closed.
                if _file_hash(source_artifact.origin) != delivered_hash:
                    raise _SuppliedHashMismatch(
                        f"delivered source {source_id} changed before bar analysis"
                    )
                with _measure(timing, "bar detection"):
                    detection = cropdetect.analyze_media(
                        source_artifact.origin,
                        used_range,
                        timeline_size=timeline_size,
                        ffmpeg=analyzer_tool.ffmpeg,
                        ffprobe=analyzer_tool.ffprobe,
                    )
                analysis = cast(
                    JsonObject, json.loads(_canonical_json(asdict(detection)))
                )
                if detection.color_range != color_range or detection.frame_rate != (
                    rate.numerator,
                    rate.denominator,
                ):
                    analysis = None
                    decision = {
                        "decision": "skip",
                        "reason": "probe_mismatch",
                    }
                elif detection.accepted and detection.zoom is not None:
                    decision = {"decision": "apply", "zoom": detection.zoom}
                else:
                    decision = {
                        "decision": "skip",
                        "reason": detection.refusal_reason or "insufficient_evidence",
                    }
            except cropdetect.CropAnalysisError as error:
                raise _error(f"bar analysis did not complete for {event_id}") from error

        row: JsonObject = {
            "eventId": event_id,
            "sourceId": source_id,
            "intent": intent,
            "deliveredHash": delivered_hash,
            "deliveredProbeHash": delivered_probe_hash,
            "sourceRange": source_range_record,
            "sourceRate": {
                "numerator": rate.numerator,
                "denominator": rate.denominator,
            },
            "toolHash": tool_hash,
            "analysisToolHash": analysis_tool_hash,
            "colorRange": color_range,
            "timelineSize": list(timeline_size),
            "analysis": analysis,
            "decision": decision,
        }
        row["recordHash"] = _hash_bytes(_canonical_json(row))
        rows.append(row)
    return {
        "schemaVersion": ENCODED_BARS_SCHEMA_VERSION,
        "buildId": manifest["buildId"],
        "manifestId": manifest["id"],
        "detectorVersion": cropdetect.DETECTOR_VERSION,
        "thresholdsHash": cropdetect.thresholds_hash(),
        "events": rows,
    }


def _validate_encoded_bars_evidence(
    manifest: JsonObject,
    dependencies: JsonObject,
    prepared: Mapping[str, _Preparation],
    evidence: object,
) -> JsonObject | None:
    """Check the frozen detector binding and pure geometry without decoding again."""
    defaults = cast(JsonObject, dependencies.get("authoringDefaults", {}))
    enabled = defaults.get("hideEncodedBars") is True
    if not enabled:
        if evidence is not None:
            raise _error("bar-removal evidence exists while the frozen setting is off")
        return None
    if not isinstance(evidence, dict) or set(evidence) != {
        "schemaVersion",
        "buildId",
        "manifestId",
        "detectorVersion",
        "thresholdsHash",
        "events",
    }:
        raise _error("bar-removal evidence is missing or malformed")
    if (
        evidence.get("schemaVersion") != ENCODED_BARS_SCHEMA_VERSION
        or evidence.get("buildId") != manifest.get("buildId")
        or evidence.get("manifestId") != manifest.get("id")
        or evidence.get("detectorVersion") != cropdetect.DETECTOR_VERSION
        or evidence.get("thresholdsHash") != cropdetect.thresholds_hash()
        or not isinstance(evidence.get("events"), list)
    ):
        raise _error("bar-removal evidence has a stale detector or build identity")

    expected_events = {
        cast(str, event["eventId"]): event
        for event in cast(list[JsonObject], manifest["events"])
        if "encodedBars" in event
    }
    rows = cast(list[JsonObject], evidence["events"])
    rows_by_id = _unique_by_id(rows, "encoded-bars evidence", "eventId")
    if set(rows_by_id) != set(expected_events):
        raise _error("bar-removal evidence event set differs from compiler intent")
    sources = _unique_by_id(manifest.get("sources"), "source")
    timeline = cast(JsonObject, manifest["timeline"])
    timeline_size = (
        _safe_frame(timeline["width"], "timeline width", positive=True),
        _safe_frame(timeline["height"], "timeline height", positive=True),
    )
    timeline_rate = _fraction(
        timeline.get("frameRate"), "timeline frame rate", positive=True
    )
    for event_id, event in expected_events.items():
        row = rows_by_id[event_id]
        if set(row) != {
            "eventId",
            "sourceId",
            "intent",
            "deliveredHash",
            "deliveredProbeHash",
            "sourceRange",
            "sourceRate",
            "toolHash",
            "analysisToolHash",
            "colorRange",
            "timelineSize",
            "analysis",
            "decision",
            "recordHash",
        }:
            raise _error(f"bar-removal evidence {event_id} has unexpected fields")
        provenance = cast(JsonObject, event["provenance"])
        source_id = cast(str, provenance["sourceId"])
        source = sources[source_id]
        requirement_key = cast(str, source["preparationRequirementKey"])
        binding = next(
            (
                item
                for item in prepared.values()
                if item.requirement_key == requirement_key
            ),
            None,
        )
        if binding is None:
            raise _error(f"bar-removal evidence {event_id} has no preparation")
        prep_binding = cast(JsonObject, binding.record["binding"])
        profile = cast(JsonObject, prep_binding["profile"])
        verification = cast(JsonObject, prep_binding["verification"])
        source_start, source_end = _range(
            event.get("sourceRange"), f"event {event_id} sourceRange"
        )
        rate = _event_source_rate(event, timeline_rate)
        expected_range = {
            "startFrame": source_start,
            "durationFrames": source_end - source_start,
        }
        expected_rate = {"numerator": rate.numerator, "denominator": rate.denominator}
        color_range = _encoded_bars_color_range(event["encodedBars"], binding)
        if (
            row.get("sourceId") != source_id
            or row.get("intent") != event.get("encodedBars")
            or row.get("deliveredHash") != source.get("deliveredHash")
            or row.get("deliveredProbeHash") != verification.get("probeHash")
            or row.get("sourceRange") != expected_range
            or row.get("sourceRate") != expected_rate
            or row.get("toolHash") != profile.get("toolHash")
            or row.get("timelineSize") != list(timeline_size)
            or row.get("colorRange") != color_range
        ):
            raise _error(
                f"bar-removal evidence {event_id} is not bound to delivered media"
            )
        record_without_hash = {
            key: value for key, value in row.items() if key != "recordHash"
        }
        expected_hash = _hash_bytes(_canonical_json(record_without_hash))
        if row.get("recordHash") != expected_hash:
            raise _error(f"bar-removal evidence {event_id} hash differs")
        decision = row.get("decision")
        analysis = row.get("analysis")
        if not isinstance(decision, dict):
            raise _error(f"bar-removal evidence {event_id} has no decision")
        if event["encodedBars"].get("mode") == "keep":
            if (
                decision
                != {
                    "decision": "skip",
                    "reason": event["encodedBars"]["reason"],
                }
                or analysis is not None
            ):
                raise _error(
                    f"bar-removal evidence {event_id} ignores authored framing"
                )
            continue
        if analysis is None:
            if (
                set(decision) != {"decision", "reason"}
                or decision.get("decision") != "skip"
                or decision.get("reason")
                not in {
                    "native_otio_route_unproven",
                    "analysis_failed",
                    "tool_identity_mismatch",
                    "probe_mismatch",
                }
                or (
                    decision.get("reason") != "tool_identity_mismatch"
                    and row.get("analysisToolHash")
                    not in {None, profile.get("toolHash")}
                )
            ):
                raise _error(
                    f"bar-removal evidence {event_id} has an invalid analysis skip"
                )
            continue
        if not isinstance(analysis, dict) or row.get("analysisToolHash") != profile.get(
            "toolHash"
        ):
            raise _error(
                f"bar-removal analysis {event_id} has an unbound tool identity"
            )
        _validate_encoded_bars_analysis(
            event_id,
            analysis,
            decision,
            binding,
            rate,
            (source_start, source_end),
            timeline_size,
            color_range,
        )
    return evidence


def _validate_encoded_bars_analysis(
    event_id: str,
    analysis: JsonObject,
    decision: JsonObject,
    preparation: _Preparation,
    rate: Fraction,
    source_range: tuple[int, int],
    timeline_size: tuple[int, int],
    color_range: str | None,
) -> None:
    expected_keys = {
        "source_size",
        "used_range",
        "samples",
        "active_rect",
        "refusal_reason",
        "zoom",
        "color_range",
        "frame_rate",
        "sample_stride",
        "source_frame_count",
    }
    if set(analysis) != expected_keys:
        raise _error(f"bar-removal analysis {event_id} has unexpected fields")
    video = _delivered_probe_video(preparation)
    source_size = (video.get("width"), video.get("height"))
    start, end = source_range
    expected_used_range = [
        float(Fraction(start, 1) / rate),
        float(Fraction(end, 1) / rate),
    ]
    frame_rate_value = analysis.get("frame_rate")
    expected_rate = [rate.numerator, rate.denominator]
    if (
        analysis.get("source_size") != list(source_size)
        or analysis.get("used_range") != expected_used_range
        or analysis.get("color_range") != color_range
        or frame_rate_value != expected_rate
        or not isinstance(analysis.get("samples"), list)
    ):
        raise _error(f"bar-removal analysis {event_id} differs from prepared media")
    raw_samples = cast(list[JsonObject], analysis["samples"])
    samples: list[cropdetect.CropFrameSample] = []
    for index, raw in enumerate(raw_samples):
        if set(raw) != {
            "frame_index",
            "pts_seconds",
            "active_rect",
            "cropdetect_rect",
            "active_mean_luma",
            "informative",
            "bar_max_luma",
            "bar_stddev_luma",
        }:
            raise _error(f"bar-removal sample {event_id} has unexpected fields")
        rect_value = raw.get("active_rect")
        if not isinstance(rect_value, dict) or set(rect_value) != {
            "x",
            "y",
            "width",
            "height",
        }:
            raise _error(f"bar-removal sample {event_id} has invalid crop geometry")
        rect = cropdetect.CropRect(**rect_value)
        cropdetect_rect_value = raw.get("cropdetect_rect")
        cropdetect_rect = None
        if cropdetect_rect_value is not None:
            if not isinstance(cropdetect_rect_value, dict) or set(
                cropdetect_rect_value
            ) != {"x", "y", "width", "height"}:
                raise _error(
                    f"bar-removal sample {event_id} has invalid raw crop geometry"
                )
            cropdetect_rect = cropdetect.CropRect(**cropdetect_rect_value)
        sample = cropdetect.CropFrameSample(
            frame_index=cast(int, raw["frame_index"]),
            pts_seconds=cast(float, raw["pts_seconds"]),
            active_rect=rect,
            active_mean_luma=cast(float, raw["active_mean_luma"]),
            informative=cast(bool, raw["informative"]),
            bar_max_luma=cast(int | None, raw["bar_max_luma"]),
            bar_stddev_luma=cast(float | None, raw["bar_stddev_luma"]),
            cropdetect_rect=cropdetect_rect,
        )
        if sample.frame_index != index:
            raise _error(f"bar-removal sample {event_id} frame sequence differs")
        samples.append(sample)
    active_value = analysis.get("active_rect")
    refusal = analysis.get("refusal_reason")
    zoom = analysis.get("zoom")
    if active_value is not None:
        if not isinstance(active_value, dict) or set(active_value) != {
            "x",
            "y",
            "width",
            "height",
        }:
            raise _error(f"bar-removal analysis {event_id} has invalid active bounds")
        assessment = cropdetect.evaluate_crop_samples(
            cast(tuple[int, int], source_size),
            timeline_size,
            cast(str, analysis["color_range"]),
            samples,
        )
        stride = max(1, round(float(rate) / cropdetect.SAMPLE_RATE_FPS))
        if (
            analysis.get("source_frame_count") != end - start
            or analysis.get("sample_stride") != stride
            or len(samples) != (end - start + stride - 1) // stride
            or any(
                not math.isfinite(sample.pts_seconds)
                or abs(sample.pts_seconds - float((start + index * stride) / rate))
                > float(1 / rate) / 2
                for index, sample in enumerate(samples)
            )
            or assessment.active_rect is None
            or asdict(assessment.active_rect) != active_value
            or assessment.zoom != zoom
            or refusal is not None
            or decision != {"decision": "apply", "zoom": zoom}
        ):
            raise _error(f"bar-removal analysis {event_id} does not justify its zoom")
    elif (
        refusal is None
        or decision != {"decision": "skip", "reason": refusal}
        or (zoom is not None and not isinstance(zoom, (int, float)))
    ):
        raise _error(f"bar-removal analysis {event_id} has inconsistent refusal data")


def _build_otio(
    view: JsonObject,
    manifest_id: str,
    build_id: str,
    manifest: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
) -> Any:
    timeline_data = cast(JsonObject, view["timeline"])
    timeline_rate = _fraction(
        timeline_data["frameRate"], "delivery view frame rate", positive=True
    )
    start = _safe_frame(timeline_data["startFrame"], "delivery view start frame")
    end = start + _safe_frame(
        timeline_data["durationFrames"], "delivery view duration", positive=True
    )
    timeline = otio.schema.Timeline(
        name=f"VERA build {build_id}",
        global_start_time=_otio_time(start, timeline_rate),
    )
    timeline.metadata["vera"] = {
        "schema_version": VIEW_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "build_id": build_id,
        "timeline": timeline_data,
        "composition": view["composition"],
    }
    sources = _unique_by_id(view["sources"], "delivery source")
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    for event in cast(list[JsonObject], view["events"]):
        events_by_track[cast(str, event["trackId"])].append(event)

    for track_data in _otio_transport_tracks(view):
        track_id = cast(str, track_data["id"])
        track = otio.schema.Track(
            name=cast(str, track_data["name"]),
            kind=_otio_track_kind(cast(str, track_data["kind"])),
            metadata={
                "vera": {
                    "track_id": track_id,
                    "track_kind": track_data["kind"],
                    "track_index": track_data["index"],
                }
            },
        )
        cursor = start
        ordered = sorted(
            events_by_track[track_id],
            key=lambda item: item["recordRange"]["startFrame"],
        )
        for event in ordered:
            record = cast(JsonObject, event["recordRange"])
            record_start = _safe_frame(
                record.get("startFrame"), f"event {event['id']} record start"
            )
            duration = _safe_frame(
                record.get("durationFrames"),
                f"event {event['id']} record duration",
                positive=True,
            )
            if record_start < cursor or record_start + duration > end:
                raise _error(
                    f"delivery event {event['id']} cannot be placed on its OTIO track"
                )
            if record_start > cursor:
                track.append(
                    otio.schema.Gap(
                        source_range=_otio_range(
                            0, record_start - cursor, timeline_rate
                        )
                    )
                )
            source = sources[cast(str, event["sourceId"])]
            source_range = cast(JsonObject, event["sourceRange"])
            source_start = _safe_frame(
                source_range.get("startFrame"), f"event {event['id']} source start"
            )
            source_duration = _safe_frame(
                source_range.get("durationFrames"),
                f"event {event['id']} source duration",
                positive=True,
            )
            source_rate = _event_source_rate(event, timeline_rate)
            if (
                Fraction(source_duration, 1) / source_rate
                != Fraction(duration, 1) / timeline_rate
            ):
                raise _error(
                    f"event {event['id']} source duration differs from record duration"
                )
            source_path = _safe_relative(
                source.get("path"), f"event {event['id']} media path"
            )
            reference = otio.schema.ExternalReference(
                target_url=source_path.as_posix(),
                available_range=_otio_range(
                    0, source_start + source_duration, source_rate
                ),
                metadata={
                    "vera": {
                        "source_id": source["id"],
                        "source_kind": source["kind"],
                        "content_hash": source["contentHash"],
                    }
                },
            )
            clip = otio.schema.Clip(
                name=f"{source['kind']}: {source_path.name}",
                media_reference=reference,
                source_range=_otio_range(source_start, source_duration, source_rate),
                metadata={
                    "vera": {
                        "event_id": event["id"],
                        "event_kind": event["kind"],
                        "source_id": event["sourceId"],
                        "source_kind": source["kind"],
                        "track_id": event["trackId"],
                        "track_kind": event["trackKind"],
                        "record_range": record,
                        "source_range": source_range,
                        "gain_db": event["gainDb"],
                        "picture_treatment": event["pictureTreatment"],
                        "v2_event": event["v2Event"],
                        **(
                            {"music_treatment": event["musicTreatment"]}
                            if event["kind"] == "music"
                            else {}
                        ),
                    }
                },
            )
            motion_effects, qualification = _native_motion_for_event(
                event, manifest, source, prepared=prepared, artifacts=artifacts
            )
            if qualification is not None:
                clip.metadata["vera"]["motion_qualification"] = qualification
            for native_effect in motion_effects:
                clip.effects.append(
                    otio.schema.Effect(
                        effect_name="Resolve Effect",
                        metadata={"Resolve_OTIO": native_effect},
                    )
                )
            track.append(clip)
            cursor = record_start + duration
        if cursor < end:
            track.append(
                otio.schema.Gap(
                    source_range=_otio_range(0, end - cursor, timeline_rate)
                )
            )
        timeline.tracks.append(track)

    for marker_data in cast(list[JsonObject], view["markers"]):
        frame = _safe_frame(
            marker_data.get("frame"), f"marker {marker_data['id']} frame"
        )
        timeline.tracks.markers.append(
            otio.schema.Marker(
                name=cast(str, marker_data["name"]),
                marked_range=_otio_range(frame - start, 0, timeline_rate),
                color=cast(
                    Any,
                    getattr(
                        otio.schema.MarkerColor,
                        str(marker_data["color"]).upper(),
                        otio.schema.MarkerColor.RED,
                    ),
                ),
                metadata={"vera": marker_data},
            )
        )
    return timeline


def _verify_otio(
    package_root: Path,
    manifest: JsonObject,
    view: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
) -> None:
    try:
        timeline = otio.adapters.read_from_file(str(package_root / OTIO_FILENAME))
    except (OSError, RuntimeError, ValueError) as error:
        raise _error(f"OTIO could not be parsed: {error}") from error
    if not isinstance(timeline, otio.schema.Timeline):
        raise _error("OTIO root is not a Timeline")
    timeline_data = cast(JsonObject, view["timeline"])
    rate = _fraction(
        timeline_data["frameRate"], "delivery view frame rate", positive=True
    )
    start = _safe_frame(timeline_data["startFrame"], "delivery view start frame")
    end = start + _safe_frame(
        timeline_data["durationFrames"], "delivery view duration", positive=True
    )
    metadata = _plain_otio(timeline.metadata.get("vera", {}))
    if (
        timeline.global_start_time is None
        or _time_frames(timeline.global_start_time, rate, "global start") != start
        or metadata.get("schema_version") != VIEW_SCHEMA_VERSION
        or metadata.get("manifest_id") != manifest.get("id")
        or metadata.get("build_id") != manifest.get("buildId")
        or metadata.get("timeline") != timeline_data
        or metadata.get("composition") != view.get("composition")
    ):
        raise _error(
            "OTIO timeline identity, start, or composition differs from v2 view"
        )
    expected_tracks = _otio_transport_tracks(view)
    if len(timeline.tracks) != len(expected_tracks):
        raise _error("OTIO track count differs from delivery view")
    expected_events = _unique_by_id(view["events"], "delivery event")
    actual_ids: set[str] = set()
    for actual_track, expected_track in zip(
        timeline.tracks, expected_tracks, strict=True
    ):
        track_metadata = _plain_otio(actual_track.metadata.get("vera", {}))
        if (
            actual_track.name != expected_track["name"]
            or actual_track.kind != _otio_track_kind(cast(str, expected_track["kind"]))
            or track_metadata.get("track_id") != expected_track["id"]
            or track_metadata.get("track_kind") != expected_track["kind"]
            or track_metadata.get("track_index") != expected_track["index"]
        ):
            raise _error(
                f"OTIO track differs from delivery view track {expected_track['id']}"
            )
        cursor = start
        for child in actual_track:
            duration = _time_frames(child.duration(), rate, "track child duration")
            if isinstance(child, otio.schema.Gap):
                cursor += duration
                continue
            if not isinstance(child, otio.schema.Clip):
                raise _error(
                    f"OTIO contains unsupported track child {type(child).__name__}"
                )
            vera = _plain_otio(child.metadata.get("vera", {}))
            event_id = vera.get("event_id")
            if (
                not isinstance(event_id, str)
                or event_id in actual_ids
                or event_id not in expected_events
            ):
                raise _error(
                    "OTIO event metadata is missing, duplicated, or unexpected"
                )
            expected = expected_events[event_id]
            record = cast(JsonObject, expected["recordRange"])
            source_range = cast(JsonObject, expected["sourceRange"])
            source = next(
                item
                for item in cast(list[JsonObject], view["sources"])
                if item["id"] == expected["sourceId"]
            )
            source_rate = _event_source_rate(expected, rate)
            reference = child.media_reference
            if (
                not isinstance(reference, otio.schema.ExternalReference)
                or child.source_range is None
            ):
                raise _error(
                    f"OTIO event {event_id} has no external media/source range"
                )
            ref_metadata = _plain_otio(reference.metadata.get("vera", {}))
            event_record_start = _safe_frame(
                record["startFrame"], f"event {event_id} record start"
            )
            event_record_duration = _safe_frame(
                record["durationFrames"],
                f"event {event_id} record duration",
                positive=True,
            )
            if cursor != event_record_start or duration != event_record_duration:
                raise _error(
                    f"OTIO event {event_id} record placement differs from delivery view"
                )
            actual_source_start = _time_frames(
                child.source_range.start_time,
                source_rate,
                f"event {event_id} source start",
            )
            actual_source_duration = _time_frames(
                child.source_range.duration,
                source_rate,
                f"event {event_id} source duration",
            )
            actual_source = {
                "startFrame": actual_source_start,
                "durationFrames": actual_source_duration,
            }
            if (
                actual_source != source_range
                or reference.target_url != source["path"]
                or ref_metadata
                != {
                    "source_id": source["id"],
                    "source_kind": source["kind"],
                    "content_hash": source["contentHash"],
                }
                or vera.get("event_kind") != expected["kind"]
                or vera.get("source_id") != expected["sourceId"]
                or vera.get("source_kind") != source["kind"]
                or vera.get("track_id") != expected["trackId"]
                or vera.get("track_kind") != expected["trackKind"]
                or vera.get("record_range") != record
                or vera.get("source_range") != source_range
                or vera.get("gain_db") != expected["gainDb"]
                or vera.get("picture_treatment") != expected["pictureTreatment"]
                or vera.get("v2_event") != expected["v2Event"]
                or vera.get("music_treatment") != expected.get("musicTreatment")
            ):
                raise _error(f"OTIO event {event_id} differs from delivery view")
            expected_effects, expected_proof = _native_motion_for_event(
                expected, manifest, source, prepared=prepared, artifacts=artifacts
            )
            if vera.get("motion_qualification") != expected_proof:
                raise _error(f"OTIO event {event_id} native qualification differs")
            if len(child.effects) != len(expected_effects):
                raise _error(f"OTIO event {event_id} native effect count differs")
            for actual_effect, native_effect in zip(
                child.effects, expected_effects, strict=True
            ):
                if (
                    type(actual_effect) is not otio.schema.Effect
                    or actual_effect.effect_name != "Resolve Effect"
                    or actual_effect.name != ""
                    or _plain_otio(actual_effect.metadata)
                    != {"Resolve_OTIO": native_effect}
                ):
                    raise _error(f"OTIO event {event_id} native effect differs")
            actual_ids.add(event_id)
            cursor += duration
        if cursor != end:
            raise _error(f"OTIO duration differs on track {expected_track['id']}")
    if actual_ids != set(expected_events):
        raise _error("OTIO event set differs from delivery view")

    expected_markers = cast(list[JsonObject], view["markers"])
    if len(timeline.tracks.markers) != len(expected_markers):
        raise _error("OTIO marker count differs from delivery view")
    for actual, expected in zip(timeline.tracks.markers, expected_markers, strict=True):
        metadata = _plain_otio(actual.metadata.get("vera", {}))
        frame = (
            _time_frames(
                actual.marked_range.start_time, rate, f"marker {expected['id']} frame"
            )
            + start
        )
        if (
            actual.name != expected["name"]
            or frame != expected["frame"]
            or actual.marked_range.duration.to_frames() != 0
            or metadata != expected
        ):
            raise _error(
                f"OTIO marker differs from delivery view marker {expected['id']}"
            )
    if list(timeline.tracks.find_children(descended_from_type=otio.schema.Transition)):
        raise _error("OTIO contains unintended transition objects")


def _walk_package(root: Path) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    if root.is_symlink() or not root.is_dir():
        raise _error(f"package root is not a real directory: {root}")
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in tuple(dirnames):
            path = current_path / name
            if path.is_symlink() or not path.is_dir():
                raise _error(
                    f"package contains a symbolic link or non-directory: {path}"
                )
            directories.add(path.relative_to(root).as_posix())
        for name in filenames:
            path = current_path / name
            _require_regular(path, "package file")
            files.add(path.relative_to(root).as_posix())
    return files, directories


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for value in files:
        path = PurePosixPath(value).parent
        while path != PurePosixPath("."):
            result.add(path.as_posix())
            path = path.parent
    return result


def _receipt_preparations(prepared: Mapping[str, _Preparation]) -> JsonObject:
    result: JsonObject = {}
    for key, item in prepared.items():
        binding = cast(JsonObject, item.record["binding"])
        original = cast(JsonObject, binding["originalSource"])
        verification = cast(JsonObject, binding["verification"])
        profile = cast(JsonObject, binding["profile"])
        result[key] = {
            "path": item.relative_path,
            "receiptHash": item.content_hash,
            "bindingHash": _compiler_hash(binding),
            "mappingHash": cast(JsonObject, binding["timeMapping"])["mappingHash"],
            "profileHash": profile["profileHash"],
            "toolHash": profile["toolHash"],
            "originalHash": original["contentHash"],
            "deliveredHash": verification["deliveredHash"],
            "originalProbeHash": original["probeHash"],
            "deliveredProbeHash": verification["probeHash"],
        }
    return result


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise _error(f"could not write staged package file {path}: {error}") from error


def _copy_artifact(
    artifact: _InputArtifact,
    root: Path,
    cache: _MediaCacheSession | None = None,
) -> None:
    if artifact.generated is not None:
        if _hash_bytes(artifact.generated) != artifact.content_hash:
            raise _error(f"generated artifact {artifact.key} hash differs")
        _write_exclusive(root / artifact.relative_path, artifact.generated)
        return
    if cache is not None:
        cache.stage(artifact, root / artifact.relative_path)
    else:
        _copy_input_file(
            artifact.origin, root / artifact.relative_path, artifact.content_hash
        )


def _build_staging(
    staging: Path,
    *,
    document: JsonObject,
    document_raw: bytes,
    dependencies: JsonObject,
    dependencies_raw: bytes,
    manifest: JsonObject,
    manifest_raw: bytes,
    report: JsonObject,
    report_raw: bytes,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    view: JsonObject,
    encoded_bars_evidence: JsonObject | None = None,
    timing: _PackageSubtimings | None = None,
    cache: _MediaCacheSession | None = None,
) -> JsonObject:
    build_id = _id_component(cast(str, manifest["buildId"]), "build id")
    build_root = staging / BUILD_DIRECTORY / build_id
    for filename, raw in (
        (MANIFEST_FILENAME, manifest_raw),
        (REPORT_FILENAME, report_raw),
        (DOCUMENT_FILENAME, document_raw),
        (DEPENDENCIES_FILENAME, dependencies_raw),
    ):
        _write_exclusive(build_root / filename, raw)
    _write_exclusive(build_root / DELIVERY_VIEW_FILENAME, _canonical_json(view))
    if encoded_bars_evidence is not None:
        _write_exclusive(
            build_root / ENCODED_BARS_FILENAME,
            _canonical_json(encoded_bars_evidence),
        )
    for item in prepared.values():
        _write_exclusive(staging / item.relative_path, item.raw)
    for artifact in artifacts.values():
        stage = (
            "audio"
            if artifact.generated is not None and artifact.kind == "audio"
            else "slates"
            if artifact.generated is not None
            else "copy + streamed hash"
        )
        with _measure(timing, stage):
            _copy_artifact(artifact, staging, cache)
    timeline = _build_otio(
        view, cast(str, manifest["id"]), build_id, manifest, prepared, artifacts
    )
    try:
        otio.adapters.write_to_file(
            timeline, str(build_root / OTIO_FILENAME), adapter_name="otio_json"
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise _error(f"could not serialize verified v2 OTIO: {error}") from error

    package_files, _ = _walk_package(staging)
    receipt_path = f"{BUILD_DIRECTORY}/{build_id}/{VERIFICATION_FILENAME}"
    with _measure(timing, "receipt hash"):
        file_hashes = {
            path: _file_hash(staging / path) for path in sorted(package_files)
        }
    sources = cast(list[JsonObject], view["sources"])
    dep_build = cast(JsonObject, dependencies["build"])
    receipt = {
        "schemaVersion": VERIFICATION_SCHEMA_VERSION,
        "status": "ready_to_import",
        "buildId": build_id,
        "manifestId": manifest["id"],
        "reportId": report["id"],
        "documentId": document["id"],
        "eventCount": len(cast(list[JsonObject], view["events"])),
        "manifestEventCount": len(cast(list[JsonObject], manifest["events"])),
        "markerCount": len(cast(list[JsonObject], view["markers"])),
        "mediaCount": len(sources),
        "fileHashes": file_hashes,
        "sourceHashes": {source["id"]: source["contentHash"] for source in sources},
        "preparations": _receipt_preparations(prepared),
    }
    if (
        dep_build.get("buildId") != build_id
        or dep_build.get("manifestId") != manifest["id"]
        or dep_build.get("reportId") != report["id"]
    ):
        raise _error("package receipt build identity does not close")
    _write_exclusive(staging / receipt_path, _canonical_json(receipt))
    return receipt


def _safe_package_file(root: Path, relative: object, label: str) -> Path:
    rel = _safe_relative(relative, label)
    path = root.joinpath(*rel.parts)
    _require_path_components_no_symlink(path, label)
    _require_regular(path, label)
    return path


def _receipt_identity(
    receipt: JsonObject, value: JsonObject, key: str, expected: object, label: str
) -> None:
    if receipt.get(key) != expected:
        raise _error(f"package verification {label} differs from its retained {key}")


def _verify_package(project_root: Path) -> tuple[V2PackageVerification, JsonObject]:
    _require_path_components_no_symlink(project_root, "package root")
    if project_root.is_symlink() or not project_root.is_dir():
        raise _error(f"package root is not a real directory: {project_root}")
    try:
        root_names = {item.name for item in project_root.iterdir()}
    except OSError as error:
        raise _error(
            f"could not inspect package root {project_root}: {error}"
        ) from error
    if root_names != {BUILD_DIRECTORY, MEDIA_DIRECTORY}:
        raise _error("package root must contain only Builds and Media")
    builds_root = project_root / BUILD_DIRECTORY
    _require_path_components_no_symlink(builds_root, "package Builds directory")
    if not builds_root.is_dir() or builds_root.is_symlink():
        raise _error("package Builds path is not a real directory")
    build_dirs = [
        item
        for item in builds_root.iterdir()
        if item.is_dir() and not item.is_symlink()
    ]
    if len(build_dirs) != 1 or len(list(builds_root.iterdir())) != 1:
        raise _error("package root must contain exactly one immutable v2 build")
    build_root = build_dirs[0]
    build_id = _id_component(build_root.name, "build id")
    receipt_rel = f"{BUILD_DIRECTORY}/{build_id}/{VERIFICATION_FILENAME}"
    receipt_path = _safe_package_file(
        project_root, receipt_rel, "package verification receipt"
    )
    receipt, receipt_raw = _load_json(receipt_path, "package verification receipt")
    if _canonical_json(receipt) != receipt_raw:
        raise _error("package verification receipt is not canonical JSON")
    receipt_keys = {
        "schemaVersion",
        "status",
        "buildId",
        "manifestId",
        "reportId",
        "documentId",
        "eventCount",
        "manifestEventCount",
        "markerCount",
        "mediaCount",
        "fileHashes",
        "sourceHashes",
        "preparations",
    }
    if (
        set(receipt) != receipt_keys
        or receipt.get("schemaVersion") != VERIFICATION_SCHEMA_VERSION
        or receipt.get("status") != "ready_to_import"
    ):
        raise _error("package verification receipt has an unsupported shape or status")
    _receipt_identity(receipt, {}, "buildId", build_id, "build id")

    raw_files, actual_directories = _walk_package(project_root)
    files_hashes = receipt.get("fileHashes")
    if not isinstance(files_hashes, dict):
        raise _error("package verification fileHashes is not an object")
    expected_files = set(files_hashes) | {receipt_rel}
    if raw_files != expected_files:
        raise _error("package file inventory differs from the immutable receipt")
    for relative, expected_hash in files_hashes.items():
        _safe_relative(relative, "package inventory path")
        _require_hash(expected_hash, f"package file hash {relative}")
        if _file_hash(project_root / relative) != expected_hash:
            raise _error(f"package file hash mismatch: {relative}")

    manifest_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{MANIFEST_FILENAME}",
        "packaged manifest",
    )
    report_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{REPORT_FILENAME}",
        "packaged report",
    )
    document_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DOCUMENT_FILENAME}",
        "packaged document",
    )
    dependencies_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DEPENDENCIES_FILENAME}",
        "packaged dependencies",
    )
    view_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DELIVERY_VIEW_FILENAME}",
        "packaged delivery view",
    )
    manifest, _ = _load_json(manifest_path, "packaged manifest")
    report, _ = _load_json(report_path, "packaged report")
    document, _ = _load_json(document_path, "packaged document")
    dependencies, _ = _load_json(dependencies_path, "packaged dependencies")
    view, view_raw = _load_json(view_path, "packaged delivery view")
    if _canonical_json(view) != view_raw:
        raise _error("delivery view is not canonical JSON")
    _validate_inputs(document, dependencies, manifest, report)
    if (
        manifest.get("buildId") != build_id
        or receipt.get("manifestId") != manifest.get("id")
        or receipt.get("reportId") != report.get("id")
        or receipt.get("documentId") != document.get("id")
    ):
        raise _error("package receipt identity differs from its retained documents")
    preparations_raw = receipt.get("preparations")
    if not isinstance(preparations_raw, dict):
        raise _error("package preparation receipt map is invalid")
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    if set(preparations_raw) != set(bindings):
        raise _error("package preparation receipt map differs from manifest bindings")
    prep_paths: dict[str, Path] = {}
    for key, info in preparations_raw.items():
        expected_rel = (
            f"{BUILD_DIRECTORY}/{build_id}/Preparation/receipts/"
            f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}/receipt.json"
        )
        if (
            not isinstance(info, dict)
            or set(info)
            != {
                "path",
                "receiptHash",
                "bindingHash",
                "mappingHash",
                "profileHash",
                "toolHash",
                "originalHash",
                "deliveredHash",
                "originalProbeHash",
                "deliveredProbeHash",
            }
            or info.get("path") != expected_rel
        ):
            raise _error(
                f"package preparation receipt {key} has an invalid identity record"
            )
        prep_path = _safe_package_file(
            project_root, expected_rel, f"package preparation receipt {key}"
        )
        record, raw = _load_json(prep_path, f"package preparation receipt {key}")
        binding = cast(JsonObject, record.get("binding"))
        original = cast(JsonObject, binding.get("originalSource"))
        verification = cast(JsonObject, binding.get("verification"))
        profile = cast(JsonObject, binding.get("profile"))
        expected_prep = {
            "receiptHash": _hash_bytes(raw),
            "bindingHash": _compiler_hash(binding),
            "mappingHash": cast(JsonObject, binding.get("timeMapping"))["mappingHash"],
            "profileHash": profile["profileHash"],
            "toolHash": profile["toolHash"],
            "originalHash": original["contentHash"],
            "deliveredHash": verification["deliveredHash"],
            "originalProbeHash": original["probeHash"],
            "deliveredProbeHash": verification["probeHash"],
        }
        if any(info.get(field) != value for field, value in expected_prep.items()):
            raise _error(f"package preparation receipt {key} hash/provenance differs")
        prep_paths[key] = prep_path
    prepared = _validate_preparations(
        document, dependencies, manifest, report, prep_paths
    )

    encoded_bars_evidence: JsonObject | None = None
    if (
        cast(JsonObject, dependencies["authoringDefaults"]).get("hideEncodedBars")
        is True
    ):
        evidence_path = _safe_package_file(
            project_root,
            f"{BUILD_DIRECTORY}/{build_id}/{ENCODED_BARS_FILENAME}",
            "packaged bar-removal evidence",
        )
        encoded_bars_evidence, evidence_raw = _load_json(
            evidence_path, "packaged bar-removal evidence"
        )
        if _canonical_json(encoded_bars_evidence) != evidence_raw:
            raise _error("bar-removal evidence is not canonical JSON")

    sources = _unique_by_id(view.get("sources"), "delivery source")
    source_hashes = receipt.get("sourceHashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != set(sources):
        raise _error("package sourceHashes differ from delivery view sources")
    artifacts: dict[str, _InputArtifact] = {}
    for source_id, source in sources.items():
        relative = _safe_relative(
            source.get("path"), f"delivery source {source_id} path"
        ).as_posix()
        _require_hash(
            source.get("contentHash"), f"delivery source {source_id} content hash"
        )
        media_path = _safe_package_file(
            project_root, relative, f"delivery source {source_id}"
        )
        actual = _file_hash(media_path)
        if actual != source["contentHash"] or source_hashes.get(source_id) != actual:
            raise _error(
                f"delivery source {source_id} hash differs from package bytes/receipt"
            )
    manifest_sources = _unique_by_id(manifest.get("sources"), "manifest source")
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            artifact_key = f"source:{source_id}"
            content_hash = cast(JsonObject, source["narrationAudio"])["audioHash"]
        elif "musicAudio" in source:
            artifact_key = f"source:{source_id}"
            content_hash = cast(JsonObject, source["musicAudio"])["source"][
                "contentHash"
            ]
        else:
            artifact_key = f"source:{source_id}"
            content_hash = source["deliveredHash"]
        view_source = sources.get(source_id)
        if view_source is None:
            raise _error(f"manifest source {source_id} is absent from delivery view")
        artifacts[artifact_key] = _InputArtifact(
            artifact_key,
            project_root / view_source["path"],
            view_source["path"],
            content_hash,
            view_source["kind"],
        )
        if "narrationAudio" not in source:
            artifacts[f"original:{source_id}"] = _InputArtifact(
                f"original:{source_id}",
                Path("."),
                "",
                content_hash if "musicAudio" in source else source["originalHash"],
                "original",
            )
    for event in cast(list[JsonObject], manifest.get("events", [])):
        event_id = cast(str, event["eventId"])
        if event["kind"] in {"quote_box", "still_credit", "placeholder"}:
            view_source = sources.get(event_id)
            if view_source is None:
                raise _error(
                    f"{event['kind']} event {event_id} is absent from delivery view"
                )
            artifacts[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                project_root / view_source["path"],
                view_source["path"],
                view_source["contentHash"],
                "still",
            )
        elif event["kind"] == "source_audio":
            view_source = sources.get(event_id)
            if view_source is None:
                raise _error(
                    f"source audio event {event_id} is absent from delivery view"
                )
            artifacts[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                project_root / view_source["path"],
                view_source["path"],
                view_source["contentHash"],
                "audio",
            )
            prep = next(
                item
                for item in prepared.values()
                if _compiler_hash(item.record["binding"])
                == event["preparationBindingHash"]
            )
            try:
                plan = endpoint_plan(
                    event,
                    prep.record["audio"],
                    _fraction(
                        manifest["timeline"]["frameRate"],
                        "timeline rate",
                        positive=True,
                    ),
                )
            except ValueError as error:
                raise _error(f"source audio {event_id}: {error}") from error
            if plan is not None:
                original_audio_relative = _original_audio_path(manifest, event_id)
                original_audio = _safe_package_file(
                    project_root, original_audio_relative, "original source audio"
                )
                artifacts[f"original-audio:{event_id}"] = _InputArtifact(
                    f"original-audio:{event_id}",
                    original_audio,
                    original_audio_relative,
                    prep.record["audio"]["contentHash"],
                    "audio",
                )
    _validate_delivery_view(
        manifest,
        dependencies,
        view,
        prepared,
        artifacts,
        encoded_bars_evidence=encoded_bars_evidence,
    )

    # Reconstruct the only permitted package inventory from frozen IDs, view
    # sources and preparation receipts; receipt-signed unrelated files are not accepted.
    expected_inventory = {
        f"{BUILD_DIRECTORY}/{build_id}/{name}"
        for name in (
            MANIFEST_FILENAME,
            REPORT_FILENAME,
            DOCUMENT_FILENAME,
            DEPENDENCIES_FILENAME,
            DELIVERY_VIEW_FILENAME,
            OTIO_FILENAME,
            VERIFICATION_FILENAME,
        )
    }
    if encoded_bars_evidence is not None:
        expected_inventory.add(f"{BUILD_DIRECTORY}/{build_id}/{ENCODED_BARS_FILENAME}")
    expected_inventory.update(item.relative_path for item in prepared.values())
    expected_inventory.update(source["path"] for source in sources.values())
    expected_inventory.update(
        item.relative_path
        for key, item in artifacts.items()
        if key.startswith("original-audio:")
    )
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            continue
        if "musicAudio" in source:
            original_rel = (
                f"{BUILD_DIRECTORY}/{build_id}/Preparation/original/{source_id}.wav"
            )
            original_music_file = _safe_package_file(
                project_root, original_rel, f"original music source {source_id}"
            )
            delivery = artifacts[f"source:{source_id}"].origin
            if delivery.suffix.lower() != ".wav":
                raise _error(f"music source {source_id} is not a WAV sidecar")
            for music_file in (original_music_file, delivery):
                try:
                    samples = inspect_music(
                        music_file, source["musicAudio"]["source"]["contentHash"]
                    )
                except BuildJobError as error:
                    raise _error(f"music package {source_id}: {error}") from error
                if samples != source["musicAudio"]["durationSamples"]:
                    raise _error(
                        f"music package {source_id} PCM duration differs from "
                        "frozen binding"
                    )
            expected_inventory.add(original_rel)
            continue
        original_matches = [
            path
            for path in files_hashes
            if isinstance(path, str)
            and path.startswith(
                f"{BUILD_DIRECTORY}/{build_id}/Preparation/original/{source_id}."
            )
        ]
        if len(original_matches) != 1:
            raise _error(
                f"package original bytes for {source_id} are missing or duplicated"
            )
        original_path = _safe_package_file(
            project_root, original_matches[0], f"original source {source_id}"
        )
        if _file_hash(original_path) != source["originalHash"]:
            raise _error(
                f"package original bytes for {source_id} differ from manifest hash"
            )
        expected_inventory.add(original_matches[0])
    expected_inventory.discard(receipt_rel)
    if set(files_hashes) != expected_inventory:
        raise _error("package inventory includes missing or unrelated artifacts")
    all_files = expected_inventory | {receipt_rel}
    if actual_directories != _expected_directories(all_files):
        raise _error("package directory inventory includes unexpected or missing paths")

    _verify_otio(build_root, manifest, view, prepared, artifacts)
    expected_counts = {
        "eventCount": len(cast(list[JsonObject], view["events"])),
        "manifestEventCount": len(cast(list[JsonObject], manifest["events"])),
        "markerCount": len(cast(list[JsonObject], view["markers"])),
        "mediaCount": len(cast(list[JsonObject], view["sources"])),
    }
    for key, value in expected_counts.items():
        if receipt.get(key) != value:
            raise _error(
                f"package verification {key} differs from retained v2 artifacts"
            )
    return V2PackageVerification(
        build_id,
        expected_counts["eventCount"],
        expected_counts["markerCount"],
        expected_counts["mediaCount"],
    ), receipt


def verify_v2_package(project_root: Path) -> V2PackageVerification:
    """Independently verify one immutable package and its OTIO projection."""
    if not isinstance(project_root, Path):
        raise V2PackageError("project_root must be a pathlib.Path")
    verification, _ = _verify_package(project_root)
    return verification


def _read_inputs(
    manifest_path: Path,
    report_path: Path,
    document_path: Path,
    dependencies_path: Path,
) -> tuple[JsonObject, bytes, JsonObject, bytes, JsonObject, bytes, JsonObject, bytes]:
    manifest, manifest_raw = _load_json(manifest_path, "v2 manifest")
    report, report_raw = _load_json(report_path, "v2 build report")
    document, document_raw = _load_json(document_path, "v2 script document")
    dependencies, dependencies_raw = _load_json(
        dependencies_path, "v2 compiler dependencies"
    )
    return (
        document,
        document_raw,
        dependencies,
        dependencies_raw,
        manifest,
        manifest_raw,
        report,
        report_raw,
    )


def _build_v2_package(
    manifest_path: Path,
    report_path: Path,
    document_path: Path,
    dependencies_path: Path,
    project_root: Path,
    *,
    media_paths: Mapping[str, Path],
    preparation_paths: Mapping[str, Path],
    timing: _PackageSubtimings | None = None,
    cache: _MediaCacheSession | None = None,
) -> V2PackageResult:
    """Create one immutable verified v2 package under a fresh project root."""
    paths = (manifest_path, report_path, document_path, dependencies_path, project_root)
    if any(not isinstance(path, Path) for path in paths):
        raise V2PackageError(
            "all package input and output paths must be pathlib.Path values"
        )
    if not isinstance(media_paths, Mapping) or not isinstance(
        preparation_paths, Mapping
    ):
        raise V2PackageError(
            "media_paths and preparation_paths must be explicit mappings"
        )
    (
        document,
        document_raw,
        dependencies,
        dependencies_raw,
        manifest,
        manifest_raw,
        report,
        report_raw,
    ) = _read_inputs(manifest_path, report_path, document_path, dependencies_path)
    _validate_inputs(document, dependencies, manifest, report)
    prepared = _validate_preparations(
        document, dependencies, manifest, report, preparation_paths
    )
    artifacts = _media_artifacts(manifest, prepared, media_paths, timing, cache)
    encoded_bars_evidence = _make_encoded_bars_evidence(
        manifest,
        dependencies,
        prepared,
        artifacts,
        timing=timing,
    )
    view = _delivery_view(
        manifest,
        dependencies,
        prepared,
        artifacts,
        cache=cache,
        encoded_bars_evidence=encoded_bars_evidence,
    )

    root = project_root.absolute()
    if root == root.parent or root.name in {"", ".", ".."}:
        raise V2PackageError("project_root must name a dedicated package directory")
    _require_path_components_no_symlink(root.parent, "package parent directory")
    root.parent.mkdir(parents=True, exist_ok=True)
    _require_path_components_no_symlink(root, "package root")
    lock_path = root.parent / f".{root.name}.v2-package.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise _error(f"could not open package lock {lock_path}: {error}") from error
    staging: Path | None = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _require_path_components_no_symlink(root, "package root")
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise _error(
                f"package root already exists and is not a real directory: {root}"
            )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{root.name}.v2-staging-", dir=root.parent)
        )
        _build_staging(
            staging,
            document=document,
            document_raw=document_raw,
            dependencies=dependencies,
            dependencies_raw=dependencies_raw,
            manifest=manifest,
            manifest_raw=manifest_raw,
            report=report,
            report_raw=report_raw,
            prepared=prepared,
            artifacts=artifacts,
            view=view,
            encoded_bars_evidence=encoded_bars_evidence,
            timing=timing,
            cache=cache,
        )
        with _measure(timing, "verification"):
            try:
                proposed_verification, proposed_receipt = _verify_package(staging)
            except V2PackageError as error:
                if cache is None or not cache.cached_used:
                    raise
                # Only an independent *staging* mismatch can trigger the one
                # fresh-source retry; never retry after native or publication.
                shutil.rmtree(staging)
                staging = None
                raise _CachedIntegrityFailure(
                    "cached package bytes failed independent staging verification"
                ) from error
        if root.exists():
            if any(root.iterdir()):
                try:
                    with _measure(timing, "verification"):
                        existing_verification, existing_receipt = _verify_package(root)
                except V2PackageError as error:
                    raise _error(
                        f"project root is not the same verified package: {root}"
                    ) from error
                if (
                    existing_verification != proposed_verification
                    or existing_receipt != proposed_receipt
                ):
                    raise _error(
                        f"project root is not the same verified package: {root}"
                    )
                old_files, _ = _walk_package(root)
                new_files, _ = _walk_package(staging)
                if old_files != new_files or any(
                    (root / item).read_bytes() != (staging / item).read_bytes()
                    for item in old_files
                ):
                    raise _error(
                        f"project root already exists and is not byte-identical: {root}"
                    )
                shutil.rmtree(staging)
                staging = None
                return V2PackageResult(root, proposed_verification.build_id, True)
            root.rmdir()
        if root.exists():
            raise _error(f"project root appeared during package publication: {root}")
        os.rename(staging, root)
        staging = None
        with _measure(timing, "verification"):
            published = verify_v2_package(root)
        if published != proposed_verification:
            raise _error("published package differs from its staged verification")
        return V2PackageResult(root, published.build_id, False)
    except _SuppliedHashMismatch:
        if staging is not None:
            shutil.rmtree(staging)
            staging = None
        raise
    except V2PackageError as error:
        if staging is None:
            raise
        retained = staging
        staging = None
        raise _error(f"{error}; partial package retained at {retained}") from error
    except (OSError, RuntimeError, ValueError) as error:
        if staging is None:
            raise _error(
                f"could not publish v2 package under {root}: {error}"
            ) from error
        retained = staging
        staging = None
        raise _error(
            f"could not publish v2 package under {root}: {error}; "
            f"partial package retained at {retained}"
        ) from error
    except Exception as error:
        if staging is None:
            raise _error(
                f"could not publish v2 package under {root}: {error}"
            ) from error
        retained = staging
        staging = None
        raise _error(
            f"could not publish v2 package under {root}: {error}; "
            f"partial package retained at {retained}"
        ) from error
    except BaseException as error:
        if staging is not None:
            retained = staging
            staging = None
            error.add_note(f"partial v2 package retained at {retained}")
        raise
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def build_v2_package(
    manifest_path: Path,
    report_path: Path,
    document_path: Path,
    dependencies_path: Path,
    project_root: Path,
    *,
    media_paths: Mapping[str, Path],
    preparation_paths: Mapping[str, Path],
    stage_observer: Callable[[str, float, bool], None] | None = None,
    package_cache: Path | None = None,
    cache_observer: Callable[[int, int], None] | None = None,
) -> V2PackageResult:
    """Build a v2 package, optionally reporting non-overlapping substep timings.

    A timing observer is diagnostic only and is never serialized into the package.
    Verification is independent and remains mandatory with or without an observer.
    """
    if package_cache is not None:
        cache_root, project_path = package_cache.resolve(), project_root.resolve()
        if cache_root.is_relative_to(project_path) or project_path.is_relative_to(
            cache_root
        ):
            raise V2PackageError("package cache must be outside the package directory")
    timing: _PackageSubtimings | None = None
    cache = _MediaCacheSession(package_cache) if package_cache is not None else None
    try:
        for attempt in range(2):
            # A failed cache attempt must not mark successful retry timings FAIL.
            timing = (
                _PackageSubtimings(stage_observer)
                if stage_observer is not None
                else None
            )
            try:
                return _build_v2_package(
                    manifest_path,
                    report_path,
                    document_path,
                    dependencies_path,
                    project_root,
                    media_paths=media_paths,
                    preparation_paths=preparation_paths,
                    timing=timing,
                    cache=cache,
                )
            except _CachedIntegrityFailure:
                if attempt or cache is None:
                    raise
                cache.discard_used()
                cache = _MediaCacheSession(cache.store.root, force_source=True)
        raise AssertionError("unreachable cache retry state")
    finally:
        if cache is not None and cache_observer is not None:
            cache_observer(cache.reused, cache.processed)
        if timing is not None:
            timing.report()
