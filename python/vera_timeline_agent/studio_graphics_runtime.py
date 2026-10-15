"""Standard-library EV24 semantics and native placement, shared by both bridges."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .ev24_fusion_spike import (
    EV24_COUNTRIES,
    EV24_SETTING_SHA256,
    EV24_TEST_BADGE_SHA256,
    _connected_ev24_stop,
    _ev24_composition_tools,
    _ev24_root_tool,
    _verify_ev24_media_out,
    connect_ev24_to_media_out,
    discover_ev24_controls,
)
from .studio_spike import PublicResolveAdapter


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


JsonObject = dict[str, Any]
SETTING = "EV24 Lower Third.setting"
ATLAS = "ev24_badges_atlas.png"
TEST_BADGE = "badge_override_test_only.png"
ATLAS_SHA256 = "008cea751e3d18a15436fe5701755c0fd7a3a023f1b7f5c585f9796007c766fd"
ATLAS_REFERENCE = "Templates:/Edit/Titles/Eurovision/ev24_badges_atlas.png"
FILE_HASHES = {
    SETTING: EV24_SETTING_SHA256,
    ATLAS: ATLAS_SHA256,
    TEST_BADGE: EV24_TEST_BADGE_SHA256,
}
TEMPLATE_REL = Path("Templates/Edit/Titles/Eurovision")


class StudioGraphicError(RuntimeError):
    """A visible blocker; no graphic is treated as successfully placed."""


def _hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _compact(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def graphic_controls(values: Mapping[str, Any]) -> dict[str, str | int]:
    if values.get("badgeOverrideAssetId") is not None:
        raise StudioGraphicError(
            "BADGE_OVERRIDE_DEFERRED: custom badges require #9/#85; "
            "occurrence not placed"
        )
    required = {
        "country",
        "topLineOverride",
        "bottomLineOverride",
        "badgeOverrideAssetId",
    }
    country = values.get("country")
    if country not in EV24_COUNTRIES:
        raise StudioGraphicError("unknown registered country")
    expected = required if country == "otis" else required | {"year"}
    if set(values) != expected:
        raise StudioGraphicError("semantic inputs differ; Otis must omit Year")
    controls: dict[str, str | int] = {"Country": EV24_COUNTRIES.index(country)}
    if country != "otis":
        year = values["year"]
        if type(year) is not int or year < 1:
            raise StudioGraphicError("Year must be a positive integer")
        controls["Year"] = year
    for field, target in (
        ("topLineOverride", "TopLine"),
        ("bottomLineOverride", "BottomLine"),
    ):
        value = values[field]
        if value is not None and (not isinstance(value, str) or not value):
            raise StudioGraphicError("text override must be nonempty or null")
        controls[target] = value if value is not None else ""
    return controls


def validate_graphics(manifest: JsonObject) -> list[JsonObject]:
    sources = {source["id"]: source for source in manifest["sources"]}
    tracks = {track["id"]: track for track in manifest["tracks"]}
    graphics = [
        event for event in manifest["events"] if event["kind"] == "fusion_graphic"
    ]
    if not graphics:
        raise StudioGraphicError(
            "Studio graphics package requires a compiled occurrence"
        )
    for event in graphics:
        snapshot = event["semanticSnapshot"]
        if _hash(_canonical_json(snapshot)) != event["semanticSnapshotHash"]:
            raise StudioGraphicError("semantic snapshot hash differs")
        graphic_controls(snapshot["values"])
        if snapshot["badgeAsset"] is not None:
            raise StudioGraphicError(
                "BADGE_OVERRIDE_DEFERRED: badge snapshot is unsupported"
            )
        source = sources.get(event["sourceId"], {})
        if (
            source.get("kind") != "fusion_template"
            or source.get("templateKey") != "ev24-lower-third"
            or source.get("entryAssetHash") != "sha256:" + EV24_SETTING_SHA256
        ):
            raise StudioGraphicError("unregistered template identity")
        track = tracks.get(event["trackId"], {})
        if track.get("kind") != "video" or track.get("index") != 4:
            raise StudioGraphicError("graphic destination must be V4")
        if event["recordRange"]["durationFrames"] < 64:
            raise StudioGraphicError("EV24 requires at least 64 frames")
    return cast(list[JsonObject], graphics)


def _require_live_plan(manifest: JsonObject, report: JsonObject) -> None:
    results = {item["eventId"]: item for item in report["eventResults"]}
    for event in manifest["events"]:
        if event["kind"] != "fusion_graphic":
            continue
        result = results.get(event["id"], {})
        if (
            result.get("graphicMaterialization") != "live"
            or result.get("manualCompletionRequired") is not False
        ):
            raise StudioGraphicError(
                "compiler must explicitly plan live Studio graphics"
            )


def _package_digest(manifest: JsonObject) -> str:
    """The accepted template-library/v1 identity, independent of file order."""
    value = copy.deepcopy(manifest)
    value["files"].sort(key=lambda item: item["path"])
    value["compatibility"]["requiredCapabilities"].sort()
    value["rights"]["declarations"].sort(key=lambda item: item["id"])
    if isinstance(value["rights"]["allowedProjectIds"], list):
        value["rights"]["allowedProjectIds"].sort()
    return _hash(
        _compact(
            {
                "canonicalization": "vera-external-template-v1",
                "manifest": value,
                "fileSet": [
                    {key: item[key] for key in ("path", "byteLength", "sha256")}
                    for item in value["files"]
                ],
            }
        )
    )


def transport_artifacts(
    manifest: JsonObject, report: JsonObject
) -> tuple[JsonObject, JsonObject]:
    """Internal placement plan only; never published as the compiler's output."""
    media = copy.deepcopy(manifest)
    result = copy.deepcopy(report)
    for index, source in enumerate(media["sources"]):
        if source["kind"] == "fusion_template":
            media["sources"][index] = {
                "id": source["id"],
                "kind": "still",
                "width": 5120,
                "height": 3072,
                "contentHash": "sha256:" + ATLAS_SHA256,
                "path": f"Media/Resolved/{source['id']}.png",
            }
    for event in media["events"]:
        if event["kind"] == "fusion_graphic":
            event["kind"] = "still"
            for key in ("semanticSnapshot", "semanticSnapshotHash", "anchor"):
                del event[key]
    for event in result["eventResults"]:
        event.pop("graphicMaterialization", None)
        event.pop("manualCompletionRequired", None)
    result["manifest"]["contentHash"] = _hash(_canonical_json(media))
    return media, result


@dataclass(frozen=True)
class StudioGraphicPackage:
    root: Path
    manifest: JsonObject
    report: JsonObject
    template: JsonObject
    transport: JsonObject


class PublicStudioGraphicAdapter(PublicResolveAdapter):
    """The existing media adapter plus the exact pinned EV24 composition seam."""

    def __init__(self, resolve: Any, package: StudioGraphicPackage) -> None:
        super().__init__(resolve)
        self.graphic_package = package
        self.graphic_fingerprints: dict[str, str] = {}
        self.graphic_observations: list[JsonObject] = []
        self.template_bin_name = (
            "VERA Templates " + _package_digest(package.template)[7:23]
        )

    def verify_package(self) -> None:
        from .studio_graphics import verify_studio_graphic_package

        verify_studio_graphic_package(self.graphic_package.root)

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        connected = self.connected_facts()
        stop = _connected_ev24_stop(connected)
        if stop is not None:
            raise StudioGraphicError(
                stop + " Fresh EV24 runtime qualification is required."
            )
        return super().probe(settings)

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        graphic_sources = {
            source["id"]
            for source in self.graphic_package.manifest["sources"]
            if source["kind"] == "fusion_template"
        }
        regular = [entry for entry in sources if entry[0] not in graphic_sources]
        if regular:
            super().import_media(regular)
        media = dict(self.media_by_source)
        media_ids = dict(self.media_id_by_source)
        parent = self.pool.GetCurrentFolder()
        folder = self.pool.AddSubFolder(
            self.pool.GetRootFolder(), self.template_bin_name
        )
        if folder is None or not self.pool.SetCurrentFolder(folder):
            raise StudioGraphicError("could not create deterministic VERA template bin")
        super().import_media(
            [entry for entry in sources if entry[0] in graphic_sources]
        )
        for item in self.media_by_source.values():
            provenance = _package_digest(self.graphic_package.template)
            if not item.SetMetadata("Comments", provenance):
                raise StudioGraphicError(
                    "template provenance metadata could not be retained"
                )
        self.media_by_source = {**media, **self.media_by_source}
        self.media_id_by_source = {**media_ids, **self.media_id_by_source}
        if not self.pool.SetCurrentFolder(parent):
            raise StudioGraphicError("could not restore package media bin")

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        package = self.graphic_package
        graphics = validate_graphics(package.manifest)
        self.verify_package()
        # Place each still separately so repeated seed media retains each exact range.
        for event in events:
            super().place_events([event])
        for event in graphics:
            item = self._graphic_item(event)
            setting = package.root / TEMPLATE_REL / SETTING
            if item.ImportFusionComp(str(setting)) is None:
                raise StudioGraphicError(
                    "ImportFusionComp rejected the pinned EV24 setting"
                )
            connect_ev24_to_media_out(item)
            composition, tools = _ev24_composition_tools(item)
            root = _ev24_root_tool(tools)
            _strict_controls(root)
            # Keep the authored reference scoped to this composition.
            composition.SetPrefs(
                {"Comp.Paths.Map.Templates:": str(package.root / "Templates") + "/"}
            )
            if (
                Path(composition.MapPath(ATLAS_REFERENCE)).resolve()
                != (package.root / TEMPLATE_REL / ATLAS).resolve()
            ):
                raise StudioGraphicError(
                    "package atlas composition path mapping failed"
                )
            controls = graphic_controls(event["semanticSnapshot"]["values"])
            discover_ev24_controls(item).set_values(controls)
            if discover_ev24_controls(item).read_values(tuple(controls)) != controls:
                raise StudioGraphicError("EV24 semantic values differ before save")
            identity = _graphic_identity(package, event)
            composition.SetData("VERA.Graphic", _compact(identity).decode())
            self.graphic_fingerprints[event["id"]] = _graph_fingerprint(root)
            composition.SetData(
                "VERA.GraphFingerprint", self.graphic_fingerprints[event["id"]]
            )

    def _graphic_item(self, event: Mapping[str, Any]) -> Any:
        matches = [
            item
            for item in self.timeline.GetItemListInTrack("video", 4)
            if item.GetStart(False) == event["recordRange"]["startFrame"]
            and item.GetDuration(False) == event["recordRange"]["durationFrames"]
        ]
        if len(matches) != 1:
            raise StudioGraphicError(
                "expected exactly one graphic at its compiled V4 range"
            )
        return matches[0]

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        discrepancies = list(super().verify(manifest))
        package = self.graphic_package
        try:
            self.verify_package()
            folders = [
                folder
                for folder in self.pool.GetRootFolder().GetSubFolderList()
                if folder.GetName() == self.template_bin_name
            ]
            if len(folders) != 1:
                raise StudioGraphicError(
                    "deterministic template bin differs after reopen"
                )
            seeds = folders[0].GetClipList()
            expected_ids = {
                self.media_id_by_source[source["id"]]
                for source in package.manifest["sources"]
                if source["kind"] == "fusion_template"
            }
            if {item.GetMediaId() for item in seeds} != expected_ids:
                raise StudioGraphicError("template bin seed identity differs")
            if any(
                item.GetMetadata("Comments") != _package_digest(package.template)
                for item in seeds
            ):
                raise StudioGraphicError("template provenance differs after reopen")
            for event in validate_graphics(package.manifest):
                item = self._graphic_item(event)
                composition, tools = _ev24_composition_tools(item)
                root = _ev24_root_tool(tools)
                _strict_controls(root)
                _verify_ev24_media_out(item)
                controls = graphic_controls(event["semanticSnapshot"]["values"])
                actual = discover_ev24_controls(item).read_values(tuple(controls))
                if actual != controls:
                    raise StudioGraphicError("reopened semantic values differ")
                if (
                    composition.GetData("VERA.Graphic")
                    != _compact(_graphic_identity(package, event)).decode()
                ):
                    raise StudioGraphicError(
                        "reopened stable graphic-use identity differs"
                    )
                expected = self.graphic_fingerprints[event["id"]]
                if (
                    _graph_fingerprint(root) != expected
                    or composition.GetData("VERA.GraphFingerprint") != expected
                ):
                    raise StudioGraphicError(
                        "reopened Fusion graph fingerprint differs"
                    )
                if (
                    Path(composition.MapPath(ATLAS_REFERENCE)).resolve()
                    != (package.root / TEMPLATE_REL / ATLAS).resolve()
                ):
                    raise StudioGraphicError("reopened package atlas mapping differs")
                self.graphic_observations.append(
                    {
                        **_graphic_identity(package, event),
                        "graphFingerprint": expected,
                        "controlReadback": actual,
                        "semanticSnapshot": event["semanticSnapshot"],
                        "startFrame": item.GetStart(False),
                        "durationFrames": item.GetDuration(False),
                        "track": "V4",
                        "itemUid": item.GetUniqueId(),
                        "verifiedAfterReopen": True,
                    }
                )
        except Exception as error:
            discrepancies.append(f"EV24 verification failed: {error}")
        return tuple(discrepancies)


def _strict_controls(root: Any) -> None:
    inputs = root.GetInputList()
    if not isinstance(inputs, dict):
        raise StudioGraphicError("trusted control list is unavailable")
    expected = {
        "Country": "Number",
        "Year": "Number",
        "TopLine": "Text",
        "BottomLine": "Text",
        "BadgeOverride": "Clip",
    }
    for name, datatype in expected.items():
        matches = [
            value for value in inputs.values() if value.GetAttrs("INPS_ID") == name
        ]
        if len(matches) != 1 or matches[0].GetAttrs("INPS_DataType") != datatype:
            raise StudioGraphicError(
                f"trusted control {name} missing, duplicated or type-incompatible"
            )


def _graph_fingerprint(root: Any) -> str:
    settings = root.SaveSettings()
    if not isinstance(settings, dict):
        raise StudioGraphicError("Fusion graph settings are unavailable")

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            # Fusion's Lua tables may mix integer keys with named keys.
            entries = {str(key): normalize(item) for key, item in value.items()}
            if len(entries) != len(value):
                raise StudioGraphicError("Fusion graph has ambiguous table keys")
            return entries
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        return value

    try:
        canonical = normalize(settings)

        def table(*path: str) -> dict[str, Any]:
            value = canonical
            for key in ("Tools", "EV24LowerThird", "Tools", *path):
                if not isinstance(value, dict):
                    return {}
                value = value.get(key)
            return value if isinstance(value, dict) else {}

        # Only the four exact Studio21.1.1/10 persistence forms approved for EV24.
        for path, flag in (
            (("ControlHub", "UserControls", "Country"), 256),
            (("ControlHub", "UserControls"), 3145984),
            (("Metrics", "UserControls"), 3145984),
        ):
            controls = table(*path)
            if type(controls.get("__flags")) is int and controls["__flags"] == flag:
                del controls["__flags"]
        ribbon = table("RibbonUnit")
        inputs = ribbon.get("Inputs")
        badge = inputs.get("BadgeImage") if isinstance(inputs, dict) else None
        if (
            isinstance(badge, dict)
            and inputs
            == {"BadgeImage": {"Value": 0.0, "__ctor": "Input", "__flags": 256}}
            and type(badge["Value"]) is float
            and _compact(badge["Value"]) == b"0.0"
            and type(badge["__flags"]) is int
        ):
            del ribbon["Inputs"]
        return _hash(_compact(canonical))
    except (TypeError, ValueError) as error:
        raise StudioGraphicError(
            "Fusion graph settings cannot be fingerprinted"
        ) from error


def _graphic_identity(
    package: StudioGraphicPackage, event: Mapping[str, Any]
) -> JsonObject:
    source = next(
        source
        for source in package.manifest["sources"]
        if source["id"] == event["sourceId"]
    )
    return {
        "buildId": package.manifest["buildId"],
        "graphicUseId": event["id"],
        "provenance": event["provenance"],
        "source": source,
        "semanticSnapshotHash": event["semanticSnapshotHash"],
        "graphSourceHash": "sha256:" + EV24_SETTING_SHA256,
        "atlasHash": "sha256:" + ATLAS_SHA256,
        "recordRange": event["recordRange"],
        "trackId": event["trackId"],
    }
