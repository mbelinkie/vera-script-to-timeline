import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  Ajv2020,
  type AnySchemaObject,
  type ErrorObject,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import {
  validBuildReport,
  validCompilerDependencies,
  validScriptDocument,
  validTimelineManifest,
} from "./samples.js";
import type { NarrationDependency } from "../src/generated/contracts.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const schemaPaths = [
  "contracts/script-document-v1.schema.json",
  "contracts/timeline-manifest-v1.schema.json",
  "contracts/build-report-v1.schema.json",
  "contracts/compiler-dependencies-v1.schema.json",
] as const;

const schemas: AnySchemaObject[] = schemaPaths.map((relativePath) => {
  const parsed: unknown = JSON.parse(
    readFileSync(`${repositoryRoot}${relativePath}`, "utf8"),
  );
  return parsed as AnySchemaObject;
});
const timelineManifestSchema = schemas[1]!;

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
for (const schema of schemas) {
  ajv.addSchema(schema);
}

const validators = {
  script: ajv.getSchema("https://schemas.vera.video/contracts/script-document-v1.schema.json"),
  manifest: ajv.getSchema("https://schemas.vera.video/contracts/timeline-manifest-v1.schema.json"),
  report: ajv.getSchema("https://schemas.vera.video/contracts/build-report-v1.schema.json"),
  dependencies: ajv.getSchema(
    "https://schemas.vera.video/contracts/compiler-dependencies-v1.schema.json",
  ),
};

function expectInvalid(
  validate: NonNullable<(typeof validators)[keyof typeof validators]>,
  value: unknown,
  expected: Pick<ErrorObject, "keyword" | "instancePath">,
): void {
  expect(validate(value)).toBe(false);
  expect(validate.errors).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        keyword: expected.keyword,
        instancePath: expected.instancePath,
      }),
    ]),
  );
}

describe("contract schemas", () => {
  it("compile together with external references resolved", () => {
    expect(Object.values(validators).every(Boolean)).toBe(true);
  });

  it.each([
    ["ScriptDocument", validators.script, validScriptDocument],
    ["TimelineManifest", validators.manifest, validTimelineManifest],
    ["BuildReport", validators.report, validBuildReport],
    ["CompilerDependencies", validators.dependencies, validCompilerDependencies],
  ])("accepts a representative %s v1 instance", (_name, validate, value) => {
    expect(validate?.(value), JSON.stringify(validate?.errors, null, 2)).toBe(
      true,
    );
  });

  it("rejects unknown ScriptDocument properties", () => {
    expectInvalid(
      validators.script!,
      { ...validScriptDocument, compilerHint: "do not accept me" },
      { keyword: "additionalProperties", instancePath: "" },
    );
  });

  it("rejects malformed canonical hashes", () => {
    expectInvalid(
      validators.script!,
      { ...validScriptDocument, liveContentHash: "abc123" },
      { keyword: "pattern", instancePath: "/liveContentHash" },
    );
  });

  it("rejects malformed entity identities", () => {
    expectInvalid(
      validators.manifest!,
      { ...validTimelineManifest, id: "manifest-1" },
      { keyword: "format", instancePath: "/id" },
    );
  });

  it("rejects later-phase visual source discriminators", () => {
    const invalid = structuredClone(validScriptDocument);
    const narration = invalid.activeDraft.blocks.find(
      (block) => block.type === "narration",
    );
    expect(narration?.type).toBe("narration");
    Reflect.set(
      narration!.visualEvents[0]!.source,
      "kind",
      "stock_provider",
    );
    expectInvalid(validators.script!, invalid, {
      keyword: "oneOf",
      instancePath: "/activeDraft/blocks/1/visualEvents/0/source",
    });
  });

  it("rejects zero-duration manifest events", () => {
    const invalid = structuredClone(validTimelineManifest);
    Reflect.set(invalid.events[0]!.recordRange, "durationFrames", 0);
    expectInvalid(validators.manifest!, invalid, {
      keyword: "minimum",
      instancePath: "/events/0/recordRange/durationFrames",
    });
  });

  it("expresses event target-track compatibility through structural kind", () => {
    const invalid = structuredClone(validTimelineManifest);
    Reflect.set(invalid.events[2]!, "trackKind", "video");
    expectInvalid(validators.manifest!, invalid, {
      keyword: "const",
      instancePath: "/events/2/trackKind",
    });
  });

  it("accepts bounded opaque track IDs and positive indices above the examples", () => {
    const manifest = structuredClone(validTimelineManifest);
    manifest.tracks[0].id = "opaque-track-id-without-a-kind-prefix";
    manifest.tracks[0].index = 101;
    manifest.tracks[5]!.index = 42;
    manifest.tracks[10]!.index = 7;
    manifest.events[0]!.trackId = manifest.tracks[0].id;
    expect(
      validators.manifest?.(manifest),
      JSON.stringify(validators.manifest?.errors, null, 2),
    ).toBe(true);
  });

  it("rejects overlong track IDs", () => {
    const invalid = structuredClone(validTimelineManifest);
    invalid.tracks[0].id = "x".repeat(129);
    expectInvalid(validators.manifest!, invalid, {
      keyword: "maxLength",
      instancePath: "/tracks/0/id",
    });
  });

  it("rejects empty track IDs and non-positive indices", () => {
    const emptyId = structuredClone(validTimelineManifest);
    emptyId.tracks[0].id = "";
    expectInvalid(validators.manifest!, emptyId, {
      keyword: "minLength",
      instancePath: "/tracks/0/id",
    });

    const zeroIndex = structuredClone(validTimelineManifest);
    zeroIndex.tracks[10]!.index = 0;
    expectInvalid(validators.manifest!, zeroIndex, {
      keyword: "minimum",
      instancePath: "/tracks/10/index",
    });
  });

  it("keeps visual layer indices positive without a five-layer ceiling", () => {
    const document = structuredClone(validScriptDocument);
    const narration = document.activeDraft.blocks.find(
      (block) => block.type === "narration",
    );
    expect(narration?.type).toBe("narration");
    narration!.visualEvents[0]!.layer = 99;
    expect(
      validators.script?.(document),
      JSON.stringify(validators.script?.errors, null, 2),
    ).toBe(true);
  });

  it("publishes D-0004 values as defaults while accepting alternate settings", () => {
    const timelineSettings = (
      timelineManifestSchema.$defs as Record<string, AnySchemaObject>
    ).TimelineSettings!;
    const properties = timelineSettings.properties as Record<
      string,
      AnySchemaObject
    >;
    const timelineFrameRate = (
      timelineManifestSchema.$defs as Record<string, AnySchemaObject>
    ).TimelineFrameRate!;
    expect(properties.frameRate?.$ref).toBe("#/$defs/TimelineFrameRate");
    expect(timelineFrameRate.default).toEqual({
      numerator: 24000,
      denominator: 1001,
    });
    expect(properties.width?.default).toBe(1920);
    expect(properties.height?.default).toBe(1080);
    expect(properties.audioSampleRate?.default).toBe(48000);

    const alternate = structuredClone(validTimelineManifest);
    alternate.timeline = {
      ...alternate.timeline,
      frameRate: { numerator: 25, denominator: 1 },
      width: 3840,
      height: 2160,
      audioSampleRate: 96000,
    };
    expect(
      validators.manifest?.(alternate),
      JSON.stringify(validators.manifest?.errors, null, 2),
    ).toBe(true);
  });

  it("rejects BuildReport event results with an unknown disposition", () => {
    const invalid = structuredClone(validBuildReport);
    Reflect.set(invalid.eventResults[0]!, "disposition", "silently_dropped");
    expectInvalid(validators.report!, invalid, {
      keyword: "enum",
      instancePath: "/eventResults/0/disposition",
    });
  });

  it("accepts all approved honest compiled timing-precision labels", () => {
    const manifest = structuredClone(validTimelineManifest);
    Reflect.set(
      manifest.events[0]!,
      "timingPrecision",
      "word_start_with_derived_end",
    );
    Reflect.set(
      manifest.events[1]!,
      "timingPrecision",
      "sentence_start_with_derived_end",
    );
    Reflect.set(manifest.events[2]!, "timingPrecision", "unavailable");
    expect(
      validators.manifest?.(manifest),
      JSON.stringify(validators.manifest?.errors, null, 2),
    ).toBe(true);
  });

  it("requires a failure reason only for failed narration dependencies", () => {
    const failed = structuredClone(validCompilerDependencies);
    failed.narration[0]!.status = "failed";
    expectInvalid(validators.dependencies!, failed, {
      keyword: "required",
      instancePath: "/narration/0",
    });

    const readyWithFailure = structuredClone(validCompilerDependencies);
    Reflect.set(readyWithFailure.narration[0]!, "failureReason", "provider down");
    expectInvalid(validators.dependencies!, readyWithFailure, {
      keyword: "not",
      instancePath: "/narration/0",
    });
  });

  it("accepts the serialized Python adapter boundary fixture", () => {
    const boundary = JSON.parse(
      readFileSync(
        `${repositoryRoot}tests/data/slice_1_3/python-adapter.ready-narration-dependency.json`,
        "utf8",
      ),
    ) as unknown;
    const dependencies = structuredClone(validCompilerDependencies);
    dependencies.narration = [boundary as NarrationDependency];
    expect(
      validators.dependencies?.(dependencies),
      JSON.stringify(validators.dependencies?.errors, null, 2),
    ).toBe(true);
  });

  it("enforces resolved-video and resolved-still field shapes", () => {
    const videoWithoutStart = structuredClone(validCompilerDependencies);
    Reflect.deleteProperty(videoWithoutStart.resolvedVisuals[0]!, "sourceStartFrame");
    expectInvalid(validators.dependencies!, videoWithoutStart, {
      keyword: "required",
      instancePath: "/resolvedVisuals/0",
    });

    const stillWithVideoFields = structuredClone(validCompilerDependencies);
    stillWithVideoFields.resolvedVisuals[0]!.source =
      validTimelineManifest.sources.find((source) => source.kind === "still")!;
    expectInvalid(validators.dependencies!, stillWithVideoFields, {
      keyword: "not",
      instancePath: "/resolvedVisuals/0",
    });
  });

  it("rejects structurally invalid timing-mark ranges", () => {
    const invalid = structuredClone(validCompilerDependencies);
    invalid.narration[0]!.timing.marks[0]!.endUtf16 = 0;
    expectInvalid(validators.dependencies!, invalid, {
      keyword: "minimum",
      instancePath: "/narration/0/timing/marks/0/endUtf16",
    });
  });
});
