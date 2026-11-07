import { createResearchClipOccurrenceV2, type ResearchLoggedCandidateInputV2 } from "../src/authoring-v2-research-snapshot.js";
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
