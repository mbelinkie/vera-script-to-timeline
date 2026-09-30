import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { compileTimeline } from "../../../packages/contracts/src/compiler-core.js";
import { validateScriptDocument } from "../../../packages/contracts/src/script-validator.js";

const read = (name: string) => JSON.parse(readFileSync(new URL(`../../../tests/data/${name}`, import.meta.url), "utf8"));
const document = () => read("slice_1_1/minimal.script-document.json");
const dependencies = () => read("slice_1_3/minimal.compiler-dependencies.json");
function splitDocument() {
  const script = document();
  const first = script.activeDraft.blocks[1];
  const second = structuredClone(first);
  second.id = "11000000-0000-4000-8000-000000000009";
  second.orderKey = "a2";
  first.text = "Hello";
  first.tokens = [first.tokens[0]];
  second.text = "world.";
  second.tokens = [{ ...second.tokens[1], startOffset: 0, endOffset: 5 }];
  for (const [row, word] of [[first, "Hello"], [second, "world"]]) {
    for (const entity of [...row.hostVisibilitySpans, ...row.visualEvents]) {
      entity.range = {
        ...entity.range, blockId: row.id,
        startTokenId: row.tokens[0].id, endTokenId: row.tokens[0].id, quotedText: word,
      };
    }
  }
  second.hostVisibilitySpans[0].id = "11000000-0000-4000-8000-000000000010";
  second.visualEvents[0].id = "11000000-0000-4000-8000-000000000011";
  script.activeDraft.blocks.push(second);
  return script;
}

describe("#131 current-contract boundary (copies only; no fixture writes)", () => {
  it("retains exact accepted minimal compiler bytes and both inputs", () => {
    const script = document();
    const deps = dependencies();
    const before = JSON.stringify([script, deps]);
    const result = compileTimeline(script, deps);
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Baseline must compile");
    expect(result.manifestJson).toBe(readFileSync(new URL("../../../tests/data/slice_1_3/minimal.manifest.golden.json", import.meta.url), "utf8"));
    expect(JSON.stringify([script, deps])).toBe(before);
  });

  it("accepts a formatting split with stable tokens but rejects unchanged audio dependencies", () => {
    const script = splitDocument();
    expect(validateScriptDocument(script).diagnostics).toEqual([]);
    const before = JSON.stringify(script);
    const result = compileTimeline(script, dependencies());
    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Unchanged narration dependencies must not compile");
    expect(result.diagnostics.map(item => item.code)).toEqual(expect.arrayContaining([
      "NARRATION_TEXT_HASH_MISMATCH", "NARRATION_DEPENDENCY_MISSING",
    ]));
    expect("manifest" in result).toBe(false);
    expect(JSON.stringify(script)).toBe(before);
  });

  it("rejects an endpoint belonging to another row; quote matching cannot repair it", () => {
    const script = splitDocument();
    script.activeDraft.blocks[1].visualEvents[0].range.endTokenId = script.activeDraft.blocks[2].tokens[0].id;
    const before = JSON.stringify(script);
    const result = validateScriptDocument(script);
    expect(result.valid).toBe(false);
    expect(result.diagnostics.map(item => item.code)).toContain("ANCHOR_TOKEN_NOT_FOUND");
    expect(JSON.stringify(script)).toBe(before);
  });

  it("rejects duplicate token identities", () => {
    const script = document();
    script.activeDraft.blocks[1].tokens[1].id = script.activeDraft.blocks[1].tokens[0].id;
    expect(validateScriptDocument(script).diagnostics.map(item => item.code)).toContain("TOKEN_ID_DUPLICATE");
  });

  it.each(["reconciliation", "dormantItems", "preservedItems", "reviewDecisions"])("rejects unapproved %s persistence in v1", field => {
    const script = document();
    script[field] = [];
    expect(validateScriptDocument(script).valid).toBe(false);
  });

  it("rejects a timeline-bounds timing override instead of inventing a word anchor", () => {
    const script = document();
    script.activeDraft.blocks[1].visualEvents[0].timingOverrides = { startFrame: 0, durationFrames: 160 };
    expect(validateScriptDocument(script).valid).toBe(false);
  });

  it("rejects stale narration revision without returning a partial manifest", () => {
    const script = document();
    script.activeDraft.blocks[1].version += 1;
    const result = compileTimeline(script, dependencies());
    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Stale audio must fail");
    expect(result.diagnostics.map(item => item.code)).toContain("NARRATION_REVISION_MISMATCH");
    expect("manifest" in result).toBe(false);
  });
});
