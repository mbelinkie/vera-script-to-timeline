import { randomUUID } from "node:crypto";

import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";
import * as Y from "yjs";

import { applyRootChange, positionBetween, readRoot, sameJson, seedRoot, type JsonObject } from "../src/tree.js";
import { scriptFor } from "./helpers.js";

function shared(document: ScriptDocumentV2): Y.Doc {
  const doc = new Y.Doc();
  const ideas = { schemaVersion: "stt-idea-outline/v1", documentId: document.id, items: [] };
  doc.transact(() => { seedRoot(doc, { document, ideas } as unknown as JsonObject); });
  return doc;
}

function copy(doc: Y.Doc): Y.Doc {
  const other = new Y.Doc();
  Y.applyUpdate(other, Y.encodeStateAsUpdate(doc));
  return other;
}

function edit(doc: Y.Doc, mutate: (document: ScriptDocumentV2) => void): void {
  const before = readRoot(doc);
  const after = structuredClone(before);
  mutate((after as unknown as { document: ScriptDocumentV2 }).document);
  doc.transact(() => { applyRootChange(doc, before, after); });
}

function merge(a: Y.Doc, b: Y.Doc): void {
  Y.applyUpdate(a, Y.encodeStateAsUpdate(b));
  Y.applyUpdate(b, Y.encodeStateAsUpdate(a));
}

const draft = (doc: Y.Doc) => (readRoot(doc) as unknown as { document: ScriptDocumentV2 }).document;
const narration = (doc: Y.Doc, index: number) =>
  draft(doc).activeDraft.blocks.filter((block) => block.type === "narration")[index] as NarrationBlockV2;

describe("shared document mapping", () => {
  it("hands back exactly the script it was given, and the script is valid", () => {
    const document = scriptFor(randomUUID(), ["hello world", "Take a breath [pause here] and go on."]);
    expect(validateScriptDocumentV2(document).diagnostics).toEqual([]);
    const doc = shared(document);
    expect(sameJson(draft(doc), document)).toBe(true);
    expect(sameJson(draft(copy(doc)), document)).toBe(true);
  });

  it("keeps tokens it would not have produced itself until the text changes", () => {
    const document = scriptFor(randomUUID(), ["hello, world"]);
    const row = document.activeDraft.blocks[1] as NarrationBlockV2;
    row.tokens = [
      { id: randomUUID(), value: "hello", startOffset: 0, endOffset: 5 },
      { id: randomUUID(), value: "world", startOffset: 7, endOffset: 12 },
    ];
    const doc = shared(document);
    expect(sameJson(draft(doc), document)).toBe(true);
  });

  it("keeps word IDs through an edit and gives a new word a new ID", () => {
    const document = scriptFor(randomUUID(), ["hello world"]);
    const original = (document.activeDraft.blocks[1] as NarrationBlockV2).tokens;
    const doc = shared(document);
    edit(doc, (next) => { (next.activeDraft.blocks[1] as NarrationBlockV2).text = "hello brave world"; });
    const tokens = narration(doc, 0).tokens;
    expect(tokens.map((token) => token.value)).toEqual(["hello", "brave", "world"]);
    expect([tokens[0]!.id, tokens[2]!.id]).toEqual([original[0]!.id, original[1]!.id]);
    expect(validateScriptDocumentV2(draft(doc)).diagnostics).toEqual([]);
  });

  it("merges two people typing in the same paragraph without losing a character", () => {
    const a = shared(scriptFor(randomUUID(), ["hello world"]));
    const b = copy(a);
    edit(a, (next) => { (next.activeDraft.blocks[1] as NarrationBlockV2).text = "hello big world"; });
    edit(b, (next) => { (next.activeDraft.blocks[1] as NarrationBlockV2).text = "hello world today"; });
    merge(a, b);
    expect(narration(a, 0).text).toBe("hello big world today");
    expect(sameJson(readRoot(a), readRoot(b))).toBe(true);
    expect(validateScriptDocumentV2(draft(a)).diagnostics).toEqual([]);
  });

  it("never duplicates or drops a row when two people move it at once", () => {
    const a = shared(scriptFor(randomUUID(), ["one", "two", "three", "four"]));
    const b = copy(a);
    const ids = draft(a).activeDraft.blocks.map((block) => block.id);
    edit(a, (next) => { next.activeDraft.blocks.push(next.activeDraft.blocks.splice(1, 1)[0]!); });
    edit(b, (next) => { next.activeDraft.blocks.splice(3, 0, next.activeDraft.blocks.splice(1, 1)[0]!); });
    expect(draft(a).activeDraft.blocks.map((block) => block.id)).toEqual([ids[0], ids[2], ids[3], ids[4], ids[1]]);
    merge(a, b);
    const merged = draft(a).activeDraft.blocks.map((block) => block.id);
    expect([...merged].sort()).toEqual([...ids].sort());
    expect(draft(b).activeDraft.blocks.map((block) => block.id)).toEqual(merged);
  });

  it("orders inserted positions strictly between their neighbours", () => {
    let low = "";
    const keys: string[] = [];
    for (let index = 0; index < 200; index += 1) keys.push(low = positionBetween(low, null));
    expect([...keys].sort()).toEqual(keys);
    let high = keys[1]!;
    for (let index = 0; index < 200; index += 1) {
      const middle = positionBetween(keys[0]!, high);
      expect(middle > keys[0]! && middle < high).toBe(true);
      high = middle;
    }
  });
});
