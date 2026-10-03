#!/usr/bin/env node

// Issue-owned compiler boundary. This is not a Studio build/observation receipt.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";

const hash = (bytes: Uint8Array): string => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
const compilerUrl = new URL("./compiler-core.ts", import.meta.url).href;
const codeFiles = [
  "./issue-144-compile-cli.ts",
  "./compiler-core.ts",
  "./script-validator.ts",
  "./generated/contracts.ts",
  "../../../contracts/script-document-v1.schema.json",
  "../../../contracts/compiler-dependencies-v1.schema.json",
  "../../../contracts/timeline-manifest-v1.schema.json",
  "../../../contracts/build-report-v1.schema.json",
  "../../../package-lock.json",
] as const;

function codeHashes(): Record<string, string> {
  return Object.fromEntries(codeFiles.map((path) => [path, hash(readFileSync(new URL(path, import.meta.url)))]));
}

async function main(args: string[]): Promise<number> {
  if (args.length !== 2) {
    process.stderr.write("USAGE: node packages/contracts/src/issue-144-compile-cli.ts <script-document.json> <compiler-dependencies.json>\n");
    return 64;
  }
  if (process.version !== "v24.19.0") {
    process.stderr.write("RUNTIME_ERROR: Issue 144 requires pinned Node v24.19.0.\n");
    return 69;
  }
  let scriptBytes: Buffer;
  let dependenciesBytes: Buffer;
  try {
    scriptBytes = readFileSync(args[0]!);
    dependenciesBytes = readFileSync(args[1]!);
  } catch (error: unknown) {
    process.stderr.write(`READ_ERROR: ${message(error)}\n`);
    return 66;
  }
  let document: unknown;
  let dependencies: unknown;
  try {
    const decoder = new TextDecoder("utf-8", { fatal: true });
    document = JSON.parse(decoder.decode(scriptBytes)) as unknown;
    dependencies = JSON.parse(decoder.decode(dependenciesBytes)) as unknown;
  } catch (error: unknown) {
    process.stderr.write(`PARSE_ERROR: ${message(error)}\n`);
    return 65;
  }

  const beforeCode = codeHashes();
  // Native TS execution needs this one .js specifier resolved to its accepted
  // source. Scope it to the compiler's import; remove the hook after loading.
  const hooks = registerHooks({
    resolve(specifier, context, nextResolve) {
      return nextResolve(context.parentURL === compilerUrl && specifier === "./script-validator.js"
        ? "./script-validator.ts" : specifier, context);
    },
  });
  let compiler: typeof import("./compiler-core.ts");
  try {
    compiler = await import("./compiler-core.ts");
  } finally {
    hooks.deregister();
  }
  const result = compiler.compileTimeline(document, dependencies);
  const inputs = { scriptSha256: hash(scriptBytes), dependenciesSha256: hash(dependenciesBytes) };
  if (hash(readFileSync(args[0]!)) !== inputs.scriptSha256
    || hash(readFileSync(args[1]!)) !== inputs.dependenciesSha256
    || compiler.canonicalJson(codeHashes()) !== compiler.canonicalJson(beforeCode)) {
    process.stderr.write("INPUT_CHANGED: Inputs or compiler code changed during compilation.\n");
    return 1;
  }
  const envelope = {
    schemaVersion: "issue-144-compile/v1",
    evidenceLevel: "compiler_only",
    runtime: process.version,
    inputs,
    codeHashes: beforeCode,
    ...(result.ok
      ? { ok: true, manifestJson: result.manifestJson, reportJson: result.reportJson }
      : { ok: false, diagnostics: result.diagnostics }),
  };
  process.stdout.write(compiler.canonicalJson(envelope));
  return result.ok ? 0 : 1;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error: unknown) {
  process.stderr.write(`INTERNAL_ERROR: ${message(error)}\n`);
  process.exitCode = 70;
}
