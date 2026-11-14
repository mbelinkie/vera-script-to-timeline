"""Build one full-size, gradeable Resolve source for a presenter recording.

The recording and its cleaned audio go into a compound clip at the
recording's own size. The edit is cut from that compound, so a grade made
inside it reaches every piece. See docs/presenter-source.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

EDIT_SIZE = (1920, 1080)
UHD = (3840, 2160)
AUDIO_RATE = 48_000
# Resolve's own names for the frame rates it accepts as a project setting.
RESOLVE_RATES = {
    Fraction(24000, 1001): "23.976",
    Fraction(24): "24",
    Fraction(25): "25",
    Fraction(30000, 1001): "29.97",
    Fraction(30): "30",
    Fraction(50): "50",
    Fraction(60000, 1001): "59.94",
    Fraction(60): "60",
}


class SourceError(ValueError):
    """The source could not be built or did not read back as built."""


@dataclass(frozen=True)
class Recording:
    video: Path
    audio: Path
    width: int
    height: int
    rate: Fraction
    frames: int

    @property
    def stem(self) -> str:
        return self.video.stem


@dataclass(frozen=True)
class Names:
    folder: str
    grade_timeline: str
    source: str
    sample: str

    @classmethod
    def of(cls, stem: str) -> Names:
        return cls(
            folder=f"VERA presenter {stem}",
            grade_timeline=f"{stem} GRADE HERE",
            source=f"{stem} SOURCE",
            sample=f"{stem} FRAMING SAMPLE",
        )


@dataclass(frozen=True)
class Piece:
    """Frames [start, end) of the source, placed at an offset in the edit."""

    start: int
    end: int
    offset: int
    framing: str  # "tight" or "wide"


@dataclass(frozen=True)
class Built:
    project: str
    names: Names
    recording: Recording
    edit_size: tuple[int, int]
    tight_zoom: float
    pieces: tuple[Piece, ...]


def _ffprobe(path: Path, stream: str, entries: str) -> dict[str, Any]:
    try:
        raw = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                stream,
                "-show_entries",
                f"stream={entries}",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            check=True,
        ).stdout
        found: dict[str, Any] = json.loads(raw)["streams"][0]
        return found
    except (OSError, subprocess.CalledProcessError, ValueError, LookupError) as error:
        raise SourceError(f"Cannot read {path.name}.") from error


def check_lengths(frames: int, rate: Fraction, audio_samples: int) -> None:
    """The cleaned audio must be the video's length, to within one frame."""
    if abs(Fraction(audio_samples, AUDIO_RATE) - frames / rate) > 1 / rate:
        raise SourceError(
            "The cleaned audio is not the same length as the video. "
            "Make it again from this video (docs/presenter-audio.md)."
        )


def probe(video: Path, audio: Path) -> Recording:
    picture = _ffprobe(video, "v:0", "width,height,r_frame_rate,nb_frames")
    sound = _ffprobe(audio, "a:0", "sample_rate,channels,duration_ts")
    try:
        rate = Fraction(picture["r_frame_rate"])
        recording = Recording(
            video=video.resolve(),
            audio=audio.resolve(),
            width=int(picture["width"]),
            height=int(picture["height"]),
            rate=rate,
            frames=int(picture["nb_frames"]),
        )
        sample_rate, channels = int(sound["sample_rate"]), int(sound["channels"])
        samples = int(sound["duration_ts"])
    except (KeyError, ValueError, ZeroDivisionError) as error:
        raise SourceError("Cannot read the recording's size or length.") from error
    if rate not in RESOLVE_RATES or recording.frames <= 0:
        raise SourceError(f"Resolve has no project setting for {float(rate):.3f} fps.")
    if sample_rate != AUDIO_RATE or channels != 1:
        raise SourceError(
            "The audio must be the cleaned 48 kHz mono file (docs/presenter-audio.md)."
        )
    check_lengths(recording.frames, rate, samples)
    return recording


def tight_zoom(source: tuple[int, int], edit: tuple[int, int]) -> float:
    """Zoom that shows a fitted source pixel for pixel; 1.0 if it is no larger."""
    return max(1.0, source[0] / edit[0], source[1] / edit[1])


def _must(ok: Any, what: str) -> None:
    if not ok:
        raise SourceError(f"Resolve refused: {what}.")


def _timelines(project: Any) -> dict[str, Any]:
    found = {}
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        found[timeline.GetName()] = timeline
    return found


def _items(timeline: Any, kind: str) -> list[Any]:
    return list(timeline.GetItemListInTrack(kind, 1) or [])


def _append(
    pool: Any, clip: Any, start: int, end: int, record: int, **more: int
) -> Any:
    placed = pool.AppendToTimeline(
        [
            {
                "mediaPoolItem": clip,
                "startFrame": start,
                "endFrame": end,
                "trackIndex": 1,
                "recordFrame": record,
                **more,
            }
        ]
    )
    _must(placed, "placing a clip")
    return placed


def _open_project(resolve: Any, recording: Recording, name: str, existing: bool) -> Any:
    manager = resolve.GetProjectManager()
    listed = list(manager.GetProjectListInCurrentFolder() or [])
    rate = RESOLVE_RATES[recording.rate]
    if not existing:
        if name in listed:
            raise SourceError(f'A project named "{name}" already exists.')
        project = manager.CreateProject(name)
        _must(project, "creating the project")
        _must(project.SetSetting("timelineFrameRate", rate), "the frame rate")
        _must(
            project.SetSetting("timelineResolutionWidth", str(EDIT_SIZE[0]))
            and project.SetSetting("timelineResolutionHeight", str(EDIT_SIZE[1])),
            "the edit size",
        )
        return project
    project = manager.GetCurrentProject()
    if project is None or project.GetName() != name:
        raise SourceError(f'Open the project "{name}" in Resolve first.')
    if Fraction(str(project.GetSetting("timelineFrameRate"))) != Fraction(rate):
        raise SourceError(
            f"The project is not {rate} fps like the recording; "
            "Resolve would have to retime it."
        )
    return project


def _edit_size(project: Any) -> tuple[int, int]:
    if project.GetSetting("timelineInputResMismatchBehavior") != "scaleToFit":
        raise SourceError(
            "Project Settings > Image Scaling > Mismatched resolution files must be "
            '"Scale entire image to fit" for wide framing to show the whole frame.'
        )
    return (
        int(project.GetSetting("timelineResolutionWidth")),
        int(project.GetSetting("timelineResolutionHeight")),
    )


def _make_source(project: Any, recording: Recording, names: Names) -> None:
    pool = project.GetMediaPool()
    taken = _timelines(project)
    root = pool.GetRootFolder()
    if (
        names.grade_timeline in taken
        or names.sample in taken
        or any(folder.GetName() == names.folder for folder in root.GetSubFolderList())
    ):
        raise SourceError(f'This project already has a source for "{recording.stem}".')
    folder = pool.AddSubFolder(root, names.folder)
    _must(folder and pool.SetCurrentFolder(folder), "making the media folder")
    clips = pool.ImportMedia([str(recording.video), str(recording.audio)])
    _must(clips and len(clips) == 2, "importing the recording")
    video, audio = clips
    size = f"{recording.width}x{recording.height}"
    if video.GetClipProperty("Resolution") != size or video.GetClipProperty(
        "Frames"
    ) != str(recording.frames):
        raise SourceError("Resolve reads the video's size or length differently.")

    timeline = pool.CreateEmptyTimeline(names.grade_timeline)
    _must(timeline, "creating the source timeline")
    _must(
        timeline.SetSetting("useCustomSettings", "1")
        and timeline.SetSetting("timelineResolutionWidth", str(recording.width))
        and timeline.SetSetting("timelineResolutionHeight", str(recording.height)),
        "the source size",
    )
    # A new timeline's A1 is stereo; the cleaned audio is mono.
    _must(
        timeline.AddTrack("audio", "mono") and timeline.DeleteTrack("audio", 1),
        "making a mono audio track",
    )
    start = timeline.GetStartFrame()
    picture = _append(pool, video, 0, recording.frames, start, mediaType=1)
    sound = _append(pool, audio, 0, recording.frames, start, mediaType=2)
    for item in (*picture, *sound):
        if item.GetStart(False) != start or item.GetDuration(False) != recording.frames:
            raise SourceError("Picture and cleaned audio did not land in sync.")
    # Resolve 21.1.1 returns nothing here for picture plus sound even when the
    # compound was made, so the result is read back by check_source instead.
    timeline.CreateCompoundClip(
        [picture[0], sound[0]], {"name": names.source, "startTimecode": "00:00:00:00"}
    )


def check_source(project: Any, recording: Recording, names: Names) -> Any:
    """Read the source back; return its media pool compound clip."""
    timeline = _timelines(project).get(names.grade_timeline)
    if timeline is None:
        raise SourceError(f'Timeline "{names.grade_timeline}" is missing.')
    size = f"{recording.width}x{recording.height}"
    picture, sound = _items(timeline, "video"), _items(timeline, "audio")
    ok = (
        timeline.GetSetting("timelineResolutionWidth") == str(recording.width)
        and timeline.GetSetting("timelineResolutionHeight") == str(recording.height)
        and timeline.GetTrackSubType("audio", 1) == "mono"
        and len(picture) == 1
        and len(sound) == 1
    )
    compound = picture[0].GetMediaPoolItem() if ok else None
    for item in (*picture, *sound) if ok else ():
        clip = item.GetMediaPoolItem()
        ok = ok and (
            clip is not None
            and clip.GetName() == names.source
            and clip.GetClipProperty("Type") == "Compound"
            and clip.GetClipProperty("Resolution") == size
            and clip.GetClipProperty("Frames") == str(recording.frames)
            and item.GetStart(False) == timeline.GetStartFrame()
            and item.GetDuration(False) == recording.frames
        )
    if not ok or compound is None:
        raise SourceError(
            f'"{names.source}" does not hold the whole picture and cleaned audio '
            "in sync at the recording's size."
        )
    return compound


def place_piece(
    project: Any, timeline: Any, compound: Any, piece: Piece, zoom: float
) -> None:
    """Cut one piece of the source into an edit timeline, framed tight or wide."""
    _must(project.SetCurrentTimeline(timeline), "selecting the edit timeline")
    placed = _append(
        project.GetMediaPool(),
        compound,
        piece.start,
        piece.end,
        timeline.GetStartFrame() + piece.offset,
    )
    if piece.framing == "tight":
        picture = [item for item in placed if item.GetProperty("ZoomX") is not False]
        picture = picture or list(placed[:1])
        _must(
            picture[0].SetProperty("ZoomX", zoom)
            and picture[0].SetProperty("ZoomY", zoom),
            "the tight framing zoom",
        )


def check_pieces(
    timeline: Any, names: Names, pieces: Sequence[Piece], zoom: float
) -> None:
    start = timeline.GetStartFrame()
    for kind in ("video", "audio"):
        items = _items(timeline, kind)
        if len(items) != len(pieces):
            raise SourceError(f"The edit has the wrong number of {kind} pieces.")
        for item, piece in zip(items, pieces, strict=True):
            clip = item.GetMediaPoolItem()
            # GetSourceStartFrame can be a frame out on nested media; the left
            # offset is exact.
            ok = (
                clip is not None
                and clip.GetName() == names.source
                and item.GetStart(False) - start == piece.offset
                and item.GetDuration(False) == piece.end - piece.start
                and item.GetLeftOffset(False) == piece.start
            )
            if ok and kind == "video":
                want = zoom if piece.framing == "tight" else 1.0
                ok = (
                    item.GetProperty("ZoomX") == want
                    and item.GetProperty("ZoomY") == want
                )
            if not ok:
                raise SourceError(
                    f"A {piece.framing} piece did not read back as placed."
                )


def sample_pieces(recording: Recording) -> tuple[Piece, ...]:
    """One tight and one wide piece from two different places in the recording."""
    length = max(1, min(round(5 * recording.rate), recording.frames // 4))
    first, second = recording.frames // 4, recording.frames // 2
    return (
        Piece(first, first + length, 0, "tight"),
        Piece(second, second + length, length, "wide"),
    )


def _save_reopen(resolve: Any, name: str) -> Any:
    manager = resolve.GetProjectManager()
    _must(manager.SaveProject(), "saving the project")
    _must(manager.CloseProject(manager.GetCurrentProject()), "closing the project")
    project = manager.LoadProject(name)
    _must(project, "reopening the project")
    return project


def build_source(
    resolve: Any,
    recording: Recording,
    *,
    project_name: str,
    existing_project: bool = False,
    sample: bool = False,
) -> Built:
    names = Names.of(recording.stem)
    project = _open_project(resolve, recording, project_name, existing_project)
    edit = _edit_size(project)
    zoom = tight_zoom((recording.width, recording.height), edit)
    _make_source(project, recording, names)
    compound = check_source(project, recording, names)
    pieces = sample_pieces(recording) if sample else ()
    if sample:
        timeline = project.GetMediaPool().CreateEmptyTimeline(names.sample)
        _must(timeline, "creating the framing sample timeline")
        for piece in pieces:
            place_piece(project, timeline, compound, piece, zoom)

    project = _save_reopen(resolve, project_name)
    check_source(project, recording, names)
    if sample:
        reopened = _timelines(project).get(names.sample)
        if reopened is None:
            raise SourceError(f'Timeline "{names.sample}" is missing after reopen.')
        check_pieces(reopened, names, pieces, zoom)
    project.SetCurrentTimeline(_timelines(project)[names.grade_timeline])
    return Built(project_name, names, recording, edit, zoom, pieces)


def report(built: Built) -> str:
    recording, names = built.recording, built.names
    size = f"{recording.width}x{recording.height}"
    lines = [
        f'Built "{names.source}" ({size}, {recording.frames} frames) in project '
        f'"{built.project}".',
        "Checked after save, close and reopen: the picture and the cleaned audio "
        "start together and are the same length.",
    ]
    if recording.width < UHD[0] or recording.height < UHD[1]:
        lines.append(
            f"This recording is {size}, not 4K, so the source is built at {size}."
        )
    if built.tight_zoom == 1.0:
        lines.append(
            "It is no larger than the edit, so tight and wide are the same picture."
        )
    else:
        lines.append(
            f"Tight framing is zoom {built.tight_zoom:g} (pixel for pixel); "
            "wide is zoom 1 (the whole frame)."
        )
    lines.append(
        f'To grade: open timeline "{names.grade_timeline}", right-click the clip, '
        "choose Open in Timeline, and grade the video there. Every piece cut from "
        f'"{names.source}" follows.'
    )
    if built.pieces:
        lines.append(
            f'Timeline "{names.sample}" holds a tight and a wide piece to try it on.'
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--audio", type=Path, required=True, help="cleaned WAV (#92)")
    parser.add_argument("--project", help="name for the new Resolve project")
    parser.add_argument(
        "--existing-project", help="add to this project, already open in Resolve"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="also cut one tight and one wide piece into a sample timeline",
    )
    args = parser.parse_args(argv)
    if args.project and args.existing_project:
        parser.error("use --project or --existing-project, not both")
    # Imported here so probing and tests need no Resolve installation.
    from .build_jobs import BuildJobError, NeedsAction, UncertainResult
    from .build_timeline_once import _external_resolve, exclusive_resolve_build

    try:
        recording = probe(args.video, args.audio)
        name = (
            args.existing_project
            or args.project
            or f"{recording.stem} presenter source"
        )
        with exclusive_resolve_build():
            built = build_source(
                _external_resolve(),
                recording,
                project_name=name,
                existing_project=args.existing_project is not None,
                sample=args.sample,
            )
    except (SourceError, BuildJobError, NeedsAction, UncertainResult) as error:
        parser.exit(1, f"Presenter source: {error}\n")
    print(report(built))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
