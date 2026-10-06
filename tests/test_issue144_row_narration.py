from __future__ import annotations

import copy
import hashlib
import html
import json
import math
import re
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from test_issue144_proof_session import _visual_inputs
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
from vera_timeline_agent.narration.polly import PollyProvider
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig
from vera_timeline_agent.roundtrip_build import (
    COMPILER_ENTRY,
    PreparedBuild,
    ProofBuildError,
    _parse,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_narration import replace_row_narration


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class WholeTextProvider:
    """Synthetic tones/marks derived from complete text, never spoken evidence."""

    adapter_version = "issue144-whole-text-test/v1"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []
        self.fail = False
        self.marks = True
        self.provenance = True
        self.change_input: Path | None = None
        self.canned: ProviderResult | None = None
        self.results: dict[str, ProviderResult] = {}

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{html.escape(request.text)}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("injected generation failure")
        if self.canned is not None:
            return self.canned
        seed = hashlib.sha256(request.text.encode()).digest()
        frequency = 220 + seed[0]
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
            cursor += 400 + seed[index % len(seed)]
        pcm = b"".join(
            struct.pack(
                "<h", round(7000 * math.sin(2 * math.pi * frequency * i / 16000))
            )
            for i in range(cursor * 16)
        )
        if self.change_input is not None:
            self.change_input.write_bytes(self.change_input.read_bytes() + b" ")
        result = ProviderResult(
            audio_bytes=pcm,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=tuple(marks) if self.marks else (),
            provenance={"provider": "issue144_synthetic", "region": "local-test"}
            if self.provenance
            else {},
            request_ids=(f"synthetic-{seed.hex()}",),
        )
        self.results[request.block_id] = result
        return result


def _row(block: dict[str, Any], text: str, prefix: str) -> None:
    block["text"] = text
    block["tokens"] = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{prefix}/{index}")),
            "value": match.group(),
            "startOffset": _utf16(text[: match.start()]),
            "endOffset": _utf16(text[: match.end()]),
        }
        for index, match in enumerate(re.finditer(r"\S+", text))
    ]
    anchor = {
        "blockId": block["id"],
        "startTokenId": block["tokens"][0]["id"],
        "endTokenId": block["tokens"][-1]["id"],
        "startAffinity": "before",
        "endAffinity": "after",
        "quotedText": text,
        "anchorVersion": 1,
    }
    block["hostVisibilitySpans"][0]["range"] = copy.deepcopy(anchor)
    block["visualEvents"][0]["range"] = {
        **anchor,
        "startTokenId": block["tokens"][1]["id"],
        "quotedText": text.split(" ", 1)[1],
    }


def _compile(root: Path, node: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            node,
            str(COMPILER_ENTRY),
            str(root / "script-document.json"),
            str(root / "compiler-dependencies.json"),
        ],
        check=True,
        capture_output=True,
    )
    return _parse(json.loads(completed.stdout)["manifestJson"].encode())


def _setup(
    tmp_path: Path, *, astral: bool = False
) -> tuple[PreparedBuild, NarrationService, WholeTextProvider, Path]:
    root = tmp_path / "proof"
    _visual_inputs(root)
    provider = WholeTextProvider()
    subject = NarrationService(
        cache=NarrationCache(root / "narration-cache"),
        provider=provider,
        normalizer=Normalizer(),
        config=ServiceConfig(
            profile=VoiceProfile(
                profile_id="issue144-synthetic/v1",
                provider="issue144_synthetic",
                region="local-test",
                engine="test",
                voice_id="tones",
                voice_version="v1",
                language="en-US",
            )
        ),
    )
    doc = load_operator_json(root / "script-document.json")
    first = doc["activeDraft"]["blocks"][1]
    _row(
        first,
        "Alpha 😀 Bravo Charlie Delta Echo"
        if astral
        else "Alpha Bravo Charlie Delta Echo",
        "first",
    )
    second = copy.deepcopy(first)
    second["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "issue144/second"))
    second["orderKey"] = "a2"
    for kind in ("hostVisibilitySpans", "visualEvents"):
        second[kind][0]["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"second/{kind}"))
    _row(second, "Foxtrot Golf Hotel", "second")
    doc["activeDraft"]["blocks"].append(second)
    dependencies = load_operator_json(root / "compiler-dependencies.json")
    dependencies["narration"] = []
    origins = {}
    for block in (first, second):
        asset = subject.process_block(block)
        assert asset.status == "ready"
        entry = subject.cache.read(
            "assets", f"{block['id']}/{asset.asset_id}", "asset.json"
        )
        assert entry is not None
        dependency = narration_dependency_from_asset(asset, entry.files["timing.json"])
        dependency["audio"]["locator"] = f"Media/Narration/{asset.asset_id}.wav"
        dependencies["narration"].append(dependency)
        origins[asset.asset_id] = entry.path / "narration.wav"
    (root / "script-document.json").write_bytes(_receipt_bytes(doc))
    (root / "compiler-dependencies.json").write_bytes(_receipt_bytes(dependencies))
    manifest = _compile(root, "node")
    plan = load_operator_json(root / "materialization-plan.json")
    plan = {
        key: value
        for key, value in plan.items()
        if value["origin"].endswith(("base.mov", "a1_alpha.wav"))
    }
    for source in manifest["sources"]:
        matched_dependency = next(
            (
                row
                for row in dependencies["narration"]
                if row["audio"]["locator"] == source.get("path")
            ),
            None,
        )
        if matched_dependency is not None:
            plan[source["id"]] = {
                "artifactId": matched_dependency["assetId"],
                "origin": str(origins[matched_dependency["assetId"]]),
                "policy": "copy",
            }
    (root / "materialization-plan.json").write_bytes(_receipt_bytes(plan))
    provider.requests.clear()
    revised = copy.deepcopy(doc)
    block = revised["activeDraft"]["blocks"][1]
    target = next(token for token in block["tokens"] if token["value"] == "Charlie")
    # Test input only: this does not qualify an omission or replace explicit
    # semantic decisions. Retain surviving identity and adjust UTF-16 offsets.
    block["text"] = block["text"].replace("Charlie ", "")
    block["tokens"].remove(target)
    for token in block["tokens"]:
        if token["startOffset"] > target["startOffset"]:
            token["startOffset"] -= 8
            token["endOffset"] -= 8
    block["version"] += 1
    for kind in ("hostVisibilitySpans", "visualEvents"):
        entity = block[kind][0]
        entity["version"] += 1
        entity["range"]["quotedText"] = entity["range"]["quotedText"].replace(
            "Charlie ", ""
        )
        entity["range"]["anchorVersion"] += 1
    revised["liveHeadSequence"] += 1
    revised["liveStateVector"] = ""
    path = root / "revised-document.json"
    path.write_bytes(_receipt_bytes(revised))
    return PreparedBuild(root), subject, provider, path


def test_new_full_row_marks_retime_anchors_and_translate_only_following_row(
    tmp_path: Path,
) -> None:
    prior, service, provider, path = _setup(tmp_path)
    before = {name: (prior.root / name).read_bytes() for name in prior.raw}
    old = _compile(prior.root, prior.node)
    result = replace_row_narration(prior, path, service)
    assert [request.text for request in provider.requests] == ["Alpha Bravo Delta Echo"]
    assert result["evidenceLevel"] == "synthetic_injected"
    deps = result["dependencies"]
    assert deps["narration"][1] == prior.dependencies["narration"][1]
    assert (
        deps["narration"][0]["audioHash"]
        != prior.dependencies["narration"][0]["audioHash"]
    )
    assert (
        deps["narration"][0]["timing"] != prior.dependencies["narration"][0]["timing"]
    )
    second = prior.document["activeDraft"]["blocks"][2]
    staging = tmp_path / "rebuilt"
    staging.mkdir()
    (staging / "script-document.json").write_bytes(path.read_bytes())
    (staging / "compiler-dependencies.json").write_bytes(_receipt_bytes(deps))
    new = _compile(staging, prior.node)
    old_second = [
        event
        for event in old["events"]
        if event["provenance"]["blockId"] == second["id"]
    ]
    new_second = [
        event
        for event in new["events"]
        if event["provenance"]["blockId"] == second["id"]
    ]
    old_start = min(event["recordRange"]["startFrame"] for event in old_second)
    new_start = min(event["recordRange"]["startFrame"] for event in new_second)
    assert old_start != new_start
    for events, start in ((old_second, old_start), (new_second, new_start)):
        for event in events:
            event["recordRange"]["startFrame"] -= start
    assert old_second == new_second
    changed_visual = prior.document["activeDraft"]["blocks"][1]["visualEvents"][0]["id"]
    old_visual = next(event for event in old["events"] if event["id"] == changed_visual)
    new_visual = next(event for event in new["events"] if event["id"] == changed_visual)
    assert (
        old_visual["recordRange"]["startFrame"]
        != new_visual["recordRange"]["startFrame"]
    )
    assert (
        new_visual["recordRange"]["durationFrames"]
        != old_visual["recordRange"]["durationFrames"]
    )
    origins = {
        replacement["assetId"]: replacement["origin"]
        for replacement in result["replacements"]
    }
    origins.update(
        {entry["artifactId"]: entry["origin"] for entry in prior.plan.values()}
    )
    plan = {}
    for source in new["sources"]:
        if source["kind"] == "placeholder":
            continue
        dep = next(
            (
                row
                for row in deps["narration"]
                if row["audio"]["locator"] == source["path"]
            ),
            None,
        )
        asset_id = dep["assetId"] if dep else source["id"]
        plan[source["id"]] = {
            "artifactId": asset_id,
            "origin": origins[asset_id],
            "policy": "copy",
        }
    (staging / "materialization-plan.json").write_bytes(_receipt_bytes(plan))
    (staging / "proof-request.json").write_bytes(_receipt_bytes(prior.request))
    rebuilt = PreparedBuild(staging)
    assert rebuilt.run()["status"] == "waiting"  # Native boundary deliberately absent.
    assert rebuilt.verified_package().build_id == new["buildId"]
    assert replace_row_narration(prior, path, service) == result
    assert len(provider.requests) == 1
    assert {name: (prior.root / name).read_bytes() for name in prior.raw} == before

    # A second wording edit against the newly prepared row gets another whole
    # recording; a session's cache remains inside its explicit enclosing proof.
    later = load_operator_json(staging / "script-document.json")
    row = later["activeDraft"]["blocks"][1]
    row["text"] = row["text"].replace("Delta", "Zulu")
    for token in row["tokens"]:
        if token["value"] == "Delta":
            token["value"] = "Zulu"
            token["endOffset"] -= 1
        elif token["value"] == "Echo":
            token["startOffset"] -= 1
            token["endOffset"] -= 1
    row["version"] += 1
    for kind in ("hostVisibilitySpans", "visualEvents"):
        row[kind][0]["range"]["quotedText"] = row[kind][0]["range"][
            "quotedText"
        ].replace("Delta", "Zulu")
    later_path = prior.root / "later-revision.json"
    later_path.write_bytes(_receipt_bytes(later))
    # Relocate only the test's enclosing owner boundary, not its prepared files.
    next_result = replace_row_narration(
        rebuilt, later_path, service, proof_root=tmp_path
    )
    assert [request.text for request in provider.requests] == [
        "Alpha Bravo Delta Echo",
        "Alpha Bravo Zulu Echo",
    ]
    assert (
        next_result["dependencies"]["narration"][0]["assetId"]
        != deps["narration"][0]["assetId"]
    )
    assert next_result["dependencies"]["narration"][1] == deps["narration"][1]


@pytest.mark.parametrize(
    "condition",
    [
        "failed",
        "missing_marks",
        "stale_version",
        "invalid",
        "input_drift",
        "real_lane",
        "empty_provenance",
    ],
)
def test_generation_refusals_do_not_change_original_inputs(
    tmp_path: Path,
    condition: str,
) -> None:
    prior, service, provider, path = _setup(tmp_path)
    before = {name: (prior.root / name).read_bytes() for name in prior.raw}
    if condition == "failed":
        provider.fail = True
    elif condition == "missing_marks":
        provider.marks = False
    elif condition == "input_drift":
        provider.change_input = path
    elif condition == "real_lane":
        prior.request["evidenceLevel"] = "real_issue145"
    elif condition == "empty_provenance":
        provider.provenance = False
    else:
        revised = load_operator_json(path)
        block = revised["activeDraft"]["blocks"][1]
        if condition == "stale_version":
            block["version"] -= 1
        else:
            block["tokens"][0]["endOffset"] = 999
        path.write_bytes(_receipt_bytes(revised))
    with pytest.raises(ProofBuildError):
        replace_row_narration(prior, path, service)
    if condition in {"stale_version", "invalid", "real_lane"}:
        assert provider.requests == []
    assert {name: (prior.root / name).read_bytes() for name in prior.raw} == before


def test_visual_only_changes_preserve_all_audio_without_service_calls(
    tmp_path: Path,
) -> None:
    prior, service, provider, path = _setup(tmp_path)
    doc = copy.deepcopy(prior.document)
    doc["liveHeadSequence"] += 1
    doc["liveStateVector"] = ""
    visual = doc["activeDraft"]["blocks"][1]["visualEvents"][0]
    visual["version"] += 1
    visual["range"]["anchorVersion"] += 1
    path.write_bytes(_receipt_bytes(doc))
    result = replace_row_narration(prior, path, service)
    assert result["dependencies"] == prior.dependencies
    assert result["replacements"] == []
    assert provider.requests == []


def test_astral_text_preserves_surviving_token_ids_with_new_utf16_marks(
    tmp_path: Path,
) -> None:
    prior, service, provider, path = _setup(tmp_path, astral=True)
    result = replace_row_narration(prior, path, service)
    assert provider.requests[0].text == "Alpha 😀 Bravo Delta Echo"
    block = load_operator_json(path)["activeDraft"]["blocks"][1]
    marks = result["dependencies"]["narration"][0]["timing"]["marks"]
    assert [(mark["startUtf16"], mark["endUtf16"]) for mark in marks] == [
        (token["startOffset"], token["endOffset"]) for token in block["tokens"]
    ]
    assert marks[1]["endUtf16"] - marks[1]["startUtf16"] == 2
    staging = tmp_path / "astral-compiled"
    staging.mkdir()
    (staging / "script-document.json").write_bytes(path.read_bytes())
    (staging / "compiler-dependencies.json").write_bytes(
        _receipt_bytes(result["dependencies"])
    )
    assert _compile(staging, prior.node)["events"]


def test_cached_audio_tamper_refuses_replay(tmp_path: Path) -> None:
    prior, service, _, path = _setup(tmp_path)
    result = replace_row_narration(prior, path, service)
    audio = Path(result["replacements"][0]["origin"])
    audio.write_bytes(audio.read_bytes() + b"bad")
    with pytest.raises(ProofBuildError):
        replace_row_narration(prior, path, service)


def test_canned_old_audio_cannot_be_relabelled_as_a_new_row(tmp_path: Path) -> None:
    prior, service, provider, path = _setup(tmp_path)
    provider.canned = provider.results[prior.document["activeDraft"]["blocks"][1]["id"]]
    with pytest.raises(ProofBuildError, match="new complete row"):
        replace_row_narration(prior, path, service)


def test_real_provider_object_refuses_despite_synthetic_profile_labels(
    tmp_path: Path,
) -> None:
    prior, service, _, path = _setup(tmp_path)
    calls = []

    class GuardedRealProvider(PollyProvider):
        def synthesize(self, request: SynthesisRequest) -> ProviderResult:
            calls.append(request)
            raise AssertionError("real provider must never be reached")

    service.provider = GuardedRealProvider()
    with pytest.raises(ProofBuildError, match="only explicitly injected"):
        replace_row_narration(prior, path, service)
    assert calls == []


def test_cache_ancestor_symlink_refuses_before_provider_call(tmp_path: Path) -> None:
    prior, service, provider, path = _setup(tmp_path)
    parent = service.cache.root.parent
    outside = tmp_path / "outside-cache"
    parent.rename(outside)
    parent.symlink_to(outside, target_is_directory=True)
    before = {
        str(file): file.read_bytes() for file in outside.rglob("*") if file.is_file()
    }
    with pytest.raises(ProofBuildError, match="local proof directory"):
        replace_row_narration(prior, path, service)
    assert provider.requests == []
    assert {
        str(file): file.read_bytes() for file in outside.rglob("*") if file.is_file()
    } == before


def test_importing_handoff_loads_no_cloud_sdk() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "import vera_timeline_agent.roundtrip_narration; "
            "assert 'boto3' not in sys.modules",
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
