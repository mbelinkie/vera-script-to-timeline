#!/usr/bin/env node
// Issue-owned stdout boundary. The strict operator JSON gate is in the host.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import type { VisualProofInputs, VisualProposalReport } from "./issue-144-semantics.ts";
import type { CompilerDependenciesV1, ScriptDocumentV1 } from "./generated/contracts.js";
import type { AcceptedOmission } from "./issue-144-text-revision.ts";
import type { VerifiedRowHandoff } from "./issue-144-omission-build.ts";

const hash = (bytes: Uint8Array): string => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
const sources = ["./issue-144-proof-cli.ts", "./issue-144-semantics.ts", "./issue-144-text-revision.ts", "./issue-144-omission-build.ts", "./compiler-core.ts", "./script-validator.ts", "../../../contracts/script-document-v1.schema.json", "../../../contracts/compiler-dependencies-v1.schema.json", "../../../contracts/timeline-manifest-v1.schema.json", "../../../contracts/build-report-v1.schema.json"];
const sourceHashes = (): Record<string, string> => Object.fromEntries(sources.map((path) => [path, hash(readFileSync(new URL(path, import.meta.url)))]));
const lockHash = (): string => hash(readFileSync(new URL("../../../package-lock.json", import.meta.url)));
const message = (error: unknown): string => error instanceof Error ? error.message : String(error);

async function main(args: string[]): Promise<number> {
  const action = args[0]; const paths = args.slice(1);
  if (!((action === "propose" && paths.length === 1) || (action === "decide" && paths.length === 3) || (action === "revise-omission" && paths.length === 2) || (action === "finalize-omission" && paths.length === 3))) {
    process.stderr.write("USAGE: internal semantic bridge: propose <inputs> | decide <inputs> <report> <decisions> | revise-omission <script> <trusted-edit> | finalize-omission <script> <prior-dependencies> <just-verified-handoff>\n"); return 64;
  }
  if (process.version !== "v24.19.0") { process.stderr.write("RUNTIME_ERROR: pinned Node v24.19.0 required.\n"); return 69; }
  let bytes: Buffer[];
  try { bytes = paths.map((path) => readFileSync(path)); }
  catch (error: unknown) { process.stderr.write(`READ_ERROR: ${message(error)}\n`); return 66; }
  let values: unknown[];
  try {
    const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
    values = bytes.map((raw) => JSON.parse(decoder.decode(raw)) as unknown);
  } catch (error: unknown) { process.stderr.write(`PARSE_ERROR: ${message(error)}\n`); return 65; }
  const beforeSources = sourceHashes(); const beforeLock = lockHash();
  const semanticUrl = new URL("./issue-144-semantics.ts", import.meta.url).href;
  const compilerUrl = new URL("./compiler-core.ts", import.meta.url).href;
  const textUrl = new URL("./issue-144-text-revision.ts", import.meta.url).href;
  const omissionUrl = new URL("./issue-144-omission-build.ts", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    if ([semanticUrl,textUrl,omissionUrl].includes(context.parentURL??"") && specifier === "./compiler-core.js") return nextResolve("./compiler-core.ts", context);
    if ([compilerUrl,textUrl].includes(context.parentURL??"") && specifier === "./script-validator.js") return nextResolve("./script-validator.ts", context);
    if (context.parentURL === omissionUrl && specifier === "./issue-144-semantics.js") return nextResolve("./issue-144-semantics.ts", context);
    return nextResolve(specifier, context);
  } });
  let semantic: typeof import("./issue-144-semantics.ts");
  let compiler: typeof import("./compiler-core.ts");
  let text: typeof import("./issue-144-text-revision.ts");
  let omission: typeof import("./issue-144-omission-build.ts");
  try { semantic = await import("./issue-144-semantics.ts"); compiler = await import("./compiler-core.ts");text=await import("./issue-144-text-revision.ts");omission=await import("./issue-144-omission-build.ts"); }
  finally { hooks.deregister(); }
  let result: unknown; let ok: boolean; let artifacts: Record<string, string> = {};
  try {
    if (action === "propose") { const report = semantic.proposeVisuals(values[0] as VisualProofInputs); result = report; ok = report.status === "ready"; }
    else if(action==="decide") {
      const applied = semantic.applyVisualDecisions(values[0] as VisualProofInputs, values[1] as VisualProposalReport, values[2]); result = applied; ok = true;
      if (applied.status === "revised") artifacts = { "script-document.json": compiler.canonicalJson(applied.document), "compiler-dependencies.json": compiler.canonicalJson(applied.dependencies) };
    } else if(action==="revise-omission") {
      const applied=text.applyAcceptedOmission(values[0] as ScriptDocumentV1,values[1] as AcceptedOmission);ok=true;
      result={status:"prepared",regeneration:applied.regeneration};artifacts={"script-document.json":applied.documentJson};
    } else {
      const handoff=values[2] as VerifiedRowHandoff;
      if(handoff.revisedDocumentHash!==hash(bytes[0]!))throw new Error("handoff raw revised document hash differs");
      const finalized=omission.finalizeOmission(values[0] as ScriptDocumentV1,values[1] as CompilerDependenciesV1,handoff);ok=true;
      result={status:"finalized",generationHash:compiler.sha256CanonicalJson(handoff),buildId:finalized.dependencies.build.buildId};
      artifacts={"compiler-dependencies.json":compiler.canonicalJson(finalized.dependencies),"timeline-manifest.json":compiler.canonicalJson(finalized.manifest),"build-report.json":compiler.canonicalJson(finalized.report)};
    }
  } catch (error: unknown) { result = { status: "refused", reason: message(error) }; ok = false; }
  const inputs = Object.fromEntries(bytes.map((raw, index) => [String(index), hash(raw)]));
  if (paths.some((path, index) => hash(readFileSync(path)) !== inputs[String(index)]) || compiler.canonicalJson(sourceHashes()) !== compiler.canonicalJson(beforeSources) || lockHash() !== beforeLock) {
    process.stderr.write("INPUT_CHANGED: inputs, sources or lockfile changed during semantic evaluation.\n"); return 75;
  }
  const resultJson = compiler.canonicalJson(result);
  const receipt = { schemaVersion: "issue-144-semantic-cli/v1", evidenceLevel: "compiler_only", runtime: process.version, action, inputs, sourceHashes: beforeSources, lockfileSha256: beforeLock, ok, result, resultJson, resultSha256: hash(Buffer.from(resultJson, "utf8")), artifacts, artifactHashes: Object.fromEntries(Object.entries(artifacts).map(([name, text]) => [name, hash(Buffer.from(text, "utf8"))])) };
  process.stdout.write(compiler.canonicalJson(receipt)); return ok ? 0 : 1;
}
try { process.exitCode = await main(process.argv.slice(2)); }
catch (error: unknown) { process.stderr.write(`INTERNAL_ERROR: ${message(error)}\n`); process.exitCode = 70; }
