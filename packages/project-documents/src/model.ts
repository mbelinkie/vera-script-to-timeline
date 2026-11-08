import { createHash } from "node:crypto";

import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import {
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
} from "@vera/contracts/authoring-v2";
import type { AuthoringProjectSettingsV1, ScriptDocumentV2 } from "@vera/contracts/v2";
import settingsSchema from "../../../contracts/authoring-project-settings-v1.schema.json" with { type: "json" };

export type ErrorCode = "invalid_request" | "not_found" | "version_conflict" |
  "idempotency_conflict" | "already_exists" | "service_unavailable";

export class ProjectDocumentError extends Error {
  override readonly name = "ProjectDocumentError";
  constructor(
    readonly code: ErrorCode,
    readonly status: 400 | 404 | 409 | 503,
    readonly metadata?: Readonly<Record<string, string | number>>,
  ) { super(code); }
}

export class ProjectDocumentInputError extends ProjectDocumentError {
  constructor(message = "Invalid project document request.") {
    super("invalid_request", 400);
    this.message = message;
  }
}

const UUID = /^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$/u;
export function requireUuid(value: unknown): string {
  if (typeof value !== "string" || !UUID.test(value)) throw new ProjectDocumentInputError("Expected a UUID.");
  return value.toLowerCase();
}

export function requireTitle(value: unknown): string {
  if (typeof value !== "string" || value.trim() !== value || value.length < 1 ||
      value.length > 300 || !value.trim()) {
    throw new ProjectDocumentInputError("Expected a nonblank title of at most 300 characters.");
  }
  return value;
}

export function requireRevision(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new ProjectDocumentInputError("Expected a non-negative safe integer revision.");
  }
  return value;
}

/** Bound history pages before querying or returning untrusted stored snapshots. */
export function requireHistoryLimit(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1 || value > 100) {
    throw new ProjectDocumentInputError("History page limit must be an integer from 1 to 100.");
  }
  return value;
}

export function requireObject(value: unknown): Record<string, unknown> {
  if (!value || Array.isArray(value) || typeof value !== "object") {
    throw new ProjectDocumentInputError();
  }
  return value as Record<string, unknown>;
}

/** The stored SHA-256 covers the exact UTF-8 text kept in the head/revision. */
export function sha256(text: string): string {
  return "sha256:" + createHash("sha256").update(text).digest("hex");
}

/** Fingerprint request semantics independent of JSON object insertion order. */
export function fingerprint(value: unknown): string {
  const canonical = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(canonical);
    if (v && typeof v === "object") {
      // Code-unit order is locale independent across API hosts and restarts.
      return Object.fromEntries(Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
        .map(([key, item]) => [key, canonical(item)]));
    }
    return v;
  };
  return sha256(JSON.stringify(canonical(value)));
}

export function checkedDocument(
  input: unknown, projectId: string, expectedDocumentId?: string,
): { document: ScriptDocumentV2; documentJson: string; digest: string } {
  const id = requireUuid(projectId);
  let documentJson: string;
  try {
    documentJson = serializeAuthoringDocumentV2(input as ScriptDocumentV2);
  } catch {
    throw new ProjectDocumentInputError("Invalid typed authoring document.");
  }
  const decoded = deserializeAuthoringDocumentV2(documentJson);
  if (!decoded.ok || requireUuid(decoded.document.projectId) !== id ||
      (expectedDocumentId !== undefined && requireUuid(decoded.document.id) !== requireUuid(expectedDocumentId))) {
    throw new ProjectDocumentInputError("Document identity or saved structure does not match the project.");
  }
  return { document: decoded.document, documentJson, digest: sha256(documentJson) };
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
const validSettings = ajv.compile<AuthoringProjectSettingsV1>(settingsSchema);

/** settingsHash is caller-supplied contract data, NOT a server storage digest or permission proof. */
export function checkedSettings(
  input: unknown, projectId: string, expectedSettingsId?: string,
): { settings: AuthoringProjectSettingsV1; settingsJson: string; digest: string } {
  if (!validSettings(input)) throw new ProjectDocumentInputError("Invalid authoring project settings.");
  if (requireUuid(input.projectId) !== requireUuid(projectId) ||
      (expectedSettingsId !== undefined && requireUuid(input.id) !== requireUuid(expectedSettingsId))) {
    throw new ProjectDocumentInputError("Settings identity does not match the project.");
  }
  const settingsJson = JSON.stringify(input);
  return { settings: input, settingsJson, digest: sha256(settingsJson) };
}
