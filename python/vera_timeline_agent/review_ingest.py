"""BuildJobStore adapter for immutable review-media ingest jobs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from threading import Event, Thread
from typing import Any, Literal

from vera_timeline_agent.build_jobs import (
    INGEST_STAGES,
    BuildJobError,
    BuildJobStore,
    IngestRequest,
    StageContext,
)
from vera_timeline_agent.media_preparation import MediaTools
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.review_proxy import (
    DEFAULT_REVIEW_PROFILE,
    ReviewProfile,
    ReviewSource,
    ReviewStage,
    StageResult,
    inspect_review_source,
    run_review_stage,
    verify_review_stage,
)

Json = dict[str, Any]
ReviewPlaybackVideo = Literal["proxy", "master"]
ReviewPlaybackAudio = Literal["audio-stage", "absent"]
REVIEW_STAGES: tuple[ReviewStage, ...] = ("proxy", "audio", "waveform")


class ReviewIngestError(BuildJobError):
    """The registered source or verified review handoff is invalid."""


@dataclass(frozen=True)
class RegisteredMaster:
    """Project-scoped source registration supplied by the owning registry."""

    project_id: str
    source_id: str
    path: Path
    content_hash: str
    video_stream_index: int | None = None
    audio_stream_index: int | None = None


MasterResolver = Callable[[str, str], RegisteredMaster | None]


@dataclass(frozen=True)
class VerifiedReviewStage:
    stage: ReviewStage
    status: Literal["complete"]
    generation_identity: str
    bundle_path: Path
    receipt_path: Path
    artifact_path: Path | None
    receipt_hash: str
    artifact_hash: str | None


@dataclass(frozen=True)
class VerifiedReviewHandoff:
    """Current registered master and separately verified browser playback media."""

    project_id: str
    source_id: str
    generation_identity: str
    master_path: Path
    master_content_hash: str
    source_probe_hash: str
    source_rate: Fraction
    source_pts_origin: Fraction
    source_frame_count: int
    profile_hash: str
    tool_hash: str
    generator_hash: str
    job_status: Literal["complete"]
    video_source: ReviewPlaybackVideo
    video_path: Path
    video_muted: Literal[True]
    proxy_path: Path | None
    frame_map: Json | None
    audio_source: ReviewPlaybackAudio
    audio_path: Path | None
    audio_timing: Json | None
    waveform_path: Path | None
    stages: tuple[VerifiedReviewStage, ...]


@dataclass(frozen=True)
class VerifiedReviewSession:
    """Immutable source/mapping snapshot verified when the session is opened.

    Range mapping does not re-read media. Open a new session to revalidate the
    current registered source and derivative artifacts.
    """

    project_id: str
    source_id: str
    generation_identity: str
    master_path: Path
    master_content_hash: str
    source_probe_hash: str
    video_source: ReviewPlaybackVideo
    video_path: Path
    video_muted: Literal[True]
    proxy_path: Path | None
    audio_source: ReviewPlaybackAudio
    audio_path: Path | None
    waveform_path: Path | None
    source_rate: Fraction
    source_pts_origin: Fraction
    source_frame_count: int
    review_pts_origin: Fraction
    proxy_to_master_offset: Fraction
    mapping_hash: str | None

    def map_proxy_frame_range(self, start_frame: int, end_frame: int) -> Json:
        if type(start_frame) is not int or type(end_frame) is not int:
            raise ReviewIngestError("frame range bounds must be integers")
        if not 0 <= start_frame < end_frame <= self.source_frame_count:
            raise ReviewIngestError(
                "frame range must be a non-empty half-open source range"
            )
        if self.source_rate <= 0 or self.source_frame_count <= 0:
            raise ReviewIngestError("verified source frame facts are invalid")

        def boundary(frame_index: int) -> Json:
            relative_time = Fraction(frame_index, 1) / self.source_rate
            review_pts = self.review_pts_origin + relative_time
            source_pts = review_pts + self.proxy_to_master_offset
            return {
                "reviewFrameIndex": frame_index,
                "sourceFrameIndex": frame_index,
                "relativeTimeSeconds": _wire_fraction(relative_time),
                "reviewPtsSeconds": _wire_fraction(review_pts),
                "sourcePtsSeconds": _wire_fraction(source_pts),
            }

        return {
            "method": "frame-index-identity/v1",
            "projectId": self.project_id,
            "sourceId": self.source_id,
            "generationIdentity": self.generation_identity,
            "sourceContentHash": self.master_content_hash,
            "sourceProbeHash": self.source_probe_hash,
            "videoSource": self.video_source,
            "mappingHash": self.mapping_hash,
            "frameRange": {
                "startInclusive": start_frame,
                "endExclusive": end_frame,
            },
            "sourceRate": _wire_fraction(self.source_rate),
            "sourcePtsOrigin": _wire_fraction(self.source_pts_origin),
            "startBoundary": boundary(start_frame),
            "endBoundary": boundary(end_frame),
        }


def _valid_identity(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _review_identity(job_identity: str) -> str:
    return f"sha256:{job_identity}"


def _wire_fraction(value: Fraction) -> Json:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _read_fraction(value: object, label: str) -> Fraction:
    if (
        not isinstance(value, dict)
        or type(value.get("numerator")) is not int
        or type(value.get("denominator")) is not int
        or value["denominator"] <= 0
    ):
        raise ReviewIngestError(f"invalid {label} in verified frame mapping")
    return Fraction(value["numerator"], value["denominator"])


def _require_text(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or value.strip() != value
    ):
        raise ReviewIngestError(f"invalid {label}")
    return value


class ReviewIngestAdapter:
    """Dispatch durable ingest stages through the review derivative cache.

    The resolver is the trust boundary for registered source ownership. Its
    returned project/source identity is checked again before media inspection.
    """

    def __init__(
        self,
        store: BuildJobStore,
        *,
        cache_root: Path,
        resolve_master: MasterResolver,
        profile: ReviewProfile = DEFAULT_REVIEW_PROFILE,
        tools: MediaTools | None = None,
    ) -> None:
        self.store = store
        self.cache_root = cache_root.resolve()
        self.resolve_master = resolve_master
        self.profile = profile
        self.tools = tools

    def submit_ingest(
        self, project_id: str, source_id: str, idempotency_key: str
    ) -> str:
        """Inspect a registered master and queue its immutable review generation."""
        project_id = _require_text(project_id, "project ID")
        source_id = _require_text(source_id, "source ID")
        idempotency_key = _require_text(idempotency_key, "idempotency key")
        _, source = self._inspect_registered_master(project_id, source_id)
        generation_identity = source.generation_identity.removeprefix("sha256:")
        if not _valid_identity(generation_identity):
            raise ReviewIngestError("inspected review generation identity is invalid")
        request_scope = hashlib.sha256(
            f"review-ingest/v1\0{project_id}\0{source_id}\0{idempotency_key}".encode()
        ).hexdigest()
        store_idempotency_key = (
            f"review-ingest/v1:{request_scope}:{generation_identity}"
        )
        return self.store.submit_ingest(
            IngestRequest(
                project_id,
                source_id,
                generation_identity,
                store_idempotency_key,
            )
        )

    def _validate_context(self, context: StageContext) -> ReviewStage:
        if context.job_kind != "ingest":
            raise ReviewIngestError("review media stages require an ingest job")
        project_id = _require_text(context.project_id, "project ID")
        job_id = _require_text(context.job_id, "job ID")
        source_id = _require_text(context.source_id, "source ID")
        if not _valid_identity(context.generation_identity):
            raise ReviewIngestError("invalid ingest generation identity")
        if context.stage not in INGEST_STAGES:
            raise ReviewIngestError("unknown ingest stage")
        stage = context.stage
        expected_key = hashlib.sha256(
            f"{project_id}\0{job_id}\0{stage}".encode()
        ).hexdigest()
        expected_output = self.store.artifacts / job_id / stage / "output"
        if context.stage_key != expected_key or context.output_path != expected_output:
            raise ReviewIngestError("stage context does not match its durable job path")
        job = self.store.status(project_id, job_id)
        if (
            job["kind"] != "ingest"
            or job["sourceId"] != source_id
            or job["generationIdentity"] != context.generation_identity
            or job["activeStage"] != stage
            or job["leaseEpoch"] != context.lease_epoch
        ):
            raise ReviewIngestError("stage context differs from the stored ingest job")
        return stage  # type: ignore[return-value]

    def _inspect_registered_source(
        self, project_id: str, source_id: str, generation_identity: str
    ) -> tuple[RegisteredMaster, ReviewSource]:
        registration, source = self._inspect_registered_master(project_id, source_id)
        if source.generation_identity != _review_identity(generation_identity):
            raise ReviewIngestError(
                "registered master generation identity differs from the ingest job"
            )
        return registration, source

    def _inspect_registered_master(
        self, project_id: str, source_id: str
    ) -> tuple[RegisteredMaster, ReviewSource]:
        registration = self.resolve_master(project_id, source_id)
        if registration is None:
            raise ReviewIngestError("registered master was not found")
        if (
            not isinstance(registration, RegisteredMaster)
            or registration.project_id != project_id
            or registration.source_id != source_id
            or not isinstance(registration.path, Path)
            or not isinstance(registration.content_hash, str)
            or not registration.content_hash.startswith("sha256:")
            or not _valid_identity(registration.content_hash.removeprefix("sha256:"))
        ):
            raise ReviewIngestError(
                "registered master ownership does not match the job"
            )
        source = inspect_review_source(
            registration.path,
            profile=self.profile,
            video_stream_index=registration.video_stream_index,
            audio_stream_index=registration.audio_stream_index,
            tools=self.tools,
        )
        if source.inspection.content_hash != registration.content_hash:
            raise ReviewIngestError(
                "registered master content hash differs from inspected media"
            )
        return registration, source

    def verified_stage(self, context: StageContext) -> StageResult | None:
        """Re-check the derivative and durable marker for the active stage."""
        stage = self._validate_context(context)
        with self._lease_heartbeat(context):
            _, source = self._inspect_registered_source(
                context.project_id,
                context.source_id or "",
                context.generation_identity or "",
            )
            result = verify_review_stage(
                source,
                stage,
                cache_root=self.cache_root,
                output_path=context.output_path,
            )
            if result is not None:
                self._check_result(result, stage, source.generation_identity)
            return result

    def reconcile(self, context: StageContext) -> bool:
        return self.verified_stage(context) is not None

    def execute(self, context: StageContext) -> None:
        stage = self._validate_context(context)
        with self._lease_heartbeat(context):
            _, source = self._inspect_registered_source(
                context.project_id,
                context.source_id or "",
                context.generation_identity or "",
            )
            result = run_review_stage(
                source,
                stage,
                cache_root=self.cache_root,
                output_path=context.output_path,
            )
            self._check_result(result, stage, source.generation_identity)

    @contextmanager
    def _lease_heartbeat(self, context: StageContext) -> Iterator[None]:
        """Renew the active store lease while inspection or media work is blocked."""
        context.renew_lease()
        job = self.store.status(context.project_id, context.job_id)
        deadline = job.get("leaseUntil")
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
            raise ReviewIngestError("active ingest lease has no deadline")
        remaining = deadline - self.store.clock()
        interval = max(0.001, min(30.0, remaining / 3))
        stopped = Event()
        errors: list[Exception] = []

        def renew_until_stopped() -> None:
            while not stopped.wait(interval):
                try:
                    context.renew_lease()
                except Exception as error:
                    errors.append(error)
                    stopped.set()
                    return

        heartbeat = Thread(
            target=renew_until_stopped,
            name=f"review-ingest-lease-{context.job_id}-{context.stage}",
            daemon=True,
        )
        heartbeat.start()
        try:
            yield
        except BaseException:
            stopped.set()
            heartbeat.join()
            raise
        else:
            stopped.set()
            heartbeat.join()
            if errors:
                raise errors[0]

    def verified_handoff(self, project_id: str, job_id: str) -> VerifiedReviewHandoff:
        """Return playback paths only after all stage artifacts are re-verified."""
        project_id = _require_text(project_id, "project ID")
        job_id = _require_text(job_id, "job ID")
        job = self.store.status(project_id, job_id)
        if job["kind"] != "ingest" or job["status"] != "complete":
            raise ReviewIngestError("review handoff requires a completed ingest job")
        source_id = _require_text(job.get("sourceId"), "source ID")
        generation_identity = job.get("generationIdentity")
        if not isinstance(generation_identity, str) or not _valid_identity(
            generation_identity
        ):
            raise ReviewIngestError("stored ingest generation identity is invalid")
        if not self.store._verify_completed(project_id, job_id):
            raise ReviewIngestError("completed ingest job markers are not intact")

        stage_rows = {
            row["name"]: row
            for row in job["stages"]
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        }
        if set(stage_rows) != set(INGEST_STAGES):
            raise ReviewIngestError("stored ingest stages are incomplete")
        output_paths: dict[str, Path] = {}
        for stage in REVIEW_STAGES:
            row = stage_rows[stage]
            expected = self.store.artifacts / job_id / stage / "output"
            if row.get("status") != "complete" or row.get("path") != str(expected):
                raise ReviewIngestError(f"stored {stage} stage is not complete")
            output_paths[stage] = expected

        _, source = self._inspect_registered_source(
            project_id, source_id, generation_identity
        )
        results: dict[str, StageResult] = {}
        for stage in REVIEW_STAGES:
            result = verify_review_stage(
                source,
                stage,
                cache_root=self.cache_root,
                output_path=output_paths[stage],
            )
            if result is None:
                raise ReviewIngestError(
                    f"completed {stage} stage has no verified bundle"
                )
            self._check_result(result, stage, source.generation_identity)
            results[stage] = result

        proxy_result = results["proxy"]
        audio_result = results["audio"]
        waveform_result = results["waveform"]
        proxy_evidence = proxy_result.receipt.get("evidence")
        if not isinstance(proxy_evidence, dict):
            raise ReviewIngestError("proxy stage has no verified playback evidence")
        playback = proxy_evidence.get("reviewPlayback")
        if not isinstance(playback, dict) or playback.get("videoUsable") is not True:
            raise ReviewIngestError(
                "review playback is unavailable for this source profile"
            )

        proxy_path = proxy_result.artifact_path
        if proxy_path is None:
            if (
                playback.get("videoSource") != "master"
                or playback.get("masterBrowserSafe") is not True
            ):
                raise ReviewIngestError(
                    "registered master is not browser-safe for review"
                )
            video_source: ReviewPlaybackVideo = "master"
            video_path = source.path
            frame_map = None
        else:
            if (
                playback.get("videoSource") != "proxy"
                or proxy_evidence.get("proxyHasAudio") is not False
            ):
                raise ReviewIngestError(
                    "proxy playback evidence does not prove silent video"
                )
            frame_map = proxy_evidence.get("frameMap")
            if not isinstance(frame_map, dict):
                raise ReviewIngestError("proxy stage has no verified frame mapping")
            video_source = "proxy"
            video_path = proxy_path

        audio_path = audio_result.artifact_path
        audio_evidence = audio_result.receipt.get("evidence")
        if not isinstance(audio_evidence, dict):
            raise ReviewIngestError("audio stage has no verified timing evidence")
        if (source.inspection.audio is None) != (audio_path is None):
            raise ReviewIngestError(
                "audio derivative does not match the registered master"
            )
        if audio_path is None:
            if (
                playback.get("audioSource") != "absent"
                or audio_evidence.get("status") != "absent"
            ):
                raise ReviewIngestError(
                    "audio playback evidence does not match the source"
                )
            audio_source: ReviewPlaybackAudio = "absent"
            audio_timing = None
            waveform_path = waveform_result.artifact_path
            if waveform_path is not None:
                raise ReviewIngestError("waveform exists without an audio derivative")
        else:
            if (
                playback.get("audioSource") != "audio-stage"
                or audio_evidence.get("status") != "aligned"
            ):
                raise ReviewIngestError(
                    "audio derivative is not proven aligned to the master"
                )
            self._validate_audio_timing(audio_evidence)
            audio_source = "audio-stage"
            audio_timing = dict(audio_evidence)
            waveform_path = waveform_result.artifact_path
            if waveform_path is None:
                raise ReviewIngestError(
                    "completed audio source has no verified waveform"
                )

        stages = tuple(
            self._stage_evidence(stage, results[stage]) for stage in REVIEW_STAGES
        )
        return VerifiedReviewHandoff(
            project_id=project_id,
            source_id=source_id,
            generation_identity=generation_identity,
            master_path=source.path,
            master_content_hash=source.inspection.content_hash,
            source_probe_hash=source.inspection.probe_hash,
            source_rate=source.inspection.rate,
            source_pts_origin=source.inspection.pts_origin,
            source_frame_count=len(source.inspection.video_frames),
            profile_hash=source.profile_hash,
            tool_hash=source.tool_hash,
            generator_hash=source.generator_hash,
            job_status="complete",
            video_source=video_source,
            video_path=video_path,
            video_muted=True,
            proxy_path=proxy_path,
            frame_map=frame_map,
            audio_source=audio_source,
            audio_path=audio_path,
            audio_timing=audio_timing,
            waveform_path=waveform_path,
            stages=stages,
        )

    def open_verified_review_session(
        self, project_id: str, job_id: str
    ) -> VerifiedReviewSession:
        """Revalidate the ingest once and open an immutable mapping snapshot."""
        handoff = self.verified_handoff(project_id, job_id)
        rate = handoff.source_rate
        origin = handoff.source_pts_origin
        if rate <= 0 or handoff.source_frame_count <= 0:
            raise ReviewIngestError("verified source frame facts are invalid")

        mapping_hash: str | None = None
        if handoff.video_source == "proxy":
            frame_map = handoff.frame_map
            if not isinstance(frame_map, dict):
                raise ReviewIngestError("verified proxy has no frame mapping")
            if (
                frame_map.get("method") != "frame-index-identity/v1"
                or frame_map.get("sourceFrameCount") != handoff.source_frame_count
                or frame_map.get("proxyFrameCount") != handoff.source_frame_count
                or _read_fraction(frame_map.get("sourceRate"), "source rate") != rate
                or _read_fraction(frame_map.get("proxyRate"), "proxy rate") != rate
                or _read_fraction(frame_map.get("sourcePtsOrigin"), "source PTS origin")
                != origin
            ):
                raise ReviewIngestError(
                    "verified proxy mapping differs from source frames"
                )
            review_origin = _read_fraction(
                frame_map.get("proxyPtsOrigin"), "proxy PTS origin"
            )
            proxy_to_master = _read_fraction(
                frame_map.get("proxyToMasterOffset"), "proxy-to-master offset"
            )
            mapping_hash = frame_map.get("mappingHash")
            if not isinstance(mapping_hash, str):
                raise ReviewIngestError("verified proxy mapping has no identity hash")
            if review_origin + proxy_to_master != origin:
                raise ReviewIngestError(
                    "proxy PTS offset does not map to the master origin"
                )
        else:
            if handoff.frame_map is not None:
                raise ReviewIngestError(
                    "master playback unexpectedly has a proxy mapping"
                )
            review_origin = origin
            proxy_to_master = Fraction(0)
        return VerifiedReviewSession(
            project_id=handoff.project_id,
            source_id=handoff.source_id,
            generation_identity=handoff.generation_identity,
            master_path=handoff.master_path,
            master_content_hash=handoff.master_content_hash,
            source_probe_hash=handoff.source_probe_hash,
            video_source=handoff.video_source,
            video_path=handoff.video_path,
            video_muted=handoff.video_muted,
            proxy_path=handoff.proxy_path,
            audio_source=handoff.audio_source,
            audio_path=handoff.audio_path,
            waveform_path=handoff.waveform_path,
            source_rate=rate,
            source_pts_origin=origin,
            source_frame_count=handoff.source_frame_count,
            review_pts_origin=review_origin,
            proxy_to_master_offset=proxy_to_master,
            mapping_hash=mapping_hash,
        )

    def map_proxy_frame_range(
        self, project_id: str, job_id: str, start_frame: int, end_frame: int
    ) -> Json:
        """Verify for one request; use a session for interactive ranges."""
        return self.open_verified_review_session(
            project_id, job_id
        ).map_proxy_frame_range(start_frame, end_frame)

    @staticmethod
    def _validate_audio_timing(evidence: Json) -> None:
        numeric = (
            "sampleRate",
            "channels",
            "outputAudioFrames",
            "audioOffsetSamples",
            "sourceSamplesSkipped",
            "leadingSilenceSamples",
            "sourceSamplesCopied",
            "trailingSilenceSamples",
        )
        if any(type(evidence.get(name)) is not int for name in numeric):
            raise ReviewIngestError("audio timing evidence is incomplete")
        if any(
            evidence[name] < 0
            for name in numeric
            if name not in {"sampleRate", "audioOffsetSamples"}
        ):
            raise ReviewIngestError("audio timing evidence contains a negative count")
        if (
            evidence["sampleRate"] <= 0
            or evidence["channels"] <= 0
            or evidence["outputAudioFrames"] <= 0
        ):
            raise ReviewIngestError("audio timing evidence has invalid PCM dimensions")
        if not isinstance(evidence.get("sourceVideoOrigin"), dict) or not isinstance(
            evidence.get("sourceAudioOrigin"), dict
        ):
            raise ReviewIngestError("audio timing evidence has no master origin")

    @staticmethod
    def _check_result(
        result: StageResult, stage: ReviewStage, generation_identity: str
    ) -> None:
        if result.stage != stage or result.generation_identity != generation_identity:
            raise ReviewIngestError("review stage result identity differs from the job")

    @staticmethod
    def _stage_evidence(stage: ReviewStage, result: StageResult) -> VerifiedReviewStage:
        artifact = result.receipt.get("artifact")
        artifact_hash = (
            artifact.get("contentHash") if isinstance(artifact, dict) else None
        )
        return VerifiedReviewStage(
            stage=stage,
            status="complete",
            generation_identity=result.generation_identity.removeprefix("sha256:"),
            bundle_path=result.bundle_path,
            receipt_path=result.receipt_path,
            artifact_path=result.artifact_path,
            receipt_hash=identity_hash(result.receipt),
            artifact_hash=artifact_hash if isinstance(artifact_hash, str) else None,
        )
