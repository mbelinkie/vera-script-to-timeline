"""Injected Resolve 21.1 Fairlight capability probe for issue 110."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import struct
import time
import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

REPORT_SCHEMA_VERSION = "vera-fairlight-capability-report-v1"
CAPABILITY_STATUSES = frozenset(
    {"supported-api", "verified-preset", "operator-only", "unavailable"}
)
REQUIRED_CAPABILITIES = frozenset(
    {
        "voiceIsolation",
        "dialogueLeveler",
        "normalization",
        "eqDynamicsPreset",
        "pcmWavRender",
    }
)
PROJECT_PREFIX = "VERA Issue 110 Fairlight Probe "
TIMELINE_NAME = "VERA Issue 110 Fairlight Probe"
SCRIPTING_README = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/README.md"
)
SCRIPTING_STUB = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/DaVinciResolveScript.pyi"
)
OFFICIAL_DOCUMENTATION = (
    (
        "Blackmagic Design support",
        "https://www.blackmagicdesign.com/support/",
        "Resolve release and developer-documentation distribution",
    ),
    (
        "DaVinci Resolve Fairlight",
        "https://www.blackmagicdesign.com/products/davinciresolve/fairlight/",
        "operator audio, EQ, dynamics, bounce, and restoration workflows",
    ),
    (
        "The Fairlight Audio Guide to DaVinci Resolve 20",
        "https://documents.blackmagicdesign.com/UserManuals/"
        "DaVinciResolveFairlightAudioPost.pdf",
        "channel mapping, normalization, dialogue processing, and delivery",
    ),
)


class FairlightProbeError(RuntimeError):
    """The bounded probe cannot proceed safely or truthfully."""


@dataclass(frozen=True)
class FairlightProbeConfig:
    """Operator-supplied bounds for one disposable probe run."""

    project_name: str
    output_dir: Path
    external_scripting_setting: str
    documentation_retrieved_at: str
    fairlight_preset_name: str | None = None


@dataclass(frozen=True)
class ResolveEvidence:
    """Version identity observed from Resolve's injected object."""

    product_name: str
    version: str
    build: str
    suffix: str
    current_page: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "productName": self.product_name,
            "version": self.version,
            "build": self.build,
            "suffix": self.suffix,
            "currentPage": self.current_page,
        }


@dataclass(frozen=True)
class CapabilityEvidence:
    """One claimed capability, backed by mutation and readback when supported."""

    status: str
    operation: str
    before: Any
    request: Any
    readback: Any
    restored: Any
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        if self.status not in CAPABILITY_STATUSES:
            raise FairlightProbeError(f"invalid capability status: {self.status}")
        return {
            "status": self.status,
            "operation": self.operation,
            "before": self.before,
            "request": self.request,
            "readback": self.readback,
            "restored": self.restored,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class OriginalAudioEvidence:
    """Proof that the synthetic source and its clean timeline path remain usable."""

    source_path: str
    source_sha256_before: str
    source_sha256_after: str | None
    original_media_id: str | None
    original_timeline_item_present: bool
    original_clip_enabled: bool | None
    replacement_timeline_item_present: bool
    preserved: bool
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourcePath": self.source_path,
            "sourceSha256Before": self.source_sha256_before,
            "sourceSha256After": self.source_sha256_after,
            "originalMediaId": self.original_media_id,
            "originalTimelineItemPresent": self.original_timeline_item_present,
            "originalClipEnabled": self.original_clip_enabled,
            "replacementTimelineItemPresent": (self.replacement_timeline_item_present),
            "preserved": self.preserved,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class ProbeExecution:
    """Results from the bounded public-API mutation sequence."""

    channel_mapping: CapabilityEvidence
    capabilities: dict[str, CapabilityEvidence]
    attachment_path: dict[str, Any]
    original_audio: OriginalAudioEvidence
    fairlight_presets: tuple[str, ...]
    rendered_wav: dict[str, Any] | None
    discrepancies: tuple[str, ...]


@dataclass(frozen=True)
class FairlightCapabilityReport:
    """Version-stamped structured report retained for #108."""

    status: str
    message: str
    created_at: str
    project_name: str
    external_scripting_setting: str
    resolve: ResolveEvidence
    runtime: dict[str, str]
    documentation: tuple[dict[str, Any], ...]
    probe_media: dict[str, Any]
    channel_mapping: CapabilityEvidence
    capabilities: dict[str, CapabilityEvidence]
    attachment_path: dict[str, Any]
    original_audio: OriginalAudioEvidence
    fairlight_presets: tuple[str, ...]
    rendered_wav: dict[str, Any] | None
    discrepancies: tuple[str, ...]

    def to_json(self) -> str:
        """Serialize and validate the staging report deterministically."""
        if set(self.capabilities) != REQUIRED_CAPABILITIES:
            raise FairlightProbeError("capability report keys are incomplete")
        payload = {
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "status": self.status,
            "message": self.message,
            "createdAt": self.created_at,
            "projectName": self.project_name,
            "externalScriptingSetting": self.external_scripting_setting,
            "resolve": self.resolve.to_dict(),
            "runtime": self.runtime,
            "documentation": list(self.documentation),
            "probeMedia": self.probe_media,
            "channelMapping": self.channel_mapping.to_dict(),
            "capabilities": {
                key: self.capabilities[key].to_dict()
                for key in sorted(self.capabilities)
            },
            "attachmentPath": self.attachment_path,
            "originalAudio": self.original_audio.to_dict(),
            "fairlightPresets": list(self.fairlight_presets),
            "renderedWav": self.rendered_wav,
            "discrepancies": list(self.discrepancies),
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


class FairlightProbeAdapter(Protocol):
    """Small injectable seam around the actual Resolve mutations."""

    def preflight(self, config: FairlightProbeConfig) -> ResolveEvidence: ...

    def execute(
        self,
        config: FairlightProbeConfig,
        source_path: Path,
        source_sha256: str,
    ) -> ProbeExecution: ...

    def restore_original_audio(
        self, source_path: Path, source_sha256: str
    ) -> OriginalAudioEvidence: ...


AdapterFactory = Callable[[Any], FairlightProbeAdapter]


def run_fairlight_capability_probe(
    resolve: Any,
    config: FairlightProbeConfig,
    *,
    adapter_factory: AdapterFactory | None = None,
) -> FairlightCapabilityReport:
    """Run one synthetic, fail-closed Fairlight probe from Resolve's object."""
    _validate_config(config)
    if resolve is None:
        raise FairlightProbeError("Resolve did not inject an API object")
    factory = adapter_factory or PublicFairlightAdapter
    adapter = factory(resolve)
    connected = adapter.preflight(config)
    config.output_dir.mkdir(parents=True, exist_ok=False)
    source_path = config.output_dir / "synthetic-stereo-probe.wav"
    _write_synthetic_probe(source_path)
    source_sha256 = _sha256(source_path)
    runtime = {
        "implementation": platform.python_implementation(),
        "pythonVersion": platform.python_version(),
    }
    documentation = _documentation_evidence(config.documentation_retrieved_at)
    probe_media = {
        "kind": "synthetic-non-presenter",
        "path": str(source_path),
        "sha256": source_sha256,
        "sampleRate": 48000,
        "channels": 2,
        "bitDepth": 16,
        "durationSamples": 48000,
        "channel1": "440 Hz sine",
        "channel2": "880 Hz sine",
    }
    try:
        execution = adapter.execute(config, source_path, source_sha256)
        verified = not execution.discrepancies and execution.original_audio.preserved
        status = "verified" if verified else "verification_failed"
        message = (
            "Fairlight capability boundary was exercised and the clean synthetic "
            "audio path was restored."
            if verified
            else "Fairlight probe completed with retained discrepancies."
        )
    except Exception as error:
        detail = str(error)
        try:
            original_audio = adapter.restore_original_audio(source_path, source_sha256)
        except Exception as restore_error:
            after_hash = _sha256(source_path) if source_path.is_file() else None
            original_audio = OriginalAudioEvidence(
                source_path=str(source_path),
                source_sha256_before=source_sha256,
                source_sha256_after=after_hash,
                original_media_id=None,
                original_timeline_item_present=False,
                original_clip_enabled=None,
                replacement_timeline_item_present=True,
                preserved=False,
                explanation=(
                    "Automatic timeline restoration also failed; the synthetic "
                    "source bytes were rechecked, but the operator must inspect "
                    f"the disposable project. Detail: {restore_error}"
                ),
            )
            detail = f"{detail}; restoration failed: {restore_error}"
        execution = _failed_execution(original_audio, detail)
        status = "mutation_failed"
        message = (
            "Fairlight probe failed after mutation began; restoration was attempted "
            f"and retained. Detail: {detail}"
        )
    return FairlightCapabilityReport(
        status=status,
        message=message,
        created_at=datetime.now(UTC).isoformat(),
        project_name=config.project_name,
        external_scripting_setting=config.external_scripting_setting,
        resolve=connected,
        runtime=runtime,
        documentation=documentation,
        probe_media=probe_media,
        channel_mapping=execution.channel_mapping,
        capabilities=execution.capabilities,
        attachment_path=execution.attachment_path,
        original_audio=execution.original_audio,
        fairlight_presets=execution.fairlight_presets,
        rendered_wav=execution.rendered_wav,
        discrepancies=execution.discrepancies,
    )


def load_probe_config(path: Path) -> FairlightProbeConfig:
    """Load the exact operator-authored bounds used by the installed launcher."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FairlightProbeError(
            f"could not read probe config {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise FairlightProbeError("probe config must be one JSON object")
    required = {
        "projectName",
        "outputDir",
        "externalScriptingSetting",
        "documentationRetrievedAt",
    }
    if not required.issubset(value):
        raise FairlightProbeError("probe config is missing required fields")
    preset = value.get("fairlightPresetName")
    if preset is not None and not isinstance(preset, str):
        raise FairlightProbeError("fairlightPresetName must be a string or null")
    config = FairlightProbeConfig(
        project_name=_string(value["projectName"], "projectName"),
        output_dir=Path(_string(value["outputDir"], "outputDir")),
        external_scripting_setting=_string(
            value["externalScriptingSetting"], "externalScriptingSetting"
        ),
        documentation_retrieved_at=_string(
            value["documentationRetrievedAt"], "documentationRetrievedAt"
        ),
        fairlight_preset_name=preset,
    )
    _validate_config(config)
    return config


def select_fairlight_preset(
    available: Sequence[str], requested: str | None
) -> tuple[str | None, CapabilityEvidence]:
    """Refuse an unnamed or absent preset instead of guessing from a catalog."""
    request = {"presetName": requested}
    if requested is None:
        return None, CapabilityEvidence(
            status="operator-only",
            operation="ApplyFairlightPresetToCurrentTimeline",
            before={"availablePresetNames": list(available)},
            request=request,
            readback=None,
            restored=None,
            explanation=(
                "No exact preset name was authorized. EQ/dynamics remain an "
                "operator step; the public API exposes no current-preset or "
                "EQ/dynamics state getter."
            ),
        )
    if requested not in available:
        return None, CapabilityEvidence(
            status="unavailable",
            operation="ApplyFairlightPresetToCurrentTimeline",
            before={"availablePresetNames": list(available)},
            request=request,
            readback=None,
            restored=None,
            explanation=(
                "The exact requested preset name was not available; no preset "
                "was applied."
            ),
        )
    return requested, CapabilityEvidence(
        status="operator-only",
        operation="ApplyFairlightPresetToCurrentTimeline",
        before={"availablePresetNames": list(available)},
        request=request,
        readback=None,
        restored=None,
        explanation=(
            "The named preset is available, but application and EQ/dynamics state "
            "still require bounded mutation plus operator-visible verification."
        ),
    )


def write_operator_handoff(report: FairlightCapabilityReport, path: Path) -> None:
    """Write numbered rerun/verification steps and #108's exact boundary."""
    statuses = "\n".join(
        f"- {name}: `{evidence.status}` — {evidence.explanation}"
        for name, evidence in sorted(report.capabilities.items())
    )
    wav_check = (
        "6. Verify the retained rendered WAV reports 48 kHz Linear PCM and that "
        "the report proves exact-start attachment, replacement, removal, save, "
        "close, reopen, and final original-audio restoration."
        if report.rendered_wav is not None
        else "6. Confirm PCM-WAV rendering is recorded as `unavailable`, with the "
        "rejected request and failed-closed attachment path retained."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Issue 110 — Resolve Fairlight operator handoff\n\n"
        f"Project: `{report.project_name}`  \n"
        f"Resolve: `{report.resolve.product_name} {report.resolve.version} build "
        f"{report.resolve.build}`  \n"
        f"Injected Python: `{report.runtime['implementation']} "
        f"{report.runtime['pythonVersion']}`\n\n"
        "## Capability boundary\n\n"
        f"- channelMapping: `{report.channel_mapping.status}` — "
        f"{report.channel_mapping.explanation}\n"
        f"{statuses}\n\n"
        "## External rerun and verification\n\n"
        "1. Confirm Resolve Preferences > System > General > **External "
        "scripting using** remains **None**. Do not relax it.\n"
        "2. Confirm the installed #110 config names a new project beginning "
        f"`{PROJECT_PREFIX}` and a new, nonexistent output directory.\n"
        "3. Open Resolve on the Fairlight page, then launch Workspace > Workflow "
        "Integrations > VERA Issue 110 Fairlight Probe. Expected: only the newly "
        "named disposable project is created.\n"
        "4. Open the retained JSON report. Expected: the Resolve version/build and "
        "Python version match this run; the probe media is synthetic stereo audio; "
        "channel 1 maps to one mono track while channel 2 is excluded, or the "
        "failure is explicit.\n"
        "5. In the named project, inspect the final channel mapping and restored "
        "effect state. Expected: channel mapping matches `channelMapping.readback`; "
        "reversible `supported-api` controls match their `restored` state while the "
        "JSON retains before/request/readback evidence. Treat `operator-only` as "
        "unautomated; do not infer EQ/dynamics from a successful API return.\n"
        f"{wav_check} Expected final timeline state: the original synthetic item is "
        "present and enabled; no replacement item remains.\n"
        "7. Confirm no existing project and no presenter file was opened, copied, "
        "hashed, transmitted, rendered, or altered. Record the report path and any "
        "discrepancy on issue #110.\n\n"
        "## Handoff to #108\n\n"
        "#108 may automate only operations marked `supported-api` with matching "
        "mutation/readback evidence on the installed Resolve build. It must leave "
        "`operator-only` steps in Fairlight, refuse `unavailable` operations, retain "
        "clean presenter audio, and collect the same exact-start, enabled-state, "
        "sample-format, save/reopen, and UI verification evidence before any A/B "
        "comparison. This handoff does not choose or apply a presenter treatment.\n",
        encoding="utf-8",
    )


class PublicFairlightAdapter:
    """Actual public Resolve 21.1 mutation/readback implementation."""

    def __init__(self, resolve: Any) -> None:
        self.resolve = resolve
        self.manager: Any = None
        self.project: Any = None
        self.pool: Any = None
        self.timeline: Any = None
        self.original_media_id: str | None = None
        self.replacement_media_id: str | None = None
        self.project_name: str | None = None

    def preflight(self, config: FairlightProbeConfig) -> ResolveEvidence:
        product = self.resolve.GetProductName()
        version_fields = self.resolve.GetVersion()
        page = self.resolve.GetCurrentPage()
        if not isinstance(product, str) or "studio" not in product.casefold():
            raise FairlightProbeError("the injected product is not Resolve Studio")
        if (
            not isinstance(version_fields, (list, tuple))
            or len(version_fields) != 5
            or any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in version_fields[:4]
            )
            or not isinstance(version_fields[4], str)
        ):
            raise FairlightProbeError("Resolve returned a malformed version identity")
        if page not in {"cut", "edit", "color", "fairlight", "deliver"}:
            raise FairlightProbeError(
                "Resolve must be on a timeline page before probing"
            )
        manager = self.resolve.GetProjectManager()
        if manager is None:
            raise FairlightProbeError("Resolve returned no project manager")
        names = manager.GetProjectListInCurrentFolder()
        if not isinstance(names, (list, tuple)):
            raise FairlightProbeError("project list has an unsupported shape")
        if config.project_name in names:
            raise FairlightProbeError(
                f"project already exists; refusing reuse: {config.project_name}"
            )
        self.manager = manager
        major, minor, patch, build = cast(
            tuple[int, int, int, int], tuple(version_fields[:4])
        )
        return ResolveEvidence(
            product_name=product,
            version=f"{major}.{minor}.{patch}",
            build=str(build),
            suffix=version_fields[4],
            current_page=page,
        )

    def execute(
        self,
        config: FairlightProbeConfig,
        source_path: Path,
        source_sha256: str,
    ) -> ProbeExecution:
        self._create_project(config.project_name)
        media = self._import_media(source_path)
        channel_mapping = self._probe_channel_mapping(media)
        original = self._append_audio(media, track_index=1, record_frame=0)
        self.original_media_id = self._media_id(media)
        capabilities = {
            "voiceIsolation": self._probe_voice_isolation(original),
            "dialogueLeveler": self._probe_dialogue_leveler(original),
            "normalization": self._probe_normalization(original),
        }
        presets = self._fairlight_presets()
        capabilities["eqDynamicsPreset"] = self._probe_preset(
            presets, config.fairlight_preset_name
        )
        render_evidence, rendered_path = self._render_pcm_wav(config.output_dir)
        capabilities["pcmWavRender"] = render_evidence
        if rendered_path is None:
            attachment = {
                "exactStartFrame": 0,
                "replacementSurvivedReopen": False,
                "replacementRemoved": False,
                "originalRestoredAfterReopen": False,
                "explanation": (
                    "No verified PCM WAV existed to attach; original remained enabled."
                ),
            }
            if not original.SetClipEnabled(True):
                raise FairlightProbeError("could not retain original clip enabled")
            self._save_reopen()
        else:
            attachment = self._probe_attachment(rendered_path)
        original_audio = self.restore_original_audio(source_path, source_sha256)
        discrepancies: list[str] = []
        if not original_audio.preserved:
            discrepancies.append(original_audio.explanation)
        if rendered_path is not None and not attachment.get(
            "originalRestoredAfterReopen", False
        ):
            discrepancies.append("original-audio restoration did not survive reopen")
        return ProbeExecution(
            channel_mapping=channel_mapping,
            capabilities=capabilities,
            attachment_path=attachment,
            original_audio=original_audio,
            fairlight_presets=presets,
            rendered_wav=(
                self._wav_evidence(rendered_path) if rendered_path is not None else None
            ),
            discrepancies=tuple(discrepancies),
        )

    def restore_original_audio(
        self, source_path: Path, source_sha256: str
    ) -> OriginalAudioEvidence:
        after_hash = _sha256(source_path) if source_path.is_file() else None
        original = self._find_item(self.original_media_id, 1)
        replacements = self._items_for_media(self.replacement_media_id, 2)
        if self.timeline is not None and replacements:
            if not self.timeline.DeleteClips(replacements, False):
                return self._preservation(
                    source_path,
                    source_sha256,
                    after_hash,
                    original,
                    True,
                    False,
                    "Resolve refused to remove the replacement item.",
                )
            replacements = self._items_for_media(self.replacement_media_id, 2)
        if original is not None and not original.SetClipEnabled(True):
            return self._preservation(
                source_path,
                source_sha256,
                after_hash,
                original,
                bool(replacements),
                False,
                "Resolve refused to re-enable the original item.",
            )
        if self.project is not None and self.project_name is not None:
            self._save_reopen()
            original = self._find_item(self.original_media_id, 1)
            replacements = self._items_for_media(self.replacement_media_id, 2)
        enabled = original.GetClipEnabled() if original is not None else None
        preserved = (
            after_hash == source_sha256
            and not replacements
            and (original is None or enabled is True)
        )
        explanation = (
            "Synthetic source bytes match, the original timeline item is enabled, "
            "and no replacement remains after save/close/reopen."
            if preserved and original is not None
            else "Synthetic source bytes remain unchanged and no replacement remains."
            if preserved
            else "Original-audio preservation could not be fully verified."
        )
        return self._preservation(
            source_path,
            source_sha256,
            after_hash,
            original,
            bool(replacements),
            preserved,
            explanation,
        )

    def _create_project(self, name: str) -> None:
        self.project = self.manager.CreateProject(name)
        if self.project is None:
            raise FairlightProbeError(f"CreateProject failed for {name}")
        self.project_name = name
        settings = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }
        if not self.project.SetSettings(settings):
            raise FairlightProbeError("project settings mutation failed")
        self.pool = self.project.GetMediaPool()
        if self.pool is None:
            raise FairlightProbeError("created project has no media pool")
        root = self.pool.GetCurrentFolder()
        folder = self.pool.AddSubFolder(root, "VERA Issue 110 Synthetic Probe")
        if folder is None or not self.pool.SetCurrentFolder(folder):
            raise FairlightProbeError("could not create/select the synthetic probe bin")
        self.timeline = self.pool.CreateEmptyTimeline(TIMELINE_NAME)
        if self.timeline is None or not self.timeline.SetStartTimecode("00:00:00:00"):
            raise FairlightProbeError("could not create a frame-zero probe timeline")
        while self.timeline.GetTrackCount("audio") < 2:
            if not self.timeline.AddTrack("audio", "mono"):
                raise FairlightProbeError("could not create two mono audio tracks")
        for index, name_value in (
            (1, "Original clean probe"),
            (2, "Rendered replacement probe"),
        ):
            if not self.timeline.SetTrackName("audio", index, name_value):
                raise FairlightProbeError(f"could not name audio track {index}")

    def _import_media(self, path: Path) -> Any:
        imported = self.pool.ImportMedia([str(path)])
        if not isinstance(imported, (list, tuple)) or len(imported) != 1:
            raise FairlightProbeError(f"ImportMedia failed for {path}")
        media = imported[0]
        properties = media.GetClipProperty()
        if not isinstance(properties, Mapping):
            raise FairlightProbeError("imported media properties were unreadable")
        observed_path = properties.get("File Path")
        if (
            not isinstance(observed_path, str)
            or Path(observed_path).resolve() != path.resolve()
        ):
            raise FairlightProbeError(
                "imported media path differs from the probe source"
            )
        return media

    def _probe_channel_mapping(self, media: Any) -> CapabilityEvidence:
        operation = "MediaPoolItem.SetAudioMapping + GetAudioMapping"
        requested = {
            "track_mapping": {"1": {"channel_idx": [1], "mute": False, "type": "mono"}}
        }
        try:
            before = _json_object(media.GetAudioMapping(), "initial audio mapping")
            if not media.SetAudioMapping(json.dumps(requested, sort_keys=True)):
                raise FairlightProbeError("SetAudioMapping returned false")
            readback = _json_object(media.GetAudioMapping(), "audio mapping readback")
            mapping = cast(Mapping[str, Any], readback.get("track_mapping", {}))
            track = mapping.get("1")
            supported = (
                len(mapping) == 1
                and isinstance(track, Mapping)
                and track.get("channel_idx") == [1]
                and track.get("mute") is False
                and str(track.get("type", "")).casefold() == "mono"
            )
            if not supported:
                raise FairlightProbeError(
                    "readback did not prove channel 1 mono with channel 2 excluded"
                )
            return CapabilityEvidence(
                "supported-api",
                operation,
                before,
                requested,
                readback,
                None,
                "SetAudioMapping readback retained one mono track using only "
                "physical channel 1; channel 2 is excluded.",
            )
        except Exception as error:
            return CapabilityEvidence(
                "unavailable",
                operation,
                None,
                requested,
                None,
                None,
                f"Channel mapping was not claimed: {error}",
            )

    def _append_audio(self, media: Any, *, track_index: int, record_frame: int) -> Any:
        placed = self.pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media,
                    "mediaType": 2,
                    "trackIndex": track_index,
                    "recordFrame": record_frame,
                }
            ]
        )
        if not isinstance(placed, (list, tuple)) or len(placed) != 1:
            raise FairlightProbeError("AppendToTimeline did not return one audio item")
        item = placed[0]
        if item.GetStart(False) != record_frame:
            raise FairlightProbeError("audio item did not land at the exact start")
        return item

    def _probe_voice_isolation(self, item: Any) -> CapabilityEvidence:
        operation = "TimelineItem.SetVoiceIsolationState + GetVoiceIsolationState"
        try:
            before = _mapping(item.GetVoiceIsolationState(), "Voice Isolation state")
            request = {
                "isEnabled": not bool(before.get("isEnabled", False)),
                "amount": 37 if before.get("amount") != 37 else 63,
            }
            if not item.SetVoiceIsolationState(request):
                raise FairlightProbeError("SetVoiceIsolationState returned false")
            readback = _mapping(
                item.GetVoiceIsolationState(), "Voice Isolation readback"
            )
            if any(readback.get(key) != value for key, value in request.items()):
                raise FairlightProbeError("Voice Isolation readback differed")
            if not item.SetVoiceIsolationState(dict(before)):
                raise FairlightProbeError("Voice Isolation restoration failed")
            restored = _mapping(
                item.GetVoiceIsolationState(), "Voice Isolation restore"
            )
            return CapabilityEvidence(
                "supported-api",
                operation,
                before,
                request,
                readback,
                restored,
                "Voice Isolation accepted a changed enabled/amount state, read "
                "it back, and restored the prior state.",
            )
        except Exception as error:
            return CapabilityEvidence(
                "unavailable",
                operation,
                None,
                None,
                None,
                None,
                f"Voice Isolation was not claimed: {error}",
            )

    def _probe_dialogue_leveler(self, item: Any) -> CapabilityEvidence:
        operation = "TimelineItem.SetProperties + GetProperties"
        keys = (
            "AudioDialogueLevelerEnabled",
            "AudioDialogueLevelerMode",
            "AudioDialogueLevelerReduceLoudDialogue",
            "AudioDialogueLevelerLiftSoftDialogue",
            "AudioDialogueLevelerBackgroundReduction",
            "AudioDialogueLevelerOutputGain",
        )
        try:
            properties = _mapping(item.GetProperties(), "timeline item properties")
            if any(key not in properties for key in keys):
                raise FairlightProbeError("documented Dialogue Leveler keys are absent")
            before = {key: properties[key] for key in keys}
            gain = float(before["AudioDialogueLevelerOutputGain"])
            modes = (
                self.resolve.DIALOGUE_LEVELER_MODE_OPTIMIZE_MODERATE_LEVELS,
                self.resolve.DIALOGUE_LEVELER_MODE_MORE_LIFT_FOR_LOW_LEVELS,
            )
            requested_mode = (
                modes[1] if before["AudioDialogueLevelerMode"] == modes[0] else modes[0]
            )
            request = {
                "AudioDialogueLevelerEnabled": not bool(
                    before["AudioDialogueLevelerEnabled"]
                ),
                "AudioDialogueLevelerMode": requested_mode,
                "AudioDialogueLevelerReduceLoudDialogue": not bool(
                    before["AudioDialogueLevelerReduceLoudDialogue"]
                ),
                "AudioDialogueLevelerLiftSoftDialogue": not bool(
                    before["AudioDialogueLevelerLiftSoftDialogue"]
                ),
                "AudioDialogueLevelerBackgroundReduction": not bool(
                    before["AudioDialogueLevelerBackgroundReduction"]
                ),
                "AudioDialogueLevelerOutputGain": 1.5 if gain != 1.5 else 2.5,
            }
            if not item.SetProperties(request):
                raise FairlightProbeError(
                    "Dialogue Leveler SetProperties returned false"
                )
            after = _mapping(item.GetProperties(), "Dialogue Leveler readback")
            readback = {key: after[key] for key in keys}
            if any(readback[key] != value for key, value in request.items()):
                raise FairlightProbeError("Dialogue Leveler readback differed")
            if not item.SetProperties(before):
                raise FairlightProbeError("Dialogue Leveler restoration failed")
            restored_all = _mapping(item.GetProperties(), "Dialogue Leveler restore")
            restored = {key: restored_all[key] for key in keys}
            return CapabilityEvidence(
                "supported-api",
                operation,
                before,
                request,
                readback,
                restored,
                "Dialogue Leveler enable, mode, loud/soft treatment, background "
                "reduction, and output gain changed, read back, and restored "
                "through documented item properties.",
            )
        except Exception as error:
            return CapabilityEvidence(
                "unavailable",
                operation,
                None,
                None,
                None,
                None,
                f"Dialogue Leveler was not claimed: {error}",
            )

    def _probe_normalization(self, item: Any) -> CapabilityEvidence:
        operation = "Timeline.NormalizeAudioLevel + TimelineItem.GetProperties"
        try:
            modes = self.timeline.GetNormalizeAudioModes()
            if not isinstance(modes, (list, tuple)) or not modes:
                raise FairlightProbeError("GetNormalizeAudioModes returned no modes")
            mode = "Sample Peak Program" if "Sample Peak Program" in modes else modes[0]
            if not isinstance(mode, str) or not mode:
                raise FairlightProbeError("normalization mode was invalid")
            properties = _mapping(item.GetProperties(), "normalization properties")
            keys = ("AudioVolumeEnabled", "AudioVolume")
            if any(key not in properties for key in keys):
                raise FairlightProbeError("audio volume readback keys are absent")
            before = {key: properties[key] for key in keys}
            request: dict[str, Any] = {
                "normalizationMode": mode,
                "setLevelMode": self.resolve.NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT,
            }
            if "loudness" in mode.casefold():
                request["targetLoudness"] = -30.0
            else:
                request["targetLevel"] = -30.0
            if not self.timeline.NormalizeAudioLevel([item], request):
                raise FairlightProbeError("NormalizeAudioLevel returned false")
            after_all = _mapping(item.GetProperties(), "normalization readback")
            readback = {key: after_all[key] for key in keys}
            if readback == before:
                raise FairlightProbeError(
                    "normalization produced no readable gain change"
                )
            if not item.SetProperties(before):
                raise FairlightProbeError("normalization gain restoration failed")
            restored_all = _mapping(item.GetProperties(), "normalization restore")
            restored = {key: restored_all[key] for key in keys}
            return CapabilityEvidence(
                "supported-api",
                operation,
                before,
                request,
                readback,
                restored,
                "Normalization accepted an actual mode/target mutation, changed "
                "readable clip gain, and restored the prior gain.",
            )
        except Exception as error:
            return CapabilityEvidence(
                "unavailable",
                operation,
                None,
                None,
                None,
                None,
                f"Normalization was not claimed: {error}",
            )

    def _fairlight_presets(self) -> tuple[str, ...]:
        try:
            values = self.resolve.GetFairlightPresets()
        except Exception:
            return ()
        if not isinstance(values, (list, tuple)):
            return ()
        return tuple(
            sorted(value for value in values if isinstance(value, str) and value)
        )

    def _probe_preset(
        self, presets: tuple[str, ...], requested: str | None
    ) -> CapabilityEvidence:
        selected, evidence = select_fairlight_preset(presets, requested)
        if selected is None:
            return evidence
        return CapabilityEvidence(
            "operator-only",
            evidence.operation,
            evidence.before,
            evidence.request,
            None,
            None,
            "The exact named preset is available, but the public API has no "
            "preset/EQ/dynamics state getter or safe restoration call. The probe "
            "refused to alter the clean timeline; application and verification "
            "remain operator-only on a duplicate timeline.",
        )

    def _render_pcm_wav(
        self, output_dir: Path
    ) -> tuple[CapabilityEvidence, Path | None]:
        operation = "Project audio render format/codec discovery + render job"
        render_dir = output_dir / "render"
        render_dir.mkdir()
        request: dict[str, Any] = {
            "TargetDir": str(render_dir),
            "CustomName": "vera-issue-110-rendered-probe",
            "SelectAllFrames": True,
            "ExportVideo": False,
            "ExportAudio": True,
            "AudioBitDepth": 24,
            "AudioSampleRate": 48000,
        }
        try:
            formats = _mapping(
                self.project.GetAudioRenderFormats(), "audio render formats"
            )
            format_pair = next(
                (
                    (str(name), str(extension))
                    for name, extension in formats.items()
                    if str(extension).casefold().lstrip(".") == "wav"
                ),
                None,
            )
            if format_pair is None:
                raise FairlightProbeError("Resolve exposed no WAV audio render format")
            _, extension = format_pair
            codecs = _mapping(
                self.project.GetAudioRenderCodecs(extension), "WAV audio codecs"
            )
            codec_pair = next(
                (
                    (str(name), str(value))
                    for name, value in codecs.items()
                    if "linear pcm" in f"{name} {value}".casefold()
                ),
                None,
            )
            if codec_pair is None:
                raise FairlightProbeError("Resolve exposed no Linear PCM WAV codec")
            codec_name, codec_value = codec_pair
            request.update({"AudioFormat": extension, "AudioCodec": codec_value})
            before = {
                "audioRenderFormats": dict(formats),
                "wavAudioCodecs": dict(codecs),
            }
            if not self.project.SetCurrentRenderMode(1):
                raise FairlightProbeError("single-clip render mode was unavailable")
            if not self.project.SetCurrentRenderFormatAndCodec(extension, codec_value):
                raise FairlightProbeError("WAV/Linear PCM render selection failed")
            if not self.project.SetRenderSettings(request):
                raise FairlightProbeError("48 kHz PCM render settings were rejected")
            job_id = self.project.AddRenderJob()
            if not isinstance(job_id, str) or not job_id:
                raise FairlightProbeError("AddRenderJob returned no job ID")
            if not self.project.StartRendering([job_id], False):
                raise FairlightProbeError("StartRendering returned false")
            status = self._wait_for_render(job_id)
            rendered = list(render_dir.glob("*.wav"))
            if len(rendered) != 1:
                raise FairlightProbeError(
                    f"expected one rendered WAV, found {len(rendered)}"
                )
            readback = self._wav_evidence(rendered[0])
            readback.update(
                {
                    "jobId": job_id,
                    "jobStatus": status,
                    "selectedCodecDescription": codec_name,
                    "selectedCodecValue": codec_value,
                }
            )
            if (
                readback["sampleRate"] != 48000
                or readback["bitDepth"] != 24
                or readback["codec"] != "Linear PCM"
            ):
                raise FairlightProbeError("rendered WAV format readback differed")
            return (
                CapabilityEvidence(
                    "supported-api",
                    operation,
                    before,
                    request,
                    readback,
                    None,
                    "Resolve discovered WAV/Linear PCM, accepted explicit 48 "
                    "kHz/24-bit settings, completed the render, and the file "
                    "header read back as requested.",
                ),
                rendered[0],
            )
        except Exception as error:
            return (
                CapabilityEvidence(
                    "unavailable",
                    operation,
                    None,
                    request,
                    None,
                    None,
                    f"48 kHz Linear PCM WAV render was not claimed: {error}",
                ),
                None,
            )

    def _wait_for_render(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            status = self.project.GetRenderJobStatus(job_id)
            if not isinstance(status, Mapping):
                raise FairlightProbeError("render job status was unreadable")
            name = str(status.get("JobStatus", ""))
            if name.casefold() == "complete":
                return dict(status)
            if name.casefold() in {"failed", "cancelled", "canceled"}:
                raise FairlightProbeError(f"render job ended as {name}")
            time.sleep(0.25)
        raise FairlightProbeError("render job did not complete within 45 seconds")

    def _probe_attachment(self, rendered_path: Path) -> dict[str, Any]:
        replacement_media = self._import_media(rendered_path)
        self.replacement_media_id = self._media_id(replacement_media)
        original = self._find_item(self.original_media_id, 1)
        if original is None:
            raise FairlightProbeError("original item disappeared before replacement")
        replacement = self._append_audio(
            replacement_media, track_index=2, record_frame=0
        )
        if not self.timeline.SetClipsLinked([original, replacement], True):
            raise FairlightProbeError("linking original and replacement failed")
        linked_ids = {self._item_media_id(item) for item in original.GetLinkedItems()}
        if self.replacement_media_id not in linked_ids:
            raise FairlightProbeError("linked-item readback omitted the replacement")
        if not self.timeline.SetClipsLinked([original, replacement], False):
            raise FairlightProbeError("unlinking original and replacement failed")
        if not original.SetClipEnabled(False) or not replacement.SetClipEnabled(True):
            raise FairlightProbeError("replacement enabled-state mutation failed")
        if (
            original.GetClipEnabled() is not False
            or replacement.GetClipEnabled() is not True
        ):
            raise FairlightProbeError("replacement enabled-state readback differed")
        self._save_reopen()
        original = self._find_item(self.original_media_id, 1)
        replacement_items = self._items_for_media(self.replacement_media_id, 2)
        survived = (
            original is not None
            and original.GetClipEnabled() is False
            and len(replacement_items) == 1
            and replacement_items[0].GetStart(False) == 0
            and replacement_items[0].GetClipEnabled() is True
        )
        if not survived:
            raise FairlightProbeError("replacement state did not survive reopen")
        if original is None:
            raise FairlightProbeError("original item disappeared after reopen")
        if not self.timeline.DeleteClips(replacement_items, False):
            raise FairlightProbeError("replacement removal failed")
        if not original.SetClipEnabled(True):
            raise FairlightProbeError("original restoration failed")
        self._save_reopen()
        original = self._find_item(self.original_media_id, 1)
        replacement_items = self._items_for_media(self.replacement_media_id, 2)
        restored = (
            original is not None
            and original.GetStart(False) == 0
            and original.GetClipEnabled() is True
            and not replacement_items
        )
        return {
            "exactStartFrame": 0,
            "linkReadbackMediaIds": sorted(
                media_id for media_id in linked_ids if media_id is not None
            ),
            "replacementSurvivedReopen": survived,
            "replacementRemoved": not replacement_items,
            "originalRestoredAfterReopen": restored,
            "saveCloseReopenCount": 2,
            "explanation": (
                "Rendered WAV attached at frame 0, linked/unlinked, replaced the "
                "disabled original, survived reopen, was removed, and the "
                "original survived a second reopen enabled."
            ),
        }

    def _save_reopen(self) -> None:
        if self.project is None or self.project_name is None:
            return
        if not self.manager.SaveProject():
            raise FairlightProbeError("SaveProject failed")
        if not self.manager.CloseProject(self.project):
            raise FairlightProbeError("CloseProject failed")
        self.project = self.manager.LoadProject(self.project_name)
        if self.project is None:
            raise FairlightProbeError("LoadProject failed")
        self.pool = self.project.GetMediaPool()
        self.timeline = self.project.GetCurrentTimeline()
        if self.pool is None or self.timeline is None:
            raise FairlightProbeError("reopened project lost its pool or timeline")

    def _find_item(self, media_id: str | None, track_index: int) -> Any | None:
        values = self._items_for_media(media_id, track_index)
        return values[0] if len(values) == 1 else None

    def _items_for_media(self, media_id: str | None, track_index: int) -> list[Any]:
        if self.timeline is None or media_id is None:
            return []
        values = self.timeline.GetItemListInTrack("audio", track_index)
        if not isinstance(values, (list, tuple)):
            return []
        return [item for item in values if self._item_media_id(item) == media_id]

    def _item_media_id(self, item: Any) -> str | None:
        media = item.GetMediaPoolItem()
        return self._media_id(media) if media is not None else None

    def _media_id(self, media: Any) -> str:
        value = media.GetMediaId()
        if not isinstance(value, str) or not value:
            raise FairlightProbeError("media item has no stable ID")
        return value

    def _wav_evidence(self, path: Path) -> dict[str, Any]:
        with wave.open(str(path), "rb") as reader:
            evidence = {
                "path": str(path),
                "sha256": _sha256(path),
                "sampleRate": reader.getframerate(),
                "channels": reader.getnchannels(),
                "bitDepth": reader.getsampwidth() * 8,
                "codec": (
                    "Linear PCM"
                    if reader.getcomptype() == "NONE"
                    else reader.getcomptype()
                ),
                "durationSamples": reader.getnframes(),
            }
        return evidence

    def _preservation(
        self,
        source_path: Path,
        before_hash: str,
        after_hash: str | None,
        original: Any | None,
        replacement_present: bool,
        preserved: bool,
        explanation: str,
    ) -> OriginalAudioEvidence:
        return OriginalAudioEvidence(
            source_path=str(source_path),
            source_sha256_before=before_hash,
            source_sha256_after=after_hash,
            original_media_id=self.original_media_id,
            original_timeline_item_present=original is not None,
            original_clip_enabled=(
                original.GetClipEnabled() if original is not None else None
            ),
            replacement_timeline_item_present=replacement_present,
            preserved=preserved,
            explanation=explanation,
        )


def _validate_config(config: FairlightProbeConfig) -> None:
    if config.external_scripting_setting != "None":
        raise FairlightProbeError("External scripting must remain None")
    if (
        not config.project_name.startswith(PROJECT_PREFIX)
        or config.project_name == PROJECT_PREFIX
        or config.project_name != config.project_name.strip()
        or any(character in config.project_name for character in "\r\n")
    ):
        raise FairlightProbeError(
            "project name must be a unique single-line name beginning "
            f"{PROJECT_PREFIX!r}"
        )
    if not config.output_dir.is_absolute():
        raise FairlightProbeError("outputDir must be absolute")
    if config.output_dir.exists():
        raise FairlightProbeError("outputDir must not already exist")
    try:
        datetime.fromisoformat(config.documentation_retrieved_at)
    except ValueError as error:
        raise FairlightProbeError(
            "documentationRetrievedAt must be an ISO date or timestamp"
        ) from error
    if config.fairlight_preset_name is not None and (
        not config.fairlight_preset_name.strip()
        or config.fairlight_preset_name != config.fairlight_preset_name.strip()
    ):
        raise FairlightProbeError("fairlightPresetName must be nonempty and trimmed")


def _write_synthetic_probe(path: Path) -> None:
    frames = bytearray()
    for sample in range(48000):
        channel_1 = round(6000 * math.sin(2 * math.pi * 440 * sample / 48000))
        channel_2 = round(3000 * math.sin(2 * math.pi * 880 * sample / 48000))
        frames.extend(struct.pack("<hh", channel_1, channel_2))
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        writer.writeframes(frames)


def _documentation_evidence(retrieved_at: str) -> tuple[dict[str, Any], ...]:
    evidence: list[dict[str, Any]] = []
    for path, title in (
        (SCRIPTING_README, "Installed DaVinci Resolve Scripting API README"),
        (SCRIPTING_STUB, "Installed DaVinci Resolve Scripting API type stubs"),
    ):
        evidence.append(
            {
                "title": title,
                "path": str(path),
                "exists": path.is_file(),
                "sha256": _sha256(path) if path.is_file() else None,
                "modifiedAt": (
                    datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
                    if path.is_file()
                    else None
                ),
                "retrievedAt": retrieved_at,
            }
        )
    evidence.extend(
        {
            "title": title,
            "url": url,
            "relevance": relevance,
            "retrievedAt": retrieved_at,
        }
        for title, url, relevance in OFFICIAL_DOCUMENTATION
    )
    return tuple(evidence)


def _failed_execution(
    original_audio: OriginalAudioEvidence, detail: str
) -> ProbeExecution:
    unavailable = CapabilityEvidence(
        "unavailable",
        "not completed",
        None,
        None,
        None,
        None,
        f"Probe stopped after failure: {detail}",
    )
    return ProbeExecution(
        channel_mapping=unavailable,
        capabilities={name: unavailable for name in REQUIRED_CAPABILITIES},
        attachment_path={
            "exactStartFrame": 0,
            "replacementSurvivedReopen": False,
            "replacementRemoved": not original_audio.replacement_timeline_item_present,
            "originalRestoredAfterReopen": original_audio.preserved,
        },
        original_audio=original_audio,
        fairlight_presets=(),
        rendered_wav=None,
        discrepancies=(detail,),
    )


def _json_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise FairlightProbeError(f"{label} was not JSON text")
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as error:
        raise FairlightProbeError(f"{label} was invalid JSON") from error
    return _mapping(loaded, label)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FairlightProbeError(f"{label} was not an object")
    return {str(key): item for key, item in value.items()}


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise FairlightProbeError(f"{label} must be a nonempty string")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
