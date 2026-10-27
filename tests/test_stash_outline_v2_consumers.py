"""Mixed saved Stash items stay outside active narration until placed."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from vera_timeline_agent.narration.service import NarrationService

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json"
CLIP_FIXTURE = (
    ROOT
    / "tests/data/authoring_v2/issue_173/compiler/selected-clip-ntsc.input.golden.json"
)

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
const { compileTimelineV2, resolveMediaRequirementsV2 } = await import(
  new URL("compiler-core-v2.ts", sourceDirectory)
);
const { exportPrompter } = await import(new URL("prompter-export.ts", sourceDirectory));
const input = JSON.parse(readFileSync(0, "utf8"));
let document = input.document;

function apply(command) {
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  document = result.document;
}

function savedSnapshot() {
  const serialized = JSON.stringify(document);
  const reloaded = JSON.parse(serialized);
  const validation = validateScriptDocumentV2(reloaded);
  if (!validation.valid) throw new Error(JSON.stringify(validation.diagnostics));
  return serialized;
}

function consumerSnapshot(value) {
  const prompter = exportPrompter(value, {
    includeSectionNavigation: true,
    includeBeatNumbers: true,
  });
  const compiled = compileTimelineV2(value, input.dependencies);
  const needs = resolveMediaRequirementsV2(value, {
    timing: input.dependencies.narrationTimingMaps,
    ...(input.dependencies.narrationBoundaryEvidence
      ? { boundaryEvidence: input.dependencies.narrationBoundaryEvidence }
      : {}),
    defaults: input.dependencies.authoringDefaults,
    sourceDescriptors: input.dependencies.occurrenceResolutions,
    frameRate: input.dependencies.timeline.frameRate,
  });
  if (!prompter.ok || !compiled.ok || !needs.ok) {
    throw new Error(JSON.stringify({ prompter, compiled, needs }));
  }
  return {
    prompterText: prompter.text,
    prompterSidecarJson: prompter.sidecarJson,
    timeline: compiled.manifest.timeline,
    events: compiled.manifest.events,
    requirements: needs.requirements,
    mediaDurationFrames: needs.durationFrames,
  };
}

const baselineActiveDraft = structuredClone(document.activeDraft);
const baselineConsumers = consumerSnapshot(document);
apply({
  kind: "create_stash_section",
  sectionId: input.sectionId,
  title: "Saved ideas",
});
document.activeDraft.blocks.push(input.savedRow);
apply({
  kind: "stash_rows",
  rowIds: [input.savedRow.id],
  bundleId: input.savedRowBundleId,
});
if (JSON.stringify(document.activeDraft) !== JSON.stringify(baselineActiveDraft)) {
  throw new Error("Stashing the ordinary row changed the active draft.");
}
const rowSavedConsumers = consumerSnapshot(document);
if (JSON.stringify(rowSavedConsumers) !== JSON.stringify(baselineConsumers)) {
  throw new Error("An ordinary saved row changed consumer output.");
}
apply({
  kind: "create_stash_note",
  bundleId: input.noteBundleId,
  row: input.noteRow,
  sectionId: input.sectionId,
  parentRowId: null,
  afterRowId: null,
});
const noteBundle = document.stash?.find((bundle) => bundle.id === input.noteBundleId);
if (!noteBundle) throw new Error("The compact note bundle is missing.");
apply({
  kind: "create_stash_clip",
  bundleId: input.clipBundleId,
  row: input.clipRow,
  sectionId: input.sectionId,
  parentRowId: input.noteRow.id,
  afterRowId: null,
});
apply({
  kind: "create_stash_note",
  bundleId: input.citationNoteBundleId,
  row: input.citationNoteRow,
  sectionId: input.sectionId,
  parentRowId: null,
  afterRowId: input.noteRow.id,
  mode: "authored",
});
const citationNoteBundle = document.stash?.find(
  (bundle) => bundle.id === input.citationNoteBundleId,
);
if (!citationNoteBundle) throw new Error("The citation note bundle is missing.");
// Seed persisted row-local data; this proof does not add citation authoring.
citationNoteBundle.supportingItems.push(input.citation);
apply({
  kind: "set_stash_outline",
  entries: [
    {
      rowId: input.noteRow.id,
      kind: "note",
      parentRowId: null,
      sectionId: input.sectionId,
    },
    {
      rowId: input.clipRow.id,
      kind: "clip",
      parentRowId: input.noteRow.id,
      sectionId: input.sectionId,
    },
    {
      rowId: input.citationNoteRow.id,
      kind: "note",
      parentRowId: null,
      sectionId: input.sectionId,
    },
    {
      rowId: input.savedRow.id,
      kind: "row",
      parentRowId: null,
      sectionId: input.sectionId,
    },
  ],
});
const savedSerialized = savedSnapshot();
if (JSON.stringify(document.activeDraft) !== JSON.stringify(baselineActiveDraft)) {
  throw new Error("Saving the mixed Stash outline changed the active draft.");
}
const mixedSavedConsumers = consumerSnapshot(document);
if (JSON.stringify(mixedSavedConsumers) !== JSON.stringify(baselineConsumers)) {
  throw new Error("The mixed saved outline changed consumer output.");
}

// After placement, the all-direction note has no speech timing and can yield
// NARRATION_DURATION_UNKNOWN, so the compiler proof stays on the saved outline.
apply({
  kind: "place_stash_rows",
  rowIds: [input.noteRow.id, input.citationNoteRow.id],
  destination: {
    sectionId: null,
    afterRowId: input.activeRowId,
    beforeRowId: null,
  },
});
const placedSerialized = savedSnapshot();

apply({
  kind: "stash_rows",
  rowIds: [input.noteRow.id, input.clipRow.id, input.citationNoteRow.id],
  bundleId: input.returnBundleId,
});
const returnedSerialized = savedSnapshot();
const returnedConsumers = consumerSnapshot(document);
if (JSON.stringify(returnedConsumers) !== JSON.stringify(baselineConsumers)) {
  throw new Error("Returning the selected Stash branch changed consumer output.");
}

process.stdout.write(
  JSON.stringify({
    baselineActiveDraft,
    baselineConsumers,
    rowSavedConsumers,
    mixedSavedConsumers,
    returnedConsumers,
    savedSerialized,
    placedSerialized,
    returnedSerialized,
  }),
);
"""


def _id(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012x}"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js 24.19.0 must be available on PATH for the authoring bridge"
        )
    return node


def _clone_with_unique_ids(row: dict[str, Any], first_id: int) -> dict[str, Any]:
    cloned = copy.deepcopy(row)
    next_id = first_id

    def rewrite(value: Any) -> None:
        nonlocal next_id
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"id", "payloadId"} and isinstance(child, str):
                    value[key] = _id(next_id)
                    next_id += 1
                else:
                    rewrite(child)
        elif isinstance(value, list):
            for child in value:
                rewrite(child)

    rewrite(cloned)
    return cloned


def _input_payload() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document = fixture["document"]
    active_row = next(
        block
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    )
    active_row_id = active_row["id"]
    stash_section_id = _id(9103)
    saved_row = _clone_with_unique_ids(active_row, 9200)
    saved_row["orderKey"] = "a1"
    saved_row["text"] = "saved-row-only"
    saved_row["tokens"] = [
        {
            **saved_row["tokens"][0],
            "value": saved_row["text"],
            "startOffset": 0,
            "endOffset": len(saved_row["text"]),
        }
    ]
    note_row = _clone_with_unique_ids(active_row, 9300)
    note_row["text"] = "stash-only"
    note_row["tokens"] = [
        {
            **note_row["tokens"][0],
            "value": note_row["text"],
            "startOffset": 0,
            "endOffset": len(note_row["text"]),
        }
    ]
    note_row["orderKey"] = "a0"
    citation_note_row = _clone_with_unique_ids(active_row, 9700)
    citation_note_row["text"] = "citation-only"
    citation_note_row["tokens"] = [
        {
            **citation_note_row["tokens"][0],
            "value": citation_note_row["text"],
            "startOffset": 0,
            "endOffset": len(citation_note_row["text"]),
        }
    ]
    citation_note_row["orderKey"] = "a0"
    note_token = citation_note_row["tokens"][0]
    citation_anchor = {
        "blockId": citation_note_row["id"],
        "tokenId": note_token["id"],
        "affinity": "before",
        "quotedWord": note_token["value"],
        "anchorVersion": 1,
    }
    citation_attachment = {"kind": "word", "anchor": citation_anchor}
    citation = {
        "id": _id(9600),
        "version": 1,
        "orderKey": "stash-citation",
        "role": "citation",
        "content": "Citation stored with the authored Stash note",
        "placement": {"kind": "point", "anchor": citation_attachment},
        "displayAttachment": citation_attachment,
    }

    clip_document = json.loads(CLIP_FIXTURE.read_text(encoding="utf-8"))["document"]
    clip_row = next(
        block
        for block in clip_document["activeDraft"]["blocks"]
        if block["type"] == "visual_only"
    )
    clip_row = copy.deepcopy(clip_row)
    clip_row["id"] = _id(9400)
    clip_row["orderKey"] = "a0"
    clip_row["payload"]["payloadId"] = _id(9401)

    return {
        "document": document,
        "dependencies": fixture["dependencies"],
        "sectionId": stash_section_id,
        "activeRowId": active_row_id,
        "savedRow": saved_row,
        "noteRow": note_row,
        "citationNoteRow": citation_note_row,
        "citation": citation,
        "clipRow": clip_row,
        "savedRowBundleId": _id(9500),
        "noteBundleId": _id(9501),
        "clipBundleId": _id(9502),
        "returnBundleId": _id(9503),
        "citationNoteBundleId": _id(9504),
    }


def _authoring_round_trip(payload: dict[str, Any]) -> dict[str, Any]:
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


def _narration_ids(document: dict[str, Any]) -> list[str]:
    calls: list[str] = []
    service = NarrationService.__new__(NarrationService)

    def record(block: dict[str, Any], *, _provider_error: object = None) -> Any:
        calls.append(block["id"])
        return SimpleNamespace(extra={}, failure_reason=None)

    with patch.object(service, "process_block", side_effect=record):
        service.process_document(document)
    return calls


def _payload_ids(row: dict[str, Any]) -> set[str]:
    if row["type"] == "visual_only":
        return {row["payload"]["payloadId"]}
    return {
        slot["payload"]["payloadId"]
        for slot in row.get("primaryVisualSequence", {}).get("slots", [])
        if slot["kind"] == "content" and slot["payload"].get("kind") == "visual"
    }


def test_stash_outline_consumers_exclude_saved_items_until_placed() -> None:
    payload = _input_payload()
    operation = _authoring_round_trip(payload)
    saved = json.loads(operation["savedSerialized"])
    placed = json.loads(operation["placedSerialized"])
    returned = json.loads(operation["returnedSerialized"])

    note_id = payload["noteRow"]["id"]
    clip_id = payload["clipRow"]["id"]
    citation_note_id = payload["citationNoteRow"]["id"]
    saved_row_id = payload["savedRow"]["id"]
    active_row_id = payload["activeRowId"]
    section_id = payload["sectionId"]
    expected_outline = [
        {
            "rowId": note_id,
            "kind": "note",
            "parentRowId": None,
            "sectionId": section_id,
        },
        {
            "rowId": clip_id,
            "kind": "clip",
            "parentRowId": note_id,
            "sectionId": section_id,
        },
        {
            "rowId": citation_note_id,
            "kind": "note",
            "parentRowId": None,
            "sectionId": section_id,
        },
        {
            "rowId": saved_row_id,
            "kind": "row",
            "parentRowId": None,
            "sectionId": section_id,
        },
    ]

    assert saved["stashOutline"] == expected_outline
    assert saved["stashSections"] == [
        {"id": section_id, "title": "Saved ideas", "rowIds": []}
    ]
    saved_note_bundle = next(
        bundle for bundle in saved["stash"] if bundle["id"] == payload["noteBundleId"]
    )
    assert saved_note_bundle["supportingItems"] == []
    citation_note_bundle = next(
        bundle
        for bundle in saved["stash"]
        if bundle["id"] == payload["citationNoteBundleId"]
    )
    assert citation_note_bundle["supportingItems"] == [payload["citation"]]
    assert saved["activeDraft"] == operation["baselineActiveDraft"]
    assert section_id not in {block["id"] for block in saved["activeDraft"]["blocks"]}
    assert _narration_ids(saved) == [active_row_id]
    assert (
        operation["baselineConsumers"]
        == operation["rowSavedConsumers"]
        == operation["mixedSavedConsumers"]
        == operation["returnedConsumers"]
    )

    consumers = operation["mixedSavedConsumers"]
    for hidden_text in (
        payload["noteRow"]["text"],
        payload["citationNoteRow"]["text"],
        payload["savedRow"]["text"],
        "Saved ideas",
    ):
        assert hidden_text not in consumers["prompterText"]
        assert hidden_text not in consumers["prompterSidecarJson"]
    hidden_row_ids = {note_id, clip_id, citation_note_id, saved_row_id}
    hidden_payload_ids = _payload_ids(payload["noteRow"])
    hidden_payload_ids.update(_payload_ids(payload["clipRow"]))
    hidden_payload_ids.update(_payload_ids(payload["citationNoteRow"]))
    hidden_payload_ids.update(_payload_ids(payload["savedRow"]))
    assert all(
        event.get("provenance", {}).get("blockId") not in hidden_row_ids
        and event.get("provenance", {}).get("payloadId") not in hidden_payload_ids
        for event in consumers["events"]
    )
    assert all(
        requirement["payloadId"] not in hidden_payload_ids
        for requirement in consumers["requirements"]
    )

    active_blocks = placed["activeDraft"]["blocks"]
    active_ids = [block["id"] for block in active_blocks]
    assert section_id not in active_ids
    assert active_ids == [active_row_id, note_id, clip_id, citation_note_id]
    assert placed["stashOutline"] == [expected_outline[3]]
    assert placed["stashSections"] == saved["stashSections"]

    placed_note = next(block for block in active_blocks if block["id"] == note_id)
    assert placed_note["type"] == "narration"
    assert placed_note["tokens"]
    assert all(token.get("spoken") is False for token in placed_note["tokens"])
    assert placed["activeDraft"]["supportingItems"] == [payload["citation"]]

    placed_clip = next(block for block in active_blocks if block["id"] == clip_id)
    assert placed_clip["type"] == "visual_only"
    assert placed_clip["payload"] == payload["clipRow"]["payload"]
    assert placed_clip["visualOnlyTiming"] == payload["clipRow"]["visualOnlyTiming"]
    placed_citation_note = next(
        block for block in active_blocks if block["id"] == citation_note_id
    )
    assert placed_citation_note["type"] == "narration"
    assert all(
        token.get("spoken") is not False for token in placed_citation_note["tokens"]
    )
    assert _narration_ids(placed) == [active_row_id, citation_note_id]

    assert returned["stashOutline"] == expected_outline
    assert returned["stashSections"] == saved["stashSections"]
    assert returned["activeDraft"] == operation["baselineActiveDraft"]
    assert returned["activeDraft"]["supportingItems"] == []
    assert any(
        payload["citation"] in bundle["supportingItems"]
        and citation_note_id in {row["id"] for row in bundle["rows"]}
        for bundle in returned["stash"]
    )
    assert _narration_ids(returned) == [active_row_id]
