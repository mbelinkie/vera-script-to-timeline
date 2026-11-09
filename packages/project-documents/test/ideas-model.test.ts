import { randomUUID } from "node:crypto";

import { describe, expect, it } from "vitest";

import { checkedIdeas, emptyIdeasV1, MAX_IDEA_DEPTH, promoteIdeaToNoteV1 } from "../src/ideas-model.js";
import { documentFor } from "./helpers.js";

const item = (id = randomUUID(), parentId: string | null = null, orderKey = "a", text = "Exact text") => ({
  id, parentId, orderKey, text, state: "open" as const,
  linkedDraftBlockIds: [] as string[], collapsed: false, version: 1,
});
const outline = (documentId: string, items: unknown[]) =>
  ({ schemaVersion: "stt-idea-outline/v1", documentId, items });

describe("strict sidecar Ideas v1 authoring", () => {
  it("accepts ordered nested DFS and preserves whitespace, ordering, and collapse state", () => {
    const doc = documentFor(randomUUID());
    const root = item(randomUUID(), null, "a", "  root  ");
    const first = { ...item(randomUUID(), root.id, "a", " x  \n\ny "), collapsed: true };
    const sibling = item(randomUUID(), root.id, "b", "sibling");
    const other = item(randomUUID(), null, "z", "other root");
    const source = outline(doc.id.toUpperCase(), [root, first, sibling, other]);
    const checked = checkedIdeas(source, doc.id);
    expect(checked).toEqual({ ...source, documentId: doc.id });
    expect(checked.items[1]?.text).toBe(first.text);
    expect(emptyIdeasV1(doc.id)).toEqual(outline(doc.id, []));
    expect(doc.ideaOutline).toEqual([]);
  });

  it("rejects duplicate IDs, missing or forward parent, cycle, and discontiguous subtree", () => {
    const doc = documentFor(randomUUID()), root = item(), sibling = item(randomUUID(), null, "b");
    const child = item(randomUUID(), root.id);
    for (const entries of [
      [root, root],
      [child, root],
      [{ ...root, parentId: randomUUID() }],
      [{ ...root, parentId: child.id }, child],
      [root, sibling, child],
      [root, { ...root, id: root.id.toUpperCase(), orderKey: "b" }],
    ]) expect(() => checkedIdeas(outline(doc.id, entries), doc.id)).toThrow();
  });

  it("rejects unsorted and duplicate sibling keys, including nested siblings", () => {
    const doc = documentFor(randomUUID()), root = item();
    for (const entries of [
      [root, item(randomUUID(), null, "a")],
      [item(randomUUID(), null, "z"), root],
      [root, item(randomUUID(), root.id, "b"), item(randomUUID(), root.id, "a")],
    ]) expect(() => checkedIdeas(outline(doc.id, entries), doc.id)).toThrow();
  });

  it("rejects excessive depth and total byte count (not just character count)", () => {
    const doc = documentFor(randomUUID());
    const chain = [item()];
    for (let i = 1; i <= MAX_IDEA_DEPTH; i++) chain.push(item(randomUUID(), chain[i - 1]!.id));
    expect(() => checkedIdeas(outline(doc.id, chain), doc.id)).toThrow();
    const giant = Array.from({ length: 25 }, (_, index) =>
      item(randomUUID(), null, String(index).padStart(3, "0"), "界".repeat(8_000)));
    expect(() => checkedIdeas(outline(doc.id, giant), doc.id)).toThrow();
  });

  it("rejects unknown fields, invalid identity, malformed JSON values and version", () => {
    const doc = documentFor(randomUUID());
    const base = item();
    const cases: unknown[] = [
      { ...base, untrustedBuildEligible: true },
      { ...base, text: "" },
      { ...base, orderKey: "  " },
      { ...base, orderKey: "bad\nkey" },
      { ...base, version: 0 },
      { ...base, version: 1.5 },
      { ...base, version: Number.NaN },
      { ...base, state: "promoted" },
      { ...base, collapsed: 0 },
      { ...base, parentId: "wrong" },
      { ...base, linkedDraftBlockIds: [randomUUID(), "invalid"] },
      Object.assign(Object.create(null) as Record<string, unknown>, base),
    ];
    for (const invalid of cases) expect(() => checkedIdeas(outline(doc.id, [invalid]), doc.id)).toThrow();
    expect(() => checkedIdeas(outline(randomUUID(), [base]), doc.id)).toThrow();
    expect(() => checkedIdeas({ ...outline(doc.id, [base]), extra: true }, doc.id)).toThrow();
  });

  it("rejects duplicate backlinks even across distinct Ideas", () => {
    const doc = documentFor(randomUUID()), block = randomUUID();
    const root = { ...item(), linkedDraftBlockIds: [block] };
    expect(() => checkedIdeas(outline(doc.id, [{ ...root, linkedDraftBlockIds: [block, block] }]), doc.id)).toThrow();
    expect(() => checkedIdeas(outline(doc.id, [root,
      { ...item(randomUUID(), null, "b"), linkedDraftBlockIds: [block] }]), doc.id)).toThrow();
  });
});

describe("pure Draft-note promotion", () => {
  const gap = { sectionId: null, afterRowId: null, beforeRowId: null };

  it("copies exact text into excluded note and retains original source/ancestry/collaboration", () => {
    const doc = documentFor(randomUUID());
    const parent = { ...item(randomUUID(), null, "a", "parent"), collapsed: true };
    const child = item(randomUUID(), parent.id, "a", "  exact  text\nwith newline \n");
    const ideas = checkedIdeas(outline(doc.id, [parent, child]), doc.id);
    const blockId = randomUUID();
    const applied = promoteIdeaToNoteV1(doc, ideas, child.id, blockId, "a", gap);
    expect(doc.activeDraft.blocks).toEqual([]);
    expect(doc.ideaOutline).toEqual([]);
    expect(ideas.items[1]).toMatchObject({ state: "open", linkedDraftBlockIds: [] });
    expect(applied.document.activeDraft.blocks).toEqual([{
      type: "note_draft", id: blockId, orderKey: "a", text: child.text,
      state: "excluded", version: 1,
    }]);
    expect(applied.document.liveHeadSequence).toEqual(doc.liveHeadSequence);
    expect(applied.document.liveStateVector).toEqual(doc.liveStateVector);
    expect(applied.document.liveContentHash).toEqual(doc.liveContentHash);
    expect(applied.document.rowEditRevision).toBe(1);
    expect(applied.ideas.items[0]).toEqual(ideas.items[0]);
    expect(applied.ideas.items[1]).toEqual({ ...child, version: 2,
      state: "incorporated", linkedDraftBlockIds: [blockId] });
  });

  it("supports a second intentional promotion without deleting or overwriting the source", () => {
    const doc = documentFor(randomUUID()), source = item();
    const ideas = checkedIdeas(outline(doc.id, [source]), doc.id);
    const a = randomUUID(), b = randomUUID();
    const first = promoteIdeaToNoteV1(doc, ideas, source.id, a, "a", gap);
    const second = promoteIdeaToNoteV1(first.document, first.ideas, source.id, b, "b",
      { sectionId: null, afterRowId: a, beforeRowId: null });
    expect(second.document.activeDraft.blocks.map(({ id }) => id)).toEqual([a, b]);
    expect(second.ideas.items[0]).toEqual({ ...source, state: "incorporated",
      linkedDraftBlockIds: [a, b], version: 3 });
  });

  it("rejects duplicate Draft/block/Idea ids, bad destination and missing source", () => {
    const doc = documentFor(randomUUID()), source = item(), ideas = checkedIdeas(outline(doc.id, [source]), doc.id);
    expect(() => promoteIdeaToNoteV1(doc, ideas, randomUUID(), randomUUID(), "a", gap)).toThrow();
    expect(() => promoteIdeaToNoteV1(doc, ideas, source.id, source.id, "a", gap)).toThrow();
    expect(() => promoteIdeaToNoteV1(doc, ideas, source.id, randomUUID(), "a", { ...gap, extra: true } as never)).toThrow();
    expect(() => promoteIdeaToNoteV1(doc, ideas, source.id, randomUUID(), "a", { ...gap, afterRowId: randomUUID() })).toThrow();
    const first = promoteIdeaToNoteV1(doc, ideas, source.id, randomUUID(), "a", gap);
    const existing = first.document.activeDraft.blocks[0]!.id;
    expect(() => promoteIdeaToNoteV1(first.document, first.ideas, source.id, existing, "b",
      { ...gap, afterRowId: existing })).toThrow();
    const max = checkedIdeas(outline(doc.id, [{ ...source, version: Number.MAX_SAFE_INTEGER }]), doc.id);
    expect(() => promoteIdeaToNoteV1(doc, max, source.id, randomUUID(), "a", gap)).toThrow();
  });
});
