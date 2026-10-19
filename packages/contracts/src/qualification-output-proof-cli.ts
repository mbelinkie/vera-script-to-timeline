// Pure subprocess bridge. The Python host authenticates complete #214 output
// evidence and current inputs before calling this CLI; this process grants no authority.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import type { QualificationOutputPureRequestV1 } from "./qualification-output-proposals-v2.js";

try {
  if (process.version !== "v24.19.0" || process.argv.length !== 3) throw new Error("locked Node and one request path required");
  const directory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    return context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? nextResolve(specifier.slice(0, -3) + ".ts", context)
      : nextResolve(specifier, context);
  } });
  const bridge = await import("./qualification-output-proposals-v2.ts");
  const { canonicalJson } = await import("./compiler-core.ts");
  hooks.deregister();

  const raw = readFileSync(process.argv[2] === "-" ? 0 : process.argv[2]!);
  const request: QualificationOutputPureRequestV1 = bridge.parseQualificationOutputPureRequest(raw);
  const result = bridge.runQualificationOutputPureRequest(request);
  process.stdout.write(canonicalJson({
    schemaVersion: "qualification-output-pure-result/v1",
    runtime: process.version,
    inputHash: `sha256:${createHash("sha256").update(raw).digest("hex")}`,
    result,
  }));
} catch (error: unknown) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 2;
}
