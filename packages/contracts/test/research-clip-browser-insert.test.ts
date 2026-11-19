import { describe, expect, it } from "vitest";

import { insertResearchClipBrowserV2, type ResearchClipBrowserInsertV2 } from "../src/research-clip-browser-insert.js";
import { indexResearchClipUsageV2 } from "../src/research-clip-usage-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import {
  researchCandidate, researchId, researchNote, researchStashFixture,
} from "./issue-367-fixture.js";

const newIds = (from: number) => {
  let next = from;
  return () => researchId(next++);
};

function fixture() {
  const doc = researchStashFixture(false).doc;
  const first = researchNote(880100);
  const second = researchNote(880200);
  for (const row of [first, second]) {
    delete row.plainDirection;
    row.tokens.forEach((token) => { token.spoken = true; });
  }
  doc.activeDraft.blocks = [first, second];
  return { doc, first, second };
}

function request(placement: ResearchClipBrowserInsertV2["placement"], revision = 0): ResearchClipBrowserInsertV2 {
  const clip = researchCandidate();
  return {
    expectedDocumentRevision: revision, researchProjectId: clip.projectId,
    clipId: clip.id, clipVersion: clip.version, placement,
  };
}

function words(row: ReturnType<typeof fixture>["first"]): Extract<ResearchClipBrowserInsertV2["placement"], { kind: "selected_words" }> {
  return {
    kind: "selected_words", rowId: row.id, expectedRowVersion: row.version,
    expectedSequenceVersion: row.primaryVisualSequence!.version,
    startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[0]!.id,
  };
}

describe("Research clip browser insertion: one atomic script edit", () => {
  it("creates an independent source-unresolved footage row in an exact section gap", () => {
    const { doc, first, second } = fixture();
    const before = structuredClone(doc);
    const candidate = researchCandidate();
    const savedCandidate = structuredClone(candidate);
    const inserted = insertResearchClipBrowserV2(doc, candidate,
      request({ kind: "gap", destination: { sectionId: null, afterRowId: first.id, beforeRowId: second.id } }),
      newIds(900100));
    expect(inserted.ok, JSON.stringify(inserted.diagnostics)).toBe(true);
    expect(inserted.document.activeDraft.blocks.map((item) => item.id)).toEqual([
      first.id, researchId(900100), second.id,
    ]);
    const row = inserted.document.activeDraft.blocks[1];
    expect(row?.type).toBe("visual_only");
    if (row?.type !== "visual_only") return;
    expect(row.payload.payloadId).toBe(researchId(900101));
    expect(row.researchClip).toMatchObject({
      clipId: candidate.id, researchProjectId: candidate.projectId, clipVersion: candidate.version,
      englishText: candidate.englishText, video: candidate.video,
      loggedSelection: { text: candidate.selection.text, timingPrecision: "cue", exportStartMs: 500, exportEndMs: 4500 },
    });
    expect(row.frameBinding).toBeUndefined();
    expect(row.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    expect(inserted.document.rowEditRevision).toBe(1);
    expect(validateScriptDocumentV2(inserted.document).valid).toBe(true);
    expect(indexResearchClipUsageV2(inserted.document)[0]).toMatchObject({
      clipId: candidate.id, scriptCount: 1, stashCount: 1,
      scriptUses: [{ rowId: row.id, placementId: row.id, kind: "visual_only" }],
    });
    expect(doc).toEqual(before);
    expect(candidate).toEqual(savedCandidate);
    candidate.video.title = "updated upstream";
    expect(row.researchClip?.video.title).toBe(savedCandidate.video.title);
  });

  it("places a Research visual on chosen spoken words and preserves On Camera coverage", () => {
    const { doc, first } = fixture();
    const before = structuredClone(doc);
    const result = insertResearchClipBrowserV2(doc, researchCandidate(), request(words(first)), newIds(900200));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const row = result.document.activeDraft.blocks[0];
    expect(row?.type).toBe("narration");
    if (row?.type !== "narration") return;
    expect(result.document.rowEditRevision).toBe(1);
    expect(row.version).toBe(first.version + 1);
    expect(row.primaryVisualSequence?.version).toBe(first.primaryVisualSequence!.version + 1);
    expect(row.unattachedVisuals).toBeUndefined();
    const clipSlots = row.primaryVisualSequence!.slots.filter((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" && slot.payload.researchClip);
    expect(clipSlots).toHaveLength(1);
    const clipSlot = clipSlots[0]!;
    if (clipSlot.kind !== "content" || clipSlot.payload.kind !== "visual") return;
    expect(clipSlot.id).toBe(researchId(900203));
    expect(clipSlot.payload.researchClip?.loggedSelection.text).toBe("Research transcript");
    expect(clipSlot.payload.sourceUsage).toBeNull();
    expect(clipSlot.payload.selectedSourceRange).toBeUndefined();
    expect(clipSlot.payload.frameBinding).toBeUndefined();
    expect(row.primaryVisualSequence!.slots.some((slot) =>
      slot.kind === "content" && slot.payload.kind === "on_camera")).toBe(true);
    expect(indexResearchClipUsageV2(result.document)[0]?.scriptUses).toEqual([
      { rowId: first.id, placementId: clipSlot.id, kind: "primary", rowExcerpt: first.text },
    ]);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(doc).toEqual(before);
  });

  it("creates a waiting visual without altering narration words, and independent repeated uses", () => {
    const { doc, first, second } = fixture();
    const before = structuredClone(doc);
    const incoming = request({
      kind: "unattached", rowId: first.id, expectedRowVersion: first.version,
      expectedSequenceVersion: first.primaryVisualSequence!.version,
    });
    const one = insertResearchClipBrowserV2(doc, researchCandidate(), incoming, newIds(900300));
    expect(one.ok, JSON.stringify(one.diagnostics)).toBe(true);
    const row = one.document.activeDraft.blocks[0];
    expect(row?.type).toBe("narration");
    if (row?.type !== "narration") return;
    expect(one.document.rowEditRevision).toBe(1);
    expect(row.version).toBe(first.version + 1);
    expect(row.primaryVisualSequence?.version).toBe(first.primaryVisualSequence!.version + 1);
    expect(row.primaryVisualSequence?.slots).toEqual(first.primaryVisualSequence?.slots);
    expect(row.tokens).toEqual(first.tokens);
    expect(row.unattachedVisuals).toHaveLength(1);
    expect(row.unattachedVisuals?.[0]).toMatchObject({
      slotId: researchId(900303), version: 1,
      payload: { payloadId: researchId(900301), pictureKind: "unresolved_visual", sourceUsage: null },
    });
    const two = insertResearchClipBrowserV2(one.document, researchCandidate(), request({
      kind: "unattached", rowId: second.id, expectedRowVersion: second.version,
      expectedSequenceVersion: second.primaryVisualSequence!.version,
    }, 1), newIds(900400));
    expect(two.ok, JSON.stringify(two.diagnostics)).toBe(true);
    expect(two.document.rowEditRevision).toBe(2);
    expect(indexResearchClipUsageV2(two.document)[0]).toMatchObject({
      scriptCount: 2, stashCount: 1,
      scriptUses: [
        { placementId: researchId(900303), kind: "unattached", rowId: first.id },
        { placementId: researchId(900403), kind: "unattached", rowId: second.id },
      ],
    });
    expect(validateScriptDocumentV2(two.document).valid).toBe(true);
    expect(doc).toEqual(before);
  });

  it("refuses stale clip/project, document/row/sequence, gap and token identities atomically", () => {
    const { doc, first, second } = fixture();
    const before = structuredClone(doc);
    const candidate = researchCandidate();
    const selected = words(first);
    const invalid = [
      { ...request(selected), clipId: researchId(990001) },
      { ...request(selected), researchProjectId: researchId(990002) },
      { ...request(selected), clipVersion: candidate.version + 1 },
      request(selected, 1),
      request({ ...selected, expectedRowVersion: first.version + 1 }),
      request({ ...selected, expectedSequenceVersion: first.primaryVisualSequence!.version + 1 }),
      request({ ...selected, rowId: second.id, startTokenId: first.tokens[0]!.id }),
      request({ ...selected, startTokenId: researchId(990003) }),
      request({ ...selected, startTokenId: first.tokens[1]!.id, endTokenId: first.tokens[0]!.id }),
      request({ kind: "unattached", rowId: researchId(720100), expectedRowVersion: 1, expectedSequenceVersion: 1 }),
      request({ kind: "gap", destination: { sectionId: null, afterRowId: first.id, beforeRowId: researchId(990004) } }),
    ];
    for (const bad of invalid) {
      const result = insertResearchClipBrowserV2(doc, candidate, bad, newIds(900500));
      expect(result.ok, JSON.stringify(bad)).toBe(false);
      expect(result.document, JSON.stringify(bad)).toBe(doc);
      expect(result.diagnostics.length).toBeGreaterThan(0);
      expect(doc).toEqual(before);
    }
    for (const duplicate of [first.id, doc.stash![0]!.rows[0].id, candidate.id]) {
      const result = insertResearchClipBrowserV2(doc, candidate, request(selected), () => duplicate);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(doc);
    }
  });
});
