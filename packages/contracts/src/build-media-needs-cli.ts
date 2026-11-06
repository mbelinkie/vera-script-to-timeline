// Pure, pinned media-needs bridge. No final compilation or invented bindings.
// Unlike the #190 compile bridge, this can run BEFORE media preparation.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";

try {
  if (process.version !== "v24.19.0") throw new Error("pinned Node v24.19.0 required");
  if (process.argv.length !== 4) throw new Error("expected frozen document and dependencies paths");
  const directory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    return nextResolve(context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? specifier.slice(0, -3) + ".ts" : specifier, context);
  } });
  const { resolveMediaRequirementsV2 } = await import("./compiler-core-v2.ts");
  const { canonicalJson } = await import("./compiler-core.ts");
  hooks.deregister();
  const raw = process.argv.slice(2).map((path) => readFileSync(path));
  const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
  const document: unknown = JSON.parse(decoder.decode(raw[0]));
  const dependencies: unknown = JSON.parse(decoder.decode(raw[1]));
  if (dependencies === null || typeof dependencies !== "object" || Array.isArray(dependencies)) throw new Error("dependencies must be an object");
  const d = dependencies as import("./generated/contracts-v2.js").CompilerDependenciesV2;
  if (d.schemaVersion !== "compiler-dependencies/v2" || !Array.isArray(d.narrationTimingMaps) ||
      !Array.isArray(d.occurrenceResolutions) || !d.authoringDefaults || !d.timeline?.frameRate)
    throw new Error("invalid frozen media-needs dependencies");
  const needs = resolveMediaRequirementsV2(document, {
    timing: d.narrationTimingMaps,
    boundaryEvidence: d.narrationBoundaryEvidence ?? [],
    defaults: d.authoringDefaults,
    sourceDescriptors: d.occurrenceResolutions,
    frameRate: d.timeline.frameRate,
  });
  process.stdout.write(canonicalJson({
    schemaVersion: "vera-build-media-needs/v1", runtime: process.version,
    inputs: raw.map((bytes) => `sha256:${createHash("sha256").update(bytes).digest("hex")}`), needs,
  }));
  process.exitCode = needs.ok ? 0 : 1;
} catch (error: unknown) {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 2;
}
