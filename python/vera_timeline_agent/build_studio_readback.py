"""Connected, read-only confirmation of a reopened frozen still build."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .build_jobs import NeedsAction
from .build_stage_receipt import hash_file
from .build_timeline_once import _external_resolve, exclusive_resolve_build
from .row_timeline_map import compare_reopened_row_map
from .workflow_v2 import (
    _assert_readback_target,
    _current_readback_target,
    _fractional_source_range_matches,
    _frame_rate,
    _native_otio_scaling,
    _package_path,
    _property_equal,
    _stamp,
    _verify_native_otio_plan,
    load_verified_package_v2,
    observe_current_timeline_v2,
)
from .workflow_v2_parent import status


def _clips(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    tracks = document["tracks"]["children"]
    return [
        child
        for track in tracks
        for child in track["children"]
        if child.get("OTIO_SCHEMA") == "Clip.2"
    ]


def _zoom_keys(clip: Mapping[str, Any]) -> dict[str, tuple[int, list[Any]]]:
    effects = [
        effect["metadata"]["Resolve_OTIO"]
        for effect in clip["effects"]
        if effect.get("metadata", {}).get("Resolve_OTIO", {}).get("Type") == 59
    ]
    if len(effects) != 1 or effects[0].get("Enabled") is not True:
        raise NeedsAction("exported native Dynamic Zoom is missing or disabled")
    parameters = effects[0].get("Parameters", [])
    result: dict[str, tuple[int, list[Any]]] = {}
    for name in ("dynamicZoomCenter", "dynamicZoomScale"):
        matches = [p for p in parameters if p.get("Parameter ID") == name]
        if len(matches) != 1 or not isinstance(matches[0].get("Key Frames"), Mapping):
            raise NeedsAction("exported native Dynamic Zoom endpoints are missing")
        frames = matches[0]["Key Frames"]
        if len(frames) != 2:
            raise NeedsAction("exported native Dynamic Zoom endpoints differ")
        try:
            keys = sorted(frames, key=int)
            result[name] = (
                int(keys[1]) - int(keys[0]),
                [frames[key]["Value"] for key in keys],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise NeedsAction(
                "exported native Dynamic Zoom endpoints are invalid"
            ) from error
    return result


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(right, list):
        return (
            isinstance(left, list)
            and len(left) == len(right)
            and all(_same_value(a, b) for a, b in zip(left, right, strict=True))
        )
    return _property_equal(left, right)


def _exported_motion_matches(
    resolve: Any, timeline: Any, package: Any, event_id: str, source: Path
) -> None:
    signed = json.loads(_verify_native_otio_plan(package).read_bytes())
    matches = [
        clip
        for clip in _clips(signed)
        if clip.get("metadata", {}).get("vera", {}).get("event_id") == event_id
    ]
    if len(matches) != 1:
        raise NeedsAction("signed still event is not unique")
    expected = _zoom_keys(matches[0])
    with tempfile.TemporaryDirectory(
        prefix="vera-still-readback-", dir="/private/tmp"
    ) as directory:
        export = Path(directory) / "timeline.otio"
        if (
            timeline.Export(str(export), resolve.EXPORT_OTIO, resolve.EXPORT_NONE)
            is not True
        ):
            raise NeedsAction(
                "Resolve could not export reopened timeline for inspection"
            )
        document = json.loads(export.read_bytes())
        found = []
        for clip in _clips(document):
            references = clip.get("media_references", {})
            reference = references.get(clip.get("active_media_reference_key"), {})
            location = reference.get("target_url")
            if not isinstance(location, str):
                continue
            parsed = urlparse(location)
            if parsed.scheme not in ("", "file") or parsed.netloc not in (
                "",
                "localhost",
            ):
                continue
            path = Path(unquote(parsed.path)).expanduser()
            if path.is_absolute() and path.resolve() == source:
                found.append(clip)
        if len(found) != 1:
            raise NeedsAction("exported still source is missing or ambiguous")
        actual = _zoom_keys(found[0])
        if not all(
            actual[name][0] == span and _same_value(actual[name][1], values)
            for name, (span, values) in expected.items()
        ):
            raise NeedsAction("reopened native Dynamic Zoom endpoints differ")


class ConnectedStillReadback:
    """Reinspect the current target, bound to the successful parent and package.

    This deliberately supports the qualified fractional-rate still case only.
    It does not select a project, retry a build, or infer success from a file.
    """

    def __init__(
        self,
        request_path: Path,
        request_sha256: str,
        request_id: str,
        *,
        resolve_app: Path | None = None,
        resolve_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.request_path = request_path
        self.request_sha256 = request_sha256
        self.request_id = request_id
        self.resolve_app = resolve_app
        self.resolve_factory = resolve_factory

    def __call__(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        if request_id != self.request_id:
            raise NeedsAction("readback request identity changed")
        parent = status(self.request_path, self.request_sha256)
        result = parent.get("result")
        package = load_verified_package_v2(attestation, digest)
        target = package.attestation
        if (
            parent.get("state") != "terminal"
            or parent.get("verified") is not True
            or not isinstance(result, Mapping)
            or result.get("status") != "verified"
            or result.get("verified") is not True
            or result.get("discrepancies") != []
            or result.get("attestationSha256") != digest
            or result.get("buildId") != target["buildId"]
            or result.get("projectName") != target["projectName"]
            or result.get("timelineName") != target["timelineName"]
        ):
            raise NeedsAction("parent result does not establish this reopened target")
        saved = result.get("rowTimelineMap")
        if not isinstance(saved, Mapping):
            raise NeedsAction("parent did not retain reopened target identities")
        project_uid, timeline_uid = (
            saved.get("resolveProjectId"),
            saved.get("timelineId"),
        )
        if not all(
            isinstance(x, str) and x.strip() for x in (project_uid, timeline_uid)
        ):
            raise NeedsAction("reopened target identities are missing")
        view, manifest = package.view, package.manifest
        if _frame_rate(view["timeline"]) != (24000, 1001):
            raise NeedsAction("this still readback requires exact 24000/1001")
        with exclusive_resolve_build():
            resolve = (
                self.resolve_factory()
                if self.resolve_factory
                else _external_resolve(self.resolve_app)
            )
            observed = observe_current_timeline_v2(
                resolve,
                view,
                project_name=target["projectName"],
                timeline_name=target["timelineName"],
                project_uid=project_uid,
                timeline_uid=timeline_uid,
                transition_plans=manifest.get("transitions", ()),
            )
            compare_reopened_row_map(
                manifest,
                view,
                observed["observed"],
                project_name=observed["projectName"],
                resolve_project_id=observed["resolveProjectId"],
                timeline_name=observed["timelineName"],
                timeline_id=observed["timelineId"],
                saved_map=saved,
            )
            manager, timeline, project_id, timeline_id = _current_readback_target(
                resolve,
                project_name=target["projectName"],
                timeline_name=target["timelineName"],
                project_uid=project_uid,
                timeline_uid=timeline_uid,
            )
            sources = {source["id"]: source for source in view["sources"]}
            manifest_sources = {source["id"]: source for source in manifest["sources"]}
            bindings = {
                binding["requirementKey"]: binding
                for binding in manifest["preparationBindings"]
            }
            tracks = {track["id"]: track for track in view["tracks"]}
            still_count = 0
            for event in view["events"]:
                source = sources.get(event.get("sourceId"), {})
                picture = event.get("pictureTreatment")
                motion = (
                    picture.get("imageMotion") if isinstance(picture, Mapping) else None
                )
                if source.get("kind") != "still" or not isinstance(motion, Mapping):
                    continue
                if motion.get("mode") != "native_dynamic_zoom":
                    continue
                still_count += 1
                track = tracks[event["trackId"]]
                items = timeline.GetItemListInTrack(track["kind"], track["index"])
                matches = [
                    item
                    for item in items
                    if item.GetMarkerCustomData(0) == _stamp(event)
                ]
                if len(matches) != 1:
                    raise NeedsAction("native still event identity differs")
                item = matches[0]
                media = item.GetMediaPoolItem()
                expected_path = _package_path(
                    package.root, source["path"], "native still source"
                )
                media_path = (
                    media.GetClipProperty("File Path") if media is not None else None
                )
                if (
                    not isinstance(media_path, str)
                    or Path(media_path).resolve() != expected_path
                ):
                    raise NeedsAction(
                        "native still source differs from attested package"
                    )
                hash_file(expected_path)
                properties = item.GetProperties()
                if (
                    not isinstance(properties, Mapping)
                    or not _property_equal(properties.get("DynamicZoomEnabled"), True)
                    or not _property_equal(
                        properties.get("Scaling"),
                        _native_otio_scaling(picture.get("framingPolicy")),
                    )
                ):
                    raise NeedsAction("native still zoom or framing differs")
                times = {
                    name: getattr(item, name)()
                    for name in ("GetSourceStartTime", "GetSourceEndTime")
                    if callable(getattr(item, name, None))
                }
                if not _fractional_source_range_matches(
                    event=event,
                    source=source,
                    manifest_source=manifest_sources[event["sourceId"]],
                    preparation_bindings=bindings,
                    timeline=view["timeline"],
                    actual_start=item.GetSourceStartFrame(),
                    actual_end=item.GetSourceEndFrame(),
                    source_times=times,
                    speed=item.GetSpeed(),
                    media_properties=media.GetClipProperty(),
                    record_duration=event["recordRange"]["durationFrames"],
                ):
                    raise NeedsAction("native still source range differs")
                _assert_readback_target(manager, project_id, timeline_id)
                _exported_motion_matches(
                    resolve, timeline, package, event["id"], expected_path
                )
                _assert_readback_target(manager, project_id, timeline_id)
            if still_count != 1:
                raise NeedsAction("exactly one qualified moving still is required")
            if load_verified_package_v2(attestation, digest) != package:
                raise NeedsAction("attested package changed during readback")
        return {
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "buildId": target["buildId"],
            "attestationSha256": digest,
            "projectName": target["projectName"],
            "timelineName": target["timelineName"],
        }
