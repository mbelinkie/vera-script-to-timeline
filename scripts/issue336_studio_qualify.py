"""Disposable #336 native OTIO raster qualification (NOT a production adapter).

Uses only freshly generated public synthetic PNGs and an existing public #325
OTIO export. Never selects an existing project, overrides an existing output,
changes Resolve preferences, or infers proof from an imported value. Run only
with exclusive Studio ownership and external scripting already enabled.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import time
import zlib


def png(path: pathlib.Path, width: int, height: int) -> None:
    """Deterministic public coordinate grid, with four source-edge witnesses."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            color = (170, 170, 170)
            if x % 100 < 2 or y % 100 < 2:
                color = (35, 35, 35)
            if x < 50 and y < 50:
                color = (245, 24, 20)  # top left red
            if x >= width - 50 and y < 50:
                color = (20, 240, 25)  # top right green
            if x < 50 and y >= height - 50:
                color = (24, 35, 245)  # bottom left blue
            if x >= width - 50 and y >= height - 50:
                color = (245, 240, 15)  # bottom right yellow
            if abs(x - int(width * 0.75)) < 23 and abs(y - int(height * 0.3)) < 23:
                color = (245, 25, 245)  # visible off-center focus target
            raw.extend(color)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def write_otio(
    template: dict,
    path: pathlib.Path,
    source: pathlib.Path,
    frames: int,
    *,
    motion: bool,
    ease: int,
    framing: str,
) -> None:
    value = copy.deepcopy(template)
    value["name"] = path.stem
    tracks = value["tracks"]["children"]
    clip = tracks[0]["children"][0]
    clip["name"] = path.stem
    clip["source_range"]["duration"]["value"] = frames
    refs = clip["media_references"]
    for ref in refs.values():
        ref["target_url"] = str(source.resolve())
        ref["name"] = source.name
    for effect in clip["effects"]:
        metadata = effect["metadata"].get("Resolve_OTIO", {})
        if metadata.get("Type") == 59:
            metadata["Enabled"] = motion
            for parameter in metadata.get("Parameters", []):
                pid = parameter.get("Parameter ID")
                if pid == "dynamicZoomCenter":
                    pairs = (("-86400", [0.0, 0.0]), ("-85400", [0.12, -0.08]))
                elif pid == "dynamicZoomScale":
                    pairs = (("-86400", 0.8), ("-85400", 1.05))
                else:
                    continue
                for key, endpoint in pairs:
                    parameter["Key Frames"][key]["Value"] = endpoint
                parameter["Parameter Value"] = pairs[-1][1]
        if metadata.get("Type") == 22:
            for parameter in metadata.get("Parameters", []):
                if parameter.get("Parameter ID") == "scale":
                    parameter["Parameter Value"] = 2 if framing == "fit" else 3
    tracks[0]["children"] = [clip]
    # A video-only public still experiment cannot accidentally import old audio.
    value["tracks"]["children"] = [tracks[0]]
    path.write_text(json.dumps(value, indent=2) + "\n")


def video_pixels(path: pathlib.Path, samples: list[int]) -> dict:
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_frames,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    frame_bytes = width * height * 3
    decoder = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        stdout=subprocess.PIPE,
    )
    digest = hashlib.sha256()
    frames = 0
    result: dict[str, object] = {}
    assert decoder.stdout is not None
    while True:
        data = decoder.stdout.read(frame_bytes)
        if not data:
            break
        if len(data) != frame_bytes:
            raise RuntimeError("partial decoded frame")
        digest.update(data)
        if frames in samples:
            witnesses: dict[str, list[int] | None] = {}
            predicates = {
                "red": lambda r, g, b: r > 185 and g < 85 and b < 85,
                "green": lambda r, g, b: r < 85 and g > 185 and b < 85,
                "blue": lambda r, g, b: r < 85 and g < 85 and b > 185,
                "yellow": lambda r, g, b: r > 185 and g > 185 and b < 85,
                "magenta": lambda r, g, b: r > 185 and b > 185 and g < 90,
            }
            for name, predicate in predicates.items():
                found = []
                for y in range(0, height, 3):
                    for x in range(0, width, 3):
                        i = (y * width + x) * 3
                        if predicate(*data[i : i + 3]):
                            found.append((x, y))
                witnesses[name] = (
                    [
                        round(sum(x for x, _ in found) / len(found)),
                        round(sum(y for _, y in found) / len(found)),
                    ]
                    if found
                    else None
                )
            result[str(frames)] = {
                "frameSha256": hashlib.sha256(data).hexdigest(),
                "witnesses": witnesses,
                "centerRgb": list(data[((height // 2) * width + width // 2) * 3 :][:3]),
            }
        frames += 1
    if decoder.wait() != 0:
        raise RuntimeError("ffmpeg decode failed")
    if frames != int(stream["nb_frames"]):
        raise RuntimeError("decoded and container frame counts disagree")
    return {
        "frames": frames,
        "size": [width, height],
        "rate": stream["r_frame_rate"],
        "decodedSha256": digest.hexdigest(),
        "samples": result,
    }


def render(
    project: object, name: str, target: pathlib.Path, timeout: int
) -> pathlib.Path:
    formats = project.GetRenderCodecs("mov")
    codec = next((v for k, v in formats.items() if "422" in k or "422" in v), None)
    if codec is None:
        raise RuntimeError(f"No local ProRes 422 codec: {formats}")
    if project.IsRenderingInProgress() is not False:
        raise RuntimeError("another render is active; no mutation")
    if not project.SetCurrentRenderFormatAndCodec("mov", codec):
        raise RuntimeError(f"Render codec rejected: {codec}")
    settings = {
        "TargetDir": str(target),
        "CustomName": name,
        "ExportVideo": True,
        "ExportAudio": False,
        "RenderMode": "Single clip",
        "SelectAllFrames": True,
        "FormatWidth": 1280,
        "FormatHeight": 720,
    }
    if not project.SetRenderSettings(settings):
        raise RuntimeError("render settings refused")
    job = project.AddRenderJob()
    if not isinstance(job, str) or not job:
        raise RuntimeError("AddRenderJob did not return job ID")
    if not project.StartRendering([job], False):
        raise RuntimeError("StartRendering refused")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = project.GetRenderJobStatus(job)
        if status.get("JobStatus") in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(1)
    else:
        raise RuntimeError("render timeout; NEVER replay pending job")
    if status.get("JobStatus") != "Complete":
        raise RuntimeError(f"render status not complete: {status}")
    movies = list(target.glob(name + "*.mov"))
    if len(movies) != 1 or not movies[0].stat().st_size:
        raise RuntimeError(f"render completed without one nonempty movie: {movies}")
    return movies[0]


def empty_disposable_project(project: object) -> bool:
    """Read-only guard; never adopt a project with possible user content."""
    root = project.GetMediaPool().GetRootFolder()
    return (
        project.GetTimelineCount() == 0
        and not root.GetClipList()
        and not root.GetSubFolderList()
        and not project.GetRenderJobList()
        and project.IsRenderingInProgress() is False
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--case", type=str)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--adopt-created-project", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required for fresh native project")
    if bool(args.case) == bool(args.finalize):
        parser.error("select exactly one --case or --finalize per bounded call")
    template = json.loads(args.template.read_text())
    sources = {"square": (1000, 1000), "wide": (1600, 900), "tall": (900, 1600)}
    sys.path.append(
        "/Library/Application Support/Blackmagic Design/"
        "DaVinci Resolve/Developer/Scripting/Modules"
    )
    import DaVinciResolveScript  # type: ignore[import-not-found]

    resolve = DaVinciResolveScript.scriptapp("Resolve")
    if resolve is None or resolve.GetVersionString() != "21.1.1.10":
        raise RuntimeError("installed supported Studio version did not connect")
    manager = resolve.GetProjectManager()
    label = "VERA336-SYN-" + args.out.name.replace("_", "-")
    if args.out.exists():
        evidence: dict = json.loads((args.out / "evidence.json").read_text())
        project = manager.GetCurrentProject()
        if project is None or project.GetName() != evidence.get("project"):
            raise RuntimeError(
                "fresh native project not current; refuse unrelated target"
            )
        if evidence.get("stoppedAt") or any(
            item.get("status") != "decoded" for item in evidence["cases"].values()
        ):
            raise RuntimeError("uncertain/refused previous case; no new native writes")
        for name in sources:
            digest = hashlib.sha256(
                (args.out / (name + ".png")).read_bytes()
            ).hexdigest()
            if digest != evidence["sourceHashes"][name]:
                raise RuntimeError("synthetic source bytes changed; refuse")
    else:
        current = manager.GetCurrentProject()
        if args.adopt_created_project:
            if (
                current is None
                or current.GetName() != label
                or not empty_disposable_project(current)
            ):
                raise RuntimeError(
                    "refuse: no exact empty pre-created synthetic project"
                )
            project = current
        else:
            if current is not None:
                # Resolve can open its empty default project on startup.  It
                # refuses CreateProject while that scratch project is active.
                # Close it without saving ONLY after independently proving it has
                # no timeline, media, queued work or render in progress.
                if (
                    current.GetName() != "Untitled Project"
                    or not empty_disposable_project(current)
                ):
                    raise RuntimeError("refuse: a nonempty existing project is active")
                if not manager.CloseProject(current):
                    raise RuntimeError("refuse: empty startup project could not close")
            project = manager.CreateProject(label)
            if project is None:
                raise RuntimeError("fresh disposable project creation refused")
        args.out.mkdir(parents=True, exist_ok=False)
        for name, (w, h) in sources.items():
            png(args.out / (name + ".png"), w, h)
        evidence = {
            "app": resolve.GetVersionString(),
            "project": label,
            "sourceHashes": {
                name: hashlib.sha256(
                    (args.out / (name + ".png")).read_bytes()
                ).hexdigest()
                for name in sources
            },
            "cases": {},
        }
        (args.out / "evidence.json").write_text(json.dumps(evidence, indent=2))
    cases = [
        ("square-none-48", "square", 48, False, 0, "fit"),
        ("square-motion-24", "square", 24, True, 0, "fit"),
        ("square-motion-48", "square", 48, True, 0, "fit"),
        ("square-motion-96", "square", 96, True, 0, "fit"),
        ("square-motion-144", "square", 144, True, 0, "fit"),
        ("wide-motion-48", "wide", 48, True, 0, "fit"),
        ("tall-motion-48", "tall", 48, True, 0, "fit"),
        ("square-cover-48", "square", 48, True, 0, "fill"),
        ("square-ease-in-48", "square", 48, True, 1, "fit"),
        ("square-ease-out-48", "square", 48, True, 2, "fit"),
        ("square-ease-both-48", "square", 48, True, 3, "fit"),
    ]
    if args.finalize:
        if not evidence["cases"] or not manager.SaveProject():
            raise RuntimeError("no successful case to save/reopen")
        if not manager.CloseProject(project):
            raise RuntimeError("CloseProject refused")
        reopened = manager.LoadProject(label)
        if reopened is None:
            raise RuntimeError("LoadProject refused; do not replay")
        evidence["reopened"] = {
            "timelineCount": reopened.GetTimelineCount(),
            "names": [
                reopened.GetTimelineByIndex(i).GetName()
                for i in range(1, reopened.GetTimelineCount() + 1)
            ],
            "durations": [
                reopened.GetTimelineByIndex(i)
                .GetItemListInTrack("video", 1)[0]
                .GetDuration()
                for i in range(1, reopened.GetTimelineCount() + 1)
            ],
        }
        (args.out / "evidence.json").write_text(
            json.dumps(evidence, indent=2, default=str)
        )
        print("REOPENED", evidence["reopened"], flush=True)
        return 0
    selected = [item for item in cases if item[0] == args.case]
    if len(selected) != 1 or args.case in evidence["cases"]:
        raise RuntimeError("unrecognized or duplicate case; refuse native write")
    pool = project.GetMediaPool()
    for name, source, frames, motion, ease, framing in selected:
        evidence["cases"][name] = {"status": "starting"}
        (args.out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        try:
            otio = args.out / (name + ".otio")
            write_otio(
                template,
                otio,
                args.out / (source + ".png"),
                frames,
                motion=motion,
                ease=ease,
                framing=framing,
            )
            timeline = pool.ImportTimelineFromFile(str(otio), {"timelineName": name})
            if timeline is None or not project.SetCurrentTimeline(timeline):
                raise RuntimeError("native OTIO import/current timeline failed")
            clips = timeline.GetItemListInTrack("video", 1)
            if len(clips) != 1 or clips[0].GetDuration() != frames:
                raise RuntimeError("import altered exact clip duration")
            clip = clips[0]
            readback = {"before": clip.GetProperty()}
            if motion and ease:
                readback["setter"] = clip.SetProperty("DynamicZoomEase", ease)
                readback["after"] = clip.GetProperty()
            if not manager.SaveProject():
                raise RuntimeError("SaveProject failed")
            video = render(project, name, args.out, args.timeout)
            decoded = video_pixels(
                video,
                sorted({0, frames // 4, frames // 2, (3 * frames) // 4, frames - 1}),
            )
            if decoded["frames"] != frames:
                raise RuntimeError("render lost or added frames")
            evidence["cases"][name] = {
                "status": "decoded",
                "frames": frames,
                "motion": motion,
                "ease": ease,
                "framing": framing,
                "readback": readback,
                "movieSha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "decoded": decoded,
            }  # type: ignore[index]
        except Exception as exc:
            evidence["cases"][name] = {"status": "refused", "reason": str(exc)}  # type: ignore[index]
            evidence["stoppedAt"] = name
            break  # no new writes after an uncertain failure
        finally:
            (args.out / "evidence.json").write_text(
                json.dumps(evidence, indent=2, default=str) + "\n"
            )
            print(name, evidence["cases"][name]["status"], flush=True)  # type: ignore[index]
    print("EVIDENCE", args.out / "evidence.json", flush=True)
    return 1 if "stoppedAt" in evidence else 0


if __name__ == "__main__":
    raise SystemExit(main())
