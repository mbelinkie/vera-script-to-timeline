import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { applyRowEditV2, validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";

import { applyExtrasStorageOperation, parseExtrasStorageCommand } from "../src/extras-operations.js";
import { documentFor } from "./helpers.js";

const id = (value: number) => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const fixturePath = fileURLToPath(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url));

function typedDraft() {
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as { document: ScriptDocumentV2 };
  const row = structuredClone(fixture.document.activeDraft.blocks[0]) as NarrationBlockV2;
  const document = documentFor(id(1));
  const first = { type: "section" as const, id: id(5000), title: "First", orderKey: "1", version: 1 };
  const second = { type: "section" as const, id: id(5001), title: "Second", orderKey: "2", version: 1 };
  const third = { type: "section" as const, id: id(5002), title: "Third", orderKey: "3", version: 1 };
  const anchor = { kind: "word" as const, anchor: {
    blockId: row.id, tokenId: row.tokens[0]!.id, affinity: "before" as const,
    quotedWord: row.tokens[0]!.value, anchorVersion: 1,
  } };
  const citation: SupportingItemV2 = {
    id: id(6000), version: 1, orderKey: "citation", role: "citation", content: "Source evidence",
    placement: { kind: "point", anchor }, displayAttachment: anchor,
  };
  document.activeDraft.blocks = [first, row, second, third];
  document.activeDraft.supportingItems = [citation];
  return { document, row, citation, first, second, third };
}

describe("Extras whole-row command allowlist", () => {
  const destination = { sectionId: null, afterRowId: null, beforeRowId: null };
  const accepted = [
    { kind: "stash_rows", rowIds: [id(11)], bundleId: id(12) },
    { kind: "stash_rows", rowIds: [id(11)], bundleId: id(12), destination: { ...destination, parentRowId: null } },
    { kind: "restore_stash", bundleId: id(12), destination },
    { kind: "restore_stash_rows", rowIds: [id(11)], destination },
    { kind: "place_stash_rows", rowIds: [id(11)], destination, includeDescendants: false },
  ];

  it("accepts only the four exact, bounded v2 Stash-backed command shapes", () => {
    for (const command of accepted) expect(parseExtrasStorageCommand(command)).toEqual(command);
    const rejected: unknown[] = [
      null, [], "stash_rows", {},
      { kind: "delete_rows", rowIds: [id(11)] },
      { kind: "edit_row", rowId: id(11), row: {} },
      { kind: "create_stash_note", row: {} },
      { kind: "stash_rows", rowIds: [id(11)], bundleId: id(12), actorId: id(99) },
      { kind: "stash_rows", rowIds: [id(11)], bundleId: "not-uuid" },
      { kind: "stash_rows", rowIds: [id(11), id(11)], bundleId: id(12) },
      { kind: "stash_rows", rowIds: [id(11), "not-uuid"], bundleId: id(12) },
      { kind: "stash_rows", rowIds: [id(11)], bundleId: id(12), destination },
      { kind: "stash_rows", rowIds: [id(11)], bundleId: id(12), destination: { ...destination, parentRowId: null, inheritedRole: "producer" } },
      { kind: "restore_stash", bundleId: id(12) },
      { kind: "restore_stash", bundleId: id(12), destination: { ...destination, arbitrary: true } },
      { kind: "restore_stash", bundleId: id(12), destination: { ...destination, afterRowId: id(11), beforeRowId: id(11) } },
      { kind: "restore_stash_rows", rowIds: [id(11)], destination: { ...destination, sectionId: 12 } },
      { kind: "place_stash_rows", rowIds: [id(11)], destination, includeDescendants: "false" },
      { ...accepted[0], __proto__: null }, // a null-prototype command is not a JSON object
      Object.assign(Object.create(null) as Record<string, unknown>, accepted[0]),
      Object.assign([], accepted[0]),
    ];
    for (const command of rejected) {
      const original = documentFor(id(1));
      const result = applyExtrasStorageOperation(original, command);
      expect(result.ok, JSON.stringify(command)).toBe(false);
      expect(result.diagnostics[0]?.code, JSON.stringify(command)).toBe("EXTRAS_COMMAND_INVALID");
      expect(result.document).toBe(original);
    }
  });

  it("rejects getters, symbols, sparse arrays and prototype-pollution keys without executing payloads", () => {
    let reads = 0;
    const getter = Object.defineProperty({ kind: "stash_rows", bundleId: id(12) }, "rowIds", {
      enumerable: true, get: () => { reads++; throw new Error("must not run"); },
    });
    const sparse = new Array<string>(2);
    sparse[1] = id(11);
    const getterArray = [id(11)];
    Object.defineProperty(getterArray, "0", {
      enumerable: true, get: () => { reads++; throw new Error("must not run"); },
    });
    const commands: unknown[] = [
      getter,
      { kind: "stash_rows", bundleId: id(12), rowIds: sparse },
      { kind: "stash_rows", bundleId: id(12), rowIds: getterArray },
      { ...accepted[0], [Symbol("forged")]: "hidden" },
      new Proxy(accepted[0]!, { get: () => { reads++; throw new Error("unsafe proxy"); } }),
      JSON.parse(`{"kind":"stash_rows","rowIds":["${id(11)}"],"bundleId":"${id(12)}","__proto__":{}}`) as unknown,
      { kind: "restore_stash", bundleId: id(12), destination: { ...destination, constructor: "unsafe" } },
    ];
    const document = documentFor(id(1));
    for (const command of commands) {
      const result = applyExtrasStorageOperation(document, command);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(document);
    }
    expect(reads).toBe(1); // The Proxy's get trap cannot be suppressed; it is caught as an invalid command.
  });
});

describe("Extras pure storage and explicit restoration", () => {
  it("parks a typed cited visual row, then restores it into a different section without lost content or new identities", () => {
    const { document, row, citation, first, second, third } = typedDraft();
    const before = structuredClone(document);
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const parked = applyExtrasStorageOperation(document, {
      kind: "stash_rows", rowIds: [row.id], bundleId: id(7000),
    });
    expect(parked.ok, JSON.stringify(parked.diagnostics)).toBe(true);
    expect(document).toEqual(before);
    expect(parked.document.activeDraft.blocks).toEqual([first, second, third]);
    expect(parked.document.activeDraft.supportingItems).toEqual([]);
    expect(parked.document.stash?.[0]?.rows).toEqual([row]);
    expect(parked.document.stash?.[0]?.supportingItems).toEqual([citation]);
    expect(parked.document.stash?.[0]?.originalGap).toEqual({ sectionId: first.id, afterRowId: null, beforeRowId: null });
    expect(parked.document.extras).toEqual([]);
    expect(parked.document.rowEditRevision).toBe(1);
    const reloaded = JSON.parse(JSON.stringify(parked.document)) as ScriptDocumentV2;
    const restored = applyExtrasStorageOperation(reloaded, {
      kind: "restore_stash", bundleId: id(7000),
      destination: { sectionId: third.id, afterRowId: null, beforeRowId: null },
    });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(restored.document.activeDraft.blocks).toEqual([first, second, third, row]);
    expect(restored.document.activeDraft.supportingItems).toEqual([citation]);
    expect(restored.document.stash).toEqual([]);
    expect(restored.document.extras).toEqual([]);
    expect(restored.document.rowEditRevision).toBe(2);
    expect(JSON.parse(JSON.stringify(restored.document))).toEqual(restored.document);
  });

  it("refuses missing targets and stale/unsafe exact Draft gaps with no changed bytes", () => {
    const { document, row, first, third } = typedDraft();
    const stale = applyExtrasStorageOperation(document, {
      kind: "restore_stash", bundleId: id(7000),
      destination: { sectionId: third.id, afterRowId: null, beforeRowId: null },
    });
    expect(stale.ok).toBe(false);
    expect(stale.document).toBe(document);

    const parked = applyExtrasStorageOperation(document, { kind: "stash_rows", rowIds: [row.id], bundleId: id(7000) });
    expect(parked.ok).toBe(true);
    const bytes = JSON.stringify(parked.document);
    for (const operation of [
      { kind: "stash_rows", rowIds: [row.id], bundleId: id(7001) },
      { kind: "stash_rows", rowIds: [id(9000)], bundleId: id(7001) },
      { kind: "restore_stash", bundleId: id(8000), destination: { sectionId: first.id, afterRowId: null, beforeRowId: null } },
      { kind: "restore_stash", bundleId: id(7000), destination: { sectionId: third.id, afterRowId: id(9000), beforeRowId: null } },
      { kind: "place_stash_rows", rowIds: [id(9000)], destination: { sectionId: third.id, afterRowId: null, beforeRowId: null } },
    ]) {
      const refused = applyExtrasStorageOperation(parked.document, operation);
      expect(refused.ok, JSON.stringify(operation)).toBe(false);
      expect(refused.document).toBe(parked.document);
      expect(JSON.stringify(parked.document)).toBe(bytes);
    }
    const staleKey = applyRowEditV2(document, 1, { kind: "stash_rows", rowIds: [row.id], bundleId: id(7001) });
    expect(staleKey.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(staleKey.document).toBe(document);
  });

  it("refuses a supporting-item anchor crossing a selected row boundary, without losing either row", () => {
    const { document, row, first } = typedDraft();
    const other = structuredClone(row);
    other.id = id(9000);
    other.tokens = other.tokens.map((token, index) => ({ ...token, id: id(9100 + index) }));
    other.primaryVisualSequence!.id = id(9200);
    other.primaryVisualSequence!.slots = other.primaryVisualSequence!.slots.map((slot, index) => ({ ...slot, id: id(9300 + index) }));
    for (const slot of other.primaryVisualSequence!.slots) {
      if (slot.kind === "content" && slot.payload.kind === "visual") slot.payload.payloadId = id(9350);
    }
    // This fixture demonstrates a cross-boundary anchor without changing the preserved content of the selected row.
    document.activeDraft.blocks.splice(2, 0, other);
    document.activeDraft.supportingItems.push({
      id: id(9400), orderKey: "cross-boundary", version: 1, role: "citation", content: "Two rows",
      placement: { kind: "point", anchor: { kind: "between_blocks", beforeBlockId: row.id, afterBlockId: other.id } },
    });
    const validation = validateScriptDocumentV2(document);
    expect(validation.valid, JSON.stringify(validation.diagnostics)).toBe(true);
    const before = JSON.stringify(document);
    const result = applyExtrasStorageOperation(document, { kind: "stash_rows", rowIds: [row.id], bundleId: id(7000) });
    expect(result.ok).toBe(false);
    expect(result.document).toBe(document);
    expect(result.diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    expect(document.activeDraft.blocks[0]).toEqual(first);
    expect(JSON.stringify(document)).toBe(before);
  });
});
