"""Pinned local Node v2 compiler port; blocked reports never ship as packages."""

from __future__ import annotations

import json
from pathlib import Path

from .build_compiler_bridge import BridgeOutput, invoke_bridge
from .build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from .build_jobs import BuildJobError, StageContext, publish_immutable_output


class CompileStagePort:
    @staticmethod
    def paths(context: StageContext, snapshot: FrozenBuildSnapshot) -> dict[str, Path]:
        root = snapshot.write_root / context.job_id / "compiling"
        return {
            "manifest": root / "timeline-manifest.json",
            "report": root / "build-report.json",
        }

    @staticmethod
    def dependencies(context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        return (
            snapshot.write_root
            / context.job_id
            / "resolving_media"
            / "compiler-dependencies.json"
        )

    def _checked_compile(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> BridgeOutput:
        result = invoke_bridge(
            "compile", snapshot.file("document"), self.dependencies(context, snapshot)
        )
        previous = (
            snapshot.write_root
            / context.job_id
            / "resolving_media"
            / "media-needs.json"
        )
        if not previous.is_file():
            raise BuildJobError("no independently verified media requirements")
        needs = json.loads(previous.read_bytes())
        if result.needs != needs:
            raise BuildJobError(
                "compiler temporal plan differs from pre-preparation plan"
            )
        if result.result["report"].get("status") != "ready":
            raise BuildJobError("blocked report is not a usable build")
        return result

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "compiling":
            raise BuildJobError("wrong compiler stage")
        paths = self.paths(context, snapshot)
        if not any(path.exists() for path in paths.values()):
            return Inspection(EffectState.ABSENT)
        if any(not path.is_file() for path in paths.values()):
            return Inspection(EffectState.UNCERTAIN, reason="partial compiler output")
        result = self._checked_compile(context, snapshot)
        for key, field in (("manifest", "manifestJson"), ("report", "reportJson")):
            if (
                paths[key].is_symlink()
                or paths[key].read_bytes() != result.result[field].encode()
            ):
                raise BuildJobError(
                    f"compiler {key} differs from pinned verified Node output"
                )
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="compiler-v2",
                adapter_version="compiler/v2",
                inputs={
                    "document": snapshot.file("document"),
                    "preparedDependencies": self.dependencies(context, snapshot),
                    "mediaNeeds": snapshot.write_root
                    / context.job_id
                    / "resolving_media"
                    / "media-needs.json",
                },
                outputs=paths,
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        context.renew_lease()
        result = self._checked_compile(context, snapshot)
        paths = self.paths(context, snapshot)
        publish_immutable_output(
            paths["manifest"], result.result["manifestJson"].encode()
        )
        publish_immutable_output(paths["report"], result.result["reportJson"].encode())
