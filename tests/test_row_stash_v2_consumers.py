"""A saved v2 stash stays outside Python narration and compiler media selection."""

# The local Python package has no py.typed marker; this test exercises its runtime API.
# mypy: disable-error-code=import-untyped

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from vera_timeline_agent.narration.service import (
    NarrationService,
)
from vera_timeline_agent.roundtrip_v2_build import (
    PreparedProofBuildV2,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json"

_AUTHORING_SCRIPT = r"""
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const root = process.argv[1];
const sourceDirectory = pathToFileURL(join(root, "packages/contracts/src") + "/").href;
registerHooks({ resolve(specifier, context, nextResolve) {
  const resolved = context.parentURL?.startsWith(sourceDirectory)
    && specifier.startsWith("./")
    && specifier.endsWith(".js")
    ? specifier.slice(0, -3) + ".ts"
    : specifier;
  return nextResolve(resolved, context);
} });

const { applyRowEditV2, validateScriptDocumentV2 } = await import(
  new URL("authoring-v2.ts", sourceDirectory)
);
const { applyStashRowEditV2 } = await import(
  new URL("authoring-v2-stash.ts", sourceDirectory)
);
const input = JSON.parse(readFileSync(0, "utf8"));
const document = input.document;
const row = document.activeDraft.blocks.find((block) => block.type === "narration");
if (!row) throw new Error("fixture narration row is missing");

const stashedResult = applyRowEditV2(document, document.rowEditRevision ?? 0, {
  kind: "stash_rows",
  rowIds: [row.id],
  bundleId: input.bundleId,
});
if (!stashedResult.ok) throw new Error(JSON.stringify(stashedResult.diagnostics));

const sectionResult = applyRowEditV2(stashedResult.document, stashedResult.document.rowEditRevision ?? 0, {
  kind: "create_stash_section",
  sectionId: input.stashSectionId,
  title: "Saved clips",
});
if (!sectionResult.ok) throw new Error(JSON.stringify(sectionResult.diagnostics));
const organizedResult = applyRowEditV2(sectionResult.document, sectionResult.document.rowEditRevision ?? 0, {
  kind: "move_stash_rows",
  rowIds: [row.id],
  sectionId: input.stashSectionId,
});
if (!organizedResult.ok) throw new Error(JSON.stringify(organizedResult.diagnostics));

// Validate the JSON that a saved project would reload, not only the live result.
const editedRow = structuredClone(row);
const prefix = "EDITED ";
editedRow.text = prefix + editedRow.text;
editedRow.tokens = editedRow.tokens.map((token) => ({
  ...token,
  startOffset: token.startOffset + prefix.length,
  endOffset: token.endOffset + prefix.length,
}));
const editedResult = applyStashRowEditV2(
  organizedResult.document, organizedResult.document.rowEditRevision ?? 0, {
  bundleId: input.bundleId,
  rowId: row.id,
  row: editedRow,
});
if (!editedResult.ok) throw new Error(JSON.stringify(editedResult.diagnostics));

const stashedSerialized = JSON.stringify(editedResult.document);
const stashed = JSON.parse(stashedSerialized);
const stashedValidation = validateScriptDocumentV2(stashed);
if (!stashedValidation.valid) {
  throw new Error(JSON.stringify(stashedValidation.diagnostics));
}

const sectionedStashed = JSON.parse(JSON.stringify(organizedResult.document));
const restoredResult = applyRowEditV2(
  sectionedStashed, sectionedStashed.rowEditRevision ?? 0, {
  kind: "restore_stash_rows",
  rowIds: [row.id],
  destination: {
    sectionId: input.sectionId,
    afterRowId: null,
    beforeRowId: input.placeholderRowId,
  },
});
if (!restoredResult.ok) throw new Error(JSON.stringify(restoredResult.diagnostics));

const restoredSerialized = JSON.stringify(restoredResult.document);
const restored = JSON.parse(restoredSerialized);
const restoredValidation = validateScriptDocumentV2(restored);
if (!restoredValidation.valid) {
  throw new Error(JSON.stringify(restoredValidation.diagnostics));
}

process.stdout.write(JSON.stringify({
  stashedSerialized,
  restoredSerialized,
  rowId: row.id,
  editedText: editedRow.text,
  bundleId: input.bundleId,
  stashSectionId: input.stashSectionId,
  mediaReferenceId: row.primaryVisualSequence.slots.flatMap((slot) => {
    if (slot.kind === "content" && slot.payload.kind === "visual") {
      return [slot.payload.source];
    }
    return [];
  })
    .find((source) => source.kind === "media_reference")?.mediaReferenceId,
}));
"""


def _id(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012x}"


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js 24.19.0 must be available on PATH for the v2 compiler bridge"
        )
    return node


def _document_with_duration_fallback(document: dict[str, Any]) -> tuple[str, str]:
    """Keep a harmless duration row active while the narration is stashed."""
    section_id = _id(9000)
    placeholder_row_id = _id(9001)
    document["activeDraft"]["blocks"].insert(
        0,
        {
            "type": "section",
            "id": section_id,
            "orderKey": "a0",
            "title": "Section",
            "version": 1,
        },
    )
    narration = next(
        block
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    )
    narration["orderKey"] = "a1"
    document["activeDraft"]["blocks"].append(
        {
            "type": "visual_only",
            "id": placeholder_row_id,
            "orderKey": "a2",
            "version": 1,
            "payload": {
                "kind": "visual",
                "payloadId": _id(9002),
                "pictureKind": "intentional_placeholder",
                "source": {"kind": "intentional_placeholder", "text": "No source"},
                "audioPolicy": "mute",
                "framingPolicy": "contain",
            },
            "visualOnlyTiming": {"kind": "visual_only"},
        },
    )
    return section_id, placeholder_row_id


def _apply_stash_and_restore(
    document: dict[str, Any], section_id: str, placeholder_row_id: str
) -> dict[str, Any]:
    payload = {
        "document": document,
        "bundleId": _id(9003),
        "stashSectionId": _id(9004),
        "sectionId": section_id,
        "placeholderRowId": placeholder_row_id,
    }
    result = subprocess.run(
        [_node(), "--input-type=module", "-e", _AUTHORING_SCRIPT, str(ROOT)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        check=False,
        cwd=ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return cast(dict[str, Any], json.loads(result.stdout))


def _compile_with_python_bridge(
    tmp_path: Path,
    document: dict[str, Any],
    dependencies: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    document_path = tmp_path / f"{label}-script-document-v2.json"
    dependencies_path = tmp_path / f"{label}-compiler-dependencies-v2.json"
    document_path.write_text(json.dumps(document), encoding="utf-8")
    dependencies_path.write_text(json.dumps(dependencies), encoding="utf-8")

    # Exercise the same Python bridge method used by the prepared-build flow.
    build = PreparedProofBuildV2.__new__(PreparedProofBuildV2)
    build.node = _node()
    build.document_path = document_path
    build.dependencies_path = dependencies_path
    build.inputs = {
        "document": {"sha256": _sha256(document_path.read_bytes())},
        "dependencies": {"sha256": _sha256(dependencies_path.read_bytes())},
    }
    return PreparedProofBuildV2._compile(build)


def _narration_ids(document: dict[str, Any]) -> list[str]:
    calls: list[str] = []
    service = NarrationService.__new__(NarrationService)

    def record(block: dict[str, Any], *, _provider_error: object = None) -> Any:
        calls.append(block["id"])
        return SimpleNamespace(extra={}, failure_reason=None)

    with patch.object(service, "process_block", side_effect=record):
        service.process_document(document)
    return calls


@pytest.mark.slow
def test_saved_stash_is_ignored_by_python_narration_and_media_needs(
    tmp_path: Path,
) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document = fixture["document"]
    dependencies = fixture["dependencies"]
    section_id, placeholder_row_id = _document_with_duration_fallback(document)
    operation = _apply_stash_and_restore(document, section_id, placeholder_row_id)
    stashed = json.loads(operation["stashedSerialized"])
    restored = json.loads(operation["restoredSerialized"])
    row_id = operation["rowId"]
    media_reference_id = operation["mediaReferenceId"]

    assert stashed["stash"][0]["rows"][0]["id"] == row_id
    assert stashed["stash"][0]["rows"][0]["primaryVisualSequence"]
    assert stashed["stash"][0]["rows"][0]["text"] == operation["editedText"]
    assert stashed["stashSections"] == [
        {"id": operation["stashSectionId"], "title": "Saved clips", "rowIds": [row_id]}
    ]
    assert all(block["id"] != row_id for block in stashed["activeDraft"]["blocks"])
    assert restored["stashSections"] == [
        {"id": operation["stashSectionId"], "title": "Saved clips", "rowIds": []}
    ]
    assert _narration_ids(stashed) == []
    assert _narration_ids(restored) == [row_id]

    # The generated dependencies track the currently buildable rows. A stash-only
    # narration row therefore contributes no source descriptors or media needs.
    stashed_dependencies = copy.deepcopy(dependencies)
    stashed_dependencies["document"]["textHash"] = _sha256(b"")
    stashed_dependencies["narrationTimingMaps"] = []
    stashed_dependencies["occurrenceResolutions"] = []
    stashed_dependencies["preparedMedia"] = []

    stashed_build = _compile_with_python_bridge(
        tmp_path, stashed, stashed_dependencies, "stashed"
    )
    restored_build = _compile_with_python_bridge(
        tmp_path, restored, dependencies, "restored"
    )
    stashed_references = {
        need["mediaReferenceId"] for need in stashed_build["needs"]["requirements"]
    }
    restored_references = {
        need["mediaReferenceId"] for need in restored_build["needs"]["requirements"]
    }

    assert media_reference_id not in stashed_references
    assert media_reference_id in restored_references
