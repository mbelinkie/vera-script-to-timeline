import { describe, expect, it } from "vitest";

import type { NarratedVisualPayloadV2, NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { createRowEditSessionV2 } from "../src/authoring-v2-rows.js";
import { attachVisualToWordsV2 } from "../src/authoring-v2-visual-lifecycle.js";
import {
  placeResearchQuoteV2,
  prepareResearchQuotePlacementV2,
  type AuthorizedResearchQuoteV2,
  type ResearchQuoteBackgroundV2,
  type ResearchQuotePlacementV2,
} from "../src/research-quote-placement.js";
import { researchId, researchNote, researchStashFixture } from "./issue-367-fixture.js";

const templateRevision = "sha256:b089282e6ccab68426eb5f0b39168cb11c051e6798cbe08230b41bf640ff3754";

function quote(): AuthorizedResearchQuoteV2 {
  return {
    researchQuoteId: researchId(890001),
    spokenText: "A historic line",
    displayText: "An edited display line",
    speakerName: "Ada Lovelace",
    speakerTitle: "Mathematician",
    citationText: "History, p. 1",
    italicSpan: { start: 0, end: 7 },
    templateRevision,
  };
}

function picture(): ResearchQuoteBackgroundV2 {
  return {
    kind: "still_image",
    source: { kind: "media_reference", mediaReferenceId: researchId(890002) },
    displayName: "Synthetic article picture",
  };
}

function generator(start = 900000) {
  let next = start;
  return () => researchId(++next);
}

function fixture(withExistingVisual = false): { doc: ScriptDocumentV2; row: NarrationBlockV2 } {
  const doc = researchStashFixture(false).doc;
  const row = researchNote(880100);
  delete row.plainDirection;
  row.tokens.forEach((token) => { token.spoken = true; });
  if (withExistingVisual) {
    const slotId = researchId(880120);
    row.unattachedVisuals = [{
      slotId, version: 1,
      payload: {
        kind: "visual", payloadId: researchId(880121), pictureKind: "image",
        source: { kind: "media_reference", mediaReferenceId: researchId(880122) },
        sourceUsage: null, audioPolicy: "mute",
      },
    }];
    const attached = attachVisualToWordsV2(row, slotId, row.tokens[0]!.id, row.tokens[0]!.id);
    expect("code" in attached).toBe(false);
  }
  doc.activeDraft.blocks = [row];
  expect(validateScriptDocumentV2(doc).valid).toBe(true);
  return { doc, row };
}

function request(row: NarrationBlockV2, destination: ResearchQuotePlacementV2["destination"]): ResearchQuotePlacementV2 {
  return {
    expectedDocumentRevision: 0,
    rowId: row.id,
    expectedRowVersion: row.version,
    expectedSequenceVersion: row.primaryVisualSequence!.version,
    destination,
  };
}

function placed(document: ScriptDocumentV2) {
  const row = document.activeDraft.blocks[0];
  if (!row || row.type !== "narration") throw new Error("Expected narration row");
  const overlay = row.overlayEvents.find((event) => event.quoteBox);
  if (!overlay?.quoteBox) throw new Error("Expected Research quote overlay");
  const background = row.primaryVisualSequence?.slots.find((slot) =>
    slot.kind === "content" && slot.payload.kind === "visual" &&
    slot.payload.payloadId === overlay.quoteBox?.backgroundPayloadId);
  if (!background || background.kind !== "content" || background.payload.kind !== "visual") {
    throw new Error("Expected linked visual background");
  }
  return { row, overlay, background: background as typeof background & { payload: NarratedVisualPayloadV2 } };
}

describe("place Research quote as one document edit", () => {
  it("inserts spoken text and linked still/box on the exact new words; preserves other coverage", () => {
    const { doc, row } = fixture(true);
    const before = structuredClone(doc);
    const previousSlot = row.primaryVisualSequence!.slots.find((slot) => slot.kind === "content" &&
      slot.payload.kind === "visual");
    const result = placeResearchQuoteV2(doc, quote(), picture(), request(row, {
      kind: "insert", beforeTokenId: row.tokens[1]!.id,
    }), generator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.rowEditRevision).toBe(1);
    const { row: edited, overlay, background } = placed(result.document);
    expect(edited.text).toBe("Look A historic line closer");
    expect(edited.tokens.map((token) => token.value)).toEqual(["Look", "A", "historic", "line", "closer"]);
    expect(edited.tokens[0]!.id).toBe(row.tokens[0]!.id);
    expect(edited.tokens[4]!.id).toBe(row.tokens[1]!.id);
    expect(edited.primaryVisualSequence!.slots).toContainEqual(previousSlot);
    expect(background.payload).toMatchObject({
      pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: researchId(890002) },
      displayName: "Synthetic article picture",
    });
    expect(overlay.quoteBox).toMatchObject({
      researchQuoteId: quote().researchQuoteId,
      displayText: quote().displayText,
      speakerName: quote().speakerName,
      speakerTitle: quote().speakerTitle,
      italicSpan: quote().italicSpan,
      templateRevision,
      backgroundPayloadId: background.payload.payloadId,
    });
    expect(overlay.timing).toMatchObject({
      kind: "timed",
      start: { kind: "word", anchor: { tokenId: edited.tokens[1]!.id, quotedWord: "A" } },
      end: { kind: "audible_word_end", anchor: { tokenId: edited.tokens[3]!.id, quotedWord: "line" } },
    });
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(doc).toEqual(before);
  });

  it("attaches existing words with a Web Capture and does not insert narration", () => {
    const { doc, row } = fixture();
    const result = placeResearchQuoteV2(doc, quote(), {
      kind: "web_capture", source: { kind: "capture_revision", captureId: researchId(910001), revisionId: researchId(910002) },
    }, request(row, { kind: "selected_words", startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[1]!.id }), generator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const { row: edited, overlay, background } = placed(result.document);
    expect(edited.text).toBe(row.text);
    expect(edited.tokens).toEqual(row.tokens);
    expect(background.payload).toMatchObject({
      pictureKind: "capture", source: { kind: "capture_revision", captureId: researchId(910001), revisionId: researchId(910002) },
    });
    expect(overlay.timing).toMatchObject({
      start: { anchor: { tokenId: row.tokens[0]!.id } },
      end: { anchor: { tokenId: row.tokens[1]!.id } },
    });
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("uses the existing Need to Find card when the article or typed quote has no picture", () => {
    const { doc, row } = fixture();
    const result = placeResearchQuoteV2(doc, quote(), null,
      request(row, { kind: "selected_words", startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[0]!.id }), generator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const { background, overlay } = placed(result.document);
    expect(background.payload).toMatchObject({
      pictureKind: "unresolved_visual",
      source: { kind: "unresolved_visual", description: "Find a picture for this Research quote." },
    });
    expect(overlay.quoteBox!.backgroundPayloadId).toBe(background.payload.payloadId);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("inserts into an empty spoken row and retains independent per-use box details", () => {
    const { doc, row } = fixture();
    row.text = "";
    row.tokens = [];
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    const first = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "insert", beforeTokenId: null }), generator());
    expect(first.ok, JSON.stringify(first.diagnostics)).toBe(true);
    const firstRow = placed(first.document).row;
    expect(firstRow.text).toBe(quote().spokenText);

    const second = placeResearchQuoteV2(first.document,
      { ...quote(), displayText: "Second-use display", citationText: "Edited citation", italicSpan: null, citationOverridden: true },
      null,
      { ...request(firstRow, {
        kind: "selected_words", startTokenId: firstRow.tokens[1]!.id, endTokenId: firstRow.tokens[2]!.id,
      }), expectedDocumentRevision: 1 }, generator(910000));
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const boxes = (second.document.activeDraft.blocks[0] as NarrationBlockV2).overlayEvents.map((item) => item.quoteBox!);
    expect(boxes).toHaveLength(2);
    expect(boxes[0]!.researchQuoteId).toBe(boxes[1]!.researchQuoteId);
    expect(boxes[0]!.citationText).toBe("History, p. 1");
    expect(boxes[1]).toMatchObject({ displayText: "Second-use display", citationText: "Edited citation", citationOverridden: true });
    expect(boxes[0]!.backgroundPayloadId).not.toBe(boxes[1]!.backgroundPayloadId);
    expect(validateScriptDocumentV2(second.document).valid).toBe(true);
  });

  it("is one existing session command and one Undo, with no history for a refusal", () => {
    const { doc, row } = fixture();
    const original = structuredClone(doc);
    const prepared = prepareResearchQuotePlacementV2(doc, quote(), picture(),
      request(row, { kind: "insert", beforeTokenId: null }), generator());
    expect(prepared.ok).toBe(true);
    if (!prepared.ok) return;
    expect(doc).toEqual(original);
    const session = createRowEditSessionV2(doc);
    const applied = session.apply(prepared.command);
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    expect(session.undoDepth).toBe(1);
    expect(placed(session.document).row.text).toBe("Look closer A historic line");
    expect(session.undo().ok).toBe(true);
    expect(session.undoDepth).toBe(0);
    expect(session.document.activeDraft.blocks).toEqual(original.activeDraft.blocks);
    expect(session.redo().ok).toBe(true);
    expect(placed(session.document).row.text).toBe("Look closer A historic line");
    const stale = prepareResearchQuotePlacementV2(session.document, quote(), null,
      request(row, { kind: "selected_words", startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[1]!.id }));
    expect(stale.ok).toBe(false);
    expect(session.undoDepth).toBe(1);
  });

  it("refuses invalid scope, stale anchors, malformed metadata and UUID collisions atomically", () => {
    const { doc, row } = fixture(true);
    const original = structuredClone(doc);
    const base = request(row, { kind: "insert", beforeTokenId: row.tokens[1]!.id });
    const invalidRequests: ResearchQuotePlacementV2[] = [
      { ...base, expectedDocumentRevision: 9 },
      { ...base, expectedRowVersion: row.version + 1 },
      { ...base, expectedSequenceVersion: row.primaryVisualSequence!.version + 1 },
      { ...base, rowId: researchId(999900) },
      { ...base, destination: { kind: "insert", beforeTokenId: researchId(999901) } },
      { ...base, destination: { kind: "selected_words", startTokenId: row.tokens[1]!.id, endTokenId: row.tokens[0]!.id } },
      { ...base, destination: { kind: "selected_words", startTokenId: researchId(999902), endTokenId: row.tokens[0]!.id } },
    ];
    for (const bad of invalidRequests) {
      const result = placeResearchQuoteV2(doc, quote(), picture(), bad, generator());
      expect(result.ok, JSON.stringify(bad)).toBe(false);
      expect(result.document).toBe(doc);
      expect(doc).toEqual(original);
    }
    const invalidQuote = { ...quote(), italicSpan: { start: 200, end: 201 } };
    const invalids: Array<{ quote: AuthorizedResearchQuoteV2; background: ResearchQuoteBackgroundV2 }> = [
      { quote: invalidQuote, background: picture() },
      { quote: { ...quote(), researchQuoteId: "not-an-id" }, background: picture() },
      { quote: { ...quote(), spokenText: "   " }, background: picture() },
      { quote: quote(), background: { kind: "web_capture", source: { kind: "capture_revision", captureId: "bad", revisionId: researchId(999901) } } },
    ];
    for (const bad of invalids) {
      const result = placeResearchQuoteV2(doc, bad.quote, bad.background, base, generator());
      expect(result.ok, JSON.stringify(bad)).toBe(false);
      expect(result.document).toBe(doc);
      expect(doc).toEqual(original);
    }
    for (const duplicate of [row.id, quote().researchQuoteId, researchId(880120)]) {
      const result = placeResearchQuoteV2(doc, quote(), picture(), base, () => duplicate);
      expect(result.ok).toBe(false);
      expect(result.document).toBe(doc);
      expect(doc).toEqual(original);
    }
    let allocated = 0;
    const lateCollision = placeResearchQuoteV2(doc, quote(), picture(), base,
      () => (++allocated === 7 ? row.id : researchId(920000 + allocated)));
    expect(allocated).toBe(7); // The overlay's last ID fails only after the row and visuals were composed.
    expect(lateCollision.ok).toBe(false);
    expect(lateCollision.document).toBe(doc);
    expect(doc).toEqual(original);
  });
});
