import { describe, expect, it } from "vitest";

import type { NarratedVisualPayloadV2, NarrationBlockV2, ResearchQuotePictureV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
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
    researchProjectId: researchId(890003),
    researchSourceId: researchId(890004),
    researchQuoteVersion: 3,
    spokenText: "A historic line",
    displayText: "An edited display line",
    speakerName: "Ada Lovelace",
    speakerTitle: "Mathematician",
    citationText: "History, p. 1",
    italicSpan: { start: 0, end: 7 },
    templateRevision,
  };
}

function picturePin(): ResearchQuotePictureV2 {
  return {
    researchProjectId: researchId(890003), ownerKind: "source", ownerId: researchId(890004),
    revisionId: researchId(890005), original: {
      versionId: "original-v1", sha256: "a".repeat(64), byteCount: 4096,
      mimeType: "image/png", width: 640, height: 480,
    },
  };
}

function picture(): ResearchQuoteBackgroundV2 {
  return {
    kind: "still_image", picture: picturePin(),
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

function gapRequest(
  expectedDocumentRevision: number,
  destination: Extract<ResearchQuotePlacementV2["destination"], { kind: "gap" }>,
): ResearchQuotePlacementV2 {
  return { expectedDocumentRevision, destination };
}

function placed(document: ScriptDocumentV2, rowId?: string) {
  const row = document.activeDraft.blocks.find((block) => block.type === "narration" && (!rowId || block.id === rowId));
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
    expect(edited.text).toBe("Look “A historic line” closer");
    expect(edited.tokens.map((token) => token.value)).toEqual(["Look", "“A", "historic", "line”", "closer"]);
    expect(edited.tokens[0]!.id).toBe(row.tokens[0]!.id);
    expect(edited.tokens[4]!.id).toBe(row.tokens[1]!.id);
    expect(edited.primaryVisualSequence!.slots).toContainEqual(previousSlot);
    expect(background.payload).toMatchObject({
      pictureKind: "image", source: { kind: "media_reference" }, researchQuotePicture: picturePin(),
      displayName: "Synthetic article picture",
    });
    expect(overlay.quoteBox).toMatchObject({
      researchQuoteId: quote().researchQuoteId,
      researchProjectId: quote().researchProjectId,
      researchSourceId: quote().researchSourceId,
      researchQuoteVersion: quote().researchQuoteVersion,
      displayText: quote().displayText,
      speakerName: quote().speakerName,
      speakerTitle: quote().speakerTitle,
      italicSpan: quote().italicSpan,
      templateRevision,
      backgroundPayloadId: background.payload.payloadId,
    });
    expect(overlay.timing).toMatchObject({
      kind: "timed",
      start: { kind: "word", anchor: { tokenId: edited.tokens[1]!.id, quotedWord: "“A" } },
      end: { kind: "audible_word_end", anchor: { tokenId: edited.tokens[3]!.id, quotedWord: "line”" } },
    });
    expect(edited.tokens.slice(1, 4).map((token) => token.researchQuoteProvenance)).toEqual(
      Array.from({ length: 3 }, () => ({
        researchProjectId: quote().researchProjectId, researchQuoteId: quote().researchQuoteId,
        researchSourceId: quote().researchSourceId, useId: overlay.quoteBox!.researchQuoteUseId,
      })),
    );
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(doc).toEqual(before);
  });

  it("attaches existing words with a retained picture and does not insert narration", () => {
    const { doc, row } = fixture();
    const result = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "selected_words", startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[1]!.id }), generator());
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const { row: edited, overlay, background } = placed(result.document);
    expect(edited.text).toBe(row.text);
    expect(edited.tokens).toEqual(row.tokens);
    expect(background.payload).toMatchObject({
      pictureKind: "image", researchQuotePicture: picturePin(),
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

  it("validates complete quote provenance and image-only pinned pictures", () => {
    const { doc, row } = fixture();
    const placedQuote = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "insert", beforeTokenId: null }), generator());
    expect(placedQuote.ok, JSON.stringify(placedQuote.diagnostics)).toBe(true);
    if (!placedQuote.ok) return;
    const validRow = placedQuote.document.activeDraft.blocks[0];
    if (!validRow || validRow.type !== "narration") throw new Error("Expected narration row");

    const mismatched = structuredClone(placedQuote.document);
    const mismatchRow = mismatched.activeDraft.blocks[0];
    if (!mismatchRow || mismatchRow.type !== "narration") throw new Error("Expected narration row");
    const attributedToken = mismatchRow.tokens.find((token) => token.researchQuoteProvenance);
    if (!attributedToken?.researchQuoteProvenance) throw new Error("Expected attributed speech");
    attributedToken.researchQuoteProvenance.researchSourceId = researchId(890099);
    expect(validateScriptDocumentV2(mismatched).diagnostics.map((item) => item.code))
      .toContain("RESEARCH_QUOTE_PROVENANCE_INVALID");

    const nonspoken = structuredClone(placedQuote.document);
    const nonspokenRow = nonspoken.activeDraft.blocks[0];
    if (!nonspokenRow || nonspokenRow.type !== "narration") throw new Error("Expected narration row");
    const attributedNonspoken = nonspokenRow.tokens.find((token) => token.researchQuoteProvenance);
    if (!attributedNonspoken) throw new Error("Expected attributed speech");
    attributedNonspoken.spoken = false;
    expect(validateScriptDocumentV2(nonspoken).diagnostics.map((item) => item.code))
      .toContain("RESEARCH_QUOTE_PROVENANCE_INVALID");

    const partialBox = structuredClone(placedQuote.document);
    const box = partialBox.activeDraft.blocks[0];
    if (!box || box.type !== "narration") throw new Error("Expected narration row");
    delete box.overlayEvents[0]!.quoteBox!.researchSourceId;
    expect(validateScriptDocumentV2(partialBox).diagnostics.map((item) => item.code))
      .toContain("RESEARCH_QUOTE_PROVENANCE_INVALID");

    const wrongPictureType = structuredClone(placedQuote.document);
    const visualRow = wrongPictureType.activeDraft.blocks[0];
    if (!visualRow || visualRow.type !== "narration") throw new Error("Expected narration row");
    const background = visualRow.primaryVisualSequence!.slots.find((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" &&
      slot.payload.researchQuotePicture !== undefined);
    if (!background || background.kind !== "content" || background.payload.kind !== "visual") {
      throw new Error("Expected a pinned quote background");
    }
    background.payload.pictureKind = "capture";
    delete background.payload.displayName;
    background.payload.framingPolicy = "contain";
    background.payload.source = { kind: "capture_revision", captureId: researchId(890098), revisionId: researchId(890097) };
    const wrongPictureDiagnostics = validateScriptDocumentV2(wrongPictureType).diagnostics;
    expect(wrongPictureDiagnostics.map((item) => item.code), JSON.stringify(wrongPictureDiagnostics))
      .toContain("RESEARCH_QUOTE_PICTURE_INVALID");
    expect(validateScriptDocumentV2(placedQuote.document).valid).toBe(true);
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
    expect(firstRow.text).toBe(`“${quote().spokenText}”`);

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

  it("creates a complete narration row at an exact gap as one Undo command", () => {
    const { doc, row } = fixture();
    const original = structuredClone(doc);
    const prepared = prepareResearchQuotePlacementV2(doc, quote(), null, gapRequest(0, {
      kind: "gap", sectionId: null, afterRowId: row.id, beforeRowId: null,
    }), generator());
    expect(prepared.ok).toBe(true);
    if (!prepared.ok) return;
    expect(prepared.command.kind).toBe("create_row");
    expect(doc).toEqual(original);
    if (prepared.command.kind !== "create_row" || prepared.command.row.type !== "narration") return;
    const created = prepared.command.row;
    expect(created.text).toBe(`“${quote().spokenText}”`);
    expect(created.overlayEvents).toHaveLength(1);
    expect(created.tokens.every((token) => token.researchQuoteProvenance?.useId ===
      created.overlayEvents[0]!.quoteBox!.researchQuoteUseId)).toBe(true);
    expect(validateScriptDocumentV2(prepared.document).valid).toBe(true);

    const session = createRowEditSessionV2(doc);
    expect(session.apply(prepared.command).ok).toBe(true);
    expect(session.undoDepth).toBe(1);
    expect(session.undo().ok).toBe(true);
    expect(session.document.activeDraft.blocks).toEqual(original.activeDraft.blocks);
  });

  it("extends one compatible same-row background across three adjacent quote uses", () => {
    const { doc, row } = fixture();
    const first = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "insert", beforeTokenId: null }), generator());
    expect(first.ok, JSON.stringify(first.diagnostics)).toBe(true);
    const firstRow = first.document.activeDraft.blocks[0];
    if (!firstRow || firstRow.type !== "narration") throw new Error("Expected first quote row");
    const firstBox = firstRow.overlayEvents[0]!.quoteBox!;
    const initialSlot = firstRow.primaryVisualSequence!.slots.find((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" &&
      slot.payload.payloadId === firstBox.backgroundPayloadId);
    if (!initialSlot || initialSlot.kind !== "content") throw new Error("Expected the first quote background");

    const secondQuote = { ...quote(), researchQuoteId: researchId(890006), spokenText: "Another line" };
    const second = placeResearchQuoteV2(first.document, secondQuote, picture(),
      { ...request(firstRow, { kind: "insert", beforeTokenId: null }), expectedDocumentRevision: 1 }, generator(930000));
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const secondRow = second.document.activeDraft.blocks[0];
    if (!secondRow || secondRow.type !== "narration") throw new Error("Expected second quote row");
    const thirdQuote = { ...quote(), researchQuoteId: researchId(890007), spokenText: "One last line" };
    const third = placeResearchQuoteV2(second.document, thirdQuote, picture(),
      { ...request(secondRow, { kind: "insert", beforeTokenId: null }), expectedDocumentRevision: 2 }, generator(940000));
    expect(third.ok, JSON.stringify(third.diagnostics)).toBe(true);
    const thirdRow = third.document.activeDraft.blocks[0];
    if (!thirdRow || thirdRow.type !== "narration") throw new Error("Expected third quote row");
    const boxes = thirdRow.overlayEvents.map((event) => event.quoteBox).filter((box) => box !== undefined);
    expect(boxes).toHaveLength(3);
    expect(new Set(boxes.map((box) => box.researchQuoteUseId)).size).toBe(3);
    expect(new Set(boxes.map((box) => box.backgroundPayloadId))).toHaveLength(1);
    const finalSlot = thirdRow.primaryVisualSequence!.slots.find((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" && slot.payload.payloadId === firstBox.backgroundPayloadId);
    expect(finalSlot).toEqual(expect.objectContaining({ id: initialSlot.id, boundaryBefore: initialSlot.boundaryBefore }));
    expect(validateScriptDocumentV2(third.document).valid).toBe(true);
  });

  it("extends an attached quote only when the next use continues the same source and picture", () => {
    const { doc, row } = fixture();
    const first = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "selected_words", startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[0]!.id }), generator());
    expect(first.ok, JSON.stringify(first.diagnostics)).toBe(true);
    const firstRow = first.document.activeDraft.blocks[0];
    if (!firstRow || firstRow.type !== "narration") throw new Error("Expected first quote row");
    const firstBox = firstRow.overlayEvents[0]!.quoteBox!;
    const nextQuote = { ...quote(), researchQuoteId: researchId(890010), spokenText: "A different saved quote" };
    const second = placeResearchQuoteV2(first.document, nextQuote, picture(),
      { ...request(firstRow, {
        kind: "selected_words", startTokenId: firstRow.tokens[1]!.id, endTokenId: firstRow.tokens[1]!.id,
      }), expectedDocumentRevision: 1 }, generator(945000));
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const secondRow = second.document.activeDraft.blocks[0];
    if (!secondRow || secondRow.type !== "narration") throw new Error("Expected attached quote row");
    const boxes = secondRow.overlayEvents.map((event) => event.quoteBox).filter((box) => box !== undefined);
    expect(boxes).toHaveLength(2);
    expect(boxes[0]!.backgroundPayloadId).toBe(firstBox.backgroundPayloadId);
    expect(new Set(boxes.map((box) => box.researchQuoteUseId)).size).toBe(2);
    expect(secondRow.text).toBe(row.text);
    expect(validateScriptDocumentV2(second.document).valid).toBe(true);

    const otherSource = { ...nextQuote, researchQuoteId: researchId(890011), researchSourceId: researchId(890012) };
    const mismatch = placeResearchQuoteV2(first.document, otherSource, picture(),
      { ...request(firstRow, {
        kind: "selected_words", startTokenId: firstRow.tokens[1]!.id, endTokenId: firstRow.tokens[1]!.id,
      }), expectedDocumentRevision: 1 }, generator(946000));
    expect(mismatch.ok).toBe(false);
  });

  it("does not extend the quote background across another picture", () => {
    const { doc, row } = fixture();
    const first = placeResearchQuoteV2(doc, quote(), picture(),
      request(row, { kind: "insert", beforeTokenId: row.tokens[1]!.id }), generator());
    expect(first.ok, JSON.stringify(first.diagnostics)).toBe(true);
    const current = first.document.activeDraft.blocks[0];
    if (!current || current.type !== "narration") throw new Error("Expected first quote row");
    const placedFirst = structuredClone(current);
    const otherToken = placedFirst.tokens.find((token) => token.value === "closer")!;
    const otherSlot = researchId(950001);
    placedFirst.unattachedVisuals = [{ slotId: otherSlot, version: 1, payload: {
      kind: "visual", payloadId: researchId(950002), pictureKind: "image",
      source: { kind: "media_reference", mediaReferenceId: researchId(950003) }, sourceUsage: null, audioPolicy: "mute",
    } }];
    const attached = attachVisualToWordsV2(placedFirst, otherSlot, otherToken.id, otherToken.id);
    expect("code" in attached).toBe(false);
    const edit = createRowEditSessionV2(first.document);
    const changed = edit.apply({ kind: "edit_row", rowId: placedFirst.id, row: placedFirst });
    expect(changed.ok, JSON.stringify(changed.diagnostics)).toBe(true);
    const intervening = edit.document;
    expect(validateScriptDocumentV2(intervening).valid).toBe(true);

    const secondQuote = { ...quote(), researchQuoteId: researchId(890008), spokenText: "A separate line" };
    const second = placeResearchQuoteV2(intervening, secondQuote, picture(), {
      ...request(placedFirst, { kind: "selected_words", startTokenId: otherToken.id, endTokenId: otherToken.id }), expectedDocumentRevision: 2,
    }, generator(960000));
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const updated = second.document.activeDraft.blocks[0];
    if (!updated || updated.type !== "narration") throw new Error("Expected narration row");
    const boxes = updated.overlayEvents.map((event) => event.quoteBox).filter((box) => box !== undefined);
    expect(boxes).toHaveLength(2);
    expect(boxes[0]!.backgroundPayloadId).not.toBe(boxes[1]!.backgroundPayloadId);
    expect([
      ...updated.primaryVisualSequence!.slots.flatMap((slot) => slot.kind === "content" && slot.payload.kind === "visual" ? [slot.payload.payloadId] : []),
      ...(updated.unattachedVisuals ?? []).map((item) => item.payload.payloadId),
    ]).toContain(researchId(950002));
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
    expect(placed(session.document).row.text).toBe("Look closer “A historic line”");
    expect(session.undo().ok).toBe(true);
    expect(session.undoDepth).toBe(0);
    expect(session.document.activeDraft.blocks).toEqual(original.activeDraft.blocks);
    expect(session.redo().ok).toBe(true);
    expect(placed(session.document).row.text).toBe("Look closer “A historic line”");
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
      { quote: { ...quote(), researchQuoteVersion: 0 }, background: picture() },
      { quote: { ...quote(), spokenText: "   " }, background: picture() },
      { quote: quote(), background: { kind: "still_image", picture: { ...picturePin(), ownerId: "bad" } } },
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
      () => (++allocated === 9 ? row.id : researchId(920000 + allocated)));
    expect(allocated).toBe(9); // The graphic is composed before its final payload ID collides.
    expect(lateCollision.ok).toBe(false);
    expect(lateCollision.document).toBe(doc);
    expect(doc).toEqual(original);
  });
});
