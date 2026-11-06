"""Real P5 media-needs to qualified #174 CFR preparation composition.

No synthetic prepared-media bindings are constructed: the accepted #174
adapter returns all bindings, locators and immutable hash/probe receipts.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_compiler_bridge import invoke_bridge
from .build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from .build_jobs import (
    BuildJobError,
    NeedsAction,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)
from .build_stage_receipt import canonical_json, hash_file
from .media_preparation import (
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    _reuse,
    prepare_media,
)


@dataclass(frozen=True)
class MediaStageAuthorization:
    project_id: str
    snapshot_id: str
    preparation: PreparationAuthorization
    streams: Mapping[str, tuple[int, int | None]]


class MediaStagePort:
    """One immutable project-media preparation stage with an explicit P5 authority."""

    def __init__(
        self,
        authorization: MediaStageAuthorization,
        *,
        tools: MediaTools | None = None,
        prepare: Callable[..., PreparedMedia] = prepare_media,
        verify: Callable[..., PreparedMedia] = _reuse,
    ) -> None:
        self.authorization = authorization
        self.tools = tools or MediaTools()
        self.prepare = prepare
        self.verify = verify

    @staticmethod
    def paths(context: StageContext, snapshot: FrozenBuildSnapshot) -> dict[str, Path]:
        directory = snapshot.write_root / context.job_id / context.stage
        return {
            k: directory / v
            for k, v in {
                "intent": "intent.json",
                "needsInput": "media-needs.dependencies.json",
                "needs": "media-needs.json",
                "dependencies": "compiler-dependencies.json",
                "preparations": "preparation-paths.json",
            }.items()
        }

    def _authorized(self, snapshot: FrozenBuildSnapshot) -> PreparationAuthorization:
        value = self.authorization
        if (
            value.project_id != snapshot.project_id
            or value.snapshot_id != snapshot.snapshot_id
        ):
            raise NeedsAction(
                "media preparation is not authorized for this frozen build"
            )
        if not value.preparation.write_root.absolute().is_relative_to(
            snapshot.write_root
        ):
            raise BuildJobError("media output must be under frozen build write root")
        sources = [
            path for name, path in snapshot.inputs.items() if name.startswith("source:")
        ]
        for source in sources:
            if not any(
                source.is_relative_to(root.resolve())
                for root in value.preparation.read_roots
            ):
                raise NeedsAction("media authorization excludes frozen source")
        return value.preparation

    @staticmethod
    def _narration_maps(
        context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> list[Any]:
        path = (
            snapshot.write_root
            / context.job_id
            / "generating_speech"
            / "timing-maps.json"
        )
        try:
            value = json.loads(path.read_bytes())
        except (OSError, ValueError) as error:
            raise NeedsAction("verified narration timing maps not published") from error
        if not isinstance(value, list):
            raise BuildJobError("narration timing maps are not a list")
        return value

    def _input_deps(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> dict[str, Any]:
        original = json.loads(snapshot.file("dependencies").read_bytes())
        if (
            not isinstance(original, dict)
            or original.get("schemaVersion") != "compiler-dependencies/v2"
        ):
            raise BuildJobError("frozen compiler dependencies have unknown schema")
        result = copy.deepcopy(original)
        result["narrationTimingMaps"] = self._narration_maps(context, snapshot)
        result["preparedMedia"] = []
        return result

    def _requirements(
        self, context: StageContext, snapshot: FrozenBuildSnapshot, *, needs_input: Path
    ) -> dict[str, Any]:
        response = invoke_bridge("needs", snapshot.file("document"), needs_input)
        return response.needs

    @staticmethod
    def _reqs(
        needs: dict[str, Any], descriptors: list[Any]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
        seen: dict[str, dict[str, Any]] = {}
        for item in needs["requirements"]:
            if item.get("sourceSufficiency") != "sufficient":
                occurrence = item.get("occurrenceKey")
                raise NeedsAction(
                    f"source range cannot satisfy occurrence {occurrence}"
                )
            key = item.get("requirementKey")
            if key is None:
                continue
            matches = [
                descriptor
                for descriptor in descriptors
                if descriptor.get("preparedMediaRequirementKey") == key
                and descriptor.get("mediaReferenceId") == item.get("mediaReferenceId")
            ]
            if len(matches) != 1:
                raise BuildJobError(
                    f"media requirement {key} does not identify one frozen source"
                )
            if key in seen:
                if seen[key] != item:
                    raise BuildJobError("conflicting repeated preparation requirement")
                continue
            seen[key] = item
            rows.append((item, matches[0]))
        return rows

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "resolving_media":
            raise BuildJobError("wrong media preparation stage")
        paths = self.paths(context, snapshot)
        if not paths["preparations"].exists() or not paths["dependencies"].exists():
            if any(path.exists() for path in paths.values()):
                return Inspection(
                    EffectState.UNCERTAIN,
                    reason="partial CFR preparation; preserve outputs for inspection",
                )
            return Inspection(EffectState.ABSENT)
        if any(
            not paths[name].is_file()
            for name in ("needsInput", "needs", "dependencies", "preparations")
        ):
            return Inspection(
                EffectState.UNCERTAIN, reason="incomplete media preparation record"
            )
        authorization = self._authorized(snapshot)
        expected_input = canonical_json(self._input_deps(context, snapshot))
        if paths["needsInput"].read_bytes() != expected_input:
            raise BuildJobError(
                "media-needs dependencies differ from frozen narration/dependencies"
            )
        needs = self._requirements(context, snapshot, needs_input=paths["needsInput"])
        if paths["needs"].read_bytes() != canonical_json(needs):
            raise BuildJobError("media-needs output changed")
        rows = self._reqs(needs, json.loads(expected_input)["occurrenceResolutions"])
        try:
            published = json.loads(paths["preparations"].read_bytes())
        except (ValueError, OSError) as error:
            raise UncertainResult(
                "cannot read existing media preparation locators"
            ) from error
        if not isinstance(published, dict) or set(published) != {
            item["requirementKey"] for item, _ in rows
        }:
            raise BuildJobError("media preparation requirement keys changed")
        bindings = []
        outputs = dict(paths)
        for item, _descriptor in rows:
            key = item["requirementKey"]
            locator = published[key]
            if not isinstance(locator, str):
                raise BuildJobError("untrusted media preparation path")
            receipt = Path(locator)
            if not receipt.is_absolute() or not receipt.is_relative_to(
                snapshot.write_root
            ):
                raise BuildJobError("preparation receipt outside frozen build root")
            hash_file(receipt)
            record = json.loads(receipt.read_bytes())
            source = snapshot.file(f"source:{item['mediaReferenceId']}")
            if record.get("inputs", {}).get("requestedRange") != item["requestedRange"]:
                raise BuildJobError("preparation source range changed")
            checked = self.verify(
                receipt.parent, source, record["inputs"], authorization, self.tools
            )
            if (
                checked.receipt_path != receipt
                or checked.binding["requirementKey"] != key
            ):
                raise BuildJobError("prepared media identity changed")
            bindings.append(checked.binding)
            outputs[f"prep:{key}"] = receipt
            if checked.video_path.is_relative_to(snapshot.write_root):
                outputs[f"video:{key}"] = checked.video_path
            if checked.audio_path is not None:
                outputs[f"audio:{key}"] = checked.audio_path
        final = self._input_deps(context, snapshot)
        final["preparedMedia"] = bindings
        if paths["dependencies"].read_bytes() != canonical_json(final):
            raise BuildJobError(
                "compiled media bindings differ from qualified receipts"
            )
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="prepare-media-v2",
                adapter_version="authoring-media-preparation/v1",
                inputs={
                    "document": snapshot.file("document"),
                    "dependencies": snapshot.file("dependencies"),
                    "narrationTiming": snapshot.write_root
                    / context.job_id
                    / "generating_speech"
                    / "timing-maps.json",
                },
                outputs=outputs,
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        authorization = self._authorized(snapshot)
        paths = self.paths(context, snapshot)
        source = self._input_deps(context, snapshot)
        context.renew_lease()
        publish_immutable_output(paths["needsInput"], canonical_json(source))
        needs = self._requirements(context, snapshot, needs_input=paths["needsInput"])
        publish_immutable_output(paths["needs"], canonical_json(needs))
        requirements = self._reqs(needs, source["occurrenceResolutions"])
        if any(
            item["requirementKey"] not in self.authorization.streams
            for item, _ in requirements
        ):
            raise NeedsAction(
                "explicitly qualified source streams required for each preparation"
            )
        publish_immutable_output(
            paths["intent"],
            canonical_json(
                {
                    "schemaVersion": "vera-build-media-intent/v1",
                    "snapshotSha256": snapshot.sha256,
                    "stageKey": context.stage_key,
                }
            ),
        )
        prepared: dict[str, str] = {}
        bindings = []
        for item, descriptor in requirements:
            context.renew_lease()
            key = item["requirementKey"]
            if key not in self.authorization.streams:
                raise NeedsAction(f"no explicitly verified source streams for {key}")
            video_index, audio_index = self.authorization.streams[key]
            result = self.prepare(
                snapshot.file(f"source:{item['mediaReferenceId']}"),
                descriptor,
                item["requestedRange"],
                source["timeline"]["frameRate"],
                authorization=authorization,
                video_stream_index=video_index,
                audio_stream_index=audio_index,
                tools=self.tools,
            )
            if result.binding["requirementKey"] != key:
                raise BuildJobError(
                    "#174 preparation returned a different occurrence identity"
                )
            if not result.receipt_path.is_relative_to(snapshot.write_root):
                raise BuildJobError("CFR receipt outside frozen build root")
            hash_file(result.receipt_path)
            prepared[key] = str(result.receipt_path)
            bindings.append(result.binding)
        output = copy.deepcopy(source)
        output["preparedMedia"] = bindings
        publish_immutable_output(paths["dependencies"], canonical_json(output))
        publish_immutable_output(paths["preparations"], canonical_json(prepared))
