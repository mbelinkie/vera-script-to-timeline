import { describe, expect, it } from "vitest";

import { researchQuoteUsage } from "../browser/research-panel.js";
import { filterLoggedResearchClips, filterResearchLibraryItems, libraryFilterOptions } from "../browser/research-search.js";

const projectId = "11111111-1111-4111-8111-111111111111";
const otherProject = "22222222-2222-4222-8222-222222222222";
const clips = [
  { id: "a", projectId, createdAt: "2026-11-10T12:00:00Z", video: { title: "Harbor" },
    englishText: "One long description ends in umbrellas", selection: { text: "first few words" },
    originalText: "puerto" },
  { id: "b", projectId, createdAt: "2026-11-11T12:00:00Z", video: { title: "Sensor" },
    englishText: "green light", selection: { text: "signal" }, createdBy: "Dana", channel: "Channel name" },
  { id: "c", projectId: otherProject, createdAt: "2026-11-12T12:00:00Z", video: { title: "Secret" },
    englishText: "umbrella", selection: { text: "hidden" } },
];
const quotes = [
  { itemId: "q1", researchProjectId: projectId, createdAt: "2026-11-13T12:00:00Z",
    text: "The harbor light was green", displayText: "The harbor light was green",
    speakerName: "Dana Lee", speakerTitle: "Engineer", sourceTitle: "Harbor Journal",
    citationText: "Lee, Dana. Harbor Journal.", credit: "Harbor Archive", logger: "logger-a", topics: ["Transport"] },
  { itemId: "q2", researchProjectId: projectId, createdAt: "2026-11-12T12:00:00Z",
    text: "A silent signal", displayText: "A silent signal", speakerName: "A. Chen",
    sourceTitle: "Signal Weekly", citationText: "Chen, A. Signal Weekly.", logger: "logger-b", topics: ["Science"] },
  { itemId: "q3", researchProjectId: otherProject, createdAt: "2026-11-14T12:00:00Z",
    text: "Secret text", sourceTitle: "Private source", citationText: "" },
];

describe("authorized Research title and full transcript filtering", () => {
  it("matches full text and title, but never incidental metadata or other projects", () => {
    for (const query of ["umbrellas", "puerto", "Harbor", "first few words"]) {
      expect(filterLoggedResearchClips(clips, [], { projectId, query }).map((c) => c.id)).toEqual(["a"]);
    }
    for (const query of ["Dana", "Channel name", "2026", "11111111", "Secret", "hidden"]) {
      expect(filterLoggedResearchClips(clips, [], { projectId, query })).toEqual([]);
    }
    expect(filterLoggedResearchClips(clips, [], { projectId: projectId.toUpperCase(), query: " HARBOR " }).map((c) => c.id))
      .toEqual(["a"]);
  });

  it("hides only script uses; Stash is not counted as used", () => {
    const usage = [{ researchProjectId: projectId.toUpperCase(), clipId: "b", scriptCount: 3, stashCount: 0 }];
    expect(filterLoggedResearchClips(clips, usage, { projectId }).map((c) => c.id)).toEqual(["a"]);
    expect(filterLoggedResearchClips(clips, usage, { projectId, showUsed: true }).map((c) => c.id))
      .toEqual(["b", "a"]);
    expect(filterLoggedResearchClips(clips, [{ ...usage[0]!, scriptCount: 0, stashCount: 2 }],
      { projectId }).map((c) => c.id)).toEqual(["b", "a"]);
  });

  it("sorts deterministically and favors seeded title/full-transcript matches without filtering", () => {
    expect(filterLoggedResearchClips(clips, [], { projectId }).map((c) => c.id)).toEqual(["b", "a"]);
    expect(filterLoggedResearchClips(clips, [], { projectId, sort: "oldest" }).map((c) => c.id)).toEqual(["a", "b"]);
    expect(filterLoggedResearchClips(clips, [], { projectId, sort: "title" }).map((c) => c.id)).toEqual(["a", "b"]);
    expect(filterLoggedResearchClips(clips, [], { projectId, seed: "harbor umbrellas" }).map((c) => c.id))
      .toEqual(["a", "b"]);
    expect(clips[0]?.englishText).toContain("umbrellas");
  });
});

describe("mixed authorized Library filtering", () => {
  it("searches all quote text and attribution while keeping quote metadata and projects private", () => {
    for (const query of ["green", "Dana Lee", "Engineer", "Harbor Journal", "Harbor Archive", "Lee, Dana"]) {
      expect(filterResearchLibraryItems([], quotes, [], { projectId, query }).map((row) => row.item.itemId))
        .toEqual(["q1"]);
    }
    for (const query of ["q1", "logger-a", "Transport", "2026", "Private source", "Secret text"]) {
      expect(filterResearchLibraryItems([], quotes, [], { projectId, query })).toEqual([]);
    }
    expect(filterResearchLibraryItems(clips, quotes, [], { projectId: projectId.toUpperCase(), kind: "quotes" })
      .map((row) => row.item.itemId)).toEqual(["q1", "q2"]);
    expect(filterResearchLibraryItems(clips, quotes, [], { projectId, kind: "footage" })
      .map((row) => row.kind)).toEqual(["footage", "footage"]);
  });

  it("applies use, logger, topic, sort and seed ranking consistently across kinds", () => {
    const usage = [{ kind: "quote" as const, researchProjectId: projectId, itemId: "q1", scriptCount: 2 }];
    expect(filterResearchLibraryItems([], quotes, usage, { projectId }).map((row) => row.item.itemId))
      .toEqual(["q2"]);
    expect(filterResearchLibraryItems([], quotes, usage, { projectId, showUsed: true }).map((row) => row.item.itemId))
      .toEqual(["q1", "q2"]);
    expect(filterResearchLibraryItems([], quotes, [], { projectId, logger: "LOGGER-A", topic: "transport" })
      .map((row) => row.item.itemId)).toEqual(["q1"]);
    expect(filterResearchLibraryItems(clips, quotes, [], { projectId, sort: "oldest" })
      .map((row) => row.item.itemId ?? row.item.id)).toEqual(["a", "b", "q2", "q1"]);
    expect(libraryFilterOptions(clips, quotes)).toEqual({
      loggers: [["dana", "Dana"], ["logger-a", "logger-a"], ["logger-b", "logger-b"]],
      topics: ["Science", "Transport"],
    });
  });

  it("counts inserted quote provenance once and retains use after card deletion", () => {
    const inserted = {
      id: "row", type: "narration", tokens: [
        { researchQuoteProvenance: { researchProjectId: projectId, researchQuoteId: "quote", useId: "use-1" } },
        { researchQuoteProvenance: { researchProjectId: projectId, researchQuoteId: "quote", useId: "use-1" } },
      ],
      overlayEvents: [{ quoteBox: { researchProjectId: projectId, researchQuoteId: "quote", researchQuoteUseId: "use-1" } }],
    };
    expect(researchQuoteUsage({ activeDraft: { blocks: [inserted] } })).toEqual([{
      kind: "quote", researchProjectId: projectId, itemId: "quote", scriptCount: 1, scriptUses: [
        { rowId: "row", useId: "use-1" },
      ],
    }]);
    const withoutCards = { activeDraft: { blocks: [{ ...inserted, overlayEvents: [] }] } };
    expect(researchQuoteUsage(withoutCards)[0]?.scriptCount).toBe(1);
    const attached = { activeDraft: { blocks: [{ ...inserted, tokens: [], overlayEvents: [
      { id: "overlay-2", quoteBox: { researchProjectId: projectId, researchQuoteId: "quote", researchQuoteUseId: "use-2" } },
    ] }] } };
    expect(researchQuoteUsage(attached)[0]?.scriptCount).toBe(1);
  });
});
