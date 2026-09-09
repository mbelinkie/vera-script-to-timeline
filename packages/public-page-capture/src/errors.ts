import { randomUUID } from "node:crypto";

import type { ApiError, WorkerError } from "@vera/contracts";

import { CaptureDenied } from "./policy.js";

export type CaptureErrorCode = ApiError["code"] | WorkerError["code"];

const statusByCode: Readonly<Record<string, number>> = {
  request_invalid: 400,
  authentication_required: 401,
  action_not_allowed: 403,
  resource_not_found: 404,
  version_conflict: 409,
  idempotency_key_reused: 409,
  selection_conflict: 409,
  revision_requires_review: 409,
  job_not_committable: 409,
  invalid_or_expired_job_capability: 401,
  capture_resource_limit: 413,
  capture_request_denied: 422,
  authorization_unavailable: 503,
  capture_worker_unavailable: 503,
  object_verification_unavailable: 503,
};

export class CaptureServiceError extends Error {
  override readonly name = "CaptureServiceError";
  readonly status: number;

  constructor(
    readonly code: CaptureErrorCode,
    readonly safeMessage: string,
    readonly retryable = false,
    readonly fieldPaths: readonly string[] = [],
    readonly denialFingerprint?: string,
  ) {
    super(safeMessage);
    this.status = statusByCode[code] ?? 500;
  }
}

function contractFieldPaths(fieldPaths: readonly string[]): string[] {
  return [
    ...new Set(
      fieldPaths.map((path) => {
        if (path === "") return path;
        const firstSegment = path.split("/", 2)[1];
        return firstSegment && /^(?:[A-Za-z0-9_~-]|~[01])*$/u.test(firstSegment)
          ? `/${firstSegment}`
          : "";
      }),
    ),
  ].slice(0, 32);
}

export function sanitizedDenial(
  denial: CaptureDenied,
  denialFingerprint: string,
): CaptureServiceError {
  return new CaptureServiceError(
    denial.code === "response_too_large"
      ? "capture_resource_limit"
      : "capture_request_denied",
    denial.safeMessage,
    false,
    ["/requestedUrl"],
    denialFingerprint,
  );
}

export function apiError(
  error: CaptureServiceError,
  requestId: string = randomUUID(),
): ApiError {
  return {
    schemaVersion: "public-page-capture-api/v1",
    messageType: "error",
    requestId,
    code: error.code as ApiError["code"],
    safeMessage: error.safeMessage,
    retryable: error.retryable,
    fieldPaths: contractFieldPaths(error.fieldPaths),
    ...(error.denialFingerprint
      ? { denialFingerprint: error.denialFingerprint }
      : {}),
  };
}

export function workerError(
  error: CaptureServiceError,
  requestId: string = randomUUID(),
): WorkerError {
  return {
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "worker_error",
    requestId,
    code: error.code as WorkerError["code"],
    safeMessage: error.safeMessage,
    retryable: error.retryable,
    fieldPaths: contractFieldPaths(error.fieldPaths),
  };
}

export function asCaptureServiceError(error: unknown): CaptureServiceError {
  if (error instanceof CaptureServiceError) return error;
  if (error instanceof CaptureDenied) {
    return new CaptureServiceError(
      "capture_request_denied",
      error.safeMessage,
      false,
      ["/requestedUrl"],
    );
  }
  return new CaptureServiceError(
    "object_verification_unavailable",
    "A required capture safety component could not verify the operation.",
    true,
  );
}
