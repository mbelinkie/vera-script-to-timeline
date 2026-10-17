"""Issue-owned synthetic inputs; frozen #173/#177 cases are read-only sources."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from issue177_package_fixture import (
    _preparation_geometry,
    _refresh_document_closure,
    make_package_case,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.placeholder_slate import render_placeholder_slate
from vera_timeline_agent.roundtrip_build import ROOT, _file_hash
from vera_timeline_agent.roundtrip_v2_build import BRIDGE
from vera_timeline_agent.roundtrip_v2_records import proof_source_hashes_v2

Json = dict[str, Any]


def write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def pin(path: Path) -> Json:
    return {"path": str(path), "sha256": _file_hash(path)}


def make_proof_case(
    root: Path, *, rate: str = "25fps", scenario: str = "default"
) -> tuple[Json, Any]:
    case = make_package_case(root, rate=rate, scenario=scenario)
    dependencies = json.loads(case.dependencies_path.read_bytes())
    if scenario == "default":
        for resolution in dependencies["occurrenceResolutions"]:
            if resolution["sourceSnapshot"]["system"] == "graphic_asset":
                resolution["graphicContentClass"] = "legacy_unclassified"
    sources = proof_source_hashes_v2()
    dependencies["compiler"]["sourceHash"] = sources[
        "packages/contracts/src/compiler-core-v2.ts"
    ]
    manifest = json.loads(case.manifest_path.read_bytes())
    narration_receipts: Json = {}
    for row in dependencies["narrationTimingMaps"]:
        old_source = next(
            s
            for s in manifest["sources"]
            if s.get("narrationAudio", {}).get("narrationAssetId")
            == row["narrationAssetId"]
        )
        audio_path = case.media_paths[f"source:{old_source['id']}"]
        with wave.open(str(audio_path), "wb") as stream:
            stream.setnchannels(row["audio"]["channels"])
            stream.setsampwidth(3)
            stream.setframerate(48000)
            stream.writeframes(
                b"\0" * row["audio"]["durationSamples"] * row["audio"]["channels"] * 3
            )
        row["audioHash"] = row["audio"]["audioHash"] = _file_hash(audio_path)
        timing = root / "timing.json"
        review = root / "timing-review.json"
        receipt = root / "narration-receipt.json"
        write(timing, {"synthetic": True, "tokens": row["tokens"]})
        write(review, {"synthetic": True, "approved": True})
        write(receipt, {"synthetic": True, "blockId": row["blockId"]})
        row["timingHash"] = row["audio"]["timingHash"] = _file_hash(timing)
        narration_receipts[row["blockId"]] = {
            "timing": pin(timing),
            "review": pin(review),
            "receipt": pin(receipt),
        }
    original_sources = {
        source["preparationRequirementKey"]: source
        for source in manifest["sources"]
        if source.get("preparationRequirementKey")
    }
    preparations: Json = {}
    probes: dict[tuple[str, str], Json] = {}
    for binding in dependencies["preparedMedia"]:
        key = binding["requirementKey"]
        receipt_path = case.preparation_paths[key]
        receipt = json.loads(receipt_path.read_bytes())
        prepared_audio_path: Path | None = None
        if scenario.startswith("source-audio-"):
            # A new synthetic reuse case consumes the entire original video,
            # with a separately verified 48k PCM sidecar. No frozen case edit.
            original = case.media_paths[f"original:{original_sources[key]['id']}"]
            delivered = case.media_paths[f"source:{original_sources[key]['id']}"]
            delivered.write_bytes(original.read_bytes())
            binding["mode"] = "verified_reuse"
            binding.pop("derivation", None)
            receipt["commands"] = []
            receipt["deliveredProbe"] = copy.deepcopy(receipt["sourceProbe"])
            frame_map = binding["timeMapping"]["sourceFrameMap"]
            binding["targetRate"] = copy.deepcopy(frame_map["decodedPackageFrameRate"])
            dependencies["timeline"]["frameRate"] = copy.deepcopy(binding["targetRate"])
            receipt["inputs"]["targetRate"] = copy.deepcopy(binding["targetRate"])
            binding["timeMapping"]["deliveredRate"] = copy.deepcopy(
                frame_map["decodedPackageFrameRate"]
            )
            binding["timeMapping"]["mappingHash"] = identity_hash(
                {k: v for k, v in binding["timeMapping"].items() if k != "mappingHash"}
            )
            binding["verification"].update(
                deliveredHash=pin(original)["sha256"],
                probeHash=identity_hash(receipt["sourceProbe"]),
                decodedFrameCount=frame_map["decodedPackageFrameCount"],
                decodedFrameRate=copy.deepcopy(frame_map["decodedPackageFrameRate"]),
                videoTimeBase=copy.deepcopy(frame_map["packageVideoTimeBase"]),
            )
            occurrence = next(
                item
                for item in dependencies["occurrenceResolutions"]
                if item["preparedMediaRequirementKey"] == key
            )
            receipt["geometry"] = _preparation_geometry(binding, occurrence)
            prepared_audio_path = root / "media" / "source-audio.wav"
            audio = receipt["audio"]
            with wave.open(str(prepared_audio_path), "wb") as stream:
                stream.setparams(
                    (audio["channels"], 3, 48000, 0, "NONE", "not compressed")
                )
                stream.writeframes(
                    bytes(audio["channels"] * 3 * audio["decodedSamples"])
                )
            audio["contentHash"] = pin(prepared_audio_path)["sha256"]
        profile = copy.deepcopy(receipt["profile"])
        if binding["mode"] == "verified_reuse":
            version = "issue-148-private-verified-reuse/v1"
        else:
            version = "issue-148-private-png-still-cfr/v1"
        profile["profileVersion"] = version
        binding["profile"]["profileVersion"] = version
        binding["profile"]["profileHash"] = identity_hash(profile)
        receipt["profile"] = profile
        if "derivation" in binding:
            binding["derivation"]["profileHash"] = identity_hash(profile)
        receipt["binding"] = copy.deepcopy(binding)
        receipt["inputs"]["profile"] = copy.deepcopy(binding["profile"])
        write(receipt_path, receipt)
        sid = original_sources[key]["id"]
        original = case.media_paths[f"original:{sid}"]
        delivered = case.media_paths[f"source:{sid}"]
        preparations[key] = {
            "receipt": pin(receipt_path),
            "original": pin(original),
            "delivered": pin(delivered),
            "audio": pin(prepared_audio_path)
            if prepared_audio_path is not None
            else None,
        }
        probes[(str(original), identity_hash(receipt["inputs"]))] = receipt[
            "sourceProbe"
        ]
        probes[(str(delivered), identity_hash(receipt["inputs"]))] = receipt[
            "deliveredProbe"
        ]
    write(case.dependencies_path, dependencies)
    actual = subprocess.run(
        [
            shutil.which("node") or "node",
            str(BRIDGE),
            str(case.document_path),
            str(case.dependencies_path),
        ],
        capture_output=True,
        check=True,
    )
    compiled = json.loads(actual.stdout)["result"]["manifest"]
    if scenario.startswith("source-audio-"):
        dependencies["timeline"] = copy.deepcopy(compiled["timeline"])
        write(case.dependencies_path, dependencies)
    media_paths = dict(case.media_paths)
    for source in compiled["sources"]:
        key = source.get("preparationRequirementKey")
        if key is not None:
            old = original_sources[key]["id"]
            for prefix in ("source", "original"):
                media_paths[f"{prefix}:{source['id']}"] = media_paths.pop(
                    f"{prefix}:{old}"
                )
        elif "narrationAudio" in source:
            old = next(
                s
                for s in manifest["sources"]
                if s.get("narrationAudio", {}).get("narrationAssetId")
                == source["narrationAudio"]["narrationAssetId"]
            )["id"]
            media_paths[f"source:{source['id']}"] = media_paths.pop(f"source:{old}")
    authority = root / "authority.json"
    write(authority, {"synthetic": True})
    inputs = {
        "document": pin(case.document_path),
        "dependencies": pin(case.dependencies_path),
    }
    request = {
        "schemaVersion": "issue-189-v2-prepared-build/v1",
        "lane": "synthetic_local",
        "originalInputs": {k: v["sha256"] for k, v in inputs.items()},
        "originalFiles": copy.deepcopy(inputs),
        "executionInputs": inputs,
        "sourcePins": sources,
        "media": {k: pin(p) for k, p in media_paths.items()},
        "preparations": preparations,
        "narrationReceipts": narration_receipts,
        "authority": pin(authority),
    }
    write(root / "proof-request-v2.json", request)

    def probe(path: Path, parameters: Json) -> Json:
        return copy.deepcopy(probes[(str(path), identity_hash(parameters))])

    return request, probe


def make_sparse_proof_case(root: Path) -> Json:
    """Copy the frozen sparse specimen shape and supply genuine synthetic PCM."""
    fixture = json.loads(
        (
            ROOT
            / "tests/data/authoring_v2/issue_180"
            / "before-gamma-24000-1001.input.golden.json"
        ).read_bytes()
    )
    document, dependencies = fixture["document"], fixture["dependencies"]
    # These new synthetic visuals are intentionally complete. Frozen #180's
    # temporary On Camera fallback has diagnostics that #177 rightly refuses.
    for index, slot in enumerate(
        document["activeDraft"]["blocks"][0]["primaryVisualSequence"]["slots"]
    ):
        if slot["kind"] == "content":
            slot["payload"] = {
                "kind": "visual",
                "payloadId": f"00000000-0000-4000-8000-{160 + index:012x}",
                "pictureKind": "intentional_placeholder",
                "sourceUsage": None,
                "source": {
                    "kind": "intentional_placeholder",
                    "text": "Synthetic sparse proof",
                },
                "audioPolicy": "mute",
                "framingPolicy": "contain",
            }
    sources = proof_source_hashes_v2()
    dependencies["compiler"]["sourceHash"] = sources[
        "packages/contracts/src/compiler-core-v2.ts"
    ]
    row = dependencies["narrationBoundaryEvidence"][0]
    # 48k/24000*1001 = 2002 samples/frame. Our newly generated synthetic
    # asset covers the compiler's complete terminal frame, without a waiver.
    row["audio"]["durationSamples"] = (
        (row["audio"]["durationSamples"] + 2001) // 2002 * 2002
    )
    wav = root / "speech.wav"
    with wave.open(str(wav), "wb") as stream:
        stream.setparams(
            (1, 3, 48000, row["audio"]["durationSamples"], "NONE", "not compressed")
        )
        stream.writeframes(bytes(row["audio"]["durationSamples"] * 3))
    row["audioHash"] = row["audio"]["audioHash"] = _file_hash(wav)
    timing, review, receipt = (
        root / name for name in ("timing.json", "review.json", "receipt.json")
    )
    write(timing, {"synthetic": True, "boundaries": row["tokens"]})
    write(review, {"synthetic": True, "reviewId": row["verification"]["reviewId"]})
    write(receipt, {"synthetic": True, "blockId": row["blockId"]})
    row["timingHash"] = row["audio"]["timingHash"] = _file_hash(timing)
    row["verification"]["reviewArtifactHash"] = _file_hash(review)
    fixture_root = ROOT / "tests/data/authoring_v2/issue_180"
    fixture_manifest = json.loads(
        (fixture_root / "before-gamma-24000-1001.manifest.golden.json").read_bytes()
    )
    dependencies["timeline"] = copy.deepcopy(fixture_manifest["timeline"])
    dependencies["authoringDefaults"] = copy.deepcopy(
        fixture_manifest["authoringDefaults"]
    )
    _refresh_document_closure(
        document,
        dependencies,
        fixture_manifest,
        json.loads(
            (fixture_root / "before-gamma-24000-1001.report.golden.json").read_bytes()
        ),
    )
    doc_path, dep_path = root / "document.json", root / "dependencies.json"
    write(doc_path, document)
    write(dep_path, dependencies)
    actual = subprocess.run(
        [shutil.which("node") or "node", str(BRIDGE), str(doc_path), str(dep_path)],
        capture_output=True,
        check=True,
    )
    manifest = json.loads(actual.stdout)["result"]["manifest"]
    media = {f"source:{row['narrationAssetId']}": pin(wav)}
    for event in manifest["events"]:
        if event["kind"] == "placeholder":
            asset = root / f"slate-{event['eventId']}.png"
            asset.write_bytes(
                render_placeholder_slate(
                    event["pictureTreatment"]["text"],
                    manifest["timeline"]["width"],
                    manifest["timeline"]["height"],
                )
            )
            media[f"event:{event['eventId']}"] = pin(asset)
    authority = root / "authority.json"
    write(authority, {"synthetic": True})
    inputs = {"document": pin(doc_path), "dependencies": pin(dep_path)}
    request = {
        "schemaVersion": "issue-189-v2-prepared-build/v1",
        "lane": "synthetic_local",
        "originalInputs": {k: v["sha256"] for k, v in inputs.items()},
        "originalFiles": copy.deepcopy(inputs),
        "executionInputs": inputs,
        "sourcePins": sources,
        "media": media,
        "preparations": {},
        "narrationReceipts": {
            row["blockId"]: {
                "timing": pin(timing),
                "review": pin(review),
                "receipt": pin(receipt),
            }
        },
        "authority": pin(authority),
    }
    write(root / "proof-request-v2.json", request)
    return request
