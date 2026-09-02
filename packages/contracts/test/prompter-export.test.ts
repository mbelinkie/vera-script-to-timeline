import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import type {
  NarrationBlock,
  ScriptDocumentV1,
} from "../src/generated/contracts.js";
import { exportPrompter } from "../src/prompter-export.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const dataDirectory = `${repositoryRoot}tests/data/issue_37`;

function load(name = "acceptance"): ScriptDocumentV1 {
  return JSON.parse(
    readFileSync(`${dataDirectory}/${name}.script-document.json`, "utf8"),
  ) as ScriptDocumentV1;
}

function loadAcceptedTorture(): ScriptDocumentV1 {
  return JSON.parse(
    readFileSync(
      `${repositoryRoot}tests/data/slice_1_1/torture.script-document.json`,
      "utf8",
    ),
  ) as ScriptDocumentV1;
}

function activeNarration(
  document: ScriptDocumentV1,
  index = 0,
): NarrationBlock {
  return document.activeDraft.blocks.filter(
    (block): block is NarrationBlock =>
      block.type === "narration" && block.state === "active",
  )[index]!;
}

const allCues = {
  includeSectionNavigation: true,
  includeBeatNumbers: true,
} as const;

describe("exportPrompter", () => {
  it("derives sentence beats when punctuation is part of tokens", () => {
    const result = exportPrompter(plainScript("First sentence. Second sentence! Third?"), allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.sidecar.beats.map(({ expectedText }) => expectedText)).toEqual([
      "First sentence.", "Second sentence!", "Third?",
    ]);
  });

  it("keeps decimals and common titles inside their sentences", () => {
    const result = exportPrompter(plainScript("Dr. Luna counted 3.5 stars. Then she waved."), allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.sidecar.beats.map(({ expectedText }) => expectedText)).toEqual([
      "Dr. Luna counted 3.5 stars.", "Then she waved.",
    ]);
  });

  it("preserves leading punctuation and begins with a marker, not a quote", () => {
    const document = plainScript('“Hello!” She waved.', /\p{L}+/gu);
    const result = exportPrompter(document, { includeBeatNumbers: false, includeSectionNavigation: false });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.text).toBe('(OC)\n“Hello!” She waved.\n');
    expect(result.sidecar.beats.map(({ expectedText }) => expectedText)).toEqual(['“Hello!”', 'She waved.']);
  });

  it("keeps same-state prose unchanged when optional beat numbers are off", () => {
    const document = plainScript("One.  Two!\nThree?");
    const result = exportPrompter(document, { includeBeatNumbers: false, includeSectionNavigation: false });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.text).toBe("(OC)\nOne.  Two!\nThree?\n");
  });

  it("allows shared annotation ranges and retains a spanning note on each intersected beat", () => {
    const document = load();
    const block = activeNarration(document);
    block.annotations![1]!.range = structuredClone(block.annotations![0]!.range);
    const spanning = block.annotations![2]!;
    spanning.range.startTokenId = block.tokens[0].id;
    spanning.range.quotedText = block.text.slice(0, block.tokens.at(-1)!.endOffset);
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.sidecar.beats.slice(0, 2).every((beat) => beat.annotations.some(({ id }) => id === spanning.id))).toBe(true);
  });

  it("rejects identity collisions between explicit and derived beats", () => {
    const document = load();
    const initial = exportPrompter(document, allCues);
    if (!initial.ok) throw new Error("fixture invalid");
    activeNarration(document).performanceBeats![0]!.id = initial.sidecar.beats.at(-1)!.id.toUpperCase();
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.diagnostics.map(({ code }) => code)).toContain("PERFORMANCE_BEAT_ID_DUPLICATE");
  });

  it("rejects unsafe revision identity and unknown export settings", () => {
    const document = load();
    document.liveHeadSequence = Number.MAX_SAFE_INTEGER + 1;
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.diagnostics.map(({ code }) => code)).toContain("PROMPTER_REVISION_INVALID");
    expect(exportPrompter(load(), { ...allCues, unknown: true } as typeof allCues)).toEqual({
      ok: false,
      diagnostics: [expect.objectContaining({ code: "PROMPTER_SETTINGS_INVALID" })],
    });
  });

  it("handles an empty active narration surface without inventing a camera state", () => {
    const document = load();
    document.activeDraft.blocks = [];
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.text).toBe("");
    expect(result.sidecar.beats).toEqual([]);
  });

  it.each(["acceptance", "legacy"])("matches the %s text and sidecar goldens without mutation", (name) => {
    const document = load(name);
    const before = JSON.stringify(document);
    const result = exportPrompter(document, name === "acceptance" ? allCues : { includeSectionNavigation: false, includeBeatNumbers: false });
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.text).toBe(
      readFileSync(`${dataDirectory}/${name}.prompter.golden.txt`, "utf8"),
    );
    expect(result.sidecarJson).toBe(
      readFileSync(`${dataDirectory}/${name}.sidecar.golden.json`, "utf8"),
    );
    expect(result.sidecarSha256).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(result.sidecar.textSha256).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(JSON.stringify(document)).toBe(before);
  });

  it("is byte-identical across repeated exports", () => {
    const document = load();
    const first = exportPrompter(document, allCues);
    const second = exportPrompter(document, allCues);
    expect(second).toEqual(first);
  });

  it("keeps a mixed-state sentence as one on-camera recording beat", () => {
    const result = exportPrompter(load(), allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.sidecar.beats[0]).toEqual(
      expect.objectContaining({
        expectedText: "Watch the beacon as the fog rolls in.",
        hostVisibility: "on_camera",
      }),
    );
    expect(result.text).toContain("beacon\n(VO)\nas the fog rolls in.");
  });

  it("derives one stable beat for a legacy mixed-state sentence", () => {
    const document = loadAcceptedTorture();
    const first = exportPrompter(document, {
      includeSectionNavigation: false,
      includeBeatNumbers: false,
    });
    const second = exportPrompter(document, {
      includeSectionNavigation: false,
      includeBeatNumbers: false,
    });
    expect(first.ok).toBe(true);
    expect(second).toEqual(first);
    if (!first.ok) return;

    expect(first.sidecar.beats).toHaveLength(1);
    expect(first.sidecar.beats[0]).toEqual(
      expect.objectContaining({
        expectedText: "Meet me here, then look beyond.",
        hostVisibility: "on_camera",
      }),
    );
  });

  it("labels an all-voiceover derived sentence as voiceover", () => {
    const result = exportPrompter(load(), allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.sidecar.beats.at(-1)?.hostVisibility).toBe("voiceover");
  });

  it("escapes cue delimiters and newlines without changing sidecar values", () => {
    const document = load();
    const section = document.activeDraft.blocks.find(
      (block) => block.type === "section",
    );
    const annotation = activeNarration(document).annotations?.[0];
    if (section?.type !== "section" || annotation === undefined) {
      throw new Error("acceptance cues missing");
    }
    section.title = "Harbor ] test";
    annotation.value = "BEE-kən\nslowly";
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.text).toContain("[SECTION: Harbor \\] test]");
    expect(result.text).toContain("BEE-kən\\nslowly]");
    expect(result.sidecar.beats[0]?.annotations[0]?.value).toBe(
      "BEE-kən\nslowly",
    );
  });

  it("changes derived beat identity when the frozen source revision changes", () => {
    const original = loadAcceptedTorture();
    const revised = loadAcceptedTorture();
    revised.liveHeadSequence += 1;
    revised.liveContentHash = `sha256:${"4".repeat(64)}`;
    const settings = {
      includeSectionNavigation: false,
      includeBeatNumbers: false,
    };
    const first = exportPrompter(original, settings);
    const second = exportPrompter(revised, settings);
    expect(first.ok).toBe(true);
    expect(second.ok).toBe(true);
    if (!first.ok || !second.ok) return;
    expect(second.sidecar.beats[0]?.id).not.toBe(first.sidecar.beats[0]?.id);
  });

  it("limits navigation and beat-number settings to declared output fields", () => {
    const withCues = exportPrompter(load(), allCues);
    const withoutCues = exportPrompter(load(), {
      includeSectionNavigation: false,
      includeBeatNumbers: false,
    });
    expect(withCues.ok).toBe(true);
    expect(withoutCues.ok).toBe(true);
    if (!withCues.ok || !withoutCues.ok) return;

    expect(withoutCues.text).not.toContain("[SECTION:");
    expect(withoutCues.text).not.toContain("[BEAT ");
    expect(withoutCues.sidecar.beats.every((beat) => beat.navigationCues.length === 0)).toBe(true);
    expect(withoutCues.sidecar.beats.map(({ id, expectedText, hostVisibility, annotations }) => ({
      id,
      expectedText,
      hostVisibility,
      annotations,
    }))).toEqual(
      withCues.sidecar.beats.map(({ id, expectedText, hostVisibility, annotations }) => ({
        id,
        expectedText,
        hostVisibility,
        annotations,
      })),
    );
  });

  it("keeps opted-out annotations in the sidecar but out of visible text", () => {
    const document = load();
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.text).not.toContain("IPA fɑɡ");
    expect(result.sidecar.beats[0]?.annotations).toContainEqual(
      expect.objectContaining({
        kind: "pronunciation_phoneme",
        value: "IPA fɑɡ",
        visibleInPrompter: false,
      }),
    );
  });

  it("changes only annotation visibility and dependent hashes when inclusion changes", () => {
    const includedDocument = load();
    const excludedDocument = load();
    const annotation = activeNarration(excludedDocument).annotations?.[0];
    if (annotation === undefined) throw new Error("acceptance annotation missing");
    annotation.includeInPrompter = false;

    const included = exportPrompter(includedDocument, allCues);
    const excluded = exportPrompter(excludedDocument, allCues);
    expect(included.ok).toBe(true);
    expect(excluded.ok).toBe(true);
    if (!included.ok || !excluded.ok) return;

    expect(included.text).toContain("[PRONUNCIATION: beacon = BEE-kən]");
    expect(excluded.text).not.toContain("BEE-kən");
    expect(excluded.sidecar.beats[0]?.annotations[0]).toEqual({
      ...included.sidecar.beats[0]?.annotations[0],
      visibleInPrompter: false,
    });
    expect(excluded.sidecar.textSha256).not.toBe(included.sidecar.textSha256);
    expect(excluded.sidecarSha256).not.toBe(included.sidecarSha256);
  });

  it.each([
    ["missing host visibility", (document: ScriptDocumentV1) => {
      activeNarration(document).hostVisibilitySpans.pop();
    }, "HOST_VISIBILITY_GAP"],
    ["overlapping host visibility", (document: ScriptDocumentV1) => {
      const block = activeNarration(document);
      block.hostVisibilitySpans.push(structuredClone(block.hostVisibilitySpans[0]!));
      block.hostVisibilitySpans.at(-1)!.id = "37000000-0000-4000-8000-000000000099";
    }, "HOST_VISIBILITY_OVERLAP"],
    ["invalid annotation anchor", (document: ScriptDocumentV1) => {
      activeNarration(document).annotations![0]!.range.quotedText = "wrong";
    }, "ANCHOR_QUOTE_MISMATCH"],
    ["duplicate annotation identity", (document: ScriptDocumentV1) => {
      const block = activeNarration(document);
      block.annotations![1]!.id = block.annotations![0]!.id;
    }, "ANNOTATION_ID_DUPLICATE"],
    ["duplicate performance beat identity", (document: ScriptDocumentV1) => {
      const beats = activeNarration(document).performanceBeats!;
      beats[1]!.id = beats[0]!.id;
    }, "PERFORMANCE_BEAT_ID_DUPLICATE"],
    ["out-of-order performance beats", (document: ScriptDocumentV1) => {
      activeNarration(document).performanceBeats!.reverse();
    }, "PERFORMANCE_BEAT_ORDER_INVALID"],
    ["uncovered performance beat", (document: ScriptDocumentV1) => {
      activeNarration(document).performanceBeats!.shift();
    }, "PERFORMANCE_BEAT_COVERAGE_GAP"],
    ["overlapping performance beats", (document: ScriptDocumentV1) => {
      const block = activeNarration(document);
      block.performanceBeats![1]!.range.startTokenId = block.tokens[7]!.id;
      block.performanceBeats![1]!.range.quotedText = "in. Keep your eyes here";
    }, "PERFORMANCE_BEAT_OVERLAP"],
  ] as const)("blocks export for %s", (_name, mutate, code) => {
    const document = load();
    mutate(document);
    const result = exportPrompter(document, allCues);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.diagnostics).toEqual(
      expect.arrayContaining([expect.objectContaining({ code })]),
    );
  });
});

function plainScript(text: string, tokenPattern = /\S+/gu): ScriptDocumentV1 {
  const document = load();
  const block = activeNarration(document);
  document.activeDraft.blocks = [block];
  block.text = text;
  block.tokens = [...text.matchAll(tokenPattern)].map((match, index) => ({
    id: `37000000-0000-4000-8000-${String(200 + index).padStart(12, "0")}`,
    value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  })) as NarrationBlock["tokens"];
  block.annotations = [];
  delete block.performanceBeats;
  block.visualEvents = [];
  block.hostVisibilitySpans = [{
    ...block.hostVisibilitySpans[0]!,
    range: {
      blockId: block.id, startTokenId: block.tokens[0].id,
      endTokenId: block.tokens.at(-1)!.id, startAffinity: "before", endAffinity: "after",
      quotedText: text.slice(block.tokens[0].startOffset, block.tokens.at(-1)!.endOffset),
      anchorVersion: 1,
    },
  }];
  return document;
}
