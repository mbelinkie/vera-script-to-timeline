import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

const fixture = (name: string): string => fileURLToPath(new URL(`../../../tests/data/${name}`, import.meta.url));
const cli = fileURLToPath(new URL("../src/issue-144-compile-cli.ts", import.meta.url));
const scriptPath = fixture("slice_1_1/minimal.script-document.json");
const dependenciesPath = fixture("slice_1_3/minimal.compiler-dependencies.json");
const temporary: string[] = [];

interface Envelope {
  schemaVersion: string;
  evidenceLevel: string;
  ok: boolean;
  inputs?: { scriptSha256: string; dependenciesSha256: string };
  sourceHashes?: Record<string, string>;
  lockfileSha256?: string;
  outputs?: { manifestSha256: string; reportSha256: string };
  manifestJson?: string;
  reportJson?: string;
  diagnostics?: { code: string }[];
}

function invoke(args: string[]) {
  return spawnSync(process.execPath, [cli, ...args], { encoding: "utf8" });
}

function fileWith(value: unknown): string {
  const root = mkdtempSync(join(tmpdir(), "vera-issue144-compile-test-"));
  temporary.push(root);
  const path = join(root, "input.json");
  writeFileSync(path, JSON.stringify(value));
  return path;
}

function body(output: string): Envelope {
  return JSON.parse(output) as Envelope;
}

const digest = (bytes: string | Buffer): string => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;

afterEach(() => {
  for (const root of temporary.splice(0)) rmSync(root, { recursive: true });
});

describe("Issue 144 compiler-only file boundary", () => {
  it("returns the actual frozen compiler bytes without modifying either input", () => {
    const scriptBefore = readFileSync(scriptPath);
    const dependenciesBefore = readFileSync(dependenciesPath);
    const result = invoke([scriptPath, dependenciesPath]);
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
    const envelope = body(result.stdout);
    expect(envelope.schemaVersion).toBe("issue-144-compile/v1");
    expect(envelope.evidenceLevel).toBe("compiler_only");
    expect(envelope.ok).toBe(true);
    expect(envelope.manifestJson).toBe(readFileSync(fixture("slice_1_3/minimal.manifest.golden.json"), "utf8"));
    expect(envelope.reportJson).toBe(readFileSync(fixture("slice_1_3/minimal.report.golden.json"), "utf8"));
    expect(envelope.inputs).toEqual({
      scriptSha256: `sha256:${createHash("sha256").update(scriptBefore).digest("hex")}`,
      dependenciesSha256: `sha256:${createHash("sha256").update(dependenciesBefore).digest("hex")}`,
    });
    expect(envelope.outputs).toEqual({
      manifestSha256: digest(envelope.manifestJson!),
      reportSha256: digest(envelope.reportJson!),
    });
    expect(envelope.sourceHashes?.["./compiler-core.ts"]).toBe(digest(readFileSync(new URL("../src/compiler-core.ts", import.meta.url))));
    expect(envelope.sourceHashes?.["../../../package-lock.json"]).toBeUndefined();
    expect(envelope.lockfileSha256).toBe(digest(readFileSync(new URL("../../../package-lock.json", import.meta.url))));
    expect(readFileSync(scriptPath)).toEqual(scriptBefore);
    expect(readFileSync(dependenciesPath)).toEqual(dependenciesBefore);
  });

  it("returns byte-identical torture outputs through the file boundary", () => {
    const result = invoke([fixture("slice_1_1/torture.script-document.json"), fixture("slice_1_3/torture.compiler-dependencies.json")]);
    expect(result.status).toBe(0);
    const envelope = body(result.stdout);
    expect(envelope.manifestJson).toBe(readFileSync(fixture("slice_1_3/torture.manifest.golden.json"), "utf8"));
    expect(envelope.reportJson).toBe(readFileSync(fixture("slice_1_3/torture.report.golden.json"), "utf8"));
  });

  it("distinguishes observed input drift from a deterministic compiler refusal", () => {
    const path = fileWith(JSON.parse(readFileSync(scriptPath, "utf8")) as unknown);
    const preload = join(temporary.at(-1)!, "change-input.mjs");
    writeFileSync(preload, `import { registerHooks } from "node:module";
import { appendFileSync } from "node:fs";
let changed = false;
registerHooks({ resolve(specifier, context, nextResolve) {
  if (!changed && specifier === "./compiler-core.ts") {
    appendFileSync(${JSON.stringify(path)}, " ");
    changed = true;
  }
  return nextResolve(specifier, context);
} });\n`);
    const result = spawnSync(process.execPath, ["--import", preload, cli, path, dependenciesPath], { encoding: "utf8" });
    expect(result.status).toBe(75);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("INPUT_CHANGED");
  });

  it("rejects a UTF-8 byte-order mark rather than disagreeing with the host", () => {
    const path = fileWith({});
    writeFileSync(path, Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), readFileSync(scriptPath)]));
    const result = invoke([path, dependenciesPath]);
    expect(result.status).toBe(65);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("PARSE_ERROR");
  });

  it("returns identical complete bytes when replayed in separate processes", () => {
    const first = invoke([scriptPath, dependenciesPath]);
    const second = invoke([scriptPath, dependenciesPath]);
    expect(first.status).toBe(0);
    expect(second.status).toBe(0);
    expect(second.stdout).toBe(first.stdout);
  });

  it("binds serialized input bytes even when compiler semantics are unchanged", () => {
    const original = invoke([scriptPath, dependenciesPath]);
    const reformatted = fileWith(JSON.parse(readFileSync(scriptPath, "utf8")) as unknown);
    const result = invoke([reformatted, dependenciesPath]);
    expect(result.status).toBe(0);
    expect(body(result.stdout).manifestJson).toBe(body(original.stdout).manifestJson);
    expect(body(result.stdout).inputs?.scriptSha256).not.toBe(body(original.stdout).inputs?.scriptSha256);
  });

  it("refuses missing arguments before reading inputs", () => {
    const result = invoke([scriptPath]);
    expect(result.status).toBe(64);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("USAGE");
  });

  it("refuses unreadable input without compiler output", () => {
    const result = invoke([`${scriptPath}.missing`, dependenciesPath]);
    expect(result.status).toBe(66);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("READ_ERROR");
  });

  it("refuses malformed JSON without compiler output", () => {
    const path = fileWith({});
    writeFileSync(path, "{bad json");
    const result = invoke([path, dependenciesPath]);
    expect(result.status).toBe(65);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("PARSE_ERROR");
  });

  it("retains actual validator diagnostics and emits no successful artifacts", () => {
    const result = invoke([fileWith({}), dependenciesPath]);
    expect(result.status).toBe(1);
    const envelope = body(result.stdout);
    expect(envelope.ok).toBe(false);
    expect(envelope.diagnostics?.length).toBeGreaterThan(0);
    expect(envelope.manifestJson).toBeUndefined();
    expect(envelope.reportJson).toBeUndefined();
  });

  it("refuses stale narration bindings through the actual compiler", () => {
    const dependencies = JSON.parse(readFileSync(dependenciesPath, "utf8")) as { narration: { textHash: string }[] };
    dependencies.narration[0]!.textHash = `sha256:${"0".repeat(64)}`;
    const result = invoke([scriptPath, fileWith(dependencies)]);
    expect(result.status).toBe(1);
    const envelope = body(result.stdout);
    expect(envelope.ok).toBe(false);
    expect(envelope.diagnostics).toContainEqual(expect.objectContaining({ code: "NARRATION_TEXT_HASH_MISMATCH" }));
    expect(envelope.manifestJson).toBeUndefined();
  });
});
