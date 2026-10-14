// Pure subprocess bridge; the Python consumer authenticates the pinned files
// before execution and again before effects. This CLI grants no authority.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import type { CompilerDependenciesV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { CompositionEvidenceV2 } from "./issue-192-v2-proposals.js";
import type { RevisionDecisionV2, RevisionRequestV2 } from "./issue-192-v2-revision-core.js";

try {
  if (process.version !== "v24.19.0" || process.argv.length !== 3) throw new Error("locked Node and one request path required");
  const directory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    return nextResolve(context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? specifier.slice(0, -3) + ".ts" : specifier, context);
  } });
  const integration = await import("./issue-192-v2-proposals.ts");
  const { canonicalJson, sha256CanonicalJson } = await import("./compiler-core.ts");
  const { compileTimelineV2 } = await import("./compiler-core-v2.ts");
  hooks.deregister();
  const raw = readFileSync(process.argv[2] === "-" ? 0 : process.argv[2]!);
  const request = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw)) as {
    document: ScriptDocumentV2; dependencies: CompilerDependenciesV2;
    evidence: CompositionEvidenceV2 | null; mode: "baseline" | "infer" | "stage" | "proposal" | "decide" | "evidence_hashes";
    preparedMedia: RevisionRequestV2["preparedMedia"]; handoff: RevisionRequestV2["handoff"];
    omissionDecisionHash: string; candidate: ReturnType<typeof integration.createInferredRevisionV2> | null;
    decision: RevisionDecisionV2 | null; history: string[];
  };
  if (canonicalJson(Object.keys(request).sort()) !== canonicalJson("document dependencies evidence mode preparedMedia handoff omissionDecisionHash candidate decision history".split(" ").sort()))
    throw new Error("unsupported request fields");
  const { document, dependencies, evidence } = request;
  const authenticatedByHost = () => { /* Pure subprocess, no receipt or native capability. */ };
  let result: unknown;
  if (request.mode === "baseline") {
    const compiled = compileTimelineV2(document, dependencies);
    if (!compiled.ok || compiled.report.status !== "ready") throw new Error("baseline compile refused");
    result = { documentHash: sha256CanonicalJson(document), dependenciesHash: sha256CanonicalJson(dependencies),
      documentJson: canonicalJson(document), manifest: compiled.manifest };
  }
  else if (!evidence) throw new Error("inference evidence required");
  else if (request.mode === "evidence_hashes") {
    const cases = Array.isArray(evidence) ? evidence : [evidence];
    result = { evidenceHash: sha256CanonicalJson(cases), caseEvidenceHashes: cases.map(sha256CanonicalJson) };
  }
  else if (request.mode === "infer") result = integration.inferCompositionV2(document, dependencies, evidence, authenticatedByHost);
  else if (request.mode === "stage") result = integration.prepareInferredRevisionV2(document, dependencies,
    integration.inferCompositionV2(document, dependencies, evidence, authenticatedByHost), request.preparedMedia, request.omissionDecisionHash);
  else if (request.mode === "proposal") result = integration.createInferredRevisionV2(document, dependencies, evidence, authenticatedByHost,
    { preparedMedia: request.preparedMedia, handoff: request.handoff }, request.omissionDecisionHash);
  else if (request.mode === "decide" && request.candidate && request.decision)
    result = integration.decideInferredRevisionV2(document, dependencies, evidence, authenticatedByHost, request.candidate, request.decision, request.history);
  else throw new Error("unsupported operation");
  process.stdout.write(canonicalJson({ schemaVersion: "issue-192-v2-pure-result/v1", runtime: process.version,
    inputHash: `sha256:${createHash("sha256").update(raw).digest("hex")}`, result }));
} catch (error: unknown) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 2;
}
