import { describe, expect, it } from "vitest";
import {
  createResearchClipOccurrenceV2,
  inwardUseRangeV2,
  snapshotResearchCandidateV2,
  withResearchClipUseRangeV2,
  type ResearchLoggedCandidateInputV2,
} from "../src/authoring-v2-research-snapshot.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { applyRowEditV2, createRowEditSessionV2 } from "../src/authoring-v2-rows.js";
import type {
  NarrationBlockV2, ResearchFrameBindingV2, ScriptDocumentV2, VisualOnlyBlockV2,
} from "../src/generated/contracts-v2.js";

const id = (i: number) => `00000000-0000-4000-8000-${i.toString(16).padStart(12, "0")}`;
const candidate = (): ResearchLoggedCandidateInputV2 => ({
  id: id(500), projectId: id(501), catalogVideoId: id(502), version: 3, createdBy: id(503),
  createdAt: "2026-10-20T12:00:00.000Z", updatedAt: "2026-10-21T12:00:00.000Z",
  video: { youtubeVideoId: "synthetic", canonicalUrl: "https://youtu.be/synthetic", title: "Synthetic", channel: "Source" },
  selection: {
    trackId: id(504), transcriptVersion: 4, firstSegmentId: id(505), lastSegmentId: id(506),
    firstTokenId: id(507), lastTokenId: id(508),
    transcriptStartMs: 1000, transcriptEndMs: 4000, exportStartMs: 500, exportEndMs: 4500,
    text: "A source quotation", timingPrecision: "cue",
  },
  englishText: "English", originalText: "Original",
});
const binding = (): ResearchFrameBindingV2 => ({
  clipId: id(500), clipVersion: 3, mediaReferenceId: id(510), loggedStartFrame: 12, loggedEndFrame: 108,
});
const ready = (rowId = 600, payloadId = 601) => createResearchClipOccurrenceV2({
  candidate: candidate(), rowId: id(rowId), payloadId: id(payloadId), orderKey: `clip-${rowId}`,
  frameBinding: binding(), selectedRange: { startFrame: 24, endFrame: 60 },
});
const unresolved = () => createResearchClipOccurrenceV2({
  candidate: candidate(), rowId: id(600), payloadId: id(601), orderKey: "clip-600",
});

function note(clip: VisualOnlyBlockV2): NarrationBlockV2 {
  return {
    type: "narration", id: id(100), orderKey: "note-100", text: "[Direction]", tokens: [
      { id: id(101), value: "Direction", startOffset: 1, endOffset: 10, spoken: false },
    ],
    primaryVisualSequence: {
      id: id(102), version: 1, slots: [
        { id: id(103), kind: "content", version: 1, relation: { kind: "base" },
          boundaryBefore: { kind: "row_start" },
          payload: { kind: "on_camera", presenterChoiceId: null },
          playoutPolicy: "match_structural_interval" },
      ],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
    attachedFootage: { clip },
  };
}
function document(clip: VisualOnlyBlockV2 = ready()): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Research ownership",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
    stash: [{ id: id(400), rows: [note(clip)], supportingItems: [] }],
    stashOutline: [{ rowId: id(100), kind: "note", parentRowId: null, sectionId: null }],
  };
}
const diagnostics = (doc: ScriptDocumentV2) => validateScriptDocumentV2(doc).diagnostics.filter((d) => d.severity !== "warning");

describe("Research logged-clip snapshot and exclusive owner", () => {
  it("preserves real source/author/selection evidence with no caller mutation or invented frame mapping", () => {
    const source = candidate();
    const before = structuredClone(source);
    const snap = snapshotResearchCandidateV2(source);
    snap.loggedSelection.exportEndMs = 4200;
    snap.video.title = "Edited copy";
    expect(source).toEqual(before);
    const row = unresolved();
    expect(row.researchClip?.createdBy).toBe(id(503));
    expect(row.researchClip?.clipVersion).toBe(3);
    expect(row.researchClip?.loggedSelection.transcriptVersion).toBe(4);
    expect(row.researchClip?.loggedSelection.timingPrecision).toBe("cue");
    expect(row.payload.pictureKind).toBe("unresolved_visual");
    expect(row.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    expect(row.frameBinding).toBeUndefined();
    const saved = JSON.parse(JSON.stringify(document(row))) as ScriptDocumentV2;
    expect(validateScriptDocumentV2(saved).valid).toBe(true);
    expect(saved.stash?.[0]?.rows[0]).toEqual(note(row));
  });

  it("creates distinct occurrence-local selected frames and clear-out without changing Research original", () => {
    const first = ready();
    const second = createResearchClipOccurrenceV2({
      candidate: candidate(), rowId: id(610), payloadId: id(611), orderKey: "clip-610",
      frameBinding: binding(), selectedRange: { startFrame: 30, endFrame: 84 },
    });
    const adjusted = withResearchClipUseRangeV2(first, { startFrame: 36, endFrame: 48 });
    const clearOut = withResearchClipUseRangeV2(adjusted, null);
    expect(first.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 24, durationFrames: 36 });
    expect(second.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 30, durationFrames: 54 });
    expect(clearOut.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 36, durationFrames: 72 });
    expect(clearOut.researchClip).toEqual(first.researchClip);
    expect(second.researchClip).toEqual(first.researchClip);
    expect(first.id).not.toBe(second.id);
    expect(inwardUseRangeV2({ startFrame: 12, endFrame: 108 }, { startFrame: 24, endFrame: 60 }))
      .toEqual({ startFrame: 24, durationFrames: 36 });
  });

  it("rejects fake revision bindings, unsupported frame inference, unsafe/empty/outward trims and invalid source intervals", () => {
    const wrong = binding(); wrong.clipVersion = 4;
    expect(() => createResearchClipOccurrenceV2({
      candidate: candidate(), rowId: id(600), payloadId: id(601), orderKey: "test", frameBinding: wrong,
    })).toThrow(/revision/);
    expect(() => createResearchClipOccurrenceV2({
      candidate: candidate(), rowId: id(600), payloadId: id(601), orderKey: "test",
      selectedRange: { startFrame: 0, endFrame: 10 },
    })).toThrow(/without/);
    for (const selected of [
      { startFrame: 11, endFrame: 60 }, { startFrame: 24, endFrame: 109 },
      { startFrame: 24, endFrame: 24 }, { startFrame: 12, endFrame: Number.MAX_SAFE_INTEGER + 1 },
    ]) expect(() => inwardUseRangeV2({ startFrame: 12, endFrame: 108 }, selected)).toThrow();
    const bad = candidate(); bad.selection.exportStartMs = 2000;
    expect(() => snapshotResearchCandidateV2(bad)).toThrow();
    const badId = candidate(); badId.selection.trackId = "invalid";
    expect(() => snapshotResearchCandidateV2(badId)).toThrow();
  });

  it("validates single-owner attachment separately from ordinary nesting and counts it after reload", () => {
    const doc = document();
    expect(validateScriptDocumentV2(doc)).toEqual({ valid: true, diagnostics: [] });
    const saved = JSON.parse(JSON.stringify(doc)) as ScriptDocumentV2;
    expect(saved.stash?.[0]?.rows.length).toBe(1); // attached clip is not a second Stash row
    expect(saved.stash?.[0]?.rows[0]).toEqual(doc.stash?.[0]?.rows[0]);
    const child = ready(610, 611);
    saved.stash![0]!.rows.push(child);
    saved.stashOutline!.push({ rowId: child.id, kind: "clip", parentRowId: id(100), sectionId: null });
    expect(validateScriptDocumentV2(saved).valid).toBe(true); // same Research clip, different occurrence
    const duplicate = structuredClone(saved);
    duplicate.stash![0]!.rows.push(structuredClone(ready()));
    duplicate.stashOutline!.push({ rowId: id(600), kind: "clip", parentRowId: id(100), sectionId: null });
    expect(diagnostics(duplicate).some((d) => d.code === "FOOTAGE_OWNER_DUPLICATE")).toBe(true);
    const activeDuplicate = document();
    activeDuplicate.activeDraft.blocks.push(ready());
    expect(diagnostics(activeDuplicate).some((d) => d.code === "FOOTAGE_OWNER_DUPLICATE")).toBe(true);
    const lackingOutline = document(); delete lackingOutline.stashOutline;
    expect(diagnostics(lackingOutline).some((d) => d.code === "RESEARCH_CLIP_INVALID")).toBe(true);
  });

  it("rejects mismatched source revision, out-of-bounds use and malformed ownership atomically", () => {
    const wrongRevision = document();
    (wrongRevision.stash![0]!.rows[0] as NarrationBlockV2).attachedFootage!.clip.frameBinding!.clipVersion = 7;
    expect(diagnostics(wrongRevision).some((d) => d.code === "RESEARCH_CLIP_INVALID")).toBe(true);
    const beyond = document();
    (beyond.stash![0]!.rows[0] as NarrationBlockV2).attachedFootage!.clip.visualOnlyTiming.selectedSourceRange!.durationFrames = 100;
    expect(diagnostics(beyond).some((d) => d.code === "RESEARCH_CLIP_INVALID")).toBe(true);
    const badKind = document();
    (badKind.stash![0]!.rows[0] as NarrationBlockV2).attachedFootage!.clip.payload.pictureKind = "image";
    expect(validateScriptDocumentV2(badKind).valid).toBe(false);
    const unknown = document();
    const attachment = (unknown.stash![0]!.rows[0] as NarrationBlockV2).attachedFootage!;
    (attachment as unknown as Record<string, unknown>).unexpected = true;
    expect(validateScriptDocumentV2(unknown).valid).toBe(false);
  });

  it("preserves the exact Research frame binding and single clip owner through explicit Stash return and Undo", () => {
    const before = document();
    const placed = applyRowEditV2(before, 0, {
      kind: "place_stash_rows", rowIds: [id(100)],
      destination: { sectionId: null, afterRowId: null, beforeRowId: null },
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const session = createRowEditSessionV2(placed.document);
    const returned = session.apply({
      kind: "stash_rows", rowIds: [id(100)], bundleId: id(700),
      destination: { sectionId: null, parentRowId: null, afterRowId: null, beforeRowId: null },
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    const saved = returned.document.stash!.flatMap((bundle) => bundle.rows);
    expect(saved).toHaveLength(1);
    expect((saved[0] as NarrationBlockV2).attachedFootage?.clip).toEqual(ready());
    expect(returned.document.stashOutline).toEqual([{ rowId: id(100), kind: "note", parentRowId: null, sectionId: null }]);
    expect(diagnostics(returned.document)).toEqual([]);
    expect(session.undo().document).toEqual({ ...placed.document, rowEditRevision: 3 });
  });
});
