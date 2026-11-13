import { describe, expect, it } from "vitest";

import {
  destinationAfterDraftRowV2,
  formatClipTime,
  formatLoggedResearchClipV2,
  insertLoggedResearchClipV2,
} from "../src/research-clip-commands.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import {
  researchCandidate, researchId, researchNote, researchStashFixture,
} from "./issue-367-fixture.js";

const ids = (start: number) => {
  let next = start;
  return () => researchId(next++);
};

describe("Research clip Draft commands", () => {
  it("inserts after the named row with an immutable, unresolved source snapshot", () => {
    const doc = researchStashFixture(false).doc;
    const first = researchNote(820100);
    const second = researchNote(820200);
    doc.activeDraft.blocks = [first, second];
    const before = structuredClone(doc);
    const candidate = researchCandidate();
    const original = structuredClone(candidate);

    const inserted = insertLoggedResearchClipV2(doc, candidate, first.id, ids(850001));
    expect(inserted.activeDraft.blocks.map((row) => row.id)).toEqual([
      first.id, researchId(850001), second.id,
    ]);
    const clip = inserted.activeDraft.blocks[1];
    expect(clip?.type).toBe("visual_only");
    if (clip?.type !== "visual_only") throw new Error("Expected a visual-only Research row");
    expect(clip.payload.payloadId).toBe(researchId(850002));
    expect(clip.payload.pictureKind).toBe("unresolved_visual");
    expect(clip.frameBinding).toBeUndefined();
    expect(clip.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    expect(clip.researchClip).toMatchObject({
      clipId: original.id,
      clipVersion: original.version,
      video: original.video,
      englishText: original.englishText,
      loggedSelection: {
        text: original.selection.text,
        timingPrecision: original.selection.timingPrecision,
        exportStartMs: 500,
        exportEndMs: 4500,
      },
    });
    expect(inserted.rowEditRevision).toBe(1);
    expect(validateScriptDocumentV2(inserted).valid).toBe(true);
    expect(doc).toEqual(before);
    expect(candidate).toEqual(original);
    // A later mutation to the fetched DTO cannot retarget an already-authored row.
    candidate.video.title = "changed at Research";
    expect(clip.researchClip?.video.title).toBe(original.video.title);
  });

  it("resolves the exact end-of-section gap, not the next section", () => {
    const doc = researchStashFixture(false).doc;
    const first = researchNote(820100);
    const after = researchNote(820200);
    const heading = {
      type: "section" as const, id: researchId(830100), orderKey: "heading",
      title: "Second", version: 1,
    };
    doc.activeDraft.blocks = [first, heading, after];
    expect(destinationAfterDraftRowV2(doc, first.id)).toEqual({
      sectionId: null, afterRowId: first.id, beforeRowId: null,
    });
    expect(destinationAfterDraftRowV2(doc, after.id)).toEqual({
      sectionId: heading.id, afterRowId: after.id, beforeRowId: null,
    });
    const inserted = insertLoggedResearchClipV2(doc, researchCandidate(), first.id, ids(851001));
    expect(inserted.activeDraft.blocks.map((row) => row.id)).toEqual([
      first.id, researchId(851001), heading.id, after.id,
    ]);
    expect(validateScriptDocumentV2(inserted).valid).toBe(true);
  });

  it("supports a second use of the same clip with distinct row and payload IDs", () => {
    const doc = researchStashFixture(false).doc;
    const first = researchNote(820100);
    doc.activeDraft.blocks = [first];
    const candidate = researchCandidate();
    const makeId = ids(852001);
    const once = insertLoggedResearchClipV2(doc, candidate, first.id, makeId);
    const twice = insertLoggedResearchClipV2(once, candidate, first.id, makeId);
    const clips = twice.activeDraft.blocks.filter((row) => row.type === "visual_only");
    expect(clips).toHaveLength(2);
    expect(clips.map((clip) => clip.id)).toEqual([researchId(852004), researchId(852001)]);
    expect(new Set(clips.map((clip) => clip.payload.payloadId)).size).toBe(2);
    expect(clips[0]!.researchClip).toEqual(clips[1]!.researchClip);
    expect(twice.rowEditRevision).toBe(2);
    expect(validateScriptDocumentV2(twice).valid).toBe(true);
    expect(once.activeDraft.blocks).toHaveLength(2);
  });

  it("rejects non-active anchors, sections, invalid documents and duplicate identities without changes", () => {
    const doc = researchStashFixture(false).doc;
    const anchor = researchNote(820100);
    doc.activeDraft.blocks = [anchor, {
      type: "section", id: researchId(830100), title: "Next", orderKey: "second", version: 1,
    }];
    const before = structuredClone(doc);
    expect(() => insertLoggedResearchClipV2(doc, researchCandidate(), researchId(720100), ids(853001)))
      .toThrow("active script row"); // same row is parked in Stash
    expect(() => insertLoggedResearchClipV2(doc, researchCandidate(), researchId(830100), ids(853001)))
      .toThrow("active script row"); // a heading is not a row
    expect(() => insertLoggedResearchClipV2(doc, researchCandidate(), anchor.id, () => anchor.id))
      .toThrow(); // duplicate occurrence identity
    const invalid = structuredClone(doc);
    invalid.activeDraft.blocks[0]!.orderKey = "";
    expect(() => insertLoggedResearchClipV2(invalid, researchCandidate(), anchor.id, ids(853101)))
      .toThrow("Script validation failed:");
    const badCandidate = researchCandidate();
    badCandidate.selection.exportEndMs = 100;
    expect(() => insertLoggedResearchClipV2(doc, badCandidate, anchor.id, ids(853201)))
      .toThrow(/Invalid Research/);
    expect(doc).toEqual(before);
  });

  it("prints one safe line with source ID, English opening and exact millisecond boundaries", () => {
    const candidate = researchCandidate();
    candidate.video.title = "Title\n\u001b[31m   live\u202e\u2028";
    candidate.englishText = "These are the first twelve words that should appear in the short English preview and no more";
    expect(formatClipTime(61005)).toBe("01:01.005");
    expect(formatClipTime(0)).toBe("00:00.000");
    expect(() => formatClipTime(-1)).toThrow("Invalid clip time");
    const line = formatLoggedResearchClipV2(candidate);
    expect(line).toContain(candidate.id);
    expect(line).toContain("Title [31m live");
    expect(line).toContain("00:00.500–00:04.500");
    expect(line).not.toContain("and no more");
    expect(line).not.toContain("\n");
    expect(line).not.toContain("\r");
    expect(line).not.toContain("\u001b");
    expect(line).not.toMatch(/[\p{Cf}\p{Zl}\p{Zp}]/u);
  });
});
