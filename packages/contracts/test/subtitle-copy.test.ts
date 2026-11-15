import { describe, expect, it } from "vitest";
import type { ResearchClipSnapshotV2 } from "../src/generated/contracts-v2.js";
import { snapshotResearchCandidateV2 } from "../src/authoring-v2-research-snapshot.js";
import {
  approveSubtitleCopyV1,
  assertValidSubtitleCopyV1,
  deriveSubtitleCopyV1,
  reviseSubtitleCopyV1,
  type SubtitleCopyTrackV1,
} from "../src/subtitle-copy.js";
import { researchCandidate, researchId } from "./issue-367-fixture.js";

const trackId = researchId(900001);
const occurrenceId = researchId(900002);
const segmentId = researchId(900003);
const reviewerId = researchId(900004);

function source(language: string | null = "es"): ResearchClipSnapshotV2 {
  const candidate = researchCandidate();
  return snapshotResearchCandidateV2({
    ...candidate,
    video: { ...candidate.video, ...(language === null ? {} : { sourceLanguage: language }) },
  });
}

function derive(pin = source()): SubtitleCopyTrackV1 {
  return deriveSubtitleCopyV1(trackId, occurrenceId, segmentId, pin);
}

describe("source-pinned English subtitle copy", () => {
  it("derives a needs-review copy over only the pinned transcript selection", () => {
    const pin = source("es-MX");
    const baseline = structuredClone(pin);
    const track = derive(pin);
    expect(track.schemaVersion).toBe("subtitle-copy/v1");
    expect(track.id).toBe(trackId);
    expect(track.occurrenceId).toBe(occurrenceId);
    expect(track.version).toBe(1);
    expect(track.sourceLanguage).toBe("es-mx");
    expect(track.reviewState).toBe("needs_review");
    expect(track.reviewerId).toBeNull();
    expect(track.source).toEqual(baseline);
    expect(track.source).not.toBe(pin);
    expect(track.source.loggedSelection).not.toBe(pin.loggedSelection);
    expect(track.segments).toEqual([{
      id: segmentId,
      sourceFirstSegmentId: pin.loggedSelection.firstSegmentId,
      sourceLastSegmentId: pin.loggedSelection.lastSegmentId,
      sourceStartMs: 1000,
      sourceEndMs: 4000,
      timingPrecision: "cue",
      englishText: pin.englishText,
      timingOverride: null,
      version: 1,
    }]);
    assertValidSubtitleCopyV1(track);
    pin.video.title = "Updated caller-owned data";
    expect(track.source).toEqual(baseline);
  });

  it("edits only the occurrence's English words, preserving both source and history", () => {
    const pin = source();
    const original = derive(pin);
    const before = structuredClone(original);
    const revised = reviseSubtitleCopyV1(original, pin, 1, "Reviewed English", reviewerId);
    expect(revised.version).toBe(2);
    expect(revised.reviewState).toBe("reviewed");
    expect(revised.reviewerId).toBe(reviewerId);
    expect(revised.segments[0]?.englishText).toBe("Reviewed English");
    expect(revised.segments[0]?.version).toBe(2);
    expect(revised.source).toEqual(pin);
    expect(revised.source).not.toBe(original.source);
    expect(revised.segments[0]?.sourceStartMs).toBe(1000);
    expect(revised.segments[0]?.timingOverride).toBeNull();
    expect(original).toEqual(before);
    expect(pin.englishText).toBe("Frozen English text");
    assertValidSubtitleCopyV1(revised);
  });

  it("keeps two uses of the same Research clip independently editable", () => {
    const pin = source();
    const first = derive(pin);
    const second = deriveSubtitleCopyV1(researchId(900010), researchId(900011), researchId(900012), pin);
    const changed = reviseSubtitleCopyV1(first, pin, 1, "Use one only", reviewerId);
    expect(second.segments[0]?.englishText).toBe("Frozen English text");
    expect(second.reviewState).toBe("needs_review");
    expect(changed.occurrenceId).not.toBe(second.occurrenceId);
  });

  it("allows explicit review without rewriting copy or increasing segment version", () => {
    const pin = source("mul");
    const initial = derive(pin);
    const approved = approveSubtitleCopyV1(initial, pin, 1, reviewerId);
    expect(approved.reviewState).toBe("reviewed");
    expect(approved.reviewerId).toBe(reviewerId);
    expect(approved.version).toBe(2);
    expect(approved.segments).toEqual(initial.segments);
    expect(approved.segments).not.toBe(initial.segments);
    expect(initial.reviewState).toBe("needs_review");
    expect(() => approveSubtitleCopyV1(approved, pin, 2, reviewerId)).toThrow(RangeError);
    const edit = reviseSubtitleCopyV1(approved, pin, 2, "More readable", researchId(900005));
    expect(edit.version).toBe(3);
    expect(edit.segments[0]?.version).toBe(2);
    assertValidSubtitleCopyV1(edit);
  });

  it("treats missing, mixed and unknown language as requiring translation, but not English-only", () => {
    for (const language of [null, "und", "mul", "mixed", "fr", "zh-Hant"]) {
      const pin = source(language);
      expect(derive(pin).sourceLanguage).toBe(language?.toLowerCase() ?? "und");
    }
    for (const language of ["en", "EN-us", "en-GB"]) {
      expect(() => derive(source(language))).toThrow(/English-only/u);
    }
    expect(() => derive(source("es_US"))).toThrow(/language/u);
  });

  it("rejects invalid or reused identity IDs", () => {
    const pin = source();
    expect(() => deriveSubtitleCopyV1("not-uuid", occurrenceId, segmentId, pin)).toThrow(RangeError);
    expect(() => deriveSubtitleCopyV1(trackId, trackId, segmentId, pin)).toThrow(RangeError);
    expect(() => deriveSubtitleCopyV1(trackId, occurrenceId, trackId.toUpperCase(), pin)).toThrow(RangeError);
  });

  it("rejects blank, oversized or control-character translations without changing input", () => {
    const pin = source();
    const before = structuredClone(pin);
    for (const englishText of ["", " \n ", "a".repeat(16_001), "bad\u0000text"]) {
      expect(() => derive({ ...pin, englishText })).toThrow(RangeError);
    }
    const track = derive(pin);
    for (const englishText of ["", " ", "x".repeat(16_001), "bad\u001btext", track.segments[0]!.englishText]) {
      expect(() => reviseSubtitleCopyV1(track, pin, 1, englishText, reviewerId)).toThrow(RangeError);
    }
    expect(pin).toEqual(before);
  });

  it("refuses transcript timing outside exported evidence or absent original transcript", () => {
    const pin = source();
    const outside = structuredClone(pin);
    outside.loggedSelection.transcriptStartMs = 100;
    expect(() => derive(outside)).toThrow(RangeError);
    const backwards = structuredClone(pin);
    backwards.loggedSelection.transcriptEndMs = backwards.loggedSelection.transcriptStartMs;
    expect(() => derive(backwards)).toThrow(RangeError);
    const missingText = structuredClone(pin);
    missingText.loggedSelection.text = "  ";
    expect(() => derive(missingText)).toThrow(RangeError);
    const invalidVersion = structuredClone(pin);
    invalidVersion.loggedSelection.transcriptVersion = 0;
    expect(() => derive(invalidVersion)).toThrow(RangeError);
  });

  it("refuses changed or stale pins, including same-version drift and changed translation", () => {
    const pin = source();
    const track = derive(pin);
    const variants: ResearchClipSnapshotV2[] = [];
    for (const change of [
      (s: ResearchClipSnapshotV2) => { s.clipId = researchId(987001); },
      (s: ResearchClipSnapshotV2) => { s.researchProjectId = researchId(987002); },
      (s: ResearchClipSnapshotV2) => { s.clipVersion += 1; },
      (s: ResearchClipSnapshotV2) => { s.clipVersion -= 1; },
      (s: ResearchClipSnapshotV2) => { s.loggedSelection.transcriptVersion += 1; },
      (s: ResearchClipSnapshotV2) => { s.loggedSelection.text = "Different transcript"; },
      (s: ResearchClipSnapshotV2) => { s.englishText = "New translation"; },
      (s: ResearchClipSnapshotV2) => { s.loggedSelection.firstSegmentId = researchId(987003); },
    ]) {
      const altered = structuredClone(pin);
      change(altered);
      variants.push(altered);
    }
    for (const altered of variants) {
      expect(() => reviseSubtitleCopyV1(track, altered, 1, "Change", reviewerId)).toThrow(RangeError);
      expect(() => approveSubtitleCopyV1(track, altered, 1, reviewerId)).toThrow(RangeError);
    }
    expect(() => reviseSubtitleCopyV1(track, structuredClone(pin), 1, "Changed", reviewerId))
      .not.toThrow();
  });

  it("rejects stale CAS, bad reviewers and exhausted versions", () => {
    const pin = source();
    const track = derive(pin);
    expect(() => reviseSubtitleCopyV1(track, pin, 0, "Changed", reviewerId)).toThrow(RangeError);
    expect(() => reviseSubtitleCopyV1(track, pin, 2, "Changed", reviewerId)).toThrow(RangeError);
    expect(() => approveSubtitleCopyV1(track, pin, 1, "invalid")).toThrow(RangeError);
    const exhausted = structuredClone(track);
    exhausted.version = Number.MAX_SAFE_INTEGER;
    exhausted.segments[0]!.version = Number.MAX_SAFE_INTEGER;
    expect(() => reviseSubtitleCopyV1(exhausted, pin, Number.MAX_SAFE_INTEGER, "Changed", reviewerId))
      .toThrow(RangeError);
  });

  it("rejects forged source bounds, timing overrides, review attribution and track shapes", () => {
    const pin = source();
    const original = derive(pin);
    const tampered: Array<(copy: SubtitleCopyTrackV1) => void> = [
      (t) => { t.segments[0]!.sourceStartMs = 500; },
      (t) => { t.segments[0]!.sourceEndMs = 4500; },
      (t) => { t.segments[0]!.sourceFirstSegmentId = researchId(901002); },
      (t) => { t.segments[0]!.timingPrecision = "word"; },
      (t) => { t.segments[0]!.timingOverride = 123 as unknown as null; },
      (t) => { t.segments[0]!.version = 2; },
      (t) => { t.occurrenceId = t.id.toUpperCase(); },
      (t) => { t.segments[0]!.id = t.id.toUpperCase(); },
      (t) => { t.version = 2; t.segments[0]!.englishText = "Forged edit"; },
      (t) => { t.reviewState = "reviewed"; },
      (t) => { t.reviewerId = reviewerId; },
      (t) => { t.sourceLanguage = "de"; },
      (t) => { t.segments.push(structuredClone(t.segments[0]!)); },
      (t) => { (t as unknown as Record<string, unknown>).unexpected = true; },
      (t) => { t.source.englishText = "Rewritten source"; },
    ];
    for (const change of tampered) {
      const candidate = structuredClone(original);
      change(candidate);
      expect(() => assertValidSubtitleCopyV1(candidate)).toThrow(RangeError);
      expect(() => reviseSubtitleCopyV1(candidate, pin, 1, "Edited", reviewerId)).toThrow(RangeError);
    }
    expect(original).toEqual(derive(pin));
  });
});
