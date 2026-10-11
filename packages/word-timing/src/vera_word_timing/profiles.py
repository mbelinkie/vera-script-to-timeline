"""Named pipeline profiles composed from the ports (draft #168 §4).

Profiles are stage selections, not new engines:

- Script to Timeline: recogniser -> script reconciliation -> aligner (with
  pronunciation guides from the prompter when available). Recommended
  recognisers: ElevenLabs (cloud default; presenter recordings are rare, paid
  is acceptable) or Parakeet (free local option).
- Research: recogniser (YouTube captions when present, else Parakeet) ->
  aligner. No script stage. Must stay free.

Audio for recognition and alignment is the original recording; DeepFilterNet
output is for the edit only (cleanup test: it hurt recognition on the halting
presenter and was neutral for alignment).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from vera_word_timing.adapters.local_engines import (
    ENGINES,
    EngineConfig,
    MfaAligner,
    run_engine,
)
from vera_word_timing.artifacts import AudioRef, Json
from vera_word_timing.ports import PortRefusal, ProjectPolicy, RecognizerPort
from vera_word_timing.script_reconcile import (
    load_dictionary_words,
    parse_prompter,
    reconcile,
)


@dataclass(frozen=True)
class StageOutputs:
    recognition: Json
    alignment: Json
    reconciliation: Json | None = None


def guide_dictionary(
    config: EngineConfig, script_text: str, dictionary_text: str, out: Path
) -> Path | None:
    """MFA dictionary entries for the prompter's pronunciation guides.

    Returns None when the script has no guides.
    """
    prompter = parse_prompter(script_text, load_dictionary_words(dictionary_text))
    guides = [
        {"display": w["display"], "guide": w["guide"]}
        for w in prompter.words
        if "guide" in w
    ]
    if not guides:
        return None
    if not config.mfa_command:
        raise PortRefusal(
            "aligner",
            "runtime-missing",
            "MFA runtime (VERA_MFA_COMMAND) is not configured.",
        )
    with tempfile.TemporaryDirectory(prefix="vera-guides-") as tmp:
        spec = Path(tmp) / "guides.json"
        spec.write_text(json.dumps({"guides": guides}))
        home = config.mfa_home or Path(tempfile.gettempdir()) / "vera-mfa"
        run_engine(
            [
                *config.mfa_command,
                str(ENGINES / "guide_g2p_engine.py"),
                "--prompter",
                str(spec),
                "--variant",
                "english_us_arpa",
                "--out",
                str(out),
            ],
            port="aligner",
            env={**config.mfa_env, "VERA_MFA_HOME": str(home)},
            timeout=config.timeout_s,
        )
    return out


def script_to_timeline(
    audio: AudioRef,
    recognizer: RecognizerPort,
    config: EngineConfig,
    *,
    script_text: str,
    dictionary_text: str,
    policy: ProjectPolicy,
    guides_out: Path | None = None,
) -> StageOutputs:
    recognition = recognizer.recognise(audio, language="en", policy=policy)
    reconciliation = reconcile(recognition, script_text, dictionary_text)
    extra = (
        guide_dictionary(config, script_text, dictionary_text, guides_out)
        if guides_out
        else None
    )
    alignment = MfaAligner(config, extra_dictionary=extra).align(
        audio, recognition, policy=policy, reconciliation=reconciliation
    )
    return StageOutputs(recognition, alignment, reconciliation)


def research(
    audio: AudioRef,
    recognizer: RecognizerPort,
    config: EngineConfig,
    *,
    policy: ProjectPolicy,
    language: str = "en",
) -> StageOutputs:
    recognition = recognizer.recognise(audio, language=language, policy=policy)
    alignment = MfaAligner(config).align(audio, recognition, policy=policy)
    return StageOutputs(recognition, alignment)
