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

import fcntl
import json
import os
import shlex
import subprocess
import tempfile
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from experiments.issue45.artifacts import (
    AlignedTime,
    AudioRef,
    Json,
    RecognizerInfo,
    Token,
    alignment_artifact,
    content_hash,
    recognition_artifact,
    reconciled_texts,
    tool,
)
from experiments.issue45.normalize import Unit, normalise_token
from experiments.issue45.ports import (
    Capabilities,
    Port,
    PortRefusal,
    ProjectPolicy,
    require_language,
)
from experiments.issue45.segmentation import (
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


def run_engine(
    cmd: list[str], *, port: Port, env: dict[str, str] | None, timeout: float
) -> str:
    try:
        done = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
            check=False,
        )
    except FileNotFoundError as error:
        raise PortRefusal(
            port, "runtime-missing", f"Engine runtime not found: {Path(cmd[0]).name}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise PortRefusal(
            port, "timeout", "Engine run timed out.", retryable=True
        ) from error
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
    config: EngineConfig, audio: AudioRef, port: Port
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
        )
    )
    regions = [(float(s), float(e)) for s, e in out["speechRegions"]]
    return group_regions(regions, float(out["durationSec"]))


class ParakeetRecognizer:
    """Free local recogniser (recommended local profile).

    Native word ends are derived from the next token start.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config

    def capabilities(self) -> Capabilities:
        european = {
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
        return Capabilities(frozenset(european), "local", "word_start_with_derived_end")

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


@contextmanager
def _mfa_lock(home: Path) -> Iterator[None]:
    home.mkdir(parents=True, exist_ok=True)
    with (home / ".vera-mfa.lock").open("w") as f:
        fcntl.flock(
            f, fcntl.LOCK_EX
        )  # MFA runs share temp state; never run two at once
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def prepare_segments(
    config: EngineConfig,
    audio: AudioRef,
    recognition: Json,
    reconciliation: Json | None,
) -> tuple[list[Segment], Json]:
    """Aligner units grouped into VAD segments, plus the aligner-contract payload.

    Shared by every aligner (MFA, the agreement partner) so they see identical
    segments and unit texts (reconciled spellings when a reconciliation is given).
    """
    tokens = recognition["tokens"]
    texts = reconciled_texts(reconciliation)
    units: list[Unit] = []
    anchors: list[tuple[float, float] | None] = []
    for t in tokens:
        spoken = [] if t["kind"] == "event" else normalise_token(t["display"])
        for sub, text in enumerate(spoken):
            units.append(Unit(t["index"], sub, texts.get((t["index"], sub), text)))
            s, e = t["anchorStartMs"], t["anchorEndMs"]
            anchors.append(None if s is None or e is None else (s / 1000, e / 1000))
    segments = assign_units(units, anchors, speech_segments(config, audio, "aligner"))
    if units and not segments:
        raise PortRefusal(
            "aligner",
            "input-invalid",
            "No speech was detected to align the transcript to.",
        )
    multi = {t["index"] for t in tokens if len(normalise_token(t["display"])) > 1}
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


class MfaAligner:
    """Montreal Forced Aligner, english_us_arpa (+ optional pronunciation guides)."""

    def __init__(
        self, config: EngineConfig, *, extra_dictionary: Path | None = None
    ) -> None:
        self.config, self.extra_dictionary = config, extra_dictionary

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset({"en"}), "local", "acoustic")

    def align(
        self,
        audio: AudioRef,
        recognition: Json,
        *,
        policy: ProjectPolicy,
        reconciliation: Json | None = None,
    ) -> Json:
        require_language(
            self.capabilities(), recognition["identity"]["language"], "aligner"
        )
        cfg = self.config
        if not cfg.mfa_command:
            raise PortRefusal(
                "aligner",
                "runtime-missing",
                "MFA runtime (VERA_MFA_COMMAND) is not configured.",
            )
        _check_wav(audio, "aligner")
        segments, payload = prepare_segments(cfg, audio, recognition, reconciliation)
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
                "english_us_arpa",
            ]
            if self.extra_dictionary is not None:
                cmd += ["--extra-dict", str(self.extra_dictionary)]
            with _mfa_lock(home):
                run_engine(
                    cmd,
                    port="aligner",
                    env={**cfg.mfa_env, "VERA_MFA_HOME": str(home)},
                    timeout=cfg.timeout_s,
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
                "variant": "english_us_arpa",
                "models": result.get("provenance", {}).get("models", []),
            },
            acousticModel="english_us_arpa",
            dictionary="english_us_arpa",
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
