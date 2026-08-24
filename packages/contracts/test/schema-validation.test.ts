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
  validScriptDocument,
  validTimelineManifest,
} from "./samples.js";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const schemaPaths = [
  "contracts/script-document-v1.schema.json",
  "contracts/timeline-manifest-v1.schema.json",
  "contracts/build-report-v1.schema.json",
] as const;

const schemas: AnySchemaObject[] = schemaPaths.map((relativePath) => {
  const parsed: unknown = JSON.parse(
    readFileSync(`${repositoryRoot}${relativePath}`, "utf8"),
  );
  return parsed as AnySchemaObject;
});

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
for (const schema of schemas) {
  ajv.addSchema(schema);
}

const validators = {
  script: ajv.getSchema("https://schemas.vera.video/contracts/script-document-v1.schema.json"),
  manifest: ajv.getSchema("https://schemas.vera.video/contracts/timeline-manifest-v1.schema.json"),
  report: ajv.getSchema("https://schemas.vera.video/contracts/build-report-v1.schema.json"),
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

  it("rejects audio placements on picture tracks", () => {
    const invalid = structuredClone(validTimelineManifest);
    Reflect.set(invalid.events[2]!, "trackId", "V1");
    expectInvalid(validators.manifest!, invalid, {
      keyword: "enum",
      instancePath: "/events/2/trackId",
    });
  });

  it("rejects BuildReport event results with an unknown disposition", () => {
    const invalid = structuredClone(validBuildReport);
    Reflect.set(invalid.eventResults[0]!, "disposition", "silently_dropped");
    expectInvalid(validators.report!, invalid, {
      keyword: "enum",
      instancePath: "/eventResults/0/disposition",
    });
  });
});
