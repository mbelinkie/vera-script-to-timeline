import { randomUUID } from "node:crypto";

import { applyVisualSequenceEditV2, applyRowEditV2, validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { describe, expect, it, vi } from "vitest";

import { createAuthoringHandler } from "../src/authoring.js";
import {
  applySelectedStashTransfer, captureStashNoteDrop, captureStashWords, createStashActions, createStashNoteCommand,
  insertStashNoteCommand, projectStash, stashWordsCommand,
  captureWholeRowStash, wholeRowStashCommand, captureSavedPlacement, savedPlacementCommand,
  originalDraftLocation, draftGapChoices,
} from "../browser/stash-actions.js";

import { captureSelectedDrop } from "../browser/visual-selection.js";

const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const ids = (start: number): (() => string) => {
  let next = start;
  return () => id(next++);
};

function narration(n: number, text: string): NarrationBlockV2 {
  const tokens = [...text.matchAll(/[^\s[\]]+/gu)].map((match, index) => ({
    id: id(n * 100 + index + 1), value: match[0], startOffset: match.index,
    endOffset: match.index + match[0].length,
  }));
  return {
    type: "narration", id: id(n), orderKey: `row-${n}`, text, tokens,
    primaryVisualSequence: { id: id(n * 100 + 90), version: 1, slots: [{
      id: id(n * 100 + 91), kind: "content", relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function fixture() {
  const source = narration(101, "Alpha beta gamma delta");
  const target = narration(102, "Harbor morning returns");
  const document: ScriptDocumentV2 = {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Synthetic Stash",
    activeDraft: { blocks: [source, target], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"0".repeat(64)}`,
  };
  expect(validateScriptDocumentV2(document).valid).toBe(true);
  return { document, source, target };
}

function apply(document: ScriptDocumentV2, command: Parameters<typeof applyRowEditV2>[2]) {
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  return result.document;
}

describe("whole-row Extras intent and provenance (#78)", () => {
  it("captures an ordered selection, parks and restores the exact row without changing its identity", () => {
    const { document, source, target } = fixture();
    const intent = captureWholeRowStash(document, [source.id])!;
    expect(Object.isFrozen(intent)).toBe(true);
    expect(Object.isFrozen(intent.rowIds)).toBe(true);
    const command = wholeRowStashCommand(document, intent, ids(2000));
    expect(command).toEqual({ kind: "stash_rows", rowIds: [source.id], bundleId: id(2000) });
    const parked = apply(document, command);
    const bundle = parked.stash![0]!;
    const before = structuredClone(parked);
    expect(originalDraftLocation(parked, bundle)).toEqual({
      label: "Before first section", available: true,
      gap: { sectionId: null, afterRowId: null, beforeRowId: target.id },
    });
    expect(projectStash(parked)[0]?.entries[0]).toMatchObject({
      bundleId: bundle.id, rowId: source.id, originalDraft: originalDraftLocation(parked, bundle),
    });
    expect(parked).toEqual(before);
    expect(parked.extras).toEqual([]);
    const restore = captureSavedPlacement(parked, "restore_stash_rows", [source.id], bundle.originalGap!)!;
    expect(Object.isFrozen(restore.destination)).toBe(true);
    expect(savedPlacementCommand(parked, restore)).toEqual({
      kind: "restore_stash_rows", rowIds: [source.id], destination: bundle.originalGap,
    });
    const restored = apply(parked, savedPlacementCommand(parked, restore));
    expect(restored.activeDraft.blocks.map((row) => row.id)).toEqual([source.id, target.id]);
    expect((restored.activeDraft.blocks[0] as NarrationBlockV2).tokens).toEqual(source.tokens);
    expect(parked).toEqual(before);
  });

  it("projects a renamed or missing original Draft heading independently of the Stash section", () => {
    const { document, source, target } = fixture();
    const section = { type: "section" as const, id: id(2100), title: "Original Draft", orderKey: "a", version: 1 };
    document.activeDraft.blocks.unshift(section);
    const stashSectionId = id(2190);
    const sectioned = apply(document, { kind: "create_stash_section", sectionId: stashSectionId, title: "Stash heading" });
    const command = wholeRowStashCommand(sectioned, captureWholeRowStash(sectioned, [source.id])!, ids(2101));
    const parked = apply(sectioned, { ...command,
      destination: { sectionId: stashSectionId, afterRowId: null, beforeRowId: null, parentRowId: null } });
    const bundle = parked.stash![0]!;
    expect(originalDraftLocation(parked, bundle)).toMatchObject({
      label: "Original Draft", available: true, gap: { sectionId: section.id, beforeRowId: target.id },
    });
    expect(projectStash(parked)[1]?.entries[0]).toMatchObject({
      sectionId: stashSectionId, originalDraft: { label: "Original Draft", available: true },
    });
    const renamed = structuredClone(parked);
    const heading = renamed.activeDraft.blocks[0];
    if (heading?.type !== "section") throw new Error("missing heading");
    heading.title = "Renamed Draft";
    expect(originalDraftLocation(renamed, bundle)).toMatchObject({ label: "Renamed Draft", available: true });
    expect(draftGapChoices(renamed)).toContainEqual({ gap: bundle.originalGap,
      label: "Renamed Draft — Before Harbor morning returns" });
    renamed.activeDraft.blocks.shift();
    expect(originalDraftLocation(renamed, bundle)).toMatchObject({ label: "Original section unavailable", available: false });
    const note = apply(parked, createStashNoteCommand(parked, "independent note", {}, ids(2200)));
    expect(projectStash(note)[0]?.entries.find((entry) => entry.kind === "note")?.originalDraft)
      .toEqual({ label: "Original section not recorded", gap: null, available: false });
  });

  it("refuses changed, missing, reversed or cross-section source without allocating a bundle", () => {
    const { document, source, target } = fixture();
    const intent = captureWholeRowStash(document, [source.id])!;
    const makeId = vi.fn(ids(2300));
    expect(captureWholeRowStash(document, [])).toBeNull();
    expect(captureWholeRowStash(document, [source.id, source.id])).toBeNull();
    expect(captureWholeRowStash(document, [target.id, source.id])).toBeNull();
    expect(captureWholeRowStash(document, [id(9999)])).toBeNull();
    const altered = structuredClone(document);
    (altered.activeDraft.blocks[0] as NarrationBlockV2).text += " changed";
    const crossSection = structuredClone(document);
    crossSection.activeDraft.blocks.splice(1, 0, {
      type: "section", id: id(2301), title: "Other", orderKey: "a", version: 1,
    });
    expect(captureWholeRowStash(crossSection, [source.id, target.id])).toBeNull();
    for (const changed of [altered, { ...document, projectId: id(9999) }, { ...document, id: id(9998) }]) {
      expect(() => wholeRowStashCommand(changed, intent, makeId)).toThrow(/changed/u);
    }
    expect(makeId).not.toHaveBeenCalled();
  });

  it("refuses stale saved material and exact destination, even with unchanged versions", () => {
    const { document, source, target } = fixture();
    const anchor = { kind: "word" as const, anchor: {
      blockId: source.id, tokenId: source.tokens[0]!.id, affinity: "before" as const,
      quotedWord: source.tokens[0]!.value, anchorVersion: 1,
    } };
    document.activeDraft.supportingItems.push({
      id: id(2401), version: 1, orderKey: "citation", role: "citation", content: "Source evidence",
      placement: { kind: "point", anchor }, displayAttachment: anchor,
    });
    const parked = apply(document, wholeRowStashCommand(document, captureWholeRowStash(document, [source.id])!, ids(2400)));
    const gap = parked.stash![0]!.originalGap!;
    const selection = [source.id];
    const intent = captureSavedPlacement(parked, "duplicate_stash_rows", selection, gap)!;
    selection[0] = target.id;
    expect(savedPlacementCommand(parked, intent)).toEqual({ kind: "duplicate_stash_rows",
      rowIds: [source.id], destination: gap });
    const placement = captureSavedPlacement(parked, "place_stash_rows", [source.id], gap, false)!;
    expect(savedPlacementCommand(parked, placement)).toEqual({ kind: "place_stash_rows",
      rowIds: [source.id], destination: gap, includeDescendants: false });
    expect(captureSavedPlacement(parked, "restore_stash_rows", [source.id], gap, false)).toBeNull();
    expect(captureSavedPlacement(parked, "restore_stash_rows", [target.id], gap)).toBeNull();
    const changedSaved = structuredClone(parked);
    (changedSaved.stash![0]!.rows[0] as NarrationBlockV2).text += " changed";
    const changedCitation = structuredClone(parked);
    changedCitation.stash![0]!.supportingItems[0]!.content = "Changed evidence";
    const changedGap = structuredClone(parked);
    (changedGap.activeDraft.blocks[0] as NarrationBlockV2).text += " changed";
    const removedGap = structuredClone(parked);
    removedGap.activeDraft.blocks.length = 0;
    expect(captureSavedPlacement(removedGap, "restore_stash_rows", [source.id], gap)).toBeNull();
    for (const changed of [changedSaved, changedCitation, changedGap, removedGap, { ...parked, projectId: id(9999) }]) {
      expect(() => savedPlacementCommand(changed, intent)).toThrow(/changed/u);
    }
  });
});

describe("Stash browser command binding (#674 phase 1)", () => {
  it("builds one saved literal note in its section, retaining row and token identities", () => {
    const { document, source } = fixture();
    const sectionId = id(600);
    const sectioned = apply(document, { kind: "create_stash_section", sectionId, title: "Ideas" });
    const command = createStashNoteCommand(sectioned, "  [literal] words  ", { sectionId }, ids(610));
    const saved = apply(sectioned, command);
    const section = projectStash(saved)[1]!;
    expect(section.id).toBe(sectionId);
    expect(section.title).toBe("Ideas");
    expect(section.entries).toHaveLength(1);
    expect(section.entries[0]).toMatchObject({ kind: "note", rowId: command.row.id, sectionId });
    expect(section.entries[0]!.row).toMatchObject({
      text: "  [literal] words  ", plainDirection: true,
      stashChecklist: { completed: false, manualRevision: 0 },
    });
    expect(section.entries[0]!.row.id).toBe(command.row.id);
    expect(section.entries[0]!.row.type).toBe("narration");
    expect((section.entries[0]!.row as NarrationBlockV2).tokens.map((token) => token.id))
      .toEqual(command.row.tokens.map((token) => token.id));
    expect(saved.activeDraft.blocks[0]).toEqual(source);
    expect(projectStash(document)[0]?.entries).toEqual([]);
  });

  it("stashes selected words as an unsectioned note, preserving the remaining source IDs", () => {
    const { document, source } = fixture();
    const selection = captureStashWords(document, source.id, { start: 7, end: 16 });
    expect(selection?.words).toEqual({
      startTokenId: source.tokens[1]!.id, endTokenId: source.tokens[2]!.id,
    });
    const command = stashWordsCommand(document, selection!, ids(700));
    const saved = apply(document, command);
    expect(saved.stashOutline?.[0]).toMatchObject({ kind: "note", sectionId: null, rowId: command.stashRowId });
    expect(projectStash(saved)[0]?.entries[0]?.row).toMatchObject({ text: "beta gamma", plainDirection: true });
    const remaining = saved.activeDraft.blocks[0] as NarrationBlockV2;
    expect(remaining.tokens.map((token) => token.id)).toEqual([source.tokens[0]!.id, source.tokens[3]!.id]);
    expect(source.text).toBe("Alpha beta gamma delta");
  });

  it("drops a saved note into an exact interior gap, leaving the original untouched and checkable", () => {
    const { document, target } = fixture();
    const creation = createStashNoteCommand(document, "[cold open] now", {}, ids(800));
    const withNote = apply(document, creation);
    const note = projectStash(withNote)[0]!.entries[0]!.row;
    const gapToken = target.tokens[1]!.id;
    const intent = captureStashNoteDrop(withNote, note.id, target.id, gapToken);
    expect(intent).not.toBeNull();
    const inserted = apply(withNote, insertStashNoteCommand(withNote, intent!));
    const row = inserted.activeDraft.blocks[1] as NarrationBlockV2;
    expect(row.text).toBe("Harbor [cold open] now morning returns");
    expect(row.tokens[0]?.id).toBe(target.tokens[0]?.id);
    expect(row.tokens.at(-1)?.id).toBe(target.tokens.at(-1)?.id);
    expect(inserted.stash?.[0]?.rows[0]).toMatchObject({ id: note.id, text: note.text,
      stashChecklist: { completed: true, manualRevision: 0 } });
    expect(note).toMatchObject({ stashChecklist: { completed: false } });
  });

  it("refuses missing sections, blank notes, stale selected words, and changed source or receiving rows", () => {
    const { document, source, target } = fixture();
    expect(() => createStashNoteCommand(document, " ")).toThrow(/Enter a note/u);
    expect(() => createStashNoteCommand(document, "note", { sectionId: id(9999) })).toThrow(/section/u);
    expect(captureStashWords(document, id(999), { start: 0, end: 3 })).toBeNull();
    const words = captureStashWords(document, source.id, { start: 6, end: 10 })!;
    const changed = structuredClone(document);
    (changed.activeDraft.blocks[0] as NarrationBlockV2).version += 1;
    expect(() => stashWordsCommand(changed, words)).toThrow(/changed/u);
    // A locally changed token that forgot to bump row.version must not be
    // applied against a selection captured before that change.
    const changedWithoutVersion = structuredClone(document);
    (changedWithoutVersion.activeDraft.blocks[0] as NarrationBlockV2).tokens[1]!.value = "changed";
    expect(() => stashWordsCommand(changedWithoutVersion, words)).toThrow(/changed/u);
    const noteCreated = apply(document, createStashNoteCommand(document, "saved note", {}, ids(900)));
    const noteId = noteCreated.stash?.[0]?.rows[0]?.id ?? "";
    expect(captureStashNoteDrop(noteCreated, id(9999), target.id, target.tokens[1]!.id)).toBeNull();
    expect(captureStashNoteDrop(noteCreated, noteId, target.id, id(7777))).toBeNull();
    const intent = captureStashNoteDrop(noteCreated, noteId, target.id, target.tokens[1]!.id)!;
    const changedNote = structuredClone(noteCreated);
    (changedNote.stash![0]!.rows[0] as NarrationBlockV2).version += 1;
    expect(() => insertStashNoteCommand(changedNote, intent)).toThrow(/changed/u);
    const changedTarget = structuredClone(noteCreated);
    (changedTarget.activeDraft.blocks[1] as NarrationBlockV2).version += 1;
    expect(() => insertStashNoteCommand(changedTarget, intent)).toThrow(/changed/u);
  });

  it("uses a single existing editor queue for each change, with zero Undo writes on denied/stale actions", async () => {
    const { document, source, target } = fixture();
    let current = document;
    const undo: ScriptDocumentV2[] = [];
    const queue = vi.fn((resolve: (doc: ScriptDocumentV2) => Parameters<typeof applyRowEditV2>[2],
      _label: string, options: { structural: true }) => {
      expect(options).toEqual({ structural: true });
      try {
        const result = applyRowEditV2(current, current.rowEditRevision ?? 0, resolve(current));
        if (!result.ok) return Promise.resolve(false);
        undo.push(current);
        current = result.document;
        return Promise.resolve(true);
      } catch { return Promise.resolve(false); }
    });
    const actions = createStashActions(queue, () => current, ids(1000));
    expect(await actions.addNote("saved note")).toBe(true);
    expect(await actions.stashWords(source.id, { start: 6, end: 10 })).toBe(true);
    expect(actions.view()[0]?.entries).toHaveLength(2);
    const noteId = actions.view()[0]!.entries[0]!.row.id;
    expect(await actions.dropNote(noteId, target.id, target.tokens[1]!.id)).toBe(true);
    expect(undo).toHaveLength(3);
    const afterInsertion = current;
    current = undo.pop()!; // Browser's existing snapshot Undo, not a second Stash history.
    expect((current.activeDraft.blocks[1] as NarrationBlockV2).text).toBe(target.text);
    expect(afterInsertion.stash?.some((bundle) => bundle.rows.some((row) => row.id === noteId))).toBe(true);
    expect(await actions.stashWords(id(9999), { start: 0, end: 2 })).toBe(false);
    expect(undo).toHaveLength(2);
    const captured = captureStashWords(current, source.id, { start: 0, end: 5 })!;
    const altered = structuredClone(current);
    (altered.activeDraft.blocks[0] as NarrationBlockV2).version += 1;
    expect(() => stashWordsCommand(altered, captured)).toThrow(/changed/u);
  });
});

describe("existing authenticated browser command endpoint", () => {
  it("accepts exactly the Stash commands and does not change document or Undo state on denial", async () => {
    const origin = "http://127.0.0.1:38429";
    const host = createAuthoringHandler(origin, "Bearer synthetic", () =>
      Promise.resolve(Response.json({ error: "No saved project requested" }, { status: 500 })));
    const request = async (path: string, body: unknown, session?: string): Promise<Response> => (await host.handle(new Request(`${origin}/authoring/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-VERA-Authoring": "1",
        "Sec-Fetch-Site": "same-origin", Origin: origin,
        ...(session ? { "X-VERA-Session": session } : {}),
        ...(path === "session" ? { "X-VERA-Launch": host.launchCode } : {}) },
      body: JSON.stringify(body),
    }))) as Response;
    const session = await request("session", {});
    expect(session.status).toBe(200);
    const { sessionProof } = await session.json() as { sessionProof: string };
    const { document, source } = fixture();
    const noteCommand = createStashNoteCommand(document, "host note", {}, ids(1300));
    const body = { document, command: noteCommand };
    expect((await request("command", body)).status).toBe(401);
    expect((await request("command", body, randomUUID())).status).toBe(401);
    const accepted = await request("command", body, sessionProof);
    expect(accepted.status).toBe(200);
    const created = await accepted.json() as { ok: boolean; document: ScriptDocumentV2 };
    expect(created.ok).toBe(true);
    expect(created.document.stash?.[0]?.rows[0]?.text).toBe("host note");
    const stale = await request("command", { document: created.document,
      command: { kind: "stash_selected_words", rowId: source.id, bundleId: id(1400), stashRowId: id(1401),
        words: { startTokenId: id(9999), endTokenId: source.tokens[2]!.id } } }, sessionProof);
    expect(stale.status).toBe(200);
    const rejected = await stale.json() as { ok: boolean; document: ScriptDocumentV2 };
    expect(rejected.ok).toBe(false);
    expect(rejected.document).toEqual(created.document);
    expect(document.stash).toBeUndefined();

    const chosen = captureStashWords(created.document, source.id, { start: 6, end: 10 })!;
    const cut = await request("command", { document: created.document,
      command: stashWordsCommand(created.document, chosen, ids(1500)) }, sessionProof);
    expect(cut.status).toBe(200);
    const cutBody = await cut.json() as { ok: boolean; document: ScriptDocumentV2 };
    expect(cutBody.ok).toBe(true);
    expect(cutBody.document.stashOutline).toHaveLength(2);
    const target = cutBody.document.activeDraft.blocks[1] as NarrationBlockV2;
    const noteId = noteCommand.row.id;
    const dropIntent = captureStashNoteDrop(cutBody.document, noteId, target.id, target.tokens[1]!.id)!;
    const placed = await request("command", { document: cutBody.document,
      command: insertStashNoteCommand(cutBody.document, dropIntent) }, sessionProof);
    expect(placed.status).toBe(200);
    const placement = await placed.json() as { ok: boolean; document: ScriptDocumentV2 };
    expect(placement.ok).toBe(true);
    expect((placement.document.activeDraft.blocks[1] as NarrationBlockV2).text).toBe("Harbor host note morning returns");
    expect(placement.document.stash?.flatMap((bundle) => bundle.rows).find((row) => row.id === noteId))
      .toMatchObject({ text: "host note", stashChecklist: { completed: true } });
    expect(placement.document.rowEditRevision).toBe(3);
  });
});

describe("#691 private selected Stash transfer", () => {
  it("guards the queued range and source, composes the real transforms, and discards failed or stale scratch", async () => {
    const { document, source, target } = fixture();
    const sourceSlot = source.primaryVisualSequence!.slots[0]!;
    if (sourceSlot.kind !== "content") throw new Error("missing fixture slot");
    sourceSlot.payload = { kind: "visual", payloadId: id(9001), pictureKind: "unresolved_visual",
      source: { kind: "unresolved_visual", description: "Synthetic picture" }, sourceUsage: null,
      audioPolicy: "mute", framingPolicy: "contain" };
    const parked = apply(document, { kind: "stash_visual", rowId: source.id, slotId: sourceSlot.id,
      bundleId: id(9002), stashRowId: id(9003), sectionId: null, parentRowId: null, afterRowId: null });
    const frozen = structuredClone(parked);
    const snapshot = captureSelectedDrop(parked, { rowId: target.id, text: target.text,
      rowVersion: target.version, sequenceVersion: target.primaryVisualSequence!.version,
      selected: true, selection: { start: 0, end: 14 } })!;
    expect(snapshot).not.toBeNull();
    const insert = { kind: "insert_stash_visual" as const, stashRowId: id(9003),
      destinationRowId: target.id, destinationSlotId: id(9004) };
    const applyTransform: Parameters<typeof applySelectedStashTransfer>[3] = (model, command, _, sequence) =>
      Promise.resolve(command.kind === "attach_visual_to_words"
        ? applyVisualSequenceEditV2(model, sequence!, command)
        : applyRowEditV2(model, model.rowEditRevision ?? 0, command as Parameters<typeof applyRowEditV2>[2]));
    const calls = vi.fn(applyTransform);
    const result = await applySelectedStashTransfer(parked, insert, snapshot, calls, () => {});
    expect(calls).toHaveBeenCalledTimes(2);
    expect(calls.mock.calls[1]?.[1]).toMatchObject({ kind: "attach_visual_to_words",
      startTokenId: target.tokens[0]!.id, endTokenId: target.tokens[1]!.id });
    expect(result.document.stash?.flatMap((bundle) => bundle.rows) ?? []).toHaveLength(0);
    expect(parked).toEqual(frozen);
    const secondRefusal = vi.fn(applyTransform).mockImplementationOnce(applyTransform)
      .mockRejectedValueOnce(new Error("second refusal"));
    await expect(applySelectedStashTransfer(parked, insert, snapshot, secondRefusal, () => {})).rejects.toThrow("second refusal");
    expect(parked).toEqual(frozen);
    const stale = vi.fn().mockImplementationOnce(() => {}).mockImplementationOnce(() => { throw new Error("stale"); });
    calls.mockClear();
    await expect(applySelectedStashTransfer(parked, insert, snapshot, calls, stale)).rejects.toThrow("stale");
    expect(calls).toHaveBeenCalledTimes(1);
    expect(parked).toEqual(frozen);
    const queue = vi.fn(() => Promise.resolve(true));
    const actions = createStashActions(queue, () => parked);
    await actions.insertStashVisual(insert.stashRowId, target.id, insert.destinationSlotId, parked, snapshot);
    expect(queue).toHaveBeenCalledTimes(1);
    const changed = structuredClone(parked);
    changed.stash = [];
    const resolve = queue.mock.calls[0] as unknown as [(model: ScriptDocumentV2) => unknown, string, unknown];
    expect(resolve[2]).toEqual({ structural: true, selectedStashDrop: snapshot });
    expect(resolve[0](parked)).toEqual(insert);
    expect(() => resolve[0](changed)).toThrow(/changed/);
  });
});
