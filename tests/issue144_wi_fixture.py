"""Explicit fake native state populated by actual accepted assembly calls.

Getters read stored state, never the manifest supplied to an inspector/capture.
Operator edits mutate that state once. Complete mixer/support evidence remains
explicitly synthetic; this module never connects to an application.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from issue144_composition_fixture import CompositionBoundary
from test_issue144_native_build import InjectedStudio, _local
from test_issue144_wi import Item, Media
from vera_timeline_agent import roundtrip_wi as wi
from vera_timeline_agent.roundtrip_build import ROOT, PreparedBuild, load_operator_json
from vera_timeline_agent.roundtrip_native import NativeStages

Json = dict[str, Any]
VERSION: list[Any] = [21, 0, 4, 5, ""]
REGISTRY: dict[str, Json] = {}


class Source(Media):
    def __init__(self, path: Path, identity: str) -> None:
        super().__init__(path)
        self.identity = identity

    def GetUniqueId(self) -> str:
        return self.identity


class GraphStudio(InjectedStudio):
    def __init__(self, build: PreparedBuild) -> None:
        super().__init__(build)
        self.project_name = self.timeline_name = ""
        self.settings: dict[str, str] = {}
        self.tracks: list[Json] = []
        self.items: dict[str, list[Item]] = {}
        self.markers: Json = {}
        self.controls: Json = {}
        self.link_calls = 0
        self.linked = self.edited = False

    def create_project(self, name: str) -> None:
        super().create_project(name)
        self.project_name = name

    def configure_project(self, settings: Mapping[str, str]) -> None:
        self.settings = dict(settings)

    def create_timeline(self, name: str) -> None:
        self.timeline_name = name

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        self.tracks = [dict(t) for t in tracks]
        self.items = {t["id"]: [] for t in tracks}

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        for index, event in enumerate(events):
            item = Item(self.sources[event["sourceId"]])
            item.uid = f"item-{index}"
            item.start = event["recordRange"]["startFrame"]
            item.duration = event["recordRange"]["durationFrames"]
            item.source = event["sourceRange"]["startFrame"]
            item.media = Source(
                self.sources[event["sourceId"]], f"media-{event['sourceId']}"
            )
            self.items[event["trackId"]].append(item)
            if event["kind"] == "audio":
                key = event["trackId"] + "/" + item.media.GetUniqueId()
                self.controls[key] = {
                    "mediaUid": item.media.GetUniqueId(),
                    "trackId": event["trackId"],
                    "controls": {
                        "enabled": True,
                        "mute": False,
                        "solo": False,
                        "effects": [],
                        "sends": [],
                        "destination": "stereo-program",
                        "gainDb": 0,
                        "pan": 0,
                    },
                }

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        self.markers[marker["frame"]] = {
            "name": marker["name"],
            "note": marker["note"],
            "color": marker["color"],
            "duration": 1,
            "customData": custom_data,
        }

    # This object provides explicitly fake Resolve/project/timeline handles.
    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[Any]:
        return VERSION

    def GetProjectManager(self) -> GraphStudio:
        return self

    def GetCurrentProject(self) -> GraphStudio:
        return self

    def GetCurrentTimeline(self) -> GraphStudio:
        return self

    def GetUniqueId(self) -> str:
        return "native-" + self.build.snapshot_id

    def GetName(self) -> str:
        # Project and timeline names require distinct explicit handles below.
        return self.timeline_name

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return max(
            item.start + item.duration
            for items in self.items.values()
            for item in items
        )

    def GetSetting(self, key: str) -> str | None:
        return self.settings.get(key)

    def GetTrackCount(self, kind: str) -> int:
        return max((t["index"] for t in self.tracks if t["kind"] == kind), default=0)

    def GetTrackName(self, kind: str, index: int) -> str:
        return next(
            (
                str(t["name"])
                for t in self.tracks
                if t["kind"] == kind and t["index"] == index
            ),
            f"{kind.title()} {index}",
        )

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        track = next(
            (t for t in self.tracks if t["kind"] == kind and t["index"] == index), None
        )
        return self.items[track["id"]] if track is not None else []

    def GetMarkers(self) -> Json:
        return self.markers

    def SetClipsLinked(self, items: list[Item], linked: bool) -> bool:
        assert linked and len(items) == 2
        self.link_calls += 1
        items[0].links, items[1].links = [items[1]], [items[0]]
        return True


class ProjectHandle:
    def __init__(self, studio: GraphStudio) -> None:
        self.studio = studio

    def GetUniqueId(self) -> str:
        return "project-" + self.studio.build.snapshot_id

    def GetName(self) -> str:
        return self.studio.project_name

    def GetCurrentTimeline(self) -> GraphStudio:
        return self.studio


class ResolveHandle:
    def __init__(self, studio: GraphStudio) -> None:
        self.studio = studio

    def GetProductName(self) -> str:
        return self.studio.GetProductName()

    def GetVersion(self) -> list[Any]:
        return VERSION

    def GetProjectManager(self) -> ResolveHandle:
        return self

    def GetCurrentProject(self) -> ProjectHandle:
        return ProjectHandle(self.studio)


class WireBoundary(CompositionBoundary):
    def __init__(self, row_id: str, move_id: str, trim_id: str) -> None:
        super().__init__(row_id, move_id, trim_id)
        self.render_calls: list[str] = []

    def native(self, build: PreparedBuild) -> NativeStages:
        if not hasattr(self, "proof_root"):
            self.proof_root = build.root
        if build.snapshot_id not in self.studios:
            self.studios[build.snapshot_id] = GraphStudio(build)
        studio = self.studios[build.snapshot_id]
        assert isinstance(studio, GraphStudio)

        def inspect(package: Path, manifest: Json) -> Json:
            return wi.inspect_native(
                ResolveHandle(studio),
                manifest,
                package_root=package,
                version=VERSION,
                project_uid=ProjectHandle(studio).GetUniqueId(),
                timeline_uid=studio.GetUniqueId(),
            )

        return NativeStages(
            build,
            adapter_factory=lambda _: studio,
            local_facts=_local(),
            inspector=inspect,
        )

    def capture(self, request: Json) -> Json:
        self.requests.append(request)
        manifest = load_operator_json(Path(request["manifestPath"]))
        studio = next(
            s
            for s in self.studios.values()
            if s.build.manifest_path == Path(request["manifestPath"])
        )
        assert isinstance(studio, GraphStudio)
        resolve = ResolveHandle(studio)
        kwargs: Json = {
            "proof_root": self.proof_root,
            "source_root": ROOT,
            "version": VERSION,
            "code_hash": wi.file_hash(Path(wi.__file__)),
        }
        identity = request["expectedIdentity"]
        if not studio.linked:
            for index, authored in enumerate((self.move_id, self.trim_id, self.row_id)):
                events = [
                    e
                    for e in manifest["events"]
                    if e["provenance"]["authoringId"] == authored
                ]
                if authored == self.row_id:
                    narr = next(e for e in events if e["kind"] == "audio")
                    events = [
                        narr,
                        next(
                            e
                            for e in manifest["events"]
                            if e["kind"] == "video"
                            and e["recordRange"] == narr["recordRange"]
                            and e["provenance"]["blockId"] == self.row_id
                        ),
                    ]
                assert len(events) == 2
                pair = [identity["occurrences"][e["id"]]["itemUid"] for e in events]
                before = wi.read_native(
                    resolve,
                    manifest,
                    package_root=Path(request["packageRoot"]),
                    version=VERSION,
                    project_uid=identity["projectUid"],
                    timeline_uid=identity["timelineUid"],
                )
                operation = {
                    **request,
                    "schemaVersion": "issue-144-wi-action/v1",
                    "nonce": f"pair-{index}",
                    "action": "link",
                    "parameters": {"pair": pair},
                    "expectedObservationHash": wi.digest(wi.encoded(before)),
                }
                path = (
                    self.proof_root
                    / "wi-setup"
                    / manifest["buildId"]
                    / operation["nonce"]
                    / "request.json"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                wi.immutable(path, operation)
                assert (
                    wi.perform(
                        resolve, path, request_hash=wi.file_hash(path), **kwargs
                    )["status"]
                    == "linked"
                )
            studio.linked = True
        if self.edit and studio.build.root == self.proof_root and not studio.edited:
            self._edits(studio, manifest, identity)
            studio.edited = True
        basis = {k: v for k, v in request.items() if k != "nonce"}
        path = (
            self.proof_root
            / "captures"
            / wi.digest(wi.encoded(basis))[7:]
            / request["nonce"]
            / "request.json"
        )
        return wi.capture(
            resolve,
            path,
            request_hash=wi.file_hash(path),
            audio_controls=lambda _r, _raw: {
                "programControls": {"gainDb": 0, "effects": [], "limiter": False},
                "audioControls": list(studio.controls.values()),
            },
            **kwargs,
        )

    def write_render(self, path: Path, raw: bytes, observation: Json) -> None:
        # The independent calibration is still an explicit synthetic fixture.
        # The current full-program render exercises the real WI queue/inspect
        # seam, with a fake renderer producing this known complete PCM fixture.
        if path.name == "reference.wav":
            super().write_render(path, raw, observation)
            return
        request = self.requests[-1]
        manifest = load_operator_json(Path(request["manifestPath"]))
        studio = next(
            s
            for s in self.studios.values()
            if s.build.manifest_path == Path(request["manifestPath"])
        )
        assert isinstance(studio, GraphStudio)
        identity = request["expectedIdentity"]
        resolve = ResolveHandle(studio)
        before = wi.read_native(
            resolve,
            manifest,
            package_root=Path(request["packageRoot"]),
            version=VERSION,
            project_uid=identity["projectUid"],
            timeline_uid=identity["timelineUid"],
        )
        nonce = "render-" + wi.digest(str(path).encode())[7:]
        operation = {
            **request,
            "schemaVersion": "issue-144-wi-action/v1",
            "nonce": nonce,
            "action": "render",
            "expectedObservationHash": wi.digest(wi.encoded(before)),
            "parameters": {
                "outputPath": str(path),
                "settings": {
                    "format": "wav",
                    "scope": "full-program",
                    "sampleRate": 48000,
                    "channels": 2,
                    "sampleWidth": 3,
                    "startFrame": 0,
                    "durationFrames": manifest["timeline"]["durationFrames"],
                },
            },
        }
        request_path = self.proof_root / "wi-render-requests" / nonce / "request.json"
        wi.immutable(request_path, operation)

        def renderer(
            _resolve: Any, action: str, parameters: Json, job: Json | None
        ) -> Json:
            self.render_calls.append(action)
            if action == "queue":
                wi.exclusive(path, raw)
            return {
                "jobId": nonce,
                "projectUid": identity["projectUid"],
                "timelineUid": identity["timelineUid"],
                **parameters,
                "state": "queued" if action == "queue" else "complete",
            }

        kwargs: Json = {
            "proof_root": self.proof_root,
            "source_root": ROOT,
            "version": VERSION,
            "code_hash": wi.file_hash(Path(wi.__file__)),
            "request_hash": wi.file_hash(request_path),
            "render_boundary": renderer,
        }
        queued = wi.perform(resolve, request_path, **kwargs)
        assert queued["status"] == "queued"
        complete = wi.perform(resolve, request_path, inspect_render=True, **kwargs)
        assert complete["status"] == "complete" and complete["outputHash"] == wi.digest(
            raw
        )

    def _edits(self, studio: GraphStudio, manifest: Json, identity: Json) -> None:
        by_uid = {i.uid: i for items in studio.items.values() for i in items}
        for event in manifest["events"]:
            authored = event["provenance"]["authoringId"]
            item = by_uid[identity["occurrences"][event["id"]]["itemUid"]]
            if authored == self.move_id:
                item.start += 25
            elif authored == self.trim_id:
                item.duration -= 25
        narr = next(
            e
            for e in manifest["events"]
            if e["kind"] == "audio" and e["provenance"]["authoringId"] == self.row_id
        )
        primary = by_uid[identity["occurrences"][narr["id"]]["itemUid"]]
        pair = [primary, primary.links[0]]
        for old in pair:
            track = next(items for items in studio.items.values() if old in items)
            track.remove(old)
        for suffix, start, duration, source in (
            ("head", 0, 49, 0),
            ("tail", 50, 125, 75),
        ):
            fragments = []
            for old in pair:
                item = copy.copy(old)
                item.uid = old.uid + "-" + suffix
                item.start, item.duration, item.source = start, duration, source
                event = next(
                    e
                    for e in manifest["events"]
                    if identity["occurrences"][e["id"]]["itemUid"] == old.uid
                )
                studio.items[event["trackId"]].append(item)
                fragments.append(item)
            fragments[0].links, fragments[1].links = [fragments[1]], [fragments[0]]
