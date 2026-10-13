// Internal pure bridge. The host strictly parses and authenticates input bytes.
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import type { ScriptDocumentV2, CompilerDependenciesV2 } from "./generated/contracts-v2.js";
import type { RowRequestV2, RowHandoffV2 } from "./issue-189-v2-replacement.js";
import type { AcceptedOmissionV2 } from "./issue-189-v2-omission.js";

try {
  if (process.version !== "v24.19.0") throw new Error("pinned Node v24.19.0 required");
  const directory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    return nextResolve(context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? specifier.slice(0, -3) + ".ts" : specifier, context);
  } });
  const replacement = await import("./issue-189-v2-replacement.ts");
  const omission = await import("./issue-189-v2-omission.ts");
  const compiler = await import("./compiler-core.ts");
  hooks.deregister();
  const input = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(0))) as {
    document: ScriptDocumentV2; request: RowRequestV2; prior: CompilerDependenciesV2; handoff: RowHandoffV2; edit: AcceptedOmissionV2;
  };
  const action = process.argv[2];
  if (action === "validate") replacement.validateRowRequestV2(input.document, input.request);
  const result = action === "validate" ? { valid: true, priorDependenciesHash: compiler.sha256CanonicalJson(input.prior) }
    : action === "inspect" ? { documentHash: compiler.sha256CanonicalJson(input.document), priorDependenciesHash: compiler.sha256CanonicalJson(input.prior), documentJson: compiler.canonicalJson(input.document) }
    : action === "finalize"
    ? replacement.finalizeReplacementV2(input.document, input.prior, input.handoff)
    : action === "omit" ? omission.applyAcceptedOmissionV2(input.document, input.edit)
    : (() => { throw new Error("unknown internal action"); })();
  process.stdout.write(compiler.canonicalJson(result));
} catch (error: unknown) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
