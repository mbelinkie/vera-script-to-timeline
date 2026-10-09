import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "vitest";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "../../../packages/contracts/src/compiler-core-v2.js";

// Investigation only: exercise the accepted compiler, never substitute a new resolver.
test("accepted complete map succeeds; identity-bound subset suppresses picture", () => {
  const here = fileURLToPath(new URL("./", import.meta.url));
  const seed = new URL("../../../tests/data/authoring_v2/issue_173/compiler/root-child-overlay-return.input.golden.json", import.meta.url);
  const full = JSON.parse(readFileSync(seed, "utf8"));
  full.document.title = "Issue 179 synthetic boundary investigation";
  const row = full.document.activeDraft.blocks[0];
  row.overlayEvents = [];
  full.dependencies.occurrenceResolutions.splice(1);
  full.dependencies.preparedMedia.splice(1);
  const map = full.dependencies.narrationTimingMaps[0];
  map.tokens[1].audibleEnd = { numerator: 3, denominator: 2 };
  map.tokens[2].audibleEnd = { numerator: 11, denominator: 4 };
  map.tokens[2].endBasis = "evidenced_audible_end";
  map.timingHash = `sha256:${createHash("sha256").update(JSON.stringify(map.tokens)).digest("hex")}`;
  map.audio.timingHash = map.timingHash;
  const sparse = structuredClone(full);
  sparse.dependencies.narrationTimingMaps[0].tokens.splice(0, 1);
  // Both views pin the same synthetic source receipt; omitted alpha is not an edit boundary.
  for (const mark of sparse.dependencies.narrationTimingMaps[0].tokens) {
    const token = row.tokens.find((token: { id: string }) => token.id === mark.tokenId);
    assert.ok(token);
    assert.equal(mark.startOffset, token.startOffset);
    assert.equal(mark.endOffset, token.endOffset);
    assert.equal(mark.quotedText, token.value);
    assert.equal(row.text.slice(mark.startOffset, mark.endOffset), mark.quotedText);
  }
  const complete = compileTimelineV2(full.document, full.dependencies);
  const subset = compileTimelineV2(sparse.document, sparse.dependencies);
  assert.ok(complete.ok);
  assert.notEqual(complete.report.status, "blocked");
  assert.ok(complete.manifest.events.some((event) => event.trackRole === "child"));
  assert.ok(subset.ok);
  assert.equal(subset.report.status, "blocked");
  assert.ok(subset.report.diagnostics.some((diagnostic) => diagnostic.code === "STALE_TIMING_MAP"));
  assert.ok(subset.manifest.events.every((event) => event.kind === "narration"));
  assert.equal(subset.manifest.timeline.durationFrames, 96);
  assert.equal(subset.manifest.timeline.durationFrames, complete.manifest.timeline.durationFrames);
  const needs = resolveMediaRequirementsV2(sparse.document, {
    timing: sparse.dependencies.narrationTimingMaps,
    defaults: sparse.dependencies.authoringDefaults,
    sourceDescriptors: sparse.dependencies.occurrenceResolutions,
    frameRate: sparse.dependencies.timeline.frameRate,
  });
  assert.equal(needs.ok, false);
  const summary = (result: typeof complete) => result.ok ? {
    ok: true, reportStatus: result.report.status, durationFrames: result.manifest.timeline.durationFrames,
    events: result.manifest.events.map(({ kind, trackRole, recordRange }) => ({ kind, trackRole, recordRange })),
    diagnostics: result.report.diagnostics.map(({ code, message }) => ({ code, message })),
  } : result;
  // Exact arithmetic checks the proposal's examples; this is not future-runtime acceptance.
  const frame = (n: bigint, d: bigint, rateN: bigint, rateD: bigint) => Number((n * rateN + d * rateD - 1n) / (d * rateD));
  const examples = [{ numerator: 24, denominator: 1 }, { numerator: 25, denominator: 1 }, { numerator: 24000, denominator: 1001 }].map((rate) => ({
    rate, betaOnset: frame(1n, 1n, BigInt(rate.numerator), BigInt(rate.denominator)),
    betaAudibleEnd: frame(3n, 2n, BigInt(rate.numerator), BigInt(rate.denominator)),
    gammaOnset: frame(2n, 1n, BigInt(rate.numerator), BigInt(rate.denominator)),
    gammaAudibleEnd: frame(11n, 4n, BigInt(rate.numerator), BigInt(rate.denominator)),
    rowEnd: frame(4n, 1n, BigInt(rate.numerator), BigInt(rate.denominator)),
  }));
  assert.deepEqual(examples.map(({ betaAudibleEnd, gammaOnset, gammaAudibleEnd, rowEnd }) => [betaAudibleEnd, gammaOnset, gammaAudibleEnd, rowEnd]), [[36, 48, 66, 96], [38, 50, 69, 100], [36, 48, 66, 96]]);
  writeFileSync(`${here}complete.input.json`, `${JSON.stringify(full, null, 2)}\n`);
  writeFileSync(`${here}sparse.input.json`, `${JSON.stringify(sparse, null, 2)}\n`);
  writeFileSync(`${here}reproduction-result.json`, `${JSON.stringify({
    observedAcceptedRuntime: { complete: summary(complete), sparse: summary(subset), sparseNeeds: needs },
    proposalOnly: {
      requiredOnsets: [row.tokens[1].id, row.tokens[2].id], unrelatedOmittedToken: row.tokens[0].id,
      expectedPicture: { root: [0, 96], childBeforeGamma: [24, 48], childAfterBetaAudibleEnd: [24, 36] },
      narrationUnchanged: [0, 96], missingRequiredGammaOnset: "block; never substitute beta audible end or row end",
      frameExamples: examples,
    },
    acousticQualification: "Synthetic identities/times only; no audio was synthesized, listened to, or verified.",
  }, null, 2)}\n`);
});
