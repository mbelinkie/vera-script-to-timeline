"""Accepted Sorting content reaches the same narration and compiler consumers."""

# The local Python package has no py.typed marker; this test exercises its runtime API.
# mypy: disable-error-code=import-untyped

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_v2_build import PreparedProofBuildV2

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json"

_AUTHORING_SCRIPT = r"""
import { createHash } from "node:crypto";
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

const api = await import(new URL("authoring-v2.ts", sourceDirectory));
const { compileTimelineV2, resolveMediaRequirementsV2 } = await import(
  new URL("compiler-core-v2.ts", sourceDirectory)
);
const { exportPrompter } = await import(new URL("prompter-export.ts", sourceDirectory));
const input = JSON.parse((await import("node:fs")).readFileSync(0, "utf8"));
const id = (n) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const hash = (value) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
function row(n, text) {
  return {
    id: id(n), type: "narration", orderKey: `${n}`, text,
    tokens: [{ id: id(n + 1000), value: text, startOffset: 0, endOffset: text.length }],
    primaryVisualSequence: { id: id(n + 2000), version: 1, slots: [{
      id: id(n + 3000), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active",
    notes: [], version: 1,
  };
}
function applyDocument(document, command) {
  const result = api.applyRowEditV2(document, document.rowEditRevision ?? 0, command);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  return result.document;
}
function applyTrial(trial, command) {
  const result = trial.apply(command);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
}
function narration(document, rowId) {
  const row = document.activeDraft.blocks.find((item) => item.id === rowId);
  if (row?.type !== "narration") throw new Error(`Missing narration row ${rowId}`);
  return row;
}
function rewritten(row) {
  const prefix = "EDIT ";
  return {
    ...row, text: prefix + row.text, version: row.version + 1,
    tokens: row.tokens.map((token) => ({
      ...token,
      startOffset: token.startOffset + prefix.length,
      endOffset: token.endOffset + prefix.length,
    })),
  };
}
const originalId = input.document.activeDraft.blocks.find(
  (block) => block.type === "narration"
)?.id;
if (!originalId) throw new Error("fixture narration row is missing");
let baseline = input.document;
for (const [number, text] of [[100, "world"], [200, "again"], [300, "third"]]) {
  const previous = baseline.activeDraft.blocks
    .filter((block) => block.type === "narration")
    .at(-1);
  if (!previous) throw new Error("baseline narration row is missing");
  baseline = applyDocument(baseline, {
    kind: "create_row",
    row: row(number, text),
    destination: { sectionId: null, afterRowId: previous.id, beforeRowId: null },
  });
}
baseline = applyDocument(baseline, {
  kind: "create_stash_note",
  row: row(400, "Saved"),
  bundleId: id(8400), sectionId: null, parentRowId: null, afterRowId: null,
  mode: "authored",
});
const dependencies = structuredClone(input.dependencies);
const originalTiming = dependencies.narrationTimingMaps.find(
  (item) => item.blockId === originalId
);
if (!originalTiming) throw new Error("fixture timing map is missing");
for (const number of [100, 200, 300]) {
  const addedRow = baseline.activeDraft.blocks.find((block) => block.id === id(number));
  if (addedRow?.type !== "narration") {
    throw new Error("seeded narration row is missing");
  }
  const timing = structuredClone(originalTiming);
  timing.blockId = addedRow.id;
  timing.blockRevision = addedRow.version;
  timing.textHash = hash(addedRow.text);
  timing.narrationAssetId = id(number + 1100);
  timing.audio.narrationAssetId = id(number + 1100);
  timing.audio.locator = `Builds/narration/${addedRow.text}.wav`;
  timing.tokens = addedRow.tokens.map((token, index) => ({
    ...timing.tokens[index], tokenId: token.id, startOffset: token.startOffset,
    endOffset: token.endOffset, quotedText: token.value,
  }));
  dependencies.narrationTimingMaps.push(timing);
}
dependencies.document.textHash = hash(
  baseline.activeDraft.blocks
    .filter((block) => block.type === "narration")
    .map((block) => block.text)
    .join("\n")
);

const gap = (afterRowId, beforeRowId) => ({ sectionId: null, afterRowId, beforeRowId });
function addSyntheticTimings(document, selectedDependencies) {
  const template = selectedDependencies.narrationTimingMaps[0];
  if (!template) throw new Error("fixture timing map is missing");
  const activeIds = new Set(
    document.activeDraft.blocks
      .filter((block) => block.type === "narration")
      .map((block) => block.id)
  );
  selectedDependencies.narrationTimingMaps = selectedDependencies.narrationTimingMaps
    .filter((item) => activeIds.has(item.blockId));
  let assetNumber = 5000;
  for (const block of document.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    if (
      selectedDependencies.narrationTimingMaps.some((item) => item.blockId === block.id)
    ) continue;
    const assetId = id(assetNumber++);
    const timing = structuredClone(template);
    timing.blockId = block.id;
    timing.blockRevision = block.version;
    timing.textHash = hash(block.text);
    timing.narrationAssetId = assetId;
    timing.audio.narrationAssetId = assetId;
    timing.audio.locator = `Builds/narration/${block.id}.wav`;
    timing.tokens = block.tokens
      .filter((token) => token.spoken !== false)
      .map((token, index) => ({
        ...timing.tokens[index], tokenId: token.id, startOffset: token.startOffset,
        endOffset: token.endOffset, quotedText: token.value,
      }));
    selectedDependencies.narrationTimingMaps.push(timing);
  }
}
function consumerResult(document, selectedDependencies) {
  const prompter = exportPrompter(document, {
    includeSectionNavigation: true,
    includeBeatNumbers: true,
  });
  const compiler = compileTimelineV2(document, selectedDependencies);
  const needs = resolveMediaRequirementsV2(document, {
    timing: selectedDependencies.narrationTimingMaps,
    defaults: selectedDependencies.authoringDefaults,
    sourceDescriptors: selectedDependencies.occurrenceResolutions,
    frameRate: selectedDependencies.timeline.frameRate,
  });
  const diagnostics = (value) =>
    (value.diagnostics ?? value.errors ?? []).map(({ code, entityId }) => ({
      code, entityId,
    }));
  return {
    prompter: {
      ok: prompter.ok,
      expectedText: prompter.ok
        ? prompter.sidecar.beats.map((beat) => beat.expectedText)
        : [],
    },
    compiler: { ok: compiler.ok, diagnostics: diagnostics(compiler) },
    needs: { ok: needs.ok, diagnostics: diagnostics(needs) },
  };
}
function saveResult(document) {
  const serialized = api.serializeAuthoringDocumentV2(document);
  const loaded = api.deserializeAuthoringDocumentV2(serialized);
  if (!loaded.ok) throw new Error("selected Sorting document did not reload");
  const validation = api.validateScriptDocumentV2(loaded.document);
  if (!validation.valid) throw new Error(JSON.stringify(validation.diagnostics));
  const selectedDependencies = structuredClone(dependencies);
  selectedDependencies.document.textHash = hash(
    loaded.document.activeDraft.blocks
      .filter((block) => block.type === "narration")
      .map((block) => block.text)
      .join("\n")
  );
  // Give trial-created active rows timing so refusals expose stale edited rows.
  addSyntheticTimings(loaded.document, selectedDependencies);
  return {
    serialized,
    dependenciesSerialized: JSON.stringify(selectedDependencies),
    consumers: consumerResult(loaded.document, selectedDependencies),
  };
}
const baselineSerialized = api.serializeAuthoringDocumentV2(baseline);
const outcomes = {};
for (const outcome of ["all", "edits_only", "sorting_only", "discard"]) {
  const trial = api.createSortingTrialV2(baseline);
  applyTrial(trial, {
    kind: "create_row", row: row(700, "Trial"), destination: gap(id(300), null),
  });
  applyTrial(trial, {
    kind: "move_rows", rowIds: [originalId], destination: gap(id(700), null),
  });
  applyTrial(trial, {
    kind: "place_stash_rows", rowIds: [id(400)], destination: gap(id(200), id(300)),
  });
  applyTrial(trial, {
    kind: "edit_row", rowId: originalId,
    row: rewritten(narration(trial.document, originalId)),
  });
  applyTrial(trial, {
    kind: "edit_row", rowId: id(400),
    row: rewritten(narration(trial.document, id(400))),
  });
  applyTrial(trial, { kind: "delete_rows", rowIds: [id(100)] });
  trial.preview();
  const resumed = api.resumeSortingTrialV2(trial.serialize());
  resumed.returnToSorting();
  const result = outcome === "discard"
    ? resumed.discard(baseline)
    : resumed.accept(baseline, outcome);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  outcomes[outcome] = saveResult(result.document);
}
process.stdout.write(JSON.stringify({
  baselineSerialized, outcomes,
  ids: {
    original: originalId, deleted: id(100), retained: id(200),
    retainedSecond: id(300),
    parked: id(400), created: id(700),
  },
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


def _sorting_outcomes(fixture: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(
        [_node(), "--input-type=module", "-e", _AUTHORING_SCRIPT, str(ROOT)],
        input=json.dumps(fixture).encode("utf-8"),
        capture_output=True,
        check=False,
        cwd=ROOT,
        timeout=60,
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


def _prepared_compile(
    tmp_path: Path, document_json: str, dependencies_json: str, label: str
) -> dict[str, Any]:
    document_path = tmp_path / f"{label}-script-document-v2.json"
    dependencies_path = tmp_path / f"{label}-compiler-dependencies-v2.json"
    document_path.write_text(document_json, encoding="utf-8")
    dependencies_path.write_text(dependencies_json, encoding="utf-8")
    build = PreparedProofBuildV2.__new__(PreparedProofBuildV2)
    build.node = _node()
    build.document_path = document_path
    build.dependencies_path = dependencies_path
    build.inputs = {
        "document": {"sha256": _sha256(document_path.read_bytes())},
        "dependencies": {"sha256": _sha256(dependencies_path.read_bytes())},
    }
    try:
        return {"ok": True, "value": PreparedProofBuildV2._compile(build)}
    except Exception as error:
        return {"ok": False, "error": str(error)}


@pytest.mark.slow
def test_sorting_outcomes_reach_python_and_typescript_consumers(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    generated = _sorting_outcomes(fixture)
    baseline = json.loads(generated["baselineSerialized"])
    outcomes = {
        name: {**result, "document": json.loads(result["serialized"])}
        for name, result in generated["outcomes"].items()
    }
    ids = generated["ids"]

    assert outcomes["all"]["document"]["activeDraft"]["blocks"]
    assert outcomes["edits_only"]["document"]["activeDraft"]["blocks"]
    assert set(_narration_ids(outcomes["all"]["document"])) == {
        ids["retained"],
        ids["parked"],
        ids["retainedSecond"],
        ids["created"],
        ids["original"],
    }
    assert set(_narration_ids(outcomes["edits_only"]["document"])) == {
        ids["original"],
        ids["retained"],
        ids["retainedSecond"],
        ids["created"],
    }
    assert set(_narration_ids(outcomes["sorting_only"]["document"])) == {
        ids["original"],
        ids["deleted"],
        ids["retained"],
        ids["retainedSecond"],
        ids["parked"],
    }
    assert set(_narration_ids(outcomes["discard"]["document"])) == {
        ids["original"],
        ids["deleted"],
        ids["retained"],
        ids["retainedSecond"],
    }

    all_document = outcomes["all"]["document"]
    edits_document = outcomes["edits_only"]["document"]
    sorting_document = outcomes["sorting_only"]["document"]
    discard_document = outcomes["discard"]["document"]
    parked_all = next(
        block
        for block in all_document["activeDraft"]["blocks"]
        if block["id"] == ids["parked"]
    )
    parked_edits = next(
        row
        for stash in edits_document["stash"]
        for row in stash["rows"]
        if row["id"] == ids["parked"]
    )
    assert parked_all["text"] == "EDIT Saved"
    assert parked_edits["text"] == "EDIT Saved"
    assert all(
        block["id"] != ids["parked"]
        for block in edits_document["activeDraft"]["blocks"]
    )
    assert all(
        block["id"] != ids["deleted"] for block in all_document["activeDraft"]["blocks"]
    )
    assert all(
        block["id"] != ids["deleted"]
        for block in edits_document["activeDraft"]["blocks"]
    )
    sorting_parked = next(
        block
        for block in sorting_document["activeDraft"]["blocks"]
        if block["id"] == ids["parked"]
    )
    baseline_parked = next(
        row
        for stash in baseline["stash"]
        for row in stash["rows"]
        if row["id"] == ids["parked"]
    )
    assert sorting_parked["text"] == baseline_parked["text"] == "Saved"
    assert sorting_parked["stashOrigin"]["returnEligible"] is True
    assert parked_all["stashOrigin"]["returnEligible"] is False
    assert (
        next(
            block
            for block in sorting_document["activeDraft"]["blocks"]
            if block["id"] == ids["original"]
        )["text"]
        == "hello"
    )
    assert discard_document == baseline

    for name in ("all", "edits_only"):
        consumers = outcomes[name]["consumers"]
        assert consumers["prompter"]["ok"] is True
        assert consumers["compiler"]["ok"] is True
        assert consumers["needs"]["ok"] is False
        assert any(
            item["entityId"] == ids["original"] and item["code"] == "STALE_TIMING_MAP"
            for item in consumers["needs"]["diagnostics"]
        )
        prepared = _prepared_compile(
            tmp_path,
            outcomes[name]["serialized"],
            outcomes[name]["dependenciesSerialized"],
            name,
        )
        assert prepared["ok"] is False

    for name in ("sorting_only", "discard"):
        consumers = outcomes[name]["consumers"]
        expected_text = ["hello", "world", "again", "third"]
        if name == "sorting_only":
            expected_text.insert(3, "Saved")
        assert consumers["prompter"]["expectedText"] == expected_text
        assert consumers["compiler"]["ok"] is True
        assert consumers["needs"]["ok"] is True
        prepared = _prepared_compile(
            tmp_path,
            outcomes[name]["serialized"],
            outcomes[name]["dependenciesSerialized"],
            name,
        )
        assert prepared["ok"] is True
        assert prepared["value"]["result"]["ok"] is True
        assert prepared["value"]["needs"]["ok"] is True
