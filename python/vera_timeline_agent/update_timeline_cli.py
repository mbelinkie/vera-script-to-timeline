"""Update only the changed rows of the open, hand-finished VERA timeline.

Shows what it would do and changes nothing until rows are agreed. Before any
change it duplicates the timeline and keeps the copy as the archive.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import timeline_update as planning
from . import timeline_update_native as native
from .build_jobs import BuildJobError, NeedsAction, UncertainResult
from .build_timeline_once import (
    BuildOptions,
    StageTimings,
    _external_resolve,
    _read_json,
    compile_prepared,
    exclusive_resolve_build,
    package_compiled,
)
from .observe_timeline_cli import baseline_timeline_name, observe_current
from .package_cache import default_cache_root
from .readback_timeline_cli import _load_readback_package, _read_saved_row_map
from .row_timeline_map import (
    SCHEMA_VERSION_V2,
    make_row_timeline_map,
    observe_item_details,
    validate_saved_row_map,
)
from .three_way_compare import compare_three_way_rows
from .workflow_v2 import (
    VerifiedPackageV2,
    _current_readback_target,
    _package_path,
    _regular_absolute,
    _stamp,
)

Choice = Sequence[str] | str | None
Chooser = Callable[[Sequence[Mapping[str, Any]]], Choice]


@dataclass(frozen=True)
class UpdateOptions:
    baseline_output: Path
    script: Path
    output: Path
    inputs: Path | None = None
    package_cache: Path | None = None


def prepare_current(options: UpdateOptions, timings: StageTimings) -> VerifiedPackageV2:
    """Compile and package the current script. Never contacts Resolve."""
    compiled = compile_prepared(
        BuildOptions(
            script=options.script, output=options.output, inputs=options.inputs
        ),
        timings=timings,
    )
    checked, _, _ = package_compiled(
        compiled,
        timings=timings,
        package_cache=options.package_cache or default_cache_root(),
    )
    return checked


def _publish(path: Path, value: Any) -> None:
    """Replace a record atomically so a crash never leaves half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _new_baseline_map(
    saved: Mapping[str, Any],
    old_view: Mapping[str, Any],
    current: VerifiedPackageV2,
    edits: Sequence[Mapping[str, Any]],
    items: Mapping[str, tuple[str, int, Any]],
) -> dict[str, Any]:
    """The row map of the whole timeline against the current script's build."""
    old_events = {event["id"]: event for event in old_view["events"]}
    uid_by_event = {
        item["eventId"]: item["resolveItemId"]
        for row in saved["rows"]
        for item in row["items"]
    }
    for edit in edits:
        uid_by_event.pop(edit["previousEventId"], None)
        uid_by_event[edit["eventId"]] = edit["resolveItemId"]
    replaced = {edit["eventId"] for edit in edits}
    tracks = {track["id"]: track for track in current.view["tracks"]}
    observed = []
    for event in current.view["events"]:
        uid = uid_by_event.get(event["id"])
        if uid is None or uid not in items:
            raise ValueError("a clip of the current script has no Resolve item")
        if event["id"] not in replaced and _stamp(event) != _stamp(
            old_events[event["id"]]
        ):
            raise ValueError("an untouched clip differs between the two builds")
        kind, index, item = items[uid]
        observed.append(
            {
                "eventId": event["id"],
                "resolveItemId": uid,
                "trackId": event["trackId"],
                "trackKind": kind,
                "trackIndex": index,
                "startFrame": item.GetStart(False),
                "durationFrames": item.GetDuration(False),
                **observe_item_details(item),
            }
        )
        if tracks[event["trackId"]]["index"] != index:
            raise ValueError("a clip is not on the track the script expects")
    result = make_row_timeline_map(
        current.manifest,
        current.view,
        observed,
        project_name=saved["projectName"],
        resolve_project_id=saved["resolveProjectId"],
        timeline_name=saved["timelineName"],
        timeline_id=saved["timelineId"],
        version=2,
    )
    validate_saved_row_map(current.manifest, current.view, result)
    return result


def update_once(
    options: UpdateOptions,
    choose: Chooser,
    *,
    emit: Callable[[str], None] = print,
    resolve_factory: Callable[[], Any] | None = None,
    prepare: Callable[[UpdateOptions, StageTimings], VerifiedPackageV2] = (
        prepare_current
    ),
    now: Callable[[], datetime] = datetime.now,
) -> dict[str, Any]:
    """Plan, ask, then update the agreed rows. Returns the report."""
    root = _regular_absolute(
        options.baseline_output.absolute(), "baseline build output", directory=True
    )
    saved = _read_saved_row_map(root)
    if (
        saved is None
        or saved.get("schemaVersion") != SCHEMA_VERSION_V2
        or saved.get("version") != 2
    ):
        raise NeedsAction("the earlier build has no row-timeline-map.json baseline")
    baseline = _load_readback_package(root)
    validate_saved_row_map(baseline.manifest, baseline.view, saved)
    if saved["timelineName"] != baseline_timeline_name(root, baseline.attestation):
        raise BuildJobError("baseline timeline name differs from the verified build")
    baseline_document = _read_json(
        baseline.root / "Builds" / baseline.manifest["buildId"] / "script-document.json"
    )
    current_document = _read_json(options.script)
    current = prepare(options, StageTimings(emit=lambda _: None))
    output = options.output.absolute()

    with exclusive_resolve_build():
        resolve = (resolve_factory or _external_resolve)()
        if (
            not resolve.IsStudio()
            or resolve.GetVersion()[:4] != native.MEASURED_VERSION
        ):
            raise NeedsAction(
                "updating in place has only been measured on Resolve Studio "
                "21.1.1 build 10; this Resolve is a different version"
            )

        def read() -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
            manager, timeline, _, _ = _current_readback_target(
                resolve,
                project_name=saved["projectName"],
                timeline_name=saved["timelineName"],
                project_uid=saved["resolveProjectId"],
                timeline_uid=saved["timelineId"],
            )
            return (
                manager,
                timeline,
                observe_current(resolve, saved, baseline.view),
                native.snapshot(timeline),
            )

        manager, timeline, observation, before = read()
        comparison = compare_three_way_rows(
            baseline.manifest,
            saved,
            baseline_document,
            current.manifest,
            current_document,
            observation,
        )
        takes = {row["id"]: row["takes"] for row in before["items"]}
        plans = planning.plan_rows(
            baseline_manifest=baseline.manifest,
            baseline_view=baseline.view,
            baseline_document=baseline_document,
            current_manifest=current.manifest,
            current_view=current.view,
            current_document=current_document,
            saved_map=saved,
            comparison=comparison,
            observation=observation,
            takes=takes,
        )
        gaps = planning.global_gaps(baseline.view, current.view, comparison)
        emit(planning.render_plan(plans, gaps))

        def finish(
            attempt: Mapping[str, Any] | None, archive: str | None, status: str
        ) -> dict[str, Any]:
            report = planning.build_report(
                plans,
                gaps,
                attempt,
                archive_name=archive,
                kept=native.READABLE if status == "updated" else (),
                not_checked=native.UNREADABLE if status == "updated" else (),
                status=status,
            )
            _publish(output / "update-report.json", report)
            emit(planning.render_report(report))
            return report

        try:
            selected = planning.choose_rows(plans, choose(plans))
        except planning.UpdatePlanError as error:
            raise NeedsAction(str(error)) from error
        if not selected:
            return finish(None, None, "unchanged")

        # He may have kept working while the plan was on screen.
        manager, timeline, observation_now, now_snapshot = read()
        if observation_now != observation or now_snapshot != before:
            raise NeedsAction(
                "the timeline changed while the plan was shown; run the update again"
            )
        project = manager.GetCurrentProject()
        frozen = planning.freeze_plan(
            plans,
            selected,
            source=str(current.manifest["document"]["contentHash"]),
            target=saved["timelineId"],
            baseline=native.fingerprint(before),
        )
        attempt = planning.start_attempt(frozen)
        _publish(output / "update-plan.json", frozen)
        _publish(output / "update-attempt.json", attempt)
        edits = [
            edit
            for plan in plans
            if plan["rowId"] in selected
            for edit in plan["edits"]
        ]
        sources = {source["id"]: source for source in current.view["sources"]}
        paths = {
            edit["sourceId"]: _package_path(
                current.root, sources[edit["sourceId"]]["path"], "replacement source"
            )
            for edit in edits
            if edit["swapPicture"]
        }
        stamps = {event["id"]: _stamp(event) for event in current.view["events"]}
        archive_name = f"{saved['timelineName']} archive {now():%Y-%m-%d %H%M%S}"

        try:
            if not manager.SaveProject():
                raise native.NativeUpdateError("Resolve could not save the project")
            archive = native.duplicate_archive(project, timeline, archive_name)
            archive_uid = archive.GetUniqueId()
            archive_before = native.snapshot(archive)
            if not native.same_content(archive_before, before):
                raise native.NativeUpdateError("the archive copy differs")
            if native.unexpected_changes(before, native.snapshot(timeline), set()):
                raise native.NativeUpdateError(
                    "making the archive changed the timeline"
                )
        except Exception as error:
            raise BuildJobError(
                "the archive copy could not be made and checked, so the "
                f"timeline was not changed ({error}). A copy named "
                f"{archive_name!r} may have been left in the project"
            ) from error

        replaced: set[str] = set()
        final: tuple[str, str] | None = None
        try:
            media = native.import_sources(
                project, f"VERA update {current.manifest['buildId'][:8]}", paths
            )
            # Handles do not survive closing the project; keep the IDs.
            media_ids = {key: item.GetMediaId() for key, item in media.items()}
            native.select(project, timeline)
            for position, row_id in enumerate(selected):
                attempt = planning.record_outcome(attempt, row_id, "uncertain")
                _publish(output / "update-attempt.json", attempt)
                items = native.live_items(timeline)
                for edit in next(p for p in plans if p["rowId"] == row_id)["edits"]:
                    item = items[edit["resolveItemId"]][2]
                    if edit["swapPicture"]:
                        native.swap_picture(
                            item,
                            media[edit["sourceId"]],
                            edit["sourceStartFrame"],
                            edit["durationFrames"],
                        )
                    native.restamp(item, edit["eventId"], stamps[edit["eventId"]])
                    replaced.add(edit["resolveItemId"])
                after = native.snapshot(timeline)
                problems = native.unexpected_changes(before, after, replaced)
                if problems:
                    raise native.NativeUpdateError("; ".join(problems))
                if position == len(selected) - 1:
                    # The last row is confirmed only after save, close and reopen.
                    final = (row_id, native.fingerprint(after))
                else:
                    attempt = planning.record_outcome(
                        attempt, row_id, "verified", after=native.fingerprint(after)
                    )
                    _publish(output / "update-attempt.json", attempt)

            project = native.save_close_reopen(
                manager, project, saved["projectName"], saved["resolveProjectId"]
            )
            timeline = native.timeline_by_uid(project, saved["timelineId"])
            archive = native.timeline_by_uid(project, archive_uid)
            archive_after = native.snapshot(archive)
            if archive_after["timelineId"] != archive_uid or native.unexpected_changes(
                archive_before, archive_after, set()
            ):
                raise native.NativeUpdateError("the archive copy changed")
            native.select(project, timeline)
            reopened = native.snapshot(timeline)
            problems = native.unexpected_changes(before, reopened, replaced)
            items = native.live_items(timeline)
            for edit in edits:
                kind, _, item = items[edit["resolveItemId"]]
                source = sources[edit["sourceId"]]
                pool_item = item.GetMediaPoolItem()
                if (
                    kind != "video"
                    or item.GetSourceStartFrame() != edit["sourceStartFrame"]
                    or item.GetDuration(False) != edit["durationFrames"]
                    or (
                        edit["swapPicture"]
                        and (
                            pool_item is None
                            or pool_item.GetMediaId() != media_ids[edit["sourceId"]]
                        )
                    )
                ):
                    problems.append(f"updated clip did not read back: {source['id']}")
            if problems or final is None:
                raise native.NativeUpdateError("; ".join(problems) or "no row applied")
            attempt = planning.record_outcome(
                attempt, final[0], "verified", after=final[1]
            )
            _publish(output / "update-attempt.json", attempt)
        except Exception as error:
            report = finish(attempt, archive_name, "uncertain")
            del report
            raise UncertainResult(
                "a change to Resolve could not be confirmed; do not run the "
                f"update again; the archive copy is {archive_name!r} ({error})"
            ) from error

        report = planning.build_report(
            plans,
            gaps,
            attempt,
            archive_name=archive_name,
            kept=native.READABLE,
            not_checked=native.UNREADABLE,
            status="updated",
        )
        if report["baselineComplete"]:
            try:
                row_map = _new_baseline_map(
                    saved, baseline.view, current, edits, native.live_items(timeline)
                )
                _publish(output / "row-timeline-map.json", row_map)
                _publish(
                    output / "timeline-update.json",
                    {
                        "schemaVersion": "vera-timeline-update/v1",
                        "buildId": current.manifest["buildId"],
                        "timelineName": saved["timelineName"],
                        "timelineId": saved["timelineId"],
                        "previousBuildId": saved["buildId"],
                        "archiveTimeline": archive_name,
                    },
                )
            except Exception as error:
                gaps.append(
                    "The rows were updated, but a whole-timeline baseline could "
                    f"not be written ({error}); the earlier baseline stays in force."
                )
        return finish(attempt, archive_name, "updated")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--baseline-output",
        type=Path,
        required=True,
        help="results folder of the build (or update) the open timeline came from",
    )
    command.add_argument("--script", type=Path, required=True, help="current v2 script")
    command.add_argument("--inputs", type=Path, help="prepared inputs for the script")
    command.add_argument(
        "--output", type=Path, required=True, help="new, unused results folder"
    )
    command.add_argument("--package-cache", type=Path, metavar="FOLDER")
    go = command.add_mutually_exclusive_group()
    go.add_argument(
        "--rows", nargs="+", metavar="ROW", help="update these row numbers or row IDs"
    )
    go.add_argument(
        "--all-safe-rows",
        action="store_true",
        help="update every row that is safe (never a row in conflict)",
    )
    return command


def _ask(plans: Sequence[Mapping[str, Any]]) -> Choice:
    if not sys.stdin.isatty() or all(plan["refusal"] for plan in plans):
        return None
    answer = input(
        'Type "all safe rows", or row numbers separated by commas, '
        "or press Return to change nothing: "
    ).strip()
    if not answer:
        return None
    if answer.lower() == "all safe rows":
        return "safe"
    return [part for part in answer.replace(",", " ").split() if part]


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    choose: Chooser = _ask
    if args.all_safe_rows:
        choose = lambda _: "safe"  # noqa: E731
    elif args.rows:
        choose = lambda _: list(args.rows)  # noqa: E731
    options = UpdateOptions(
        baseline_output=args.baseline_output,
        script=args.script,
        output=args.output,
        inputs=args.inputs,
        package_cache=args.package_cache,
    )
    try:
        report = update_once(options, choose)
    except UncertainResult as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 3
    except (BuildJobError, NeedsAction) as error:
        print(f"Update refused, nothing changed: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"Update stopped: {error}", file=sys.stderr)
        return 2
    return 0 if report["status"] in {"updated", "unchanged"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
