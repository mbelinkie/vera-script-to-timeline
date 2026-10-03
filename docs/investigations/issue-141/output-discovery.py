"""Read-only Resolve render capability inventory for Issue 141 R2."""

import json
import platform
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
MATRIX_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
RESOLVE_VERSION = [21, 1, 0, 14, ""]
PIN_NAME = "capture-20260930T234711.275916Z.json"
PIN_SHA256 = "3d08f757c8e188bbc5c1584158f5ea29c23f5bb7745bf01bd5de42c6d6436a46"


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _append(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "phase": phase,
                "value": value,
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _expected_sources(config, probe):
    media = Path(config["mediaDir"])
    manifest_path = media / "manifest.json"
    if probe.sha256(manifest_path) != config.get("manifestSha256"):
        raise RuntimeError("Synthetic media manifest hash differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Only generated issue-141 synthetic inputs are allowed")
    expected = {}
    for entry in manifest.get("files", []):
        relative = Path(entry["path"])
        path = media / relative
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink():
            raise RuntimeError("Unsafe synthetic input path")
        if not path.resolve().is_relative_to(media.resolve()):
            raise RuntimeError("Synthetic input escaped its media directory")
        expected[str(path)] = entry["sha256"]
    if len(expected) != len(manifest.get("files", [])):
        raise RuntimeError("Synthetic manifest contains duplicate paths")
    return expected, manifest


def run(resolve, config, *, probe):
    """Capture discovered render APIs without setting or queueing a render."""
    if config.get("externalScriptingSetting") != "None":
        raise RuntimeError("Operator must attest External Scripting None")
    if config.get("projectName", "")[: len(probe.PREFIX)] != probe.PREFIX:
        raise RuntimeError("Named issue-141 synthetic project is required")
    root = Path(probe.ROOT).resolve()
    media_dir = Path(config["mediaDir"])
    if (
        not media_dir.is_absolute()
        or media_dir.is_symlink()
        or media_dir.parent.resolve() != (root / "out").resolve()
        or not media_dir.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only generated issue-141 media under out is allowed")
    output_parent = Path(config["outputDir"])
    if (
        not output_parent.is_absolute()
        or output_parent.is_symlink()
        or output_parent.parent.resolve() != (root / "out").resolve()
        or not output_parent.name.startswith("issue-141-observation-")
        or not output_parent.is_dir()
    ):
        raise RuntimeError(
            "Only an existing issue-141 evidence directory under out is allowed"
        )
    pin_path = Path(config["checkpointPath"])
    if (
        not pin_path.is_absolute()
        or pin_path.is_symlink()
        or not pin_path.resolve().is_relative_to((root / "out").resolve())
        or pin_path.name != PIN_NAME
        or probe.sha256(pin_path) != PIN_SHA256
    ):
        raise RuntimeError("Exact saved Matrix checkpoint is missing or changed")
    pinned_capture = json.loads(pin_path.read_text(encoding="utf-8"))
    pin_passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(pin_passes) != 2
        or pin_passes[0] != pin_passes[1]
        or probe.errors(pin_passes)
        or pin_passes[0].get("projectId") != PROJECT_ID
        or len(pin_passes[0].get("timelines", [])) != 3
    ):
        raise RuntimeError("Saved Matrix checkpoint is incomplete or inconsistent")
    pinned = pin_passes[0]
    matrix = probe._pass_timeline(pinned, MATRIX_ID)
    if matrix.get("GetName") != {"value": MATRIX_NAME}:
        raise RuntimeError("Pinned Matrix identity differs")

    expected, manifest = _expected_sources(config, probe)
    for locator, digest in expected.items():
        if probe.source_evidence(locator, expected).get("sha256") != digest:
            raise RuntimeError("Generated synthetic source bytes differ from manifest")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence_dir = output_parent / f"program-output-discovery-{stamp}"
    evidence_dir.mkdir(exist_ok=False)
    journal = evidence_dir / "journal.jsonl"
    config_for_probe = dict(config)
    config_for_probe["stage"] = "R2-program-output-discovery"
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}

    product = resolve.GetProductName()
    version = resolve.GetVersion()
    source_path = Path(probe.__file__).resolve()
    stamps = {
        "productName": product,
        "resolveVersion": version,
        "pythonVersion": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "sourcePath": str(source_path),
        "sourceSha256": probe.sha256(source_path),
        "discoverySourceSha256": probe.sha256(Path(__file__).resolve()),
        "manifestSha256": config["manifestSha256"],
        "syntheticSources": expected,
        "installedDocs": manifest.get("installedDocs", {}),
        "externalScriptingSetting": "None",
    }
    if "studio" not in str(product).casefold() or version != RESOLVE_VERSION:
        _write(
            evidence_dir / "refusal.json",
            {"reason": "Resolve product/build differs", "stamps": stamps},
        )
        raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
    _append(journal, "OutputDiscovery", "start", {"stamps": stamps})

    def context_check():
        project = probe.require_current(resolve, config_for_probe, identity)
        selected = project.GetCurrentTimeline()
        selected_uid = None if selected is None else selected.GetUniqueId()
        if selected_uid != MATRIX_ID:
            raise RuntimeError("Exact Matrix timeline must remain selected")
        return project

    def full_capture(label):
        captures = []
        for _ in range(2):
            try:
                context_check()
                captures.append(
                    json.loads(
                        json.dumps(
                            probe.observe(
                                resolve, config_for_probe, identity, expected
                            ),
                            allow_nan=False,
                        )
                    )
                )
            except Exception as error:
                captures.append({"error": f"{type(error).__name__}: {error}"})
        payload = {
            "label": label,
            "passes": captures,
            "consistency": "equal-adjacent-reads"
            if captures[0] == captures[1]
            else "inconsistent-refused",
        }
        if probe.errors(captures):
            payload["consistency"] = "incomplete-refused"
        _write(evidence_dir / f"{label}.json", payload)
        return payload

    before = full_capture("before")
    _append(journal, "Preflight", "readback", before)
    if before["consistency"] != "equal-adjacent-reads" or probe.errors(before):
        _write(
            evidence_dir / "refusal.json",
            {
                "reason": "Live preflight reads are not equal",
                "before": before,
                "stamps": stamps,
            },
        )
        raise RuntimeError("Live preflight reads are not equal")
    if before["passes"][0] != pinned:
        _write(
            evidence_dir / "refusal.json",
            {
                "reason": "Live preflight differs from saved Matrix pin",
                "before": before,
                "stamps": stamps,
            },
        )
        raise RuntimeError("Live preflight differs from saved Matrix pin")

    project = context_check()
    reads = [
        ("GetRenderFormats", ()),
        ("GetAudioRenderFormats", ()),
        ("GetCurrentRenderFormatAndCodec", ()),
        ("GetCurrentRenderMode", ()),
        ("GetRenderJobList", ()),
        ("IsRenderingInProgress", ()),
    ]
    results = {}

    def read_project(method, args=()):
        nonlocal project
        project = context_check()
        _append(journal, method, "request", list(args))
        try:
            value = getattr(project, method)(*args)
            results[method] = {"status": "returned", "value": value}
            _append(journal, method, "return", value)
            return value
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
            results[method] = {"status": "error", "error": failure}
            _append(journal, method, "failure", failure)
            return None

    render_formats = read_project(*reads[0])
    if isinstance(render_formats, dict) and any(
        str(extension).casefold().lstrip(".") == "mov"
        for extension in render_formats.values()
    ):
        read_project("GetRenderCodecs", ("mov",))
    audio_formats = read_project(*reads[1])
    if isinstance(audio_formats, dict) and any(
        str(extension).casefold().lstrip(".") == "wav"
        for extension in audio_formats.values()
    ):
        read_project("GetAudioRenderCodecs", ("wav",))
    for method, args in reads[2:]:
        read_project(method, args)

    after = full_capture("after")
    _append(journal, "Postflight", "readback", after)
    unchanged = (
        after["consistency"] == "equal-adjacent-reads"
        and after["passes"][0] == before["passes"][0]
        and not probe.errors(after)
    )
    report = {
        "kind": "read-only-render-api-discovery",
        "capturedAt": stamp,
        "status": "equal-read-only-capture"
        if unchanged
        else "changed-or-incomplete-refused",
        "projectId": PROJECT_ID,
        "selectedTimelineId": MATRIX_ID,
        "stamps": stamps,
        "before": before,
        "projectReads": results,
        "after": after,
        "unchanged": unchanged,
        "journal": str(journal),
        "limits": [
            "Enumeration and getters establish availability/readback only, "
            "not a successful render.",
            "No render settings, queue jobs, output files, "
            "or project content were changed.",
        ],
    }
    _write(evidence_dir / "report.json", report)
    _append(
        journal,
        "OutputDiscovery",
        "complete",
        {"status": report["status"], "unchanged": unchanged},
    )
    if not unchanged:
        raise RuntimeError(
            "Project capture changed or became incomplete; evidence retained"
        )
    return report
