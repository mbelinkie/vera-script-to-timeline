import { describe, expect, it, vi } from "vitest";

const formatMlaCitation = vi.hoisted(() => vi.fn());
vi.mock("../src/mla-citation.js", () => ({ formatMlaCitation }));

import {
  exportScriptSources,
} from "../src/research-citation-commands.js";
import {
  formatResearchSourceList,
  usedResearchLibraryItems,
} from "../src/research-source-list.js";
import type { MlaSource } from "../src/mla-citation.js";
import { researchId, researchNestedNote, researchNote, researchOccurrence, researchStashFixture, researchStillFixture } from "./issue-367-fixture.js";

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

  it("retains a quote source from surviving spoken tokens after its visual cards are removed", () => {
    const { doc } = researchStashFixture(false);
    const projectId = researchId(981251);
    const quoteId = researchId(981252);
    const sourceId = researchId(981253);
    const useId = researchId(981254);
    const row = researchNestedNote(981255);
    delete row.plainDirection;
    row.tokens.forEach((token) => {
      token.spoken = true;
      token.researchQuoteProvenance = { researchProjectId: projectId, researchQuoteId: quoteId, researchSourceId: sourceId, useId };
    });
    // Both the quote box and its background are gone; ordinary narration still remembers its source.
    row.overlayEvents = [];
    row.primaryVisualSequence!.slots = row.primaryVisualSequence!.slots.filter((slot) =>
      slot.kind !== "content" || slot.payload.kind !== "visual");
    doc.activeDraft.blocks = [row];

    expect(usedResearchLibraryItems(doc, researchId(981250))).toEqual([
      { projectId, itemId: quoteId, kind: "quote", sourceId },
    ]);

    row.tokens = [];
    expect(usedResearchLibraryItems(doc, researchId(981250))).toEqual([]);
  });

  it("exports a retained quote source without requiring its deleted quote item", async () => {
    formatMlaCitation.mockImplementation((value: TestSource) => ({
      citationText: value.label, italicSpan: null,
    }));
    const { doc } = researchStashFixture(false);
    const projectId = researchId(981261);
    const quoteId = researchId(981262);
    const sourceId = researchId(981263);
    const row = researchNote(981264);
    delete row.plainDirection;
    row.tokens.forEach((token) => {
      token.spoken = true;
      token.researchQuoteProvenance = {
        researchProjectId: projectId, researchQuoteId: quoteId, researchSourceId: sourceId, useId: researchId(981265),
      };
    });
    row.overlayEvents = [];
    doc.activeDraft.blocks = [row];
    const retainedSource = { id: sourceId, projectId, label: "Retained quote source" };
    const client = {
      item: vi.fn(),
      source: vi.fn(async () => retainedSource),
    };

    await expect(exportScriptSources(doc, projectId, client as never)).resolves.toBe("Retained quote source");
    expect(client.item).not.toHaveBeenCalled();
    expect(client.source).toHaveBeenCalledWith(projectId, sourceId);
  });
});

it("collects placed stills from primary slots and overlays, but not parked, excluded or waiting visuals", () => {
  const first = researchStillFixture(982000);
  const other = researchStillFixture(982100, researchId(982900), first.still.itemId);
  const overlay = researchNestedNote(982200);
  delete overlay.primaryVisualSequence;
  overlay.overlayEvents[0]!.payload = other.payload;
  const duplicate = researchStillFixture(982300, first.still.researchProjectId, first.still.itemId);
  const excluded = researchStillFixture(982400);
  excluded.row.state = "excluded";
  const loose = researchStillFixture(982500);
  delete loose.row.primaryVisualSequence;
  loose.row.unattachedVisuals = [{ slotId: researchId(982599), payload: loose.payload, version: 1 }];
  const parked = researchStillFixture(982600);
  first.doc.stash = [{ id: researchId(982699), rows: [parked.row], supportingItems: [] }];
  first.doc.activeDraft.blocks = [first.row, overlay, duplicate.row, excluded.row, loose.row];
  const before = structuredClone(first.doc);
  const expected = [
    { projectId: first.still.researchProjectId, itemId: first.still.itemId, kind: "still" },
    { projectId: other.still.researchProjectId, itemId: other.still.itemId, kind: "still" },
  ];
  expect(usedResearchLibraryItems(first.doc, researchId(982999))).toEqual(expected);
  expect(usedResearchLibraryItems(first.doc, researchId(982999))).toEqual(expected);
  expect(first.doc).toEqual(before);
});
