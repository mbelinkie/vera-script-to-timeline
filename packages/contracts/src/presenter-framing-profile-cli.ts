#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";

const directory = new URL("./", import.meta.url).href;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    return nextResolve(context.parentURL?.startsWith(directory) && specifier.startsWith("./") && specifier.endsWith(".js")
      ? `${specifier.slice(0, -3)}.ts` : specifier, context);
  },
});
const framing = await import("./presenter-framing.ts");
const { canonicalJson } = await import("./compiler-core.ts");
hooks.deregister();

try {
  const input: unknown = JSON.parse(readFileSync(0, "utf8"));
  if (input === null || typeof input !== "object" || Array.isArray(input)
    || Object.keys(input).sort().join(" ") !== "calibration id prior") throw new Error("Expected calibration, id and prior fields.");
  const fields = input as Record<string, unknown>;
  if (typeof fields.id !== "string") throw new Error("Profile id must be a UUID.");
  const prior = fields.prior === null ? null : framing.validatePresenterFramingProfile(fields.prior);
  const profile = framing.snapshotPresenterFramingCalibration(fields.calibration, prior, fields.id);
  process.stdout.write(canonicalJson({ profile, profileContentJson: framing.presenterFramingProfileContentJson(profile) }));
} catch (error: unknown) {
  process.stderr.write(`Presenter calibration snapshot refused: ${error instanceof Error ? error.message : "invalid input"}\n`);
  process.exitCode = 1;
}
