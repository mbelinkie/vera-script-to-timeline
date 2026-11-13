/** Pure commands for placing an immutable Research clip snapshot in the active Draft. */
import { randomUUID } from "node:crypto";

import type { RowGapV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import {
  createResearchClipOccurrenceV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";
import { applyRowEditV2 } from "./authoring-v2-rows.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";

/** Exact gap after an active row, never an identically named Stash row or section. */
export function destinationAfterDraftRowV2(
  document: ScriptDocumentV2,
  afterRowId: string,
): RowGapV2 {
  const blocks = document.activeDraft.blocks;
  const index = blocks.findIndex((block) => block.id === afterRowId && block.type !== "section");
  if (index < 0) throw new Error("The after-row ID must name an active script row.");

  let sectionId: string | null = null;
  for (let position = 0; position <= index; position += 1) {
    const block = blocks[position]!;
    if (block.type === "section") sectionId = block.id;
  }
  const next = blocks[index + 1];
  return {
    sectionId,
    afterRowId,
    beforeRowId: next && next.type !== "section" ? next.id : null,
  };
}

/** A rejected command never mutates the input script or the Research record. */
export function insertLoggedResearchClipV2(
  document: ScriptDocumentV2,
  candidate: ResearchLoggedCandidateInputV2,
  afterRowId: string,
  makeId: () => string = randomUUID,
): ScriptDocumentV2 {
  const before = validateScriptDocumentV2(document);
  if (!before.valid) {
    throw new Error(`Script validation failed: ${problems(before.diagnostics)}`);
  }
  const destination = destinationAfterDraftRowV2(document, afterRowId);
  const row = createResearchClipOccurrenceV2({
    rowId: makeId(), payloadId: makeId(), orderKey: `research-${makeId()}`,
    candidate,
    // Intentionally unresolved: no invented frame binding or selected duration.
  });
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, {
    kind: "create_row", row, destination,
  });
  if (!result.ok) {
    throw new Error(`Script refused insertion: ${problems(result.diagnostics)}`);
  }
  const after = validateScriptDocumentV2(result.document);
  if (!after.valid) {
    throw new Error(`Script validation failed after insertion: ${problems(after.diagnostics)}`);
  }
  return result.document;
}

function problems(diagnostics: readonly { code: string; message: string; severity?: string }[]): string {
  return diagnostics.filter((item) => item.severity !== "warning")
    .map((item) => `${item.code}: ${item.message}`).join("; ");
}

export function formatClipTime(ms: number): string {
  if (!Number.isSafeInteger(ms) || ms < 0) throw new RangeError("Invalid clip time.");
  const seconds = Math.floor(ms / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:` +
    `${String(seconds % 60).padStart(2, "0")}.${String(ms % 1000).padStart(3, "0")}`;
}

/** Each returned clip gets one safe-to-print line, without altering its source text. */
export function formatLoggedResearchClipV2(clip: ResearchLoggedCandidateInputV2): string {
  const oneLine = (value: string): string => [...value].map((char) => {
    const code = char.codePointAt(0)!;
    return code < 32 || (code >= 127 && code <= 159) ? " " : char;
  }).join("").replace(/\s+/gu, " ").trim();
  const words = oneLine(clip.englishText).split(/\s+/u).filter(Boolean).slice(0, 12).join(" ");
  return `${clip.id} | ${oneLine(clip.video.title)} | ${words} | ` +
    `${formatClipTime(clip.selection.exportStartMs)}–${formatClipTime(clip.selection.exportEndMs)}`;
}
