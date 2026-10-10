#!/usr/bin/env python3
"""Build an MFA pronunciation dictionary from a prompter script's pronunciation guides.

Run inside the `mfa` micromamba env:
  MAMBA_ROOT_PREFIX=~/.local/share/micromamba micromamba run -n mfa \
    python guide_dict.py --prompter prompter.json --variant english_us_arpa|english_mfa --out extra.dict \
    [--rule whole|syllable]

For each guided word ({"display": "Bara", "guide": "BAH-ra"}) the respelling is lower-cased and run
through the SAME G2P model align_mfa.py uses for that variant. Output lines are
`<casefolded script word>\t<phones>` ("bara\tB AA1 R AH0").
Rules: `whole`: drop hyphens, G2P the joined respelling ("bahra").
       `syllable` (default): G2P each hyphen-separated syllable, concatenate the phones.
Only the first (best) G2P pronunciation is used. G2P runs in a private MFA root/temp dir, so it can
run while other MFA jobs use the shared cache.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "mfa"))
from align_mfa import HOME, PM, VARIANTS  # noqa: E402


def g2p_first(words, variant, work):
    """words: list of str -> {word: 'PH ON ES'} (first pronunciation each)."""
    v = VARIANTS[variant]
    work = Path(work)
    root = work / "root"
    root.mkdir(parents=True, exist_ok=True)
    link = root / "pretrained_models"
    if not link.exists():
        link.symlink_to(PM)
    inp, outp = work / "words.txt", work / "g2p.out"
    inp.write_text("\n".join(sorted(set(words))) + "\n")
    mfa = str(Path(sys.executable).parent / "mfa")
    r = subprocess.run([mfa, "g2p", str(inp), str(PM / "g2p" / f"{v['g2p']}.zip"), str(outp),
                        "--clean", "--num_pronunciations", "1", "--temporary_directory", str(work / "tmp")],
                       env=dict(os.environ, MFA_ROOT_DIR=str(root)), capture_output=True, text=True)
    if r.returncode or not outp.exists():
        sys.exit("mfa g2p failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    res = {}
    for line in outp.read_text().splitlines():
        w, _, ph = line.partition("\t")
        res.setdefault(w, ph.strip())  # first = best
    return res


def build(guides, variant, rule, work):
    entries = {}  # script word -> phones (first guide wins if a word repeats)
    spell = {}
    for g in guides:
        word = g["display"].casefold()
        if word in spell:
            continue
        spell[word] = g["guide"].lower()
    parts = {w: ([s.replace("-", "")] if rule == "whole" else [p for p in s.split("-") if p]) for w, s in spell.items()}
    g2p = g2p_first([p for ps in parts.values() for p in ps], variant, work)
    for w, ps in parts.items():
        entries[w] = " ".join(g2p[p] for p in ps)
    return spell, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompter", required=True)
    ap.add_argument("--variant", required=True, choices=list(VARIANTS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--rule", default="syllable", choices=["whole", "syllable"])
    a = ap.parse_args()
    guides = json.load(open(a.prompter)).get("guides", [])
    (HOME / "work").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="guide-g2p-", dir=HOME / "work") as work:
        spell, entries = build(guides, a.variant, a.rule, work)
    with open(a.out, "w") as f:
        for w, ph in entries.items():
            f.write(f"{w}\t{ph}\n")
    for w, ph in entries.items():
        print(f"{w} [{spell[w]}] -> {ph}")


if __name__ == "__main__":
    main()
