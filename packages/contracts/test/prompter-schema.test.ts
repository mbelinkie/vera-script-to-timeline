import { readFileSync } from "node:fs";
import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

import scriptSchema from "../../../contracts/script-document-v1.schema.json" with { type: "json" };
import prompterSchema from "../../../contracts/prompter-export-v1.schema.json" with { type: "json" };
import { validateScriptDocument } from "../src/script-validator.js";

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(scriptSchema);
const validateSidecar = ajv.compile(prompterSchema);
const data = new URL("../../../tests/data/issue_37/", import.meta.url);

describe("issue 37 additive schemas", () => {
  it("accepts the fictional document and independently validates its sidecar", () => {
    const document: unknown = JSON.parse(readFileSync(new URL("acceptance.script-document.json", data), "utf8"));
    const sidecar: unknown = JSON.parse(readFileSync(new URL("acceptance.sidecar.golden.json", data), "utf8"));
    expect(validateScriptDocument(document)).toEqual({ valid: true, diagnostics: [] });
    expect(validateSidecar(sidecar), JSON.stringify(validateSidecar.errors)).toBe(true);
  });

  it.each([
    ["kind", "ssml"], ["includeInPrompter", "true"], ["version", 0],
    ["value", ""], ["id", "bad-id"], ["provider", "engine"],
  ])("rejects invalid annotation %s", (key, value) => {
    const document = JSON.parse(readFileSync(new URL("acceptance.script-document.json", data), "utf8")) as {
      activeDraft: { blocks: Array<{ annotations?: Record<string, unknown>[] }> };
    };
    document.activeDraft.blocks[1]!.annotations![0]![key] = value;
    expect(validateScriptDocument(document).valid).toBe(false);
  });

  it("requires explicit annotation inclusion without mutating missing defaults", () => {
    const document = JSON.parse(readFileSync(new URL("acceptance.script-document.json", data), "utf8")) as {
      activeDraft: { blocks: Array<{ annotations?: Record<string, unknown>[] }> };
    };
    delete document.activeDraft.blocks[1]!.annotations![0]!.includeInPrompter;
    const before = JSON.stringify(document);
    expect(validateScriptDocument(document).valid).toBe(false);
    expect(JSON.stringify(document)).toBe(before);
  });

  it.each([
    ["textSha256", "sha256:bad"], ["schemaVersion", "prompter-export/v2"],
    ["provider", "engine"], ["settings", { includeBeatNumbers: true }],
  ])("rejects invalid sidecar %s", (key, value) => {
    const sidecar = JSON.parse(readFileSync(new URL("acceptance.sidecar.golden.json", data), "utf8")) as Record<string, unknown>;
    sidecar[key] = value;
    expect(validateSidecar(sidecar)).toBe(false);
  });
});
