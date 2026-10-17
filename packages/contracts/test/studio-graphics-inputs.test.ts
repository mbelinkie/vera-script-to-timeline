import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, it } from "vitest";

import { canonicalJson, compileTimeline } from "../src/compiler-core.js";
import { assembleEv24Package, registerEv24LowerThird } from "../src/ev24-lower-third.js";
import type { CompilerDependenciesV1, ScriptDocumentV1, TimelineManifestV1 } from "../src/generated/contracts.js";
import { TemplateLibraryService, type Actor } from "../src/template-library.js";

const fixture = (name: string) => fileURLToPath(new URL(`../../../tests/data/issue_7/${name}`, import.meta.url));

it("compiles the live acceptance matrix and one-field revision from a registered pinned revision", () => {
  const retained = process.env.VERA_ISSUE8_INPUTS;
  const output = retained ?? mkdtempSync(join(tmpdir(), "vera-issue8-"));
  mkdirSync(output, { recursive: true });
  const document = JSON.parse(readFileSync(fixture("otis.script-document.json"), "utf8")) as ScriptDocumentV1;
  const approval = {
    projectId: document.projectId, producerName: "Matt Belinkie",
    brandApproved: true, packageDistributionApproved: true, fontUseApproved: true,
    settingRightsHolder: "Matt Belinkie", atlasRightsHolder: "Matt Belinkie",
    fontRightsBasis: "Producer acceptance of #12 on 2026-09-22 for VERA; licensed local fonts",
  };
  const candidate = assembleEv24Package(approval);
  const service = new TemplateLibraryService({
    projects: [{ id: document.projectId, name: "VERA issue 8 acceptance", suiteId: "vera",
      compatibility: ["fusion", "resolve-studio:21.1.0.0014"] }],
    validatorProfiles: [{ profile: "ev24-lower-third", version: "1" }],
  });
  const actor: Actor = { id: "issue8-acceptance", grants: [
    { capability: "template:intake", scope: "registry" },
    { capability: "template:register", scope: "registry" },
    { capability: "project:member", scope: document.projectId },
    { capability: "template:manage", scope: document.projectId },
  ] };
  const registration = registerEv24LowerThird(service, actor, document.projectId, approval, candidate);
  expect(registration.ok).toBe(true);
  if (!registration.ok) throw new Error(JSON.stringify(registration.report));
  const template = join(output, "registered-template");
  mkdirSync(template);
  writeFileSync(join(template, "package-manifest.json"), canonicalJson(candidate.manifest));
  writeFileSync(join(template, "registration.json"), canonicalJson(registration.value));
  for (const file of candidate.files) writeFileSync(join(template, file.path), file.bytes);
  let caseIndex = 0;
  for (const duration of [64, 120]) {
    const samples = duration * 2000;
    const audio = Buffer.alloc(44 + samples * 4);
    audio.write("RIFF"); audio.writeUInt32LE(audio.length - 8, 4); audio.write("WAVEfmt ", 8);
    audio.writeUInt32LE(16, 16); audio.writeUInt16LE(1, 20); audio.writeUInt16LE(2, 22);
    audio.writeUInt32LE(48000, 24); audio.writeUInt32LE(192000, 28);
    audio.writeUInt16LE(4, 32); audio.writeUInt16LE(16, 34); audio.write("data", 36);
    audio.writeUInt32LE(samples * 4, 40);
    const audioPath = join(output, `silence-${duration}.wav`);
    writeFileSync(audioPath, audio);
    const hash = createHash("sha256").update(audio).digest("hex");
    const modes = duration === 120 ? ["standard", "overrides", "otis", "revised"] : ["standard", "overrides", "otis"];
    for (const mode of modes) {
      const doc = structuredClone(document);
      const block = doc.activeDraft.blocks[1];
      if (block?.type !== "narration") throw new Error("Expected narration");
      const graphic = block.visualEvents[1];
      if (graphic?.source.kind !== "curated_fusion_graphic") throw new Error("Expected graphic");
      graphic.source.projectRevisionId = registration.value.projectRevision.id;
      graphic.source.packageDigest = registration.value.packageDigest;
      graphic.source.semanticInputs = {
        country: mode === "otis" ? "otis" : "finland",
        ...(mode === "otis" ? {} : { year: 2024 }),
        topLineOverride: mode === "revised" ? "The Code — revised" : mode === "overrides" ? "The Code" : null,
        bottomLineOverride: mode === "overrides" || mode === "revised" ? "Nemo" : null,
        badgeOverrideAssetId: null,
      };
      if (mode === "revised") graphic.version += 1;
      // The lower third remains the overlay; retain a harmless visual beneath it on V1.
      const background = block.visualEvents[0];
      if (!background) throw new Error("Expected background");
      background.layer = 1;
      const deps = JSON.parse(readFileSync(fixture("normal.compiler-dependencies.json"), "utf8")) as CompilerDependenciesV1;
      deps.build.buildId = `88000000-0000-4000-8000-${String(++caseIndex).padStart(12, "0")}`;
      deps.build.timeline.frameRate = { numerator: 24, denominator: 1 };
      const narration = deps.narration[0];
      if (narration?.status !== "ready") throw new Error("Expected ready narration");
      narration.audioHash = `sha256:${hash}`;
      narration.audio.durationSamples = samples;
      narration.audio.channels = 2;
      const resolved = deps.resolvedGraphics?.[0];
      if (!resolved) throw new Error("Expected resolved graphic");
      resolved.projectRevisionId = registration.value.projectRevision.id;
      resolved.packageDigest = registration.value.packageDigest;
      resolved.badgeAssets = [];
      const compiled = compileTimeline(doc, deps);
      expect(compiled.ok).toBe(true);
      if (!compiled.ok) throw new Error(JSON.stringify(compiled));
      const event = compiled.manifest.events.find((event) => event.kind === "fusion_graphic");
      expect(event?.recordRange.durationFrames).toBe(duration);
      const folder = join(output, `${mode}-${duration}`);
      mkdirSync(folder);
      writeFileSync(join(folder, "timeline-manifest.json"), compiled.manifestJson);
      writeFileSync(join(folder, "build-report.json"), compiled.reportJson);
      const source = compiled.manifest.sources.find((source) => source.kind === "audio");
      if (!source) throw new Error("Expected audio source");
      writeFileSync(join(folder, "materialization-plan.json"), canonicalJson({
        [source.id]: { artifactId: "issue8-synthetic-silence", origin: audioPath, policy: "copy" },
      }));
      if (mode === "revised") {
        const previous = JSON.parse(readFileSync(join(output, "overrides-120/timeline-manifest.json"), "utf8")) as TimelineManifestV1;
        const oldGraphic = previous.events.find((item) => item.kind === "fusion_graphic");
        if (oldGraphic?.kind !== "fusion_graphic") throw new Error("Expected previous compiled graphic");
        if (event?.kind !== "fusion_graphic") throw new Error("Expected compiled graphic");
        expect(event.id).toBe(oldGraphic.id);
        expect(event.recordRange).toEqual(oldGraphic.recordRange);
        expect(event.semanticSnapshot.values).toEqual({
          ...oldGraphic.semanticSnapshot.values, topLineOverride: "The Code — revised",
        });
        expect(event.semanticSnapshotHash).not.toBe(oldGraphic.semanticSnapshotHash);
        expect(compiled.manifest.buildId).not.toBe(previous.buildId);
        expect(oldGraphic.semanticSnapshot.values.topLineOverride).toBe("The Code");
      }
    }
  }
  if (!retained) rmSync(output, { recursive: true });
});
