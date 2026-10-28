import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { spokenNarrationViewV2 } from "../src/authoring-v2-stage-directions.js";
import type { ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

describe("stage-direction prompter spacing", () => {
  it.each([
    ["[Beat] Hello.", "Hello."],
    ["Hello. [Beat]", "Hello."],
    ["Hello [beat], world", "Hello, world"],
    ["Hello [beat] , world", "Hello, world"],
    ["Hello [beat] world", "Hello world"],
    ["Hello[beat] world", "Hello world"],
    ["[Beat] [Pause] Hello.", "Hello."],
    ["Hello [Beat] [Pause]", "Hello"],
    ["Hello [Beat] [Pause], world", "Hello, world"],
    ['He said "go [beat]" now', 'He said "go" now'],
    ['"[sighs] Not now"', '"Not now"'],
    ["“[sighs] Not now [beat]”", "“Not now”"],
    ["Hello\n[Beat] Now", "Hello\nNow"],
  ])("removes directions without stray spacing: %s", (text, expected) => {
    const fixture = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
    const row = fixture.document.activeDraft.blocks.find((block) => block.type === "narration")!;
    row.text = text;
    const tokens = [...text.matchAll(/[A-Za-z]+/gu)].map((match, index) => ({
      id: `word-${index}`, value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
      spoken: text.lastIndexOf("[", match.index) <= text.lastIndexOf("]", match.index),
    }));
    row.tokens = [tokens[0]!, ...tokens.slice(1)];
    const view = spokenNarrationViewV2(row);
    expect(view.text).toBe(expected);
    for (const token of view.tokens) expect(view.text.slice(token.startOffset, token.endOffset)).toBe(token.value);
  });
});
