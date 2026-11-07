import { describe, expect, it } from "vitest";

import {
  chooseReturnSlotV2,
  freezeOriginalParentContextV2,
  freezeOriginalSiblingCandidatesV2,
  originalParentUnmovedV2,
} from "../src/authoring-v2-stash-return-location.js";
import type { StashOriginV2, StashOutlineEntryV2 } from "../src/generated/contracts-v2.js";

const id = (value: number) => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const a = id(1);
const b = id(2);
const c = id(3);
const d = id(4);
const parent = id(5);
const child = id(6);
const otherParent = id(7);
const section = id(8);
const otherSection = id(9);
const newPeer = id(10);

function entry(rowId: string, parentRowId: string | null = null, sectionId: string | null = null,
  kind: StashOutlineEntryV2["kind"] = "note"): StashOutlineEntryV2 {
  return { rowId, kind, parentRowId, sectionId };
}

function origin(options: Partial<StashOriginV2> = {}): StashOriginV2 {
  return {
    kind: "note", parentRowId: null, sectionId: null,
    afterSiblingRowId: b, beforeSiblingRowId: d, returnEligible: true,
    ...options,
  };
}

function resolve(value: StashOriginV2 | undefined, entries: StashOutlineEntryV2[],
  parentChoice: { kind: "root" } | { kind: "note"; rowId: string } | { kind: "invalid" } = { kind: "root" },
  sectionIds: ReadonlySet<string> = new Set()): ReturnType<typeof chooseReturnSlotV2> {
  return chooseReturnSlotV2({ origin: value, entries, parent: parentChoice, sectionIds });
}

describe("pure forgiving Stash return location", () => {
  it("freezes only same-level original siblings nearest first without changing input", () => {
    const entries = [entry(a), entry(b), entry(c), entry(child, b), entry(d), entry(newPeer, null, section)];
    const snapshot = structuredClone(entries);
    expect(freezeOriginalSiblingCandidatesV2(entries, c)).toEqual({
      precedingSiblingRowIds: [b, a], followingSiblingRowIds: [d],
    });
    expect(freezeOriginalSiblingCandidatesV2(entries, child)).toEqual({
      precedingSiblingRowIds: [], followingSiblingRowIds: [],
    });
    expect(freezeOriginalSiblingCandidatesV2(entries, id(500))).toBeNull();
    expect(entries).toEqual(snapshot);
  });

  it("freezes the note parent's own original location separately from its child", () => {
    const entries = [entry(a), entry(parent), entry(child, parent), entry(d)];
    expect(freezeOriginalParentContextV2(entries, child)).toEqual({
      parentRowId: null, sectionId: null,
      precedingSiblingRowIds: [a], followingSiblingRowIds: [d],
    });
    expect(freezeOriginalParentContextV2(entries, parent)).toBeNull();
    expect(freezeOriginalParentContextV2([entry(parent, null, null, "clip"), entry(child, parent)], child)).toBeNull();
    expect(freezeOriginalParentContextV2([entry(child, id(800))], child)).toBeNull();
  });

  it("prefers nearest surviving historical predecessor, then successor, never an interposed peer", () => {
    const saved = origin({
      precedingSiblingRowIds: [b, a], followingSiblingRowIds: [d],
    });
    expect(resolve(saved, [entry(a), entry(newPeer), entry(b), entry(d)])).toEqual({
      kind: "after", siblingRowId: b, parentRowId: null, sectionId: null,
    });
    expect(resolve(saved, [entry(a), entry(newPeer), entry(d)])).toEqual({
      kind: "after", siblingRowId: a, parentRowId: null, sectionId: null,
    });
    expect(resolve(saved, [entry(newPeer), entry(d)])).toEqual({
      kind: "before", siblingRowId: d, parentRowId: null, sectionId: null,
    });
    expect(resolve(saved, [entry(newPeer)])).toEqual({
      kind: "section_start", parentRowId: null, sectionId: null,
    });
  });

  it("selects the original predecessor even if later Stash moves reverse the surviving anchors", () => {
    const saved = origin({ precedingSiblingRowIds: [b], followingSiblingRowIds: [d] });
    expect(resolve(saved, [entry(d), entry(newPeer), entry(b)])).toEqual({
      kind: "after", siblingRowId: b, parentRowId: null, sectionId: null,
    });
    expect(resolve(saved, [entry(b, otherParent), entry(d)])).toEqual({
      kind: "before", siblingRowId: d, parentRowId: null, sectionId: null,
    });
  });

  it("honors a named original section, or falls back to unsectioned top if it is gone", () => {
    const saved = origin({ sectionId: section, precedingSiblingRowIds: [], followingSiblingRowIds: [] });
    expect(resolve(saved, [entry(newPeer, null, otherSection)], { kind: "root" }, new Set([section, otherSection]))).toEqual({
      kind: "section_start", parentRowId: null, sectionId: section,
    });
    expect(resolve(saved, [entry(newPeer, null, otherSection)], { kind: "root" }, new Set([otherSection]))).toEqual({
      kind: "unsectioned_top", parentRowId: null, sectionId: null,
    });
  });

  it("returns first under a still-valid note after all original child anchors disappear", () => {
    const entries = [entry(a), entry(parent), entry(newPeer, parent), entry(d)];
    const parentHistory = freezeOriginalParentContextV2(
      [entry(a), entry(parent), entry(child, parent), entry(d)], child);
    expect(parentHistory).not.toBeNull();
    const saved = origin({
      parentRowId: parent, afterSiblingRowId: null, beforeSiblingRowId: null,
      precedingSiblingRowIds: [], followingSiblingRowIds: [],
      originalParentContext: parentHistory!,
    });
    const baseline = structuredClone(entries);
    expect(resolve(saved, entries, { kind: "note", rowId: parent })).toEqual({
      kind: "first_child", parentRowId: parent, sectionId: null,
    });
    expect(entries).toEqual(baseline);
    expect(originalParentUnmovedV2(entries, parent, parentHistory!)).toBe(true);
  });

  it("rejects missing, non-note, reparented or relatively reordered original parents", () => {
    const originalEntries = [entry(a), entry(parent), entry(child, parent), entry(d)];
    const context = freezeOriginalParentContextV2(originalEntries, child)!;
    const saved = origin({ parentRowId: parent, originalParentContext: context });
    const fallback = { kind: "unsectioned_top", parentRowId: null, sectionId: null };
    expect(resolve(saved, [entry(a), entry(d)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(resolve(saved, [entry(a), entry(parent, null, null, "row"), entry(d)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(resolve(saved, [entry(a), entry(parent, otherParent), entry(d)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(resolve(saved, [entry(parent, null, section), entry(a), entry(d)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(resolve(saved, [entry(parent), entry(a), entry(d)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(resolve(saved, [entry(a), entry(d), entry(parent)], { kind: "note", rowId: parent })).toEqual(fallback);
    expect(originalParentUnmovedV2([entry(a), entry(newPeer), entry(parent), entry(d)], parent, context)).toBe(true);
    expect(resolve(saved, [entry(a), entry(parent), entry(d)], { kind: "note", rowId: otherParent })).toEqual(fallback);
  });

  it("does not invent original parent evidence for an old nested origin", () => {
    const oldNested = origin({ parentRowId: parent, afterSiblingRowId: null, beforeSiblingRowId: null });
    expect(resolve(oldNested, [entry(parent)], { kind: "note", rowId: parent })).toEqual({
      kind: "unsectioned_top", parentRowId: null, sectionId: null,
    });
  });

  it("preserves six-field legacy immediate sibling anchors without fabricating a history", () => {
    const old = origin();
    expect(resolve(old, [entry(b), entry(d)])).toEqual({
      kind: "after", siblingRowId: b, parentRowId: null, sectionId: null,
    });
    expect(resolve(old, [entry(d)])).toEqual({
      kind: "before", siblingRowId: d, parentRowId: null, sectionId: null,
    });
    expect(resolve(old, [])).toEqual({ kind: "section_start", parentRowId: null, sectionId: null });
  });

  it("accepts explicit frozen root history when the original parent remains active in Draft", () => {
    const nested = origin({ parentRowId: parent, precedingSiblingRowIds: [b], followingSiblingRowIds: [] });
    const entries = [entry(a), entry(d)];
    expect(resolve(nested, entries)).toEqual({ kind: "unsectioned_top", parentRowId: null, sectionId: null });
    expect(chooseReturnSlotV2({
      origin: nested, entries, sectionIds: new Set(), parent: { kind: "root" },
      promotedRootPreceding: [a], promotedRootFollowing: [d],
    })).toEqual({ kind: "after", siblingRowId: a, parentRowId: null, sectionId: null });
    expect(chooseReturnSlotV2({
      origin: nested, entries: [entry(b), entry(d)], sectionIds: new Set(), parent: { kind: "root" },
      promotedRootFollowing: [d],
    })).toEqual({ kind: "before", siblingRowId: d, parentRowId: null, sectionId: null });
  });

  it("fails safely for missing origins, invalid parent decisions and ancestors with no evidence", () => {
    const fallback = { kind: "unsectioned_top", parentRowId: null, sectionId: null };
    expect(resolve(undefined, [])).toEqual(fallback);
    expect(resolve(origin(), [], { kind: "invalid" })).toEqual(fallback);
    expect(resolve(origin({ parentRowId: parent }), [])).toEqual(fallback);
  });
});
