import { describe, expect, it } from "vitest";

import type { NarratedVisualPayloadV2, ResearchStillSnapshotV2 } from "../src/generated/contracts-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { retypeVisualPayloadV2 } from "../src/authoring-v2-visual-type.js";
import { toWordlessPlacementV2 } from "../src/authoring-v2-wordless.js";
import {
  insertResearchStillBrowserV2,
  type ResearchStillBrowserInsertV2,
} from "../src/research-still-browser-insert.js";
import { researchId, researchNote, researchStashFixture } from "./issue-367-fixture.js";

const digest = "a".repeat(64);

function stillSnapshot(): ResearchStillSnapshotV2 {
  return {
    researchProjectId: researchId(910001),
    itemId: researchId(910002),
    itemVersion: 4,
    sourceId: researchId(910003),
    title: "Saved Research still",
    credit: "Synthetic credit",
    licence: "CC BY",
    usageNote: "Synthetic usage note",
    provenance: {
      kind: "still_crop",
      sourceUrl: "https://example.com/original.jpg",
      resolvedUrl: "https://cdn.example.com/original.jpg",
      pageUrl: "https://example.com/page",
      altText: "Synthetic still",
      parentItemId: researchId(910004),
      crop: { x: 0.1, y: 0.2, width: 0.7, height: 0.6 },
      inputSha256: digest,
    },
    original: {
      versionId: "original-v4",
      sha256: digest,
      byteCount: 1234,
      mimeType: "image/jpeg",
      width: 1920,
      height: 1080,
    },
  };
}

function fixture() {
  const doc = researchStashFixture(false).doc;
  const row = researchNote(880100);
  delete row.plainDirection;
  row.tokens.forEach((token) => { token.spoken = true; });
  doc.activeDraft.blocks = [row];
  return { doc, row };
}

function request(
  row: ReturnType<typeof fixture>["row"],
  still = stillSnapshot(),
  revision = 0,
): ResearchStillBrowserInsertV2 & { placement: Extract<ResearchStillBrowserInsertV2["placement"], { kind: "selected_words" }> } {
  return {
    expectedDocumentRevision: revision,
    researchProjectId: still.researchProjectId,
    itemId: still.itemId,
    itemVersion: still.itemVersion,
    placement: {
      kind: "selected_words",
      rowId: row.id,
      expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence!.version,
      startTokenId: row.tokens[0]!.id,
      endTokenId: row.tokens[0]!.id,
    },
  };
}

function insertedPayload(document: ReturnType<typeof fixture>["doc"]): NarratedVisualPayloadV2 {
  const row = document.activeDraft.blocks[0];
  if (row?.type !== "narration") throw new Error("Expected narration row");
  const slot = row.primaryVisualSequence?.slots.find((item) =>
    item.kind === "content" && item.payload.kind === "visual" && item.payload.researchStill,
  );
  if (!slot || slot.kind !== "content" || slot.payload.kind !== "visual") {
    throw new Error("Expected Research still slot");
  }
  return slot.payload;
}

describe("Research still browser insertion: one atomic selected-words edit", () => {
  it("attaches one normal image with the exact kept pin and no thumbnail/display asset", () => {
    const { doc, row } = fixture();
    const before = structuredClone(doc);
    const still = stillSnapshot();
    const savedStill = structuredClone(still);
    const ids = [researchId(920001), researchId(920002), researchId(920003)];
    const result = insertResearchStillBrowserV2(doc, still, request(row, still), () => ids.shift()!);

    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.rowEditRevision).toBe(1);
    const payload = insertedPayload(result.document);
    expect(payload).toMatchObject({
      payloadId: researchId(920001),
      pictureKind: "image",
      displayName: still.title,
      source: { kind: "media_reference", mediaReferenceId: researchId(920003) },
      sourceUsage: null,
      audioPolicy: "mute",
      researchStill: still,
    });
    expect(payload.researchStill).toEqual(savedStill);
    expect(JSON.stringify(payload)).not.toContain('"display"');
    expect(JSON.stringify(payload)).not.toContain('"thumbnail"');
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(doc).toEqual(before);
    expect(still).toEqual(savedStill);
  });

  it("adds an unattached kept image without modifying narration and advances both versions", () => {
    const { doc, row } = fixture();
    const still = stillSnapshot();
    const intent: ResearchStillBrowserInsertV2 = request(row, still);
    intent.placement = { kind: "unattached", rowId: row.id, expectedRowVersion: row.version,
      expectedSequenceVersion: row.primaryVisualSequence!.version };
    const result = insertResearchStillBrowserV2(doc, still, intent);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const updated = result.document.activeDraft.blocks[0];
    if (updated?.type !== "narration") throw new Error("Expected narration");
    expect(updated.text).toBe(row.text);
    expect(updated.tokens).toEqual(row.tokens);
    expect(updated.version).toBe(row.version + 1);
    expect(updated.primaryVisualSequence).toEqual({ ...row.primaryVisualSequence,
      version: row.primaryVisualSequence!.version + 1 });
    expect(updated.unattachedVisuals).toHaveLength(1);
    expect(updated.unattachedVisuals?.[0]?.payload).toMatchObject({ kind: "visual", pictureKind: "image", researchStill: still });
    expect(result.document.rowEditRevision).toBe(1);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(insertResearchStillBrowserV2(result.document, still, intent).ok).toBe(false);
  });

  it("keeps repeated uses independent and refuses wordless conversion", () => {
    const { doc, row } = fixture();
    const still = stillSnapshot();
    const first = insertResearchStillBrowserV2(doc, still, request(row, still), (() => {
      const ids = [researchId(930001), researchId(930002), researchId(930003)];
      return () => ids.shift()!;
    })());
    expect(first.ok, JSON.stringify(first.diagnostics)).toBe(true);
    const firstPayload = insertedPayload(first.document);
    const firstRow = first.document.activeDraft.blocks[0];
    if (firstRow?.type !== "narration") throw new Error("Expected narration row");
    const secondRequest = request(firstRow, still, 1);
    secondRequest.placement.expectedRowVersion = firstRow.version;
    secondRequest.placement.expectedSequenceVersion = firstRow.primaryVisualSequence!.version;
    const second = insertResearchStillBrowserV2(first.document, still, secondRequest, (() => {
      const ids = [researchId(930004), researchId(930005), researchId(930006)];
      return () => ids.shift()!;
    })());
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const secondPayload = insertedPayload(second.document);
    expect(secondPayload.source).not.toEqual(firstPayload.source);
    expect(secondPayload.payloadId).not.toBe(firstPayload.payloadId);
    expect(validateScriptDocumentV2(second.document).valid).toBe(true);
    expect(toWordlessPlacementV2(secondPayload)).toMatchObject({
      code: "WORDLESS_RESEARCH_STILL_UNSUPPORTED",
    });
  });

  it("refuses stale identity, row state, token state and UUID collisions atomically", () => {
    const { doc, row } = fixture();
    const before = structuredClone(doc);
    const still = stillSnapshot();
    const valid = request(row, still);
    const invalid = [
      { ...valid, researchProjectId: researchId(940001) },
      { ...valid, itemId: researchId(940002) },
      { ...valid, itemVersion: still.itemVersion + 1 },
      { ...valid, expectedDocumentRevision: 1 },
      { ...valid, placement: { ...valid.placement, expectedRowVersion: row.version + 1 } },
      { ...valid, placement: { ...valid.placement, expectedSequenceVersion: row.primaryVisualSequence!.version + 1 } },
      { ...valid, placement: { ...valid.placement, startTokenId: researchId(940003) } },
    ];
    for (const bad of invalid) {
      const result = insertResearchStillBrowserV2(doc, still, bad);
      expect(result.ok, JSON.stringify(bad)).toBe(false);
      expect(result.document).toBe(doc);
      expect(doc).toEqual(before);
    }
    for (const duplicate of [row.id, still.itemId, researchId(940004)]) {
      const result = insertResearchStillBrowserV2(doc, still, valid, () => duplicate);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(doc);
      expect(result.diagnostics[0]?.code).toBe("RESEARCH_STILL_INSERT_INVALID");
      expect(doc).toEqual(before);
    }
  });

  it("rejects malformed snapshot metadata and keeps ordinary image constraints strict", () => {
    const { doc, row } = fixture();
    const still = stillSnapshot();
    const result = insertResearchStillBrowserV2(doc, still, request(row, still), (() => {
      const ids = [researchId(950001), researchId(950002), researchId(950003)];
      return () => ids.shift()!;
    })());
    expect(result.ok).toBe(true);
    const malformed = structuredClone(result.document);
    const payload = insertedPayload(malformed);
    payload.researchStill!.original.sha256 = "not-a-sha";
    expect(validateScriptDocumentV2(malformed).valid).toBe(false);

    const extra = structuredClone(result.document);
    (insertedPayload(extra).researchStill as ResearchStillSnapshotV2 & { thumbnail?: unknown }).thumbnail = {};
    expect(validateScriptDocumentV2(extra).valid).toBe(false);

    const wrongKind = structuredClone(result.document);
    const wrongPayload = insertedPayload(wrongKind);
    wrongPayload.pictureKind = "clip";
    expect(validateScriptDocumentV2(wrongKind).valid).toBe(false);
  });

  it("preserves a kept still when the ordinary Still Image type is reapplied to the same source", () => {
    const { doc, row } = fixture();
    const still = stillSnapshot();
    const result = insertResearchStillBrowserV2(doc, still, request(row, still), (() => {
      const ids = [researchId(960001), researchId(960002), researchId(960003)];
      return () => ids.shift()!;
    })());
    expect(result.ok).toBe(true);
    const payload = structuredClone(insertedPayload(result.document));
    payload.framingPolicy = "cover";
    if (payload.source.kind !== "media_reference") throw new Error("Expected media source");
    const retyped = retypeVisualPayloadV2(payload, {
      type: "still_image",
      source: structuredClone(payload.source),
    });
    expect(retyped).toMatchObject({ ok: false, code: "CHANGE_TYPE_UNCHANGED" });
  });
});
