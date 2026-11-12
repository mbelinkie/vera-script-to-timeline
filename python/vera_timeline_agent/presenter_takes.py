"""Find the takes in a presenter recording and match them to the script (#45).

One command:

    python -m vera_timeline_agent.presenter_takes VIDEO --script SCRIPT
        [--audio SEPARATE_AUDIO] --out FOLDER
    python -m vera_timeline_agent.presenter_takes VIDEO --audio SEPARATE_AUDIO
        --sync-only

It writes `takes.json` (for the take-approval work in #46 and #47) and
`report.txt` (for a person), and prints the time taken.

How it works, in order:

1. The camera sound is decoded. With `--audio`, the separate recording is
   lined up with it (`presenter_sync`) and used instead; if the match is not
   confident the command stops.
2. The accepted local engines transcribe and time every word
   (`vera_word_timing`: Parakeet, script reconciliation, Montreal Forced
   Aligner).
3. The script is split into passages: its `(on)` / `(off)` blocks, or its
   paragraphs when it has none.
4. The take rules the Producer accepted in #53 (`experiments.issue53`,
   refined by `experiments.issue45.take_rules`) group the words into takes
   per passage and suggest the last complete one. Nothing here adds rules.
5. Each take's cut points are moved out into measured quiet, about ten
   frames clear of speech (`experiments.issue53.boundaries`).

Everything that was said is kept: speech matching no passage is listed as
off-script. A word the aligner could not place has no time, and a take whose
edge word has no time has no cut. A suggestion is never an approval.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from vera_word_timing.adapters.local_engines import EngineConfig, ParakeetRecognizer
from vera_word_timing.artifacts import AudioRef, file_hash
from vera_word_timing.ports import PortRefusal, ProjectPolicy
from vera_word_timing.profiles import script_to_timeline
from vera_word_timing.script_reconcile import load_dictionary_words, parse_prompter

from experiments.issue45.take_rules import differences, refine
from experiments.issue53.boundaries import propose_quiet_cuts
from experiments.issue53.takes import discover, tokens
from vera_timeline_agent.presenter_sync import (
    Samples,
    SyncRefused,
    SyncResult,
    find_offset,
)

Json = dict[str, Any]
RATE = 16000  # the engines' sample rate; all audio work happens at it
MARKER = re.compile(r"\((?:on|off)\)", re.IGNORECASE)
PADDING_FRAMES = 10
QUIET_DB = -40.0  # the #53 quiet rule: RMS at or below this ...
QUIET_PEAK_DB = -28.0  # ... peaks at or below this ...
QUIET_MIN_S = 0.12  # ... for at least this long
MAX_DISAGREEMENT_S = 0.4  # aligner versus recogniser, on where a word starts


class TakesError(Exception):
    """A plain-language reason the command cannot continue."""


# --------------------------------------------------------------------------
# Script


_RTF_TOKEN = re.compile(
    r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)",
    re.IGNORECASE,
)
_RTF_SKIPPED_GROUPS = {
    "fonttbl",
    "colortbl",
    "stylesheet",
    "info",
    "pict",
    "header",
    "footer",
    "expandedcolortbl",
    "listtable",
    "listoverridetable",
    "generator",
}
_RTF_BREAKS = {"par": "\n", "line": "\n", "sect": "\n", "page": "\n", "tab": "\t"}


def rtf_to_text(data: str) -> str:
    """The plain text of an RTF document; formatting is dropped."""
    out: list[str] = []
    stack: list[tuple[int, bool]] = []
    unicode_skip, skipping, pending_skip = 1, False, 0
    for match in _RTF_TOKEN.finditer(data):
        word, number, hexadecimal, symbol, brace, char = match.groups()
        if brace == "{":
            stack.append((unicode_skip, skipping))
        elif brace == "}":
            if stack:
                unicode_skip, skipping = stack.pop()
        elif symbol:
            pending_skip = 0
            if symbol == "*":
                skipping = True
            elif not skipping:
                out.append({"~": chr(160), "\n": "\n", "\r": "\n"}.get(symbol, symbol))
        elif word:
            pending_skip = 0
            if word in _RTF_SKIPPED_GROUPS:
                skipping = True
            elif skipping:
                continue
            elif word in _RTF_BREAKS:
                out.append(_RTF_BREAKS[word])
            elif word == "uc" and number:
                unicode_skip = int(number)
            elif word == "u" and number:
                code = int(number)
                out.append(chr(code + 65536 if code < 0 else code))
                pending_skip = unicode_skip
        elif hexadecimal:
            if pending_skip:
                pending_skip -= 1
            elif not skipping:
                out.append(bytes.fromhex(hexadecimal).decode("cp1252", "replace"))
        elif char:
            if pending_skip:
                pending_skip -= 1
            elif not skipping:
                out.append(char)
    return "".join(out)


def read_script(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise TakesError(f"The script could not be read: {path.name}") from error
    if raw.lstrip().startswith(b"{\\rtf"):
        return rtf_to_text(raw.decode("ascii", "replace"))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TakesError("The script must be RTF or UTF-8 text.") from error


@dataclass(frozen=True)
class Passage:
    id: str
    script: str  # as written, for people
    text: str  # spoken words with sentence stops, for the take rules


def script_passages(script_text: str, dictionary: set[str]) -> list[Passage]:
    """`(on)` / `(off)` blocks, or paragraphs when the script has no markers."""
    blocks = (
        MARKER.split(script_text)
        if MARKER.search(script_text)
        else script_text.splitlines()
    )
    passages: list[Passage] = []
    for block in blocks:
        pieces: list[str] = []
        for word in parse_prompter(block, dictionary).words:
            if word["sentenceStart"] and pieces:
                pieces[-1] += "."
            pieces.append(" ".join(word["spoken"]))
        if pieces:
            shown = " ".join(re.sub(r"\[[^\]]*\]", "", block).split())
            passages.append(
                Passage(f"passage-{len(passages) + 1}", shown, " ".join(pieces) + ".")
            )
    if not passages:
        raise TakesError("The script has no words.")
    return passages


# --------------------------------------------------------------------------
# Media


def _run(command: list[str]) -> bytes:
    try:
        done = subprocess.run(command, capture_output=True, check=False)
    except OSError as error:
        raise TakesError(f"{command[0]} is not installed.") from error
    if done.returncode != 0:
        tail = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
        raise TakesError(f"{command[0]} could not read the file: {' '.join(tail)}")
    return done.stdout


def probe_video(path: Path) -> tuple[float, list[int]]:
    """(duration in seconds, [fps numerator, denominator]) of the picture."""
    raw = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate,duration:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        data = json.loads(raw)
        stream = data["streams"][0]
        rate = Fraction(stream["r_frame_rate"])
        duration = float(stream.get("duration") or data["format"]["duration"])
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as error:
        raise TakesError(f"{path.name} has no readable picture.") from error
    if rate <= 0 or duration <= 0:
        raise TakesError(f"{path.name} has no readable picture.")
    return duration, [rate.numerator, rate.denominator]


def decode_audio(path: Path) -> Samples:
    """The file's first audio stream as mono float samples at RATE."""
    raw = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "aresample=async=1:first_pts=0",
            "-ac",
            "1",
            "-ar",
            str(RATE),
            "-f",
            "f32le",
            "-",
        ]
    )
    samples = np.frombuffer(raw, dtype=np.float32)
    if not len(samples):
        raise TakesError(f"{path.name} has no sound.")
    return samples


def shift_to_video(
    separate: Samples, offset_s: float, camera: Samples
) -> tuple[Samples, list[list[float]]]:
    """The separate audio on the video's clock.

    Where the separate recording does not reach (it started late or stopped
    early) the camera's own sound is kept, so nothing said is lost. Returns
    the sound and the video-time ranges that are camera sound.
    """
    start = round(offset_s * RATE)
    out = camera.copy()
    lo, hi = max(0, start), min(len(separate), start + len(camera))
    if hi <= lo:
        return out, [[0.0, len(camera) / RATE]]
    out[lo - start : hi - start] = separate[lo:hi]
    uncovered = [
        [a / RATE, b / RATE]
        for a, b in ((0, lo - start), (hi - start, len(camera)))
        if b - a >= RATE // 100
    ]
    return out, uncovered


def write_wav(path: Path, samples: Samples) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())


def quiet_intervals(
    samples: Samples, duration_s: float, rate: int = RATE
) -> list[list[float]]:
    """Sustained low-level stretches, measured in 10 ms windows (the #53 rule).

    Low level is evidence for a clean cut, not proof that nobody is speaking.
    Intervals never run past `duration_s`, the end of the picture.
    """
    window = max(1, rate // 100)
    count = len(samples) // window
    if not count:
        return []
    blocks = samples[: count * window].astype(np.float64).reshape(count, window)
    low = (np.sqrt((blocks * blocks).mean(axis=1)) <= 10 ** (QUIET_DB / 20)) & (
        np.abs(blocks).max(axis=1) <= 10 ** (QUIET_PEAK_DB / 20)
    )
    edges = np.flatnonzero(np.diff(np.concatenate(([False], low, [False]))))
    spans = (
        (float(a * window / rate), min(float(b * window / rate), duration_s))
        for a, b in zip(edges[::2], edges[1::2], strict=True)
    )
    return [[a, b] for a, b in spans if b - a >= QUIET_MIN_S - 1e-9]


# --------------------------------------------------------------------------
# Takes


def timed_words(recognition: Json, alignment: Json) -> list[Json]:
    """One record per aligned unit: text, start and end in seconds, precision.

    `acoustic`: the aligner's time. `derived`: the aligner and the recogniser
    disagree about where the word starts by more than MAX_DISAGREEMENT_S, so
    the aligner's time is not trusted (it drags words onto sniffs, laughs and
    stammers); the word gets the recogniser's own rougher time instead, shared
    evenly between its units. `missing`: no usable time. Times never run
    backwards: a time that would overlap its neighbour is shortened or dropped.
    """
    anchors = {t["index"]: t for t in recognition["tokens"]}
    units = alignment["words"]
    by_token: dict[int, list[int]] = {}
    for i, unit in enumerate(units):
        by_token.setdefault(unit["tokenIndex"], []).append(i)
    words: list[Json] = [
        {"text": u["text"], "start": None, "end": None, "precision": "missing"}
        for u in units
    ]
    for token_index, members in by_token.items():
        anchor = anchors.get(token_index, {})
        a, b = anchor.get("anchorStartMs"), anchor.get("anchorEndMs")
        placed = [i for i in members if units[i]["status"] == "acoustic"]
        aligned_start = min((units[i]["startMs"] for i in placed), default=None)
        trusted = len(placed) == len(members) and (
            a is None
            or aligned_start is None
            or abs(aligned_start - a) <= MAX_DISAGREEMENT_S * 1000
        )
        if trusted:
            for i in members:
                words[i].update(
                    start=units[i]["startMs"] / 1000,
                    end=units[i]["endMs"] / 1000,
                    precision="acoustic",
                )
        elif a is not None and b is not None and b > a:
            step = (b - a) / len(members)
            for n, i in enumerate(members):
                words[i].update(
                    start=(a + n * step) / 1000,
                    end=(a + (n + 1) * step) / 1000,
                    precision="derived",
                )
    floor = 0.0
    for i, word in enumerate(words):
        if word["start"] is None:
            continue
        following = next(
            (w["start"] for w in words[i + 1 :] if w["precision"] == "acoustic"), None
        )
        if word["precision"] == "derived" and following is not None:
            word["end"] = min(word["end"], following)
        word["start"] = max(word["start"], floor)
        if word["end"] - word["start"] < 0.01:
            word.update(start=None, end=None, precision="missing")
        else:
            floor = word["end"]
    return words


def take_packet(
    words: list[Json],
    alignment: Json,
    passages: list[Passage],
    duration_s: float,
    fps: list[int],
) -> Json:
    """The accepted #53 input, built from `timed_words`."""
    words = [{**w, "provenance": "vera-word-timing"} for w in words]
    return {
        "version": "take-experiment/1",
        "source": {"alias": "recording", "duration": duration_s, "fps": fps},
        "rows": [{"id": p.id, "text": p.text, "beat_ids": []} for p in passages],
        "words": words,
        "audio_activity": [],
        "decisions": {},
        "provenance": {"alignmentArtifactId": alignment["artifactId"]},
        "options": {"include_partial_alternates": True},
    }


def _cut(
    words: list[Json],
    word_range: list[int],
    quiet: list[list[float]],
    duration_s: float,
    fps: list[int],
) -> Json:
    """Speech times and a cut in quiet for one run of words, or the reason not."""
    first, last = words[word_range[0]], words[word_range[1] - 1]
    start, end = first["start"], last["end"]
    out: Json = {
        "speechStartS": start,
        "speechEndS": end,
        "approximateStart": first["precision"] != "acoustic",
        "approximateEnd": last["precision"] != "acoustic",
        "cut": None,
    }
    if start is None or end is None:
        edge = "first" if start is None else "last"
        out["cutProblem"] = f"the {edge} word could not be placed in time"
        return out
    before = [w for w in words[: word_range[0]] if w["end"] is not None][-1:]
    after = [w for w in words[word_range[1] :] if w["start"] is not None][:1]
    try:
        plan = propose_quiet_cuts(
            [start, end],
            fps,
            duration_s,
            quiet,
            [[w["start"], w["end"]] for w in before + after],
            padding_frames=PADDING_FRAMES,
            allow_reduced_padding=True,
        )
    except ValueError:
        out["cutProblem"] = "the cut could not be worked out from these times"
        return out
    if plan["frame_range"] is None:
        reasons = set(plan["reasons"])
        out["cutProblem"] = (
            "too close to the start or end of the recording"
            if "source_limit" in reasons
            else "no quiet gap next to the speech"
        )
        return out
    rate = Fraction(*fps)
    start_frame, end_frame = plan["frame_range"]
    out["cut"] = {
        "startFrame": start_frame,
        "endFrame": end_frame,
        "startS": round(float(start_frame / rate), 3),
        "endS": round(float(end_frame / rate), 3),
        "framesClearOfSpeech": plan["added_frames"],
        "reducedPadding": "reduced_padding_to_fit_quiet_gap" in plan["reasons"],
    }
    return out


def _said(
    words: list[Json], word_range: list[int], units: list[Json], rec: Json
) -> str:
    """The recogniser's own words for a run, each recognised token once."""
    display = {t["index"]: t["display"] for t in rec["tokens"]}
    seen: list[int] = []
    for word in words[word_range[0] : word_range[1]]:
        index = units[word["input_index"]]["tokenIndex"]
        if not seen or seen[-1] != index:
            seen.append(index)
    return " ".join(display[i] for i in seen)


def build_takes(
    report: Json,
    timed: list[Json],
    recognition: Json,
    alignment: Json,
    passages: list[Passage],
    quiet: list[list[float]],
    duration_s: float,
    fps: list[int],
) -> Json:
    """The takes file body from the refined #53 report. Adds no take rules."""
    units = alignment["words"]
    # The take rules relabel some words' precision for their own use; the
    # report goes by how each word was actually timed.
    words = [
        {**w, "precision": timed[w["input_index"]]["precision"]}
        for w in report["words"]
    ]
    number_of = {p.id: n for n, p in enumerate(passages, 1)}
    row_tokens = {p.id: tokens(p.text) for p in passages}
    by_passage: dict[str, list[Json]] = {p.id: [] for p in passages}
    take_of: dict[str, Json] = {}
    off_script: list[Json] = []
    for c in report["candidates"]:
        if "members" in c:  # a delivery run made of takes already listed
            continue
        timing = _cut(words, c["word_range"], quiet, duration_s, fps)
        unplaced = sum(
            w["start"] is None for w in words[c["word_range"][0] : c["word_range"][1]]
        )
        common = {
            **timing,
            "said": _said(words, c["word_range"], units, recognition),
            "unplacedWords": unplaced,
        }
        if not c["row"]:
            off_script.append(common)
            continue
        expected = row_tokens[c["row"]]
        takes = by_passage[c["row"]]
        covered = sum(op["op"] in ("equal", "substitute") for op in c["diff"])
        take = {
            "id": f"{c['row']}-take-{len(takes) + 1}",
            "number": len(takes) + 1,
            "complete": bool(c["complete"]),
            "scriptWordsCovered": covered,
            "scriptWords": len(expected),
            "couldAlsoBePassages": [
                number_of[r] for r in c["row_options"] if r != c["row"]
            ],
            **common,
            "differences": differences([c], expected, words, None),
        }
        takes.append(take)
        take_of[c["id"]] = take
    candidates = {c["id"]: c for c in report["candidates"]}
    out_passages = []
    for number, (passage, group) in enumerate(
        zip(passages, report["groups"], strict=True), 1
    ):
        suggested: list[str] = []
        if chosen := group["suggested_last_complete"]:
            members = candidates[chosen].get("members", [chosen])
            suggested = [take_of[m]["id"] for m in members]
        assembly = group.get("assembly") if not suggested else None
        notes = [
            {
                "said": _said(words, s["word_range"], units, recognition),
                "meaning": "The presenter may be pointing at an earlier take. "
                "The choice is yours.",
            }
            for s in report["editorial_signals"]
            if passage.id in s["row_options"]
        ]
        out_passages.append(
            {
                "id": passage.id,
                "number": number,
                "script": passage.script,
                "takes": by_passage[passage.id],
                "suggestedTakes": suggested,
                "choiceNeeded": bool(notes),
                "pieces": [
                    [take_of[m]["id"] for m in piece["members"]]
                    for piece in assembly["pieces"]
                ]
                if assembly
                else [],
                "missingScriptWords": [
                    row_tokens[passage.id][i] for i in assembly["missing_row_tokens"]
                ]
                if assembly
                else [],
                "notes": notes,
            }
        )
    return {
        "passages": out_passages,
        "offScript": off_script,
        "words": {
            "heard": len(units),
            "placed": sum(w["precision"] == "acoustic" for w in timed),
            "recogniserTimed": sum(w["precision"] == "derived" for w in timed),
            "unplaced": sum(w["start"] is None for w in timed),
        },
    }


# --------------------------------------------------------------------------
# Report


def clock(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    minutes, rest = divmod(round(seconds * 100), 6000)
    return f"{minutes}:{rest / 100:05.2f}"


def _times(item: Json) -> str:
    if item["cut"]:
        cut = item["cut"]
        text = (
            f"{clock(cut['startS'])} to {clock(cut['endS'])}"
            f"  (frames {cut['startFrame']} to {cut['endFrame']})"
        )
        if cut["reducedPadding"]:
            a, b = cut["framesClearOfSpeech"]
            text += f"  tight: {a} and {b} frames clear of speech"
        rough = [
            edge
            for edge, flag in (("start", "approximateStart"), ("end", "approximateEnd"))
            if item[flag]
        ]
        if rough:
            text += f"  CHECK BY EAR: {' and '.join(rough)} timed roughly"
        return text
    return (
        f"speech {clock(item['speechStartS'])} to {clock(item['speechEndS'])}"
        f"  NO CLEAN CUT: {item['cutProblem']}"
    )


def _difference_lines(d: Json) -> list[str]:
    lines = [f'said "{s["said"]}" for "{s["script"]}"' for s in d["substituted"]]
    if d["added"]:
        lines.append("added: " + " ".join(d["added"]))
    if d["omitted"]:
        lines.append("left out: " + " ".join(d["omitted"]))
    if d["moved"]:
        lines.append("moved: " + " ".join(m["word"] for m in d["moved"]))
    return lines


def render_report(takes: Json) -> str:
    video, sync = takes["video"], takes["sync"]
    lines = [
        "PRESENTER TAKES",
        "",
        f"Recording: {video['file']}  ({clock(video['durationS'])}, "
        f"{float(Fraction(*video['fps'])):.2f} frames a second)",
        f"Script:    {takes['script']['file']}  ({len(takes['passages'])} passages)",
    ]
    if sync:
        first = "before" if sync["offsetS"] >= 0 else "after"
        lines.append(
            f"Sound:     {sync['file']}, which starts {abs(sync['offsetS']):.3f} "
            f"seconds ({abs(sync['offsetFrames']):.1f} frames) {first} the video. "
            f"Checked at {sync['checkPoints']} points, which agree within "
            f"{sync['spreadMs']:.0f} ms."
        )
        for a, b in sync["cameraSoundUsed"]:
            lines.append(
                f"           The separate file does not cover {clock(a)} to "
                f"{clock(b)} of the video; the camera's sound is used there."
            )
    else:
        lines.append("Sound:     the camera's own")
    counts = takes["words"]
    lines += [
        f"Words:     {counts['heard']} heard: {counts['placed']} placed exactly, "
        f"{counts['recogniserTimed']} placed roughly (the two timing engines "
        f"disagreed), {counts['unplaced']} not placed",
        f"Time taken: {takes['secondsTaken']:.0f} seconds",
        "",
        "Times are minutes:seconds from the start of the video. Each take's times",
        "are cut points in quiet, about ten frames clear of the speech.",
        "A suggested take is the last complete one. Nothing here is approved.",
    ]
    for passage in takes["passages"]:
        lines += [
            "",
            "-" * 72,
            f"PASSAGE {passage['number']}",
            f"Script: {passage['script']}",
            "",
        ]
        if not passage["takes"]:
            lines.append("  NO TAKE FOUND for this passage.")
        for take in passage["takes"]:
            if take["complete"]:
                kind = "complete"
            else:
                kind = (
                    f"partial ({take['scriptWordsCovered']} of "
                    f"{take['scriptWords']} script words)"
                )
            mark = ""
            if take["id"] in passage["suggestedTakes"]:
                mark = (
                    "  <- LAST COMPLETE TAKE, but see the note below"
                    if passage["choiceNeeded"]
                    else "  <- SUGGESTED"
                )
            lines.append(f"  Take {take['number']}, {kind}{mark}")
            lines.append(f"    {_times(take)}")
            lines.append(f"    Said: {take['said']}")
            if take["couldAlsoBePassages"]:
                others = ", ".join(str(n) for n in take["couldAlsoBePassages"])
                lines.append(f"    Matches passage {others} equally well")
            if take["unplacedWords"]:
                lines.append(f"    {take['unplacedWords']} words not placed in time")
            if take["complete"]:
                lines += [
                    f"    Differs: {text}"
                    for text in _difference_lines(take["differences"])
                ]
        numbers = {t["id"]: t["number"] for t in passage["takes"]}
        if len(passage["suggestedTakes"]) > 1:
            joined = ", ".join(str(numbers[i]) for i in passage["suggestedTakes"])
            lines.append(
                f"  Takes {joined} are one continuous read; together complete."
            )
        if passage["takes"] and not passage["suggestedTakes"]:
            lines.append(
                "  No take is suggested: a complete take here is ambiguous or "
                "badly timed."
                if any(take["complete"] for take in passage["takes"])
                else "  No complete take, so nothing is suggested."
            )
            if passage["pieces"]:
                parts = [
                    " + ".join(f"take {numbers[i]}" for i in piece)
                    for piece in passage["pieces"]
                ]
                lines.append(f"  Pieces that could be joined: {'; '.join(parts)}")
            if passage["missingScriptWords"]:
                lines.append("  Never said: " + " ".join(passage["missingScriptWords"]))
        for note in passage["notes"]:
            lines.append(
                f'  Note: the presenter said "{note["said"]}". {note["meaning"]}'
            )
    lines += ["", "-" * 72, "OFF-SCRIPT (said, but matches no passage)", ""]
    if not takes["offScript"]:
        lines.append("  None.")
    for item in takes["offScript"]:
        lines.append(f"  {_times(item)}")
        lines.append(f"    Said: {item['said']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Command


def _dictionary_path(config: EngineConfig) -> Path:
    home = config.mfa_home or Path.home() / ".local/share/vera/word-timing-v2"
    root = Path(config.mfa_env.get("MFA_ROOT_DIR", home / "cache/mfa")).expanduser()
    return root / "pretrained_models/dictionary/english_us_arpa.dict"


def sync_line(sync: SyncResult, fps: list[int]) -> str:
    frames = sync.offset_s * fps[0] / fps[1]
    order = "before" if sync.offset_s >= 0 else "after"
    return (
        f"Sync: the separate audio starts {abs(sync.offset_s):.3f} seconds "
        f"({abs(frames):.1f} frames) {order} the video; "
        f"{len(sync.windows)} check points agree within "
        f"{sync.spread_s * 1000:.0f} ms."
    )


def sync_only(video: Path, separate_audio: Path) -> SyncResult:
    """Line up the separate audio and print the offset; no transcription."""
    _, fps = probe_video(video)
    sync = find_offset(decode_audio(video), decode_audio(separate_audio), RATE)
    print(sync_line(sync, fps))
    return sync


def find_takes(
    video: Path, script: Path, separate_audio: Path | None, out: Path
) -> Json:
    started = time.monotonic()
    config = EngineConfig.from_env()
    dictionary_path = _dictionary_path(config)
    if not dictionary_path.is_file():
        raise TakesError(
            "The aligner's pronunciation dictionary was not found. "
            "Set the VERA engine settings (see docs/presenter-takes.md)."
        )
    dictionary_text = dictionary_path.read_text(encoding="utf-8")
    script_text = read_script(script)
    passages = script_passages(script_text, load_dictionary_words(dictionary_text))
    duration_s, fps = probe_video(video)
    sound = decode_audio(video)
    sync: SyncResult | None = None
    uncovered: list[list[float]] = []
    if separate_audio is not None:
        separate = decode_audio(separate_audio)
        sync = find_offset(sound, separate, RATE)
        sound, uncovered = shift_to_video(separate, sync.offset_s, sound)
        print(sync_line(sync, fps), flush=True)
    duration_s = min(duration_s, len(sound) / RATE)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "sound-16k.wav"
    write_wav(wav, sound)
    audio = AudioRef(wav, file_hash(wav), RATE, len(sound))
    stages = script_to_timeline(
        audio,
        ParakeetRecognizer(config),
        config,
        script_text=script_text,
        dictionary_text=dictionary_text,
        policy=ProjectPolicy(),
        guides_out=work / "guides.dict",
    )
    for name, artifact in (
        ("recognition", stages.recognition),
        ("reconciliation", stages.reconciliation),
        ("alignment", stages.alignment),
    ):
        (work / f"{name}.json").write_text(json.dumps(artifact, indent=1))
    words = timed_words(stages.recognition, stages.alignment)
    report = refine(
        discover(take_packet(words, stages.alignment, passages, duration_s, fps))
    )
    body = build_takes(
        report,
        words,
        stages.recognition,
        stages.alignment,
        passages,
        quiet_intervals(sound, duration_s),
        duration_s,
        fps,
    )
    takes = {
        "schemaVersion": "presenter-takes/1",
        "video": {"file": video.name, "durationS": duration_s, "fps": fps},
        "script": {"file": script.name},
        "sync": {
            "file": separate_audio.name,
            "offsetS": round(sync.offset_s, 4),
            "offsetFrames": round(sync.offset_s * fps[0] / fps[1], 2),
            "spreadMs": round(sync.spread_s * 1000, 1),
            "checkPoints": len(sync.windows),
            "cameraSoundUsed": [[round(a, 2), round(b, 2)] for a, b in uncovered],
        }
        if sync and separate_audio
        else None,
        "approved": False,
        **body,
        "secondsTaken": round(time.monotonic() - started, 1),
    }
    (out / "takes.json").write_text(json.dumps(takes, indent=1, ensure_ascii=False))
    (out / "report.txt").write_text(render_report(takes), encoding="utf-8")
    return takes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="presenter_takes",
        description="List every take in a presenter recording against its script.",
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--script", type=Path)
    parser.add_argument("--audio", type=Path, help="separately recorded sound")
    parser.add_argument("--out", type=Path, help="output folder")
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="only line up --audio with the video and print the offset",
    )
    args = parser.parse_args(argv)
    if args.sync_only and args.audio is None:
        parser.error("--sync-only needs --audio")
    if not args.sync_only and (args.script is None or args.out is None):
        parser.error("--script and --out are required")
    started = time.monotonic()
    try:
        if args.sync_only:
            sync_only(args.video, args.audio)
            print(f"Time taken: {time.monotonic() - started:.0f} seconds")
            return 0
        takes = find_takes(args.video, args.script, args.audio, args.out)
    except (TakesError, SyncRefused) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    except PortRefusal as error:
        print(f"Stopped ({error.port}, {error.code}): {error}", file=sys.stderr)
        return 3
    found = sum(len(p["takes"]) for p in takes["passages"])
    print(
        f"{found} takes across {len(takes['passages'])} passages, "
        f"{len(takes['offScript'])} off-script. Report: {args.out / 'report.txt'}"
    )
    print(f"Time taken: {takes['secondsTaken']:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
