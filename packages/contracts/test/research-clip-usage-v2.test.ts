import { describe, expect, it } from "vitest";
import { indexResearchClipUsageV2 } from "../src/authoring-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { createRowEditSessionV2 } from "../src/authoring-v2-rows.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
import {
  researchId, researchMirroredNote, researchNestedNote,
  researchOccurrence, researchStashFixture,
} from "./issue-367-fixture.js";

const clipId = researchId(710001);
const projectId = researchId(710002);

function assertValid(document: ScriptDocumentV2): void {
  const checked = validateScriptDocumentV2(document);
  expect(checked.diagnostics.filter((item) => item.severity !== "warning")).toEqual([]);
}

/** Preserve token IDs for visual anchors while exercising authored-text excerpts. */
function setText(row: NarrationBlockV2, text: string): void {
  const oldTokens = row.tokens;
  row.text = text;
  row.tokens = [...text.matchAll(/\S+/gu)].map((match, index) => ({
    id: oldTokens[index]?.id ?? researchId(900000 + index),
    value: match[0],
    startOffset: match.index,
    endOffset: match.index + match[0].length,
    spoken: true,
  }));
}

describe("Research clip usage derived from the saved document", () => {
  it("returns independent primary and overlay uses followed by one exact attached mirror", () => {
    const { doc, note } = researchStashFixture(false);
    const nested = researchNestedNote(760100);
    const mirrored = researchMirroredNote(760200, false);
    doc.activeDraft.blocks = [nested, mirrored];
    assertValid(doc);
    const before = structuredClone(doc);

    const [usage] = indexResearchClipUsageV2(doc);
    expect(usage).toMatchObject({ researchProjectId: projectId, clipId, scriptCount: 3, stashCount: 1 });
    expect(usage?.scriptUses).toEqual([
      { rowId: nested.id, placementId: nested.primaryVisualSequence!.slots[0]!.id,
        kind: "primary", rowExcerpt: "Look closer" },
      { rowId: nested.id, placementId: nested.overlayEvents[0]!.id,
        kind: "overlay", rowExcerpt: "Look closer" },
      { rowId: mirrored.id, placementId: mirrored.primaryVisualSequence!.slots[0]!.id,
        kind: "primary", rowExcerpt: "Look closer" },
    ]);
    expect(usage?.stashUses).toEqual([{
      rowId: note.id, placementId: note.attachedFootage!.clip.id,
      kind: "attached", rowExcerpt: "Look closer",
    }]);
    expect(doc).toEqual(before);
    expect(indexResearchClipUsageV2(doc)).toEqual([usage]);
  });

  it("uses the first three and last five authored words, or the entire short row", () => {
    const { doc } = researchStashFixture(false);
    const long = researchNestedNote(760300);
    const short = researchMirroredNote(760400, false);
    setText(long, "Look closer café ☕ begins the vivid winding final coastal scene!");
    setText(short, "  Look   closer  ");
    doc.activeDraft.blocks = [long, short];
    const [usage] = indexResearchClipUsageV2(doc);
    expect(usage?.scriptUses.map((use) => use.rowExcerpt)).toEqual([
      "Look closer café … vivid winding final coastal scene!",
      "Look closer café … vivid winding final coastal scene!",
      "Look   closer",
    ]);
    // A footage-only row has no authored spoken words to excerpt.
    doc.activeDraft.blocks.push(researchOccurrence(760500, false));
    expect(indexResearchClipUsageV2(doc)[0]?.scriptUses.at(-1)?.rowExcerpt).toBe("");
  });

  it("counts standalone, unresolved and unattached visuals, even in an excluded row", () => {
    const { doc } = researchStashFixture(false);
    const standalone = researchOccurrence(761000, false);
    const excluded = researchNestedNote(761100);
    excluded.state = "excluded";
    const baseSlot = excluded.primaryVisualSequence!.slots[0]!;
    if (baseSlot.kind !== "content" || baseSlot.payload.kind !== "visual") throw new Error("Missing clip slot");
    const loose = structuredClone(baseSlot.payload);
    loose.payloadId = researchId(761200);
    excluded.unattachedVisuals = [{ slotId: researchId(761201), payload: loose, version: 1 }];
    doc.activeDraft.blocks = [standalone, excluded];
    assertValid(doc);

    const [usage] = indexResearchClipUsageV2(doc);
    expect(usage?.scriptCount).toBe(4);
    expect(usage?.scriptUses).toEqual([
      { rowId: standalone.id, placementId: standalone.id, kind: "visual_only", rowExcerpt: "" },
      { rowId: excluded.id, placementId: baseSlot.id, kind: "primary", rowExcerpt: "Look closer" },
      { rowId: excluded.id, placementId: excluded.overlayEvents[0]!.id,
        kind: "overlay", rowExcerpt: "Look closer" },
      { rowId: excluded.id, placementId: researchId(761201),
        kind: "unattached", rowExcerpt: "Look closer" },
    ]);
    expect(usage?.stashCount).toBe(1);
  });

  it("reports Stash-only clips as unused and optionally seeds truly unseen catalog clips", () => {
    const { doc, note } = researchStashFixture();
    const unseen = researchId(999999);
    assertValid(doc);
    const indexed = indexResearchClipUsageV2(doc, [
      { researchProjectId: projectId, clipId },
      { researchProjectId: projectId, clipId: unseen },
      { researchProjectId: projectId, clipId: unseen },
    ]);

    expect(indexed).toHaveLength(2);
    expect(indexed[0]).toMatchObject({ clipId, scriptCount: 0, stashCount: 1 });
    expect(indexed[0]?.stashUses[0]?.rowId).toBe(note.id);
    expect(indexed[1]).toEqual({
      researchProjectId: projectId, clipId: unseen,
      scriptCount: 0, scriptUses: [], stashCount: 0, stashUses: [],
    });
  });

  it("groups revisions and trims by (Research project, clip ID), not by clip version", () => {
    const { doc } = researchStashFixture(false);
    delete doc.stash;
    delete doc.stashOutline;
    const first = researchOccurrence(762000, false);
    const newer = researchOccurrence(762100, false);
    newer.researchClip!.clipVersion = 42;
    newer.researchClip!.video.title = "Retitled revision";
    newer.researchClip!.loggedSelection.text = "Revised transcript";
    const otherProject = researchOccurrence(762200, false);
    otherProject.researchClip!.researchProjectId = researchId(762300);
    doc.activeDraft.blocks = [first, newer, otherProject];
    assertValid(doc);

    const result = indexResearchClipUsageV2(doc);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({ researchProjectId: projectId, clipId, scriptCount: 2 });
    expect(result[0]?.scriptUses.map((use) => use.rowId)).toEqual([first.id, newer.id]);
    expect(result[1]).toMatchObject({ researchProjectId: researchId(762300), clipId, scriptCount: 1 });
    expect(result[1]?.scriptUses[0]?.rowId).toBe(otherProject.id);
  });

  it("reads Stash's canonical mixed order including nested uses, not a second script", () => {
    const { doc, note } = researchStashFixture(false);
    const standalone = researchOccurrence(763000, false);
    const nested = researchNestedNote(763100);
    doc.stash!.push({ id: researchId(763200), rows: [standalone, nested], supportingItems: [] });
    doc.stashOutline = [
      { rowId: standalone.id, kind: "clip", parentRowId: null, sectionId: null },
      ...doc.stashOutline!,
      { rowId: nested.id, kind: "note", parentRowId: null, sectionId: null },
    ];
    assertValid(doc);

    const [usage] = indexResearchClipUsageV2(doc);
    expect(usage?.scriptCount).toBe(0);
    expect(usage?.stashCount).toBe(4);
    expect(usage?.stashUses.map((use) => [use.rowId, use.kind])).toEqual([
      [standalone.id, "visual_only"], [note.id, "attached"],
      [nested.id, "primary"], [nested.id, "overlay"],
    ]);
    // For legacy/partial outlines, no saved row is silently lost.
    doc.stashOutline = doc.stashOutline.filter((item) => item.rowId !== standalone.id);
    expect(indexResearchClipUsageV2(doc)[0]?.stashCount).toBe(4);
    delete doc.stashOutline;
    expect(indexResearchClipUsageV2(doc)[0]?.stashCount).toBe(4);
  });

  it("does not merge separate placements with matching snapshots or near-mirrors", () => {
    const { doc } = researchStashFixture(false);
    const owned = researchMirroredNote(764000, false);
    const independent = structuredClone(owned);
    independent.id = researchId(764100);
    independent.stashOrigin!.returnEligible = false;
    const different = researchMirroredNote(764200, false);
    const slot = different.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Missing mirror");
    slot.payload.sourceUsage = { sourceInFrame: 12 }; // No longer an exact mirror.
    doc.activeDraft.blocks = [owned, independent, different];

    const [usage] = indexResearchClipUsageV2(doc);
    expect(usage?.scriptCount).toBe(5); // 1 exact mirror + 2 independent + 2 near-mirror
    expect(usage?.scriptUses.map((use) => use.kind)).toEqual([
      "primary", "primary", "attached", "primary", "attached",
    ]);
  });

  it("recomputes after a real Stash return and Undo without persisted counts", () => {
    const { doc, note } = researchStashFixture(false);
    const before = indexResearchClipUsageV2(doc)[0]!;
    expect([before.scriptCount, before.stashCount]).toEqual([0, 1]);
    const session = createRowEditSessionV2(doc);
    const returned = session.apply({
      kind: "place_stash_rows", rowIds: [note.id],
      destination: { sectionId: null, afterRowId: null, beforeRowId: null },
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    assertValid(returned.document);
    const moved = indexResearchClipUsageV2(returned.document)[0]!;
    expect([moved.scriptCount, moved.stashCount]).toEqual([1, 0]);
    expect(moved.scriptUses[0]?.rowId).toBe(note.id);

    const undone = session.undo();
    expect(undone.ok, JSON.stringify(undone.diagnostics)).toBe(true);
    assertValid(undone.document);
    expect(indexResearchClipUsageV2(undone.document)[0]).toMatchObject({
      researchProjectId: projectId, clipId, scriptCount: 0, stashCount: 1,
    });
    expect(indexResearchClipUsageV2(doc)).toEqual([before]);
  });
});
