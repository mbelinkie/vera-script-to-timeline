"""Small fake-native check of the read-only menu-result collector."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "editorial_readback", Path(__file__).with_name("editorial-readback.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def demo():
    for mode in (
        "success",
        "unknown-format-success",
        "single-track-success",
        "residual-interval-success",
        "list-refused",
        "selection-drift",
        "format-drift",
        "mutable-format-drift",
        "full-state-drift",
        "queue-refused",
        "wrong-page-refused",
        "unknown-label-refused",
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out" / "issue-141-observation-fake"
            output.mkdir(parents=True)
            selected_calls = []
            format_reads = []
            pair_reads = []
            shared_format = {"format": "mov", "codec": "H264"}

            def selected(mode=mode, calls=selected_calls):
                calls.append("GetSelectedClips")
                if mode == "list-refused":
                    return {}
                if mode == "selection-drift" and len(calls) > 1:
                    return ["different"]
                return ["video", "audio"]

            def format_codec(
                mode=mode, reads=format_reads, shared=shared_format
            ):
                value = {"format": "mov", "codec": "H264"}
                if mode == "unknown-format-success" or (
                    mode == "format-drift" and reads
                ):
                    value = {"format": "unknown", "codec": ""}
                elif mode == "mutable-format-drift":
                    value = shared
                    if reads:
                        shared.update(format="unknown", codec="")
                reads.append(value.copy() if isinstance(value, dict) else value)
                return value

            def read_pair(*args, mode=mode, reads=pair_reads):
                reads.append(None)
                pool_passes = (
                    [{}, {"drift": True}]
                    if mode == "full-state-drift" and len(reads) > 1
                    else [{}, {}]
                )
                return {
                    "selectedTimelineUid": "matrix",
                    "timelinePasses": [{}, {}],
                    "poolPasses": pool_passes,
                    "timelineConsistency": "equal-adjacent-reads",
                    "poolConsistency": "equal-adjacent-reads",
                }

            timeline = SimpleNamespace(
                GetSelectedClips=selected,
                GetCurrentTimecode=lambda: "00:01:04:00",
            )
            project = SimpleNamespace(
                GetCurrentTimeline=lambda timeline=timeline: timeline,
                GetRenderJobList=lambda mode=mode: (
                    ["foreign"] if mode == "queue-refused" else []
                ),
                GetCurrentRenderFormatAndCodec=format_codec,
            )
            reader = SimpleNamespace(
                BUILD=[21, 1, 0, 14, ""],
                PROJECT_ID="pinned",
                MATRIX_UID="matrix",
                _manifest=lambda *args: ({}, {}),
                _context=lambda *args, project=project: project,
                _read_pair=read_pair,
                _validate_read_pair=lambda *args: ({}, {}),
                _write=lambda path, value: path.write_text(json.dumps(value)),
            )
            resolve = SimpleNamespace(
                GetProductName=lambda: "DaVinci Resolve Studio",
                GetVersion=lambda reader=reader: reader.BUILD,
                GetCurrentPage=lambda mode=mode: (
                    "deliver" if mode == "wrong-page-refused" else "edit"
                ),
            )
            probe = SimpleNamespace(
                ROOT=root,
                sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                item_evidence=lambda item, sources: {"uid": item},
                errors=lambda value: [],
            )
            config = {
                "action": "editorial-readback",
                "editorialReadbackLabel": "r1-razor-selected",
                "outputDir": str(output),
                "projectName": "synthetic",
                "externalScriptingSetting": "None",
            }
            if mode == "single-track-success":
                config["editorialReadbackLabel"] = "r2-picture-selected"
            elif mode == "residual-interval-success":
                config["editorialReadbackLabel"] = "r2-residual-interval-selected"
            elif mode == "unknown-label-refused":
                config["editorialReadbackLabel"] = "arbitrary-ui-action"
            fake_spec = SimpleNamespace(
                loader=SimpleNamespace(exec_module=lambda m: None)
            )
            with (
                patch.object(
                    module.importlib.util,
                    "spec_from_file_location",
                    return_value=fake_spec,
                ),
                patch.object(
                    module.importlib.util, "module_from_spec", return_value=reader
                ),
            ):
                if mode in {
                    "queue-refused",
                    "wrong-page-refused",
                    "unknown-label-refused",
                }:
                    try:
                        module.run(resolve, config, probe=probe)
                    except RuntimeError:
                        assert not selected_calls
                    else:
                        raise AssertionError("Unsafe readback context was accepted")
                else:
                    result = module.run(resolve, config, probe=probe)
                    assert result["readOnly"] is True
                    assert result["status"] == (
                        "editorial-readback-retained"
                        if mode in {
                            "success",
                            "unknown-format-success",
                            "single-track-success",
                            "residual-interval-success",
                        }
                        else "refused"
                    )
                    assert result["renderFormatPasses"] == format_reads
                    assert format_reads
                    if mode in {"format-drift", "mutable-format-drift"}:
                        assert len(set(map(str, format_reads))) == 2
                    else:
                        assert len(set(map(str, format_reads))) == 1
                    if mode == "unknown-format-success":
                        assert result["renderFormatPasses"][0] == {
                            "format": "unknown",
                            "codec": "",
                        }
                    elif mode in {"format-drift", "mutable-format-drift"}:
                        assert "Render format/codec changed" in result["failure"]
                    elif mode == "full-state-drift":
                        assert "Full state changed" in result["failure"]
                    elif mode == "list-refused":
                        assert "selected-clip list unreadable" in result["failure"]
                    elif mode == "selection-drift":
                        assert "Selected-clip adjacent reads" in result["failure"]
                    assert len(list(output.glob("*/pair.json"))) == 1
    print("Editorial readback checks passed; fake has no native mutations.")


if __name__ == "__main__":
    demo()
