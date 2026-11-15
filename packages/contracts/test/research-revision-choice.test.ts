import { describe, expect, it } from "vitest";
import { snapshotResearchCandidateV2 } from "../src/authoring-v2-research-snapshot.js";
import { assessResearchRevision } from "../src/research-revision-choice.js";
import { researchCandidate, researchId } from "./issue-367-fixture.js";

describe("Research pinned-revision comparison", () => {
  it("reports a matching snapshot as current and returns an isolated pin copy", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    const result = assessResearchRevision(pinned, candidate);
    expect(result.kind).toBe("current");
    if (result.kind !== "current") throw new Error("Expected current pin");
    expect(result.pinned).toEqual(pinned);
    expect(result.pinned).not.toBe(pinned);
    result.pinned.video.title = "changed result";
    expect(pinned.video.title).toBe("Frozen research source");
    expect(candidate.video.title).toBe("Frozen research source");
  });

  it("reports version-only updates even when frozen fields did not change", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    const result = assessResearchRevision(pinned, { ...candidate, version: 4 });
    expect(result.kind).toBe("update_available");
    if (result.kind !== "update_available") throw new Error("Expected update");
    expect(result.changedFields).toEqual([]);
    expect(result.pinned.clipVersion).toBe(3);
    expect(result.latest.clipVersion).toBe(4);
    expect(candidate.version).toBe(3);
    expect(pinned.clipVersion).toBe(3);
  });

  it("identifies each changed frozen field without mutating either input", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    const edited = {
      ...candidate,
      version: 4,
      catalogVideoId: researchId(710099),
      createdBy: researchId(710098),
      createdAt: "2026-10-20T12:00:00Z",
      updatedAt: "2026-11-14T12:00:00Z",
      video: { ...candidate.video, title: "Changed Research source" },
      selection: { ...candidate.selection, text: "Different transcript" },
      englishText: "Different English text",
      originalText: "Original transcript",
    };
    const before = structuredClone(edited);
    const result = assessResearchRevision(pinned, edited);
    expect(result.kind).toBe("update_available");
    if (result.kind !== "update_available") throw new Error("Expected update");
    expect(result.changedFields).toEqual([
      "catalogVideoId", "video", "loggedSelection", "englishText", "originalText",
      "createdBy", "createdAt", "updatedAt",
    ]);
    expect(edited).toEqual(before);
    expect(pinned).toEqual(snapshotResearchCandidateV2(candidate));
    result.pinned.loggedSelection.text = "result-only pin edit";
    result.latest.video.title = "result-only latest edit";
    expect(pinned.loggedSelection.text).toBe("Research transcript");
    expect(edited.video.title).toBe("Changed Research source");
  });

  it("refuses equal-version content drift but not identical copies", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    expect(assessResearchRevision(pinned, { ...candidate, englishText: "altered" }))
      .toEqual({ kind: "inconsistent", reason: "same_version_changed" });
    expect(assessResearchRevision(pinned, { ...candidate, video: { ...candidate.video } }).kind)
      .toBe("current");
  });

  it("refuses older versions and cross-project or cross-clip candidates", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    expect(assessResearchRevision(pinned, { ...candidate, version: 2 }))
      .toEqual({ kind: "inconsistent", reason: "older_version" });
    expect(assessResearchRevision(pinned, { ...candidate, version: 4, projectId: researchId(711001) }))
      .toEqual({ kind: "inconsistent", reason: "identity" });
    expect(assessResearchRevision(pinned, { ...candidate, version: 4, id: researchId(711002) }))
      .toEqual({ kind: "inconsistent", reason: "identity" });
  });

  it("fails closed on malformed Research read results", () => {
    const candidate = researchCandidate();
    const pinned = snapshotResearchCandidateV2(candidate);
    expect(() => assessResearchRevision(pinned, { ...candidate, version: 0 })).toThrow(RangeError);
    expect(() => assessResearchRevision(pinned, { ...candidate, projectId: "not-a-uuid" })).toThrow(RangeError);
    expect(() => assessResearchRevision(pinned, {
      ...candidate, selection: { ...candidate.selection, exportEndMs: 100 },
    })).toThrow(RangeError);
  });
});
