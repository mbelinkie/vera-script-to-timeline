import type {
  NarrationBlockV2,
  ResearchClipSnapshotV2,
  ScriptDocumentV2,
} from "./generated/contracts-v2.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

type Row = Exclude<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "section" }>;
type ClipIdentity = Pick<ResearchClipSnapshotV2, "researchProjectId" | "clipId">;

export type ResearchClipLocationKindV2 = "visual_only" | "primary" | "overlay" | "unattached" | "attached";

export interface ResearchClipUseLocationV2 {
  rowId: string;
  /** Saved row or visual-placement ID, independent of excerpt and Research revision. */
  placementId: string;
  kind: ResearchClipLocationKindV2;
  rowExcerpt: string;
}

export interface ResearchClipUsageV2 extends ClipIdentity {
  scriptCount: number;
  scriptUses: ResearchClipUseLocationV2[];
  stashCount: number;
  stashUses: ResearchClipUseLocationV2[];
}

/** Use the authored row text, not transcript text or the spoken-only projection. */
function rowExcerpt(row: Row): string {
  if (row.type === "visual_only") return "";
  const text = row.text.trim();
  const words = text.match(/\S+/gu) ?? [];
  return words.length <= 8
    ? text
    : `${words.slice(0, 3).join(" ")} … ${words.slice(-5).join(" ")}`;
}

/**
 * An attached footage owner can also be displayed as a single primary slot.
 * Authored edits clear return eligibility without removing that exact mirror,
 * so provenance flags cannot decide the count. Independent or stale placements
 * are still counted separately unless every mirror field matches exactly.
 */
function hasExactAttachedMirror(row: NarrationBlockV2): boolean {
  const clip = row.attachedFootage?.clip;
  const slots = row.primaryVisualSequence?.slots;
  const slot = slots?.length === 1 ? slots[0] : undefined;
  if (!clip || slot?.kind !== "content" || slot.payload.kind !== "visual") return false;

  const payload = slot.payload;
  const selected = clip.visualOnlyTiming.selectedSourceRange;
  return payload.pictureKind === clip.payload.pictureKind &&
    payload.framingPolicy === clip.payload.framingPolicy &&
    payload.audioPolicy === (clip.payload.audioPolicy === "quiet" ? "quiet" : "mute") &&
    sameAuthoringJsonV2(payload.source, clip.payload.source) &&
    sameAuthoringJsonV2(payload.researchClip, clip.researchClip) &&
    sameAuthoringJsonV2(payload.frameBinding, clip.frameBinding) &&
    sameAuthoringJsonV2(payload.selectedSourceRange, selected) &&
    sameAuthoringJsonV2(payload.sourceUsage, selected ? { sourceInFrame: selected.startFrame } : null);
}

/**
 * Derive current script and Stash occurrences without modifying the document.
 * The optional authorized catalog identities also produce zero-use records.
 * Callers validate untrusted documents and enforce Research catalog access.
 */
export function indexResearchClipUsageV2(
  document: ScriptDocumentV2,
  knownClips: readonly ClipIdentity[] = [],
): ResearchClipUsageV2[] {
  const index = new Map<string, ResearchClipUsageV2>();
  const ensure = (identity: ClipIdentity): ResearchClipUsageV2 => {
    const key = JSON.stringify([identity.researchProjectId, identity.clipId]);
    let entry = index.get(key);
    if (!entry) {
      entry = {
        researchProjectId: identity.researchProjectId,
        clipId: identity.clipId,
        scriptCount: 0,
        scriptUses: [],
        stashCount: 0,
        stashUses: [],
      };
      index.set(key, entry);
    }
    return entry;
  };
  for (const identity of knownClips) ensure(identity);

  const visit = (row: Row, surface: "script" | "stash"): void => {
    const excerpt = rowExcerpt(row);
    const add = (
      snapshot: ResearchClipSnapshotV2 | undefined,
      kind: ResearchClipLocationKindV2,
      placementId: string,
    ): void => {
      if (!snapshot) return;
      const location = { rowId: row.id, placementId, kind, rowExcerpt: excerpt };
      const entry = ensure(snapshot);
      if (surface === "script") entry.scriptUses.push(location);
      else entry.stashUses.push(location);
    };

    if (row.type === "visual_only") {
      add(row.researchClip, "visual_only", row.id);
      for (const visual of row.additionalVisuals ?? []) {
        add(visual.researchClip, "visual_only", visual.payload.payloadId);
      }
    } else if (row.type === "narration") {
      // These are structural saved-occurrence order, not inferred playback times.
      for (const slot of row.primaryVisualSequence?.slots ?? []) {
        if (slot.kind === "content" && slot.payload.kind === "visual") {
          add(slot.payload.researchClip, "primary", slot.id);
        }
      }
      for (const overlay of row.overlayEvents) {
        add(overlay.payload.researchClip, "overlay", overlay.id);
      }
      for (const loose of row.unattachedVisuals ?? []) {
        add(loose.payload.researchClip, "unattached", loose.slotId);
      }
      if (row.attachedFootage && !hasExactAttachedMirror(row)) {
        add(row.attachedFootage.clip.researchClip, "attached", row.attachedFootage.clip.id);
      }
    }
  };

  for (const row of document.activeDraft.blocks) {
    if (row.type !== "section") visit(row, "script");
  }

  const parked = (document.stash ?? []).flatMap((bundle) => bundle.rows);
  if (document.stashOutline) {
    const byId = new Map(parked.map((row) => [row.id, row] as const));
    const seen = new Set<string>();
    for (const item of document.stashOutline) {
      const row = byId.get(item.rowId);
      if (!row || seen.has(row.id)) continue;
      visit(row, "stash");
      seen.add(row.id);
    }
    // A partially migrated/legacy outline must not hide a parked occurrence.
    for (const row of parked) {
      if (seen.has(row.id)) continue;
      visit(row, "stash");
      seen.add(row.id);
    }
  } else {
    for (const row of parked) visit(row, "stash");
  }

  return [...index.values()].map((entry) => ({
    ...entry,
    scriptCount: entry.scriptUses.length,
    stashCount: entry.stashUses.length,
  }));
}
