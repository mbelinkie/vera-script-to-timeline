// Pure v2 proof bridge. The Python host strictly parses and pins input bytes.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";

try {
  if (process.version !== "v24.19.0") throw new Error("pinned Node v24.19.0 required");
  if (process.argv.length !== 4) throw new Error("expected document and dependencies paths");
  const directory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    return nextResolve(context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? specifier.slice(0, -3) + ".ts" : specifier, context);
  } });
  const compiler = await import("./compiler-core-v2.ts");
  const { canonicalJson } = await import("./compiler-core.ts");
  hooks.deregister();
  const raw = process.argv.slice(2).map((path) => readFileSync(path));
  const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
  const document: unknown = JSON.parse(decoder.decode(raw[0]));
  const dependencies: unknown = JSON.parse(decoder.decode(raw[1]));
  const result = compiler.compileTimelineV2(document, dependencies);
  // Access dependency fields only after the accepted strict compiler validation.
  const needs = result.ok ? (() => {
    const value = dependencies as import("./generated/contracts-v2.js").CompilerDependenciesV2;
    return compiler.resolveMediaRequirementsV2(document, {
      timing: value.narrationTimingMaps,
      boundaryEvidence: value.narrationBoundaryEvidence ?? [],
      defaults: value.authoringDefaults,
      sourceDescriptors: value.occurrenceResolutions,
      frameRate: value.timeline.frameRate,
    });
  })() : null;
  const envelope = {
    schemaVersion: "issue-190-v2-compile/v1", runtime: process.version,
    inputs: raw.map((bytes) => `sha256:${createHash("sha256").update(bytes).digest("hex")}`),
    result, needs,
  };
  process.stdout.write(canonicalJson(envelope));
  process.exitCode = result.ok && needs?.ok ? 0 : 1;
} catch (error: unknown) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 2;
}
