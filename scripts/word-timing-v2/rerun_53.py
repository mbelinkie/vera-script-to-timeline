"""Re-run the accepted #53 take logic on machine transcripts (recording A).

#53's accepted run ("Sample v2") fed the Producer's accurate transcript, with no
word times, to `discover()` and recovered all 15 highlighted spans. This
re-run feeds each Script to Timeline pipeline's transcript instead
(recogniser -> script reconcile -> MFA with guides), with acoustic word times,
and asks the same question in time rather than word indices, because machine
transcripts have different words:

- A highlight's reference span = the frozen A answer key's start of its first
  word and end of its last word (highlight word indices map to key words by
  edit alignment; the key is the Producer transcript with corrected times).
- **Recovered**: the candidates that overlap the highlight in time (row
  candidates only) together span it to within TOL seconds at both ends.
- **Primary match**: after confirming the single flagged earlier-read option
  (exactly as Sample v2's evaluation did), the ordinary suggestion's selected
  material equals the blue spans to within TOL at every edge.

`discover()` is imported unchanged from the accepted commit on branch
`codex/issue-53-provider-neutral-takes` (extracted read-only with
`git archive`). Discovery never sees the highlights. Private outputs go to
OUT; this script prints aggregates only.

Usage: rerun_53.py --code-dir DIR_WITH_experiments --out OUT_DIR
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import score

DATA = Path.home() / ".local/share/vera/word-timing-v2"
H = Path.home() / ".local/share/vera/issue-51-preflight/run-a/issue-53"
HR = H / "producer-highlight-review-01"
TOL = 0.25
SOURCES = [
    "eleven-or",
    "assemblyai",
    "speechmatics",
    "chirp2-kt",
    "resolve",
    "parakeet",
    "whisper",
]


def key_times(acc_words: list[str]) -> list[tuple[float, float] | None]:
    key = score.load_key(DATA / "answer-key/rec-a/rec-a-markers-adjusted.csv")
    k = [score.canon(x.text) for x in key]
    out: list[tuple[float, float] | None] = [None] * len(acc_words)
    sm = difflib.SequenceMatcher(None, acc_words, k, autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for t in range(n):
            out[a + t] = (key[b + t].start, key[b + t].end)
    return out


def pipeline_words(src: str) -> list[dict]:
    runs = DATA / "rec-a/runs"
    result = runs / f"T-CR-{src}__A-MFA-G-english_us_arpa.json"
    if not result.exists():
        result = runs / f"T-CR-{src}__A-MFA-english_us_arpa.json"
    rows = {
        (r["i"], r.get("sub", 0)): r for r in json.loads(result.read_text())["words"]
    }
    tokens = json.loads((DATA / f"rec-a/pipe/tokens-{src}.json").read_text())
    tokens = tokens["tokens"] if isinstance(tokens, dict) else tokens
    seg = json.loads((DATA / f"rec-a/pipe/segments-{src}.json").read_text())
    subs: dict[int, list[tuple]] = {}
    for s in seg["segments"]:
        for e in s["words"]:
            subs.setdefault(int(e["i"]), []).append((int(e["i"]), int(e.get("sub", 0))))
    words = []
    for i, display in enumerate(tokens):
        parts = [rows.get(k) for k in subs.get(i, [])]
        ok = parts and all(p and p["status"] == "aligned" for p in parts)
        words.append(
            {
                "text": str(display),
                "start": min(p["start"] for p in parts) if ok else None,
                "end": max(p["end"] for p in parts) if ok else None,
                "precision": "acoustic" if ok else "missing",
                "provenance": f"T-CR-{src} + {result.stem.split('__')[1]}",
            }
        )
    return words, result.name


def span(words: list[dict], rng: range) -> tuple[float, float] | None:
    times = [
        (w["start"], w["end"])
        for w in (words[i] for i in rng)
        if w["start"] is not None
    ]
    return (min(t[0] for t in times), max(t[1] for t in times)) if times else None


def close(a: tuple[float, float] | None, b: tuple[float, float]) -> bool:
    return a is not None and abs(a[0] - b[0]) <= TOL and abs(a[1] - b[1]) <= TOL


def evaluate(report: dict, labels: list[dict], ref: list[tuple[float, float]]) -> dict:
    words = report["words"]
    cands = [c for c in report["candidates"] if c["row"]]
    by_id = {c["id"]: c for c in report["candidates"]}
    rec = []
    for lab, r in zip(labels, ref, strict=True):
        hits = []
        for c in cands:
            s = span(words, range(*c["word_range"]))
            if s and min(s[1], r[1]) - max(s[0], r[0]) > 0.1:
                hits.append(s)
        union = (min(h[0] for h in hits), max(h[1] for h in hits)) if hits else None
        rec.append(
            {
                "label": lab["id"],
                "color": lab["color"],
                "recovered": close(union, r),
                "deltaStart": None if union is None else round(union[0] - r[0], 3),
                "deltaEnd": None if union is None else round(union[1] - r[1], 3),
            }
        )
    # ordinary suggestion, with the single flagged earlier option confirmed (as Sample v2)
    # Same selection as Sample v2's evaluation: last complete read per row, else
    # the row's assembly pieces; then swap in the single flagged earlier option.
    selected: set[int] = set()
    for g in report["groups"]:
        if g["suggested_last_complete"]:
            selected.update(range(*by_id[g["suggested_last_complete"]]["word_range"]))
        elif g["assembly"]:
            for p in g["assembly"]["pieces"]:
                selected.update(range(*p["source_word_range"]))
    for sig in report["editorial_signals"]:
        if len(sig["earlier_candidate_options"]) == 1 and sig["related_candidates"]:
            selected.difference_update(
                range(*by_id[sig["related_candidates"][-1]]["word_range"])
            )
            selected.update(
                range(*by_id[sig["earlier_candidate_options"][0]]["word_range"])
            )
    runs: list[range] = []
    for i in sorted(selected):
        if runs and runs[-1].stop == i:
            runs[-1] = range(runs[-1].start, i + 1)
        else:
            runs.append(range(i, i + 1))
    chosen_spans = [s for rng in runs if (s := span(words, rng))]
    blue = [r for lab, r in zip(labels, ref, strict=True) if lab["color"] == "blue"]

    def covered(b: tuple[float, float]) -> bool:
        parts = [s for s in chosen_spans if min(s[1], b[1]) - max(s[0], b[0]) > 0.1]
        return bool(parts) and close(
            (min(p[0] for p in parts), max(p[1] for p in parts)), b
        )

    blue_hit = sum(covered(b) for b in blue)
    return {
        "recovered": sum(x["recovered"] for x in rec),
        "spans": len(rec),
        "blueMatchedBySuggestion": blue_hit,
        "blueSpans": len(blue),
        "assemblyGroups": sum(
            1 for g in report["groups"] if not g["suggested_last_complete"]
        ),
        "editorialSignals": len(report["editorial_signals"]),
        "perSpan": rec,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_dir))
    from experiments.issue53.takes import discover

    args.out.mkdir(parents=True, exist_ok=True)
    acc = json.loads((HR / "accurate-normalized.json").read_text())
    labels = json.loads((HR / "highlight-evaluation-private.json").read_text())
    kt = key_times([w["text"].lower() for w in acc["words"]])
    ref = []
    for lab in labels:
        first, last = kt[lab["indices"][0]], kt[lab["indices"][-1]]
        ref.append((first[0], last[1]))
    activity = json.loads((H / "review-03/audio-activity.json").read_text())

    summary = {}
    # Exact Sample v2 replica: untimed accurate text; key times attached only
    # after discovery, for scoring. Validates this evaluator (expect 15/15, 7/7).
    replica = discover({**acc, "options": {"include_partial_alternates": True}})
    for i, t in enumerate(kt):
        replica["words"][i]["start"], replica["words"][i]["end"] = (
            t if t else (None, None)
        )
    summary["producer-text, untimed (Sample v2 replica)"] = evaluate(
        replica, labels, ref
    )
    variants = {
        "producer-text (Sample v2 input, key times)": [
            {
                **w,
                "start": t[0] if t else None,
                "end": t[1] if t else None,
                "precision": "acoustic" if t else "missing",
            }
            for w, t in zip(acc["words"], kt, strict=True)
        ]
    }
    for src in SOURCES:
        words, name = pipeline_words(src)
        variants[f"{src} ({name})"] = words
    for name, words in variants.items():
        for timed in (True, False):
            # untimed: discovery sees text only (as Sample v2 did); the
            # pipeline's acoustic times are attached afterwards for scoring.
            fed = (
                words
                if timed
                else [
                    {**w, "start": None, "end": None, "precision": "missing"}
                    for w in words
                ]
            )
            packet = {
                **{k: acc[k] for k in ("version", "source", "rows", "decisions")},
                "provenance": {"variant": name, "reference_labels_removed": True},
                "words": fed,
                "audio_activity": activity.get("intervals", activity),
                "options": {"include_partial_alternates": True},
            }
            label = f"{name.split(' (')[0]} [{'timed' if timed else 'untimed'}]"
            try:
                report = discover(packet)
            except Exception as e:  # report and continue: a rejection is a finding
                summary[label] = {"error": f"{type(e).__name__}: {e}"[:300]}
                continue
            if not timed:
                for i, w in enumerate(words):
                    report["words"][i]["start"], report["words"][i]["end"] = (
                        w["start"],
                        w["end"],
                    )
            slug = label.replace(" ", "_").replace("[", "").replace("]", "")
            (args.out / f"discovery-{slug}.json").write_text(
                json.dumps(report, indent=1)
            )
            summary[label] = evaluate(report, labels, ref)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    for name, s in summary.items():
        if "error" in s:
            print(f"{name:60s} ERROR {s['error']}")
        else:
            print(
                f"{name:60s} spans {s['recovered']:2d}/{s['spans']}  blue-by-suggestion "
                f"{s['blueMatchedBySuggestion']}/{s['blueSpans']}  assembly-groups {s['assemblyGroups']}  "
                f"edit-notes {s['editorialSignals']}"
            )


if __name__ == "__main__":
    main()
