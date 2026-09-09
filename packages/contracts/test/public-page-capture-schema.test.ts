import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  Ajv2020,
  type AnySchemaObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const schemaDirectory = `${repositoryRoot}contracts/`;
const exampleDirectory =
  `${repositoryRoot}tests/data/issue_39_public_page_capture/`;

const schemaFiles = [
  "public-page-capture-api-v1.schema.json",
  "public-page-capture-worker-v1.schema.json",
  "public-page-capture-provenance-v1.schema.json",
] as const;

const expectedExamples = [
  "api-create-capture.json",
  "api-request-now.json",
  "api-request-on-build.json",
  "api-ready-revision.json",
  "api-review-required-revision.json",
  "api-same-byte-revision.json",
  "api-selection-conflict.json",
  "api-sanitized-denial.json",
  "api-duplicate-recovery.json",
  "worker-lease-attempt.json",
  "worker-late-epoch-denial.json",
  "provenance-revision-observation.json",
  "provenance-terminal-denial.json",
] as const;

function parseJson(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf8")) as unknown;
}

const schemas = schemaFiles.map(
  (file) => parseJson(`${schemaDirectory}${file}`) as AnySchemaObject,
);
const ajv = new Ajv2020({
  allErrors: true,
  allowUnionTypes: true,
  strict: true,
});
formatsModule.default.default(ajv);
for (const schema of schemas) ajv.addSchema(schema);

const validators = {
  api: ajv.getSchema(
    "https://schemas.vera.video/contracts/public-page-capture-api-v1.schema.json",
  ),
  worker: ajv.getSchema(
    "https://schemas.vera.video/contracts/public-page-capture-worker-v1.schema.json",
  ),
  provenance: ajv.getSchema(
    "https://schemas.vera.video/contracts/public-page-capture-provenance-v1.schema.json",
  ),
};

function validatorFor(file: string): ValidateFunction {
  if (file.startsWith("api-")) return validators.api!;
  if (file.startsWith("worker-")) return validators.worker!;
  return validators.provenance!;
}

describe("public-page capture v1 contracts", () => {
  it("compiles the three accepted roots together", () => {
    expect(Object.values(validators).every(Boolean)).toBe(true);
  });

  it("retains the complete required fictional example inventory", () => {
    expect(readdirSync(exampleDirectory).filter((file) => file.endsWith(".json")).sort())
      .toEqual([...expectedExamples].sort());
  });

  it.each(expectedExamples)("validates %s", (file) => {
    const validate = validatorFor(file);
    const value = parseJson(`${exampleDirectory}${file}`);
    expect(validate(value), JSON.stringify(validate.errors, null, 2)).toBe(true);
  });

  it("rejects Periodic as an executable trigger", () => {
    const value = structuredClone(
      parseJson(`${exampleDirectory}api-request-now.json`),
    ) as Record<string, unknown>;
    value.trigger = { kind: "periodic", schedule: "daily" };
    expect(validators.api!(value)).toBe(false);
  });

  it("admits only versioned build snapshots for On build", () => {
    const value = structuredClone(
      parseJson(`${exampleDirectory}api-request-on-build.json`),
    ) as { trigger: { buildSnapshot: { kind: string } } };
    value.trigger.buildSnapshot.kind = "document_revision";
    expect(validators.api!(value)).toBe(false);
  });

  it("rejects unknown API and worker fields", () => {
    for (const [file, validate] of [
      ["api-request-now.json", validators.api!],
      ["worker-lease-attempt.json", validators.worker!],
    ] as const) {
      const value = structuredClone(
        parseJson(`${exampleDirectory}${file}`),
      ) as Record<string, unknown>;
      value.futureEscapeHatch = true;
      expect(validate(value)).toBe(false);
    }
  });

  it("admits the approved worker availability and commit-authorization errors", () => {
    const base = parseJson(
      `${exampleDirectory}worker-late-epoch-denial.json`,
    ) as Record<string, unknown>;
    for (const code of ["capture_worker_unavailable", "action_not_allowed"]) {
      const value = {
        ...base,
        code,
        safeMessage: "The capture operation cannot proceed.",
      };
      expect(
        validators.worker!(value),
        JSON.stringify(validators.worker!.errors, null, 2),
      ).toBe(true);
    }
  });

  it("does not admit object locators, local paths, cookies, or raw capabilities in normal API messages", () => {
    for (const forbidden of [
      { objectLocator: "s3://bucket/key" },
      { localPath: "/private/tmp/file" },
      { cookie: "session=secret" },
      { leaseCapability: "raw-secret" },
    ]) {
      const value = {
        ...(parseJson(`${exampleDirectory}api-ready-revision.json`) as object),
        ...forbidden,
      };
      expect(validators.api!(value)).toBe(false);
    }
  });

  it("rejects malformed IDs, digests, timestamps, and secret-bearing requested URLs", () => {
    const malformedId = structuredClone(
      parseJson(`${exampleDirectory}api-request-now.json`),
    ) as Record<string, unknown>;
    malformedId.projectId = "project-1";
    expect(validators.api!(malformedId)).toBe(false);

    const malformedDigest = structuredClone(
      parseJson(`${exampleDirectory}api-ready-revision.json`),
    ) as { revision: { settingsDigest: string } };
    malformedDigest.revision.settingsDigest = "sha256:ABC";
    expect(validators.api!(malformedDigest)).toBe(false);

    const malformedTime = structuredClone(
      parseJson(`${exampleDirectory}provenance-revision-observation.json`),
    ) as { timing: { serverStartedAt: string } };
    malformedTime.timing.serverStartedAt = "tomorrow";
    expect(validators.provenance!(malformedTime)).toBe(false);

    const secretUrl = structuredClone(
      parseJson(`${exampleDirectory}api-create-capture.json`),
    ) as { requestedUrl: string };
    secretUrl.requestedUrl = "https://capture.example.org/?token=not-allowed";
    expect(validators.api!(secretUrl)).toBe(false);

    const userInfoUrl = structuredClone(
      parseJson(`${exampleDirectory}api-create-capture.json`),
    ) as { requestedUrl: string };
    userInfoUrl.requestedUrl = "https://user:password@capture.example.org/";
    expect(validators.api!(userInfoUrl)).toBe(false);
  });
});
