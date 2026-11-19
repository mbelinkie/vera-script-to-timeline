"""Local engine adapters: Parakeet TDT 0.6B v3 (RecognizerPort) and MFA (AlignerPort).

Engines run in their own runtimes (configured, never installed by this code):
- Silero VAD in a "tools" Python with silero-vad + soundfile;
- Parakeet in a Python with onnx-asr + onnxruntime and a model snapshot;
- MFA through a command such as `micromamba run -n mfa python`.
A missing runtime is a `runtime-missing` refusal; nothing falls back.
Audio must be 16 kHz mono 16-bit WAV (the AudioPrep stage makes it).

Configuration comes from `EngineConfig.from_env()` (VERA_TOOLS_PYTHON,
VERA_PARAKEET_PYTHON, VERA_PARAKEET_MODEL_GLOB, VERA_MFA_COMMAND,
VERA_MFA_HOME, VERA_MFA_ROOT_DIR) or explicit construction.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shlex
import signal
import subprocess
import tempfile
import time
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from vera_word_timing.artifacts import (
    AlignedTime,
    AudioRef,
    Json,
    RecognizerInfo,
    Token,
    alignment_artifact,
    content_hash,
    file_hash,
    recognition_artifact,
    reconciled_texts,
    tool,
)
from vera_word_timing.normalize import Unit, normalise_token
from vera_word_timing.ports import (
    Capabilities,
    Port,
    PortRefusal,
    ProjectPolicy,
    check_alignment_inputs,
    require_language,
)
from vera_word_timing.segmentation import (
    MAX_SEGMENT_S,
    PAD_S,
    Segment,
    assign_units,
    group_regions,
)

ENGINES = Path(__file__).resolve().parent / "engines"
VAD_SETTINGS = {
    "engine": "silero-vad",
    "version": "6.2.1",
    "onnx": True,
    "padS": PAD_S,
    "maxSegmentS": MAX_SEGMENT_S,
}
_CANCEL_POLL_S = 0.1
_STOP_GRACE = ((signal.SIGTERM, 15.0), (signal.SIGKILL, 10.0))


@dataclass(frozen=True)
class EngineConfig:
    tools_python: Path | None = None
    parakeet_python: Path | None = None
    parakeet_model_glob: str | None = None
    mfa_command: tuple[str, ...] = ()
    mfa_home: Path | None = None
    mfa_env: dict[str, str] = field(default_factory=dict)
    qwen_command: tuple[str, ...] = ()
    # Container engines (Colima/Docker) only see the home directory, so
    # hand-off files for them live here rather than in the system temp dir.
    work_dir: Path = field(default_factory=lambda: Path.home() / ".cache/vera-engines")
    canary_model_dir: Path | None = None
    timeout_s: float = 1800.0

    @classmethod
    def from_env(cls) -> EngineConfig:
        def path(name: str) -> Path | None:
            value = os.environ.get(name)
            return Path(value).expanduser() if value else None

        extra = {k: v for k in ("MAMBA_ROOT_PREFIX",) if (v := os.environ.get(k))}
        if root := os.environ.get("VERA_MFA_ROOT_DIR"):
            extra["MFA_ROOT_DIR"] = root
        return cls(
            tools_python=path("VERA_TOOLS_PYTHON"),
            parakeet_python=path("VERA_PARAKEET_PYTHON"),
            parakeet_model_glob=os.environ.get("VERA_PARAKEET_MODEL_GLOB"),
            mfa_command=tuple(shlex.split(os.environ.get("VERA_MFA_COMMAND", ""))),
            qwen_command=tuple(shlex.split(os.environ.get("VERA_QWEN_COMMAND", ""))),
            canary_model_dir=path("VERA_CANARY_MODEL_DIR"),
            work_dir=path("VERA_ENGINE_WORK") or Path.home() / ".cache/vera-engines",
            mfa_home=path("VERA_MFA_HOME"),
            mfa_env=extra,
        )


def _check_wav(audio: AudioRef, port: Port) -> None:
    try:
        with wave.open(str(audio.path)) as w:
            ok = (
                w.getnchannels() == 1
                and w.getsampwidth() == 2
                and w.getframerate() == 16000
            )
    except (OSError, wave.Error) as error:
        raise PortRefusal(
            port, "input-invalid", "Audio is missing or not a WAV file."
        ) from error
    if not ok:
        raise PortRefusal(
            port,
            "input-invalid",
            "Engines need 16 kHz mono 16-bit WAV (run AudioPrep).",
        )


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _stop_group(proc: subprocess.Popen[str]) -> bool:
    """Stop the entire engine group and confirm that it is gone."""
    try:
        for sig, grace in _STOP_GRACE:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(proc.pid, sig)
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline:
                if proc.poll() is not None and not _group_alive(proc.pid):
                    return True
                time.sleep(0.05)
        return proc.poll() is not None and not _group_alive(proc.pid)
    finally:
        # Discard engine output without waiting for EOF from any surviving child.
        for pipe in (proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()


def check_cancelled(cancel_file: Path | None, port: Port = "aligner") -> None:
    if cancel_file is None:
        return
    try:
        cancel_file.stat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise PortRefusal(
            port, "input-invalid", "Could not check the cancellation file."
        ) from error
    raise PortRefusal(
        port, "cancelled", "Alignment was cancelled and its engines have stopped."
    )


def _communicate(
    proc: subprocess.Popen[str], timeout: float, cancel_file: Path | None, port: Port
) -> tuple[str, str]:
    if cancel_file is None:
        return proc.communicate(timeout=timeout)
    deadline = time.monotonic() + timeout
    while True:
        check_cancelled(cancel_file, port)
        remaining = max(0.0, deadline - time.monotonic())
        try:
            return proc.communicate(timeout=min(_CANCEL_POLL_S, remaining))
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                raise


def _shutdown_unconfirmed(port: Port) -> PortRefusal:
    return PortRefusal(
        port, "shutdown-unconfirmed", "Could not confirm that all job engines stopped."
    )


def run_engine(
    cmd: list[str],
    *,
    port: Port,
    env: dict[str, str] | None,
    timeout: float,
    cancel_file: Path | None = None,
) -> str:
    check_cancelled(cancel_file, port)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, **(env or {})},
            start_new_session=True,  # its own process group, so timeouts reach children
        )
    except FileNotFoundError as error:
        check_cancelled(cancel_file, port)
        raise PortRefusal(
            port, "runtime-missing", f"Engine runtime not found: {Path(cmd[0]).name}"
        ) from error
    try:
        stdout, stderr = _communicate(proc, timeout, cancel_file, port)
    except (PortRefusal, subprocess.TimeoutExpired, OSError, UnicodeError) as error:
        if cancel_file is None and not isinstance(error, subprocess.TimeoutExpired):
            raise
        stopped = _stop_group(proc)
        if cancel_file is not None and not stopped:
            raise _shutdown_unconfirmed(port) from error
        if isinstance(error, PortRefusal):
            raise
        check_cancelled(cancel_file, port)
        if not isinstance(error, subprocess.TimeoutExpired):
            raise
        raise PortRefusal(
            port, "timeout", "Engine run timed out.", retryable=True
        ) from error
    if cancel_file is not None:
        # A child can close its pipes and outlive the wrapper. Check before
        # advancing to the next engine or acknowledging a late cancellation.
        if _group_alive(proc.pid) and not _stop_group(proc):
            raise _shutdown_unconfirmed(port)
        check_cancelled(cancel_file, port)
    done = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if done.returncode != 0:
        # Engine output can contain private paths, so it goes to a local log,
        # never into the refusal message.
        log = Path(tempfile.gettempdir()) / "vera-engine-errors.log"
        with log.open("a", encoding="utf-8") as f:
            f.write(
                f"--- {Path(cmd[min(1, len(cmd) - 1)]).name} exit {done.returncode}\n"
            )
            f.write(done.stderr[-4000:] + "\n")
        raise PortRefusal(
            port,
            "provider-failed",
            f"Engine exited with status {done.returncode} (see the local engine log).",
            retryable=True,
        )
    return done.stdout


def speech_segments(
    config: EngineConfig,
    audio: AudioRef,
    port: Port,
    *,
    cancel_file: Path | None = None,
) -> list[tuple[float, float]]:
    if config.tools_python is None or not config.tools_python.exists():
        raise PortRefusal(
            port,
            "runtime-missing",
            "VAD runtime (VERA_TOOLS_PYTHON) is not configured.",
        )
    out = json.loads(
        run_engine(
            [
                str(config.tools_python),
                str(ENGINES / "silero_vad_engine.py"),
                str(audio.path),
            ],
            port=port,
            env=None,
            timeout=config.timeout_s,
            cancel_file=cancel_file,
        )
    )
    regions = [(float(s), float(e)) for s, e in out["speechRegions"]]
    return group_regions(regions, float(out["durationSec"]))


EUROPEAN = frozenset(
    {
        "bg",
        "hr",
        "cs",
        "da",
        "nl",
        "en",
        "et",
        "fi",
        "fr",
        "de",
        "el",
        "hu",
        "it",
        "lv",
        "lt",
        "mt",
        "pl",
        "pt",
        "ro",
        "sk",
        "sl",
        "es",
        "sv",
        "ru",
        "uk",
    }
)


class ParakeetRecognizer:
    """Free local recogniser (recommended local profile).

    Native word ends are derived from the next token start.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config

    def capabilities(self) -> Capabilities:
        return Capabilities(EUROPEAN, "local", "word_start_with_derived_end")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        require_language(self.capabilities(), language, "recognizer")
        cfg = self.config
        if (
            cfg.parakeet_python is None
            or not cfg.parakeet_python.exists()
            or not cfg.parakeet_model_glob
        ):
            raise PortRefusal(
                "recognizer",
                "runtime-missing",
                "Parakeet runtime or model is not configured.",
            )
        _check_wav(audio, "recognizer")
        segments = speech_segments(cfg, audio, "recognizer")
        with tempfile.TemporaryDirectory(prefix="vera-parakeet-") as tmp:
            vad, out = Path(tmp) / "vad.json", Path(tmp) / "tc.json"
            vad.write_text(json.dumps({"segments": [list(s) for s in segments]}))
            run_engine(
                [
                    str(cfg.parakeet_python),
                    str(ENGINES / "parakeet_engine.py"),
                    "--audio",
                    str(audio.path),
                    "--vad",
                    str(vad),
                    "--out",
                    str(out),
                ],
                port="recognizer",
                env={"VERA_PARAKEET_MODEL_GLOB": cfg.parakeet_model_glob},
                timeout=cfg.timeout_s,
            )
            tc = json.loads(out.read_text())
        prov = tc.get("provenance", {})
        tokens = [
            Token(
                str(w["text"]),
                "word",
                float(w["start"]),
                float(w["end"]),
                "word_start_with_derived_end",
            )
            for w in tc["words"]
            if str(w["text"]).strip()
        ]
        info = RecognizerInfo(
            "asr-local",
            "nvidia",
            "parakeet-tdt-0.6b-v3",
            prov.get("snapshot"),
            {
                "quantization": prov.get("quantization"),
                "vad": VAD_SETTINGS,
                "onnx": prov.get("onnxSha256"),
            },
        )
        return recognition_artifact(
            audio, info, tokens, language=language, consent_policy=None
        )


CANARY_REVISION = "5ebc1520cef7b6b318b3526ad17adbfe00bc1bfc"
# SHA-256 of the int8 weights at that revision (recorded in the study). The
# adapter refuses other files, so the revision in each artifact is true.
CANARY_WEIGHTS = {
    "encoder-model.int8.onnx": (
        "6d96e9945898e5ace48f4efecd459ca1df81859730be27b8af6b197639403ee1"
    ),
    "decoder-model.int8.onnx": (
        "52d83aa7aad41fbbe4f9dfcd341d784735a6eb4c6eb0d3290fc27a0d8ac39abf"
    ),
}


class CanaryRecognizer:
    """NVIDIA Canary-1B v2 with a forced language (recommended for non-English).

    Study: best on Italian (1.0% WER) and Swedish (8.6%), within 2-5 points of
    whisper on German/French, 4-5x faster than whisper. No timestamps, so each
    word is anchored to its VAD segment (`segment` precision); the aligner
    supplies word times. CC-BY-4.0: credit NVIDIA in the product.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config

    def capabilities(self) -> Capabilities:
        return Capabilities(EUROPEAN, "local", "segment")

    def recognise(
        self, audio: AudioRef, *, language: str, policy: ProjectPolicy
    ) -> Json:
        require_language(self.capabilities(), language, "recognizer")
        cfg = self.config
        if (
            cfg.parakeet_python is None
            or not cfg.parakeet_python.exists()
            or cfg.canary_model_dir is None
            or not cfg.canary_model_dir.is_dir()
        ):
            raise PortRefusal(
                "recognizer",
                "runtime-missing",
                "Canary runtime or model (VERA_CANARY_MODEL_DIR) is not configured.",
            )
        for name, expected in CANARY_WEIGHTS.items():
            weights = cfg.canary_model_dir / name
            if not weights.is_file() or file_hash(weights) != f"sha256:{expected}":
                raise PortRefusal(
                    "recognizer",
                    "runtime-missing",
                    "Canary model files do not match the pinned revision.",
                )
        _check_wav(audio, "recognizer")
        segments = speech_segments(cfg, audio, "recognizer")
        with tempfile.TemporaryDirectory(prefix="vera-canary-") as tmp:
            seg_file, out = Path(tmp) / "segments.json", Path(tmp) / "canary.json"
            seg_file.write_text(json.dumps([list(x) for x in segments]))
            run_engine(
                [
                    str(cfg.parakeet_python),
                    str(ENGINES / "canary_engine.py"),
                    "--audio",
                    str(audio.path),
                    "--segments",
                    str(seg_file),
                    "--language",
                    language.split("-")[0],
                    "--out",
                    str(out),
                ],
                port="recognizer",
                env={"VERA_CANARY_MODEL_DIR": str(cfg.canary_model_dir)},
                timeout=cfg.timeout_s,
            )
            result = json.loads(out.read_text())
        tokens = [
            Token(word, "word", seg["start"], seg["end"], "segment")
            for seg in result["segments"]
            for word in seg["text"].split()
        ]
        if not tokens:
            raise PortRefusal(
                "recognizer", "provider-failed", "Canary returned no words."
            )
        info = RecognizerInfo(
            "asr-local",
            "nvidia",
            "canary-1b-v2",
            CANARY_REVISION,
            {"quantization": "int8", "vad": VAD_SETTINGS, "itn": False},
        )
        return recognition_artifact(
            audio, info, tokens, language=language, consent_policy=None
        )


@contextmanager
def _mfa_lock(home: Path, *, cancel_file: Path | None = None) -> Iterator[None]:
    check_cancelled(cancel_file)
    home.mkdir(parents=True, exist_ok=True)
    with (home / ".vera-mfa.lock").open("w") as f:
        # MFA runs share temp state; never run two at once.
        if cancel_file is None:
            fcntl.flock(f, fcntl.LOCK_EX)
        else:
            while True:
                check_cancelled(cancel_file)
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(_CANCEL_POLL_S)
                else:
                    break
        try:
            check_cancelled(cancel_file)
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def prepare_segments(
    config: EngineConfig,
    audio: AudioRef,
    recognition: Json,
    reconciliation: Json | None,
    *,
    cancel_file: Path | None = None,
) -> tuple[list[Segment], Json]:
    """Aligner units grouped into VAD segments, plus the aligner-contract payload.

    Shared by every aligner (MFA, the agreement partner) so they see identical
    segments and unit texts (reconciled spellings when a reconciliation is given).
    """
    tokens = recognition["tokens"]
    language = recognition["identity"]["language"]
    texts = reconciled_texts(reconciliation)
    units: list[Unit] = []
    anchors: list[tuple[float, float] | None] = []
    for t in tokens:
        spoken = [] if t["kind"] == "event" else normalise_token(t["display"], language)
        for sub, text in enumerate(spoken):
            units.append(Unit(t["index"], sub, texts.get((t["index"], sub), text)))
            s, e = t["anchorStartMs"], t["anchorEndMs"]
            anchors.append(None if s is None or e is None else (s / 1000, e / 1000))
    segments = assign_units(
        units,
        anchors,
        speech_segments(config, audio, "aligner", cancel_file=cancel_file),
    )
    if units and not segments:
        raise PortRefusal(
            "aligner",
            "input-invalid",
            "No speech was detected to align the transcript to.",
        )
    multi = {
        t["index"] for t in tokens if len(normalise_token(t["display"], language)) > 1
    }
    payload: Json = {
        "audio": audio.path.name,
        "offsetSec": 0.0,
        "segments": [
            {
                "id": f"s{n:03d}",
                "start": seg.start,
                "end": seg.end,
                "words": [
                    {
                        "i": u.token_index,
                        "text": u.text,
                        "display": tokens[u.token_index]["display"],
                        **({"sub": u.sub} if u.token_index in multi else {}),
                    }
                    for u in seg.units
                ],
            }
            for n, seg in enumerate(segments)
        ],
    }
    return segments, payload


# MFA 3.x model per language (all downloaded and pinned in the word-timing study).
MFA_VARIANTS = {
    "en": "english_us_arpa",
    "de": "german_mfa",
    "fr": "french_mfa",
    "sv": "swedish_mfa",
}


class MfaAligner:
    """Montreal Forced Aligner; the model follows the recognition's language.

    English uses english_us_arpa (+ optional prompter pronunciation guides);
    German, French and Swedish use the MFA 3.0.0 language models. Italian and
    Finnish have no MFA model: alignment refuses (capability-missing).
    """

    def __init__(
        self, config: EngineConfig, *, extra_dictionary: Path | None = None
    ) -> None:
        self.config, self.extra_dictionary = config, extra_dictionary

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset(MFA_VARIANTS), "local", "acoustic")

    def align(
        self,
        audio: AudioRef,
        recognition: Json,
        *,
        policy: ProjectPolicy,
        reconciliation: Json | None = None,
        cancel_file: Path | None = None,
    ) -> Json:
        check_cancelled(cancel_file)
        require_language(
            self.capabilities(), recognition["identity"]["language"], "aligner"
        )
        check_alignment_inputs(audio, recognition, reconciliation)
        variant = MFA_VARIANTS[recognition["identity"]["language"].split("-")[0]]
        cfg = self.config
        if not cfg.mfa_command:
            raise PortRefusal(
                "aligner",
                "runtime-missing",
                "MFA runtime (VERA_MFA_COMMAND) is not configured.",
            )
        _check_wav(audio, "aligner")
        segments, payload = prepare_segments(
            cfg, audio, recognition, reconciliation, cancel_file=cancel_file
        )
        home = cfg.mfa_home or Path(tempfile.gettempdir()) / "vera-mfa"
        with tempfile.TemporaryDirectory(prefix="vera-mfa-in-") as tmp:
            seg_file, out = Path(tmp) / "segments.json", Path(tmp) / "result.json"
            seg_file.write_text(json.dumps(payload))
            cmd = [
                *cfg.mfa_command,
                str(ENGINES / "mfa_engine.py"),
                "--segments",
                str(seg_file),
                "--audio-dir",
                str(audio.path.parent),
                "--out",
                str(out),
                "--variant",
                variant,
            ]
            if self.extra_dictionary is not None:
                cmd += ["--extra-dict", str(self.extra_dictionary)]
            with _mfa_lock(home, cancel_file=cancel_file):
                run_engine(
                    cmd,
                    port="aligner",
                    env={**cfg.mfa_env, "VERA_MFA_HOME": str(home)},
                    timeout=cfg.timeout_s,
                    cancel_file=cancel_file,
                )
            result = json.loads(out.read_text())
        rows = {(r["i"], r.get("sub", 0)): r for r in result["words"]}
        times = []
        for seg in segments:
            for u in seg.units:
                r = rows.get((u.token_index, u.sub))
                ok = r is not None and r["status"] == "aligned"
                times.append(
                    AlignedTime(
                        u,
                        r["start"] if ok and r else None,
                        r["end"] if ok and r else None,
                    )
                )
        if times and not any(t.status == "acoustic" for t in times):
            raise PortRefusal(
                "aligner",
                "provider-failed",
                "MFA aligned no words (see its log in the MFA work folder).",
                retryable=False,
            )
        packages = result.get("provenance", {}).get("packages", {})
        aligner = tool(
            "montreal-forced-aligner",
            str(packages.get("montreal-forced-aligner", "unknown")),
            {
                "variant": variant,
                "models": result.get("provenance", {}).get("models", []),
            },
            acousticModel=variant,
            dictionary=variant,
            extraDictionaryHash=None
            if self.extra_dictionary is None
            else content_hash(self.extra_dictionary.read_text()),
        )
        segmentation = tool("silero-vad", "6.2.1", VAD_SETTINGS)
        return alignment_artifact(
            recognition,
            audio,
            aligner,
            segmentation,
            times,
            reconcile_id=None
            if reconciliation is None
            else reconciliation["artifactId"],
        )
