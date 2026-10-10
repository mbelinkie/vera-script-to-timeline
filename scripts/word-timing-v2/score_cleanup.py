"""Score the audio-cleanup test: raw vs Adobe Enhance vs DeepFilterNet.

For each recording and recogniser, compares the frozen Script to Timeline
pipeline (recogniser -> reconcile -> MFA, guides on A) across audio
conditions:

- words: WER, script-name spelling, stumble recall of the reconciled
  transcript against the full key;
- timing: onset/offset median, p95 and share over 120 ms on the unanchored
  reference (A: independent 80; B: blind 40), plus coverage;
- displaced: key words whose same-text MFA word sits 0.5-3 s away (gross
  errors the 0.5 s matcher counts as lost coverage);
- isolation ("same text"): the original condition's reconciled text re-aligned
  on this condition's audio, so only the audio changes.

Prints aggregate tables only; writes the full numbers to --out.

Usage: score_cleanup.py --out cleanup-scores.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import score

DATA = Path.home() / ".local/share/vera/word-timing-v2"
IND_A = (
    Path.home()
    / ".local/share/vera/issue-51-preflight/run-a/ctc-direct-v1/annotation/frozen-reference-v2.json"
)
DICT = DATA / "cache/mfa/pretrained_models/dictionary/english_us_arpa.dict"
SOURCES = [
    "eleven-or",
    "assemblyai",
    "speechmatics",
    "chirp2-kt",
    "resolve",
    "parakeet",
]
RECS = {
    "A": {
        "key": "answer-key/rec-a/rec-a-markers-adjusted.csv",
        "aliases": "scripts/aliases-rec-a.json",
        "prompter": "scripts/rec-a-prompter.json",
        "independent": IND_A,
        "original": "rec-a",
        "conditions": {"raw": "rec-a", "adobe": "rec-a-enh", "dfn": "rec-a-dfn"},
    },
    "B": {
        "key": "answer-key/rec-b/rec-b-markers-final.csv",
        "aliases": "scripts/aliases-rec-b.json",
        "prompter": "scripts/rec-b-prompter.json",
        "independent": DATA / "answer-key/rec-b-blind/rec-b-blind-adjusted.csv",
        "original": "rec-b",
        "conditions": {"raw": "rec-b-raw", "adobe": "rec-b", "dfn": "rec-b-dfn"},
    },
}


def mfa_words(result: Path, segments: Path) -> list[tuple[str, float, float]]:
    ent = {
        (int(e["i"]), int(e.get("sub", 0))): e["text"]
        for s in json.loads(segments.read_text())["segments"]
        for e in s["words"]
    }
    return [
        (ent[(r["i"], r.get("sub", 0))], r["start"], r["end"])
        for r in json.loads(result.read_text())["words"]
        if r["status"] == "aligned"
    ]


def tc_words(tc: Path) -> list[tuple[str, float, float]]:
    return score.system_words_from_tc(json.loads(tc.read_text()))


def script_names(prompter: Path) -> set[str]:
    """Out-of-dictionary script names, exactly as score.py counts them."""
    from prompter import load_dictionary
    from reconcile import script_units

    dictionary = load_dictionary(DICT)
    return {
        u["text"]
        for u in script_units(json.loads(prompter.read_text()))
        if u["name"] and u["text"] not in dictionary
    }


def displaced(key: list, words: list[tuple[str, float, float]]) -> int:
    pairs = score.match(key, words)
    used, count = set(pairs.values()), 0
    for n, k in enumerate(key):
        if n in pairs or k.tag:
            continue
        mid = (k.start + k.end) / 2
        cands = [
            j
            for j, w in enumerate(words)
            if j not in used
            and score.canon(w[0]) == score.canon(k.text)
            and abs((w[1] + w[2]) / 2 - mid) < 3
        ]
        if cands:
            used.add(min(cands, key=lambda j: abs(words[j][1] - k.start)))
            count += 1
    return count


def timing(ref: list, words: list[tuple[str, float, float]]) -> dict:
    pairs = score.match(ref, words)
    on = [(words[j][1] - ref[n].start) * 1000 for n, j in pairs.items()]
    off = [(words[j][2] - ref[n].end) * 1000 for n, j in pairs.items()]
    return {
        "coverage": len(pairs) / len(ref),
        "onset": score.stats(on),
        "offset": score.stats(off),
    }


def run_file(
    cond_dir: Path, src: str, original: bool, iso: bool = False
) -> tuple[Path, Path] | None:
    runs, pipe = cond_dir / "runs", cond_dir / "pipe"
    if iso:
        pairs = [
            (
                runs / f"ORIGTEXT-{src}__A-MFA-english_us_arpa.json",
                pipe / f"segments-origtext-{src}.json",
            )
        ]
    else:
        pairs = [
            (
                runs / f"T-CR-{src}__A-MFA-G-english_us_arpa.json",
                pipe / f"segments-{src}.json",
            ),
            (
                runs / f"T-CR-{src}__A-MFA-english_us_arpa.json",
                pipe / f"segments-{src}.json",
            ),
        ]
        if not original:
            pairs = pairs[1:]
    return next(((r, s) for r, s in pairs if r.exists() and s.exists()), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: dict = {}
    for rec, cfg in RECS.items():
        score.ALIASES.clear()
        score.ALIASES.update(
            {
                k: v
                for k, v in json.loads((DATA / cfg["aliases"]).read_text()).items()
                if not k.startswith("_")
            }
        )
        key = score.load_key(DATA / cfg["key"])
        blind = cfg["independent"].suffix.lower() == ".csv"
        ref = score.load_independent(cfg["independent"], [] if blind else key)
        names = script_names(DATA / cfg["prompter"])
        print(
            f"\n== Recording {rec}  (timing ref n={len(ref)}; words vs full key n={len(key)})"
        )
        print(
            f"{'recogniser':13s} {'audio':6s} | {'WER':>5s} {'names':>6s} {'stumb':>5s} | {'cov':>5s} "
            f"{'on med/p95/>120':>16s} | {'off med/p95/>120':>16s} | disp | same-text on/off med"
        )
        for src in SOURCES:
            for cname, cdir in cfg["conditions"].items():
                d = DATA / cdir
                original = cdir == cfg["original"]
                row: dict = {}
                tc = d / "cloud" / f"T-CR-{src}.json"
                if tc.exists():
                    hyp = tc_words(tc)
                    row["wer"] = score.wer(key, hyp)["wer"]
                    pairs = score.match(key, hyp)
                    st = score.stumble_recall(key, hyp, pairs).get("all")
                    row["stumbles"] = st["recall"] if st else None
                    if names:
                        row["names"] = score.name_spelling(key, hyp, pairs, names)
                rf = run_file(d, src, original)
                if rf:
                    words = mfa_words(*rf)
                    row["timing"] = timing(ref, words)
                    row["displaced"] = displaced(key, words)
                iso = None if original else run_file(d, src, False, iso=True)
                if iso:
                    row["sameText"] = timing(ref, mfa_words(*iso))
                out.setdefault(rec, {}).setdefault(src, {})[cname] = row

                def s3(s: dict) -> str:
                    return (
                        f"{s['median']:3.0f}/{s['p95']:4.0f}/{100 * s['over120Share']:4.1f}%"
                        if s.get("n")
                        else "        -"
                    )

                t = row.get("timing", {})
                nm = row.get("names")
                same = row.get("sameText")
                print(
                    f"{src:13s} {cname:6s} | {100 * row.get('wer', float('nan')):4.1f}% "
                    f"{(str(nm['scriptSpelled']) + '/' + str(nm['names'])) if nm else '  -':>6s} "
                    f"{100 * row['stumbles'] if row.get('stumbles') is not None else float('nan'):4.0f}% | "
                    f"{100 * t.get('coverage', float('nan')):4.1f}% {s3(t.get('onset', {})):>16s} | "
                    f"{s3(t.get('offset', {})):>16s} | {row.get('displaced', '-'):>4} | "
                    + (
                        f"{same['onset']['median']:3.0f}/{same['offset']['median']:3.0f}"
                        if same
                        else "(orig)"
                    )
                )
    args.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
