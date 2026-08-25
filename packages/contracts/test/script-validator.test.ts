import type {
  NarrationBlock,
  ScriptDocumentV1,
  TextAnchorRange,
  VisualBlock,
} from "../src/generated/contracts.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { validateScriptDocument } from "../src/script-validator.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));

function load(name = "minimal"): ScriptDocumentV1 {
  return JSON.parse(
    readFileSync(
      `${repositoryRoot}tests/data/slice_1_1/${name}.script-document.json`,
      "utf8",
    ),
  ) as ScriptDocumentV1;
}

function narration(document: ScriptDocumentV1, index = 0): NarrationBlock {
  const blocks = document.activeDraft.blocks.filter(
    (block): block is NarrationBlock => block.type === "narration",
  );
  return blocks[index]!;
}

function codes(document: unknown): string[] {
  return validateScriptDocument(document).diagnostics.map(
    (diagnostic) => diagnostic.code,
  );
}

function firstAnchor(document: ScriptDocumentV1): TextAnchorRange {
  return narration(document).hostVisibilitySpans[0]!.range;
}

describe("validateScriptDocument", () => {
  it.each(["minimal", "torture"])(
    "accepts the canonical %s script without mutating it",
    (name) => {
      const document = load(name);
      const before = JSON.stringify(document);
      expect(validateScriptDocument(document)).toEqual({
        valid: true,
        diagnostics: [],
      });
      expect(JSON.stringify(document)).toBe(before);
    },
  );

  it("ratchets every required torture-script block, source, and coverage shape", () => {
    const document = load("torture");
    expect(document.activeDraft.blocks.map(({ type }) => type)).toEqual([
      "section",
      "direction",
      "narration",
      "narration",
      "visual",
      "note_draft",
    ]);
    const active = narration(document);
    expect(active.state).toBe("active");
    expect(
      active.hostVisibilitySpans.map(({ state, range }) => ({
        state,
        start: range.startTokenId,
        end: range.endTokenId,
        startAffinity: range.startAffinity,
        endAffinity: range.endAffinity,
      })),
    ).toEqual([
      { state: "on_camera", start: active.tokens[0].id, end: active.tokens[1]?.id, startAffinity: "before", endAffinity: "after" },
      { state: "voiceover", start: active.tokens[2]?.id, end: active.tokens[3]?.id, startAffinity: "before", endAffinity: "after" },
      { state: "on_camera", start: active.tokens[4]?.id, end: active.tokens[4]?.id, startAffinity: "before", endAffinity: "after" },
      { state: "voiceover", start: active.tokens[5]?.id, end: active.tokens[5]?.id, startAffinity: "before", endAffinity: "after" },
    ]);

    const nestedEvents = active.visualEvents;
    expect(
      nestedEvents.map(({ presentationMode, source, status, range }) => ({
        presentationMode,
        sourceKind: source.kind,
        mediaKind: source.kind === "local_media" ? source.mediaKind : undefined,
        status,
        start: range.startTokenId,
        end: range.endTokenId,
      })),
    ).toEqual([
      {
        presentationMode: "overlay",
        sourceKind: "local_media",
        mediaKind: "still",
        status: "ready",
        start: active.tokens[0].id,
        end: active.tokens[1]?.id,
      },
      {
        presentationMode: "full_frame",
        sourceKind: "local_media",
        mediaKind: "video",
        status: "ready",
        start: active.tokens[2]?.id,
        end: active.tokens[2]?.id,
      },
      {
        presentationMode: "full_frame",
        sourceKind: "placeholder",
        mediaKind: undefined,
        status: "unresolved",
        start: active.tokens[3]?.id,
        end: active.tokens[3]?.id,
      },
    ]);
    const standalone = document.activeDraft.blocks.find(
      (block): block is VisualBlock => block.type === "visual",
    );
    if (standalone === undefined) {
      throw new Error("canonical torture input lost its standalone visual row");
    }
    expect(standalone.event.presentationMode).toBe("full_frame");
    expect(standalone.event.status).toBe("ready");
    expect(standalone.event.source).toEqual(
      expect.objectContaining({ kind: "local_media", mediaKind: "still" }),
    );
    expect(standalone.event.range).toEqual(
      expect.objectContaining({
        startTokenId: active.tokens[5]?.id,
        endTokenId: active.tokens[5]?.id,
      }),
    );
  });

  it("uses UTF-16 code-unit offsets and exact anchor slices", () => {
    const document = load();
    const block = narration(document);
    block.text = "Go 🚀 now.";
    block.tokens = [
      { ...block.tokens[0], value: "Go", startOffset: 0, endOffset: 2 },
      { ...block.tokens[1]!, value: "🚀", startOffset: 3, endOffset: 5 },
      {
        id: "11000000-0000-4000-8000-000000000009",
        value: "now",
        startOffset: 6,
        endOffset: 9,
      },
    ];
    for (const range of [
      block.hostVisibilitySpans[0]!.range,
      block.visualEvents[0]!.range,
    ]) {
      range.endTokenId = block.tokens[2]!.id;
      range.quotedText = "Go 🚀 now";
    }
    expect(validateScriptDocument(document).valid).toBe(true);
  });

  it("returns only structural diagnostics before semantic validation", () => {
    const document = load();
    document.title = "";
    document.activeDraft.blocks[1]!.id = document.activeDraft.blocks[0]!.id;
    const result = validateScriptDocument(document);
    expect(result.valid).toBe(false);
    expect(result.diagnostics.length).toBeGreaterThan(0);
    expect(new Set(result.diagnostics.map(({ code }) => code))).toEqual(
      new Set(["SCHEMA_INVALID"]),
    );
  });

  it("reports stable schema paths and row references", () => {
    const document = load();
    narration(document).tokens[0].value = "";
    const result = validateScriptDocument(document);
    expect(result.diagnostics).toContainEqual(
      expect.objectContaining({
        code: "SCHEMA_INVALID",
        jsonPath: "/activeDraft/blocks/1/tokens/0/value",
        blockIndex: 1,
        blockId: narration(document).id,
      }),
    );
  });

  it("collapses a non-object draft row to one readable schema diagnostic", () => {
    const document = load() as unknown as {
      activeDraft: { blocks: unknown[] };
    };
    document.activeDraft.blocks[1] = null;
    expect(validateScriptDocument(document)).toEqual({
      valid: false,
      diagnostics: [
        {
          code: "SCHEMA_INVALID",
          message: "type: block must be an object",
          jsonPath: "/activeDraft/blocks/1",
          blockIndex: 1,
        },
      ],
    });
  });

  it("reports duplicate block, token, visibility-span, and visual-event IDs", () => {
    const document = load();
    const block = narration(document);
    document.activeDraft.blocks[0]!.id = block.id;
    block.tokens[1]!.id = block.tokens[0].id;
    block.hostVisibilitySpans.push(
      structuredClone(block.hostVisibilitySpans[0]!),
    );
    block.visualEvents.push(structuredClone(block.visualEvents[0]!));
    expect(validateScriptDocument(document).diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: "BLOCK_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/1/id",
          blockIndex: 1,
          entityId: block.id,
        }),
        expect.objectContaining({
          code: "TOKEN_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/1/tokens/1/id",
          blockIndex: 1,
          entityId: block.tokens[0].id,
        }),
        expect.objectContaining({
          code: "VISIBILITY_SPAN_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/1/hostVisibilitySpans/1/id",
          blockIndex: 1,
          entityId: block.hostVisibilitySpans[0]?.id,
        }),
        expect.objectContaining({
          code: "VISUAL_EVENT_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/1/visualEvents/1/id",
          blockIndex: 1,
          entityId: block.visualEvents[0]?.id,
        }),
      ]),
    );
  });

  it("enforces entity ID uniqueness across rows and visual storage forms", () => {
    const document = load("torture");
    const active = narration(document);
    const excluded = narration(document, 1);
    const duplicateSpan = structuredClone(active.hostVisibilitySpans[0]!);
    duplicateSpan.range.blockId = excluded.id;
    duplicateSpan.range.startTokenId = excluded.tokens[0].id;
    duplicateSpan.range.endTokenId = excluded.tokens[1]!.id;
    duplicateSpan.range.quotedText = "Unused alternative";
    excluded.hostVisibilitySpans = [duplicateSpan];

    const standalone = document.activeDraft.blocks.find(
      (block): block is VisualBlock => block.type === "visual",
    );
    if (standalone === undefined) {
      throw new Error("canonical torture input lost its standalone visual row");
    }
    standalone.event.id = active.visualEvents[0]!.id;

    expect(validateScriptDocument(document).diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: "VISIBILITY_SPAN_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/3/hostVisibilitySpans/0/id",
          blockIndex: 3,
          entityId: active.hostVisibilitySpans[0]!.id,
        }),
        expect.objectContaining({
          code: "VISUAL_EVENT_ID_DUPLICATE",
          jsonPath: "/activeDraft/blocks/4/event/id",
          blockIndex: 4,
          entityId: active.visualEvents[0]!.id,
        }),
      ]),
    );
  });

  it.each([
    ["out-of-bounds offsets", (block: NarrationBlock) => {
      block.tokens[0].endOffset = block.text.length + 1;
    }, "TOKEN_OFFSET_INVALID", "/activeDraft/blocks/1/tokens/0"],
    ["overlapping token order", (block: NarrationBlock) => {
      block.tokens[1]!.startOffset = 4;
    }, "TOKEN_ORDER_INVALID", "/activeDraft/blocks/1/tokens/1"],
    ["token text mismatch", (block: NarrationBlock) => {
      block.tokens[0].value = "Wrong";
    }, "TOKEN_TEXT_MISMATCH", "/activeDraft/blocks/1/tokens/0/value"],
  ])("rejects %s", (_name, mutate, expectedCode, jsonPath) => {
    const document = load();
    const block = narration(document);
    mutate(block);
    expect(validateScriptDocument(document).diagnostics).toContainEqual(
      expect.objectContaining({
        code: expectedCode,
        jsonPath,
        blockIndex: 1,
        blockId: block.id,
        entityKind: "token",
      }),
    );
  });

  it("reports every token that overlaps an earlier token", () => {
    const document = load();
    const block = narration(document);
    const secondToken = block.tokens[1];
    if (secondToken === undefined) {
      throw new Error("canonical minimal input lost its second token");
    }
    block.tokens = [
      { ...block.tokens[0], endOffset: 11, value: "Hello world" },
      { ...secondToken, startOffset: 6, endOffset: 8, value: "wo" },
      {
        id: "11000000-0000-4000-8000-000000000009",
        startOffset: 9,
        endOffset: 11,
        value: "ld",
      },
    ];
    const overlapDiagnostics = validateScriptDocument(document).diagnostics.filter(
      ({ code }) => code === "TOKEN_ORDER_INVALID",
    );
    expect(overlapDiagnostics).toHaveLength(2);
  });

  it.each([
    ["missing target blocks", (document: ScriptDocumentV1) => {
      firstAnchor(document).blockId = "11000000-0000-4000-8000-000000000099";
    }, "ANCHOR_BLOCK_NOT_FOUND", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/blockId", undefined],
    ["non-narration target blocks", (document: ScriptDocumentV1) => {
      firstAnchor(document).blockId = document.activeDraft.blocks[0]!.id;
    }, "ANCHOR_BLOCK_NOT_NARRATION", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/blockId", 0],
    ["wrong nested target blocks", (document: ScriptDocumentV1) => {
      const other = narration(load("torture"), 1);
      document.activeDraft.blocks.push(structuredClone(other));
      firstAnchor(document).blockId = other.id;
    }, "ANCHOR_BLOCK_MISMATCH", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/blockId", 2],
    ["missing start tokens", (document: ScriptDocumentV1) => {
      firstAnchor(document).startTokenId = "11000000-0000-4000-8000-000000000099";
    }, "ANCHOR_TOKEN_NOT_FOUND", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/startTokenId", undefined],
    ["missing end tokens", (document: ScriptDocumentV1) => {
      firstAnchor(document).endTokenId = "11000000-0000-4000-8000-000000000099";
    }, "ANCHOR_TOKEN_NOT_FOUND", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/endTokenId", undefined],
    ["empty affinity-resolved ranges", (document: ScriptDocumentV1) => {
      firstAnchor(document).startAffinity = "after";
      firstAnchor(document).endAffinity = "before";
    }, "ANCHOR_RANGE_EMPTY", "/activeDraft/blocks/1/hostVisibilitySpans/0/range", undefined],
    ["reversed affinity-resolved ranges", (document: ScriptDocumentV1) => {
      const range = firstAnchor(document);
      [range.startTokenId, range.endTokenId] = [
        range.endTokenId,
        range.startTokenId,
      ];
      range.startAffinity = "after";
      range.endAffinity = "before";
    }, "ANCHOR_RANGE_REVERSED", "/activeDraft/blocks/1/hostVisibilitySpans/0/range", undefined],
    ["inexact quoted text", (document: ScriptDocumentV1) => {
      firstAnchor(document).quotedText = "hello world";
    }, "ANCHOR_QUOTE_MISMATCH", "/activeDraft/blocks/1/hostVisibilitySpans/0/range/quotedText", undefined],
  ] as const)("rejects %s", (_name, mutate, expectedCode, jsonPath, targetBlockIndex) => {
    const document = load();
    mutate(document);
    const span = narration(document).hostVisibilitySpans[0];
    expect(validateScriptDocument(document).diagnostics).toContainEqual(
      expect.objectContaining({
        code: expectedCode,
        jsonPath,
        blockIndex: 1,
        blockId: narration(document).id,
        entityKind: "visibility_span",
        entityId: span?.id,
        ...(targetBlockIndex === undefined ? {} : { targetBlockIndex }),
      }),
    );
  });

  it.each([
    ["before", "before", [0, 0, 4, 5]],
    ["before", "after", [0, 0, 5, 5]],
    ["after", "before", [0, 1, 4, 5]],
    ["after", "after", [0, 1, 5, 5]],
  ] as const)(
    "resolves valid %s/%s affinities to exact half-open coverage boundaries",
    (startAffinity, endAffinity, expectedGapIndexes) => {
      const document = load("torture");
      const block = narration(document);
      const span = structuredClone(block.hostVisibilitySpans[0]!);
      span.state = "on_camera";
      span.range.startTokenId = block.tokens[1]!.id;
      span.range.endTokenId = block.tokens[4]!.id;
      span.range.startAffinity = startAffinity;
      span.range.endAffinity = endAffinity;
      const selectedStart = 1 + (startAffinity === "after" ? 1 : 0);
      const selectedEnd = 4 + (endAffinity === "after" ? 1 : 0);
      span.range.quotedText = block.text.slice(
        block.tokens[selectedStart]!.startOffset,
        block.tokens[selectedEnd - 1]!.endOffset,
      );
      block.hostVisibilitySpans = [span];

      const gaps = validateScriptDocument(document).diagnostics.filter(
        ({ code }) => code === "HOST_VISIBILITY_GAP",
      );
      expect(gaps).toEqual([
        expect.objectContaining({
          tokenId: block.tokens[expectedGapIndexes[0]].id,
          endTokenId: block.tokens[expectedGapIndexes[1]]!.id,
        }),
        expect.objectContaining({
          tokenId: block.tokens[expectedGapIndexes[2]]!.id,
          endTokenId: block.tokens[expectedGapIndexes[3]]!.id,
        }),
      ]);
      expect(codes(document)).not.toContain("ANCHOR_QUOTE_MISMATCH");
    },
  );

  it("reports zero-duration visual events at the owning visual row and target narration row", () => {
    const document = load("torture");
    const visualBlockIndex = document.activeDraft.blocks.findIndex(
      (block) => block.type === "visual",
    );
    const visualBlock = document.activeDraft.blocks[
      visualBlockIndex
    ] as VisualBlock;
    visualBlock.event.range.startAffinity = "before";
    visualBlock.event.range.endAffinity = "before";
    const result = validateScriptDocument(document);
    expect(result.diagnostics).toContainEqual(
      expect.objectContaining({
        code: "VISUAL_EVENT_ZERO_DURATION",
        jsonPath: "/activeDraft/blocks/4/event/range",
        blockIndex: visualBlockIndex,
        targetBlockIndex: 2,
        entityKind: "visual_event",
        entityId: visualBlock.event.id,
      }),
    );
  });

  it("reports missing host visibility as a contiguous token range", () => {
    const missing = load();
    narration(missing).hostVisibilitySpans = [];
    expect(validateScriptDocument(missing).diagnostics).toContainEqual(
      expect.objectContaining({
        code: "HOST_VISIBILITY_GAP",
        jsonPath: "/activeDraft/blocks/1/hostVisibilitySpans",
        entityKind: "token",
        tokenId: narration(missing).tokens[0].id,
        endTokenId: narration(missing).tokens[1]!.id,
        blockIndex: 1,
      }),
    );

  });

  it.each([
    ["duplicate", "voiceover", "duplicate host-visibility"],
    ["contradictory", "on_camera", "contradictory on-camera and voiceover"],
  ] as const)("reports %s host visibility", (_name, state, message) => {
    const document = load();
    const block = narration(document);
    const original = block.hostVisibilitySpans[0];
    if (original === undefined) {
      throw new Error("canonical minimal input lost its visibility span");
    }
    const duplicate = structuredClone(original);
    duplicate.id = "11000000-0000-4000-8000-000000000010";
    duplicate.state = state;
    block.hostVisibilitySpans.push(duplicate);
    const overlap = validateScriptDocument(document).diagnostics.find(
      ({ code }) => code === "HOST_VISIBILITY_OVERLAP",
    );
    expect(overlap).toEqual(
      expect.objectContaining({
        code: "HOST_VISIBILITY_OVERLAP",
        jsonPath: "/activeDraft/blocks/1/hostVisibilitySpans",
        blockIndex: 1,
        tokenId: block.tokens[0].id,
        endTokenId: block.tokens[1]?.id,
      }),
    );
    expect(overlap?.message).toContain(message);
  });

  it("does not mislabel adjacent same-state duplicates as contradictory", () => {
    const document = load();
    const block = narration(document);
    const original = block.hostVisibilitySpans[0];
    const secondToken = block.tokens[1];
    if (original === undefined || secondToken === undefined) {
      throw new Error("canonical minimal input lost its coverage entities");
    }
    const onCamera = structuredClone(original);
    onCamera.state = "on_camera";
    onCamera.range.endTokenId = block.tokens[0].id;
    onCamera.range.quotedText = "Hello";
    const onCameraDuplicate = structuredClone(onCamera);
    onCameraDuplicate.id = "11000000-0000-4000-8000-000000000010";

    const voiceover = structuredClone(original);
    voiceover.id = "11000000-0000-4000-8000-000000000011";
    voiceover.range.startTokenId = secondToken.id;
    voiceover.range.quotedText = "world";
    const voiceoverDuplicate = structuredClone(voiceover);
    voiceoverDuplicate.id = "11000000-0000-4000-8000-000000000012";
    block.hostVisibilitySpans = [
      onCamera,
      onCameraDuplicate,
      voiceover,
      voiceoverDuplicate,
    ];

    const overlaps = validateScriptDocument(document).diagnostics.filter(
      ({ code }) => code === "HOST_VISIBILITY_OVERLAP",
    );
    expect(overlaps).toHaveLength(1);
    expect(overlaps[0]?.message).toContain("duplicate host-visibility");
    expect(overlaps[0]?.message).not.toContain("contradictory");
  });

  it.each([
    ["no visual", (block: NarrationBlock) => {
      block.visualEvents = [];
    }],
    ["overlay only", (block: NarrationBlock) => {
      block.visualEvents[0]!.presentationMode = "overlay";
    }],
    ["unready local media", (block: NarrationBlock) => {
      block.visualEvents[0]!.source = {
        kind: "local_media",
        mediaReferenceId: "11000000-0000-4000-8000-000000000011",
        mediaKind: "video",
        label: "Not ready",
      };
      block.visualEvents[0]!.status = "unresolved";
    }],
    ["ready placeholder", (block: NarrationBlock) => {
      block.visualEvents[0]!.status = "ready";
    }],
  ])("reports a VO visual gap for %s", (_name, mutate) => {
    const document = load();
    mutate(narration(document));
    expect(validateScriptDocument(document).diagnostics).toContainEqual(
      expect.objectContaining({
        code: "VOICEOVER_VISUAL_GAP",
        jsonPath: "/activeDraft/blocks/1/visualEvents",
        entityKind: "token",
        blockIndex: 1,
        tokenId: narration(document).tokens[0].id,
        endTokenId: narration(document).tokens[1]!.id,
      }),
    );
  });

  it("validates excluded narration integrity but skips its coverage checks", () => {
    const document = load("torture");
    const excluded = narration(document, 1);
    expect(excluded.hostVisibilitySpans).toEqual([]);
    expect(validateScriptDocument(document).valid).toBe(true);
    excluded.tokens[0].value = "Broken";
    expect(codes(document)).toContain("TOKEN_TEXT_MISMATCH");
    expect(codes(document)).not.toContain("HOST_VISIBILITY_GAP");
  });

  it("orders diagnostics deterministically by row, path, code, and identity", () => {
    const document = load();
    const block = narration(document);
    block.hostVisibilitySpans = [];
    block.visualEvents = [];
    block.tokens[0].value = "Wrong";
    const first = validateScriptDocument(document);
    const second = validateScriptDocument(document);
    expect(second).toEqual(first);
    expect(first.diagnostics.map(({ code }) => code)).toEqual([
      "HOST_VISIBILITY_GAP",
      "TOKEN_TEXT_MISMATCH",
    ]);
  });
});
