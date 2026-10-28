from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
import vera_timeline_agent.review_ingest as review_ingest
import vera_timeline_agent.review_proxy as review_proxy
from vera_timeline_agent.build_jobs import BuildJobStore, IngestRequest, StageContext
from vera_timeline_agent.media_preparation import MediaInspection, MediaTools, file_hash
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.review_ingest import (
    RegisteredMaster,
    ReviewIngestAdapter,
    ReviewIngestError,
)
from vera_timeline_agent.review_proxy import ReviewProxyError, StageResult

GENERATION = "a" * 64
REVIEW_GENERATION = f"sha256:{GENERATION}"


@dataclass
class Clock:
    value: float = 100.0

    def __call__(self) -> float:
        return self.value


class SingleThreadMediaTools(MediaTools):
    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        if command[0] == self.ffmpeg and "-i" in command:
            command = command.copy()
            input_position = command.index("-i")
            command[input_position:input_position] = [
                "-threads:v",
                "1",
                "-threads:a",
                "1",
            ]
            command[-1:-1] = ["-threads:v", "1", "-threads:a", "1"]
        return super().run(command, timeout=timeout)


class InterruptAfterProxy:
    def __init__(self, adapter: ReviewIngestAdapter) -> None:
        self.adapter = adapter
        self.interrupted = False

    def reconcile(self, context: StageContext) -> bool:
        return self.adapter.reconcile(context)

    def execute(self, context: StageContext) -> None:
        self.adapter.execute(context)
        if context.stage == "proxy" and not self.interrupted:
            self.interrupted = True
            raise KeyboardInterrupt("simulated interruption after proxy publication")


@dataclass(frozen=True)
class SyntheticInspection:
    content_hash: str
    probe_hash: str = "probe-hash"
    audio: dict[str, Any] | None = field(default_factory=lambda: {"index": 1})
    rate: Fraction = Fraction(25)
    pts_origin: Fraction = Fraction(0)
    video_frames: list[dict[str, Any]] = field(
        default_factory=lambda: [{} for _ in range(24)]
    )


@dataclass(frozen=True)
class SyntheticSource:
    path: Path
    inspection: SyntheticInspection
    generation_identity: str
    profile_hash: str = "profile-hash"
    tool_hash: str = "tool-hash"
    generator_hash: str = "generator-hash"


class SyntheticReviewProxy:
    def __init__(
        self,
        master: Path,
        *,
        video_usable: bool = True,
        proxy_required: bool = True,
        master_browser_safe: bool = False,
        source_rate: Fraction = Fraction(25),
        source_pts_origin: Fraction = Fraction(0),
        source_frame_count: int = 24,
    ) -> None:
        self.master = master
        self.original_bytes = master.read_bytes()
        self.video_usable = video_usable
        self.proxy_required = proxy_required
        self.master_browser_safe = master_browser_safe
        self.source_rate = source_rate
        self.source_pts_origin = source_pts_origin
        self.source_frame_count = source_frame_count
        self.results: dict[tuple[str, str], StageResult] = {}
        self.runs: dict[str, int] = {"proxy": 0, "audio": 0, "waveform": 0}
        self.verifications: dict[str, int] = {"proxy": 0, "audio": 0, "waveform": 0}
        self.inspect_calls = 0
        self.interrupt_after_publish: str | None = None

    def inspect(self, path: Path, **_: Any) -> SyntheticSource:
        self.inspect_calls += 1
        content = path.read_bytes()
        changed = content != self.original_bytes
        return cast(
            SyntheticSource,
            SyntheticSource(
                path.resolve(),
                SyntheticInspection(
                    f"sha256:{hashlib.sha256(content).hexdigest()}",
                    rate=self.source_rate,
                    pts_origin=self.source_pts_origin,
                    video_frames=[{} for _ in range(self.source_frame_count)],
                ),
                f"sha256:{'b' * 64}" if changed else REVIEW_GENERATION,
            ),
        )

    def run(
        self,
        source: SyntheticSource,
        stage: str,
        *,
        cache_root: Path,
        output_path: Path,
    ) -> StageResult:
        self.runs[stage] += 1
        bundle = cache_root / source.generation_identity / stage / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        artifact_name = {
            "proxy": "proxy.mp4",
            "audio": "audio.wav",
            "waveform": "waveform.json",
        }[stage]
        artifact = (
            None
            if stage == "proxy" and not self.proxy_required
            else bundle / artifact_name
        )
        if artifact is not None:
            artifact.write_bytes(f"verified-{stage}".encode())
            artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            artifact_record = {
                "name": artifact_name,
                "size": artifact.stat().st_size,
                "contentHash": f"sha256:{artifact_digest}",
            }
        else:
            artifact_record = None
        if stage == "proxy":
            video_source = "proxy" if self.proxy_required else "master"
            source_rate = source.inspection.rate
            source_origin = source.inspection.pts_origin
            frame_count = len(source.inspection.video_frames)
            proxy_to_master = Fraction(7, 1001)
            proxy_origin = source_origin - proxy_to_master
            evidence: dict[str, Any] = {
                "decision": {"required": self.proxy_required},
                "frameMap": (
                    {
                        "method": "frame-index-identity/v1",
                        "sourceFrameCount": frame_count,
                        "proxyFrameCount": frame_count,
                        "sourceRate": self._wire_fraction(source_rate),
                        "proxyRate": self._wire_fraction(source_rate),
                        "sourcePtsOrigin": self._wire_fraction(source_origin),
                        "proxyPtsOrigin": self._wire_fraction(proxy_origin),
                        "proxyToMasterOffset": self._wire_fraction(proxy_to_master),
                        "mappingHash": "mapping-hash",
                    }
                    if self.proxy_required
                    else None
                ),
                "proxyHasAudio": False if self.proxy_required else None,
                "reviewPlayback": {
                    "videoSource": video_source,
                    "videoUsable": self.video_usable,
                    "masterBrowserSafe": self.master_browser_safe,
                    "audioSource": "audio-stage",
                    "audioRequired": True,
                },
            }
        elif stage == "audio":
            evidence = {
                "status": "aligned",
                "sampleRate": 48000,
                "channels": 2,
                "sampleWidthBytes": 2,
                "sourceAudioFrames": 48000,
                "outputAudioFrames": 48000,
                "sourceVideoFrameCount": 24,
                "sourceAudioOrigin": {"numerator": 1, "denominator": 100},
                "sourceVideoOrigin": {"numerator": 0, "denominator": 1},
                "audioOffsetFromVideo": {"numerator": 1, "denominator": 100},
                "audioOffsetSamples": 480,
                "sourceSamplesSkipped": 0,
                "leadingSilenceSamples": 480,
                "sourceSamplesCopied": 47520,
                "trailingSilenceSamples": 0,
            }
        else:
            evidence = {"status": "ready", "audioHash": "audio-hash", "windowMs": 100}
        receipt = {
            "stage": stage,
            "generationIdentity": source.generation_identity,
            "artifact": artifact_record,
            "evidence": evidence,
        }
        result = StageResult(
            stage,  # type: ignore[arg-type]
            source.generation_identity,
            bundle,
            bundle / "receipt.json",
            artifact,
            output_path,
            False,
            receipt,
        )
        result.receipt_path.write_bytes(canonical_json_bytes(receipt))
        self.results[(source.generation_identity, stage)] = result
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self._marker(result))
        if self.interrupt_after_publish == stage:
            self.interrupt_after_publish = None
            raise KeyboardInterrupt
        return result

    def verify(
        self,
        source: SyntheticSource,
        stage: str,
        *,
        cache_root: Path,
        output_path: Path,
    ) -> StageResult | None:
        del cache_root
        self.verifications[stage] += 1
        result = self.results.get((source.generation_identity, stage))
        if not output_path.exists():
            return None
        if result is None or output_path.read_bytes() != self._marker(result):
            raise ReviewIngestError(f"synthetic {stage} marker is corrupt")
        if result.artifact_path is not None:
            artifact_digest = hashlib.sha256(
                result.artifact_path.read_bytes()
            ).hexdigest()
            actual_hash = f"sha256:{artifact_digest}"
            if actual_hash != result.receipt["artifact"]["contentHash"]:
                raise ReviewIngestError(f"synthetic {stage} derivative is corrupt")
        return replace(result, output_path=output_path, reused=True)

    @staticmethod
    def _marker(result: StageResult) -> bytes:
        return canonical_json_bytes(
            {
                "generationIdentity": result.generation_identity,
                "stage": result.stage,
                "bundleId": result.bundle_path.name,
                "receiptHash": identity_hash(result.receipt),
            }
        )

    @staticmethod
    def _wire_fraction(value: Fraction) -> dict[str, int]:
        return {"numerator": value.numerator, "denominator": value.denominator}


def request(
    *,
    project_id: str = "project-a",
    source_id: str = "source-a",
    idempotency_key: str = "ingest-1",
) -> IngestRequest:
    return IngestRequest(
        project_id,
        source_id,
        GENERATION,
        idempotency_key,
    )


def adapter_for(
    store: BuildJobStore,
    master: Path,
    proxy: SyntheticReviewProxy,
    monkeypatch: pytest.MonkeyPatch,
    *,
    registration: RegisteredMaster | None = None,
) -> ReviewIngestAdapter:
    monkeypatches: dict[str, Any] = {
        "inspect_review_source": proxy.inspect,
        "run_review_stage": proxy.run,
        "verify_review_stage": proxy.verify,
    }
    for name, value in monkeypatches.items():
        monkeypatch.setattr(review_ingest, name, value)
    registered = registration
    return ReviewIngestAdapter(
        store,
        cache_root=store.root / "review-cache",
        resolve_master=lambda project_id, source_id: (
            registered
            if registered is not None
            else RegisteredMaster(
                project_id,
                source_id,
                master,
                f"sha256:{hashlib.sha256(master.read_bytes()).hexdigest()}",
            )
        ),
    )


def test_restart_reconciles_published_marker_and_handoff_has_verified_playback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master.mp4"
    master.write_bytes(b"synthetic master bytes")
    proxy = SyntheticReviewProxy(master)
    clock = Clock()
    store = BuildJobStore(tmp_path / "jobs", clock=clock)
    job_id = store.submit_ingest(request())
    adapter = adapter_for(store, master, proxy, monkeypatch)
    proxy.interrupt_after_publish = "proxy"

    with pytest.raises(KeyboardInterrupt):
        store.run_one("project-a", job_id, "worker-a", adapter, lease_seconds=5)
    assert store.status("project-a", job_id)["stages"][0]["status"] == "running"
    assert proxy.runs["proxy"] == 1

    clock.value += 6
    restarted = BuildJobStore(tmp_path / "jobs", clock=clock)
    restarted_adapter = adapter_for(restarted, master, proxy, monkeypatch)
    for _ in range(3):
        assert restarted.run_one(
            "project-a", job_id, "worker-b", restarted_adapter, lease_seconds=5
        )

    assert proxy.runs == {"proxy": 1, "audio": 1, "waveform": 1}
    before_handoff_inspections = proxy.inspect_calls
    handoff = restarted_adapter.verified_handoff("project-a", job_id)

    assert handoff.job_status == "complete"
    assert handoff.master_path == master.resolve()
    assert handoff.video_source == "proxy"
    assert handoff.video_path == handoff.proxy_path
    assert handoff.video_muted is True
    assert (
        handoff.frame_map
        == proxy.results[(REVIEW_GENERATION, "proxy")].receipt["evidence"]["frameMap"]
    )
    assert handoff.audio_source == "audio-stage"
    assert (
        handoff.audio_path == proxy.results[(REVIEW_GENERATION, "audio")].artifact_path
    )
    assert handoff.audio_timing is not None
    assert handoff.audio_timing["audioOffsetSamples"] == 480
    assert handoff.audio_timing["leadingSilenceSamples"] == 480
    assert (
        handoff.waveform_path
        == proxy.results[(REVIEW_GENERATION, "waveform")].artifact_path
    )
    assert [(stage.stage, stage.status) for stage in handoff.stages] == [
        ("proxy", "complete"),
        ("audio", "complete"),
        ("waveform", "complete"),
    ]
    assert all(stage.receipt_hash for stage in handoff.stages)
    assert proxy.inspect_calls > before_handoff_inspections
    assert proxy.verifications == {"proxy": 3, "audio": 3, "waveform": 3}

    cast(Path, handoff.proxy_path).write_bytes(b"tampered proxy")
    with pytest.raises(ReviewIngestError, match="derivative is corrupt"):
        restarted_adapter.verified_handoff("project-a", job_id)


def test_adapter_rejects_wrong_registered_project_or_source_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master.mp4"
    master.write_bytes(b"synthetic master bytes")
    proxy = SyntheticReviewProxy(master)
    store = BuildJobStore(tmp_path / "jobs")
    job_id = store.submit_ingest(request())
    adapter = adapter_for(
        store,
        master,
        proxy,
        monkeypatch,
        registration=RegisteredMaster(
            "project-b",
            "source-a",
            master,
            file_hash(master),
        ),
    )

    assert not store.run_one("project-a", job_id, "worker-a", adapter)
    status = store.status("project-a", job_id)
    assert status["status"] == "failed"
    assert "ownership does not match" in str(status["lastError"])
    assert proxy.runs == {"proxy": 0, "audio": 0, "waveform": 0}


def test_adapter_rejects_generation_change_and_unusable_master_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master.mp4"
    master.write_bytes(b"synthetic master bytes")
    proxy = SyntheticReviewProxy(master)
    store = BuildJobStore(tmp_path / "jobs")
    job_id = store.submit_ingest(request())
    adapter = adapter_for(store, master, proxy, monkeypatch)

    master.write_bytes(b"changed master bytes")
    assert not store.run_one("project-a", job_id, "worker-a", adapter)
    assert "generation identity differs" in str(
        store.status("project-a", job_id)["lastError"]
    )
    assert proxy.runs == {"proxy": 0, "audio": 0, "waveform": 0}

    unsafe_store = BuildJobStore(tmp_path / "unsafe-jobs")
    unsafe_job_id = unsafe_store.submit_ingest(request(idempotency_key="unsafe-ingest"))
    unsafe_proxy = SyntheticReviewProxy(
        master, video_usable=False, proxy_required=False, master_browser_safe=False
    )
    unsafe_adapter = adapter_for(unsafe_store, master, unsafe_proxy, monkeypatch)
    for _ in range(3):
        assert unsafe_store.run_one(
            "project-a", unsafe_job_id, "worker-a", unsafe_adapter
        )

    with pytest.raises(ReviewIngestError, match="playback is unavailable"):
        unsafe_adapter.verified_handoff("project-a", unsafe_job_id)


class SyntheticTools:
    ffmpeg = "synthetic-ffmpeg"
    ffprobe = "synthetic-ffprobe"

    def fingerprint(self) -> dict[str, str]:
        return {"fixtureTools": "synthetic-media-tools/v1"}

    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        del timeout
        if "-show_streams" in command:
            return json.dumps(
                {
                    "streams": [
                        {"index": 0, "codec_type": "video"},
                        {"index": 1, "codec_type": "audio"},
                    ]
                }
            ).encode()
        return b""


def synthetic_media_inspection(path: Path) -> MediaInspection:
    video = {
        "index": 0,
        "codec_type": "video",
        "codec_name": "h264",
        "profile": "Baseline",
        "pix_fmt": "yuv420p",
        "field_order": "progressive",
        "sample_aspect_ratio": "1:1",
        "width": 640,
        "height": 360,
        "avg_frame_rate": "25/1",
        "r_frame_rate": "25/1",
        "time_base": "1/25",
        "bit_rate": "2000000",
    }
    audio = {
        "index": 1,
        "codec_type": "audio",
        "codec_name": "aac",
        "sample_rate": "48000",
        "channels": 2,
    }
    video_frames = [
        {
            "stream_index": 0,
            "pts": 0,
            "duration": 1,
            "width": 640,
            "height": 360,
            "pix_fmt": "yuv420p",
            "sample_aspect_ratio": "1:1",
            "interlaced_frame": 0,
        }
    ]
    audio_frames = [
        {
            "stream_index": 1,
            "pts": 480,
            "duration": 48000,
            "nb_samples": 48000,
        }
    ]
    probe = {
        "streams": [video, audio],
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "bit_rate": "2000000",
            "duration": "0.04",
        },
        "frames": video_frames + audio_frames,
    }
    return MediaInspection(
        probe=probe,
        probe_hash=identity_hash(probe),
        content_hash=file_hash(path),
        video=video,
        video_frames=video_frames,
        rate=Fraction(25),
        time_base=Fraction(1, 25),
        pts_origin=Fraction(0),
        audio=audio,
        audio_frames=audio_frames,
        audio_origin=Fraction(1, 100),
        audio_samples=48000,
        audio_hash=None,
        audio_timestamp_residual=Fraction(0),
        audio_timestamp_drift=Fraction(0),
    )


def test_adapter_normalizes_review_hash_and_binds_registered_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "registered-master.mp4"
    master.write_bytes(b"synthetic source for the actual inspector")
    tools = SyntheticTools()
    inspected = synthetic_media_inspection(master)
    monkeypatch.setattr(
        review_proxy, "inspect_media", lambda *args, **kwargs: inspected
    )
    monkeypatch.setattr(
        review_ingest, "inspect_review_source", review_proxy.inspect_review_source
    )
    source = review_proxy.inspect_review_source(master, tools=tools)
    job_generation = source.generation_identity.removeprefix("sha256:")
    assert job_generation == source.generation_identity[7:]

    store = BuildJobStore(tmp_path / "real-inspection-jobs")
    proxy = SyntheticReviewProxy(master)
    adapter = ReviewIngestAdapter(
        store,
        cache_root=store.root / "review-cache",
        resolve_master=lambda project_id, source_id: RegisteredMaster(
            project_id,
            source_id,
            master,
            file_hash(master),
            video_stream_index=0,
            audio_stream_index=1,
        ),
        tools=tools,  # type: ignore[arg-type]
    )
    job_id = adapter.submit_ingest("project-a", "source-a", "actual-source-flow")
    assert store.status("project-a", job_id)["generationIdentity"] == job_generation
    assert (
        adapter.submit_ingest("project-a", "source-a", "actual-source-flow") == job_id
    )

    wrong_hash_adapter = ReviewIngestAdapter(
        store,
        cache_root=store.root / "review-cache",
        resolve_master=lambda project_id, source_id: RegisteredMaster(
            project_id,
            source_id,
            master,
            "sha256:" + "0" * 64,
            video_stream_index=0,
            audio_stream_index=1,
        ),
        tools=tools,  # type: ignore[arg-type]
    )
    with pytest.raises(ReviewIngestError, match="content hash differs"):
        wrong_hash_adapter.submit_ingest(
            "project-a", "source-a", "wrong-registered-hash"
        )

    monkeypatch.setattr(review_ingest, "run_review_stage", proxy.run)
    monkeypatch.setattr(review_ingest, "verify_review_stage", proxy.verify)

    for _ in range(3):
        assert store.run_one("project-a", job_id, "worker-a", adapter)

    handoff = adapter.verified_handoff("project-a", job_id)
    assert handoff.generation_identity == job_generation
    assert handoff.master_content_hash == file_hash(master)
    assert handoff.audio_source == "audio-stage"


@pytest.mark.slow
def test_real_ffmpeg_restart_reuses_derivative_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg and ffprobe are required for the real-media integration")

    master = tmp_path / "numbered-master.mov"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-frames:v",
            "12",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads:v",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-x264-params",
            "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a",
            "pcm_s16le",
            "-threads:a",
            "1",
            "-ar",
            "48000",
            "-ac",
            "1",
            str(master),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    master_before = master.read_bytes()
    tools = SingleThreadMediaTools(ffmpeg, ffprobe)
    root = tmp_path / "issue44-real-ingest"
    cache_root = root / "review-cache"
    clock = Clock()
    store = BuildJobStore(root / "jobs", clock=clock)

    def resolve_master(project_id: str, source_id: str) -> RegisteredMaster | None:
        if (project_id, source_id) != ("project-real", "source-real"):
            return None
        return RegisteredMaster(
            project_id,
            source_id,
            master,
            file_hash(master),
            video_stream_index=0,
            audio_stream_index=1,
        )

    adapter = ReviewIngestAdapter(
        store,
        cache_root=cache_root,
        resolve_master=resolve_master,
        tools=tools,
    )
    job_id = adapter.submit_ingest("project-real", "source-real", "real-short-clip")
    generation_identity = store.status("project-real", job_id)["generationIdentity"]
    assert isinstance(generation_identity, str) and len(generation_identity) == 64

    # Simulate a crash after review_proxy publishes the proxy marker but before
    # BuildJobStore can commit the stage receipt.
    with pytest.raises(KeyboardInterrupt, match="after proxy publication"):
        store.run_one(
            "project-real",
            job_id,
            "worker-before-restart",
            InterruptAfterProxy(adapter),
            lease_seconds=5,
        )
    interrupted = store.status("project-real", job_id)
    proxy_output = root / "jobs" / "artifacts" / job_id / "proxy" / "output"
    proxy_bundles = cache_root / generation_identity / "proxy" / "bundles"
    bundles_before_restart = sorted(
        path.name for path in proxy_bundles.iterdir() if path.is_dir()
    )
    assert interrupted["activeStage"] == "proxy"
    assert interrupted["stages"][0]["status"] == "running"
    assert proxy_output.is_file()
    assert len(bundles_before_restart) == 1

    clock.value += 6
    reopened_store = BuildJobStore(root / "jobs", clock=clock)
    reopened_adapter = ReviewIngestAdapter(
        reopened_store,
        cache_root=cache_root,
        resolve_master=resolve_master,
        tools=tools,
    )
    assert (
        reopened_adapter.submit_ingest("project-real", "source-real", "real-short-clip")
        == job_id
    )
    for index in range(3):
        assert reopened_store.run_one(
            "project-real",
            job_id,
            f"worker-after-restart-{index}",
            reopened_adapter,
            lease_seconds=5,
        )

    complete = reopened_store.status("project-real", job_id)
    assert complete["status"] == "complete"
    assert [stage["status"] for stage in complete["stages"]] == [
        "complete",
        "complete",
        "complete",
    ]
    assert sorted(path.name for path in proxy_bundles.iterdir() if path.is_dir()) == (
        bundles_before_restart
    )

    handoff = reopened_adapter.verified_handoff("project-real", job_id)
    assert handoff.video_source == "proxy"
    assert handoff.video_muted is True
    assert handoff.frame_map is not None
    assert handoff.frame_map["sourceFrameCount"] == 12
    assert handoff.frame_map["proxyFrameCount"] == 12
    assert handoff.frame_map["proxyToMasterOffset"] == {
        "numerator": 0,
        "denominator": 1,
    }
    assert handoff.audio_source == "audio-stage"
    assert handoff.audio_timing is not None
    assert handoff.audio_timing["status"] == "aligned"
    assert handoff.audio_timing["sampleRate"] == 48000
    assert handoff.audio_timing["outputAudioFrames"] == 23040
    assert handoff.audio_timing["audioOffsetSamples"] == 0
    assert handoff.proxy_path is not None
    with pytest.raises(ReviewProxyError, match="corrupt"):
        handoff.proxy_path.write_bytes(b"tampered synthetic derivative")
        reopened_adapter.verified_handoff("project-real", job_id)
    assert master.read_bytes() == master_before
    assert file_hash(master) == handoff.master_content_hash


def test_map_proxy_frame_range_uses_verified_nonzero_origin_and_exact_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master.mp4"
    master.write_bytes(b"synthetic master bytes")
    rate = Fraction(24000, 1001)
    origin = Fraction(13, 7)
    proxy = SyntheticReviewProxy(
        master,
        source_rate=rate,
        source_pts_origin=origin,
        source_frame_count=24,
    )
    store = BuildJobStore(tmp_path / "jobs")
    job_id = store.submit_ingest(request())
    adapter = adapter_for(store, master, proxy, monkeypatch)
    for _ in range(3):
        assert store.run_one("project-a", job_id, "worker-a", adapter)

    mapping = adapter.map_proxy_frame_range("project-a", job_id, 2, 5)
    start = mapping["startBoundary"]
    end = mapping["endBoundary"]
    start_relative = Fraction(2, 1) / rate
    end_relative = Fraction(5, 1) / rate
    start_source_pts = origin + start_relative
    end_source_pts = origin + end_relative
    start_review_pts = start_source_pts - Fraction(7, 1001)
    end_review_pts = end_source_pts - Fraction(7, 1001)
    assert mapping["videoSource"] == "proxy"
    assert mapping["frameRange"] == {"startInclusive": 2, "endExclusive": 5}
    assert mapping["sourceRate"] == {"numerator": 24000, "denominator": 1001}
    assert mapping["sourcePtsOrigin"] == {"numerator": 13, "denominator": 7}
    assert start["reviewFrameIndex"] == start["sourceFrameIndex"] == 2
    assert start["relativeTimeSeconds"] == {
        "numerator": start_relative.numerator,
        "denominator": start_relative.denominator,
    }
    assert start["reviewPtsSeconds"] == {
        "numerator": start_review_pts.numerator,
        "denominator": start_review_pts.denominator,
    }
    assert start["sourcePtsSeconds"] == {
        "numerator": start_source_pts.numerator,
        "denominator": start_source_pts.denominator,
    }
    assert end["reviewFrameIndex"] == end["sourceFrameIndex"] == 5
    assert end["relativeTimeSeconds"] == {
        "numerator": end_relative.numerator,
        "denominator": end_relative.denominator,
    }
    assert end["reviewPtsSeconds"] == {
        "numerator": end_review_pts.numerator,
        "denominator": end_review_pts.denominator,
    }
    assert end["sourcePtsSeconds"] == {
        "numerator": end_source_pts.numerator,
        "denominator": end_source_pts.denominator,
    }

    for invalid in ((-1, 2), (4, 4), (0, 25), (True, 2)):
        with pytest.raises(ReviewIngestError, match="frame range"):
            adapter.map_proxy_frame_range("project-a", job_id, *invalid)

    proxy_path = proxy.results[(REVIEW_GENERATION, "proxy")].artifact_path
    assert proxy_path is not None
    proxy_path.write_bytes(b"tampered proxy")
    with pytest.raises(ReviewIngestError, match="derivative is corrupt"):
        adapter.map_proxy_frame_range("project-a", job_id, 2, 5)


def test_map_master_frame_range_uses_verified_source_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "safe-master.mp4"
    master.write_bytes(b"synthetic safe master bytes")
    rate = Fraction(24000, 1001)
    origin = Fraction(17, 5)
    proxy = SyntheticReviewProxy(
        master,
        video_usable=True,
        proxy_required=False,
        master_browser_safe=True,
        source_rate=rate,
        source_pts_origin=origin,
        source_frame_count=8,
    )
    store = BuildJobStore(tmp_path / "jobs")
    job_id = store.submit_ingest(request())
    adapter = adapter_for(store, master, proxy, monkeypatch)
    for _ in range(3):
        assert store.run_one("project-a", job_id, "worker-a", adapter)

    mapping = adapter.map_proxy_frame_range("project-a", job_id, 1, 3)
    start = mapping["startBoundary"]
    end = mapping["endBoundary"]
    start_relative = Fraction(1, 1) / rate
    end_relative = Fraction(3, 1) / rate
    start_source_pts = origin + start_relative
    end_source_pts = origin + end_relative
    assert mapping["videoSource"] == "master"
    assert start["reviewFrameIndex"] == start["sourceFrameIndex"] == 1
    assert (
        start["reviewPtsSeconds"]
        == start["sourcePtsSeconds"]
        == {
            "numerator": start_source_pts.numerator,
            "denominator": start_source_pts.denominator,
        }
    )
    assert end["reviewFrameIndex"] == end["sourceFrameIndex"] == 3
    assert end["relativeTimeSeconds"] == {
        "numerator": end_relative.numerator,
        "denominator": end_relative.denominator,
    }
    assert (
        end["reviewPtsSeconds"]
        == end["sourcePtsSeconds"]
        == {
            "numerator": end_source_pts.numerator,
            "denominator": end_source_pts.denominator,
        }
    )
