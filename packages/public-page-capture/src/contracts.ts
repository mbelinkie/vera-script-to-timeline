import { readFileSync } from "node:fs";

import {
  Ajv2020,
  type AnySchemaObject,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";

const contractDirectory = new URL("../../../contracts/", import.meta.url);

function readSchema(file: string): AnySchemaObject {
  return JSON.parse(
    readFileSync(new URL(file, contractDirectory), "utf8"),
  ) as AnySchemaObject;
}

const schemas = [
  readSchema("public-page-capture-api-v1.schema.json"),
  readSchema("public-page-capture-worker-v1.schema.json"),
  readSchema("public-page-capture-provenance-v1.schema.json"),
];
const ajv = new Ajv2020({
  allErrors: true,
  allowUnionTypes: true,
  strict: true,
});
formatsModule.default.default(ajv);
for (const schema of schemas) ajv.addSchema(schema);

function requiredValidator(id: string): ValidateFunction {
  const validator = ajv.getSchema(id);
  if (!validator) throw new Error(`Contract schema was not registered: ${id}`);
  return validator;
}

const validators = {
  api: requiredValidator(
    "https://schemas.vera.video/contracts/public-page-capture-api-v1.schema.json",
  ),
  provenance: requiredValidator(
    "https://schemas.vera.video/contracts/public-page-capture-provenance-v1.schema.json",
  ),
  worker: requiredValidator(
    "https://schemas.vera.video/contracts/public-page-capture-worker-v1.schema.json",
  ),
} as const;

export class ContractValidationError extends Error {
  override readonly name = "ContractValidationError";

  constructor(
    readonly boundary: keyof typeof validators,
    readonly fieldPaths: readonly string[],
  ) {
    super("The message does not satisfy the required capture contract.");
  }
}

function safeFieldPaths(errors: ErrorObject[] | null | undefined): string[] {
  return [...new Set((errors ?? []).map(({ instancePath }) => instancePath))].slice(
    0,
    32,
  );
}

export function validateApiMessage(value: unknown): void {
  if (!validators.api(value)) {
    throw new ContractValidationError(
      "api",
      safeFieldPaths(validators.api.errors),
    );
  }
}

export function validateWorkerMessage(value: unknown): void {
  if (!validators.worker(value)) {
    throw new ContractValidationError(
      "worker",
      safeFieldPaths(validators.worker.errors),
    );
  }
}

export function validateProvenance(value: unknown): void {
  if (!validators.provenance(value)) {
    throw new ContractValidationError(
      "provenance",
      safeFieldPaths(validators.provenance.errors),
    );
  }
}
