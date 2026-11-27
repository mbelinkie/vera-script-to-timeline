import { insertResearchStillBrowserV2 } from "../src/research-still-browser-insert.js";
import { createResearchClipOccurrenceV2, type ResearchLoggedCandidateInputV2 } from "../src/authoring-v2-research-snapshot.js";
import { toNarratedPlacementV2, wordlessPlacementsV2 } from "../src/authoring-v2-wordless.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

export const researchId = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

export function researchCandidate(): ResearchLoggedCandidateInputV2 {
  return {
    id: researchId(710001), projectId: researchId(710002), catalogVideoId: researchId(710003),
    version: 3, createdBy: researchId(710004),
    video: { youtubeVideoId: "synthetic", canonicalUrl: "https://youtu.be/synthetic", title: "Frozen research source" },
    selection: {
      trackId: researchId(710005), transcriptVersion: 4,
      firstSegmentId: researchId(710006), lastSegmentId: researchId(710007),
      transcriptStartMs: 1000, transcriptEndMs: 4000, exportStartMs: 500, exportEndMs: 4500,
      text: "Research transcript", timingPrecision: "cue",
    }, englishText: "Frozen English text",
  };
}

export function researchOccurrence(rowNumber: number, resolved = true) {
  return createResearchClipOccurrenceV2({
    rowId: researchId(rowNumber), payloadId: researchId(rowNumber + 1), orderKey: `clip-${rowNumber}`,
    candidate: researchCandidate(),
    ...(resolved ? {
      frameBinding: {
        clipId: researchId(710001), clipVersion: 3, mediaReferenceId: researchId(710008),
        loggedStartFrame: 12, loggedEndFrame: 108,
      }, selectedRange: { startFrame: 24, endFrame: 60 },
    } : {}),
  });
}

export function researchNote(n: number): NarrationBlockV2 {
  const text = "Look closer";
  return {
    type: "narration", id: researchId(n), orderKey: `note-${n}`, text, plainDirection: true,
    tokens: [
      { id: researchId(n + 1), value: "Look", startOffset: 0, endOffset: 4, spoken: false },
      { id: researchId(n + 2), value: "closer", startOffset: 5, endOffset: 11, spoken: false },
    ],
    primaryVisualSequence: { id: researchId(n + 3), version: 1, slots: [{
      id: researchId(n + 4), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

/** Two independently pinned visuals in a narration row (not an attachment mirror). */
export function researchNestedNote(n: number): NarrationBlockV2 {
  const note = researchNote(n);
  delete note.plainDirection;
  note.tokens.forEach((token) => { token.spoken = true; });
  const source = researchOccurrence(n + 20, false);
  const slot = note.primaryVisualSequence!.slots[0]!;
  if (slot.kind !== "content") throw new Error("Expected base content slot");
  slot.payload = {
    kind: "visual", payloadId: researchId(n + 10), pictureKind: "unresolved_visual",
    source: structuredClone(source.payload.source), sourceUsage: null, audioPolicy: "mute",
    framingPolicy: "contain", researchClip: structuredClone(source.researchClip!),
  };
  note.overlayEvents = [{
    id: researchId(n + 11), version: 1,
    payload: {
      kind: "visual", payloadId: researchId(n + 12), pictureKind: "unresolved_visual",
      source: structuredClone(source.payload.source), sourceUsage: null, audioPolicy: "mute",
      framingPolicy: "contain", researchClip: structuredClone(source.researchClip!),
    },
    timing: { kind: "timed", durationMs: 1000, start: { kind: "word", anchor: {
      blockId: note.id, tokenId: note.tokens[0]!.id, affinity: "before",
      quotedWord: "Look", anchorVersion: 1,
    } } },
  }];
  return note;
}

/** A converted attached note has one *projected* slot, not two owned clips. */
export function researchMirroredNote(n: number, resolved = true): NarrationBlockV2 {
  const note = researchNote(n);
  const clip = researchOccurrence(n + 20, resolved);
  note.attachedFootage = { clip };
  note.stashOrigin = { kind: "note", returnEligible: true, parentRowId: null,
    sectionId: null, afterSiblingRowId: null, beforeSiblingRowId: null };
  const slot = note.primaryVisualSequence!.slots[0]!;
  if (slot.kind !== "content") throw new Error("Expected base slot");
  const selected = clip.visualOnlyTiming.selectedSourceRange;
  slot.payload = {
    kind: "visual", payloadId: researchId(n + 30), pictureKind: clip.payload.pictureKind,
    source: structuredClone(clip.payload.source),
    sourceUsage: selected ? { sourceInFrame: selected.startFrame } : null,
    audioPolicy: "mute",
    ...(clip.payload.framingPolicy !== undefined ? { framingPolicy: clip.payload.framingPolicy } : {}),
    researchClip: structuredClone(clip.researchClip!),
    ...(clip.frameBinding ? { frameBinding: structuredClone(clip.frameBinding) } : {}),
    ...(selected ? { selectedSourceRange: structuredClone(selected) } : {}),
  };
  return note;
}

/** The first note is an anchor; the second owns exactly one embedded clip. */
export function researchStashFixture(resolved = true) {
  const anchor = researchNote(720100);
  const note = researchNote(720200);
  const clip = researchOccurrence(730100, resolved);
  note.attachedFootage = { clip };
  const doc: ScriptDocumentV2 = {
    schemaVersion: "script-document/v2", id: researchId(1), projectId: researchId(2), title: "Research Stash phase 3",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
    stash: [
      { id: researchId(740100), rows: [anchor], supportingItems: [] },
      { id: researchId(740200), rows: [note], supportingItems: [] },
    ],
    stashOutline: [
      { rowId: anchor.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: note.id, kind: "note", parentRowId: null, sectionId: null },
    ],
  };
  return { doc, anchor, note, clip };
}

/** Already-bound synthetic primary and waiting uses of the same logged source. */
export function boundPrimaryFixture() {
  const { doc } = researchStashFixture();
  const row = researchNote(850100);
  delete row.plainDirection;
  row.tokens.forEach(token => { token.spoken = true; });
  const first = researchOccurrence(850200);
  const second = researchOccurrence(850300);
  const a = toNarratedPlacementV2(wordlessPlacementsV2(first)[0]!);
  const b = toNarratedPlacementV2(wordlessPlacementsV2(second)[0]!);
  if (!("value" in a) || !("value" in b)) throw new Error("Expected bound clips");
  const slot = row.primaryVisualSequence!.slots[0]!;
  if (slot.kind !== "content") throw new Error("Expected primary slot");
  slot.payload = a.value;
  row.unattachedVisuals = [{ slotId: researchId(850400), version: 1, payload: b.value }];
  doc.activeDraft.blocks = [row];
  return { doc, row, first, second, slot };
}

/** Synthetic saved still placed through the normal browser insertion path. */
export function researchStillFixture(n: number, projectId = researchId(710002), itemId = researchId(n + 20)) {
  const doc = researchStashFixture(false).doc;
  const row = researchNote(n);
  delete row.plainDirection;
  row.tokens.forEach((token) => { token.spoken = true; });
  doc.activeDraft.blocks = [row];
  const still = {
    researchProjectId: projectId, itemId, itemVersion: 1, sourceId: researchId(710090),
    title: "Saved synthetic still", credit: "Synthetic credit", licence: "CC BY",
    provenance: { kind: "url" as const, sourceUrl: "https://example.com/image.jpg", inputSha256: "a".repeat(64) },
    original: { versionId: "original-v1", sha256: "a".repeat(64), byteCount: 1234,
      mimeType: "image/jpeg" as const, width: 1920, height: 1080 },
  };
  const ids = [researchId(n + 30), researchId(n + 31), researchId(n + 32)];
  const result = insertResearchStillBrowserV2(doc, still, {
    expectedDocumentRevision: 0, researchProjectId: projectId, itemId, itemVersion: 1,
    placement: { kind: "selected_words", rowId: row.id, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence!.version,
      startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[0]!.id },
  }, () => ids.shift()!);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  const placed = result.document.activeDraft.blocks[0];
  if (placed?.type !== "narration") throw new Error("Missing still row");
  const slot = placed.primaryVisualSequence?.slots.find((entry) =>
    entry.kind === "content" && entry.payload.kind === "visual" && entry.payload.researchStill);
  if (!slot || slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Missing still payload");
  return { doc: result.document, row: placed, still, payload: slot.payload };
}
