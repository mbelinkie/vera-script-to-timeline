"""Build a Resolve timeline from approved presenter takes (#48).

The frozen timing from the recorded conform preview (#47) goes through the
normal one-command build. Then each approved take is cut from the recording's
graded source clip (#94) onto V1 and A1, in place of the temporary presenter
picture and the silent stand-in for its sound. See the presenter conform guide
in docs.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .presenter_source import (
    Names,
    Piece,
    Recording,
    SourceError,
    _must,
    _save_reopen,
    _timelines,
    check_source,
    place_piece,
    probe,
    tight_zoom,
)
from .recorded_conform import BLOCKED, SCHEMA, ConformRefused
from .recorded_timing_adapter import (
    _timeline_rows,
    derived_dependencies,
    write_silent_carrier,
)
from .recorded_word_evidence import canonical_json, sha256

Json = dict[str, Any]
PICTURE_TRACK = "vera-presenter-picture"
SOUND_TRACK = "vera-presenter-sound"
COLORS = {"wide": "Blue", "tight": "Orange"}


class ConformError(ValueError):
    """The presenter timeline could not be built; the message says why."""


@dataclass(frozen=True)
class Take:
    row_id: str
    piece: Piece

    @property
    def label(self) -> str:
        return f"OC {self.piece.framing.upper()} {self.row_id}"


@dataclass(frozen=True)
class Plan:
    takes: tuple[Take, ...]
    replaced: tuple[str, ...]  # events of the normal build the takes replace


@dataclass(frozen=True)
class Inputs:
    snapshot: Json
    recording: Recording
    folder: Path


@dataclass(frozen=True)
class Conformed:
    project: str
    timeline: str
    takes: tuple[Take, ...]
    temp_voice_rows: tuple[str, ...]


def _read(path: Path, what: str) -> Json:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise ConformError(f"Cannot read {what} ({path.name}).") from error
    if not isinstance(value, dict):
        raise ConformError(f"{what} ({path.name}) is not a JSON object.")
    return value


def load_snapshot(folder: Path) -> Json:
    snapshot = _read(folder / "snapshot.json", "the frozen takes")
    body = {key: value for key, value in snapshot.items() if key != "snapshotSha256"}
    if (
        snapshot.get("schemaVersion") != SCHEMA
        or snapshot.get("snapshotSha256") != sha256(canonical_json(body))
        or not isinstance(snapshot.get("rows"), list)
        or not snapshot["rows"]
    ):
        raise ConformError(
            "snapshot.json is not an unchanged recorded conform snapshot; "
            "make it again with recorded_conform_cli."
        )
    blocked = [
        f"{row.get('rowId')} ({row.get('state')})"
        for row in snapshot["rows"]
        if row.get("state") in BLOCKED
        or row.get("state") not in {"take", "temp_voice", "no_spoken_line"}
    ]
    if blocked:
        raise ConformError("These rows still need a decision: " + ", ".join(blocked))
    return snapshot


def check_recording(
    snapshot: Json,
    video: Path,
    audio: Path,
    *,
    hash_video: Callable[[Path], str] | None = None,
    probe_recording: Callable[[Path, Path], Recording] = probe,
) -> Recording:
    """The video must be the one the takes were found in, with its clean audio."""
    from .presenter_approvals import ApprovalError, observed_video

    source = snapshot["source"]
    try:
        digest = observed_video(video, hash_video)
    except ApprovalError as error:
        raise ConformError(f"Cannot read the recording {video.name}.") from error
    if digest != source["sha256"]:
        raise ConformError(
            f'"{video.name}" is not the recording the takes were found in '
            f'("{source["file"]}"). Use that recording, or find and approve the '
            "takes again for this one."
        )
    recording = probe_recording(video, audio)
    if recording.rate != Fraction(*source["fps"]):
        raise ConformError(
            f'"{video.name}" does not have the frame rate the takes were found at.'
        )
    for row in snapshot["rows"]:
        if row["state"] != "take":
            continue
        cut = row["effectiveCut"]
        if (
            Fraction(*row["sourceRate"]) != recording.rate
            or not 0 <= cut["startFrame"] < cut["endFrame"] <= recording.frames
        ):
            raise ConformError(f"{row['rowId']}: the take is outside the recording.")
    return recording


def relayout(dependencies: Json) -> Json:
    """Give the presenter the lowest picture and sound tracks, both empty.

    The normal build puts the script's pictures on the lowest video track and
    the narration on A1. The presenter goes under the pictures, so every other
    track moves up one.
    """
    result = copy.deepcopy(dependencies)
    roles, tracks = result["roles"], result["tracks"]
    if {PICTURE_TRACK, SOUND_TRACK} & {track["id"] for track in tracks}:
        raise ConformError("These build inputs already hold a presenter timeline.")
    old = roles.get("presenterTrackId")
    held = {
        roles.get("primaryRootTrackId"),
        roles.get("placeholderTrackId"),
        roles.get("markerTrackId"),
        *roles.get("childTrackIds", []),
        *roles.get("overlayTrackIds", []),
    }
    if old not in held:  # an empty track kept only for the presenter
        tracks[:] = [track for track in tracks if track["id"] != old]
    roles["presenterTrackId"] = PICTURE_TRACK
    roles["sourceAudioTrackIds"] = [SOUND_TRACK, *roles.get("sourceAudioTrackIds", [])]
    for kind, track_id, name in (
        ("video", PICTURE_TRACK, "Presenter"),
        ("audio", SOUND_TRACK, "Presenter sound"),
    ):
        same = sorted(
            (track for track in tracks if track["kind"] == kind),
            key=lambda track: track["index"],
        )
        for index, track in enumerate(same, 2):
            track["index"] = index
        tracks.append({"id": track_id, "kind": kind, "index": 1, "name": name})
    return result


def prepare_inputs(
    snapshot_folder: Path,
    prepared: Path,
    video: Path,
    audio: Path,
    folder: Path,
    *,
    hash_video: Callable[[Path], str] | None = None,
    probe_recording: Callable[[Path, Path], Recording] = probe,
) -> Inputs:
    """Check the frozen takes and write the normal build's inputs. No Resolve."""
    snapshot = load_snapshot(snapshot_folder)
    recording = check_recording(
        snapshot, video, audio, hash_video=hash_video, probe_recording=probe_recording
    )
    original = _read(prepared / "compiler-dependencies.json", "the prepared inputs")
    try:
        derived, carriers = derived_dependencies(snapshot, original)
    except (ConformRefused, KeyError, TypeError) as error:
        raise ConformError(
            "The prepared inputs are not the ones the takes were frozen against."
        ) from error
    frozen = snapshot_folder / "compiler-dependencies.json"
    script = snapshot_folder / "script-document.json"
    if (
        snapshot["compilerDependenciesSha256"] != sha256(canonical_json(original))
        or not frozen.is_file()
        or frozen.read_bytes() != canonical_json(derived)
        or not script.is_file()
    ):
        raise ConformError(
            "The prepared inputs are not the ones the takes were frozen against."
        )
    rate = derived["timeline"]["frameRate"]
    if Fraction(rate["numerator"], rate["denominator"]) != recording.rate:
        raise ConformError(
            f"The script's timeline is {rate['numerator']}/{rate['denominator']} fps "
            f"and the recording is {recording.rate} fps. They must match; nothing "
            "is retimed."
        )
    impact_path = snapshot_folder / "impact.json"
    impact = _read(impact_path, "the timing preview") if impact_path.is_file() else {}
    short = [
        f"{item.get('sourceId')} (needs {item.get('requiredRange')}, "
        f"has {item.get('availableRange')})"
        for item in impact.get("shortSources", [])
    ]
    if short:
        raise ConformError(
            "These clips are too short for where the recorded words put them: "
            + "; ".join(short)
            + ". Nothing is looped, frozen or slowed. Choose a longer clip or a "
            "different picture, then freeze the takes again."
        )

    # The frozen settings still carry the temporary voice's timeline length.
    try:
        rows = _timeline_rows(_read(script, "the frozen script"), derived)
    except (ConformRefused, KeyError, TypeError) as error:
        raise ConformError("The frozen script does not match its timing.") from error
    build_inputs = relayout(derived)
    build_inputs["timeline"]["durationFrames"] = sum(
        row["durationFrames"] for row in rows
    )

    folder.mkdir(parents=True)
    shutil.copyfile(script, folder / "script-document.json")
    (folder / "compiler-dependencies.json").write_bytes(canonical_json(build_inputs))
    paths_file = prepared / "media-paths.json"
    media = _read(paths_file, "the prepared media list") if paths_file.is_file() else {}
    carrier_folder = folder / "timing-carriers"
    carrier_folder.mkdir()
    by_name = {carrier["name"]: carrier for carrier in carriers}
    for carrier in carriers:
        write_silent_carrier(carrier, carrier_folder)
    for timing in derived["narrationTimingMaps"]:
        name = Path(timing["audio"]["locator"]).name
        if name in by_name:
            media[f"source:{timing['narrationAssetId']}"] = str(carrier_folder / name)
    for row in snapshot["rows"]:
        if row["state"] != "temp_voice":  # its temporary voice is not built
            media.pop(f"source:{row['oldNarrationAssetId']}", None)
    (folder / "media-paths.json").write_bytes(canonical_json(media))
    preparations = prepared / "preparation-paths.json"
    if preparations.is_file():
        shutil.copyfile(preparations, folder / "preparation-paths.json")
    return Inputs(snapshot, recording, folder)


def plan_takes(snapshot: Json, manifest: Json) -> Plan:
    """Where each take goes, and which normal-build clips it replaces."""
    origin = manifest["timeline"]["startFrame"]
    narration = {
        event["provenance"]["blockId"]: event
        for event in manifest["events"]
        if event["kind"] == "narration"
    }
    takes: list[Take] = []
    replaced: list[str] = []
    for row in snapshot["rows"]:
        if row["state"] != "take":
            continue
        event = narration.get(row["blockId"])
        cut = row["effectiveCut"]
        length = cut["endFrame"] - cut["startFrame"]
        span = event["recordRange"] if event else {}
        if not event or span["endFrame"] - span["startFrame"] != length:
            raise ConformError(
                f"{row['rowId']}: the built row is not the length of its take."
            )
        takes.append(
            Take(
                row["rowId"],
                Piece(
                    cut["startFrame"],
                    cut["endFrame"],
                    span["startFrame"] - origin,
                    row["framing"],
                ),
            )
        )
        replaced.append(event["eventId"])
        replaced.extend(
            other["eventId"]
            for other in manifest["events"]
            if other["kind"] == "placeholder"
            and other["provenance"]["blockId"] == row["blockId"]
            and (other.get("pictureTreatment") or {}).get("kind") == "still"
        )
    if not takes:
        raise ConformError("No row has an approved take, so there is nothing to cut.")
    return Plan(tuple(takes), tuple(replaced))


def _signature(timeline: Any) -> list[tuple[Any, ...]]:
    return [
        (kind, index, item.GetStart(False), item.GetDuration(False), item.GetName())
        for kind in ("video", "audio")
        for index in range(1, timeline.GetTrackCount(kind) + 1)
        for item in timeline.GetItemListInTrack(kind, index) or []
    ]


def other_timelines(project: Any, name: str | None = None) -> dict[str, Any]:
    return {
        title: _signature(timeline)
        for title, timeline in _timelines(project).items()
        if title != name
    }


def _current(resolve: Any, name: str) -> Any:
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None or project.GetName() != name:
        raise ConformError(f'Open the project "{name}" in Resolve first.')
    return project


def check_project(resolve: Any, name: str, recording: Recording) -> dict[str, Any]:
    """Before anything is built: the graded source must be in the open project."""
    project = _current(resolve, name)
    try:
        check_source(project, recording, Names.of(recording.stem))
    except SourceError as error:
        raise ConformError(
            f'The project "{name}" has no source for "{recording.video.name}" '
            f"({error}) Build it with presenter_source first."
        ) from error
    return other_timelines(project)


def _expected(row_map: Json, plan: Plan) -> dict[tuple[str, int], list[tuple[int, int]]]:
    kept: dict[tuple[str, int], list[tuple[int, int]]] = {}
    for row in row_map["rows"]:
        for item in row["items"]:
            if item["eventId"] not in plan.replaced:
                kept.setdefault((item["trackKind"], item["trackIndex"]), []).append(
                    (item["startFrame"], item["durationFrames"])
                )
    return {slot: sorted(spans) for slot, spans in kept.items()}


def check_conformed(
    timeline: Any, names: Names, plan: Plan, zoom: float, row_map: Json
) -> None:
    """Read the finished timeline back against the takes and the normal build."""
    start = timeline.GetStartFrame()
    kept = _expected(row_map, plan)
    for kind in ("video", "audio"):
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            items = sorted(
                timeline.GetItemListInTrack(kind, index) or [],
                key=lambda item: item.GetStart(False),
            )
            if index > 1:
                spans = [(i.GetStart(False), i.GetDuration(False)) for i in items]
                if spans != kept.get((kind, index), []):
                    raise ConformError(
                        f"The script's own clips on {kind} track {index} changed."
                    )
                continue
            if len(items) != len(plan.takes):
                raise ConformError(f"The presenter {kind} track has the wrong clips.")
            for item, take in zip(items, plan.takes, strict=True):
                piece, clip = take.piece, item.GetMediaPoolItem()
                ok = (
                    clip is not None
                    and clip.GetName() == names.source
                    and item.GetStart(False) - start == piece.offset
                    and item.GetDuration(False) == piece.end - piece.start
                    and item.GetLeftOffset(False) == piece.start
                )
                if ok and kind == "video":
                    want = zoom if piece.framing == "tight" else 1.0
                    ok = item.GetClipColor() == COLORS[piece.framing] and all(
                        isinstance(got, (int, float)) and abs(got - want) <= 1e-6
                        for got in (
                            item.GetProperty("ZoomX"),
                            item.GetProperty("ZoomY"),
                        )
                    )
                if not ok:
                    raise ConformError(
                        f"{take.row_id}: the take did not read back as placed."
                    )


def conform_timeline(
    resolve: Any,
    project_name: str,
    timeline_name: str,
    recording: Recording,
    plan: Plan,
    row_map: Json,
    before: Mapping[str, Any],
) -> None:
    """Swap the takes into the timeline the normal build just made and check it."""
    project = _current(resolve, project_name)
    names = Names.of(recording.stem)
    timeline = _timelines(project).get(timeline_name)
    if timeline is None:
        raise ConformError(f'Timeline "{timeline_name}" is missing.')
    try:
        compound = check_source(project, recording, names)
        size = (
            int(timeline.GetSetting("timelineResolutionWidth")),
            int(timeline.GetSetting("timelineResolutionHeight")),
        )
        zoom = tight_zoom((recording.width, recording.height), size)
        _must(project.SetCurrentTimeline(timeline), "selecting the new timeline")
        found = {
            item.GetUniqueId(): item
            for kind in ("video", "audio")
            for index in range(1, timeline.GetTrackCount(kind) + 1)
            for item in timeline.GetItemListInTrack(kind, index) or []
        }
        ids = {
            item["eventId"]: item["resolveItemId"]
            for row in row_map["rows"]
            for item in row["items"]
        }
        gone = [found.get(ids.get(event, "")) for event in plan.replaced]
        if any(item is None for item in gone):
            raise ConformError("The new timeline is not as the normal build left it.")
        _must(timeline.DeleteClips(gone, False), "removing the temporary clips")
        for take in plan.takes:
            placed = place_piece(project, timeline, compound, take.piece, zoom)
            picture = [item for item in placed if item.GetProperty("ZoomX") is not False]
            for item in picture or list(placed[:1]):
                item.SetName(take.label)
                _must(
                    item.SetClipColor(COLORS[take.piece.framing]),
                    "the framing colour",
                )
        project = _save_reopen(resolve, project_name)
        reopened = _timelines(project).get(timeline_name)
        if reopened is None:
            raise ConformError(f'Timeline "{timeline_name}" is missing after reopen.')
        check_conformed(reopened, names, plan, zoom, row_map)
        if other_timelines(project, timeline_name) != dict(before):
            raise ConformError("An earlier timeline in the project changed.")
        project.SetCurrentTimeline(reopened)
    except (SourceError, ConformError) as error:
        raise ConformError(
            f'{error} The unfinished timeline "{timeline_name}" is left in '
            f'"{project_name}"; delete it before trying again.'
        ) from error


def report(done: Conformed) -> str:
    lines = [
        f'Built timeline "{done.timeline}" in project "{done.project}".',
        "Checked after save, close and reopen: every take is cut from the graded "
        "source, picture on V1 and sound on A1, and earlier timelines are unchanged.",
    ]
    for take in done.takes:
        piece = take.piece
        lines.append(
            f"  {take.row_id}: recording frames {piece.start}-{piece.end} at "
            f"timeline frame {piece.offset}, {piece.framing}"
        )
    if done.temp_voice_rows:
        lines.append(
            "Still on the temporary voice: " + ", ".join(done.temp_voice_rows) + "."
        )
    lines.append(
        "Wide takes are blue and tight takes orange; their names start OC WIDE "
        "or OC TIGHT."
    )
    return "\n".join(lines)


def build(
    snapshot_folder: Path,
    prepared: Path,
    video: Path,
    audio: Path,
    output: Path,
    project_name: str,
    *,
    resolve_app: Path | None = None,
    emit: Callable[[str], None] = print,
) -> Conformed:
    # Imported here so the offline checks and tests need no Resolve installation.
    from .build_jobs import NeedsAction
    from .build_timeline_once import (
        BuildOptions,
        StageTimings,
        _external_resolve,
        compile_prepared,
        deliver_compiled,
        exclusive_resolve_build,
    )
    from .package_cache import default_cache_root

    output = output.absolute()
    if output.exists():
        raise ConformError("The output folder already exists; choose a new one.")
    inputs = prepare_inputs(
        snapshot_folder.absolute(),
        prepared.absolute(),
        video.absolute(),
        audio.absolute(),
        output / "inputs",
    )
    with exclusive_resolve_build():
        before = check_project(
            _external_resolve(resolve_app), project_name, inputs.recording
        )
    timings = StageTimings(emit=emit)
    try:
        compiled = compile_prepared(
            BuildOptions(
                script=inputs.folder / "script-document.json",
                inputs=inputs.folder,
                output=output / "build",
                existing_project=project_name,
                resolve_app=resolve_app,
            ),
            timings=timings,
        )
    except NeedsAction as error:
        raise ConformError(
            f"{error}. The recorded timing changed what a picture needs from its "
            "clip; see impact.txt beside the snapshot for the rows that moved, "
            "then prepare the media again."
        ) from error
    plan = plan_takes(inputs.snapshot, _read(compiled.manifest, "the build plan"))
    delivered = deliver_compiled(
        compiled,
        timings=timings,
        existing_project=project_name,
        package_cache=default_cache_root(),
        resolve_app=resolve_app,
    )
    row_map = _read(output / "build" / "row-timeline-map.json", "the row map")
    with exclusive_resolve_build():
        conform_timeline(
            _external_resolve(resolve_app),
            project_name,
            delivered.timeline_name,
            inputs.recording,
            plan,
            row_map,
            before,
        )
    return Conformed(
        project_name,
        delivered.timeline_name,
        plan.takes,
        tuple(
            row["rowId"]
            for row in inputs.snapshot["rows"]
            if row["state"] == "temp_voice"
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, required=True, help="folder from recorded_conform_cli"
    )
    parser.add_argument(
        "--prepared", type=Path, required=True, help="the prepared inputs it used"
    )
    parser.add_argument("--video", type=Path, required=True, help="the recording")
    parser.add_argument("--audio", type=Path, required=True, help="cleaned WAV (#92)")
    parser.add_argument(
        "--existing-project",
        required=True,
        help="the project holding the recording's source, open in Resolve",
    )
    parser.add_argument("--output", type=Path, required=True, help="a new folder")
    parser.add_argument(
        "--resolve-app", type=Path, metavar="BUNDLE.app", help="Resolve Studio bundle"
    )
    args = parser.parse_args(argv)
    from .build_jobs import BuildJobError, NeedsAction, UncertainResult

    try:
        done = build(
            args.snapshot,
            args.prepared,
            args.video,
            args.audio,
            args.output,
            args.existing_project,
            resolve_app=args.resolve_app,
        )
    except (
        ConformError,
        SourceError,
        BuildJobError,
        NeedsAction,
        UncertainResult,
    ) as error:
        print(f"Presenter timeline not built: {error}", file=sys.stderr)
        return 1
    print(report(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
