"""Pristine source/graph binding and synthetic omission proposal; no decisions.

Native capture/render authenticity and real support qualification remain #145.
All file hashes prove consistency only; the synthetic supplier is explicit.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.roundtrip_audio import (
    _Files,
    _observation,
    _shape,
    verify_omission_evidence,
)
from vera_timeline_agent.roundtrip_build import (
    JsonObject,
    ProofBuildError,
    _digest,
    _file_hash,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_proof import publish_immutable_output

if TYPE_CHECKING:
    from vera_timeline_agent.roundtrip_proof import ProofSession

ITEM_KEYS = {
    "itemUid",
    "mediaUid",
    "sourcePath",
    "sourceHash",
    "trackId",
    "trackKind",
    "recordRange",
    "sourceRange",
    "available",
    "enabled",
    "speed",
    "linkedUids",
}


def _fact(condition: bool, message: str) -> None:
    if not condition:
        raise ProofBuildError(message)


def _source_key(item: JsonObject) -> tuple[Any, ...]:
    return tuple(
        item[key]
        for key in ("mediaUid", "sourcePath", "sourceHash", "trackId", "trackKind")
    )


class OmissionProof:
    def __init__(self, session: ProofSession) -> None:
        self.session = session
        self.root = session.root
        self.request_path = self.root / "omission-request.json"
        self.request = load_operator_json(self.request_path)
        _shape(self.request, {"schemaVersion", "rowId"}, "omission request")
        _fact(
            self.request["schemaVersion"] == "issue-144-omission-request/v1",
            "unknown omission request",
        )
        self.request_hash = _file_hash(self.request_path)
        self.pointer_hash = _file_hash(session.pointer)
        self.baseline_hash = load_operator_json(session.pointer)["baselineHash"]
        self.baseline, self.build = session._baseline(self.baseline_hash)
        _fact(
            self.build.request["evidenceLevel"] == "synthetic_injected",
            "real audio/source/observer/render qualification remains #145",
        )
        self.manifest = load_operator_json(self.build.manifest_path)
        rows = [
            row
            for row in self.build.document["activeDraft"]["blocks"]
            if row["id"] == self.request["rowId"]
        ]
        _fact(
            len(rows) == 1
            and rows[0]["type"] == "narration"
            and rows[0]["state"] == "active",
            "one active narration row required",
        )
        self.row = rows[0]
        events = [
            event
            for event in self.manifest["events"]
            if event["kind"] == "audio"
            and event["provenance"]["authoringKind"] == "narration_block"
            and event["provenance"]["blockId"] == self.row["id"]
        ]
        _fact(len(events) == 1, "unique actual compiled primary narration required")
        self.primary = events[0]
        self.old_items = {
            item["eventId"]: {
                key: value for key, value in item.items() if key != "eventId"
            }
            for item in self.baseline["observation"]["items"]
        }
        first = self.old_items[self.primary["id"]]
        companions = [
            event
            for event in self.manifest["events"]
            if event["kind"] == "video"
            and event["provenance"]["blockId"] == self.row["id"]
            and self.old_items[event["id"]]["linkedUids"] == [first["itemUid"]]
        ]
        _fact(
            len(companions) == 1,
            "unique baseline linked muted video companion required",
        )
        self.companion = companions[0]
        authored = [
            visual
            for row in self.build.document["activeDraft"]["blocks"]
            for visual in (
                row.get("visualEvents", [])
                if row["type"] == "narration"
                else [row["event"]]
                if row["type"] == "visual"
                else []
            )
            if visual["id"] == self.companion["provenance"]["authoringId"]
        ]
        _fact(
            len(authored) == 1 and authored[0]["audioPolicy"] == "mute",
            "only an authored muted video companion is supported",
        )
        second = self.old_items[self.companion["id"]]
        _fact(
            first["linkedUids"] == [second["itemUid"]]
            and first["recordRange"] == second["recordRange"]
            and first["sourceRange"] == second["sourceRange"],
            "pristine reciprocal full-row proof pair differs",
        )
        self.allowed = {self.primary["id"], self.companion["id"]}
        self.sources = self._sources()
        self.preparation = (
            self.root
            / "omission-preparations"
            / self.pointer_hash[7:]
            / self.request_hash[7:]
        )

    def _sources(self) -> list[JsonObject]:
        self.build._verify_speech()
        self.build._verify_media()
        result = []
        used: set[str] = set()
        for event in self.manifest["events"]:
            if event["kind"] != "audio":
                continue
            source_id = event["sourceId"]
            _fact(source_id not in used, "repeated audio source profile is unsupported")
            used.add(source_id)
            source = next(
                source
                for source in self.manifest["sources"]
                if source["id"] == source_id
            )
            origin = self.build.origins[source_id]
            _fact(
                _file_hash(origin) == source["contentHash"],
                "actual source bytes differ",
            )
            with wave.open(str(origin), "rb") as stream:
                size = stream.getnframes()
                _fact(
                    stream.getnchannels() == 1
                    and stream.getframerate() == 48000
                    and stream.getsampwidth() in {2, 3}
                    and size % 1920 == 0,
                    "frame-aligned mono48k source required; "
                    "EOF partial frames unsupported",
                )
            block_id = event["provenance"]["blockId"]
            token_ids = []
            if event["provenance"]["authoringKind"] == "narration_block":
                block = next(
                    row
                    for row in self.build.document["activeDraft"]["blocks"]
                    if row["id"] == block_id
                )
                token_ids = [token["id"] for token in block["tokens"]]
            result.append(
                {
                    "id": source_id,
                    "rowId": block_id,
                    "origin": str(origin),
                    "sha256": source["contentHash"],
                    "tokenIds": token_ids,
                    "samples": size,
                }
            )
        return result

    def current(self) -> None:
        self.build._assert_current()
        self.build._verify_media()
        self.build._verify_speech()
        _fact(
            _file_hash(self.session.pointer) == self.pointer_hash
            and _file_hash(self.request_path) == self.request_hash,
            "omission baseline/request changed",
        )

    def audio(self, observation: JsonObject, *, pristine: bool) -> JsonObject:
        _shape(
            observation,
            {
                "schemaVersion",
                "evidenceLevel",
                "projectUid",
                "timelineUid",
                "timeline",
                "tracks",
                "items",
                "programControls",
                "audioControls",
            },
            "complete omission observation",
        )
        identity = self.baseline["nativeIdentity"]
        _fact(
            observation["schemaVersion"] == "issue-144-omission-observation/v1"
            and observation["evidenceLevel"] == "synthetic_injected"
            and observation["projectUid"] == identity["projectUid"]
            and observation["timelineUid"] == identity["timelineUid"],
            "omission capture target/lane differs",
        )
        _fact(
            observation["timeline"] == self.manifest["timeline"]
            and observation["tracks"] == self.manifest["tracks"],
            "omission settings/tracks/extent differ",
        )
        items = observation["items"]
        _fact(
            isinstance(items, list) and len(items) <= len(self.old_items) + 128,
            "bounded complete item inventory required",
        )
        by_uid: dict[str, JsonObject] = {}
        groups: dict[str, list[JsonObject]] = {
            identity: [] for identity in self.old_items
        }
        for item in items:
            _shape(item, ITEM_KEYS, "omission occurrence")
            _fact(
                isinstance(item["itemUid"], str)
                and bool(item["itemUid"])
                and item["itemUid"] not in by_uid,
                "duplicate/missing native occurrence",
            )
            _fact(
                item["available"] is True
                and item["enabled"] is True
                and type(item["speed"]) in {int, float}
                and item["speed"] == 100,
                "disabled/offline/retimed occurrence",
            )
            for name in ("recordRange", "sourceRange"):
                value = item[name]
                if value is None:
                    _fact(name == "sourceRange", "missing record geometry")
                    continue
                _shape(value, {"startFrame", "durationFrames"}, "frame range")
                _fact(
                    type(value["startFrame"]) is int
                    and value["startFrame"] >= 0
                    and type(value["durationFrames"]) is int
                    and value["durationFrames"] > 0,
                    "uncertain frame geometry",
                )
            _fact(
                isinstance(item["linkedUids"], list)
                and all(isinstance(uid, str) and uid for uid in item["linkedUids"])
                and len(set(item["linkedUids"])) == len(item["linkedUids"]),
                "uncertain links",
            )
            existing = [
                event
                for event, old in self.old_items.items()
                if item["itemUid"] == old["itemUid"]
            ]
            candidates = existing or [
                event
                for event in self.allowed
                if _source_key(item) == _source_key(self.old_items[event])
            ]
            _fact(
                len(candidates) == 1, "unknown/ambiguous source-based split association"
            )
            event_id = candidates[0]
            _fact(
                _source_key(item) == _source_key(self.old_items[event_id]),
                "source/media/track binding differs",
            )
            if pristine or event_id not in self.allowed:
                _fact(
                    item == self.old_items[event_id],
                    "pristine or untouched native facts differ",
                )
            groups[event_id].append(item)
            by_uid[item["itemUid"]] = item
        _fact(all(groups.values()), "missing managed occurrence")
        for event_id, group in groups.items():
            _fact(
                (not pristine and event_id in self.allowed) or len(group) == 1,
                "extra untouched occurrence",
            )
        pair_groups = [groups[self.primary["id"]], groups[self.companion["id"]]]
        _fact(
            len(pair_groups[0]) == len(pair_groups[1]),
            "linked split pair inventory differs",
        )
        for item in pair_groups[0]:
            _fact(
                len(item["linkedUids"]) == 1 and item["linkedUids"][0] in by_uid,
                "missing/extra linked split companion",
            )
            peer = by_uid[item["linkedUids"][0]]
            _fact(
                peer in pair_groups[1]
                and peer["linkedUids"] == [item["itemUid"]]
                and peer["recordRange"] == item["recordRange"]
                and peer["sourceRange"] == item["sourceRange"],
                "nonreciprocal or unequal linked split pair",
            )
        controls = observation["audioControls"]
        _fact(isinstance(controls, list), "complete audio controls required")
        routes = []
        for event in self.manifest["events"]:
            if event["kind"] != "audio":
                continue
            old = self.old_items[event["id"]]
            for entry in controls:
                _shape(entry, {"mediaUid", "trackId", "controls"}, "route controls")
            matches = [
                entry
                for entry in controls
                if entry["mediaUid"] == old["mediaUid"]
                and entry["trackId"] == old["trackId"]
            ]
            _fact(len(matches) == 1, "missing/duplicate audio route controls")
            segments = []
            for item in sorted(
                groups[event["id"]],
                key=lambda value: value["recordRange"]["startFrame"],
            ):
                _fact(item["sourceRange"] is not None, "missing audio source geometry")
                record, source = item["recordRange"], item["sourceRange"]
                segments.append(
                    {
                        "uid": item["itemUid"],
                        "recordStart": record["startFrame"],
                        "recordEnd": record["startFrame"] + record["durationFrames"],
                        "sourceStart": source["startFrame"],
                        "sourceEnd": source["startFrame"] + source["durationFrames"],
                        "speed": item["speed"],
                        "enabled": item["enabled"],
                        "online": item["available"],
                    }
                )
            routes.append(
                {
                    "id": event["id"],
                    "sourceId": event["sourceId"],
                    "controls": matches[0]["controls"],
                    "segments": segments,
                }
            )
        _fact(len(controls) == len(routes), "unknown/additional audio route")
        audio = {
            "schemaVersion": "issue-144-audio-observation/v1",
            "target": {
                "projectUid": identity["projectUid"],
                "timelineUid": identity["timelineUid"],
            },
            "extentFrames": self.manifest["timeline"]["durationFrames"],
            "programControls": observation["programControls"],
            "routes": routes,
        }
        _fact(
            self.manifest["timeline"]["startFrame"] == 0,
            "zero-start bounded audio profile required",
        )
        _observation(
            audio,
            {source["id"]: source for source in self.sources},
            audio["target"],
            audio["extentFrames"],
            retained=False,
        )
        return audio

    def capture(
        self, purpose: str, binding: str, *, pristine: bool
    ) -> tuple[JsonObject, JsonObject]:
        def validate(observation: JsonObject) -> None:
            self.audio(observation, pristine=pristine)

        return self.session._capture_files(
            self.build,
            purpose,
            binding,
            validate=validate,
            request_schema="issue-144-omission-capture-request/v1",
            response_schema="issue-144-omission-capture-response/v1",
        )

    def evidence(
        self, baseline: JsonObject, current: JsonObject, destination: Path
    ) -> JsonObject:
        if self.session.omission_evidence is None:
            raise NeedsAction(
                "explicit synthetic independent-support/closed-render supplier "
                "required; real qualification remains #145"
            )
        request = {
            "purpose": "issue144-synthetic-audio-evidence",
            "destination": str(destination.parent / "supplier-input"),
            "baselineAudio": baseline,
            "currentAudio": current,
            "expectedSources": self.sources,
            "sources": self.build.source_hashes,
        }
        supplied = self.session.omission_evidence(request).absolute()
        _fact(
            supplied.is_relative_to(self.root),
            "audio evidence must be inside the proof directory",
        )
        files = _Files(supplied)
        for name, expected in (
            ("baseline.json", baseline),
            ("observation-a.json", current),
            ("observation-b.json", current),
        ):
            _fact(
                files.json(name) == expected,
                "audio envelopes differ from actual bound captures",
            )
        profile = files.json("profile.json")
        _shape(
            profile,
            {
                "schemaVersion",
                "evidenceLevel",
                "supportProvenance",
                "baselineHash",
                "extentFrames",
                "sources",
            },
            "profile",
        )
        entries = profile["sources"]
        _fact(
            isinstance(entries, list) and len(entries) == len(self.sources),
            "complete actual source inventory required",
        )
        _fact(
            profile["baselineHash"] == _digest(_receipt_bytes(baseline))
            and profile["extentFrames"] == baseline["extentFrames"]
            and profile["schemaVersion"] == "issue-144-audio-profile/v1"
            and profile["evidenceLevel"] == "synthetic_injected"
            and profile["supportProvenance"] == "fixture_generator",
            "independent synthetic profile binding differs",
        )
        _fact(
            len({entry["id"] for entry in entries}) == len(entries),
            "duplicate profile source",
        )
        for entry in entries:
            _shape(
                entry, {"id", "rowId", "path", "sha256", "supports"}, "profile source"
            )
            expected_source = next(
                (source for source in self.sources if source["id"] == entry["id"]), None
            )
            _fact(expected_source is not None, "unknown profile source")
            assert expected_source is not None
            _fact(
                entry["rowId"] == expected_source["rowId"]
                and entry["sha256"] == expected_source["sha256"]
                and _digest(files.read(entry["path"])) == expected_source["sha256"],
                "actual row/source bytes differ",
            )
            _fact(
                [word["tokenId"] for word in entry["supports"]]
                == expected_source["tokenIds"],
                "complete actual row token supports required",
            )
        for name in ("calibration.json", "render.json"):
            receipt = files.json(name)
            files.read(receipt["output"]["path"])
        for name in tuple(files.hashes):
            raw = files.read(name, json_file=name.endswith(".json"))
            publish_immutable_output(destination / name, raw)
        files.current()
        self.current()
        return {"path": str(destination), "inputs": dict(files.hashes)}

    def prepare(self) -> JsonObject:
        a, b = self.capture("bind-omission-evidence", self.pointer_hash, pristine=True)
        audio = self.audio(a, pristine=True)
        inputs = {
            "baselineHash": self.baseline_hash,
            "baselinePointerHash": self.pointer_hash,
            "requestHash": self.request_hash,
            "observationA": a,
            "observationB": b,
            "baselineAudio": audio,
            "sources": self.build.source_hashes,
        }
        publish_immutable_output(
            self.preparation / "inputs.json", _receipt_bytes(inputs)
        )
        evidence = self.evidence(audio, audio, self.preparation / "evidence")
        receipt = {
            "status": "prepared",
            "evidenceLevel": "synthetic_injected",
            "inputHash": _digest(_receipt_bytes(inputs)),
            "evidence": evidence,
            "limitation": (
                "Preparation binds pristine observed source/graph facts. "
                "Complete calibration and omission verdict are evaluated on "
                "proposal; no real/native qualification."
            ),
        }
        self.current()
        publish_immutable_output(
            self.preparation / "receipt.json", _receipt_bytes(receipt)
        )
        return receipt

    def retained_preparation(self) -> tuple[JsonObject, JsonObject]:
        _fact(
            (self.preparation / "receipt.json").exists(),
            "pristine audio preparation required before editing",
        )
        inputs = load_operator_json(self.preparation / "inputs.json")
        receipt = load_operator_json(self.preparation / "receipt.json")
        expected = {
            "baselineHash": self.baseline_hash,
            "baselinePointerHash": self.pointer_hash,
            "requestHash": self.request_hash,
            "observationA": inputs["observationA"],
            "observationB": inputs["observationB"],
            "baselineAudio": self.audio(inputs["observationA"], pristine=True),
            "sources": self.build.source_hashes,
        }
        _fact(
            inputs == expected
            and inputs["observationA"] == inputs["observationB"]
            and receipt["inputHash"] == _file_hash(self.preparation / "inputs.json")
            and receipt["evidence"]["path"] == str(self.preparation / "evidence"),
            "pristine preparation binding differs",
        )
        for name, digest in receipt["evidence"]["inputs"].items():
            _fact(
                _file_hash(self.preparation / "evidence" / name) == digest,
                "retained pristine audio evidence changed",
            )
        self.current()
        return inputs, receipt

    def propose(self) -> JsonObject:
        prepared, retained = self.retained_preparation()
        a, b = self.capture("propose-omission", self.pointer_hash, pristine=False)
        audio = self.audio(a, pristine=False)
        inputs = {
            "preparationHash": _file_hash(self.preparation / "receipt.json"),
            "baselineHash": self.baseline_hash,
            "baselinePointerHash": self.pointer_hash,
            "requestHash": self.request_hash,
            "scriptHash": self.build.input_hashes["script-document.json"],
            "observationA": a,
            "observationB": b,
            "sources": self.build.source_hashes,
        }
        directory = (
            self.root / "omission-proposal-inputs" / _digest(_receipt_bytes(inputs))[7:]
        )
        publish_immutable_output(directory / "inputs.json", _receipt_bytes(inputs))
        evidence = self.evidence(
            prepared["baselineAudio"], audio, directory / "evidence"
        )
        prior_render = load_operator_json(self.preparation / "evidence" / "render.json")
        replaced_files = {
            "observation-a.json",
            "observation-b.json",
            "render.json",
            prior_render["output"]["path"],
        }
        for name, digest in retained["evidence"]["inputs"].items():
            if name not in replaced_files:
                _fact(
                    evidence["inputs"].get(name) == digest,
                    "pristine profile/source/calibration changed",
                )
        result = verify_omission_evidence(
            directory / "evidence",
            baseline_hash=_digest(_receipt_bytes(prepared["baselineAudio"])),
            target=audio["target"],
            row_id=self.row["id"],
            primary_source_id=self.primary["sourceId"],
            evidence_level="synthetic_injected",
        )
        report: JsonObject = {
            "schemaVersion": "issue-144-omission-proposal/v1",
            "evidenceLevel": "synthetic_injected",
            "classification": "unsupported",
            "bindings": inputs,
            "evidence": evidence,
            "audio": result,
            "rowId": self.row["id"],
            "primarySourceId": self.primary["sourceId"],
            "beforeText": self.row["text"],
            "afterText": None,
            "revision": None,
            "limitation": (
                "Explicit synthetic source-based split association, not ancestry or "
                "live absence qualification. No decision, generation, rebuild "
                "or baseline promotion."
            ),
        }
        if result["status"] == "supported":
            document_path = self.build.root / "script-document.json"
            inspected = self.session._semantic("inspect-script", [document_path])
            edit = {
                "expectedDocumentHash": inspected["result"]["documentHash"],
                "blockId": self.row["id"],
                "tokenIds": result["omittedTokenIds"],
            }
            publish_immutable_output(
                directory / "trusted-edit.json", _receipt_bytes(edit)
            )
            revised = self.session._semantic(
                "revise-omission", [document_path, directory / "trusted-edit.json"]
            )
            report["revision"] = revised
            if revised["ok"]:
                report["classification"] = "supported"
                report["afterText"] = revised["result"]["regeneration"]["text"]
        self.current()
        digest = _digest(_receipt_bytes(report))
        path = self.root / "reports" / f"{digest[7:]}.json"
        publish_immutable_output(path, _receipt_bytes(report))
        receipt = {
            "status": "proposed"
            if report["classification"] == "supported"
            else "refused",
            "reportHash": digest,
            "reportPath": str(path),
            "inputPath": str(directory / "inputs.json"),
            "baselinePointerHash": self.pointer_hash,
        }
        publish_immutable_output(
            path.with_suffix(".receipt.json"), _receipt_bytes(receipt)
        )
        return receipt
