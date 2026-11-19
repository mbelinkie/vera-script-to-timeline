import { describe, expect, it, vi } from "vitest";

const formatMlaCitation = vi.hoisted(() => vi.fn());
vi.mock("../src/mla-citation.js", () => ({ formatMlaCitation }));

import {
  formatResearchSourceList,
  usedResearchLibraryItems,
} from "../src/research-source-list.js";
import type { MlaSource } from "../src/mla-citation.js";
import { researchId, researchNestedNote, researchOccurrence, researchStashFixture } from "./issue-367-fixture.js";

type TestSource = MlaSource & { id: string; label: string; projectId?: string };

function source(id: string, label: string): TestSource {
  return { id, label } as TestSource;
}

describe("Research source list", () => {
  it("deduplicates by source ID, keeps first-use order, and requests full citations without a quote location", () => {
    formatMlaCitation.mockImplementation((value: TestSource, options: { full?: boolean; location?: string }) => ({
      citationText: value.label ? `${value.label}${options.full ? " [full]" : ""}` : "",
      italicSpan: null,
    }));
    const first = source(researchId(980001), "First source https://first.example");
    const repeated = source(first.id, "A later quote location should not replace the source");
    const second = source(researchId(980002), "Second source https://second.example");
    const empty = source(researchId(980005), "");

    expect(formatResearchSourceList([first, repeated, second, empty])).toBe(
      "First source https://first.example [full]\nSecond source https://second.example [full]",
    );
    expect(formatMlaCitation).toHaveBeenNthCalledWith(1, first, { full: true });
    expect(formatMlaCitation).toHaveBeenNthCalledWith(2, second, { full: true });

    const sameIdInOtherProject = { ...first, projectId: researchId(980003), label: "Other project source" };
    expect(formatResearchSourceList([{ ...first, projectId: researchId(980004) }, sameIdInOtherProject])).toBe(
      "First source https://first.example [full]\nOther project source [full]",
    );
  });

  it("collects each active quote and clip item once, ignoring Stash, excluded rows, and unattached-only clips", () => {
    const { doc } = researchStashFixture(false);
    const activeClip = researchOccurrence(981000, false);
    const activeNote = researchNestedNote(981100);
    const quote = {
      researchQuoteId: researchId(981200), displayText: "Quote", speakerName: "", speakerTitle: "",
      citationText: "Citation", italicSpan: null, templateRevision: "quote-box-v1",
      backgroundPayloadId: researchId(981201),
    };
    activeNote.overlayEvents[0]!.quoteBox = quote;
    activeNote.overlayEvents.push({ ...activeNote.overlayEvents[0]!, id: researchId(981202), quoteBox: quote });

    const excluded = researchNestedNote(981300);
    excluded.state = "excluded";
    excluded.overlayEvents[0]!.quoteBox = { ...quote, researchQuoteId: researchId(981301) };

    const unattached = researchNestedNote(981400);
    const baseSlot = unattached.primaryVisualSequence!.slots[0]!;
    if (baseSlot.kind !== "content" || baseSlot.payload.kind !== "visual") throw new Error("Missing clip payload");
    delete unattached.primaryVisualSequence;
    unattached.overlayEvents = [];
    unattached.unattachedVisuals = [{ slotId: researchId(981401), payload: baseSlot.payload, version: 1 }];

    doc.activeDraft.blocks = [activeClip, activeNote, excluded, unattached];
    expect(usedResearchLibraryItems(doc, researchId(981250))).toEqual([
      { projectId: researchId(981250), itemId: researchId(981200), kind: "quote" },
      { projectId: researchId(710002), itemId: researchId(710001), kind: "clip" },
    ]);
    expect(doc.stash).toBeDefined();
  });
});
