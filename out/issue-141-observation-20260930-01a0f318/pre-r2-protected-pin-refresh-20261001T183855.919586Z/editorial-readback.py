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
    "r1-copy-context",
    "r1-copy-deselected",
    "r1-copy-selected",
    "r1-copy-copied",
    "r1-copy-paste-ready",
    "r1-copy-pasted",
    "r2-linked-context",
    "r2-linked-deselected",
    "r2-linked-selected",
    "r2-linked-first-split",
    "r2-linked-second-position",
    "r2-linked-second-selected",
    "r2-linked-second-split",
    "r2-linked-deleted",
    "r5-edit-context",
    "r5-edit-note",
    "r5-edit-deselected",
    "r5-edit-selected",
    "r5-edit-moved",
}
LABELS.update(
    f"r2-{case}-{stage}"
    for case in ("unlinked", "picture", "partial")
    for stage in (
        "context",
        "deselected",
        "selected",
        "first-split",
        "second-position",
        "second-selected",
        "second-split",
        "deleted",
    )
)
LABELS.update(
    f"r2-offset-{stage}"
    for stage in ("context", "deselected", "selected", "edited")
)
LABELS.update(
    f"r2-residual-{stage}"
    for stage in (
        "context",
        "deselected",
        "selected",
        "first-split",
        "second-position",
        "second-selected",
        "second-split",
        "interval-selected",
        "deleted",
    )
)
LABELS.update(
    f"{case}-{stage}"
    for case in ("r3-graphic", "r3-boundary", "r3-boundary-a3")
    for stage in ("context", "deselected", "selected", "split")
)


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
    render_format_passes = []

    def context():
        project = reader._context(resolve, config, identity, probe, reader.MATRIX_UID)
        render_format = project.GetCurrentRenderFormatAndCodec()
        if isinstance(render_format, dict):
            render_format = render_format.copy()
        render_format_passes.append(render_format)
        if (
            len(render_format_passes) > 1
            and render_format != render_format_passes[0]
        ):
            raise RuntimeError("Render format/codec changed during readback")
        if (
            resolve.GetCurrentPage() != "edit"
            or project.GetRenderJobList() != []
        ):
            raise RuntimeError("Exact Edit/empty queue required")
        return project.GetCurrentTimeline()

    selections, selection_shapes, failure = [], [], None
    context()
    pair = reader._read_pair(
        resolve, config, identity, sources, reader.MATRIX_UID, probe
    )
    reader._write(directory / "pair.json", pair)
    try:
        reader._validate_read_pair(pair, probe)
        context()
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
        context()
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
        "renderFormatPasses": render_format_passes,
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
