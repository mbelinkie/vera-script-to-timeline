#!/usr/bin/env python3
"""A-MFA wrapper (see ../ALIGNER-CONTRACT.md). Run inside the `mfa` micromamba env:

  MAMBA_ROOT_PREFIX=~/.local/share/micromamba micromamba run -n mfa \
    python align_mfa.py --segments S.json --audio-dir DIR --out R.json \
    --variant english_us_arpa|english_mfa
"""
import argparse, hashlib, json, os, resource, shutil, subprocess, sys, tempfile, time, wave
from pathlib import Path
import numpy as np

HOME = Path.home() / ".local/share/vera/word-timing-v2"
ROOT = Path(os.environ.get("MFA_ROOT_DIR", HOME / "cache/mfa")).expanduser()
PM = ROOT / "pretrained_models"
# variant -> (acoustic zip, dictionary, g2p zip, dictionary release tag, acoustic tag, g2p tag)
VARIANTS = {
    "english_us_arpa": dict(acoustic="english_us_arpa", dictionary="english_us_arpa", g2p="english_us_arpa",
                            versions={"acoustic": "3.0.0", "dictionary": "3.0.0", "g2p": "2.0.0"}),
    "english_mfa": dict(acoustic="english_mfa", dictionary="english_us_mfa", g2p="english_us_mfa",
                        versions={"acoustic": "3.1.0", "dictionary": "3.1.0", "g2p": "3.0.0"}),
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", default="english_us_arpa", choices=list(VARIANTS))
    ap.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1))
    a = ap.parse_args()
    v = VARIANTS[a.variant]
    t0 = time.time()
    spec = json.load(open(a.segments))
    offset = float(spec.get("offsetSec", 0.0))
    with wave.open(str(Path(a.audio_dir) / spec["audio"]), "rb") as w:
        sr, nch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        assert sw == 2, "expects 16-bit PCM wav"
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, nch)

    env = dict(os.environ, MFA_ROOT_DIR=str(ROOT))
    mfa = str(Path(sys.executable).parent / "mfa")
    tmp = Path(tempfile.mkdtemp(prefix="mfa-run-", dir=HOME / "work"))
    corpus, outd, tdir = tmp / "corpus", tmp / "out", tmp / "tmp"
    corpus.mkdir()
    segs = spec["segments"]
    for s in segs:
        a0, a1 = int(round(s["start"] * sr)), int(round(s["end"] * sr))
        with wave.open(str(corpus / f"{s['id']}.wav"), "wb") as w:
            w.setnchannels(nch); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(np.ascontiguousarray(pcm[a0:a1]).tobytes())
        (corpus / f"{s['id']}.lab").write_text(" ".join(x["text"] for x in s["words"]) + "\n")

    cmd = [mfa, "align", str(corpus), v["dictionary"], v["acoustic"], str(outd),
           "--g2p_model_path", str(PM / "g2p" / f"{v['g2p']}.zip"),
           "--single_speaker", "--clean", "--final_clean", "-j", str(a.jobs),
           "--temporary_directory", str(tdir), "--output_format", "long_textgrid"]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    log = HOME / "cache" / f"mfa-last-{a.variant}.log"
    log.write_text(r.stdout + "\n" + r.stderr)
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss  # bytes on macOS

    from praatio import textgrid as tg
    rows = []
    for s in segs:
        words = s["words"]
        ivs = None
        f = outd / f"{s['id']}.TextGrid"
        if f.exists():
            t = tg.openTextgrid(str(f), includeEmptyIntervals=False)
            tier = t.getTier("words")
            ivs = [e for e in tier.entries if e.label.strip()]
            if len(ivs) != len(words):
                ivs = None
        for k, x in enumerate(words):
            row = {"i": x["i"]}
            if "sub" in x:
                row["sub"] = x["sub"]
            iv = ivs[k] if ivs else None
            if iv is None or iv.label.strip().lower() in ("<unk>", "spn"):
                row.update(start=None, end=None, status="failed")
            else:
                row.update(start=round(s["start"] + iv.start + offset, 3),
                           end=round(s["start"] + iv.end + offset, 3), status="aligned")
            rows.append(row)

    models = []
    for kind, sub, ext in (("acoustic", "acoustic", ".zip"), ("dictionary", "dictionary", ".dict"), ("g2p", "g2p", ".zip")):
        p = PM / sub / f"{v[kind]}{ext}"
        models.append({"id": f"{kind}/{v[kind]}", "revision": "v" + v["versions"][kind], "sha256": sha256(p)})
    mfa_ver = subprocess.run([mfa, "version"], env=env, capture_output=True, text=True).stdout.strip()
    out = {"aligner": "A-MFA", "variant": a.variant, "words": rows, "provenance": {
        "packages": {"montreal-forced-aligner": mfa_ver},
        "models": models,
        "settings": {"frameMs": 10, "beam": "default(10)", "retry_beam": "default(40)", "single_speaker": True,
                     "jobs": a.jobs, "g2p_for_oov": True, "mfaExitCode": r.returncode,
                     "peakRssNote": "resource.RUSAGE_CHILDREN ru_maxrss: largest single waited-for descendant, not a summed tree"},
        "platform": "darwin x86_64 native (micromamba env mfa)",
        "wallSeconds": round(time.time() - t0, 2),
        "peakRssBytes": int(rss)}}
    json.dump(out, open(a.out, "w"), indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode:
        print("mfa exit", r.returncode, "see", log, file=sys.stderr)


if __name__ == "__main__":
    main()
