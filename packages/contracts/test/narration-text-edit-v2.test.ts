import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  createRowEditSessionV2,
  spliceNarrationTextV2,
  type NarrationTextReplacementV2,
  type RowEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";

const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const H = "now the harbor sleeps the harbor wakes";
const U = "cafe\u0301 🌊 שלום end";

function rowOf(text: string): NarrationBlockV2 {
  const tokens = [...text.matchAll(/[^\s[\]]+/gu)].map((match, index) => ({
    id: id(100 + index), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  }));
  return {
    type: "narration", id: id(10), orderKey: "narration-10", text, tokens,
    primaryVisualSequence: {
      id: id(300), version: 1,
      slots: [{
        id: id(301), kind: "content", relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval", version: 1,
      }],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function documentOf(row: NarrationBlockV2): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Narration edit",
    activeDraft: { blocks: [row], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

function edit(startOffset: number, endOffset: number, insertedText: string, seed = 2000): NarrationTextReplacementV2 {
  return { startOffset, endOffset, insertedText, editId: id(seed) };
}

function plan(row: NarrationBlockV2, command: NarrationTextReplacementV2, extraReserved: string[] = []) {
  return spliceNarrationTextV2(row, command, {
    documentId: id(1), revision: 0,
    reservedIds: new Set([...row.tokens.map((token) => token.id), id(1), id(2), id(10), id(300), id(301), ...extraReserved]),
  });
}

function outline(row: NarrationBlockV2): [string, string, number, number][] {
  return row.tokens.map((token) => [token.id, token.value, token.startOffset, token.endOffset]);
}

function editedRow(document: ScriptDocumentV2): NarrationBlockV2 {
  const block = document.activeDraft.blocks[0];
  if (!block || block.type !== "narration") throw new Error("Expected narration row");
  return block;
}

function apply(row: NarrationBlockV2, replacement: NarrationTextReplacementV2) {
  const session = createRowEditSessionV2(documentOf(row));
  const original = session.document;
  const result = session.apply({ kind: "edit_narration_text", rowId: row.id, ...replacement });
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expect(session.undoDepth).toBe(1);
  expect(session.revision).toBe(1);
  const undo = session.undo();
  expect(undo.ok).toBe(true);
  expect({ ...session.document, rowEditRevision: 0 }).toEqual({ ...original, rowEditRevision: 0 });
  return editedRow(result.document);
}

describe("#580 positional word identities (H matrix)", () => {
  it("H1 replaces only the second harbor, retaining its T6 ID rather than attaching it to old", () => {
    const source = rowOf(H);
    const old = structuredClone(source);
    const planned = plan(source, edit(26, 32, "old harbor"));
    expect(planned.ok).toBe(true);
    if (!planned.ok) return;
    expect(outline(planned.row)).toEqual([
      [id(100), "now", 0, 3], [id(101), "the", 4, 7], [id(102), "harbor", 8, 14],
      [id(103), "sleeps", 15, 21], [id(104), "the", 22, 25],
      [planned.createdTokenIds[0]!, "old", 26, 29], [id(105), "harbor", 30, 36],
      [id(106), "wakes", 37, 42],
    ]);
    expect(planned.createdTokenIds).toHaveLength(1);
    expect(planned.deletedTokenIds).toEqual([]);
    expect(source).toEqual(old);
    expect(outline(apply(source, edit(26, 32, "old harbor")))).toEqual(outline(planned.row));
  });

  it("H2 and H3 produce the same text but preserve the opposite occurrence IDs", () => {
    const source = rowOf(H);
    const h2 = plan(source, edit(4, 4, "the harbor ", 2002));
    const h3 = plan(source, edit(15, 15, "the harbor ", 2003));
    expect(h2.ok && h3.ok).toBe(true);
    if (!h2.ok || !h3.ok) return;
    expect(h2.row.text).toBe(h3.row.text);
    expect(outline(h2.row).map(([, value, start, end]) => [value, start, end])).toEqual(
      outline(h3.row).map(([, value, start, end]) => [value, start, end]),
    );
    expect(outline(h2.row)).toEqual([
      [id(100), "now", 0, 3], [h2.createdTokenIds[0]!, "the", 4, 7],
      [h2.createdTokenIds[1]!, "harbor", 8, 14], [id(101), "the", 15, 18],
      [id(102), "harbor", 19, 25], [id(103), "sleeps", 26, 32],
      [id(104), "the", 33, 36], [id(105), "harbor", 37, 43], [id(106), "wakes", 44, 49],
    ]);
    expect(outline(h3.row)).toEqual([
      [id(100), "now", 0, 3], [id(101), "the", 4, 7], [id(102), "harbor", 8, 14],
      [h3.createdTokenIds[0]!, "the", 15, 18], [h3.createdTokenIds[1]!, "harbor", 19, 25],
      [id(103), "sleeps", 26, 32], [id(104), "the", 33, 36],
      [id(105), "harbor", 37, 43], [id(106), "wakes", 44, 49],
    ]);
    expect(h2.createdTokenIds).toHaveLength(2);
    expect(h3.createdTokenIds).toHaveLength(2);
    expect(h2.createdTokenIds).not.toEqual(h3.createdTokenIds);
    expect(outline(apply(source, edit(4, 4, "the harbor ", 2002)))).toEqual(outline(h2.row));
    expect(outline(apply(source, edit(15, 15, "the harbor ", 2003)))).toEqual(outline(h3.row));
  });
});

describe("#580 UTF-16, Unicode and partial-word edits (U matrix)", () => {
  const cases: {
    name: string; replacement: NarrationTextReplacementV2;
    expected: (created: string[]) => [string, string, number, number][];
    deleted?: string[];
  }[] = [
    {
      name: "U1 prepending a word shifts all four original IDs",
      replacement: edit(0, 0, "le ", 2011),
      expected: (ids) => [[ids[0]!, "le", 0, 2], [id(100), "cafe\u0301", 3, 8], [id(101), "🌊", 9, 11], [id(102), "שלום", 12, 16], [id(103), "end", 17, 20]],
    },
    {
      name: "U2 removing combining accent preserves T1, without normalizing",
      replacement: edit(4, 5, "", 2012),
      expected: () => [[id(100), "cafe", 0, 4], [id(101), "🌊", 5, 7], [id(102), "שלום", 8, 12], [id(103), "end", 13, 16]],
    },
    {
      name: "U3 deleting an emoji and space discards T2, retaining the Hebrew cue word",
      replacement: edit(6, 9, "", 2013),
      expected: () => [[id(100), "cafe\u0301", 0, 5], [id(102), "שלום", 6, 10], [id(103), "end", 11, 14]],
      deleted: [id(101)],
    },
    {
      name: "U4 inserting a Hebrew word before T3 does not steal the original ID",
      replacement: edit(9, 9, "עולם ", 2014),
      expected: (ids) => [[id(100), "cafe\u0301", 0, 5], [id(101), "🌊", 6, 8], [ids[0]!, "עולם", 9, 13], [id(102), "שלום", 14, 18], [id(103), "end", 19, 22]],
    },
    {
      name: "U6 replacing decomposed cafe with composed café preserves T1 identity",
      replacement: edit(0, 5, "café", 2016),
      expected: () => [[id(100), "café", 0, 4], [id(101), "🌊", 5, 7], [id(102), "שלום", 8, 12], [id(103), "end", 13, 16]],
    },
  ];

  for (const testCase of cases) {
    it(testCase.name, () => {
      const source = rowOf(U);
      const planned = plan(source, testCase.replacement);
      expect(planned.ok).toBe(true);
      if (!planned.ok) return;
      expect(outline(planned.row)).toEqual(testCase.expected(planned.createdTokenIds));
      expect(planned.deletedTokenIds).toEqual(testCase.deleted ?? []);
      expect(outline(apply(source, testCase.replacement))).toEqual(outline(planned.row));
    });
  }

  it("U5 refuses a half emoji before changing the document or undo history", () => {
    const source = rowOf(U);
    expect(plan(source, edit(6, 7, "", 2015))).toMatchObject({ ok: false, code: "NARRATION_TEXT_SPAN_INVALID" });
    const initial = documentOf(source);
    const session = createRowEditSessionV2(initial);
    const result = session.apply({ kind: "edit_narration_text", rowId: source.id, ...edit(6, 7, "", 2015) });
    expect(result.ok).toBe(false);
    expect(result.document).toEqual(initial);
    expect(session.document).toEqual(initial);
    expect(session.undoDepth).toBe(0);
    expect(session.revision).toBe(0);
    expect(session.undo().ok).toBe(false);
  });

  it("retains a rewritten token's identity for an insertion inside a word", () => {
    const planned = plan(rowOf(U), edit(2, 2, "x", 2020));
    expect(planned.ok).toBe(true);
    if (planned.ok) {
      expect(planned.row.tokens[0]).toMatchObject({ id: id(100), value: "caxfe\u0301", startOffset: 0, endOffset: 6 });
      expect(planned.createdTokenIds).toEqual([]);
    }
  });

  it("keeps adjacent punctuation and repeated RTL words local, without Unicode normalization", () => {
    const source = rowOf("שלום, שלום 🌊 שלום");
    const result = plan(source, edit(6, 6, "שלום ", 2021));
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.row.tokens[0]!.value).toBe("שלום,");
      expect(result.row.tokens[1]!.id).not.toBe(id(101));
      expect(result.row.tokens[2]!.id).toBe(id(101));
      expect(result.row.tokens[3]!.id).toBe(id(102));
      expect(result.row.tokens[4]!.id).toBe(id(103));
    }
  });
});

describe("#580 strict atomic command gates", () => {
  it("rejects malformed commands, stale revisions, out-of-range and unpaired UTF-16 without an undo entry", () => {
    const source = rowOf(U);
    const initial = documentOf(source);
    const good = { kind: "edit_narration_text" as const, rowId: source.id, ...edit(0, 0, "new ") };
    const bad: unknown[] = [
      { ...good, surprise: true }, { ...good, editId: "not-a-uuid" },
      { ...good, rowId: 17 }, { ...good, insertedText: 42 },
      { ...good, startOffset: 0.5 }, { ...good, startOffset: -1 },
      { ...good, startOffset: 99 }, { ...good, endOffset: 999 },
      { ...good, startOffset: 8, endOffset: 6 },
      { ...good, insertedText: "\ud83c" },
      { ...good, rowId: id(9999) },
      { ...good, insertedText: "" },
    ];
    for (const command of bad) {
      const session = createRowEditSessionV2(initial);
      const result = session.apply(command as RowEditCommandV2);
      expect(result.ok, JSON.stringify(command)).toBe(false);
      expect(result.document).toEqual(initial);
      expect(session.document).toEqual(initial);
      expect(session.undoDepth).toBe(0);
    }
    const session = createRowEditSessionV2(initial);
    const stale = session.apply(good, 1);
    expect(stale.ok).toBe(false);
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(session.undoDepth).toBe(0);
    expect(applyRowEditV2(initial, 1, good).ok).toBe(false);
  });

  it("refuses ID collisions deterministically and leaves the original row unchanged", () => {
    const row = rowOf(H);
    const replacement = edit(4, 4, "new ", 2022);
    const first = plan(row, replacement);
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    const second = plan(row, replacement, [first.createdTokenIds[0]!]);
    expect(second).toMatchObject({ ok: false, code: "NARRATION_TEXT_ID_COLLISION" });
    expect(plan(row, replacement)).toEqual(first);
  });

  it("refuses edits inside nonspoken stage directions without changing flags or text", () => {
    const source = rowOf("listen [soft voice] now");
    source.tokens[1]!.spoken = false;
    source.tokens[2]!.spoken = false;
    const before = structuredClone(source);
    expect(plan(source, edit(9, 13, "loud", 2023))).toMatchObject({ ok: false, code: "NARRATION_TEXT_DIRECTION_UNSUPPORTED" });
    expect(source).toEqual(before);
  });
});
