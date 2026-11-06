"""One-use public synthetic source -> still matte -> native Studio motion proof.

This is *investigation evidence*, not a shipped general-purpose matte engine.
It writes only a new derived PNG/OTIO and a unique render in the pre-owned,
isolated VERA336-SYN-run5 project. Never imports twice or modifies prior media.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
import zlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.issue336_studio_qualify import render, video_pixels, write_otio
else:
    try:
        from scripts.issue336_studio_qualify import render, video_pixels, write_otio
    except ModuleNotFoundError as error:
        # The installed Mac probe is deliberately copied into one private
        # scratch directory as qualify.py, not installed as a package.
        # Do not mask an import failure *inside* the repository probe.
        if error.name not in {"scripts", "scripts.issue336_studio_qualify"}:
            raise
        from qualify import render, video_pixels, write_otio


def _chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def _source_rgb(
    path: pathlib.Path, expected_size: tuple[int, int] = (1000, 1000)
) -> tuple[int, int, bytes]:
    """Only supports RGB8/filter-none public PNG from our fixture generator."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("source PNG signature does not match")
    pos, encoded = 8, bytearray()
    width = height = 0
    while pos < len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + size]
        checksum = struct.unpack_from(">I", data, pos + 8 + size)[0]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != checksum:
            raise ValueError("source PNG CRC differs")
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", body)
            )
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise ValueError("only public RGB8/no-interlace fixture supported")
        if kind == b"IDAT":
            encoded.extend(body)
        pos += 12 + size
    if (width, height) != expected_size:
        raise ValueError("public synthetic source dimensions differ")
    raw = zlib.decompress(encoded)
    stride = 1 + width * 3
    if len(raw) != stride * height:
        raise ValueError("public source PNG decoded extent differs")
    if any(raw[row * stride] != 0 for row in range(height)):
        raise ValueError("public source PNG has unexpected filter")
    return (
        width,
        height,
        b"".join(raw[row * stride + 1 : (row + 1) * stride] for row in range(height)),
    )


def create_public_matte(source: pathlib.Path, target: pathlib.Path) -> dict[str, Any]:
    """Verified still-only composition, scaled original + black matte.

    Canvas 1600x900, content 450x450 at (575,225). Native motion may move and
    magnify the *precomposed still*, but no motion is baked by this operation.
    """
    if target.exists():
        raise ValueError("matte output exists; refuse overwrite")
    width, height, source_bytes = _source_rgb(source)
    canvas_width, canvas_height = 1600, 900
    image_width = image_height = 450
    left, top = 575, 225
    output = bytearray()
    for y in range(canvas_height):
        row = bytearray(canvas_width * 3)
        if top <= y < top + image_height:
            source_y = (y - top) * height // image_height
            for x in range(left, left + image_width):
                source_x = (x - left) * width // image_width
                i = (source_y * width + source_x) * 3
                row[x * 3 : x * 3 + 3] = source_bytes[i : i + 3]
        output.append(0)
        output.extend(row)
    ihdr = struct.pack(">IIBBBBB", canvas_width, canvas_height, 8, 2, 0, 0, 0)
    target.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(output, 6))
        + _chunk(b"IEND", b"")
    )
    return {
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "derivedSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "canvas": [canvas_width, canvas_height],
        "contentRect": [left, top, image_width, image_height],
        "resampling": "integer nearest-neighbor",
        "backgroundRgb": [0, 0, 0],
        "alpha": "opaque RGB still; native motion remains an independent effect",
    }


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save(path: pathlib.Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--template", type=pathlib.Path)
    parser.add_argument(
        "--phase",
        choices=("prepare", "import", "render", "decode", "finalize"),
        required=True,
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required")
    sys.path.append(
        "/Library/Application Support/Blackmagic Design/"
        "DaVinci Resolve/Developer/Scripting/Modules"
    )
    import DaVinciResolveScript  # type: ignore[import-not-found]

    app = DaVinciResolveScript.scriptapp("Resolve")
    if app is None or app.GetVersionString() != "21.1.1.10":
        raise ValueError("refuse: unqualified native Studio version")
    manager = app.GetProjectManager()
    project = manager.GetCurrentProject()
    root = args.root.resolve()
    if project is None or project.GetName() != "VERA336-SYN-run5":
        raise ValueError("refuse: wrong synthetic project")
    prior = json.loads((root / "evidence.json").read_text())
    old_names = prior["reopened"]["names"]
    old_durations = prior["reopened"]["durations"]
    if len(old_names) != 11 or any(
        prior["cases"][name]["status"] != "decoded" for name in old_names
    ):
        raise ValueError("refuse: prior native cases are incomplete")
    if _sha(root / "square.png") != prior["sourceHashes"]["square"]:
        raise ValueError("refuse: original public source changed")
    render_dir = pathlib.Path.home() / "Movies" / "VERA336-native-proof-run5"
    if not render_dir.is_dir() or not (render_dir / ".write-check").is_file():
        raise ValueError("refuse: independent render destination missing")
    old_paths = [render_dir / (name + ".mov") for name in old_names]
    if any(not path.is_file() for path in old_paths):
        raise ValueError("refuse: previous render output missing")
    old_hashes = {path.name: _sha(path) for path in old_paths}
    if project.IsRenderingInProgress() is not False:
        raise ValueError("refuse: other render active")
    state_path = root / "matte-proof.json"
    name = "square-matte-motion-48"
    matte = root / "square-matte-1600x900.png"

    if args.phase == "prepare":
        if (
            state_path.exists()
            or matte.exists()
            or (render_dir / (name + ".mov")).exists()
        ):
            raise ValueError("refuse: existing matte run; no replay")
        if project.GetTimelineCount() != len(old_names):
            raise ValueError("refuse: baseline project unexpectedly changed")
        if [project.GetTimelineByIndex(i).GetName() for i in range(1, 12)] != old_names:
            raise ValueError("refuse: baseline timeline names changed")
        if args.template is None or not args.template.is_file():
            raise ValueError(
                "refuse: explicit retained public native OTIO template required"
            )
        provenance = create_public_matte(root / "square.png", matte)
        state: dict[str, Any] = {
            "status": "reserved",
            "name": name,
            "project": project.GetName(),
            "sourceToMatte": provenance,
            "originalMoviesSha256": old_hashes,
            "otioTemplateSha256": _sha(args.template),
        }
        _save(state_path, state)
        print("MATTE_PREPARED", provenance["derivedSha256"], flush=True)
        return 0

    if not state_path.is_file():
        raise ValueError("refuse: no prepared matte evidence")
    state = json.loads(state_path.read_text())
    if (
        state.get("project") != project.GetName()
        or _sha(matte) != state["sourceToMatte"]["derivedSha256"]
        or {path.name: _sha(path) for path in old_paths}
        != state["originalMoviesSha256"]
    ):
        raise ValueError("refuse: prior source/matte/movie identity changed")

    if args.phase == "import":
        if state.get("status") != "reserved" or project.GetTimelineCount() != 11:
            raise ValueError("refuse: import already attempted or target changed")
        if args.template is None or not args.template.is_file():
            raise ValueError("refuse: exact retained OTIO template required")
        if _sha(args.template) != state["otioTemplateSha256"]:
            raise ValueError("refuse: native template changed after prepare")
        path = root / (name + ".otio")
        write_otio(
            json.loads(args.template.read_text()),
            path,
            matte,
            48,
            motion=True,
            ease=0,
            framing="fit",
        )
        state["otioSha256"] = _sha(path)
        state["status"] = "import-attempted"
        _save(state_path, state)  # no replay after uncertain import
        pool = project.GetMediaPool()
        timeline = pool.ImportTimelineFromFile(
            str(path.resolve()), {"timelineName": name}
        )
        if timeline is None or not project.SetCurrentTimeline(timeline):
            raise ValueError("refuse: matte native OTIO import/current timeline failed")
        clips = timeline.GetItemListInTrack("video", 1)
        if len(clips) != 1 or clips[0].GetDuration() != 48:
            raise ValueError("refuse: matte clip extent changed")
        source_item = clips[0].GetMediaPoolItem()
        if (
            source_item is None
            or pathlib.Path(source_item.GetClipProperty("File Path")).resolve() != matte
        ):
            raise ValueError("refuse: imported matte source identity differs")
        state["status"] = "imported"
        _save(state_path, state)
        print("MATTE_IMPORTED", clips[0].GetDuration(), flush=True)
        return 0

    if args.phase == "render":
        if state.get("status") != "imported" or project.GetTimelineCount() != 12:
            raise ValueError("refuse: render requires one verified new matte timeline")
        if project.GetCurrentTimeline().GetName() != name:
            raise ValueError("refuse: native current timeline differs")
        if (render_dir / (name + ".mov")).exists():
            raise ValueError("refuse: render output already exists")
        state["status"] = "render-attempted"
        _save(state_path, state)  # no replay after uncertain job
        movie = render(project, name, render_dir, 120)
        state.update(status="rendered", nativeMovieSha256=_sha(movie), movie=movie.name)
        _save(state_path, state)
        print("MATTE_RENDERED", state["nativeMovieSha256"], flush=True)
        return 0

    if args.phase == "decode":
        if state.get("status") != "rendered":
            raise ValueError("refuse: no verified native matte movie")
        movie = render_dir / state["movie"]
        if _sha(movie) != state["nativeMovieSha256"]:
            raise ValueError("refuse: rendered movie changed before decode")
        decoded = video_pixels(movie, [0, 12, 24, 36, 47])
        if decoded["frames"] != 48 or decoded["size"] != [1280, 720]:
            raise ValueError("refuse: decoded matte output size/duration changed")
        for sample in decoded["samples"].values():
            if any(
                sample["witnesses"][color] is None
                for color in ("red", "green", "blue", "yellow", "magenta")
            ):
                raise ValueError(
                    "refuse: source corners/focus lost during native matte motion"
                )
        if (
            len(
                {
                    tuple(sample["witnesses"]["magenta"])
                    for sample in decoded["samples"].values()
                }
            )
            <= 1
        ):
            raise ValueError("refuse: matte has no visible native motion")
        if {path.name: _sha(path) for path in old_paths} != old_hashes:
            raise ValueError("refuse: prior render bytes changed")
        state.update(
            status="decoded",
            decoded=decoded,
        )
        _save(state_path, state)
        print(
            "MATTE_DECODED",
            json.dumps(
                {
                    "sourceToMatte": state["sourceToMatte"],
                    "decodedSha256": decoded["decodedSha256"],
                    "samples": decoded["samples"],
                },
                default=str,
            ),
            flush=True,
        )
        return 0

    if state.get("status") != "decoded" or state.get("project") != project.GetName():
        raise ValueError("refuse: unverified/uncertain matte output")
    if _sha(matte) != state["sourceToMatte"]["derivedSha256"]:
        raise ValueError("refuse: derived matte mutated")
    if _sha(render_dir / state["movie"]) != state["nativeMovieSha256"]:
        raise ValueError("refuse: native matte movie mutated")
    if {path.name: _sha(path) for path in old_paths} != state["originalMoviesSha256"]:
        raise ValueError("refuse: earlier movie bytes changed")
    if project.GetTimelineCount() != 12:
        raise ValueError("refuse: matte was not the sole new timeline")
    if not manager.SaveProject() or not manager.CloseProject(project):
        raise ValueError("refuse: native matte save/close failed")
    reopened = manager.LoadProject(state["project"])
    if reopened is None or reopened.GetTimelineCount() != 12:
        raise ValueError("refuse: matte project reopen failed")
    names = [reopened.GetTimelineByIndex(i).GetName() for i in range(1, 13)]
    durations = [
        reopened.GetTimelineByIndex(i).GetItemListInTrack("video", 1)[0].GetDuration()
        for i in range(1, 13)
    ]
    if names != [*old_names, name] or durations != [*old_durations, 48]:
        raise ValueError("refuse: imported timelines changed after save/reopen")
    state.update(status="reopened", reopenedNames=names, reopenedDurations=durations)
    _save(state_path, state)
    print("MATTE_REOPENED", len(names), durations, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
