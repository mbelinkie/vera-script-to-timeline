import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { canonicalJson, compileTimeline, sha256CanonicalJson } from "../src/compiler-core.js";
import type { NarrationBlock } from "../src/generated/contracts.js";
import { applyVisualDecisions, proposeVisuals } from "../src/issue-144-semantics.js";

import { edit, hash, id, inputs } from "./issue-144-test-inputs.js";

describe("Issue144 compiler-backed visual semantics", () => {
  it.each(["move", "trim"] as const)("maps a linked %s without rewriting narration", (operation) => {
    const input = inputs();
    const original = canonicalJson(input);
    edit(input, operation);
    const edited = canonicalJson(input);
    const report = proposeVisuals(input);
    expect(report.status).toBe("ready");
    expect(report.rows).toHaveLength(1);
    expect(report.rows[0]).toMatchObject({ classification: "supported", operation });
    const decisions = { schemaVersion: "issue-144-decisions/v1", reportHash: sha256CanonicalJson(report), choices: [{ proposalId: report.rows[0]!.id, decision: "accept" }] };
    const applied = applyVisualDecisions(input, report, decisions);
    expect(applied.status).toBe("revised");
    if (applied.status !== "revised") return;
    const before = input.currentDocument.activeDraft.blocks[1];
    const after = applied.document.activeDraft.blocks[1];
    if (before?.type !== "narration" || after?.type !== "narration") throw new Error("missing narration");
    expect([after.text, after.tokens, after.version]).toEqual([before.text, before.tokens, before.version]);
    expect(after.visualEvents[0]!.range.quotedText).toBe(operation === "move" ? "Charlie Delta" : "Bravo");
    expect(after.visualEvents[0]!.version).toBe(before.visualEvents[0]!.version + 1);
    expect(applied.document.liveHeadSequence).toBe(input.currentDocument.liveHeadSequence + 1);
    expect(applied.document.liveStateVector).toBe("");
    expect(applied.dependencies.narration).toEqual(input.dependencies.narration);
    expect(applied.dependencies.build.buildId).not.toBe(input.dependencies.build.buildId);
    expect(compileTimeline(applied.document, applied.dependencies).ok).toBe(true);
    expect(applyVisualDecisions(input, report, decisions)).toEqual(applied);
    expect(canonicalJson(input)).toBe(edited);
    expect(original).not.toBe(edited);
  });

  it("refuses a picture-only trim as a linked semantic edit", () => {
    const input = inputs(); edit(input, "trim", true);
    expect(proposeVisuals(input).rows[0]).toMatchObject({ classification: "unsupported" });
  });

  it("refuses two token candidates that round to the same frame bounds", () => {
    const input = inputs(({ block, dependencies }) => {
      block.text = "Alpha Bravo Charlie Delta Echo Foxtrot";
      let offset = 0;
      block.tokens = block.text.split(" ").map((value, index) => {
        const token = { id: id(index + 1), value, startOffset: offset, endOffset: offset + value.length };
        offset += value.length + 1; return token;
      }) as NarrationBlock["tokens"];
      block.hostVisibilitySpans[0]!.range.endTokenId = id(6);
      block.hostVisibilitySpans[0]!.range.quotedText = block.text;
      const dependency = dependencies.narration[0]!;
      dependency.textHash = `sha256:${createHash("sha256").update(block.text).digest("hex")}`;
      dependency.timing.marks = block.tokens.map((token, index) => ({ kind: "word", timeMs: [0, 1000, 1999, 2000, 3000, 4000][index]!, startUtf16: token.startOffset, endUtf16: token.endOffset, value: token.value }));
    });
    edit(input, "move");
    expect(proposeVisuals(input).rows[0]).toMatchObject({ classification: "unsupported", reason: "ambiguous token boundaries after frame rounding" });
  });

  it("checks clearance on the shared source-audio track", () => {
    const input = inputs(({ block }) => {
      const neighbor = structuredClone(block.visualEvents[0]!);
      neighbor.id = id(30); neighbor.layer = 3;
      neighbor.range = { ...neighbor.range, startTokenId: id(4), endTokenId: id(5), quotedText: "Delta Echo" };
      block.visualEvents.push(neighbor);
    });
    edit(input, "move");
    expect(proposeVisuals(input).rows[0]).toMatchObject({ classification: "unsupported", reason: "video or shared source-audio track has no clearance" });
  });

  it("refuses a move that leaves voiceover tokens without coverage", () => {
    const input = inputs(({ block }) => {
      block.hostVisibilitySpans[0]!.state = "voiceover";
      for (const [identity, first, last, text] of [[31, 1, 1, "Alpha"], [32, 4, 5, "Delta Echo"]] as const) {
        const cover = structuredClone(block.visualEvents[0]!);
        cover.id = id(identity); cover.layer = 5; cover.status = "unresolved"; cover.audioPolicy = "mute";
        cover.source = { kind: "placeholder", description: text, unresolvedVisual: true };
        cover.range = { ...cover.range, startTokenId: id(first), endTokenId: id(last), quotedText: text };
        block.visualEvents.push(cover);
      }
    });
    edit(input, "move");
    expect(proposeVisuals(input).rows[0]).toMatchObject({ classification: "unsupported", reason: "no validator-passing compiler range reproduces both endpoints" });
  });

  it.each(["project", "timeline", "source", "duplicate", "unavailable", "stale", "script"])("refuses %s evidence", (fault) => {
    const input = inputs(); edit(input, "move");
    if (fault === "project") input.observationA.projectUid = "other-project";
    if (fault === "timeline") input.observationA.timelineUid = "other-timeline";
    if (fault === "source") input.observationA.items[0]!.sourceHash = hash("f");
    if (fault === "duplicate") input.observationA.items[1]!.itemUid = input.observationA.items[0]!.itemUid;
    if (fault === "unavailable") input.observationA.items[0]!.available = false;
    if (fault === "script") input.currentDocument.title = "changed";
    if (fault !== "stale") input.observationB = structuredClone(input.observationA);
    else input.observationB.items[0]!.recordRange.startFrame += 1;
    const before = canonicalJson(input);
    expect(proposeVisuals(input).status).toBe("refused");
    expect(canonicalJson(input)).toBe(before);
  });

  it("rejects all choices without advancing a revision", () => {
    const input = inputs(); edit(input, "trim");
    const report = proposeVisuals(input);
    expect(applyVisualDecisions(input, report, { schemaVersion: "issue-144-decisions/v1", reportHash: sha256CanonicalJson(report), choices: [{ proposalId: report.rows[0]!.id, decision: "reject" }] })).toEqual({ status: "rejected" });
  });

  it.each(["missing", "duplicate", "unknown", "stale", "unsupported", "malformed"])("refuses %s decisions", (fault) => {
    const input = inputs(); edit(input, "move", fault === "unsupported");
    const report = proposeVisuals(input);
    const choice = { proposalId: report.rows[0]!.id, decision: "accept" };
    const decisions: Record<string, unknown> = { schemaVersion: "issue-144-decisions/v1", reportHash: sha256CanonicalJson(report), choices: [choice] };
    if (fault === "missing") decisions.choices = [];
    if (fault === "duplicate") decisions.choices = [choice, choice];
    if (fault === "unknown") choice.proposalId = "foreign";
    if (fault === "stale") input.observationA.items[0]!.recordRange.startFrame += 1;
    if (fault === "malformed") decisions.extra = true;
    const before = canonicalJson(input);
    expect(() => applyVisualDecisions(input, report, decisions)).toThrow();
    expect(canonicalJson(input)).toBe(before);
  });
});
