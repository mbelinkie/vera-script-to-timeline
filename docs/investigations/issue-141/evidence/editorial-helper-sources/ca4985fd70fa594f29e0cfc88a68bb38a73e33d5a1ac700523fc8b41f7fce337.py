"""Read-only full state and selected-item evidence around approved menus."""

import importlib.util
import platform
from datetime import UTC, datetime
from pathlib import Path

READER_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
LABELS = {
    "editorial-context",
    "r1-razor-deselected",
    "r1-razor-selected",
    "r1-razor-split",
    "r1-trim-deselected",
    "r1-trim-selected",
    "r1-trim-edited",
    "r1-move-context",
    "r1-move-deselected",
    "r1-move-selected",
    "r1-move-edited",
}


def run(resolve, config, *, probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != READER_SHA:
        raise RuntimeError("Pinned complete reader changed")
    spec = importlib.util.spec_from_file_location("editorial_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    label = config.get("editorialReadbackLabel")
    output = Path(config["outputDir"])
    if (
        config.get("action") != "editorial-readback"
        or label not in LABELS
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != Path(probe.ROOT).resolve() / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact approved editorial readback required")
    _, sources = reader._manifest(config, Path(probe.ROOT).resolve(), probe)
    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = output / f"{label}-{stamp}"
    directory.mkdir()
    journal = directory / "journal.jsonl"
    journal.touch()

    def context():
        project = reader._context(resolve, config, identity, probe, reader.MATRIX_UID)
        if (
            resolve.GetCurrentPage() != "edit"
            or project.GetRenderJobList() != []
            or project.GetCurrentRenderFormatAndCodec()
            != {"format": "mov", "codec": "H264"}
        ):
            raise RuntimeError("Exact Edit/known format/empty queue required")
        return project.GetCurrentTimeline()

    selections, selection_shapes, failure = [], [], None
    context()
    pair = reader._read_pair(
        resolve, config, identity, sources, reader.MATRIX_UID, probe
    )
    reader._write(directory / "pair.json", pair)
    try:
        reader._validate_read_pair(pair, probe)
        for _ in range(2):
            timeline = context()
            selected = timeline.GetSelectedClips()
            selection_shapes.append(
                {
                    "type": type(selected).__name__,
                    "count": len(selected)
                    if isinstance(selected, (list, dict, tuple))
                    else None,
                }
            )
            if not isinstance(selected, list):
                raise RuntimeError("Documented selected-clip list unreadable")
            selections.append(
                {
                    "playhead": timeline.GetCurrentTimecode(),
                    "items": [probe.item_evidence(item, sources) for item in selected],
                }
            )
            context()
        if selections[0] != selections[1] or probe.errors(selections):
            raise RuntimeError("Selected-clip adjacent reads incomplete or differing")
        after = reader._read_pair(
            resolve, config, identity, sources, reader.MATRIX_UID, probe
        )
        reader._write(directory / "pair-after-selection.json", after)
        reader._validate_read_pair(after, probe)
        if after != pair:
            raise RuntimeError("Full state changed during selected-clip readback")
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    result = {
        "status": "editorial-readback-retained" if failure is None else "refused",
        "label": label,
        "pair": {
            "path": str(directory / "pair.json"),
            "sha256": probe.sha256(directory / "pair.json"),
        },
        "selectionPasses": selections,
        "selectionShapes": selection_shapes,
        "failure": failure,
        "readOnly": True,
        "environment": {
            "productName": resolve.GetProductName(),
            "version": resolve.GetVersion(),
            "python": platform.python_version(),
        },
        "limits": ["External menu result requires separate full-state interpretation."],
    }
    reader._write(directory / "result.json", result)
    return result
