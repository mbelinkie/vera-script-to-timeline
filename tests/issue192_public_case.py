"""Actual public B1/B3 ports over newly created sanitized test media/receipts.

Only injected native/provider/probe/authority ports are fake. No accepted
revision, compiler result, omission report or package result is fabricated.
"""

from __future__ import annotations

import copy
import html
import io
import json
import shutil
import struct
import subprocess
import uuid
import wave
from array import array
from fractions import Fraction
from math import ceil
from pathlib import Path
from typing import Any, override

from issue177_package_fixture import _preparation_geometry, _refresh_document_closure
from issue190_case import pin, write
from issue190_native_fixture import FakeProject, FakeResolve, fake_controls
from test_issue191_narration import FakeNormalizer
from test_workflow_v2 import _FakeAdapter
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    VoiceProfile,
    identity_hash,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import NormalizationResult
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig
from vera_timeline_agent.placeholder_slate import render_placeholder_slate
from vera_timeline_agent.roundtrip_v2_build import BRIDGE, PreparedProofBuildV2
from vera_timeline_agent.roundtrip_v2_native import NativeProofBoundaryV2
from vera_timeline_agent.roundtrip_v2_records import (
    ROOT,
    JsonObject,
    _file_hash,
    proof_source_hashes_v2,
)
from vera_timeline_agent.roundtrip_v2_revised_build import PreparedRevisedProofBuildV2
from vera_timeline_agent.v2_package import _compiler_hash
from vera_timeline_agent.workflow_v2 import load_verified_package_v2

FRAME = 2002
RATE = {"numerator": 24000, "denominator": 1001}
AUTHORITY = b"issue192 independent fake authority; no installed qualification"


def id_for(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012x}"


def wav_bytes(pcm: bytes, channels: int = 1) -> bytes:
    result = io.BytesIO()
    with wave.open(result, "wb") as stream:
        stream.setparams((channels, 3, 48000, 0, "NONE", "not compressed"))
        stream.writeframes(pcm)
    return result.getvalue()


def signal(frames: int, seed: int) -> bytes:
    # Distinct complete PCM per source, including source offsets beyond extent.
    cycle = b"".join(
        ((seed * 101 + i * (seed + 7)) % 4000 - 2000).to_bytes(3, "little", signed=True)
        for i in range(256)
    )
    count = frames * FRAME * 3
    return (cycle * ((count + len(cycle) - 1) // len(cycle)))[:count]


class FakeAuthority:
    def __init__(self) -> None:
        self.records: dict[str, tuple[str, JsonObject]] = {}
        self.stage: JsonObject | None = None
        self.handoff: JsonObject | None = None

    def receipt(self, root: Path, name: str, kind: str, binding: JsonObject) -> None:
        value = {
            "schemaVersion": "issue-192-fake-authority-receipt/v1",
            "kind": kind,
            "binding": binding,
        }
        write(root / name, value)
        self.records[_file_hash(root / name)] = (kind, copy.deepcopy(binding))

    def __call__(self, kind: str, raw: bytes, binding: JsonObject) -> None:
        if raw == AUTHORITY:
            if kind == "proof_preparation":
                assert binding["lane"] == "synthetic_local"
                assert binding["sourcePins"] == proof_source_hashes_v2()
            elif kind in {"native_proof_binding", "native_delivery"}:
                assert binding["sourceHashes"] == proof_source_hashes_v2()
            elif kind == "revised_preparation":
                assert binding["sourcePins"] == proof_source_hashes_v2()
                assert binding["request"]["lane"] == "synthetic_revision"
                assert (
                    binding["result"]["document"]
                    == binding["candidate"]["proposal"]["document"]
                )
                assert (
                    binding["result"]["dependencies"]
                    == binding["candidate"]["proposal"]["dependencies"]
                )
            elif kind == "revised_preflight":
                assert binding["sourceHashes"] == proof_source_hashes_v2()
                assert binding["schemaVersion"] == "issue-192-v2-revised-preflight/v1"
                assert binding["lane"] == "synthetic_revision"
            elif kind == "revised_proof_lineage":
                assert binding["preflight"]["sourceHashes"] == proof_source_hashes_v2()
                assert binding["evidence"]
                assert (
                    binding["candidate"]["proposal"]["document"]
                    == binding["result"]["document"]
                )
                assert binding["decision"]["outcome"] == "accept"
                assert (
                    binding["candidate"]["proposal"]["request"]["handoff"]
                    == self.handoff
                )
            elif kind == "revised_native_lineage":
                assert (
                    binding["binding"]["schemaVersion"]
                    == "issue-192-v2-revised-native-binding/v1"
                )
                assert binding["preflight"]["sourceHashes"] == proof_source_hashes_v2()
            elif kind == "native_observation":
                assert binding["binding"]["sourceHashes"] == proof_source_hashes_v2()
                assert binding["observation"]["target"]["projectUid"].startswith(
                    "fake-"
                )
            elif kind.startswith("roundtrip_"):
                if kind == "roundtrip_row_handoff":
                    assert binding["handoff"] == self.handoff
                elif (
                    kind == "roundtrip_inference_currentness"
                    or kind == "roundtrip_inference_observations"
                ):
                    assert binding["sourcePins"] == proof_source_hashes_v2()
            else:
                assert kind in {"native_item_mapping", "native_pcm_render"}
            return
        if kind == "synthesis_authorization":
            assert raw == b"explicit fake service authorization"
            assert self.stage is not None
            assert binding["request"] == self.stage["regeneration"]
            assert binding["priorDependenciesHash"] == _compiler_hash(
                self.stage["dependencies"]
            )
            assert binding["service"]["config"]["max_cost_usd"] == 0.01
            return
        if kind == "replacement_boundaries":
            assert raw == b"fresh synthetic source-boundary review"
            assert self.stage is not None
            assert binding["request"] == self.stage["regeneration"]
            return
        if kind == "private_preparation":
            record = json.loads(raw)
            assert record["binding"] == binding["binding"]
            assert binding["sourcePins"] == proof_source_hashes_v2()
            assert (
                record["profile"]["profileVersion"]
                == "issue-148-private-verified-reuse/v1"
            )
            return
        if kind == "narration_preparation":
            record = json.loads(raw)
            assert (
                record.get("blockId", binding["row"]["blockId"])
                == binding["row"]["blockId"]
            )
            assert binding["audioHash"] == binding["row"]["audioHash"]
            return
        if kind == "selected_review":
            assert json.loads(raw) == binding
            assert self.records[sha256_bytes(raw)] == (kind, binding)
            return
        assert self.records[sha256_bytes(raw)] == (kind, binding)


class MaterializedCase:
    def __init__(
        self,
        root: Path,
        authority: FakeAuthority,
        *,
        prior: MaterializedCase | None = None,
        document: JsonObject | None = None,
        dependencies: JsonObject | None = None,
        fresh_narration: JsonObject | None = None,
    ) -> None:
        root.mkdir(parents=True)
        self.root = root
        self.authority = authority
        self.preparations: dict[str, JsonObject] = {}
        self.media: dict[str, Path] = {}
        self.source_audio: dict[str, Path] = {}
        self.narration: dict[str, JsonObject] = {}
        if prior is None:
            generated = subprocess.run(
                [
                    shutil.which("node") or "node",
                    str(ROOT / "packages/contracts/test/issue-192-public-fixture.ts"),
                ],
                capture_output=True,
                check=True,
            )
            value = json.loads(generated.stdout)
            self.document, self.dependencies = value["document"], value["dependencies"]
            # Explicit new synthetic picture holds avoid asserting that #177
            # accepts the real specimen's temporary On Camera diagnostics.
            for block in self.document["activeDraft"]["blocks"]:
                if block["type"] != "narration":
                    continue
                for slot in block["primaryVisualSequence"]["slots"]:
                    if (
                        slot["kind"] == "content"
                        and slot["payload"]["kind"] == "on_camera"
                    ):
                        slot["payload"] = {
                            "kind": "visual",
                            "payloadId": id_for(5000 + int(slot["id"][-12:], 16)),
                            "pictureKind": "intentional_placeholder",
                            "sourceUsage": None,
                            "source": {
                                "kind": "intentional_placeholder",
                                "text": "Synthetic #192 static picture hold",
                            },
                            "audioPolicy": "mute",
                            "framingPolicy": "contain",
                        }
            self._initial_media()
            self.dependencies["compiler"]["sourceHash"] = proof_source_hashes_v2()[
                "packages/contracts/src/compiler-core-v2.ts"
            ]
            # Populate actual document identity after binding new synthetic bytes.
            _refresh_document_closure(
                self.document,
                self.dependencies,
                {"document": {}},
                {"document": {}, "manifest": {}},
            )
        else:
            assert (
                document is not None
                and dependencies is not None
                and fresh_narration is not None
            )
            self.document, self.dependencies = (
                copy.deepcopy(document),
                copy.deepcopy(dependencies),
            )
            self.media = dict(prior.media)
            self.source_audio.update(prior.source_audio)
            self.narration = copy.deepcopy(prior.narration)
            self.narration[id_for(10)] = fresh_narration
            self._revised_preparations(prior)
        for name, value in (
            ("document", self.document),
            ("dependencies", self.dependencies),
        ):
            write(root / f"{name}.json", value)
        result = subprocess.run(
            [
                shutil.which("node") or "node",
                str(BRIDGE),
                str(root / "document.json"),
                str(root / "dependencies.json"),
            ],
            capture_output=True,
            check=True,
        )
        self.compiled = json.loads(result.stdout)["result"]
        self.manifest = self.compiled["manifest"]
        if prior is None and self.dependencies["timeline"] != self.manifest["timeline"]:
            self.dependencies["timeline"] = copy.deepcopy(self.manifest["timeline"])
            write(root / "dependencies.json", self.dependencies)
            result = subprocess.run(
                [
                    shutil.which("node") or "node",
                    str(BRIDGE),
                    str(root / "document.json"),
                    str(root / "dependencies.json"),
                ],
                capture_output=True,
                check=True,
            )
            self.compiled = json.loads(result.stdout)["result"]
            self.manifest = self.compiled["manifest"]
        # Revised inputs are actual decision outputs; no post-decision repair.
        assert self.dependencies["timeline"] == self.manifest["timeline"]
        media_pins = self._package_media()
        auth_path = root / "authority.txt"
        auth_path.write_bytes(AUTHORITY)
        inputs = {
            name: pin(root / f"{name}.json") for name in ("document", "dependencies")
        }
        self.request: JsonObject = {
            "schemaVersion": "issue-189-v2-prepared-build/v1",
            "lane": "synthetic_local",
            "originalInputs": {k: p["sha256"] for k, p in inputs.items()},
            "originalFiles": inputs,
            "executionInputs": inputs,
            "sourcePins": proof_source_hashes_v2(),
            "media": media_pins,
            "preparations": self.preparations,
            "narrationReceipts": {
                row: {k: pin(v[k]) for k in ("timing", "review", "receipt")}
                for row, v in self.narration.items()
            },
            "authority": pin(auth_path),
        }
        write(root / "proof-request-v2.json", self.request)
        self.build = PreparedProofBuildV2(
            root, authenticate=authority, read_probe=self.probe
        )
        self.build.prepare_package()
        self.package = load_verified_package_v2(
            self.build.attestation_path, _file_hash(self.build.attestation_path)[7:]
        )

    def _initial_media(self) -> None:
        self.probes: dict[str, JsonObject] = {}
        counts = {30: 250, 31: 1, 41: 200, 51: 2800, 61: 500}
        for binding in self.dependencies["preparedMedia"]:
            key = binding["requirementKey"]
            n = int(key.rsplit(":", 1)[1])
            occurrence = next(
                d
                for d in self.dependencies["occurrenceResolutions"]
                if d["preparedMediaRequirementKey"] == key
            )
            count = counts[n]
            image = n == 31
            original = self.root / f"source-{n}.{'png' if image else 'mov'}"
            original.write_bytes(
                render_placeholder_slate("Synthetic #192 image", 1920, 1080)
                if image
                else (
                    f"synthetic #192 source video {n}; no decoder qualification"
                ).encode()
            )
            pcm = None if image else signal(count, n)
            audio_path = self.root / f"source-{n}.wav"
            if pcm is not None:
                audio_path.write_bytes(wav_bytes(pcm))
            source_probe: JsonObject = {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "png" if image else "synthetic",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "24000/1001",
                        "time_base": "1/24000",
                    }
                ],
                "frames": [
                    {
                        "pts": i * 1001,
                        "best_effort_timestamp": i * 1001,
                        "duration": 1001,
                    }
                    for i in range(count)
                ],
            }
            if not image:
                source_probe["streams"].append(
                    {
                        "codec_type": "audio",
                        "codec_name": "synthetic-pcm",
                        "sample_rate": "48000",
                        "channels": 1,
                        "time_base": "1/48000",
                    }
                )
            probe_hash = identity_hash(source_probe)
            occurrence["sourceSnapshot"].update(
                contentHash=_file_hash(original), probeHash=probe_hash
            )
            occurrence["logicalSourceBounds"]["endFrame"] = count
            frame_map = occurrence["sourceFrameMap"]
            frame_map.update(
                decodedPackageFrameCount=count,
                packageVideoTimeBase={"numerator": 1, "denominator": 24000},
                probeHash=probe_hash,
            )
            frame_map["sourceAudioStreamMappings"] = (
                []
                if image
                else [
                    {
                        "streamIndex": 1,
                        "sampleRate": 48000,
                        "packagePtsOrigin": {"numerator": 0, "denominator": 1},
                        "loggedTimeAtPackageOrigin": {"numerator": 0, "denominator": 1},
                        "audioHash": sha256_bytes(pcm or b""),
                        "probeHash": probe_hash,
                    }
                ]
            )
            profile = {
                "profileVersion": "issue-148-private-verified-reuse/v1",
                "video": {"codec": "synthetic", "pixelFormat": "synthetic"},
            }
            policy = {
                "policyVersion": "synthetic-192-policy/v1",
                "audio": "not_applicable" if image else "aligned",
            }
            tools = {
                "ffprobe": {"path": "test-double", "version": "not executed"},
                "ffmpeg": {"path": "test-double", "version": "not executed"},
            }
            binding["profile"] = {
                "profileVersion": profile["profileVersion"],
                "profileHash": identity_hash(profile),
                "policyHash": identity_hash(policy),
                "toolHash": identity_hash(tools),
            }
            binding["originalSource"].update(
                contentHash=_file_hash(original), probeHash=probe_hash
            )
            binding["timeMapping"]["sourceFrameMap"] = copy.deepcopy(frame_map)
            binding["timeMapping"]["mappingHash"] = identity_hash(
                {k: v for k, v in binding["timeMapping"].items() if k != "mappingHash"}
            )
            binding["verification"].update(
                deliveredHash=_file_hash(original),
                probeHash=probe_hash,
                decodedFrameCount=count,
                videoTimeBase={"numerator": 1, "denominator": 24000},
            )
            if not image:
                binding["verification"]["sourceAudio"] = {
                    "status": "aligned",
                    "offset": {"numerator": 0, "denominator": 1},
                    "maxDrift": {"numerator": 0, "denominator": 1},
                    "sampleRate": 48000,
                }
            audio_record = (
                None
                if image
                else {
                    "sourceAudioHash": sha256_bytes(pcm or b""),
                    "contentHash": _file_hash(audio_path),
                    "probe": {
                        "streams": [
                            {
                                "codec_name": "pcm_s24le",
                                "sample_rate": "48000",
                                "channels": 1,
                            }
                        ]
                    },
                    "channels": 1,
                    "sourcePtsOrigin": {"numerator": 0, "denominator": 1},
                    "deliveredTimeAtFirstSample": {"numerator": 0, "denominator": 1},
                    "boundaryOffset": {"numerator": 0, "denominator": 1},
                    "endpointError": {"numerator": 0, "denominator": 1},
                    "decodedSourceTimestampResidual": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "decodedSourceTimestampDrift": {"numerator": 0, "denominator": 1},
                    "sourceFirstSample": 0,
                    "sourceExclusiveSample": count * FRAME,
                    "resampledFirstSample": 0,
                    "resampledExclusiveSample": count * FRAME,
                    "decodedSamples": count * FRAME,
                }
            )
            if audio_record is not None:
                audio_record["probeHash"] = identity_hash(audio_record["probe"])
            record = {
                "recordVersion": "authoring-media-preparation/v1",
                "requirementKey": key,
                "binding": binding,
                "sourceProbe": source_probe,
                "deliveredProbe": source_probe,
                "tools": tools,
                "profile": profile,
                "policy": policy,
                "commands": [],
                "audio": audio_record,
            }
            self._receipt(
                binding, occurrence, record, original, audio_path if not image else None
            )
            self.media[f"video:{key}"] = original
            self.probes[str(original)] = source_probe
        for row in self.dependencies["narrationBoundaryEvidence"]:
            n = 1 if row["blockId"] == id_for(10) else 2
            audio = self.root / f"narration-{n}.wav"
            audio.write_bytes(
                wav_bytes(signal(row["audio"]["durationSamples"] // FRAME, 80 + n))
            )
            timing, review, receipt = (
                self.root / f"narration-{n}-{name}.json"
                for name in ("timing", "review", "receipt")
            )
            write(timing, {"synthetic": True, "tokens": row["tokens"]})
            write(review, {"synthetic": True, "blockId": row["blockId"]})
            write(receipt, {"synthetic": True, "blockId": row["blockId"]})
            row["audioHash"] = row["audio"]["audioHash"] = _file_hash(audio)
            row["timingHash"] = row["audio"]["timingHash"] = _file_hash(timing)
            row["verification"]["reviewArtifactHash"] = _file_hash(review)
            self.narration[row["blockId"]] = {
                "audio": audio,
                "timing": timing,
                "review": review,
                "receipt": receipt,
            }

    def _receipt(
        self,
        binding: JsonObject,
        occurrence: JsonObject,
        record: JsonObject,
        original: Path,
        audio: Path | None,
    ) -> None:
        key = binding["requirementKey"]
        record = copy.deepcopy(record)
        record["binding"] = copy.deepcopy(binding)
        record["inputs"] = {
            "mediaReferenceId": occurrence["mediaReferenceId"],
            "sourceSnapshot": occurrence["sourceSnapshot"],
            "sourceFrameMap": occurrence["sourceFrameMap"],
            "requestedRange": binding["requestedRange"],
            "targetRate": binding["targetRate"],
            "profile": binding["profile"],
            "videoStreamIndex": 0,
            "audioStreamIndex": None if audio is None else 1,
        }
        record["geometry"] = _preparation_geometry(binding, occurrence)
        if audio is not None:
            self.source_audio[key] = audio
            geometry = record["geometry"]
            start, end = (
                Fraction(geometry[name]["numerator"], geometry[name]["denominator"])
                for name in ("packageStart", "packageEnd")
            )
            first, exclusive = ceil(start * 48000), ceil(end * 48000)
            with wave.open(str(audio), "rb") as stream:
                assert stream.getsampwidth() == 3 and stream.getframerate() == 48000
                assert 0 <= first < exclusive <= stream.getnframes()
                stream.setpos(first)
                selected_pcm = stream.readframes(exclusive - first)
                channels = stream.getnchannels()
            sidecar = self.root / f"prepared-{key.replace(':', '-')}.wav"
            sidecar.write_bytes(wav_bytes(selected_pcm, channels))
            offset = Fraction(first, 48000) - start
            delivered_first = start + offset
            record["audio"].update(
                contentHash=_file_hash(sidecar),
                sourceFirstSample=first,
                sourceExclusiveSample=exclusive,
                resampledFirstSample=first,
                resampledExclusiveSample=exclusive,
                decodedSamples=exclusive - first,
                boundaryOffset={
                    "numerator": offset.numerator,
                    "denominator": offset.denominator,
                },
                deliveredTimeAtFirstSample={
                    "numerator": delivered_first.numerator,
                    "denominator": delivered_first.denominator,
                },
            )
            audio = sidecar
            self.media[f"audio:{key}"] = sidecar
        path = self.root / f"prep-{key.replace(':', '-')}.json"
        write(path, record)
        self.preparations[key] = {
            "receipt": pin(path),
            "original": pin(original),
            "delivered": pin(original),
            "audio": None if audio is None else pin(audio),
        }

    def _revised_preparations(self, prior: MaterializedCase) -> None:
        self.probes = copy.deepcopy(prior.probes)
        for binding in self.dependencies["preparedMedia"]:
            key = binding["requirementKey"]
            occurrence = next(
                d
                for d in self.dependencies["occurrenceResolutions"]
                if d["preparedMediaRequirementKey"] == key
            )
            record = json.loads(
                Path(prior.preparations[key]["receipt"]["path"]).read_bytes()
            )
            self._receipt(
                binding,
                occurrence,
                record,
                prior.media[f"video:{key}"],
                prior.source_audio.get(key),
            )

    def probe(self, path: Path, _: JsonObject) -> JsonObject:
        return copy.deepcopy(self.probes[str(path)])

    def _package_media(self) -> JsonObject:
        result: JsonObject = {}
        for source in self.manifest["sources"]:
            key = source.get("preparationRequirementKey")
            if key is not None:
                result[f"source:{source['id']}"] = pin(self.media[f"video:{key}"])
                result[f"original:{source['id']}"] = pin(self.media[f"video:{key}"])
            else:
                row = next(
                    r
                    for r in self.dependencies["narrationBoundaryEvidence"]
                    if r["narrationAssetId"] == source["id"]
                )
                result[f"source:{source['id']}"] = pin(
                    self.narration[row["blockId"]]["audio"]
                )
        for event in self.manifest["events"]:
            if event["kind"] == "source_audio":
                key = next(
                    b["requirementKey"]
                    for b in self.dependencies["preparedMedia"]
                    if b["timeMapping"] == event["sourceTimeMapping"]
                )
                result[f"event:{event['eventId']}"] = pin(self.media[f"audio:{key}"])
            elif event["kind"] == "placeholder":
                path = self.root / f"slate-{event['eventId']}.png"
                path.write_bytes(
                    render_placeholder_slate(
                        event["pictureTreatment"]["text"], 1920, 1080
                    )
                )
                result[f"event:{event['eventId']}"] = pin(path)
        return result

    def native(
        self, root: Path, *, revised: PreparedRevisedProofBuildV2 | None = None
    ) -> tuple[NativeProofBoundaryV2, FakeResolve, _FakeAdapter]:
        build = revised or self.build
        package = load_verified_package_v2(
            build.attestation_path, _file_hash(build.attestation_path)[7:]
        )
        resolve = FakeResolve(package)
        resolve.project = MixingProject(package)
        resolve.project.uid += ":" + root.name
        resolve.project.timeline.uid += ":" + root.name
        adapter = _FakeAdapter()
        view = {e["id"]: e for e in package.view["events"]}
        timeline = resolve.project.timeline
        for items in timeline.items.values():
            for item in items:
                # Real split clips keep their MediaPoolItem identity. The old
                # generic fake returns the clip itself, so supply a separate
                # immutable fake media object before any public capture.
                media = StableMedia(item.source, item.root)

                def get_media(media: StableMedia = media) -> StableMedia:
                    return media

                vars(item)["GetMediaPoolItem"] = get_media
                block_id = view[timeline.mapping[item.uid]["eventId"]]["v2Event"][
                    "provenance"
                ]["blockId"]
                if block_id in {id_for(40), id_for(50), id_for(60)}:
                    item.links = [
                        peer
                        for others in timeline.items.values()
                        for peer in others
                        if peer is not item
                        and view[timeline.mapping[peer.uid]["eventId"]]["v2Event"][
                            "provenance"
                        ]["blockId"]
                        == block_id
                    ]

        def controls(project: Any, current: Any, target: JsonObject) -> JsonObject:
            result = fake_controls(project, current, target)
            for route in result["routes"]:
                event = view[current.mapping[route["itemUid"]]["eventId"]]
                route["controls"]["gainDb"] = event["gainDb"] or 0
            return result

        arguments: JsonObject = dict(
            resolve=resolve,
            attestation_path=build.attestation_path,
            attestation_hash=_file_hash(build.attestation_path),
            proof_package_path=build.execution / "proof-package.json",
            proof_package_hash=_file_hash(build.execution / "proof-package.json"),
            evidence_root=root,
            authenticate=self.authority,
            authority=AUTHORITY,
            code_hashes=proof_source_hashes_v2(),
            read_controls=controls,
            adapter_factory=lambda _: adapter,
        )
        if revised is None:
            boundary = NativeProofBoundaryV2(**arguments)
        else:
            boundary = NativeProofBoundaryV2.from_revised_proof(
                **arguments,
                revised_preflight_path=build.preflight_path,
                revised_preflight_hash=_file_hash(build.preflight_path),
            )
        return boundary, resolve, adapter


class StableMedia:
    def __init__(self, source: JsonObject, root: Path) -> None:
        self.source, self.root = source, root

    def GetUniqueId(self) -> str:
        return "independent-fake-media:" + str(self.source["id"])

    def GetClipProperty(self) -> JsonObject:
        return {
            "File Path": str(self.root / self.source["path"]),
            "Online Status": "Online",
        }


class MixingProject(FakeProject):
    def __init__(self, package: Any) -> None:
        super().__init__(package)
        self.job_status: dict[str, str] = {}
        self.gains = {e["id"]: e["gainDb"] or 0 for e in package.view["events"]}
        self.kinds = {e["id"]: e["kind"] for e in package.view["events"]}

    @override
    def AddRenderJob(self) -> str:
        super().AddRenderJob()
        key = f"independently-queued-fake-job-{len(self.queue)}"
        self.queue[-1]["JobId"] = key
        self.job_status[key] = "Ready"
        return key

    @override
    def GetRenderJobStatus(self, job_id: str) -> JsonObject:
        assert any(j["JobId"] == job_id for j in self.queue)
        status = self.job_status[job_id]
        return {
            "JobStatus": status,
            "CompletionPercentage": 100 if status == "Complete" else 0,
        }

    @override
    def StartRendering(self, job_ids: list[str], interactive: bool) -> bool:
        assert not interactive and len(job_ids) == 1
        assert any(j["JobId"] == job_ids[0] for j in self.queue)
        assert self.job_status[job_ids[0]] == "Ready"
        self.calls.append("start")
        self.job_status[job_ids[0]] = "Rendering"
        self.write_output()
        self.job_status[job_ids[0]] = "Complete"
        return True

    @override
    def write_output(self) -> None:
        render_mix(self, self.gains)


def render_mix(project: FakeProject, gains: dict[str, int]) -> None:
    timeline = project.timeline
    count = (project.settings["MarkOut"] - project.settings["MarkIn"] + 1) * FRAME
    mixed = array("d", [0.0]) * count
    for (kind, _), items in timeline.items.items():
        if kind != "audio":
            continue
        for item in items:
            with wave.open(str(item.root / item.source["path"]), "rb") as stream:
                stream.setpos(item.source_start * FRAME)
                raw = stream.readframes(item.duration * FRAME)
            event_id = timeline.mapping[item.uid]["eventId"]
            # Full source gain comes from independently set fake event inventory.
            gain_db = gains[event_id]
            if event_id == "":
                raise AssertionError("complete mapped audio required")
            gain = 10 ** (gain_db / 20)
            start = item.start * FRAME
            for offset in range(0, len(raw), 3):
                mixed[start + offset // 3] += (
                    int.from_bytes(raw[offset : offset + 3], "little", signed=True)
                    * gain
                )
    pcm = b"".join(round(v).to_bytes(3, "little", signed=True) * 2 for v in mixed)
    output = Path(project.settings["TargetDir"]) / (
        project.settings["CustomName"] + ".wav"
    )
    output.write_bytes(wav_bytes(pcm, 2))


class FixedFrameProvider:
    adapter_version = "issue-192-fake-provider/v1"

    def __init__(self, frames: int) -> None:
        self.frames = frames
        self.calls = 0
        self.fail = False

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{html.escape(request.text)}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("uncertain injected fake provider result")
        pcm = b"".join(
            struct.pack("<h", (i % 127) * 7 - 400) for i in range(self.frames * FRAME)
        )
        return ProviderResult(
            audio_bytes=pcm,
            audio_format="pcm_s16le",
            sample_rate=48000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    "sentence",
                    0,
                    0,
                    len(request.text.encode()),
                    0,
                    len(request.text.encode("utf-16-le")) // 2,
                    request.text,
                ),
            ),
            provenance={
                "provider": "issue192_fake",
                "region": "local-test",
                "engine": "fake",
                "voiceId": "fake",
                "voiceVersion": "1",
                "adapterVersion": self.adapter_version,
            },
            request_ids=(f"actual-fake-call-{self.calls}",),
        )


class ExactFrameNormalizer(FakeNormalizer):
    def normalize_pcm(
        self, audio_bytes: bytes, *, sample_rate: int, channels: int
    ) -> NormalizationResult:
        assert sample_rate == 48000 and channels == 1
        return self.result(
            b"".join(
                (value * 256).to_bytes(3, "little", signed=True)
                for (value,) in struct.iter_unpack("<h", audio_bytes)
            )
        )


def service_case(
    root: Path, frames: int
) -> tuple[NarrationService, FixedFrameProvider]:
    provider = FixedFrameProvider(frames)
    service = NarrationService(
        cache=NarrationCache(root),
        provider=provider,
        normalizer=ExactFrameNormalizer(),
        config=ServiceConfig(
            profile=VoiceProfile(
                "fake", "issue192_fake", "local-test", "fake", "fake", "1", "en-US"
            ),
            data_policy_attestation="explicit fake only",
            max_cost_usd=0.01,
        ),
    )
    return service, provider


def fresh_boundary(
    stage: JsonObject, service: NarrationService, receipt: JsonObject
) -> JsonObject:
    row = next(
        b
        for b in stage["document"]["activeDraft"]["blocks"]
        if b["id"] == stage["regeneration"]["blockId"]
    )
    cached = service.cache.read(
        "assets", f"{row['id']}/{receipt['assetId']}", "asset.json"
    )
    assert cached is not None
    metadata = cached.metadata["asset"]
    asset_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, "vera:narration-cache-asset:" + receipt["assetId"]
        )
    )
    first = row["tokens"][0]
    return {
        "schemaVersion": "narration-boundary-evidence/v1",
        "blockId": row["id"],
        "blockRevision": row["version"],
        "textHash": stage["regeneration"]["textHash"],
        "tokenizationVersion": "script-document/v2-frozen-tokens",
        "narrationAssetId": asset_id,
        "audioHash": receipt["audioHash"],
        "timingHash": receipt["providerTimingHash"],
        "alignmentVersion": "synthetic-source-review/v1",
        "audio": {
            "narrationAssetId": asset_id,
            "cacheAssetId": receipt["assetId"],
            "audioHash": receipt["audioHash"],
            "timingHash": receipt["providerTimingHash"],
            "durationSamples": metadata["duration_samples"],
            "sampleRate": 48000,
            "channels": 1,
            "locator": f"Media/Narration/{receipt['assetId']}.wav",
        },
        "tokens": [
            {
                "tokenId": first["id"],
                "quotedText": first["value"],
                "startOffset": first["startOffset"],
                "endOffset": first["endOffset"],
                "onset": {"numerator": 0, "denominator": 1},
            }
        ],
        "verification": {
            "method": "reviewed_audio_boundaries/v1",
            "reviewId": id_for(999),
            "reviewRevision": 1,
            "reviewerReference": "synthetic fake review",
            "reviewArtifactLocator": "Reviews/issue192-fresh.json",
            "reviewArtifactHash": sha256_bytes(
                b"fresh synthetic source-boundary review"
            ),
        },
    }
