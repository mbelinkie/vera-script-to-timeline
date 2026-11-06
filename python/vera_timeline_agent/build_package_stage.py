"""Real #177 package publication and independent v2 import attestation ports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote, urlparse

from .build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from .build_jobs import BuildJobError, StageContext, UncertainResult
from .build_stage_receipt import hash_file
from .narration.cache import NarrationCache
from .v2_package import build_v2_package, verify_v2_package
from .workflow_v2 import load_verified_package_v2
from .workflow_v2_cli import attest_package_v2


def package_root(context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
    return snapshot.write_root / context.job_id / "package"


def package_inputs(
    context: StageContext, snapshot: FrozenBuildSnapshot
) -> dict[str, Path]:
    root = snapshot.write_root / context.job_id
    return {
        "manifest": root / "compiling" / "timeline-manifest.json",
        "report": root / "compiling" / "build-report.json",
        "document": snapshot.file("document"),
        "dependencies": root / "resolving_media" / "compiler-dependencies.json",
        "preparationPaths": root / "resolving_media" / "preparation-paths.json",
    }


def package_receipt(context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
    return (
        package_root(context, snapshot)
        / "Builds"
        / snapshot.build_id
        / "package-verification.json"
    )


def _file_locator(locator: str, root: Path) -> Path:
    uri = urlparse(locator)
    if (
        uri.scheme != "file"
        or uri.netloc not in ("", "localhost")
        or uri.query
        or uri.fragment
    ):
        raise BuildJobError("untrusted prepared media locator")
    path = Path(unquote(uri.path))
    if not path.is_absolute() or not path.is_relative_to(root):
        raise BuildJobError("prepared media locator outside frozen build root")
    hash_file(path)
    return path


class PackageStagePort:
    """Builds an actual package and rechecks both source pins and its inventory."""

    def __init__(
        self,
        *,
        narration_cache: NarrationCache | None = None,
        extra_media: Mapping[str, str] | None = None,
    ) -> None:
        self.cache = narration_cache
        # Each explicit extra key names a frozen snapshot input, not a path.
        self.extra_media = dict(extra_media or {})

    @staticmethod
    def _preparations(
        context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> dict[str, Path]:
        raw = package_inputs(context, snapshot)["preparationPaths"].read_bytes()
        rows = json.loads(raw)
        if not isinstance(rows, dict):
            raise BuildJobError("invalid preparation path mapping")
        result: dict[str, Path] = {}
        for key, value in rows.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise BuildJobError("invalid preparation locator")
            path = Path(value)
            if not path.is_absolute() or not path.is_relative_to(snapshot.write_root):
                raise BuildJobError("preparation path escapes frozen output root")
            hash_file(path)
            result[key] = path
        return result

    def _media(
        self,
        context: StageContext,
        snapshot: FrozenBuildSnapshot,
        preparations: Mapping[str, Path],
    ) -> dict[str, Path]:
        manifest = json.loads(
            package_inputs(context, snapshot)["manifest"].read_bytes()
        )
        result: dict[str, Path] = {
            key: snapshot.file(name) for key, name in self.extra_media.items()
        }
        needs_voice = any(
            source.get("narrationAudio") is not None for source in manifest["sources"]
        )
        assets_path = (
            snapshot.write_root / context.job_id / "generating_speech" / "assets.json"
        )
        if needs_voice or assets_path.exists():
            recorded = json.loads(assets_path.read_bytes())
            narration_rows = recorded.get("assets")
            if not isinstance(narration_rows, list):
                raise BuildJobError("verified narration assets not retained")
        else:
            narration_rows = []
        for source in manifest["sources"]:
            key = f"source:{source['id']}"
            narration = source.get("narrationAudio")
            if narration is not None:
                if self.cache is None:
                    raise BuildJobError("narration cache verifier not installed")
                asset_id = narration["cacheAssetId"]
                matches = [
                    row for row in narration_rows if row.get("assetId") == asset_id
                ]
                if len(matches) != 1:
                    raise BuildJobError(
                        "narration source lacks exact verified cache identity"
                    )
                row = matches[0]
                cached = self.cache.read(
                    "assets", f"{row['blockId']}/{row['assetId']}", "asset.json"
                )
                if (
                    cached is None
                    or cached.metadata.get("asset", {}).get("status") != "ready"
                ):
                    raise BuildJobError("failed narration asset cannot enter package")
                result[key] = cached.path / "narration.wav"
                continue
            requirement_key = source.get("preparationRequirementKey")
            if requirement_key not in preparations:
                raise BuildJobError("compiled media source is missing P5 preparation")
            prepared = json.loads(preparations[requirement_key].read_bytes())
            binding = prepared["binding"]
            if key not in result:
                result[key] = (
                    _file_locator(binding["artifactLocator"], snapshot.write_root)
                    if binding["mode"] != "verified_reuse"
                    else snapshot.file(f"source:{source['mediaReferenceId']}")
                )
            original_key = f"original:{source['id']}"
            if original_key not in result:
                result[original_key] = snapshot.file(
                    f"source:{source['mediaReferenceId']}"
                )
        for event in manifest["events"]:
            if event["kind"] != "source_audio":
                continue
            from .v2_package import _compiler_hash

            matches = [
                receipt
                for receipt in preparations.values()
                if _compiler_hash(json.loads(receipt.read_bytes())["binding"])
                == event["preparationBindingHash"]
            ]
            if len(matches) != 1:
                raise BuildJobError("source audio has no unique verified preparation")
            result[f"event:{event['eventId']}"] = matches[0].parent / "audio.wav"
        # Placeholder slates are explicitly generated by the accepted P7 test
        # adapter; a caller must supply a pinned file instead of fabricating a
        # new source here. Hash verification is enforced inside build_v2_package.
        for key, path in result.items():
            if not path.is_absolute() or (
                not path.is_relative_to(snapshot.write_root)
                and path not in snapshot.inputs.values()
                and not (self.cache and path.is_relative_to(self.cache.root))
            ):
                raise BuildJobError(f"untrusted package media path: {key}")
            hash_file(path)
        return result

    def _verify(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        root = package_root(context, snapshot)
        result = verify_v2_package(root)
        if result.build_id != snapshot.build_id:
            raise BuildJobError("package build identity differs from frozen snapshot")
        inputs = package_inputs(context, snapshot)
        build = root / "Builds" / result.build_id
        for input_name, package_name in (
            ("document", "script-document.json"),
            ("dependencies", "compiler-dependencies.json"),
            ("manifest", "timeline-manifest.json"),
            ("report", "build-report.json"),
        ):
            if hash_file(inputs[input_name]) != hash_file(build / package_name):
                raise BuildJobError(
                    "package contains different compiler/frozen input bytes"
                )
        return build / "package-verification.json"

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "writing_interchange":
            raise BuildJobError("wrong package publication stage")
        root = package_root(context, snapshot)
        if not root.exists():
            return Inspection(EffectState.ABSENT)
        if not root.is_dir() or not any(root.iterdir()):
            return Inspection(
                EffectState.UNCERTAIN, reason="partial package output retained"
            )
        receipt = self._verify(context, snapshot)
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="v2-package",
                adapter_version="v2-package/v1",
                inputs=package_inputs(context, snapshot),
                outputs={"packageVerification": receipt},
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        context.renew_lease()
        inputs = package_inputs(context, snapshot)
        prep = self._preparations(context, snapshot)
        media = self._media(context, snapshot, prep)
        built = build_v2_package(
            inputs["manifest"],
            inputs["report"],
            inputs["document"],
            inputs["dependencies"],
            package_root(context, snapshot),
            media_paths=media,
            preparation_paths=prep,
        )
        if built.build_id != snapshot.build_id:
            raise BuildJobError("published package uses a different build ID")
        self._verify(context, snapshot)


class VerifyPackageStagePort:
    """Independent no-rebuild verification; Free ends at ready_to_import."""

    @staticmethod
    def attestation(context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        return snapshot.write_root / context.job_id / "v2-attestation.json"

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "verifying_import_package":
            raise BuildJobError("wrong import verification stage")
        attestation = self.attestation(context, snapshot)
        if not attestation.exists():
            return Inspection(EffectState.ABSENT)
        digest = hash_file(attestation)
        verified = load_verified_package_v2(attestation, digest)
        if (
            verified.root != package_root(context, snapshot)
            or verified.attestation.get("buildId") != snapshot.build_id
        ):
            raise BuildJobError("attestation does not match frozen package/build")
        receipt = package_receipt(context, snapshot)
        hash_file(receipt)
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="v2-attestation",
                adapter_version="vera-injected-delivery-attestation/v2",
                inputs={"packageVerification": receipt},
                outputs={"attestation": attestation},
                attestation=attestation,
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        context.renew_lease()
        attestation = self.attestation(context, snapshot)
        if attestation.exists():
            raise UncertainResult(
                "existing attestation requires independent reconciliation"
            )
        attest_package_v2(package_root(context, snapshot), attestation)
        if self.inspect(context, snapshot).state != EffectState.VERIFIED:
            raise UncertainResult("attestation did not independently verify")
