"""#190 audited injected proof delivery/capture/local PCM render sibling.

No connection discovery, fallback, scheduler, deletion or live qualification.
Complete native controls require a trusted installed reader; absence refuses.
Every possibly mutating call has an exclusive retained intent. An uncertain
call is never retried. Polling an already owned render is read-only.
"""

from __future__ import annotations

import copy
import fcntl
import io
import os
import wave
from collections.abc import Callable
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.narration.models import canonical_json_bytes
from vera_timeline_agent.roundtrip_v2_records import (
    ROOT,
    JsonObject,
    ReceiptVerifier,
    _destination,
    _digest,
    _file_hash,
    _open_file,
    _operator_bytes,
    _parse,
    _regular,
    fact,
    identity,
    integer,
    proof_source_hashes_v2,
    publish_immutable_output,
    shape,
)
from vera_timeline_agent.workflow_v2 import (
    load_verified_package_v2,
    run_workflow_delivery_v2,
)

ControlReader = Callable[[Any, Any, JsonObject], JsonObject]


def _get(handle: Any, method: str, *arguments: Any) -> Any:
    call = getattr(handle, method, None)
    fact(callable(call), f"unavailable native interface {method}: operator handoff")
    assert callable(call)
    return call(*arguments)


def _rate(value: Any) -> Fraction:
    shape(value, "numerator denominator", "rational rate")
    n, d = integer(value["numerator"], 1), integer(value["denominator"], 1)
    rate = Fraction(n, d)
    fact(rate.numerator == n and rate.denominator == d, "reduced rational required")
    return rate


def _wire(rate: Fraction) -> JsonObject:
    return {"numerator": rate.numerator, "denominator": rate.denominator}


def _speed(value: Any) -> JsonObject:
    observed = shape(
        value,
        "Percentage PitchCorrection StretchKeyframesToFit RippleTimeline",
        "complete native speed options",
    )
    fact(
        type(observed["Percentage"]) in {int, float}
        and observed["Percentage"] == 100
        and type(observed["PitchCorrection"]) is bool
        and observed["StretchKeyframesToFit"] is False
        and observed["RippleTimeline"] is False,
        "unsupported/unknown native speed options",
    )
    return observed


def _exclusive(path: Path, value: JsonObject) -> None:
    _destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(
        _open_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb"
    ) as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _controls(value: JsonObject, audio_items: set[str]) -> None:
    shape(value, "programControls routes", "complete control inventory")
    program = shape(
        value["programControls"],
        "gainDb effects limiter automation destination",
        "programme controls",
    )
    fact(
        program
        == {
            "gainDb": 0,
            "effects": [],
            "limiter": False,
            "automation": [],
            "destination": "stereo-program",
        },
        "unsupported/unknown programme controls",
    )
    fact(
        type(program["gainDb"]) in {int, float} and program["limiter"] is False,
        "programme control types",
    )
    seen: set[str] = set()
    fact(isinstance(value["routes"], list), "complete routes required")
    for route in value["routes"]:
        shape(route, "itemUid sourceId controls", "native route")
        uid = identity(route["itemUid"])
        identity(route["sourceId"])
        fact(uid in audio_items and uid not in seen, "unknown/duplicate route")
        seen.add(uid)
        controls = shape(
            route["controls"],
            "enabled mute solo gainDb pan effects sends automation "
            "destination channelMap",
            "route controls",
        )
        fact(
            controls["enabled"] is True
            and controls["mute"] is False
            and controls["solo"] is False
            and type(controls["gainDb"]) in {int, float}
            and controls["gainDb"] in {-18, 0}
            and type(controls["pan"]) in {int, float}
            and controls["pan"] == 0
            and controls["effects"] == controls["sends"] == controls["automation"] == []
            and controls["destination"] == "stereo-program"
            and controls["channelMap"] in {"mono-dual", "stereo-direct"},
            "unsupported/unknown complete audio controls",
        )
    fact(seen == audio_items, "incomplete audible-source control inventory")


class NativeProofBoundaryV2:
    def __init__(
        self,
        resolve: Any,
        *,
        attestation_path: Path,
        attestation_hash: str,
        proof_package_path: Path,
        proof_package_hash: str,
        evidence_root: Path,
        authenticate: ReceiptVerifier,
        authority: bytes,
        code_hashes: JsonObject,
        read_controls: ControlReader | None = None,
        adapter_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self.resolve = resolve
        self.attestation_path = attestation_path
        self.attestation_hash = attestation_hash
        fact(
            _file_hash(attestation_path) == attestation_hash,
            "attestation raw pin differs",
        )
        self.package = load_verified_package_v2(attestation_path, attestation_hash[7:])
        self.proof_path = proof_package_path
        fact(
            _file_hash(proof_package_path) == proof_package_hash,
            "proof package pin differs",
        )
        proof = _parse(_operator_bytes(proof_package_path))
        shape(
            proof,
            "schemaVersion evidenceLevel preflightHash requestHash package "
            "verification attestationPath attestationHash",
            "proof package",
        )
        self.preflight_path = proof_package_path.with_name("preflight.json")
        self.preflight_raw = _operator_bytes(self.preflight_path)
        self.preflight = _parse(self.preflight_raw)
        shape(
            self.preflight,
            "schemaVersion status evidenceLevel lane requestHash originalInputs "
            "executionInputs sourceHashes verifiedFiles manifestHash reportHash "
            "needs packageVerification unchecked",
            "preflight handoff",
        )
        fact(
            proof.get("schemaVersion") == "issue-189-v2-proof-package/v1"
            and proof.get("evidenceLevel") == "local_prepared"
            and proof.get("attestationPath") == str(attestation_path)
            and proof.get("attestationHash") == attestation_hash,
            "verified local proof handoff required",
        )
        fact(
            _digest(canonical_json_bytes(self.preflight)) == proof["preflightHash"]
            and self.preflight["schemaVersion"] == "issue-189-v2-preflight/v1"
            and self.preflight["status"] == "prepared"
            and self.preflight["evidenceLevel"] == "local_prepared"
            and self.preflight["requestHash"] == proof["requestHash"]
            and self.preflight["sourceHashes"] == code_hashes
            and proof["package"]["project_root"] == str(self.package.root)
            and proof["package"]["build_id"] == self.package.attestation["buildId"],
            "proof preflight/package lineage differs",
        )
        self.root = evidence_root.absolute()
        fact(
            not self.root.is_relative_to(self.package.root),
            "native evidence cannot write package",
        )
        for source in [
            attestation_path,
            proof_package_path,
            self.preflight_path,
            *(Path(p) for p in self.preflight["verifiedFiles"]),
            *(ROOT / p for p in code_hashes),
        ]:
            fact(
                not source.absolute().is_relative_to(self.root),
                "native evidence overlaps proof input",
            )
        _destination(self.root / "binding.json")
        self.authenticate = authenticate
        self.authority = authority
        self.read_controls = read_controls
        self.adapter_factory = adapter_factory
        self.code_hashes = copy.deepcopy(code_hashes)
        self.binding = {
            "schemaVersion": "issue-189-v2-native-binding/v1",
            "attestationHash": attestation_hash,
            "proofPackageHash": proof_package_hash,
            "sourceHashes": self.code_hashes,
            "evidenceRoot": str(self.root),
            "projectName": self.package.attestation["projectName"],
            "timelineName": self.package.attestation["timelineName"],
            "authorityHash": _digest(authority),
        }
        self._guard()
        authenticate("native_proof_binding", authority, copy.deepcopy(self.binding))
        publish_immutable_output(
            self.root / "binding.json", canonical_json_bytes(self.binding)
        )

    def _guard(self) -> None:
        binding_path = self.root / "binding.json"
        if binding_path.exists():
            fact(
                _operator_bytes(binding_path) == canonical_json_bytes(self.binding),
                "native binding ownership changed",
            )
        fact(
            proof_source_hashes_v2() == self.code_hashes, "native proof source changed"
        )
        fact(
            _file_hash(self.proof_path) == self.binding["proofPackageHash"],
            "proof handoff changed",
        )
        fact(
            load_verified_package_v2(self.attestation_path, self.attestation_hash[7:])
            == self.package,
            "native proof package changed",
        )
        fact(
            _operator_bytes(self.preflight_path) == self.preflight_raw,
            "preflight handoff changed",
        )
        for path, digest in self.preflight["verifiedFiles"].items():
            fact(
                _file_hash(Path(path)) == digest,
                "proof input changed before native operation",
            )

    @contextmanager
    def _lock(self) -> Any:
        path = self.root / "effect.lock"
        _destination(path)
        with os.fdopen(
            _open_file(path, os.O_RDWR | os.O_CREAT, 0o600), "r+b"
        ) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                fact(
                    os.fstat(stream.fileno()).st_nlink == 1
                    and path.stat().st_ino == os.fstat(stream.fileno()).st_ino,
                    "independent effect lock required",
                )
                self._guard()
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def deliver(self) -> JsonObject:
        """Consume #109/#177 public delivery exactly once; retain every failure."""
        with self._lock():
            intent = self.root / "delivery-intent.json"
            fact(
                not intent.exists(),
                "delivery intent already exists: read-only recovery required",
            )
            self.authenticate(
                "native_delivery", self.authority, copy.deepcopy(self.binding)
            )
            _exclusive(
                intent,
                {
                    "schemaVersion": "issue-189-v2-effect-intent/v1",
                    "operation": "new_target_delivery",
                    "bindingHash": _file_hash(self.root / "binding.json"),
                    "owner": str(self.root),
                },
            )
            result = run_workflow_delivery_v2(
                self.resolve,
                self.attestation_path,
                self.attestation_hash[7:],
                action="build",
                authorize_new_nonproduction=True,
                external_scripting="None",
                adapter_factory=self.adapter_factory,
            )
            # Even stopped/partial results consume the intent; no hidden retry.
            fact(
                result.get("schemaVersion") == "vera-injected-delivery-result/v2"
                and result.get("attestationSha256") == self.attestation_hash[7:]
                and result.get("action") == "build",
                "delivery result binding differs",
            )
            _exclusive(
                self.root / "delivery-effect.json",
                {
                    "schemaVersion": "issue-189-v2-delivery-effect/v1",
                    "intentHash": _file_hash(intent),
                    "result": result,
                },
            )
            self._guard()
            if result.get("verified") is True and result.get("status") == "verified":
                project = _get(
                    _get(self.resolve, "GetProjectManager"), "GetCurrentProject"
                )
                timeline = _get(project, "GetCurrentTimeline")
                target = {
                    "projectUid": identity(_get(project, "GetUniqueId")),
                    "timelineUid": identity(_get(timeline, "GetUniqueId")),
                }
                self._context(target)
                _exclusive(
                    self.root / "delivery-complete.json",
                    {
                        "schemaVersion": "issue-189-v2-effect-complete/v1",
                        "intentHash": _file_hash(intent),
                        "effectHash": _file_hash(self.root / "delivery-effect.json"),
                        "target": target,
                        "evidenceLevel": "injected_execution_unqualified",
                    },
                )
            return copy.deepcopy(result)

    def recover_delivery(self) -> JsonObject:
        """Read retained records only; never create/reconfigure an uncertain target."""
        self._guard()
        records = {
            name: _parse(_operator_bytes(self.root / name))
            for name in (
                "delivery-intent.json",
                "delivery-effect.json",
                "delivery-complete.json",
            )
            if (self.root / name).exists()
        }
        intent = records.get("delivery-intent.json")
        effect = records.get("delivery-effect.json")
        complete = records.get("delivery-complete.json")
        if intent is not None:
            shape(
                intent, "schemaVersion operation bindingHash owner", "delivery intent"
            )
            fact(
                intent["schemaVersion"] == "issue-189-v2-effect-intent/v1"
                and intent["operation"] == "new_target_delivery"
                and intent["owner"] == str(self.root)
                and intent["bindingHash"] == _file_hash(self.root / "binding.json"),
                "delivery intent ownership differs",
            )
        if effect is not None:
            shape(effect, "schemaVersion intentHash result", "delivery effect")
            fact(
                intent is not None
                and effect["schemaVersion"] == "issue-189-v2-delivery-effect/v1"
                and effect["intentHash"]
                == _file_hash(self.root / "delivery-intent.json"),
                "delivery effect ancestry differs",
            )
            result = effect["result"]
            fact(
                isinstance(result, dict)
                and result.get("schemaVersion") == "vera-injected-delivery-result/v2"
                and result.get("attestationSha256") == self.attestation_hash[7:]
                and result.get("action") == "build",
                "delivery effect attestation differs",
            )
        if complete is not None:
            shape(
                complete,
                "schemaVersion intentHash effectHash target evidenceLevel",
                "delivery completion",
            )
            fact(
                effect is not None
                and complete["schemaVersion"] == "issue-189-v2-effect-complete/v1"
                and complete["intentHash"] == effect["intentHash"]
                and complete["effectHash"]
                == _file_hash(self.root / "delivery-effect.json")
                and complete["evidenceLevel"] == "injected_execution_unqualified"
                and effect["result"].get("verified") is True
                and effect["result"].get("status") == "verified",
                "delivery completion ancestry differs",
            )
            shape(complete["target"], "projectUid timelineUid", "delivery target")
        return {
            "schemaVersion": "issue-189-v2-readonly-recovery/v1",
            "status": "retained_no_retry",
            "records": records,
            "nativeEffects": 0,
        }

    def _delivery_lineage(self, target: JsonObject) -> JsonObject:
        records = self.recover_delivery()["records"]
        if not records:
            return {
                "kind": "externally_supplied_target",
                "target": copy.deepcopy(target),
            }
        complete = records.get("delivery-complete.json")
        fact(
            complete is not None and complete["target"] == target,
            "incomplete or failed delivery cannot supply proof evidence",
        )
        return {
            "kind": "owned_verified_delivery",
            "completionHash": _file_hash(self.root / "delivery-complete.json"),
            "intentHash": complete["intentHash"],
            "effectHash": complete["effectHash"],
            "target": copy.deepcopy(target),
        }

    def _context(self, target: JsonObject) -> tuple[Any, Any]:
        shape(target, "projectUid timelineUid", "target")
        product = _get(self.resolve, "GetProductName")
        version = _get(self.resolve, "GetVersion")
        fact(
            product == "DaVinci Resolve Studio"
            and version in ([21, 1, 0, 14, ""], [21, 1, 1, 10, ""]),
            "unsupported injected Studio identity",
        )
        manager = _get(self.resolve, "GetProjectManager")
        project = _get(manager, "GetCurrentProject")
        timeline = _get(project, "GetCurrentTimeline")
        fact(
            _get(project, "GetUniqueId") == target["projectUid"]
            and _get(timeline, "GetUniqueId") == target["timelineUid"]
            and _get(project, "GetName") == self.binding["projectName"]
            and _get(timeline, "GetName") == self.binding["timelineName"],
            "native target/currentness changed",
        )
        return project, timeline

    def _read(self, target: JsonObject, mapping: JsonObject) -> JsonObject:
        self._guard()
        self.authenticate(
            "native_item_mapping",
            self.authority,
            {"binding": self.binding, "target": target, "mapping": mapping},
        )
        project, timeline = self._context(target)
        lineage = self._delivery_lineage(target)
        expected_timeline = self.package.manifest["timeline"]
        rate = _rate(expected_timeline["frameRate"])
        native_rate = str(_get(timeline, "GetSetting", "timelineFrameRate"))
        fact(
            native_rate
            == ("23.976" if rate == Fraction(24000, 1001) else str(rate.numerator)),
            "native frame-rate presentation differs",
        )
        start, end = (
            integer(_get(timeline, "GetStartFrame")),
            integer(_get(timeline, "GetEndFrame"), 1),
        )
        fact(
            start == expected_timeline["startFrame"]
            and 0 < end - start <= expected_timeline["durationFrames"],
            "native complete extent differs",
        )
        settings: JsonObject = {}
        for key, setting in (
            ("width", "timelineResolutionWidth"),
            ("height", "timelineResolutionHeight"),
            ("audioSampleRate", "timelineSampleRate"),
        ):
            value = _get(timeline, "GetSetting", setting)
            fact(
                type(value) in {str, int} and str(value).isdigit(),
                "unreadable native setting",
            )
            settings[key] = int(value)
            fact(settings[key] == expected_timeline[key], "native setting differs")
        sources = {
            str(self.package.root / source["path"]): source
            for source in self.package.view["sources"]
        }
        events = {e["id"]: e for e in self.package.view["events"]}
        items: list[JsonObject] = []
        tracks: list[JsonObject] = []
        seen: set[str] = set()
        for kind in ("video", "audio", "subtitle"):
            count = integer(_get(timeline, "GetTrackCount", kind))
            fact(
                count <= 32 and (kind != "subtitle" or count == 0),
                "unsupported track inventory",
            )
            for index in range(1, count + 1):
                enabled = _get(timeline, "GetIsTrackEnabled", kind, index)
                locked = _get(timeline, "GetIsTrackLocked", kind, index)
                fact(
                    enabled is True and type(locked) is bool,
                    "disabled or unreadable native track state",
                )
                tracks.append(
                    {
                        "kind": kind,
                        "index": index,
                        "name": identity(_get(timeline, "GetTrackName", kind, index)),
                        "enabled": enabled,
                        "locked": locked,
                    }
                )
                native_items = _get(timeline, "GetItemListInTrack", kind, index)
                fact(
                    isinstance(native_items, (list, tuple))
                    and len(native_items) <= 1024,
                    "incomplete native item inventory",
                )
                for item in native_items:
                    uid = identity(_get(item, "GetUniqueId"))
                    fact(
                        uid in mapping and uid not in seen,
                        "unknown/duplicate native item identity",
                    )
                    seen.add(uid)
                    owner = shape(mapping[uid], "eventId sourceId", "item mapping")
                    fact(owner["eventId"] in events, "unknown event owner")
                    event = events[owner["eventId"]]
                    fact(
                        event["sourceId"] == owner["sourceId"]
                        and event["trackKind"] == kind,
                        "event/source owner mismatch",
                    )
                    media = _get(item, "GetMediaPoolItem")
                    props = _get(media, "GetClipProperty")
                    fact(
                        isinstance(props, dict)
                        and props.get("Online Status") == "Online",
                        "offline/unreadable media",
                    )
                    path = props.get("File Path")
                    fact(
                        path in sources and sources[path]["id"] == owner["sourceId"],
                        "native media/source mapping differs",
                    )
                    source_hash = _file_hash(Path(path))
                    fact(
                        source_hash == sources[path]["contentHash"],
                        "native source bytes differ",
                    )
                    record_start = integer(_get(item, "GetStart", False))
                    duration = integer(_get(item, "GetDuration", False), 1)
                    record_end = integer(_get(item, "GetEnd", False))
                    fact(
                        record_end - record_start in {duration, duration - 1},
                        "native endpoint convention differs",
                    )
                    fact(
                        start <= record_start < record_start + duration <= end,
                        "native item outside programme extent",
                    )
                    fact(
                        all(
                            _get(item, method, True) == observed
                            for method, observed in (
                                ("GetStart", record_start),
                                ("GetDuration", duration),
                                ("GetEnd", record_end),
                            )
                        ),
                        "unsupported fractional record geometry",
                    )
                    source_start = integer(_get(item, "GetSourceStartFrame"))
                    source_end = integer(_get(item, "GetSourceEndFrame")) + 1
                    fact(source_end > source_start, "empty source range")
                    links = _get(item, "GetLinkedItems")
                    fact(isinstance(links, (list, tuple)), "unreadable native links")
                    linked = sorted(
                        identity(_get(peer, "GetUniqueId")) for peer in links
                    )
                    fact(
                        len(linked) == len(set(linked)) and uid not in linked,
                        "duplicate/self links",
                    )
                    enabled = _get(item, "GetClipEnabled")
                    speed = _speed(_get(item, "GetSpeed"))
                    fact(
                        enabled is True and speed["Percentage"] == 100,
                        "unsupported native enable/speed",
                    )
                    items.append(
                        {
                            "itemUid": uid,
                            "mediaUid": identity(_get(media, "GetUniqueId")),
                            "eventId": owner["eventId"],
                            "sourceId": owner["sourceId"],
                            "kind": kind,
                            "trackIndex": index,
                            "recordStart": record_start,
                            "recordEnd": record_start + duration,
                            "rawRecordEnd": record_end,
                            "sourceStart": source_start,
                            "sourceEnd": source_end,
                            # #177's native delivery view expresses source frames
                            # in timeline-rate units; retain the logical v2 event
                            # separately so no logical/source-rate cast is hidden.
                            "sourceRangeRate": expected_timeline["frameRate"],
                            "authoredEvent": event["v2Event"],
                            "sourceHash": source_hash,
                            "sourcePath": path,
                            "enabled": enabled,
                            "online": True,
                            "speed": {"numerator": 1, "denominator": 1},
                            "rawSpeedOptions": speed,
                            "linkedUids": linked,
                        }
                    )
        fact(seen == set(mapping), "stale/incomplete item mapping")
        fact(
            {item["eventId"] for item in items} == set(events),
            "incomplete event ownership inventory",
        )
        for item in items:
            fact(
                all(
                    peer in seen
                    and item["itemUid"]
                    in next(i for i in items if i["itemUid"] == peer)["linkedUids"]
                    for peer in item["linkedUids"]
                ),
                "nonreciprocal/unknown links",
            )
        fact(
            self.read_controls is not None,
            "complete installed native control reader unavailable: operator handoff",
        )
        assert self.read_controls is not None
        controls = self.read_controls(project, timeline, copy.deepcopy(target))
        _controls(controls, {i["itemUid"] for i in items if i["kind"] == "audio"})
        for route in controls["routes"]:
            fact(
                route["sourceId"]
                == next(i for i in items if i["itemUid"] == route["itemUid"])[
                    "sourceId"
                ],
                "route/source owner differs",
            )
        self._context(target)
        self._guard()
        observed = {
            "schemaVersion": "issue-189-v2-native-readback/v1",
            "target": target,
            "deliveryLineage": lineage,
            "nativeIdentity": {
                "product": _get(self.resolve, "GetProductName"),
                "version": _get(self.resolve, "GetVersion"),
            },
            "timeline": {
                **settings,
                "startFrame": start,
                "durationFrames": end - start,
                "frameRate": _wire(rate),
            },
            "tracks": tracks,
            "items": sorted(items, key=lambda i: i["itemUid"]),
            "controls": controls,
            "markers": _get(timeline, "GetMarkers"),
        }
        # Full observed geometry is authenticated separately from item lineage;
        # a copied event stamp alone never authorizes an edit or shortened extent.
        self.authenticate(
            "native_observation",
            self.authority,
            {"binding": self.binding, "observation": copy.deepcopy(observed)},
        )
        return observed

    def capture(self, target: JsonObject, mapping: JsonObject, name: str) -> JsonObject:
        fact(name.isidentifier(), "bounded observation name required")
        with self._lock():
            first, second = self._read(target, mapping), self._read(target, mapping)
            fact(first == second, "adjacent native observations disagree")
            raw = canonical_json_bytes(first)
            audio = self._derive_audio(first)
            path = self.root / "observations" / f"{name}.json"
            _exclusive(path, first)
            audio_path = path.with_suffix(".audio.json")
            _exclusive(audio_path, audio)
            result: JsonObject = {
                "schemaVersion": "issue-189-v2-observation-receipt/v1",
                "bindingHash": _file_hash(self.root / "binding.json"),
                "rawHash": _digest(raw),
                "derivedAudioHash": _file_hash(audio_path),
                "mappingHash": _digest(canonical_json_bytes(mapping)),
                "target": target,
                "deliveryLineage": copy.deepcopy(first["deliveryLineage"]),
                "adjacentConsistent": True,
                "evidenceLevel": "injected_execution_unqualified",
            }
            _exclusive(path.with_suffix(".receipt.json"), result)
            return result

    def _derive_audio(self, raw: JsonObject) -> JsonObject:
        """Map complete native WAV-local geometry to #191's audio record."""
        rate = _rate(raw["timeline"]["frameRate"])
        samples_per_frame = Fraction(48000, 1) / rate
        fact(
            samples_per_frame.denominator == 1,
            "audio observation requires exact sample/frame mapping",
        )
        routes: list[JsonObject] = []
        by_source: dict[str, JsonObject] = {}
        for native_route in raw["controls"]["routes"]:
            item = next(
                i for i in raw["items"] if i["itemUid"] == native_route["itemUid"]
            )
            sid = item["sourceId"]
            source = Path(item["sourcePath"])
            pcm = _operator_bytes(source, limit=64 * 1024 * 1024)
            fact(_digest(pcm) == item["sourceHash"], "audio source bytes changed")
            with wave.open(io.BytesIO(pcm), "rb") as stream:
                fact(
                    stream.getnchannels() in {1, 2}
                    and stream.getsampwidth() in {2, 3}
                    and stream.getframerate() == 48000
                    and stream.getcomptype() == "NONE"
                    and item["sourceEnd"] * samples_per_frame <= stream.getnframes(),
                    "native audio WAV-local range/profile differs",
                )
                fact(
                    native_route["controls"]["channelMap"]
                    == ("mono-dual" if stream.getnchannels() == 1 else "stereo-direct"),
                    "native channel mapping differs from actual PCM",
                )
            fact(_file_hash(source) == item["sourceHash"], "audio source changed")
            fact(
                item["recordEnd"] - item["recordStart"]
                == item["sourceEnd"] - item["sourceStart"],
                "native audio geometry requires unqualified retiming",
            )
            segment = {
                "uid": item["itemUid"],
                "recordStart": item["recordStart"],
                "recordEnd": item["recordEnd"],
                "sourceStart": item["sourceStart"],
                "sourceEnd": item["sourceEnd"],
                "speed": item["speed"],
                "enabled": item["enabled"],
                "online": item["online"],
            }
            if sid in by_source:
                fact(
                    by_source[sid]["controls"] == native_route["controls"],
                    "split source controls differ",
                )
                by_source[sid]["segments"].append(segment)
            else:
                by_source[sid] = {
                    "id": f"native-route:{sid}",
                    "sourceId": sid,
                    "controls": native_route["controls"],
                    "segments": [segment],
                }
        for sid in sorted(by_source):
            route = by_source[sid]
            route["segments"].sort(key=lambda s: (s["recordStart"], s["uid"]))
            fact(
                all(
                    a["recordEnd"] <= b["recordStart"]
                    and a["sourceEnd"] <= b["sourceStart"]
                    for a, b in zip(
                        route["segments"], route["segments"][1:], strict=False
                    )
                ),
                "split source segments overlap/reorder",
            )
            routes.append(route)
        return {
            "schemaVersion": "issue-189-v2-audio-observation/v1",
            "target": raw["target"],
            "extentFrames": raw["timeline"]["durationFrames"],
            "frameRate": raw["timeline"]["frameRate"],
            "programControls": raw["controls"]["programControls"],
            "routes": routes,
        }

    def _job(
        self,
        project: Any,
        job_id: str,
        output: Path,
        settings: JsonObject,
        target: JsonObject,
    ) -> JsonObject:
        self._context(target)
        queue = _get(project, "GetRenderJobList")
        fact(isinstance(queue, list), "actual render queue unreadable")
        matches = [
            job for job in queue if isinstance(job, dict) and job.get("JobId") == job_id
        ]
        fact(len(matches) == 1, "owned render job missing/duplicated")
        job = matches[0]
        expected = {
            "TimelineName": self.binding["timelineName"],
            "TargetDir": str(output.parent),
            "OutputFilename": output.name,
            "IsExportVideo": False,
            "IsExportAudio": True,
            "MarkIn": settings["MarkIn"],
            "MarkOut": settings["MarkOut"],
            "AudioBitDepth": 24,
            "AudioSampleRate": 48000,
            "AudioCodec": settings["AudioCodec"],
            "RenderMode": "Single clip",
            "ReplaceExistingFilesInPlace": False,
        }
        fact(
            all(
                key in job and type(job[key]) is type(value) and job[key] == value
                for key, value in expected.items()
            ),
            "actual render job/settings/output mismatch or unknown control",
        )
        status = _get(project, "GetRenderJobStatus", job_id)
        fact(
            isinstance(status, dict)
            and status.get("JobStatus") in {"Ready", "Rendering", "Complete"},
            "render failed/unknown/unsupported state",
        )
        fact(
            type(status.get("CompletionPercentage")) is int
            and 0 <= status["CompletionPercentage"] <= 100,
            "unknown render completion percentage",
        )
        if status["JobStatus"] == "Complete":
            fact(
                status["CompletionPercentage"] == 100,
                "incomplete job cannot claim completion",
            )
        self._context(target)
        return {"queue": job, "poll": status}

    def render_complete_programme(
        self,
        *,
        target: JsonObject,
        mapping: JsonObject,
        observation_hash: str,
        output: Path,
        render_format: str,
        render_codec: str,
    ) -> JsonObject:
        """Start once or read-only poll one job; no background service."""
        with self._lock():
            observation = self._read(target, mapping)
            fact(
                self._read(target, mapping) == observation
                and _digest(canonical_json_bytes(observation)) == observation_hash,
                "render observation currentness differs",
            )
            project, _ = self._context(target)
            output = output.absolute()
            fact(
                output.suffix == ".wav"
                and output.is_relative_to(self.root / "renders"),
                "owned local WAV output required",
            )
            _destination(output)
            timeline = observation["timeline"]
            count = Fraction(timeline["durationFrames"] * 48000, 1) / _rate(
                timeline["frameRate"]
            )
            fact(
                count.denominator == 1 and 0 < count <= 3_000_000,
                "bounded exact whole-programme PCM samples required",
            )
            settings = {
                "SelectAllFrames": False,
                "MarkIn": timeline["startFrame"],
                "MarkOut": timeline["startFrame"] + timeline["durationFrames"] - 1,
                "TargetDir": str(output.parent),
                "CustomName": output.stem,
                "UseUniqueFilenames": False,
                "ExportVideo": False,
                "ExportAudio": True,
                "AudioFormat": render_format,
                "AudioCodec": render_codec,
                "AudioBitDepth": 24,
                "AudioSampleRate": 48000,
                "ReplaceExistingFilesInPlace": False,
            }
            parameters = {
                "target": target,
                "deliveryLineage": copy.deepcopy(observation["deliveryLineage"]),
                "mapping": mapping,
                "observationHash": observation_hash,
                "output": str(output),
                "settings": settings,
                "format": render_format,
                "codec": render_codec,
            }
            self.authenticate(
                "native_pcm_render",
                self.authority,
                {"binding": self.binding, "parameters": parameters},
            )
            slot = self.root / "render" / _digest(canonical_json_bytes(parameters))[7:]
            output_owner = (
                self.root
                / "render-output-owners"
                / (_digest(str(output).encode())[7:] + ".json")
            )
            intent_path, effect_path = slot / "intent.json", slot / "effect.json"
            if not intent_path.exists():
                fact(
                    not output_owner.exists(),
                    "render output already reserved: no retry",
                )
                fact(not output.exists(), "render output collision")
                before_queue = _get(project, "GetRenderJobList")
                fact(isinstance(before_queue, list), "queue inventory unavailable")
                fact(
                    all(
                        job.get("OutputFilename") != output.name
                        or job.get("TargetDir") != str(output.parent)
                        for job in before_queue
                    ),
                    "output already claimed by another job",
                )
                _exclusive(
                    output_owner,
                    {
                        "output": str(output),
                        "slot": str(slot),
                        "bindingHash": _file_hash(self.root / "binding.json"),
                    },
                )
                _exclusive(
                    intent_path,
                    {
                        "schemaVersion": "issue-189-v2-render-intent/v1",
                        "bindingHash": _file_hash(self.root / "binding.json"),
                        "parameters": parameters,
                        "priorQueue": before_queue,
                    },
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                self._guard()
                self._context(target)
                fact(
                    _get(
                        project,
                        "SetCurrentRenderFormatAndCodec",
                        render_format,
                        render_codec,
                    )
                    is True,
                    "PCM render format/codec unsupported",
                )
                fact(
                    _get(project, "GetCurrentRenderFormatAndCodec")
                    == {"format": render_format, "codec": render_codec},
                    "current render format/codec differs",
                )
                self._guard()
                self._context(target)
                fact(
                    _get(project, "SetRenderSettings", settings) is True,
                    "PCM render settings unsupported",
                )
                self._context(target)
                self._guard()
                fact(
                    not output.exists(), "render output appeared before queue creation"
                )
                job_id = identity(_get(project, "AddRenderJob"))
                fact(
                    job_id not in {job["JobId"] for job in before_queue},
                    "render job ID collision",
                )
                actual = self._job(project, job_id, output, settings, target)
                fact(
                    actual["poll"]["JobStatus"] == "Ready",
                    "new job has not been started by owner",
                )
                _exclusive(
                    effect_path,
                    {
                        "schemaVersion": "issue-189-v2-render-effect/v1",
                        "intentHash": _file_hash(intent_path),
                        "jobId": job_id,
                        "actual": actual,
                    },
                )
                _exclusive(
                    slot / "start-intent.json",
                    {"jobId": job_id, "effectHash": _file_hash(effect_path)},
                )
                self._guard()
                self._context(target)
                fact(not output.exists(), "render output appeared before start")
                fact(
                    _get(project, "StartRendering", [job_id], False) is True,
                    "render start uncertain: no retry",
                )
                _exclusive(
                    slot / "start-returned.json", {"jobId": job_id, "returned": True}
                )
            else:
                fact(
                    _parse(_operator_bytes(output_owner))
                    == {
                        "output": str(output),
                        "slot": str(slot),
                        "bindingHash": _file_hash(self.root / "binding.json"),
                    },
                    "render output reservation differs",
                )
                retained = _parse(_operator_bytes(intent_path))
                fact(
                    retained["parameters"] == parameters
                    and retained["bindingHash"]
                    == _file_hash(self.root / "binding.json"),
                    "immutable render intent ownership differs",
                )
                fact(
                    effect_path.exists() and (slot / "start-returned.json").exists(),
                    "uncertain queue/start: read-only operator recovery, no retry",
                )
                effect = _parse(_operator_bytes(effect_path))
                shape(effect, "schemaVersion intentHash jobId actual", "render effect")
                fact(
                    effect["intentHash"] == _file_hash(intent_path),
                    "render effect ownership differs",
                )
                job_id = identity(effect["jobId"])
                start_intent = _parse(_operator_bytes(slot / "start-intent.json"))
                start_returned = _parse(_operator_bytes(slot / "start-returned.json"))
                fact(
                    start_intent
                    == {"jobId": job_id, "effectHash": _file_hash(effect_path)}
                    and start_returned == {"jobId": job_id, "returned": True}
                    and effect["actual"]["queue"]["JobId"] == job_id,
                    "render start/effect lineage differs",
                )
            actual = self._job(project, job_id, output, settings, target)
            result: JsonObject = {
                "schemaVersion": "issue-189-v2-render-result/v1",
                "evidenceLevel": "injected_execution_unqualified",
                "intentHash": _file_hash(intent_path),
                "effectHash": _file_hash(effect_path),
                "parameters": parameters,
                "jobId": job_id,
                "actual": actual,
                "status": "pending",
            }
            if actual["poll"]["JobStatus"] == "Complete":
                _regular(output)
                raw = _operator_bytes(output, limit=int(count) * 6 + 64 * 1024)
                with wave.open(io.BytesIO(raw), "rb") as stream:
                    fact(
                        (
                            stream.getnchannels(),
                            stream.getsampwidth(),
                            stream.getframerate(),
                            stream.getnframes(),
                            stream.getcomptype(),
                        )
                        == (2, 3, 48000, int(count), "NONE"),
                        "rendered whole-programme WAV PCM/profile/extent differs",
                    )
                    fact(
                        len(stream.readframes(int(count) + 1)) == int(count) * 6,
                        "rendered PCM truncated",
                    )
                fact(
                    _file_hash(output) == _digest(raw),
                    "render bytes changed during independent verification",
                )
                fact(
                    self._read(target, mapping) == observation
                    and self._read(target, mapping) == observation,
                    "native source/control/target drift during render",
                )
                result.update(
                    status="complete", outputHash=_digest(raw), sampleCount=int(count)
                )
                publish_immutable_output(
                    slot / "complete.json", canonical_json_bytes(result)
                )
            self._guard()
            return result
