import type { ResearchStillSnapshotV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { ResearchLibraryItemKind } from "./research-library-records.js";
import { indexResearchClipUsageV2 } from "./research-clip-usage-v2.js";
import { formatMlaCitation, type MlaSource } from "./mla-citation.js";

export interface ResearchLibraryItemReference {
  projectId: string;
  itemId: string;
  kind: ResearchLibraryItemKind;
  sourceId?: string;
}

/**
 * Format each used Research source once, retaining the order of first use.
 * Source-level citations deliberately have no quote location.
 */
export function formatResearchSourceList(
  sources: readonly (MlaSource & { id: string; projectId?: string })[],
): string {
  const seen = new Set<string>();
  const entries: string[] = [];
  for (const source of sources) {
    // Research library IDs are scoped by project when the client returns a
    // project-bearing source record; plain citation fixtures remain ID-only.
    const key = `${source.projectId ?? ""}\u0000${source.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const citation = formatMlaCitation(source, { full: true }).citationText;
    if (citation.trim()) entries.push(citation);
  }
  return entries.join("\n");
}

/**
 * Collect exact Research item identities from active script rows only.
 * Quote boxes carry their item ID; clip usage indexing supplies the stable
 * (Research project, clip) identity and knows how to collapse attached mirrors.
 * Placed stills carry their own project and item identity in the visual payload.
 */
export function usedResearchLibraryItems(
  document: ScriptDocumentV2,
  quoteProjectId: string,
): ResearchLibraryItemReference[] {
  const items: ResearchLibraryItemReference[] = [];
  const seen = new Map<string, number>();
  const add = (item: ResearchLibraryItemReference): void => {
    const key = JSON.stringify([item.projectId, item.itemId, item.kind]);
    const index = seen.get(key);
    if (index !== undefined) {
      if (!items[index]!.sourceId && item.sourceId) items[index] = { ...items[index]!, sourceId: item.sourceId };
      return;
    }
    seen.set(key, items.length);
    items.push(item);
  };

  const activeOnly: ScriptDocumentV2 = {
    ...document,
    activeDraft: {
      ...document.activeDraft,
      blocks: document.activeDraft.blocks.filter((block) => block.type !== "narration" || block.state === "active"),
    },
  };
  delete activeOnly.stash;
  delete activeOnly.stashOutline;
  for (const block of activeOnly.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    for (const event of block.overlayEvents) {
      const quote = event.quoteBox;
      if (quote) add({
        projectId: quote.researchProjectId ?? quoteProjectId,
        itemId: quote.researchQuoteId,
        kind: "quote",
        ...(quote.researchSourceId ? { sourceId: quote.researchSourceId } : {}),
      });
    }
    for (const token of block.tokens) {
      const quote = token.researchQuoteProvenance;
      if (quote) add({
        projectId: quote.researchProjectId,
        itemId: quote.researchQuoteId,
        kind: "quote",
        sourceId: quote.researchSourceId,
      });
    }
  }
  for (const usage of indexResearchClipUsageV2(activeOnly)) {
    if (!usage.scriptUses.some((use) => use.kind !== "unattached")) continue;
    add({ projectId: usage.researchProjectId, itemId: usage.clipId, kind: "clip" });
  }
  // Keep the existing quote/clip ordering; append stills in active row,
  // primary-slot, then overlay order. Waiting visuals are not placed content.
  const addStill = (still: ResearchStillSnapshotV2 | undefined): void => {
    if (still) add({ projectId: still.researchProjectId, itemId: still.itemId, kind: "still" });
  };
  for (const block of activeOnly.activeDraft.blocks) {
    if (block.type !== "narration") continue;
    for (const slot of block.primaryVisualSequence?.slots ?? []) {
      if (slot.kind === "content" && slot.payload.kind === "visual") addStill(slot.payload.researchStill);
    }
    for (const event of block.overlayEvents) addStill(event.payload.researchStill);
  }
  return items;
}
