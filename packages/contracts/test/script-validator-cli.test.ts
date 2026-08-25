import type { ScriptDocumentV1 } from "../src/generated/contracts.js";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

import { afterEach, describe, expect, it } from "vitest";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const cliPath = `${repositoryRoot}packages/contracts/src/script-validator-cli.ts`;
const dataRoot = `${repositoryRoot}tests/data/slice_1_1`;
const temporaryDirectories: string[] = [];
const canonicalRows = {
  minimal: [
    "Row 1 [section] order=a0 id=11000000-0000-4000-8000-000000000003",
    "Row 2 [narration] order=a1 id=11000000-0000-4000-8000-000000000004",
  ],
  torture: [
    "Row 1 [section] order=a0 id=12000000-0000-4000-8000-000000000003",
    "Row 2 [direction] order=a1 id=12000000-0000-4000-8000-000000000004",
    "Row 3 [narration] order=a2 id=12000000-0000-4000-8000-000000000005",
    "Row 4 [narration] order=a3 id=12000000-0000-4000-8000-000000000021",
    "Row 5 [visual] order=a4 id=12000000-0000-4000-8000-000000000024",
    "Row 6 [note_draft] order=a5 id=12000000-0000-4000-8000-000000000027",
  ],
} as const;

function run(...args: string[]) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
}

function temporaryFile(name: string, contents: string): string {
  const directory = mkdtempSync(join(tmpdir(), "vera-slice-1-1-"));
  temporaryDirectories.push(directory);
  const path = join(directory, name);
  writeFileSync(path, contents, "utf8");
  return path;
}

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("script validator CLI subprocess", () => {
  it.each(["minimal", "torture"] as const)(
    "prints deterministic pass output and every row for %s",
    (name) => {
      const path = `${dataRoot}/${name}.script-document.json`;
      const before = readFileSync(path, "utf8");
      const first = run(path);
      const second = run(path);
      expect(first.status).toBe(0);
      expect(first.stderr).toBe("");
      const expected = [
        `PASS ScriptDocument valid: ${path}`,
        ...canonicalRows[name],
        `${canonicalRows[name].length} row(s) validated.`,
        "",
      ].join("\n");
      expect(first.stdout).toBe(expected);
      expect(second.stdout).toBe(expected);
      expect(readFileSync(path, "utf8")).toBe(before);
    },
  );

  it("distinguishes usage failures", () => {
    const none = run();
    const many = run("one.json", "two.json");
    expect(none.status).toBe(64);
    expect(none.stderr).toContain("USAGE");
    expect(many.status).toBe(64);
    expect(many.stderr).toContain("exactly one JSON file");
  });

  it("distinguishes read failures", () => {
    const result = run("/definitely/not/a/vera-script.json");
    expect(result.status).toBe(66);
    expect(result.stderr).toContain("READ_ERROR");
    expect(result.stderr).not.toContain("at ");
  });

  it("distinguishes JSON parse failures", () => {
    const result = run(temporaryFile("broken.json", "{ not json\n"));
    expect(result.status).toBe(65);
    expect(result.stderr).toContain("PARSE_ERROR");
    expect(result.stderr).not.toContain("\n    at ");
  });

  it("prints schema failures with a row and exits for validation", () => {
    const document = JSON.parse(
      readFileSync(`${dataRoot}/minimal.script-document.json`, "utf8"),
    ) as ScriptDocumentV1;
    document.activeDraft.blocks[1]!.orderKey = "";
    const path = temporaryFile(
      "schema-invalid.json",
      JSON.stringify(document),
    );
    const result = run(path);
    expect(result.status).toBe(1);
    expect(result.stdout).toBe(
      [
        `FAIL ScriptDocument invalid: ${path}`,
        "1 diagnostic(s):",
        "- SCHEMA_INVALID | Row 2 order= block=11000000-0000-4000-8000-000000000004 | /activeDraft/blocks/1/orderKey | minLength: must NOT have fewer than 1 characters",
        "",
      ].join("\n"),
    );
    expect(result.stderr).toBe("");
  });

  it("prints a precise semantic VO gap with narration row and token range", () => {
    const document = JSON.parse(
      readFileSync(`${dataRoot}/minimal.script-document.json`, "utf8"),
    ) as ScriptDocumentV1;
    const block = document.activeDraft.blocks[1];
    if (block?.type !== "narration") {
      throw new Error("canonical minimal input lost its narration row");
    }
    block.visualEvents = [];
    const path = temporaryFile(
      "semantic-invalid.json",
      JSON.stringify(document),
    );
    const result = run(path);
    expect(result.status).toBe(1);
    expect(result.stdout).toBe(
      [
        `FAIL ScriptDocument invalid: ${path}`,
        "1 diagnostic(s):",
        "- VOICEOVER_VISUAL_GAP | Row 2 order=a1 block=11000000-0000-4000-8000-000000000004 | token | tokens=11000000-0000-4000-8000-000000000005..11000000-0000-4000-8000-000000000006 | /activeDraft/blocks/1/visualEvents | Voiceover tokens require ready full-frame local media or an unresolved full-frame visual placeholder.",
        "",
      ].join("\n"),
    );
    expect(result.stderr).toBe("");
  });
});
