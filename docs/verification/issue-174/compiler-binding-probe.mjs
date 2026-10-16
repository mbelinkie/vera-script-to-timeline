import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { fileURLToPath } from "node:url";

// Exercise the accepted compiler with a real adapter binding; do not alter fixtures.
const root = new URL("../../../", import.meta.url);
const sourceRoot = new URL("packages/contracts/src/", root).href;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith(sourceRoot) && specifier.startsWith("./") && specifier.endsWith(".js")) {
      const candidate = new URL(specifier.slice(0, -3) + ".ts", context.parentURL);
      if (existsSync(candidate)) return nextResolve(candidate.href, context);
    }
    return nextResolve(specifier, context);
  },
});
let compileTimelineV2, resolveMediaRequirementsV2;
try {
  ({ compileTimelineV2, resolveMediaRequirementsV2 } = await import(new URL("compiler-core-v2.ts", sourceRoot)));
} finally {
  hooks.deregister();
}
const { descriptor, binding } = JSON.parse(readFileSync(0, "utf8"));
const deps = JSON.parse(readFileSync(new URL("tests/data/authoring_v2/compiler-dependencies-v2.json", root)));
const doc = {
  schemaVersion: "script-document/v2", id: deps.document.documentId,
  projectId: deps.document.projectId, title: "Issue 174 synthetic binding probe",
  activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
  liveHeadSequence: 0, liveStateVector: "", liveContentHash: deps.document.contentHash,
};
const range = binding.requestedRange;
const rate = descriptor.logicalSourceBounds.frameRate;
const count = range.duration.numerator * rate.numerator / (range.duration.denominator * rate.denominator);
assert(Number.isSafeInteger(count));
assert.deepEqual(range.preHandle, { numerator: 0, denominator: 1 });
assert.deepEqual(range.postHandle, { numerator: 0, denominator: 1 });
descriptor.selectedSourceRange = { startFrame: range.sourceInFrame, endFrame: range.sourceInFrame + count };
descriptor.occurrenceSourceInFrame = range.sourceInFrame;
descriptor.preparedMediaRequirementKey = binding.requirementKey;
const hasAudio = descriptor.sourceFrameMap.sourceAudioStreamMappings.length > 0;
doc.activeDraft.blocks = [{
  type: "visual_only", id: descriptor.owner.blockId, orderKey: "a0", version: 1,
  payload: {
    kind: "visual", payloadId: descriptor.payloadId, pictureKind: "clip",
    source: { kind: "media_reference", mediaReferenceId: descriptor.mediaReferenceId },
    audioPolicy: hasAudio ? "full" : "mute", framingPolicy: "contain",
  },
  visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: range.sourceInFrame, durationFrames: count } },
}];
doc.activeDraft.supportingItems = [];
deps.document.textHash = "sha256:" + createHash("sha256").update("").digest("hex");
deps.narrationTimingMaps = [];
deps.occurrenceResolutions = [descriptor];
deps.preparedMedia = [binding];
deps.timeline.frameRate = binding.targetRate;
deps.tracks.push(
  { id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
  { id: "presenter", kind: "video", index: 3, name: "Presenter" },
  { id: "markers", kind: "video", index: 4, name: "Markers" },
  { id: "source-audio", kind: "audio", index: 2, name: "Source audio" },
);
deps.roles.sourceAudioTrackIds = ["source-audio"];
const needs = resolveMediaRequirementsV2(doc, {
  timing: [], defaults: deps.authoringDefaults,
  sourceDescriptors: [descriptor], frameRate: binding.targetRate,
});
assert.equal(needs.ok, true, JSON.stringify(needs));
assert.deepEqual(needs.requirements[0].requestedRange, range);
const compiled = compileTimelineV2(doc, deps);
assert.equal(compiled.ok, true, JSON.stringify(compiled));
const audio = compiled.manifest.events.find(event => event.kind === "source_audio");
assert.equal(Boolean(audio), hasAudio);
process.stdout.write(JSON.stringify({
  compilerSource: fileURLToPath(new URL("compiler-core-v2.ts", sourceRoot)),
  requirementsPassed: true, bindingAccepted: true,
  durationFrames: compiled.manifest.timeline.durationFrames,
  originalAudioSampleRate: binding.verification.sourceAudio.sampleRate,
  sourceAudioSampleRange: audio?.audio.sampleRange ?? null,
}) + "\n");
