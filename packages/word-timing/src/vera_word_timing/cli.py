"""`vera-word-timing` JSON CLI: the language-neutral entry point (Research's TS worker).

Every command reads and writes the Producer-approved #168 contract JSON:

  vera-word-timing recognise --engine parakeet|canary|elevenlabs|youtube --audio X.wav
        [--language en] [--captions X.json3] [--consent-policy ID] [--keyterms a,b]
  vera-word-timing reconcile --recognition R.json --script S.txt --dictionary D.dict
  vera-word-timing align --recognition R.json --audio X.wav [--reconciliation C.json]
        [--extra-dictionary G.dict]
  vera-word-timing agree --recognition R.json --alignment A.json --audio X.wav
        [--reconciliation C.json]
  vera-word-timing resolve --alignment A.json --audio X.wav [--recognition R.json]

Output goes to stdout (or --out). Exit 0 = artifact; exit 3 = a
`port-refusal/v1` record on stdout (engine missing, consent missing, ...);
exit 2 = usage error. Engine runtimes come from the VERA_* environment
variables documented in `adapters/local_engines.py`. Audio must be 16 kHz
mono 16-bit WAV of the original recording (no cleanup: see the study's
cleanup verdict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vera_word_timing.artifacts import AudioRef, Json, file_hash, schema_errors
from vera_word_timing.ports import Port, PortRefusal, ProjectPolicy, RecognizerPort

REFUSED = 3
LANGUAGE_TAG = re.compile(
    r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*"
)  # same pattern as the contract


def _audio(path: Path) -> AudioRef:
    try:
        with wave.open(str(path)) as w:
            return AudioRef(path, file_hash(path), w.getframerate(), w.getnframes())
    except (OSError, wave.Error) as error:
        raise PortRefusal(
            "audio-prep", "input-invalid", "Audio is missing or not a WAV file."
        ) from error


def _read(path: Path) -> Json:
    """Read an input artifact; refuse anything that is not a valid contract document."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortRefusal(
            "aligner",
            "input-invalid",
            "An input file is missing, unreadable or not JSON.",
        ) from error
    if not isinstance(data, dict) or schema_errors(data):
        raise PortRefusal(
            "aligner",
            "input-invalid",
            "An input file is not a valid contract artifact.",
        )
    return data


def _read_text(path: Path) -> str:
    """Strict UTF-8: a corrupted script must refuse, not silently lose words."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PortRefusal(
            "aligner",
            "input-invalid",
            "An input file is missing, unreadable or not UTF-8 text.",
        ) from error


def _recognise(a: argparse.Namespace) -> Any:
    from vera_word_timing.adapters.elevenlabs_cloud import ElevenLabsCloudRecognizer
    from vera_word_timing.adapters.local_engines import (
        CanaryRecognizer,
        EngineConfig,
        ParakeetRecognizer,
    )
    from vera_word_timing.adapters.youtube_captions import YouTubeCaptionRecognizer

    if not LANGUAGE_TAG.fullmatch(a.language):
        raise PortRefusal(
            "recognizer",
            "input-invalid",
            "The language must be a tag like en or de-CH.",
        )
    recognizer: RecognizerPort
    if a.engine == "parakeet":
        recognizer = ParakeetRecognizer(EngineConfig.from_env())
    elif a.engine == "canary":
        recognizer = CanaryRecognizer(EngineConfig.from_env())
    elif a.engine == "elevenlabs":
        keyterms = tuple(t for t in (a.keyterms or "").split(",") if t) or None
        recognizer = ElevenLabsCloudRecognizer(keyterms=keyterms)
    else:
        if a.captions is None:
            raise PortRefusal(
                "recognizer",
                "input-invalid",
                "--captions is required for the youtube engine.",
            )
        recognizer = YouTubeCaptionRecognizer(a.captions)
    policy = ProjectPolicy(cloud_consent_policy_id=a.consent_policy)
    return recognizer.recognise(_audio(a.audio), language=a.language, policy=policy)


def _reconcile(a: argparse.Namespace) -> Any:
    from vera_word_timing.script_reconcile import reconcile

    return reconcile(
        _read(a.recognition),
        _read_text(a.script),
        _read_text(a.dictionary),
    )


def _align(a: argparse.Namespace) -> Any:
    from vera_word_timing.adapters.local_engines import EngineConfig, MfaAligner

    aligner = MfaAligner(EngineConfig.from_env(), extra_dictionary=a.extra_dictionary)
    return aligner.align(
        _audio(a.audio),
        _read(a.recognition),
        policy=ProjectPolicy(),
        reconciliation=_read(a.reconciliation) if a.reconciliation else None,
    )


def _agree(a: argparse.Namespace) -> Any:
    from vera_word_timing.adapters.agreement import QwenAgreement
    from vera_word_timing.adapters.local_engines import EngineConfig

    return QwenAgreement(EngineConfig.from_env()).check(
        _audio(a.audio),
        _read(a.recognition),
        _read(a.alignment),
        reconciliation=_read(a.reconciliation) if a.reconciliation else None,
    )


def _resolve(a: argparse.Namespace) -> Any:
    from vera_word_timing.resolve_review import Loudness, resolve

    alignment = _read(a.alignment)
    recognition = _read(a.recognition) if a.recognition else None
    _audio(a.audio)  # refuses a missing or non-WAV file
    try:
        loudness = Loudness(a.audio)
    except (OSError, EOFError, wave.Error, ValueError) as error:
        raise PortRefusal(
            "aligner", "input-invalid", "Audio must be 16-bit mono WAV."
        ) from error
    resolutions = resolve(alignment, loudness, recognition)
    return {
        "schemaVersion": "boundary-resolutions/v0",
        "resolutions": [asdict(r) for r in resolutions],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vera-word-timing", description=__doc__.split("\n\n")[0]
    )
    sub = p.add_subparsers(dest="command", required=True)

    def command(
        name: str, handler: Callable[[argparse.Namespace], Any]
    ) -> argparse.ArgumentParser:
        c = sub.add_parser(name)
        c.set_defaults(handler=handler)
        c.add_argument("--out", type=Path, help="write JSON here instead of stdout")
        return c

    r = command("recognise", _recognise)
    r.add_argument(
        "--engine",
        choices=["parakeet", "canary", "elevenlabs", "youtube"],
        required=True,
    )
    r.add_argument("--audio", type=Path, required=True)
    r.add_argument("--language", default="en")
    r.add_argument("--captions", type=Path)
    r.add_argument("--consent-policy")
    r.add_argument("--keyterms", help="comma-separated script keyterms (cloud only)")
    c = command("reconcile", _reconcile)
    for name in ("--recognition", "--script", "--dictionary"):
        c.add_argument(name, type=Path, required=True)
    al = command("align", _align)
    al.add_argument("--recognition", type=Path, required=True)
    al.add_argument("--audio", type=Path, required=True)
    al.add_argument("--reconciliation", type=Path)
    al.add_argument("--extra-dictionary", type=Path)
    ag = command("agree", _agree)
    for name in ("--recognition", "--alignment", "--audio"):
        ag.add_argument(name, type=Path, required=True)
    ag.add_argument("--reconciliation", type=Path)
    rs = command("resolve", _resolve)
    rs.add_argument("--alignment", type=Path, required=True)
    rs.add_argument("--audio", type=Path, required=True)
    rs.add_argument("--recognition", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    port: Port = "recognizer" if args.command == "recognise" else "aligner"
    try:
        result = args.handler(args)
        if (
            isinstance(result, dict)
            and "artifactId" in result
            and schema_errors(result)
        ):
            raise PortRefusal(
                port, "provider-failed", "The result failed contract validation."
            )
        code = 0
    except PortRefusal as refusal:
        result, code = refusal.record(), REFUSED
    except (KeyError, ValueError, TypeError) as error:
        # Expected shape problems (e.g. resolve without an agreement block):
        # a sanitised refusal, never a traceback with private paths.
        shape = PortRefusal(
            port, "input-invalid", "The inputs do not fit this command."
        )
        shape.__cause__ = error
        result, code = shape.record(), REFUSED
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out and code == 0:
        try:
            args.out.write_text(text + "\n", encoding="utf-8")
        except OSError:
            text = json.dumps(
                PortRefusal(
                    port, "input-invalid", "Could not write the output file."
                ).record(),
                indent=1,
            )
            sys.stdout.write(text + "\n")
            return REFUSED
    else:
        sys.stdout.write(text + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
