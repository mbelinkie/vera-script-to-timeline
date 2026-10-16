import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import { applyVisualDecisions, proposeVisuals } from "../src/issue-144-semantics.js";
import { edit, inputs } from "./issue-144-test-inputs.js";

const cli = fileURLToPath(new URL("../src/issue-144-proof-cli.ts", import.meta.url));
const roots: string[] = [];
const digest = (bytes: Buffer): string => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
function file(name: string, value: unknown): string {
  const root = mkdtempSync(join(tmpdir(), "vera144-proof-cli-")); roots.push(root);
  const path = join(root, name); writeFileSync(path, canonicalJson(value)); return path;
}
function invoke(args: string[]) { return spawnSync(process.execPath, [cli, ...args], { encoding: "utf8", timeout: 300_000 }); }
interface Envelope { schemaVersion: string; evidenceLevel: string; ok: boolean; inputs: Record<string, string>; result: unknown; sourceHashes: Record<string, string>; artifacts: Record<string, string>; artifactHashes: Record<string, string>; }
const body = (text: string): Envelope => JSON.parse(text) as Envelope;
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true }); });

describe("Issue144 proposal/decision stdout file entry", () => {
  it("uses the actual mapper with byte-bound files and deterministic replay", () => {
    const input = inputs(); edit(input, "move");
    const path = file("inputs.json", input); const before = readFileSync(path);
    const first = invoke(["propose", path]); const second = invoke(["propose", path]);
    expect(first.status).toBe(0); expect(first.stderr).toBe(""); expect(second.stdout).toBe(first.stdout);
    const receipt = body(first.stdout);
    expect(receipt).toMatchObject({ schemaVersion: "issue-144-semantic-cli/v1", evidenceLevel: "compiler_only", ok: true, inputs: { "0": digest(before) } });
    expect(receipt.result).toEqual(proposeVisuals(input));
    expect(receipt.sourceHashes["./issue-144-semantics.ts"]).toBe(digest(readFileSync(new URL("../src/issue-144-semantics.ts", import.meta.url))));
    expect(readFileSync(path)).toEqual(before);
  });

  it("applies explicit decisions through the actual canonical revision path", () => {
    const input = inputs(); edit(input, "trim");
    const report = proposeVisuals(input);
    const decisions = { schemaVersion: "issue-144-decisions/v1", reportHash: sha256CanonicalJson(report), choices: [{ proposalId: report.rows[0]!.id, decision: "accept" }] };
    const paths = [file("inputs.json", input), file("report.json", report), file("decisions.json", decisions)];
    const before = paths.map((path) => readFileSync(path));
    const result = invoke(["decide", ...paths]);
    expect(result.status).toBe(0);
    const applied = applyVisualDecisions(input, report, decisions);
    const receipt = body(result.stdout);
    expect(receipt.result).toEqual(applied);
    if (applied.status !== "revised") throw Error("expected revision");
    expect(receipt.artifacts).toEqual({ "script-document.json": canonicalJson(applied.document), "compiler-dependencies.json": canonicalJson(applied.dependencies) });
    for (const [name, text] of Object.entries(receipt.artifacts)) expect(receipt.artifactHashes[name]).toBe(digest(Buffer.from(text, "utf8")));
    expect(paths.map((path) => readFileSync(path))).toEqual(before);
  });

  it("distinguishes a semantic refusal from a process fault", () => {
    const input = inputs(); input.currentDocument.title = "stale";
    const result = invoke(["propose", file("inputs.json", input)]);
    expect(result.status).toBe(1); expect(body(result.stdout)).toMatchObject({ ok: false, result: { status: "refused" } });
  });

  it.each(["usage", "read", "parse"])("refuses %s faults without outputs", (kind) => {
    const path = file("input.json", {}); if (kind === "parse") writeFileSync(path, Buffer.from([0xef, 0xbb, 0xbf, 0x7b, 0x7d]));
    const result = invoke(kind === "usage" ? ["decide", path] : ["propose", kind === "read" ? `${path}.missing` : path]);
    expect(result.status).toBe(kind === "usage" ? 64 : kind === "read" ? 66 : 65); expect(result.stdout).toBe("");
  });
});
