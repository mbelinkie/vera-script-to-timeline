"""Load the baseline a finished timeline is compared against.

A build's results folder is a baseline as it stands. An in-place update (#104)
changes only some rows, so its folder describes the timeline as "the earlier
baseline, with the updated rows taken from this build". That keeps a usable
baseline even when other rows were refused or left out of sync.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .readback_timeline_cli import _load_readback_package, _read_saved_row_map
from .row_timeline_map import SCHEMA_VERSION_V2, validate_saved_row_map
from .workflow_v2 import _read_regular, _regular_absolute, _strict_object

RECORD_NAME = "timeline-update.json"
RECORD_SCHEMA = "vera-timeline-update/v1"
_MAX_JSON = 16 * 1024 * 1024
_MAX_CHAIN = 200


@dataclass(frozen=True)
class Baseline:
    root: Path
    manifest: dict[str, Any]
    view: dict[str, Any]
    saved: dict[str, Any]
    document: dict[str, Any]
    updated_in_place: bool


def compose(
    manifest: Mapping[str, Any],
    view: Mapping[str, Any],
    new_manifest: Mapping[str, Any],
    new_view: Mapping[str, Any],
    updated_rows: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The earlier manifest and view with the updated rows' clips swapped in.

    Only rows updated in place qualify: their clips keep their positions, so
    the timeline's length, tracks and every other row are the earlier ones.
    """
    rows = set(updated_rows)

    def row_of(event: Mapping[str, Any]) -> Any:
        return event["provenance"].get("blockId")

    events = [event for event in manifest["events"] if row_of(event) not in rows]
    events += [event for event in new_manifest["events"] if row_of(event) in rows]
    events.sort(
        key=lambda event: (event["recordRange"]["startFrame"], event["eventId"])
    )
    view_events = [e for e in view["events"] if row_of(e["v2Event"]) not in rows]
    view_events += [e for e in new_view["events"] if row_of(e["v2Event"]) in rows]
    view_events.sort(key=lambda e: (e["recordRange"]["startFrame"], e["id"]))
    used = {event["sourceId"] for event in view_events}
    sources = {source["id"]: source for source in view["sources"]}
    sources.update({source["id"]: source for source in new_view["sources"]})
    replacements = {plan["id"]: plan for plan in new_manifest.get("transitions", [])}
    transitions = []
    for plan in manifest.get("transitions", []):
        if rows & {plan.get("fromRowId"), plan["toRowId"]}:
            if plan["id"] not in replacements:
                raise ValueError("an updated row lost its transition plan")
            plan = replacements[plan["id"]]
        transitions.append(plan)
    tracks = {track["id"] for track in view["tracks"]}
    if any(event["trackId"] not in tracks for event in view_events):
        raise ValueError("an updated clip is on a track the timeline does not have")
    composed_manifest = {**manifest, "events": events}
    if "transitions" in manifest:
        composed_manifest["transitions"] = transitions
    if "sources" in manifest:
        by_id = {source["id"]: source for source in manifest["sources"]}
        by_id.update({source["id"]: source for source in new_manifest["sources"]})
        composed_manifest["sources"] = [by_id[key] for key in sorted(by_id)]
    composed_view = {
        **view,
        "events": view_events,
        "sources": [sources[key] for key in sorted(used)],
    }
    return composed_manifest, composed_view


def read_record(root: Path) -> dict[str, Any] | None:
    path = root / RECORD_NAME
    if not path.exists() and not path.is_symlink():
        return None
    record = _strict_object(
        _read_regular(path, "timeline update record", max_bytes=_MAX_JSON),
        "timeline update record",
    )
    rows = record.get("updatedRows")
    previous = record.get("previousBaseline")
    full = record.get("mode") == "full"
    if (
        record.get("schemaVersion") != RECORD_SCHEMA
        or record.get("mode") not in (None, "full")
        or (
            not full
            and (
                not isinstance(rows, list)
                or not rows
                or any(not isinstance(row, str) or not row for row in rows)
                or len(set(rows)) != len(rows)
            )
        )
        or not isinstance(previous, str)
        or not Path(previous).is_absolute()
    ):
        raise ValueError("timeline update record is invalid")
    return record


def load_baseline(output: Path, *, _depth: int = 0) -> Baseline:
    """Verify and load a build or update folder as a comparison baseline."""
    if _depth > _MAX_CHAIN:
        raise ValueError("the chain of timeline updates is too long or loops")
    root = _regular_absolute(output.absolute(), "baseline output", directory=True)
    saved = _read_saved_row_map(root)
    if saved is None:
        raise ValueError("this output has no row-timeline-map.json baseline")
    if saved.get("version") == 1:
        raise ValueError("this build has a version 1 row map; it needs a new baseline")
    if saved.get("schemaVersion") != SCHEMA_VERSION_V2:
        raise ValueError("unrecognized Resolve baseline format")
    package = _load_readback_package(root)
    record = read_record(root)
    if record is not None and record.get("buildId") != package.manifest["buildId"]:
        raise ValueError("timeline update record is for a different build")
    if record is None or record.get("mode") == "full":
        # A build, or an update that brought the whole timeline to its script.
        validate_saved_row_map(package.manifest, package.view, saved)
        if record is None and (
            saved["timelineName"] != package.attestation["timelineName"]
        ):
            raise ValueError("baseline timeline name differs from the verified build")
        if record is not None and saved.get("timelineId") != record.get("timelineId"):
            raise ValueError("update baseline is for a different Resolve timeline")
        document = _strict_object(
            _read_regular(
                package.root
                / "Builds"
                / package.manifest["buildId"]
                / "script-document.json",
                "attested original script",
                max_bytes=_MAX_JSON,
            ),
            "attested original script",
        )
        return Baseline(
            root, package.manifest, package.view, saved, document, record is not None
        )
    try:
        earlier = load_baseline(Path(record["previousBaseline"]), _depth=_depth + 1)
    except (OSError, ValueError) as error:
        raise ValueError(
            f"the earlier baseline this update builds on is unusable ({error})"
        ) from error
    manifest, view = compose(
        earlier.manifest,
        earlier.view,
        package.manifest,
        package.view,
        record["updatedRows"],
    )
    validate_saved_row_map(manifest, view, saved)
    if any(
        saved.get(key) != earlier.saved.get(key)
        for key in ("timelineId", "timelineName", "resolveProjectId", "projectName")
    ):
        raise ValueError("update baseline is for a different Resolve timeline")
    return Baseline(root, manifest, view, saved, earlier.document, True)
