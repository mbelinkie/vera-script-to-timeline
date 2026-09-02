import { mkdtempSync, readFileSync, writeFileSync, readdirSync, symlinkSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  PROMPTER_EXPORT_EXIT,
  runPrompterExportCli,
} from "../src/prompter-export-cli.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const inputPath = `${repositoryRoot}tests/data/issue_37/acceptance.script-document.json`;

function harness(files: Record<string, string>) {
  let stdout = "";
  let stderr = "";
  const writes = new Map<string, string>();
  return {
    io: {
      stdout: (text: string) => { stdout += text; },
      stderr: (text: string) => { stderr += text; },
      readFile: (path: string) => {
        const value = files[path];
        if (value === undefined) throw new Error("missing input");
        return value;
      },
      writeFile: (path: string, value: string) => { writes.set(path, value); },
    },
    stdout: () => stdout,
    stderr: () => stderr,
    writes,
  };
}

describe("runPrompterExportCli", () => {
  it.each([
    ["input.json", "--text", "input.json", "--sidecar", "out.json"],
    ["input.json", "--text", "out.txt", "--sidecar", "./out.txt"],
    ["input.json", "--text", "", "--sidecar", "out.json"],
    ["input.json", "--text", "out.txt", "--sidecar", "out.json", "--unknown"],
  ])("rejects unsafe or ambiguous paths and arguments: %j", (...args) => {
    const test = harness({});
    expect(runPrompterExportCli(args, test.io)).toBe(PROMPTER_EXPORT_EXIT.usage);
    expect(test.writes.size).toBe(0);
  });

  it("runs the real CLI twice with byte-identical outputs matching the goldens", () => {
    const directory = mkdtempSync(join(tmpdir(), "vera-prompter-cli-"));
    for (const run of [1, 2]) {
      const result = cli([inputPath, "--text", join(directory, `${run}.txt`), "--sidecar", join(directory, `${run}.json`), "--include-section-navigation", "--include-beat-numbers"]);
      expect(result.status, result.stderr).toBe(0);
      expect(result.stdout).toContain("PASS Prompter export written");
    }
    for (const [extension, golden] of [["txt", "acceptance.prompter.golden.txt"], ["json", "acceptance.sidecar.golden.json"]]) {
      const first = readFileSync(join(directory, `1.${extension}`));
      expect(first.equals(readFileSync(join(directory, `2.${extension}`)))).toBe(true);
      expect(first.equals(readFileSync(`${repositoryRoot}tests/data/issue_37/${golden}`))).toBe(true);
    }
  });

  it.each(["file", "symlink"])('refuses an existing %s output before writing either artifact', (kind) => {
    const directory = mkdtempSync(join(tmpdir(), "vera-prompter-preserve-"));
    const sidecar = join(directory, "sidecar.json");
    if (kind === "file") writeFileSync(sidecar, "keep me");
    else {
      const target = join(directory, "original.json");
      writeFileSync(target, "keep me");
      symlinkSync(target, sidecar);
    }
    const before = readFileSync(sidecar);
    const result = cli([inputPath, "--text", join(directory, "text.txt"), "--sidecar", sidecar]);
    expect(result.status).toBe(PROMPTER_EXPORT_EXIT.write);
    expect(result.stdout).not.toContain("PASS");
    expect(readFileSync(sidecar).equals(before)).toBe(true);
    expect(readdirSync(directory)).toEqual(kind === "file" ? ["sidecar.json"] : ["original.json", "sidecar.json"]);
  });

  it("reports read/parse/write failures with distinct exit codes", () => {
    const args = ["input.json", "--text", "out.txt", "--sidecar", "out.json"];
    expect(runPrompterExportCli(args, harness({}).io)).toBe(PROMPTER_EXPORT_EXIT.read);
    expect(runPrompterExportCli(args, harness({ "input.json": "bad JSON" }).io)).toBe(PROMPTER_EXPORT_EXIT.parse);
    const test = harness({ "input.json": readFileSync(inputPath, "utf8") });
    test.io.writeFile = () => { throw new Error("write failed"); };
    expect(runPrompterExportCli(args, test.io)).toBe(PROMPTER_EXPORT_EXIT.write);
    expect(test.stdout()).not.toContain("PASS");
  });

  it("writes both canonical artifacts and reports their hashes", () => {
    const test = harness({ [inputPath]: readFileSync(inputPath, "utf8") });
    const exit = runPrompterExportCli([
      inputPath,
      "--text",
      "out/prompter.txt",
      "--sidecar",
      "out/prompter.json",
      "--include-section-navigation",
      "--include-beat-numbers",
    ], test.io);

    expect(exit).toBe(PROMPTER_EXPORT_EXIT.ok);
    expect(test.stderr()).toBe("");
    expect(test.stdout()).toMatch(
      /^PASS Prompter export written\ntext=out\/prompter\.txt sha256:[a-f0-9]{64}\nsidecar=out\/prompter\.json sha256:[a-f0-9]{64}\n$/u,
    );
    expect(test.writes.get("out/prompter.txt")).toContain("(OC)\n");
    expect(test.writes.get("out/prompter.json")).toContain('"schemaVersion": "prompter-export/v1"');
  });

  it("reports stable diagnostics and performs no writes on invalid input", () => {
    const parsed = JSON.parse(readFileSync(inputPath, "utf8")) as {
      activeDraft: { blocks: Array<{ type: string; hostVisibilitySpans?: unknown[] }> };
    };
    const narration = parsed.activeDraft.blocks.find((block) => block.type === "narration")!;
    narration.hostVisibilitySpans = [];
    const test = harness({ "broken.json": JSON.stringify(parsed) });
    const exit = runPrompterExportCli([
      "broken.json",
      "--text",
      "out.txt",
      "--sidecar",
      "out.json",
    ], test.io);

    expect(exit).toBe(PROMPTER_EXPORT_EXIT.validation);
    expect(test.stdout()).toContain("HOST_VISIBILITY_GAP");
    expect(test.stderr()).toBe("");
    expect(test.writes.size).toBe(0);
  });

  it("rejects incomplete or unknown arguments without reading or writing", () => {
    const test = harness({});
    expect(runPrompterExportCli(["input.json", "--text", "out.txt"], test.io)).toBe(
      PROMPTER_EXPORT_EXIT.usage,
    );
    expect(test.stderr()).toContain("USAGE:");
    expect(test.writes.size).toBe(0);
  });
});

function cli(args: string[]) {
  return spawnSync(process.execPath, [`${repositoryRoot}packages/contracts/src/prompter-export-cli.ts`, ...args], { encoding: "utf8" });
}
