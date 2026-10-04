from __future__ import annotations

import copy
import hashlib
import html
import math
import re
import struct
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from test_issue144_proof_session import Boundary, _visual_inputs
from test_issue144_row_narration import _compile, _row, _utf16
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.compiler_dependencies import (
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    VoiceProfile,
)
from vera_timeline_agent.narration.normalize import Normalizer
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig
from vera_timeline_agent.roundtrip_build import (
    _digest,
    _receipt_bytes,
    load_operator_json,
)


class FrameProvider:
    adapter_version = "issue144-frame-tone/v1"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []
        self.revised = False
        self.fail = False

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{html.escape(request.text)}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("injected generation failure")
        seed = hashlib.sha256(request.text.encode()).digest()
        cursor = 0
        marks = []
        for index, match in enumerate(re.finditer(r"\S+", request.text)):
            marks.append(
                ProviderTimingMark(
                    kind="word",
                    time_ms=cursor,
                    start_byte=len(request.text[: match.start()].encode()),
                    end_byte=len(request.text[: match.end()].encode()),
                    start_utf16=_utf16(request.text[: match.start()]),
                    end_utf16=_utf16(request.text[: match.end()]),
                    value=match.group(),
                )
            )
            cursor += 800 + index * 40 if self.revised else 1000
        pcm = b"".join(
            struct.pack(
                "<h", round(6000 * math.sin(2 * math.pi * (220 + seed[0]) * i / 16000))
            )
            for i in range(cursor * 16)
        )
        return ProviderResult(
            audio_bytes=pcm,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=tuple(marks),
            provenance={"provider": "issue144_synthetic", "region": "local-test"},
            request_ids=("synthetic-" + seed.hex(),),
        )


def inputs(root: Path) -> tuple[NarrationService, FrameProvider, str]:
    _visual_inputs(root)
    doc = load_operator_json(root / "script-document.json")
    deps = load_operator_json(root / "compiler-dependencies.json")
    provider = FrameProvider()
    service = NarrationService(
        cache=NarrationCache(root / "narration-cache"),
        provider=provider,
        normalizer=Normalizer(),
        config=ServiceConfig(
            profile=VoiceProfile(
                profile_id="issue144-frame-synthetic/v1",
                provider="issue144_synthetic",
                region="local-test",
                engine="test",
                voice_id="tones",
                voice_version="v1",
                language="en-US",
            )
        ),
    )
    first = doc["activeDraft"]["blocks"][1]
    _row(first, "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel", "omission-first")
    first["hostVisibilitySpans"][0]["state"] = "voiceover"
    first["visualEvents"][0]["range"] = copy.deepcopy(
        first["hostVisibilitySpans"][0]["range"]
    )
    first["visualEvents"][0]["audioPolicy"] = "mute"
    aux = copy.deepcopy(first["visualEvents"][0])
    aux["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "omission/aux"))
    aux["layer"] = 3
    aux["audioPolicy"] = "use_source"
    aux["range"]["startTokenId"] = first["tokens"][4]["id"]
    aux["range"]["quotedText"] = "Echo Foxtrot Golf Hotel"
    first["visualEvents"].append(aux)
    second = copy.deepcopy(first)
    second["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "omission/second"))
    second["orderKey"] = "a2"
    second["hostVisibilitySpans"][0]["id"] = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "omission/second/host")
    )
    second["visualEvents"] = [copy.deepcopy(first["visualEvents"][0])]
    second["visualEvents"][0]["id"] = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "omission/second/visual")
    )
    _row(second, "One Two Three Four Five", "omission-second")
    second["visualEvents"][0]["range"] = copy.deepcopy(
        second["hostVisibilitySpans"][0]["range"]
    )
    second["visualEvents"][0]["layer"] = 2
    doc["activeDraft"]["blocks"].append(second)
    deps["narration"] = []
    origins = {}
    for row in (first, second):
        asset = service.process_block(row)
        assert asset.status == "ready"
        entry = service.cache.read(
            "assets", f"{row['id']}/{asset.asset_id}", "asset.json"
        )
        assert entry
        dependency = narration_dependency_from_asset(asset, entry.files["timing.json"])
        dependency["audio"]["locator"] = f"Media/Narration/{asset.asset_id}.wav"
        deps["narration"].append(dependency)
        origins[asset.asset_id] = entry.path / "narration.wav"
    (root / "script-document.json").write_bytes(_receipt_bytes(doc))
    (root / "compiler-dependencies.json").write_bytes(_receipt_bytes(deps))
    manifest = _compile(root, "node")
    old = load_operator_json(root / "materialization-plan.json")
    plan = {}
    for source in manifest["sources"]:
        if source["id"] in old:
            plan[source["id"]] = old[source["id"]]
        else:
            dep = next(
                row
                for row in deps["narration"]
                if row["audio"]["locator"] == source["path"]
            )
            plan[source["id"]] = {
                "artifactId": dep["assetId"],
                "origin": str(origins[dep["assetId"]]),
                "policy": "copy",
            }
    (root / "materialization-plan.json").write_bytes(_receipt_bytes(plan))
    provider.requests.clear()
    provider.revised = True
    return service, provider, first["id"]


class OmissionBoundary(Boundary):
    def __init__(self, row_id: str) -> None:
        super().__init__()
        self.row_id = row_id
        self.change: Callable[[dict[str, Any]], None] | None = None
        self.evidence_calls: list[dict[str, Any]] = []

    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        manifest = load_operator_json(Path(request["manifestPath"]))
        identity = load_operator_json(Path(request["identityPath"]))
        sources = {source["id"]: source for source in manifest["sources"]}
        items = []
        for event in manifest["events"]:
            source = sources[event["sourceId"]]
            path = (
                source["path"]
                if source["kind"] != "placeholder"
                else f"Media/Placeholders/{source['id']}.png"
            )
            items.append(
                {
                    "eventId": event["id"],
                    **identity["occurrences"][event["id"]],
                    "sourcePath": path,
                    "sourceHash": _digest(
                        (Path(request["packageRoot"]) / path).read_bytes()
                    ),
                    "trackId": event["trackId"],
                    "trackKind": event["trackKind"],
                    "recordRange": copy.deepcopy(event["recordRange"]),
                    "sourceRange": copy.deepcopy(event.get("sourceRange")),
                    "available": True,
                    "enabled": True,
                    "speed": 100,
                    "linkedUids": [],
                }
            )
        byid = {item["eventId"]: item for item in items}
        for event in manifest["events"]:
            group = [
                other
                for other in manifest["events"]
                if other["provenance"]["authoringId"]
                == event["provenance"]["authoringId"]
            ]
            if (
                event["provenance"]["authoringKind"] == "visual_event"
                and len(group) == 2
            ):
                pair = [byid[row["id"]] for row in group]
                pair[0]["linkedUids"] = [pair[1]["itemUid"]]
                pair[1]["linkedUids"] = [pair[0]["itemUid"]]
        narr = next(
            event
            for event in manifest["events"]
            if event["kind"] == "audio"
            and event["provenance"]["authoringKind"] == "narration_block"
            and event["provenance"]["blockId"] == self.row_id
        )
        companion = next(
            event
            for event in manifest["events"]
            if event["kind"] == "video"
            and event["recordRange"] == narr["recordRange"]
            and event["provenance"]["blockId"] == self.row_id
        )
        pair = [byid[narr["id"]], byid[companion["id"]]]
        pair[0]["linkedUids"] = [pair[1]["itemUid"]]
        pair[1]["linkedUids"] = [pair[0]["itemUid"]]
        omission = request["schemaVersion"] == "issue-144-omission-capture-request/v1"
        if omission and self.edit and request["purpose"] != "bind-omission-evidence":
            for old in pair:
                items.remove(old)
            for suffix, start, duration, source_start in (
                ("head", 0, 49, 0),
                ("tail", 50, 125, 75),
            ):
                a, b = [
                    {
                        **copy.deepcopy(old),
                        "itemUid": old["itemUid"] + "-" + suffix,
                        "recordRange": {
                            "startFrame": start,
                            "durationFrames": duration,
                        },
                        "sourceRange": {
                            "startFrame": source_start,
                            "durationFrames": duration,
                        },
                        "linkedUids": [],
                    }
                    for old in pair
                ]
                a["linkedUids"] = [b["itemUid"]]
                b["linkedUids"] = [a["itemUid"]]
                items.extend((a, b))
        observation = {
            "schemaVersion": "issue-144-observation/v1",
            "evidenceLevel": "synthetic_injected",
            "projectUid": identity["projectUid"],
            "timelineUid": identity["timelineUid"],
            "timeline": manifest["timeline"],
            "tracks": manifest["tracks"],
            "items": items,
        }
        if omission:
            observation["schemaVersion"] = "issue-144-omission-observation/v1"
            observation["items"] = [
                {key: value for key, value in item.items() if key != "eventId"}
                for item in items
            ]
            observation["programControls"] = {
                "gainDb": 0,
                "effects": [],
                "limiter": False,
            }
            observation["audioControls"] = [
                {
                    "mediaUid": identity["occurrences"][event["id"]]["mediaUid"],
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
                for event in manifest["events"]
                if event["kind"] == "audio"
            ]
            if self.change:
                self.change(observation)
        return {
            "schemaVersion": "issue-144-omission-capture-response/v1"
            if omission
            else "issue-144-capture-response/v1",
            "nonce": "old-nonce" if self.stale else request["nonce"],
            "requestHash": _digest(_receipt_bytes(request)),
            "observationA": observation,
            "observationB": observation,
        }

    def evidence(self, request: dict[str, Any]) -> Path:
        self.evidence_calls.append(request)
        root = Path(request["destination"])
        root.mkdir(parents=True, exist_ok=True)
        baseline = request["baselineAudio"]
        current = request["currentAudio"]
        sources = []
        samples = {}
        from test_issue144_audio_evidence import _wav
        from vera_timeline_agent.roundtrip_audio import _pcm

        for source in request["expectedSources"]:
            path = f"source-{source['id']}.wav"
            raw = Path(source["origin"]).read_bytes()
            assert _digest(raw) == source["sha256"]
            (root / path).write_bytes(raw)
            samples[source["id"]] = _pcm(raw, 1)[0]
            supports = [
                {
                    "tokenId": token,
                    "startSample": index * 48000 + 4000,
                    "endSample": index * 48000 + 16000,
                }
                for index, token in enumerate(source["tokenIds"])
            ]
            sources.append(
                {
                    "id": source["id"],
                    "rowId": source["rowId"],
                    "path": path,
                    "sha256": source["sha256"],
                    "supports": supports,
                }
            )
        profile = {
            "schemaVersion": "issue-144-audio-profile/v1",
            "evidenceLevel": "synthetic_injected",
            "supportProvenance": "fixture_generator",
            "baselineHash": _digest(_receipt_bytes(baseline)),
            "extentFrames": baseline["extentFrames"],
            "sources": sources,
        }
        for name, value in (
            ("baseline.json", baseline),
            ("profile.json", profile),
            ("observation-a.json", current),
            ("observation-b.json", current),
        ):
            (root / name).write_bytes(_receipt_bytes(value))
        for name, observation, out in (
            ("calibration.json", baseline, "reference.wav"),
            ("render.json", current, "program.wav"),
        ):
            channels = [[0.0] * (baseline["extentFrames"] * 1920) for _ in range(2)]
            for route in observation["routes"]:
                data = samples[route["sourceId"]]
                for segment in route["segments"]:
                    source = data[
                        segment["sourceStart"] * 1920 : segment["sourceEnd"] * 1920
                    ]
                    for ch, gain in enumerate((0.7, 0.6)):
                        for i, value in enumerate(source):
                            channels[ch][segment["recordStart"] * 1920 + i] += (
                                value * gain
                            )
            (root / out).write_bytes(_wav(channels, 3))
            observation_hash = _digest(_receipt_bytes(observation))
            receipt = {
                "schemaVersion": "issue-144-audio-render/v1",
                "target": baseline["target"],
                "baselineHash": profile["baselineHash"],
                "observationHash": observation_hash,
                "profileHash": _digest(_receipt_bytes(profile)),
                "jobId": name,
                "queuedJobId": name,
                "polledJobId": name,
                "status": "complete",
                "settings": {
                    "startFrame": 0,
                    "endFrame": baseline["extentFrames"],
                    "frameRate": "25/1",
                    "sampleRate": 48000,
                    "channels": 2,
                    "codec": "pcm",
                    "sampleWidth": 3,
                },
                "output": {"path": out, "sha256": _digest((root / out).read_bytes())},
            }
            (root / name).write_bytes(_receipt_bytes(receipt))
        return root
