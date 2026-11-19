import { describe, expect, it } from "vitest";

import { filterLoggedResearchClips } from "../browser/research-search.js";

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
