import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import schema from "../../../contracts/spotlight-evidence-v1.schema.json" with { type: "json" };

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
const validate = ajv.compile(schema);
const digest = `sha256:${"a".repeat(64)}`;

function attempt() {
  return {
    schemaVersion: "spotlight-evidence/v1",
    recordType: "ocr_attempt_evidence",
    recordId: "11111111-1111-4111-8111-111111111111",
    projectId: "22222222-2222-4222-8222-222222222222",
    createdAt: "2026-09-09T12:00:00.000Z",
    payloadDigest: digest,
    captureRevisionId: "33333333-3333-4333-8333-333333333333",
    rasterDigest: digest,
    profileDigest: digest,
    outcome: "succeeded",
  };
}

describe("Spotlight evidence v1 shared contract", () => {
  it("accepts a complete fictional immutable attempt", () => {
    expect(validate(attempt()), JSON.stringify(validate.errors)).toBe(true);
  });

  it("rejects unknown fields and unapproved record variants", () => {
    const withUnknown = { ...attempt(), unexpected: true };
    expect(validate(withUnknown)).toBe(false);
    const unknownVariant = { ...attempt(), recordType: "automatic_confirmation" };
    expect(validate(unknownVariant)).toBe(false);
  });
});
