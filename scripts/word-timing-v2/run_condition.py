"""Run the frozen pipelines on one audio condition (e.g. A cleaned with DeepFilterNet).

For a condition directory DIR holding `<name>-48k.wav` and `<name>-16k.wav`:
1. Recognisers: Parakeet (local), cloud (eleven-or, assemblyai, speechmatics,
   chirp2, and chirp2 with keyterms) and headless Resolve. Existing outputs
   are skipped.
2. Script to Timeline pipelines: reconcile → MFA (plus guides when given).
3. Aligner isolation: the *original* condition's reconciled segments, re-timed
   by MFA on this condition's audio. Text is held constant, so only the audio
   changes.

The VAD segmentation of the original recording is reused for every condition,
so segment boundaries are identical across conditions. Frozen settings, no
tuning.

Usage: run_condition.py --dir DIR --name NAME --original-dir ORIG --vad vad.json \
           --prompter prompter.json [--guides extra.dict]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path.home() / ".local/share/vera/word-timing-v2"
VENV = DATA / "venv/bin/python"
PARAKEET_PY = Path.home() / ".local/share/vera/issue-51-preflight/run-a/autosubs/parakeet-env/bin/python"
DICT = DATA / "cache/mfa/pretrained_models/dictionary/english_us_arpa.dict"
SOURCES = ["eleven-or", "chirp2-kt", "assemblyai", "speechmatics", "resolve", "parakeet"]
ENV = {**os.environ, "MAMBA_ROOT_PREFIX": str(Path.home() / ".local/share/micromamba")}


def run(cmd: list[str], log: Path | None = None, cwd: Path = HERE) -> int:
    with (log.open("w") if log else open(os.devnull, "w")) as out:
        return subprocess.run(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, env=ENV).returncode


def mfa(segments: Path, audio_dir: Path, out: Path, guides: Path | None, log: Path) -> int:
    if out.exists():
        return 0
    cmd = ["micromamba", "run", "-n", "mfa", "python", "align_mfa.py", "--segments", str(segments),
           "--audio-dir", str(audio_dir), "--out", str(out), "--variant", "english_us_arpa"]
    if guides:
        cmd += ["--extra-dict", str(guides)]
    return run(cmd, log, HERE / "mfa")


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--dir", "--original-dir", "--vad", "--prompter"):
        parser.add_argument(name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--guides", type=Path)
    args = parser.parse_args()
    d, cloud, runs, pipe = args.dir, args.dir / "cloud", args.dir / "runs", args.dir / "pipe"
    for p in (cloud, runs, pipe):
        p.mkdir(parents=True, exist_ok=True)
    a48, a16 = d / f"{args.name}-48k.wav", d / f"{args.name}-16k.wav"
    status = {}

    if not (cloud / "T-C-parakeet.json").exists():
        status["parakeet"] = run([str(PARAKEET_PY), "run_parakeet.py", "--audio", str(a16), "--vad", str(args.vad),
                                  "--out", str(cloud / "T-C-parakeet.json")])
    need = [p for p in ("eleven-or", "assemblyai", "speechmatics", "chirp2") if not (cloud / f"T-C-{p}.json").exists()]
    if need:
        status["cloud"] = run([str(VENV), "run_cloud.py", "--audio", str(a48), "--out-dir", str(cloud),
                               "--providers", ",".join(need)], cloud / "run.log", HERE / "cloud")
    if not (cloud / "T-C-chirp2-kt.json").exists():
        status["chirp2-kt"] = run([str(VENV), "run_cloud.py", "--audio", str(a48), "--out-dir", str(cloud),
                                   "--providers", "chirp2", "--keyterms", str(args.prompter)], cloud / "run-kt.log", HERE / "cloud")
    if not (cloud / "T-C-resolve.json").exists():
        # -x matches the process name only; -f would also match any shell whose
        # command line merely mentions Resolve (a self-deadlock seen twice).
        while subprocess.run(["pgrep", "-x", "Resolve"], capture_output=True).returncode == 0:
            time.sleep(10)
        status["resolve"] = run([str(VENV), "resolve_headless.py", "--audio", str(a48), "--out", str(cloud / "raw-resolve.json")],
                                cloud / "resolve.log")
        if status["resolve"] == 0:
            run([str(VENV), "resolve_to_tc.py", "--raw", str(cloud / "raw-resolve.json"), "--out", str(cloud / "T-C-resolve.json")])

    for src in SOURCES:
        tc = cloud / f"T-C-{src}.json"
        if not tc.exists():
            status[src] = "missing recogniser output"
            continue
        cr = cloud / f"T-CR-{src}.json"
        run([str(VENV), "reconcile.py", "--tc", str(tc), "--prompter", str(args.prompter), "--dictionary", str(DICT),
             "--out", str(cr)])
        run([str(VENV), "tc_tokens.py", "--tc", str(cr), "--tokens-out", str(pipe / f"tokens-{src}.json"),
             "--anchors-out", str(pipe / f"anchors-{src}.json")])
        seg = pipe / f"segments-{src}.json"
        run([str(VENV), "segment.py", "assign", "--vad", str(args.vad), "--tokens", str(pipe / f"tokens-{src}.json"),
             "--anchors", str(pipe / f"anchors-{src}.json"), "--audio-name", a16.name, "--out", str(seg)])
        status[f"{src} mfa"] = mfa(seg, d, runs / f"T-CR-{src}__A-MFA-english_us_arpa.json", args.guides,
                                   runs / f"pipe-{src}.log")
        # isolation: original text, this audio
        orig_seg = args.original_dir / "pipe" / f"segments-{src}.json"
        if orig_seg.exists():
            iso = json.loads(orig_seg.read_text())
            iso["audio"] = a16.name
            iso_seg = pipe / f"segments-origtext-{src}.json"
            iso_seg.write_text(json.dumps(iso))
            status[f"{src} isolation"] = mfa(iso_seg, d, runs / f"ORIGTEXT-{src}__A-MFA-english_us_arpa.json", args.guides,
                                             runs / f"iso-{src}.log")
    print(json.dumps(status))


if __name__ == "__main__":
    main()
