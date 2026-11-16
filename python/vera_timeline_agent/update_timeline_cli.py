"""Update only the changed rows of the open, hand-finished VERA timeline.

Shows what it would do and changes nothing until rows are agreed. Before any
change it duplicates the timeline and keeps the copy as the archive.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import timeline_retime_native as retime
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
from .observe_timeline_cli import observe_current
from .package_cache import default_cache_root
from .row_timeline_map import (
    make_row_timeline_map,
    observe_item_details,
)
from .three_way_compare import compare_three_way_rows
from .timeline_baseline import (
    RECORD_NAME,
    RECORD_SCHEMA,
    Baseline,
    compose,
    load_baseline,
)
from .workflow_v2 import (
    VerifiedPackageV2,
    _current_readback_target,
    _package_path,
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
    resolve_app: Path | None = None


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


def _write_new_baseline(
    output: Path,
    baseline: Baseline,
    current: VerifiedPackageV2,
    updated_rows: Sequence[str],
    edits: Sequence[Mapping[str, Any]],
    items: Mapping[str, tuple[str, int, Any]],
    archive_name: str,
) -> None:
    """Record the timeline as the earlier baseline with the updated rows swapped in.

    The folder is then loaded back exactly as the next command will load it.
    """
    saved = baseline.saved
    manifest, view = compose(
        baseline.manifest, baseline.view, current.manifest, current.view, updated_rows
    )
    uid_by_event = {
        item["eventId"]: item["resolveItemId"]
        for row in saved["rows"]
        for item in row["items"]
    }
    for edit in edits:
        uid_by_event.pop(edit["previousEventId"], None)
        uid_by_event[edit["eventId"]] = edit["resolveItemId"]
    observed = []
    for event in view["events"]:
        uid = uid_by_event.get(event["id"])
        if uid is None or uid not in items:
            raise ValueError("a clip of the updated timeline has no Resolve item")
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
    row_map = make_row_timeline_map(
        manifest,
        view,
        observed,
        project_name=saved["projectName"],
        resolve_project_id=saved["resolveProjectId"],
        timeline_name=saved["timelineName"],
        timeline_id=saved["timelineId"],
        version=2,
    )
    _publish(output / "row-timeline-map.json", row_map)
    _publish(
        output / RECORD_NAME,
        {
            "schemaVersion": RECORD_SCHEMA,
            "buildId": current.manifest["buildId"],
            "previousBaseline": str(baseline.root),
            "updatedRows": list(updated_rows),
            "timelineName": saved["timelineName"],
            "timelineId": saved["timelineId"],
            "archiveTimeline": archive_name,
        },
    )
    load_baseline(output)


def _batch(
    edits: Sequence[Mapping[str, Any]], timeline: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a length change's edits into clip operations and transitions."""
    ops: list[dict[str, Any]] = []
    transition_edits: list[dict[str, Any]] = []
    for edit in edits:
        if edit["route"] == planning.ROUTE_TRANSITION:
            transition_edits.append(dict(edit))
        elif edit["route"] == planning.ROUTE_RETIME:
            ops.append(dict(edit))
        else:  # A same-length swap is a retime that goes nowhere.
            item = native.live_items(timeline)[edit["resolveItemId"]][2]
            ops.append(
                {
                    **edit,
                    "startFrame": item.GetStart(False),
                    "previousStartFrame": item.GetStart(False),
                    "previousDurationFrames": edit["durationFrames"],
                    "replaceAudio": False,
                }
            )
    return ops, transition_edits


def _write_full_baseline(
    output: Path,
    baseline: Baseline,
    current: VerifiedPackageV2,
    uid_by_event: Mapping[str, str],
    items: Mapping[str, tuple[str, int, Any]],
    archive_name: str,
) -> None:
    """After a length change the whole timeline matches the current build."""
    saved = baseline.saved
    observed = []
    for event in current.view["events"]:
        uid = uid_by_event.get(event["id"])
        if uid is None or uid not in items:
            raise ValueError("a clip of the updated timeline has no Resolve item")
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
    row_map = make_row_timeline_map(
        current.manifest,
        current.view,
        observed,
        project_name=saved["projectName"],
        resolve_project_id=saved["resolveProjectId"],
        timeline_name=saved["timelineName"],
        timeline_id=saved["timelineId"],
        version=2,
    )
    _publish(output / "row-timeline-map.json", row_map)
    _publish(
        output / RECORD_NAME,
        {
            "schemaVersion": RECORD_SCHEMA,
            "buildId": current.manifest["buildId"],
            "mode": "full",
            "previousBaseline": str(baseline.root),
            "timelineName": saved["timelineName"],
            "timelineId": saved["timelineId"],
            "archiveTimeline": archive_name,
        },
    )
    load_baseline(output)


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
    try:
        baseline = load_baseline(options.baseline_output)
    except ValueError as error:
        raise NeedsAction(
            f"the earlier build cannot be used as a baseline: {error}"
        ) from error
    saved, baseline_document = baseline.saved, baseline.document
    current_document = _read_json(options.script)
    current = prepare(options, StageTimings(emit=lambda _: None))
    output = options.output.absolute()

    with exclusive_resolve_build():
        resolve = (
            resolve_factory()
            if resolve_factory
            else _external_resolve(options.resolve_app)
        )
        version = resolve.GetVersion()[:4]
        if not resolve.IsStudio() or version not in (
            native.MEASURED_VERSION,
            retime.RETIME_VERSION,
        ):
            raise NeedsAction(
                "updating in place has only been measured on Resolve Studio "
                "21.1.1 build 10 and 21.2.0 build 6; this Resolve is a "
                "different version"
            )
        can_retime = version == retime.RETIME_VERSION

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
            can_retime=can_retime,
        )
        grouped = any(
            plan["group"] == planning.ROUTE_RETIME and plan["refusal"] is None
            for plan in plans
        )
        if grouped:
            # Show a problem with the live timeline in the plan, not after he
            # has agreed to it. This reads Resolve and changes nothing.
            try:
                all_ops, all_transitions = _batch(
                    [edit for plan in plans for edit in plan["edits"]], timeline
                )
                retime.precheck(
                    timeline,
                    all_ops,
                    planning.editor_moves(observation, comparison)[0],
                    all_transitions,
                    current.view.get("markers", []),
                    baseline.view.get("markers", []),
                )
            except retime.RetimePrecheckError as error:
                grouped = False
                for plan in plans:
                    if plan["refusal"] is None:
                        plan["refusal"] = (
                            "The timeline's length changes, so every changed "
                            "row has to be updated together, and that is not "
                            f"possible: {error}."
                        )
                        plan["edits"] = []
        # A length change brings the whole timeline to the script, markers too.
        gaps = (
            []
            if grouped
            else planning.global_gaps(baseline.view, current.view, comparison)
        )
        emit(planning.render_plan(plans, gaps))
        # The same music warnings the build prints, so a short file is not missed.
        report_path = output / "build-report.json"
        if report_path.is_file():
            for diagnostic in _read_json(report_path).get("diagnostics", []):
                if diagnostic.get("code") in {
                    "MUSIC_FILE_MISSING",
                    "MUSIC_SOURCE_SHORTER",
                    "MUSIC_SPAN_INVALID",
                    "MUSIC_SETTINGS_UNSUPPORTED",
                }:
                    emit(f"Music warning: {diagnostic.get('message')}")

        def finish(
            attempt: Mapping[str, Any] | None, archive: str | None, status: str
        ) -> dict[str, Any]:
            report = planning.build_report(
                plans,
                gaps,
                attempt,
                archive_name=archive,
                kept=native.READABLE if status == "updated" else (),
                not_checked=(
                    (
                        *native.UNREADABLE,
                        *(
                            f"{fact} (Resolve did not return this for every clip)"
                            for fact in native.unread_facts(before)
                        ),
                    )
                    if status == "updated"
                    else ()
                ),
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
            if edit.get("swapPicture") or edit.get("replaceAudio")
        }
        stamps = {event["id"]: _stamp(event) for event in current.view["events"]}
        archive_name = f"{saved['timelineName']} archive {now():%Y-%m-%d %H%M%S}"
        retiming = grouped and any(
            plan["group"] == planning.ROUTE_RETIME
            for plan in plans
            if plan["rowId"] in selected
        )
        ops: list[dict[str, Any]] = []
        transition_edits: list[dict[str, Any]] = []
        editor: dict[str, int] = {}
        checked: dict[str, Any] = {"expect": {}, "bonds": [], "end": 0}
        if retiming:
            ops, transition_edits = _batch(edits, timeline)
            editor = planning.editor_moves(observation, comparison)[0]
            try:
                checked = retime.precheck(
                    timeline,
                    ops,
                    editor,
                    transition_edits,
                    current.view.get("markers", []),
                    baseline.view.get("markers", []),
                )
            except retime.RetimePrecheckError as error:
                raise NeedsAction(f"{error}; nothing was changed") from error

        stamp = archive_name.rsplit(" archive ", 1)[1]
        if archive_name in native.timeline_names(project) or not manager.SaveProject():
            raise BuildJobError(
                "Resolve could not save the project or the archive name is "
                "already in use; wait a second and run the update again"
            )
        try:
            archive = native.duplicate_archive(project, timeline, archive_name)
            archive_uid = archive.GetUniqueId()
            archive_before = native.snapshot(archive)
            if not native.same_content(archive_before, before):
                raise native.NativeUpdateError("the archive copy differs")
            if native.unexpected_changes(before, native.snapshot(timeline), {}):
                raise native.NativeUpdateError(
                    "making the archive changed the timeline"
                )
            media = native.import_sources(project, f"VERA update {stamp}", paths)
            # Handles do not survive closing the project; keep the IDs.
            media_ids = {key: item.GetMediaId() for key, item in media.items()}
            native.select(project, timeline)
        except Exception as error:
            # VERA has not edited a clip, but Resolve is not as it was found.
            raise UncertainResult(
                "the archive copy or the new pictures could not be set up "
                f"({error}). VERA did not edit any clip. Check in Resolve that "
                f"the open timeline is the original, not {archive_name!r}, "
                "before working on or running the update again"
            ) from error

        if retiming:
            window = current.view["timeline"]
            # A clip he added may run past the script's last frame.
            bounds = [
                window["startFrame"],
                max(window["startFrame"] + window["durationFrames"], checked["end"]),
            ]
            uid_by_event = {
                item["eventId"]: item["resolveItemId"]
                for row in saved["rows"]
                for item in row["items"]
            }
            for op in ops:
                uid_by_event.pop(op["previousEventId"], None)
                uid_by_event[op["eventId"]] = op["resolveItemId"]
            try:
                attempt = planning.record_outcome(
                    attempt, planning.LENGTH_CHANGE, "uncertain"
                )
                _publish(output / "update-attempt.json", attempt)
                made = retime.apply(
                    project,
                    timeline,
                    ops,
                    editor,
                    transition_edits,
                    media=media,
                    stamps=stamps,
                    uid_by_event=uid_by_event,
                    old_markers=baseline.view.get("markers", []),
                    new_markers=current.view.get("markers", []),
                    bonds=checked["bonds"],
                )
                for old_uid, new_uid in made["created"].items():
                    for event_id, uid in uid_by_event.items():
                        if uid == old_uid:
                            uid_by_event[event_id] = new_uid

                def verify(target: Any) -> dict[str, Any]:
                    seen = native.snapshot(target)
                    problems = retime.check(
                        before,
                        seen,
                        checked["expect"],
                        created=made["created"],
                        transitions=made["transitions"],
                        bounds=bounds,
                        required_transitions=[
                            (edit["startFrame"], edit["endFrame"])
                            for edit in transition_edits
                        ],
                    )
                    live = native.live_items(target)
                    for op in ops:
                        item = live[uid_by_event[op["eventId"]]][2]
                        pool_item = item.GetMediaPoolItem()
                        if item.GetSourceStartFrame() != op["sourceStartFrame"] or (
                            (op["swapPicture"] or op["replaceAudio"])
                            and (
                                pool_item is None
                                or pool_item.GetMediaId() != media_ids[op["sourceId"]]
                            )
                        ):
                            problems.append(
                                f"updated clip did not read back: {op['sourceId']}"
                            )
                    if problems:
                        raise native.NativeUpdateError("; ".join(problems))
                    return seen

                verify(timeline)
                project = native.save_close_reopen(
                    manager, project, saved["projectName"], saved["resolveProjectId"]
                )
                timeline = native.timeline_by_uid(project, saved["timelineId"])
                archive = native.timeline_by_uid(project, archive_uid)
                archive_after = native.snapshot(archive)
                if archive_after[
                    "timelineId"
                ] != archive_uid or native.unexpected_changes(
                    archive_before, archive_after, {}
                ):
                    raise native.NativeUpdateError("the archive copy changed")
                native.select(project, timeline)
                final_print = native.fingerprint(verify(timeline))
                attempt = planning.record_outcome(
                    attempt, planning.LENGTH_CHANGE, "verified", after=final_print
                )
                _publish(output / "update-attempt.json", attempt)
            except Exception as error:
                # The stop itself must still be reported if the report cannot be saved.
                with contextlib.suppress(Exception):
                    finish(attempt, archive_name, "uncertain")
                raise UncertainResult(
                    "a change to Resolve could not be confirmed; do not run the "
                    f"update again; the archive copy is {archive_name!r} ({error})"
                ) from error
            try:
                _write_full_baseline(
                    output,
                    baseline,
                    current,
                    uid_by_event,
                    native.live_items(timeline),
                    archive_name,
                )
            except Exception as error:
                for name in ("row-timeline-map.json", RECORD_NAME):
                    (output / name).unlink(missing_ok=True)
                gaps.append(
                    "The rows were updated, but the new baseline could not be "
                    f"written ({error}). Build the timeline afresh before the "
                    "next update."
                )
            return finish(attempt, archive_name, "updated")

        replaced: dict[str, bool] = {}
        final: tuple[str, str] | None = None
        try:
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
                    replaced[edit["resolveItemId"]] = edit["swapPicture"]
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
                archive_before, archive_after, {}
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
            # The stop itself must still be reported if the report cannot be saved.
            with contextlib.suppress(Exception):
                finish(attempt, archive_name, "uncertain")
            raise UncertainResult(
                "a change to Resolve could not be confirmed; do not run the "
                f"update again; the archive copy is {archive_name!r} ({error})"
            ) from error

        try:
            _write_new_baseline(
                output,
                baseline,
                current,
                selected,
                edits,
                native.live_items(timeline),
                archive_name,
            )
        except Exception as error:
            for name in ("row-timeline-map.json", RECORD_NAME):
                (output / name).unlink(missing_ok=True)
            gaps.append(
                "The rows were updated, but the new baseline could not be "
                f"written ({error}). Build the timeline afresh before the next update."
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
    command.add_argument(
        "--resolve-app",
        type=Path,
        metavar="APP",
        help="the Resolve Studio .app to connect to, when it is not at the usual path",
    )
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
        resolve_app=args.resolve_app,
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
