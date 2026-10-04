import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { compileTimeline } from "../src/compiler-core.js";
import type { CompilerDependenciesV1, NarrationBlock, ScriptDocumentV1 } from "../src/generated/contracts.js";
import type { ProofObservation, VisualProofInputs } from "../src/issue-144-semantics.js";

export const id = (suffix: number): string => `14400000-0000-4000-8000-${String(suffix).padStart(12, "0")}`;
export const hash = (letter: string): string => `sha256:${letter.repeat(64)}`;
function fixture(): { document: ScriptDocumentV1; dependencies: CompilerDependenciesV1; block: NarrationBlock } {
  const load = (path: string): unknown => JSON.parse(readFileSync(fileURLToPath(new URL(`../../../tests/data/${path}`, import.meta.url)), "utf8"));
  const document = load("slice_1_1/minimal.script-document.json") as ScriptDocumentV1;
  const dependencies = load("slice_1_3/minimal.compiler-dependencies.json") as CompilerDependenciesV1;
  const block = document.activeDraft.blocks[1];
  if (block?.type !== "narration") throw new Error("fixture narration missing");
  block.text = "Alpha Bravo Charlie Delta Echo";
  let offset = 0;
  block.tokens = block.text.split(" ").map((value, index) => {
    const token = { id: id(index + 1), value, startOffset: offset, endOffset: offset + value.length };
    offset += value.length + 1;
    return token;
  }) as NarrationBlock["tokens"];
  const fullRange = { blockId: block.id, startTokenId: id(1), endTokenId: id(5), startAffinity: "before" as const, endAffinity: "after" as const, quotedText: block.text, anchorVersion: 1 };
  block.hostVisibilitySpans[0]!.range = fullRange;
  block.hostVisibilitySpans[0]!.state = "on_camera";
  const visual = block.visualEvents[0]!;
  visual.range = { ...fullRange, startTokenId: id(2), endTokenId: id(3), quotedText: "Bravo Charlie" };
  visual.source = { kind: "local_media", mediaReferenceId: id(20), mediaKind: "video", label: "Issue144 synthetic visual" };
  visual.layer = 2;
  visual.audioPolicy = "use_source";
  visual.status = "ready";
  dependencies.build.timeline.frameRate = { numerator: 25, denominator: 1 };
  const narration = dependencies.narration[0]!;
  narration.textHash = `sha256:${createHash("sha256").update(block.text).digest("hex")}`;
  narration.audio.durationSamples = 240_000;
  narration.timing.marks = block.tokens.map((token, index) => ({ kind: "word", timeMs: index * 1000, startUtf16: token.startOffset, endUtf16: token.endOffset, value: token.value }));
  dependencies.resolvedVisuals = [{ mediaReferenceId: id(20), source: { id: id(21), kind: "video", path: "Media/Resolved/visual.mov", contentHash: hash("c"), durationFrames: 1000, frameRate: { numerator: 25, denominator: 1 }, width: 1920, height: 1080, audioChannels: 0 }, sourceStartFrame: 10, sourceAudio: { source: { id: id(22), kind: "audio", path: "Media/Resolved/source.wav", contentHash: hash("d"), durationFrames: 1000, sampleRate: 48000, channels: 1 }, sourceStartFrame: 10 } }];
  return { document, dependencies, block };
}

export function inputs(adjust?: (data: ReturnType<typeof fixture>) => void): VisualProofInputs {
  const data = fixture();
  adjust?.(data);
  const { document, dependencies } = data;
  const result = compileTimeline(document, dependencies);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  const manifest = result.manifest;
  const observation: ProofObservation = {
    schemaVersion: "issue-144-observation/v1", evidenceLevel: "synthetic_injected",
    projectUid: "fake-project", timelineUid: "fake-timeline",
    timeline: structuredClone(manifest.timeline), tracks: structuredClone(manifest.tracks),
    items: manifest.events.map((event, index) => {
      const source = manifest.sources.find((row) => row.id === event.sourceId)!;
      return { eventId: event.id, itemUid: `item-${index}`, mediaUid: `media-${event.sourceId}`,
        sourcePath: source.kind === "placeholder" ? `Media/Placeholders/${source.id}.png` : source.path,
        sourceHash: source.kind === "placeholder" ? hash("e") : source.contentHash,
        trackId: event.trackId, trackKind: event.trackKind, recordRange: structuredClone(event.recordRange),
        sourceRange: "sourceRange" in event ? structuredClone(event.sourceRange) : null,
        available: true, enabled: true, speed: 100, linkedUids: [] };
    }),
  };
  for (const visual of data.block.visualEvents) {
    const pair = observation.items.filter((item) => manifest.events.find((event) => event.id === item.eventId)!.provenance.authoringId === visual.id);
    if (pair.length === 2) {
      pair[0]!.linkedUids = [pair[1]!.itemUid];
      pair[1]!.linkedUids = [pair[0]!.itemUid];
    }
  }
  return { baselineDocument: document, currentDocument: structuredClone(document), dependencies, baselineManifest: manifest, baselineObservation: observation, observationA: structuredClone(observation), observationB: structuredClone(observation) };
}

export function edit(input: VisualProofInputs, operation: "move" | "trim", pictureOnly = false): void {
  const authoringId = input.baselineManifest.events.find((event) => event.kind === "video")!.provenance.authoringId;
  for (const observation of [input.observationA, input.observationB]) {
    for (const item of observation.items) {
      const event = input.baselineManifest.events.find((row) => row.id === item.eventId)!;
      if (event.provenance.authoringId !== authoringId || (pictureOnly && event.kind !== "video")) continue;
      if (operation === "move") item.recordRange.startFrame += 25;
      else { item.recordRange.durationFrames -= 25; item.sourceRange!.durationFrames -= 25; }
    }
  }
}
