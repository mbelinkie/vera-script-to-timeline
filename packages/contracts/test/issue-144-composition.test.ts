import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import type { NarrationBlock } from "../src/generated/contracts.js";
import { composeEdits, inspectComposition } from "../src/issue-144-composition.js";

import { hash, id, inputs } from "./issue-144-test-inputs.js";

function fixture(overlap = false) {
  const input = inputs(({ block, dependencies }) => {
    block.text = "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel";
    let offset = 0;
    block.tokens = block.text.split(" ").map((value, index) => {
      const row = { id: id(index + 1), value, startOffset: offset, endOffset: offset + value.length };
      offset += value.length + 1;
      return row;
    }) as NarrationBlock["tokens"];
    const full = { blockId: block.id, startTokenId: id(1), endTokenId: id(8), startAffinity: "before" as const, endAffinity: "after" as const, quotedText: block.text, anchorVersion: 1 };
    block.hostVisibilitySpans[0]!.range = { ...full };
    block.hostVisibilitySpans[0]!.state = "voiceover";
    const cover = block.visualEvents[0]!;
    cover.range = { ...full }; cover.audioPolicy = "mute";
    const move = structuredClone(cover);
    move.id = id(30); move.layer = 3; move.audioPolicy = "use_source";
    move.range = { ...full, startTokenId: id(4), endTokenId: id(5), quotedText: "Delta Echo" };
    if (overlap) move.range = { ...full, endTokenId: id(4), quotedText: "Alpha Bravo Charlie Delta" };
    const trim = structuredClone(move);
    trim.id = id(31); trim.layer = 4;
    trim.source = { kind: "local_media", mediaReferenceId: id(40), mediaKind: "video", label: "Distinct synthetic trim source" };
    trim.range = { ...full, startTokenId: id(7), endTokenId: id(8), quotedText: "Golf Hotel" };
    block.visualEvents.push(move, trim);
    const narration = dependencies.narration[0]!;
    narration.textHash = `sha256:${createHash("sha256").update(block.text).digest("hex")}`;
    narration.audio.durationSamples = 384_000;
    narration.timing.marks = block.tokens.map((row, index) => ({ kind: "word", timeMs: index * 1000, startUtf16: row.startOffset, endUtf16: row.endOffset, value: row.value }));
    dependencies.resolvedVisuals[0]!.sourceStartFrame = 0;
    dependencies.resolvedVisuals[0]!.sourceAudio!.sourceStartFrame = 0;
    const resolved = structuredClone(dependencies.resolvedVisuals[0]!);
    resolved.mediaReferenceId = id(40); resolved.source.path = "Media/Resolved/trim.mov"; resolved.source.contentHash = hash("f");
    resolved.sourceAudio!.source.path = "Media/Resolved/trim.wav"; resolved.sourceAudio!.source.contentHash = hash("a");
    dependencies.resolvedVisuals.push(resolved);
  });
  const row = input.currentDocument.activeDraft.blocks[1];
  if (row?.type !== "narration") throw new Error("missing row");
  const primary = input.baselineManifest.events.find(event => event.kind === "audio" && event.provenance.authoringKind === "narration_block")!;
  const cover = input.baselineObservation.items.find(item => item.eventId === row.visualEvents[0]!.id)!;
  const narration = input.baselineObservation.items.find(item => item.eventId === primary.id)!;
  cover.linkedUids = [narration.itemUid]; narration.linkedUids = [cover.itemUid];
  const items = input.baselineObservation.items.filter(item => ![primary.id, cover.eventId].includes(item.eventId)).map(item => {
    const { eventId, ...raw } = structuredClone(item);
    const event = input.baselineManifest.events.find(candidate => candidate.id === eventId)!;
    if (event.provenance.authoringId === id(30)) raw.recordRange.startFrame += 25;
    if (event.provenance.authoringId === id(31)) { raw.recordRange.durationFrames -= 25; raw.sourceRange!.durationFrames -= 25; }
    return raw;
  });
  for (const [suffix, start, duration, sourceStart] of [["head", 0, 49, 0], ["tail", 50, 125, 75]] as const) {
    const a = { ...structuredClone(narration), itemUid: `${narration.itemUid}-${suffix}`, recordRange: { startFrame: start, durationFrames: duration }, sourceRange: { startFrame: sourceStart, durationFrames: duration }, linkedUids: [`${cover.itemUid}-${suffix}`] };
    const b = { ...structuredClone(cover), itemUid: `${cover.itemUid}-${suffix}`, recordRange: { ...a.recordRange }, sourceRange: { ...a.sourceRange }, linkedUids: [a.itemUid] };
    const { eventId: unusedA, ...rawA } = a; const { eventId: unusedB, ...rawB } = b;
    void unusedA; void unusedB; items.push(rawA, rawB);
  }
  const { items: unusedItems, ...envelope } = input.baselineObservation; void unusedItems;
  const raw = { ...envelope, schemaVersion: "issue-144-omission-observation/v1" as const, items, programControls: { observed: false }, audioControls: [] };
  return { rowId: row.id, baselineDocument: input.baselineDocument, currentDocument: input.currentDocument, dependencies: input.dependencies, baselineManifest: input.baselineManifest, baselineObservation: input.baselineObservation, observationA: raw, observationB: structuredClone(raw) };
}

describe("Issue144 pure three-edit composition", () => {
  it("derives both linked visual candidates from raw capture without returning a projected observation", () => {
    const input = fixture(); const before = canonicalJson(input);
    const inspected = inspectComposition(input);
    expect(inspected.visualReport.rows.map(row => row.operation).sort()).toEqual(["move", "trim"]);
    expect(inspected.visualReport.rows.every(row => row.classification === "supported")).toBe(true);
    expect(Object.keys(inspected).sort()).toEqual(["visualManifest", "visualReport"]);
    expect(canonicalJson(input)).toBe(before);
  });

  it("omits original token identity then transfers surviving visual anchors into one canonical revision", () => {
    const input = fixture(); const before = canonicalJson(input);
    const revised = composeEdits(input, { expectedDocumentHash: sha256CanonicalJson(input.currentDocument), blockId: input.rowId, tokenIds: [id(3)] });
    const row = revised.document.activeDraft.blocks[1];
    if (row?.type !== "narration") throw new Error("missing revised row");
    expect(row.text).toBe("Alpha Bravo Delta Echo Foxtrot Golf Hotel");
    expect(row.visualEvents.find(visual => visual.id === id(30))!.range).toMatchObject({ startTokenId: id(5), endTokenId: id(6), quotedText: "Echo Foxtrot", anchorVersion: 2 });
    expect(row.visualEvents.find(visual => visual.id === id(31))!.range).toMatchObject({ startTokenId: id(7), endTokenId: id(7), quotedText: "Golf", anchorVersion: 2 });
    expect(row.version).toBe(input.currentDocument.activeDraft.blocks[1]!.version + 1);
    expect(revised.document.liveHeadSequence).toBe(input.currentDocument.liveHeadSequence + 1);
    expect(revised.document.liveContentHash).toBe(sha256CanonicalJson(Object.fromEntries(Object.entries(revised.document).filter(([key]) => key !== "liveContentHash"))));
    expect(revised.regeneration).toMatchObject({ policy: "replace_whole_row", blockId: input.rowId, text: row.text, blockRevision: row.version });
    expect(revised.documentJson).toBe(canonicalJson(revised.document));
    expect(canonicalJson(input)).toBe(before);
  });

  it.each(["stale", "extra", "picture-only", "wrong-source", "duplicate", "wrong-target", "missing-edit"])("refuses %s raw composition", fault => {
    const input = fixture();
    const item = input.observationA.items.find(candidate => candidate.trackKind === "video" && candidate.itemUid === input.baselineObservation.items.find(old => old.eventId === id(30))!.itemUid)!;
    if (fault === "stale") item.recordRange.startFrame += 1;
    if (fault === "extra") input.observationA.items.push({ ...structuredClone(item), itemUid: "unknown" });
    if (fault === "picture-only") {
      const peer = input.observationA.items.find(candidate => candidate.itemUid === item.linkedUids[0])!;
      peer.recordRange.startFrame -= 25;
    }
    if (fault === "wrong-source") item.sourceHash = hash("b");
    if (fault === "duplicate") input.observationA.items.push(structuredClone(item));
    if (fault === "wrong-target") input.observationA.projectUid = "other";
    if (fault === "missing-edit") {
      item.recordRange.startFrame -= 25;
      input.observationA.items.find(candidate => candidate.itemUid === item.linkedUids[0])!.recordRange.startFrame -= 25;
    }
    if (fault !== "stale") input.observationB = structuredClone(input.observationA);
    expect(() => inspectComposition(input)).toThrow();
  });

  it("retains the original omission transformer's removed-endpoint refusal", () => {
    const input = fixture();
    expect(() => composeEdits(input, { expectedDocumentHash: sha256CanonicalJson(input.currentDocument), blockId: input.rowId, tokenIds: [id(4)] })).toThrow(/removed anchor endpoint/u);
  });

  it("records both an omission quote update and an accepted range change when they touch the same visual", () => {
    const input = fixture(true);
    const revised = composeEdits(input, { expectedDocumentHash: sha256CanonicalJson(input.currentDocument), blockId: input.rowId, tokenIds: [id(3)] });
    const row = revised.document.activeDraft.blocks[1];
    if (row?.type !== "narration") throw new Error("missing revised row");
    const visual = row.visualEvents.find(event => event.id === id(30))!;
    expect(visual.version).toBe(3);
    expect(visual.range).toMatchObject({ startTokenId: id(2), endTokenId: id(5), quotedText: "Bravo Delta Echo", anchorVersion: 3 });
    expect(revised.document.liveHeadSequence).toBe(input.currentDocument.liveHeadSequence + 1);
    expect(row.version).toBe(input.currentDocument.activeDraft.blocks[1]!.version + 1);
  });

  it.each([false, true])("exchanges raw files and actual compiler/script results through the pinned CLI (revision=%s)", revise => {
    const input = fixture(); const root = mkdtempSync(join(tmpdir(), "vera144-compose-"));
    const rawPath = join(root, "raw-inputs.json"); const editPath = join(root, "trusted-edit.json");
    writeFileSync(rawPath, canonicalJson(input));
    writeFileSync(editPath, canonicalJson({ expectedDocumentHash: sha256CanonicalJson(input.currentDocument), blockId: input.rowId, tokenIds: [id(3)] }));
    const cli = fileURLToPath(new URL("../src/issue-144-proof-cli.ts", import.meta.url));
    const result = spawnSync(process.execPath, [cli, "compose", rawPath, ...(revise ? [editPath] : [])], { encoding: "utf8", timeout: 300_000 });
    expect(result.status, result.stderr).toBe(0);
    const receipt = JSON.parse(result.stdout) as { ok: boolean; result: { status: string; visualManifest?: unknown; regeneration?: { text: string } }; artifacts: Record<string, string>; sourceHashes: Record<string, string> };
    expect(receipt.ok).toBe(true);
    expect(receipt.sourceHashes["./issue-144-composition.ts"]).toMatch(/^sha256:[a-f0-9]{64}$/u);
    if (revise) {
      expect(Object.keys(receipt.artifacts)).toEqual(["script-document.json"]);
      expect(receipt.result.regeneration!.text).toBe("Alpha Bravo Delta Echo Foxtrot Golf Hotel");
    } else {
      expect(receipt.artifacts).toEqual({});
      expect(receipt.result.visualManifest).toEqual(inspectComposition(input).visualManifest);
    }
    expect(receipt.result).not.toHaveProperty("projection");
  });
});
