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
off-script, and so is speech the rules paired with a passage mostly through
substituted words (`_really_matches`). A word the aligner could not place
has no time, and a take whose edge word has no time has no cut. A suggestion
is never an approval.
"""

from __future__ import annotations

import argparse
import difflib
import io
import itertools
import json
import re
import subprocess
import sys
import time
import wave
import zipfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
from vera_word_timing.adapters.local_engines import EngineConfig, ParakeetRecognizer
from vera_word_timing.artifacts import AudioRef, file_hash
from vera_word_timing.ports import PortRefusal, ProjectPolicy
from vera_word_timing.profiles import script_to_timeline
from vera_word_timing.script_reconcile import (
    load_dictionary_words,
    parse_prompter,
    similar,
)

from experiments.issue45.take_rules import differences, refine
from experiments.issue53.boundaries import propose_quiet_cuts
from experiments.issue53.review_rules import sentence_spans
from experiments.issue53.takes import discover, tokens
from vera_timeline_agent.presenter_sync import (
    Samples,
    SyncRefused,
    SyncResult,
    find_offset,
)

Json = dict[str, Any]
RATE = 16000  # the engines' sample rate; all audio work happens at it
MARKER = re.compile(r"\((on|off)\)", re.IGNORECASE)
TOLERANCE = 0.75  # share of a stretch's script words a read must say as written
EDGE_WORDS = 2  # ... and fewer than this many words may be missing at either end
MAX_STRAY_WORDS = 2  # unmatched words allowed inside one continuous read
MAX_PAUSE_S = 1.4  # the #53 pause that separates two reads
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


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_script(data: bytes) -> str:
    """A Word export of the script document, as prompter text.

    The script is the first table: each table row is a script row and its
    first column is what the presenter says. Bold is on camera, plain is
    covered by footage. When the document has no table, its paragraphs are
    the rows. When nothing is bold, no camera marks are written: the document
    does not say.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            body = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise TakesError("The script is not a readable Word document.") from error
    table = body.find(f".//{_W}tbl")
    if table is not None:
        cells = [row.find(f"{_W}tc") for row in table.findall(f"{_W}tr")]
        blocks = [list(c.iter(f"{_W}r")) for c in cells if c is not None]
    else:
        blocks = [list(p.iter(f"{_W}r")) for p in body.iter(f"{_W}p")]
    rows: list[list[tuple[bool, str]]] = []
    for runs in blocks:
        row: list[tuple[bool, str]] = []
        for run in runs:
            text = "".join(
                node.text or "" if node.tag == f"{_W}t" else " "
                for node in run
                if node.tag in (f"{_W}t", f"{_W}tab", f"{_W}br", f"{_W}cr")
            )
            bold = run.find(f"{_W}rPr/{_W}b")
            is_bold = bold is not None and bold.get(f"{_W}val") not in ("0", "false")
            if not text.strip():
                if row:
                    row[-1] = (row[-1][0], row[-1][1] + text)
            elif row and row[-1][0] == is_bold:
                row[-1] = (is_bold, row[-1][1] + text)
            else:
                row.append((is_bold, text))
        if row:
            rows.append(row)
    marked = any(bold for row in rows for bold, _ in row)
    lines = []
    for row in rows:
        parts = [
            (f"({'on' if bold else 'off'}) " if marked else "") + " ".join(text.split())
            for bold, text in row
        ]
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def read_script(path: Path) -> str:
    """The script as prompter text: one row per line, `(on)` / `(off)` marks."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise TakesError(f"The script could not be read: {path.name}") from error
    if raw.startswith(b"PK"):
        return docx_to_script(raw)
    if raw.lstrip().startswith(b"{\\rtf"):
        return rtf_to_text(raw.decode("ascii", "replace"))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TakesError("The script must be Word, RTF or UTF-8 text.") from error


@dataclass(frozen=True)
class Passage:
    """One script row: what a presenter take is matched against."""

    id: str
    row: int
    camera: str  # "on", "off", "mixed" or "unknown" over the whole row
    cameras: tuple[str, ...]  # per script word: "on", "off" or "unknown"
    script: str  # as written, with its (on) / (off) marks, for people
    text: str  # spoken words with sentence stops, for the take rules


def _spoken(text: str, dictionary: set[str]) -> str:
    pieces: list[str] = []
    for word in parse_prompter(text, dictionary).words:
        if word["sentenceStart"] and pieces:
            pieces[-1] += "."
        pieces.append(" ".join(word["spoken"]))
    return " ".join(pieces) + "." if pieces else ""


def script_passages(script_text: str, dictionary: set[str]) -> list[Passage]:
    """The script rows. Each line is a row and each row is one passage.

    `(on)` and `(off)` inside a row mark what is on camera and what is
    voiceover covered by footage. That is recorded per word. It never splits a
    row: a change of picture is not a cut in the presenter's take.
    """
    passages: list[Passage] = []
    camera = "unknown"
    for line in script_text.splitlines():
        cameras: list[str] = []
        for index, part in enumerate(MARKER.split(line)):
            if index % 2:
                camera = part.lower()
            else:
                cameras += [camera] * len(tokens(_spoken(part, dictionary)))
        text = _spoken(MARKER.sub(" ", line), dictionary)
        count = len(tokens(text))
        if not count:
            continue
        if len(cameras) != count:  # a mark fell inside a word group; do not guess
            cameras = ["unknown"] * count
        states = set(cameras)
        number = len(passages) + 1
        passages.append(
            Passage(
                f"row-{number}",
                number,
                states.pop() if len(states) == 1 else "mixed",
                tuple(cameras),
                " ".join(re.sub(r"\[[^\]]*\]", "", line).split()),
                text,
            )
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
        runs_on = [
            side
            for side, near in (
                ("from what comes before", before and start - before[0]["end"] < 0.4),
                ("into what comes next", after and after[0]["start"] - end < 0.4),
            )
            if near
        ]
        out["cutProblem"] = (
            "too close to the start or end of the recording"
            if "source_limit" in reasons
            else f"the presenter runs straight on {' and '.join(runs_on)}"
            if runs_on
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


def _really_matches(candidate: Json) -> bool:
    """Guard against an invented match.

    The take rules can attach a long stretch of unrelated speech to a passage
    as a "modified read" made almost entirely of substituted words. Speech
    counts as an attempt at a passage only when more of its paired words are
    the script's words than are different words. Otherwise it is off-script.
    """
    ops = [op["op"] for op in candidate["diff"]]
    return ops.count("equal") > ops.count("substitute")


def _deliveries(takes: list[Json], words: list[Json]) -> list[Json]:
    """Takes of one passage, with a read that was split in two put back together.

    The take rules split a continuous read at a word they could not match
    ("kinda" for "kind of"). Two neighbouring takes are one delivery when at
    most MAX_STRAY_WORDS lie between them, the pause is short, and the second
    carries on in the script where the first stopped.
    """
    out: list[Json] = []
    for take in takes:
        start, end = take["_range"]
        script = {e for e, _ in take["_pairs"]}
        if out and script:
            last = out[-1]
            before = words[last["range"][1] - 1]["end"]
            after = words[start]["start"]
            reached = max((e for e, _ in last["pairs"]), default=-1)
            if (
                0 <= start - last["range"][1] <= MAX_STRAY_WORDS
                and before is not None
                and after is not None
                and after - before <= MAX_PAUSE_S
                and min(script) > reached
            ):
                last["range"][1] = end
                last["pairs"] += take["_pairs"]
                last["takes"].append(take["id"])
                continue
        out.append(
            {"takes": [take["id"]], "range": [start, end], "pairs": [*take["_pairs"]]}
        )
    return out


def _read(
    delivery: Json, a: int, b: int, expected: list[str], words: list[Json]
) -> Json | None:
    """How a delivery reads script words [a, b), or None if it does not.

    A read may differ from the script by a few words: at least TOLERANCE of
    the stretch must be said as written, and no more than one word may be
    missing or changed at either end. The spoken range covers just this
    stretch, so a countdown or a stumble before it is left out.
    """
    inside = [(e, s) for e, s in delivery["pairs"] if a <= e < b]
    if len(inside) < TOLERANCE * (b - a):
        return None
    lead, trail = inside[0][0] - a, b - 1 - inside[-1][0]
    if lead >= EDGE_WORDS or trail >= EDGE_WORDS:
        return None
    earlier = [s for e, s in delivery["pairs"] if e < a]
    later = [s for e, s in delivery["pairs"] if e >= b]
    # A changed first or last word is still part of the read.
    start = max(
        inside[0][1] - lead, earlier[-1] + 1 if earlier else delivery["range"][0]
    )
    end = min(inside[-1][1] + 1 + trail, later[0] if later else delivery["range"][1])
    spoken = [w["token"] for w in words[start:end]]
    changes: Json = {"moved": [], "substituted": [], "added": [], "omitted": []}
    matcher = difflib.SequenceMatcher(None, expected[a:b], spoken, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        script, said = expected[a + i1 : a + i2], spoken[j1:j2]
        if op == "replace" and len(script) == len(said):
            changes["substituted"] += [
                {"script": x, "said": y} for x, y in zip(script, said, strict=True)
            ]
        elif op != "equal":
            changes["omitted"] += script
            changes["added"] += said
    return {
        "takes": delivery["takes"],
        "scriptWords": [a, b],
        "spoken": [start, end],
        "exact": lead == 0 and trail == 0,
        "differences": changes,
    }


def _segments(passage: Passage, count: int) -> list[tuple[int, int]]:
    """Where a row may be joined from different reads: at sentence ends and
    where the picture changes between presenter and footage."""
    starts = {a for a, _ in sentence_spans(passage.text, tokens)} | {
        i for i in range(1, count) if passage.cameras[i] != passage.cameras[i - 1]
    }
    points = [*sorted(starts | {0}), count]
    return list(itertools.pairwise(points))


def _voiceover(
    read: Json, delivery: Json, passage: Passage, words: list[Json]
) -> list[list[float]]:
    """The video-time ranges of a read where the script says voiceover."""
    script_of = {s: e for e, s in delivery["pairs"]}
    start, end = read["spoken"]
    a, b = read["scriptWords"]
    state = passage.cameras[a]
    marks: list[tuple[float, str]] = []
    for k in range(start, end):
        if k in script_of and a <= script_of[k] < b:
            state = passage.cameras[script_of[k]]
        if words[k]["start"] is not None:
            marks.append((words[k]["start"], state))
    if not marks or read["speechEndS"] is None:
        return []
    cut = read["cut"]
    first = cut["startS"] if cut else marks[0][0]
    last = cut["endS"] if cut else read["speechEndS"]
    marks[0] = (first, marks[0][1])
    ranges: list[list[float]] = []
    ends = [*(m[0] for m in marks[1:]), last]
    for (begin, state), finish in zip(marks, ends, strict=True):
        if state != "off" or finish <= begin:
            continue
        if ranges and abs(ranges[-1][1] - begin) < 1e-6:
            ranges[-1][1] = finish
        else:
            ranges.append([begin, finish])
    return [[round(x, 3), round(y, 3)] for x, y in ranges]


def _join(passage: Passage, at: int) -> str:
    """Whether a join before script word `at` would show in the picture."""
    sides = {passage.cameras[at - 1], passage.cameras[at]}
    if "off" in sides:
        return "hidden"  # footage is on screen on at least one side
    return "check" if "unknown" in sides else "visible"


def _best(reads: list[Json]) -> Json:
    """The last read that reaches both ends and can be cut cleanly."""
    pool = [r for r in reads if r["exact"]] or reads
    return ([r for r in pool if r["cut"]] or pool)[-1]


def build_takes(
    report: Json,
    timed: list[Json],
    recognition: Json,
    alignment: Json,
    passages: list[Passage],
    quiet: list[list[float]],
    duration_s: float,
    fps: list[int],
    last_take: bool = False,
) -> Json:
    """The takes file body: every take, and the suggested coverage per passage.

    `last_take` is the choice a project makes once it allows jump cuts: where
    a row has to be joined on camera, switch to the latest read of each
    stretch instead of staying in the take in hand. Either way the reads not
    chosen are kept as alternates.

    The takes themselves come from the accepted #53 rules. The suggestion for
    a passage is the best read of the whole of it; failing that, the best read
    of each sentence (`_read`, `_best`).
    """
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
    off_script: list[Json] = []

    def located(spoken: list[int]) -> Json:
        return {
            **_cut(words, spoken, quiet, duration_s, fps),
            "said": _said(words, spoken, units, recognition),
            "unplacedWords": sum(w["start"] is None for w in words[slice(*spoken)]),
        }

    for c in report["candidates"]:
        if "members" in c:  # a delivery run made of takes already listed
            continue
        if not c["row"] or not _really_matches(c):
            off_script.append(located(c["word_range"]))
            continue
        expected = row_tokens[c["row"]]
        takes = by_passage[c["row"]]
        start = c["word_range"][0]
        spoken = [w["token"] for w in words[slice(*c["word_range"])]]
        blocks = difflib.SequenceMatcher(
            None, expected, spoken, autojunk=False
        ).get_matching_blocks()
        takes.append(
            {
                "id": f"{c['row']}-take-{len(takes) + 1}",
                "number": len(takes) + 1,
                "complete": bool(c["complete"]),
                "wholePassage": False,
                "alternate": False,
                "scriptWordsCovered": sum(block.size for block in blocks),
                "scriptWords": len(expected),
                "couldAlsoBePassages": [
                    number_of[r] for r in c["row_options"] if r != c["row"]
                ],
                **located(c["word_range"]),
                "differences": differences([c], expected, words, None),
                "_range": list(c["word_range"]),
                "_pairs": [
                    (block.a + k, start + block.b + k)
                    for block in blocks
                    for k in range(block.size)
                ],
            }
        )
    out_passages = []
    edit: list[Json] = []
    for number, passage in enumerate(passages, 1):
        takes = by_passage[passage.id]
        expected = row_tokens[passage.id]
        deliveries = _deliveries(takes, words)

        def reads(a: int, b: int) -> list[Json]:
            out = []
            for delivery in deliveries:  # noqa: B023
                read = _read(delivery, a, b, expected, words)  # noqa: B023
                if read:
                    read.update(located(read["spoken"]))
                    read["voiceover"] = _voiceover(read, delivery, passage, words)  # noqa: B023
                    out.append(read)
            return out

        suggested: Json | None = None
        alternates: list[Json] = []
        pieces: list[Json] = []
        gaps: list[Json] = []
        whole = reads(0, len(expected))
        if whole:
            suggested = _best(whole)
            alternates = [r for r in whole if r is not suggested]
            for read in whole:
                for take in takes:
                    if take["id"] in read["takes"]:
                        take["wholePassage"] = True
                        take["alternate"] = read is not suggested
        elif takes:
            said_somewhere = {e for take in takes for e, _ in take["_pairs"]}
            for a, b in _segments(passage, len(expected)):
                found = reads(a, b)
                if not found:
                    closest = max(
                        takes, key=lambda t: sum(a <= e < b for e, _ in t["_pairs"])
                    )
                    gaps.append(
                        {
                            "scriptWords": [a, b],
                            "script": " ".join(expected[a:b]),
                            "notCovered": [
                                expected[e]
                                for e in range(a, b)
                                if e not in said_somewhere
                            ],
                            "closestTake": closest["id"],
                        }
                    )
                    continue
                # Inside a row the clean cut is judged once the clip is whole.
                pick = ([r for r in found if r["exact"]] or found)[-1]
                last = pieces[-1] if pieces else None
                if last and last["scriptWords"][1] == a:
                    # Never cut where it would show if the read in hand carries on.
                    same = [r for r in found if r["takes"] == last["takes"]]
                    join = _join(passage, a)
                    stay = join == "check" or (join == "visible" and not last_take)
                    if same and stay:
                        pick = same[0]
                others = [t for r in found if r is not pick for t in r["takes"]]
                if (
                    last
                    and last["takes"] == pick["takes"]
                    and last["scriptWords"][1] == a
                ):
                    # The same read carries on: keep it one clip.
                    joined = reads(last["scriptWords"][0], b)
                    joined = [r for r in joined if r["takes"] == pick["takes"]]
                    if joined:
                        pieces[-1] = {
                            **joined[0],
                            "join": last["join"],
                            "alternates": [
                                t for t in last["alternates"] if t in others
                            ],
                        }
                        continue
                pieces.append(
                    {
                        **pick,
                        "join": _join(passage, a) if a and pieces else None,
                        "alternates": others,
                    }
                )
        for index, piece in enumerate(pieces):
            if piece["cut"]:
                continue
            # A clip that cannot be cut cleanly gives way to another read of
            # the same words that can.
            cleaner = [
                r
                for r in reads(*piece["scriptWords"])
                if r["cut"] and r["takes"] != piece["takes"]
            ]
            if cleaner:
                pieces[index] = {
                    **cleaner[-1],
                    "join": piece["join"],
                    "alternates": [
                        *piece["takes"],
                        *(
                            t
                            for t in piece["alternates"]
                            if t not in cleaner[-1]["takes"]
                        ),
                    ],
                }
        # Every other read of part of a clip stays on record, so whoever
        # reviews the suggestion can overrule it stretch by stretch.
        for clip in [suggested, *pieces] if suggested else pieces:
            start, end = clip["scriptWords"]
            clip["otherReads"] = [
                {"scriptWords": [a, b], "takes": r["takes"]}
                for a, b in _segments(passage, len(expected))
                if start <= a and b <= end and (a, b) != (start, end)
                for r in reads(a, b)
                if r["takes"] != clip["takes"]
            ]
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
                "row": passage.row,
                "camera": passage.camera,
                "script": passage.script,
                "takes": takes,
                "suggested": suggested,
                "suggestedTakes": suggested["takes"] if suggested else [],
                "alternateReads": alternates,
                "choiceNeeded": bool(notes),
                "suggestedCoverage": pieces,
                "gaps": gaps,
                "notes": notes,
            }
        )
        for read in [suggested] if suggested else pieces:
            cut = read["cut"]
            edit.append(
                {
                    "row": passage.row,
                    "takes": read["takes"],
                    "startS": cut["startS"] if cut else read["speechStartS"],
                    "endS": cut["endS"] if cut else read["speechEndS"],
                    "cleanCut": cut is not None,
                    "join": read.get("join"),
                    "voiceover": read["voiceover"],
                    "differences": read["differences"],
                    "checkByEar": read["approximateStart"] or read["approximateEnd"],
                }
            )
        edit += [{"row": passage.row, "gap": gap["script"]} for gap in gaps]
    for takes in by_passage.values():
        for take in takes:
            del take["_range"], take["_pairs"]
    return {
        "rows": out_passages,
        "suggestedEdit": edit,
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
    lines = [
        f'said "{s["said"]}" for "{s["script"]}"'
        + (
            " (sounds alike; may only be spelling)"
            if similar(s["said"], s["script"])
            else ""
        )
        for s in d["substituted"]
    ]
    if d["added"]:
        lines.append("added: " + " ".join(d["added"]))
    if d["omitted"]:
        lines.append("left out: " + " ".join(d["omitted"]))
    if d["moved"]:
        lines.append("moved: " + " ".join(m["word"] for m in d["moved"]))
    return lines


LONG_TAKES, LAST_TAKE = "long-takes", "last-take"
JOIN = {
    None: "",
    "hidden": "(join hidden by footage) ",
    "check": "(CHECK THE JOIN: the script does not say if this is on camera) ",
    "visible": "(JUMP CUT ON CAMERA) ",
}
CAMERA = {
    "on": "on camera",
    "off": "voiceover, covered by footage",
    "mixed": "on camera, with voiceover cutaways",
    "unknown": "the script does not say whether this is on camera",
}


def render_report(takes: Json) -> str:
    video, sync = takes["video"], takes["sync"]
    lines = [
        "PRESENTER TAKES",
        "",
        f"Recording: {video['file']}  ({clock(video['durationS'])}, "
        f"{float(Fraction(*video['fps'])):.2f} frames a second)",
        f"Script:    {takes['script']['file']}  ({len(takes['rows'])} rows)",
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
    if takes.get("allowJumpCuts"):
        choice = (
            "the latest read is used"
            if takes.get("jumpCutChoice") == LAST_TAKE
            else "long takes are preferred"
        )
        lines.append(f"Jump cuts: allowed, so they are not flagged; {choice}")
    counts = takes["words"]
    lines += [
        f"Words:     {counts['heard']} heard: {counts['placed']} placed exactly, "
        f"{counts['recogniserTimed']} placed roughly (the two timing engines "
        f"disagreed), {counts['unplaced']} not placed",
        f"Time taken: {takes['secondsTaken']:.0f} seconds",
        "",
        "Times are minutes:seconds from the start of the video. Each take's times",
        "are cut points in quiet, about ten frames clear of the speech.",
        "A row is one presenter clip whenever a take reads the whole row; a",
        "change between presenter and footage inside it is not a cut. The",
        "suggested take is the last such read that can be cut cleanly, and the",
        "others are alternates. A few changed words are listed as differences.",
        "Only when no take reads the whole row is it built from several clips,",
        "joined where footage hides the join if possible. Nothing is approved.",
    ]
    for passage in takes["rows"]:
        lines += [
            "",
            "-" * 72,
            f"ROW {passage['number']}  ({CAMERA[passage['camera']]})",
            f"Script: {passage['script']}",
            "",
        ]
        numbers = {t["id"]: t["number"] for t in passage["takes"]}
        if not passage["takes"]:
            lines.append("  NOT COVERED: nothing in the recording matches this row.")
        for take in passage["takes"]:
            if take["complete"]:
                kind = "complete"
            elif take["wholePassage"]:
                kind = "complete, with wording changes"
            else:
                kind = (
                    f"partial ({take['scriptWordsCovered']} of "
                    f"{take['scriptWords']} script words)"
                )
            mark = ""
            if take["id"] in passage["suggestedTakes"]:
                mark = "  <- SUGGESTED"
                if passage["choiceNeeded"]:
                    mark += ", but see the note below"
            elif any(take["id"] in p["takes"] for p in passage["suggestedCoverage"]):
                mark = "  <- used in the suggested coverage below"
            elif take["alternate"]:
                mark = "  (alternate)"
            lines.append(f"  Take {take['number']}, {kind}{mark}")
            lines.append(f"    {_times(take)}")
            lines.append(f"    Said: {take['said']}")
            if take["couldAlsoBePassages"]:
                others = ", ".join(str(n) for n in take["couldAlsoBePassages"])
                lines.append(f"    Matches row {others} equally well")
            if take["unplacedWords"]:
                lines.append(f"    {take['unplacedWords']} words not placed in time")
            if take["complete"]:
                lines += [
                    f"    Differs: {text}"
                    for text in _difference_lines(take["differences"])
                ]
        if read := passage["suggested"]:
            which = " + ".join(str(numbers[i]) for i in read["takes"])
            joined = " (one continuous read)" if len(read["takes"]) > 1 else ""
            lines += ["", f"  SUGGESTED: take {which}{joined}", f"    {_times(read)}"]
            if len(read["takes"]) > 1:
                lines.append(f"    Said: {read['said']}")
            lines += [
                f"    Differs: {text}"
                for text in _difference_lines(read["differences"])
            ]
            later = [
                "+".join(str(numbers[i]) for i in other["takes"])
                for other in passage["alternateReads"]
                if numbers[other["takes"][0]] > numbers[read["takes"][-1]]
            ]
            if later:
                lines.append(
                    f"    Take {', '.join(later)} is later, but it changes or drops "
                    "an end word or has no clean cut."
                )
        if passage["suggestedCoverage"] or passage["gaps"]:
            lines += ["", "  No single take covers this row. SUGGESTED CLIPS:"]
            for piece in passage["suggestedCoverage"]:
                a, b = piece["scriptWords"]
                join = piece["join"]
                if join == "visible" and takes.get("allowJumpCuts"):
                    join = None  # the project allows jump cuts: nothing to warn of
                lines.append(
                    f"    {JOIN[join]}Script words {a + 1} to {b}, from take "
                    f"{' + '.join(str(numbers[i]) for i in piece['takes'])}: "
                    f"{_times(piece)}"
                )
                lines.append(f"      Said: {piece['said']}")
                lines += [
                    f"      Differs: {text}"
                    for text in _difference_lines(piece["differences"])
                ]
                if piece["alternates"]:
                    others = ", ".join(str(numbers[i]) for i in piece["alternates"])
                    lines.append(f"      Alternates: take {others}")
                for other in piece.get("otherReads", []):
                    a, b = other["scriptWords"]
                    lines.append(
                        f"      Also read: script words {a + 1} to {b} in take "
                        f"{' + '.join(str(numbers[i]) for i in other['takes'])}"
                    )
            for gap in passage["gaps"]:
                a, b = gap["scriptWords"]
                lines.append(
                    f"    Script words {a + 1} to {b} ({gap['script']}): no take "
                    f"reads this through. Closest is take "
                    f"{numbers[gap['closestTake']]}."
                )
                if gap["notCovered"]:
                    lines.append("      NOT COVERED: " + " ".join(gap["notCovered"]))
        elif passage["takes"] and not passage["suggestedTakes"]:
            lines.append(
                "  Nothing is suggested: the takes here are ambiguous or badly timed."
            )
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
    video: Path,
    script: Path,
    separate_audio: Path | None,
    out: Path,
    allow_jump_cuts: bool = False,
    jump_cut_choice: str = LONG_TAKES,
) -> Json:
    """`allow_jump_cuts` alone changes no cut: jump cuts just stop being flagged.

    With it, `jump_cut_choice` says which read to use across an on-camera
    join: stay in the take in hand (`long-takes`) or the latest (`last-take`).
    """
    last_take = allow_jump_cuts and jump_cut_choice == LAST_TAKE
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
        last_take,
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
        "allowJumpCuts": allow_jump_cuts,
        "jumpCutChoice": jump_cut_choice if allow_jump_cuts else None,
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
    parser.add_argument(
        "--allow-jump-cuts",
        action="store_true",
        help="do not flag joins that show on camera (the edit itself is the same)",
    )
    parser.add_argument(
        "--jump-cut-choice",
        choices=(LONG_TAKES, LAST_TAKE),
        help="with --allow-jump-cuts: stay in the take in hand across an "
        "on-camera join (long-takes, the default) or use the latest read",
    )
    args = parser.parse_args(argv)
    if args.jump_cut_choice and not args.allow_jump_cuts:
        parser.error("--jump-cut-choice needs --allow-jump-cuts")
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
        takes = find_takes(
            args.video,
            args.script,
            args.audio,
            args.out,
            args.allow_jump_cuts,
            args.jump_cut_choice or LONG_TAKES,
        )
    except (TakesError, SyncRefused) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    except PortRefusal as error:
        print(f"Stopped ({error.port}, {error.code}): {error}", file=sys.stderr)
        return 3
    found = sum(len(p["takes"]) for p in takes["rows"])
    print(
        f"{found} takes across {len(takes['rows'])} rows, "
        f"{len(takes['offScript'])} off-script. Report: {args.out / 'report.txt'}"
    )
    print(f"Time taken: {takes['secondsTaken']:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
