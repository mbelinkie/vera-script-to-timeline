"""Recording B: run the accepted #53 take logic on the default pipeline and render a playback.

Recording B has no take reference, so this is for the Producer to watch, not a
score. Rows are the B prompter's paragraphs (B has no on/off restart markers;
assumption recorded in the report). Words come from the recommended Script to
Timeline pipeline: ElevenLabs Scribe v2 -> script reconcile -> MFA. #53's
`discover()` and `propose_quiet_cuts()` run unchanged from the accepted commit
(`--code-dir`, extracted read-only). Quiet intervals are measured on the
original recorder audio (the #53 -40 dBFS / 120 ms gate).

For each row, the playback shows the default suggestion (last complete read,
else the review-only assembly pieces), cut at quiet frames with ten-frame
handles (reduced padding allowed and reported, as approved for #53 previews).
Each segment is a chapter; 0.5 s of black separates segments.

Private outputs (video, plan, report) go to --out; nothing is committed.

Usage: b_playback.py --code-dir DIR --video SAMPLE.mp4 --out OUT_DIR
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import soundfile as sf

DATA = Path.home() / ".local/share/vera/word-timing-v2"
SRC = "eleven-or"
FPS = [30, 1]


def words_for(rec: Path) -> list[dict]:
    rows = {
        (r["i"], r.get("sub", 0)): r
        for r in json.loads(
            (rec / f"runs/T-CR-{SRC}__A-MFA-english_us_arpa.json").read_text()
        )["words"]
    }
    tokens = json.loads((rec / f"pipe/tokens-{SRC}.json").read_text())
    tokens = tokens["tokens"] if isinstance(tokens, dict) else tokens
    subs: dict[int, list[tuple[int, int]]] = {}
    for s in json.loads((rec / f"pipe/segments-{SRC}.json").read_text())["segments"]:
        for e in s["words"]:
            subs.setdefault(int(e["i"]), []).append((int(e["i"]), int(e.get("sub", 0))))
    out = []
    for i, display in enumerate(tokens):
        parts = [rows.get(k) for k in subs.get(i, [])]
        ok = bool(parts) and all(p and p["status"] == "aligned" for p in parts)
        out.append(
            {
                "text": str(display),
                "start": min(p["start"] for p in parts) if ok else None,
                "end": max(p["end"] for p in parts) if ok else None,
                "precision": "acoustic" if ok else "missing",
                "provenance": f"T-CR-{SRC} + MFA",
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--rules",
        choices=["v1", "v2"],
        default="v2",
        help="v1 = accepted #53 output; v2 = take_rules_v2 refinement",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_dir))
    from experiments.issue53.boundaries import find_quiet_intervals, propose_quiet_cuts
    from experiments.issue53.takes import discover

    args.out.mkdir(parents=True, exist_ok=True)
    paragraphs = [
        p.strip()
        for p in (DATA / "scripts/rec-b-prompter.txt").read_text().split("\n\n")
        if p.strip()
    ]
    rows = [
        {"id": f"row-{n}", "text": p, "beat_ids": []}
        for n, p in enumerate(paragraphs, 1)
    ]
    pcm, sr = sf.read(DATA / "rec-b-raw/rec-b-raw-48k.wav", dtype="int16")
    duration = len(pcm) / sr
    quiet = find_quiet_intervals(pcm.tolist(), sr, 1)
    words = words_for(DATA / "rec-b")
    report = discover(
        {
            "version": "take-experiment/1",
            "source": {"alias": "Run B", "duration": round(duration, 3), "fps": FPS},
            "rows": rows,
            "words": words,
            "audio_activity": [],
            "decisions": {},
            "provenance": {
                "variant": f"T-CR-{SRC} + MFA",
                "reference_labels_removed": True,
            },
            "options": {"include_partial_alternates": True},
        }
    )
    if args.rules == "v2":
        from take_rules_v2 import refine

        report = refine(report)
    (args.out / "discovery.json").write_text(json.dumps(report, indent=1))
    notes = {i["row"]: i for i in report.get("take_rules_v2", {}).get("rows", [])}

    def diff_line(d: dict | None) -> str:
        if not d or not d.get("differs_from_script"):
            return "word-for-word as scripted"
        bits = []
        if d["moved"]:
            bits.append("moved " + ", ".join(f"'{m['word']}'" for m in d["moved"]))
        if d["substituted"]:
            bits.append(
                "said "
                + ", ".join(
                    f"'{x['said']}' for '{x['script']}'" for x in d["substituted"]
                )
            )
        if d["added"]:
            bits.append("added '" + " ".join(d["added"]) + "'")
        if d["omitted"]:
            bits.append("skipped '" + " ".join(d["omitted"]) + "'")
        return "DIFFERS FROM SCRIPT: " + "; ".join(bits)

    by_id = {c["id"]: c for c in report["candidates"]}
    rw = report["words"]

    def span(a: int, b: int) -> list[float] | None:
        t = [(w["start"], w["end"]) for w in rw[a:b] if w.get("start") is not None]
        return [min(x[0] for x in t), max(x[1] for x in t)] if t else None

    plan, lines = (
        [],
        [
            "# Recording B — #53 take logic on the default pipeline",
            "",
            f"Words: ElevenLabs → reconcile → MFA. Rows: {len(rows)} prompter paragraphs "
            "(assumption: B has no on/off markers). Chapters in the video follow this list.",
            "",
        ],
    )
    for row, g in zip(report["rows"], report["groups"], strict=True):
        ranges = []
        info = notes.get(row["id"], {})
        if g["suggested_last_complete"]:
            c = by_id[g["suggested_last_complete"]]
            kind = (
                "continuous delivery (complete)"
                if c.get("kind") == "delivery_run"
                else "last complete read"
            )
            ranges = [
                (
                    kind,
                    tuple(c["word_range"]),
                    info.get("differences"),
                    info.get("alternates", []),
                )
            ]
        elif g["assembly"]:
            ranges = [
                (
                    "assembly piece (review only)",
                    tuple(p["source_word_range"]),
                    p.get("differences"),
                    p.get("alternates", []),
                )
                for p in g["assembly"]["pieces"]
            ]
        alts = len(g["alternatives"]) + len(g["partial_alternatives"])
        lines += [
            f"## {row['id']}: {row['text'][:90]}…",
            "",
            f"Default: {g['suggested_last_complete'] or 'none (assembly)'}; "
            f"earlier complete/partial alternatives kept: {alts}; status: {g['selection_status']}.",
            "",
        ]
        for kind, (a, b), dif, alts_v2 in ranges:
            sp = span(a, b)
            if sp is None:
                lines.append(f"- {kind}: no acoustic timing, not rendered")
                continue
            adjacent = [
                [w["start"], w["end"]]
                for k, w in enumerate(rw)
                if w.get("start") is not None and not a <= k < b
            ]
            cut = propose_quiet_cuts(
                sp, FPS, duration, quiet, adjacent, allow_reduced_padding=True
            )
            fr = cut["frame_range"] or [int(sp[0] * 30) - 10, int(sp[1] * 30) + 10]
            text = " ".join(w["token"] for w in rw[a:b])
            plan.append(
                {
                    "row": row["id"],
                    "kind": kind,
                    "frames": fr,
                    "quiet": cut["frame_range"] is not None,
                    "reasons": cut["reasons"],
                    "text": text,
                }
            )
            lines.append(
                f"- **Chapter {len(plan)}** ({kind}, {fr[0] / 30:.2f}–{fr[1] / 30:.2f} s"
                f"{'' if cut['frame_range'] else ', NO quiet edge found: padded preview'}): {text}"
            )
            lines.append(f"  - {diff_line(dif)}")
            for n_alt, alt in enumerate(alts_v2, 1):
                asp = span(*alt["source_word_range"])
                when = f"{asp[0]:.2f}–{asp[1]:.2f} s" if asp else "untimed"
                lines.append(
                    f"  - Usable alternate {n_alt} (earlier, {when}): {diff_line(alt['differences'])}"
                )
        lines.append("")
    for s in report["editorial_signals"]:
        lines.append(
            f"Spoken edit note flagged for review: {' '.join(w['token'] for w in rw[s['word_range'][0] : s['word_range'][1]])}"
        )
    (args.out / "plan.json").write_text(json.dumps(plan, indent=1))
    (args.out / "REPORT.md").write_text("\n".join(lines) + "\n")

    parts, meta, t = [], [";FFMETADATA1"], 0.0
    black = args.out / "black.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1920x1080:r=30",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(black),
        ],
        check=True,
    )
    for n, s in enumerate(plan, 1):
        a, b = s["frames"]
        seg = args.out / f"seg-{n:02d}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{a / 30:.4f}",
                "-i",
                str(args.video),
                "-t",
                f"{(b - a) / 30:.4f}",
                "-vf",
                "scale=1920:1080,fps=30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-b:a",
                "192k",
                str(seg),
            ],
            check=True,
        )
        dur = (b - a) / 30
        meta += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(t * 1000)}",
            f"END={int((t + dur) * 1000)}",
            f"title={n}. {s['row']} — {s['kind']}",
        ]
        t += dur + 0.5
        parts += [seg, black]
    (args.out / "concat.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
    (args.out / "chapters.txt").write_text("\n".join(meta) + "\n")
    final = args.out / "rec-b-take-playback.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(args.out / "concat.txt"),
            "-i",
            str(args.out / "chapters.txt"),
            "-map_metadata",
            "1",
            "-map",
            "0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
    )
    print(
        json.dumps(
            {
                "segments": len(plan),
                "quietEdges": sum(s["quiet"] for s in plan),
                "assemblyRows": sum(
                    1 for g in report["groups"] if not g["suggested_last_complete"]
                ),
                "editNotes": len(report["editorial_signals"]),
                "video": final.name,
            }
        )
    )


if __name__ == "__main__":
    main()
