import { randomUUID } from "node:crypto";

import type {
  DraftOccurrenceReference,
  PrincipalRef,
  PublicPageCaptureApiV1,
  PublicPageCaptureWorkerV1,
  VersionedExternalReference,
} from "@vera/contracts";

import {
  ContractValidationError,
  validateApiMessage,
  validateWorkerMessage,
} from "./contracts.js";
import {
  apiError,
  asCaptureServiceError,
  CaptureServiceError,
  workerError,
} from "./errors.js";
import type { CaptureMutationReceipt, CaptureService } from "./service.js";

type ExternalReference = DraftOccurrenceReference | VersionedExternalReference;

export interface CaptureApiBoundary {
  authenticate(request: Request): Promise<PrincipalRef>;
  visibleReference(
    request: Request,
    projectId: string,
    revisionId: string,
  ): Promise<ExternalReference>;
}

export interface CaptureApiHandlerOptions {
  readonly boundary: CaptureApiBoundary;
  readonly service: CaptureService;
}

export interface CaptureWorkerApiBoundary {
  authenticate(request: Request): Promise<string>;
}

export interface CaptureWorkerHandlerOptions {
  readonly boundary: CaptureWorkerApiBoundary;
  readonly service: CaptureService;
  readonly maxStagingBytes?: number;
}

function jsonResponse(value: PublicPageCaptureApiV1, status = 200): Response {
  validateApiMessage(value);
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "cache-control": "no-store",
      "content-type": "application/json; charset=utf-8",
      "x-content-type-options": "nosniff",
    },
  });
}

function workerJsonResponse(
  value: PublicPageCaptureWorkerV1,
  status = 200,
): Response {
  validateWorkerMessage(value);
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "cache-control": "no-store",
      "content-type": "application/json; charset=utf-8",
      "x-content-type-options": "nosniff",
    },
  });
}

function requestInvalid(
  message: string,
  fieldPaths: readonly string[] = [],
): CaptureServiceError {
  return new CaptureServiceError("request_invalid", message, false, fieldPaths);
}

async function readJson(request: Request): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.split(";", 1)[0];
  if (contentType !== "application/json") {
    throw requestInvalid("The request must contain JSON.", ["/content-type"]);
  }
  try {
    return await request.json();
  } catch {
    throw requestInvalid("The request body is not valid JSON.", ["/"]);
  }
}

async function readBoundedBytes(request: Request, maxBytes: number): Promise<Buffer> {
  const declaredLength = request.headers.get("content-length");
  if (declaredLength && !/^\d+$/u.test(declaredLength)) {
    throw requestInvalid("The content length is invalid.", ["/content-length"]);
  }
  if (declaredLength && Number(declaredLength) > maxBytes) {
    throw new CaptureServiceError(
      "capture_resource_limit",
      "The staged object exceeds the worker protocol limit.",
    );
  }
  if (!request.body) return Buffer.alloc(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let byteLength = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      byteLength += next.value.byteLength;
      if (byteLength > maxBytes) {
        await reader.cancel();
        throw new CaptureServiceError(
          "capture_resource_limit",
          "The staged object exceeds the worker protocol limit.",
        );
      }
      chunks.push(next.value);
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks, byteLength);
}

function apiMessage(value: unknown): PublicPageCaptureApiV1 {
  try {
    validateApiMessage(value);
    return value as PublicPageCaptureApiV1;
  } catch (error) {
    if (error instanceof ContractValidationError) {
      throw requestInvalid(
        "The request does not satisfy the capture API contract.",
        error.fieldPaths,
      );
    }
    throw error;
  }
}

function workerMessage(value: unknown): PublicPageCaptureWorkerV1 {
  try {
    validateWorkerMessage(value);
    return value as PublicPageCaptureWorkerV1;
  } catch (error) {
    if (error instanceof ContractValidationError) {
      throw requestInvalid(
        "The request does not satisfy the capture worker contract.",
        error.fieldPaths,
      );
    }
    throw error;
  }
}

function assertPathField(
  actual: string,
  expected: string,
  fieldPath: string,
): void {
  if (actual !== expected) {
    throw requestInvalid("A path identifier does not match the request.", [
      fieldPath,
    ]);
  }
}

function effectResponse(receipt: CaptureMutationReceipt): Response {
  return new Response(null, {
    status: receipt.duplicateDelivery ? 200 : 204,
    headers: {
      "cache-control": "no-store",
      "vera-duplicate-delivery": String(receipt.duplicateDelivery),
      "vera-effect-id": receipt.effectId,
      "vera-recorded-at": receipt.recordedAt,
      "x-content-type-options": "nosniff",
    },
  });
}

function requestIdFrom(value: unknown): string {
  if (
    value !== null &&
    typeof value === "object" &&
    "clientRequestId" in value &&
    typeof value.clientRequestId === "string"
  ) {
    return value.clientRequestId;
  }
  return randomUUID();
}

function projectRoute(pathname: string): readonly string[] | null {
  let segments: string[];
  try {
    segments = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  } catch {
    return null;
  }
  if (segments[0] !== "v1" || segments[1] !== "projects") return null;
  return segments.slice(2);
}

export function createCaptureApiHandler({
  boundary,
  service,
}: CaptureApiHandlerOptions): (request: Request) => Promise<Response> {
  return async (request) => {
    let parsedBody: unknown;
    let requestId: string = randomUUID();
    try {
      const route = projectRoute(new URL(request.url).pathname);
      if (!route || route.length < 2) {
        return new Response(null, { status: 404 });
      }
      const [projectId, collection, objectId, action] = route;
      if (!projectId || !collection) return new Response(null, { status: 404 });

      // Authentication intentionally precedes body parsing. Project role checks
      // remain inside CaptureService and precede URL inspection or state writes.
      const principal = await boundary.authenticate(request);
      if (request.method === "POST") {
        parsedBody = await readJson(request);
        requestId = requestIdFrom(parsedBody);
      }

      if (collection === "captures" && route.length === 2 && request.method === "POST") {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "create_capture") {
          throw requestInvalid("Expected a create_capture request.", ["/messageType"]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        return jsonResponse(await service.createCapture(message, principal), 201);
      }
      if (collection === "captures" && objectId && route.length === 3 && request.method === "GET") {
        return jsonResponse(await service.getCapture(projectId, objectId, principal));
      }
      if (
        collection === "captures" &&
        objectId &&
        action === "configurations" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "create_configuration_version") {
          throw requestInvalid("Expected a create_configuration_version request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.captureId, objectId, "/captureId");
        return jsonResponse(
          await service.createConfigurationVersion(message, principal),
          201,
        );
      }
      if (
        collection === "captures" &&
        objectId &&
        action === "jobs" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "request_capture_job") {
          throw requestInvalid("Expected a request_capture_job request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.captureId, objectId, "/captureId");
        return jsonResponse(await service.requestCaptureJob(message, principal), 202);
      }
      if (
        collection === "captures" &&
        objectId &&
        action === "audit-events" &&
        route.length === 4 &&
        request.method === "GET"
      ) {
        return jsonResponse(
          await service.getAuditEvents(projectId, objectId, principal),
        );
      }
      if (collection === "jobs" && objectId && route.length === 3 && request.method === "GET") {
        return jsonResponse(await service.getJob(projectId, objectId, principal));
      }
      if (
        collection === "revisions" &&
        objectId &&
        route.length === 3 &&
        request.method === "GET"
      ) {
        return jsonResponse(await service.getRevision(projectId, objectId, principal));
      }
      if (
        collection === "revisions" &&
        objectId &&
        (action === "raster" || action === "provenance") &&
        route.length === 4 &&
        request.method === "GET"
      ) {
        const reference = await boundary.visibleReference(
          request,
          projectId,
          objectId,
        );
        const artifact =
          action === "raster"
            ? await service.readRasterArtifact(
                projectId,
                objectId,
                reference,
                principal,
                requestId,
              )
            : await service.readRestrictedProvenance(
                projectId,
                objectId,
                reference,
                principal,
                requestId,
              );
        const responseBytes = new Uint8Array(artifact.bytes.byteLength);
        responseBytes.set(artifact.bytes);
        return new Response(responseBytes, {
          status: 200,
          headers: {
            "cache-control": "private, no-store",
            "content-disposition":
              action === "raster"
                ? "inline; filename=vera-capture.png"
                : "attachment; filename=vera-capture-provenance.json",
            "content-length": String(artifact.bytes.byteLength),
            "content-type": artifact.descriptor.mimeType,
            etag: `"${artifact.descriptor.digest}"`,
            "x-content-type-options": "nosniff",
            "x-vera-artifact-id": artifact.descriptor.artifactId,
          },
        });
      }
      if (
        collection === "revisions" &&
        objectId &&
        action === "use-decisions" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "record_revision_use_decision") {
          throw requestInvalid("Expected a record_revision_use_decision request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.revisionId, objectId, "/revisionId");
        return effectResponse(
          await service.recordRevisionUseDecision(message, principal),
        );
      }
      if (
        collection === "revisions" &&
        objectId &&
        action === "selections" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "select_revision") {
          throw requestInvalid("Expected a select_revision request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.revisionId, objectId, "/revisionId");
        return effectResponse(await service.selectRevision(message, principal));
      }
      if (
        collection === "revisions" &&
        objectId &&
        action === "pins" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "add_explicit_pin") {
          throw requestInvalid("Expected an add_explicit_pin request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.revisionId, objectId, "/revisionId");
        return effectResponse(await service.addExplicitPin(message, principal));
      }
      if (
        collection === "pins" &&
        objectId &&
        action === "release" &&
        route.length === 4 &&
        request.method === "POST"
      ) {
        const message = apiMessage(parsedBody);
        if (message.messageType !== "release_explicit_pin") {
          throw requestInvalid("Expected a release_explicit_pin request.", [
            "/messageType",
          ]);
        }
        assertPathField(message.projectId, projectId, "/projectId");
        assertPathField(message.pinId, objectId, "/pinId");
        return effectResponse(await service.releaseExplicitPin(message, principal));
      }
      return new Response(null, { status: 404 });
    } catch (error) {
      const failure =
        error instanceof ContractValidationError
          ? requestInvalid(
              "The request does not satisfy the capture API contract.",
              error.fieldPaths,
            )
          : asCaptureServiceError(error);
      return jsonResponse(apiError(failure, requestId), failure.status);
    }
  };
}

const workerRoutes = new Map<string, PublicPageCaptureWorkerV1["messageType"]>([
  ["/v1/capture-worker/leases/claim", "claim_lease"],
  ["/v1/capture-worker/attempts/start", "start_attempt"],
  ["/v1/capture-worker/attempts/navigation-start", "record_navigation_start"],
  ["/v1/capture-worker/leases/renew", "renew_lease"],
  ["/v1/capture-worker/attempts/staging-grants", "request_staging_grants"],
  ["/v1/capture-worker/attempts/commit", "commit_attempt"],
  ["/v1/capture-worker/attempts/fail", "fail_attempt"],
  ["/v1/capture-worker/attempts/abandon", "abandon_attempt"],
]);

export function createCaptureWorkerProtocolHandler({
  boundary,
  service,
  maxStagingBytes = 16 * 1024 * 1024,
}: CaptureWorkerHandlerOptions): (request: Request) => Promise<Response> {
  return async (request) => {
    let requestId: string = randomUUID();
    try {
      const pathname = new URL(request.url).pathname;
      if (pathname === "/v1/capture-worker/staging" && request.method === "PUT") {
        const workerInstallationId = await boundary.authenticate(request);
        const authorization = request.headers.get("authorization");
        if (!authorization?.startsWith("Bearer ")) {
          throw new CaptureServiceError(
            "authentication_required",
            "Worker authentication is required.",
          );
        }
        const rawGrant = authorization.slice("Bearer ".length);
        const upload = await service.authorizeStagingUpload(
          rawGrant,
          workerInstallationId,
        );
        const contentType = request.headers.get("content-type")?.split(";", 1)[0];
        if (contentType !== upload.mimeType) {
          throw requestInvalid("The staged object media type is invalid.", [
            "/content-type",
          ]);
        }
        const bytes = await readBoundedBytes(
          request,
          Math.min(Math.max(0, maxStagingBytes), upload.maxBytes),
        );
        const staged = await service.stageObject(
          rawGrant,
          workerInstallationId,
          bytes,
        );
        return new Response(JSON.stringify(staged), {
          status: 201,
          headers: {
            "cache-control": "no-store",
            "content-type": "application/json; charset=utf-8",
            "x-content-type-options": "nosniff",
          },
        });
      }
      const expected = workerRoutes.get(pathname);
      if (!expected || request.method !== "POST") {
        return new Response(null, { status: 404 });
      }
      const workerInstallationId = await boundary.authenticate(request);
      const parsed = await readJson(request);
      requestId = requestIdFrom(parsed);
      const message = workerMessage(parsed);
      if (message.messageType !== expected) {
        throw requestInvalid("The worker message does not match its route.", [
          "/messageType",
        ]);
      }
      const messageWorkerInstallationId =
        message.messageType === "claim_lease"
          ? message.workerInstallationId
          : "lease" in message
            ? message.lease.workerInstallationId
            : null;
      if (messageWorkerInstallationId !== workerInstallationId) {
        throw new CaptureServiceError(
          "invalid_or_expired_job_capability",
          "The worker capability is invalid or expired.",
        );
      }
      switch (message.messageType) {
        case "claim_lease":
          return workerJsonResponse(await service.claimLease(message));
        case "start_attempt":
          return workerJsonResponse(await service.startAttempt(message));
        case "record_navigation_start":
          return workerJsonResponse(await service.recordNavigationStart(message));
        case "renew_lease":
          return workerJsonResponse(await service.renewLease(message));
        case "request_staging_grants":
          return workerJsonResponse(await service.requestStagingGrants(message));
        case "commit_attempt":
          return workerJsonResponse(await service.commitAttempt(message));
        case "fail_attempt":
          return workerJsonResponse(await service.failAttempt(message));
        case "abandon_attempt":
          return workerJsonResponse(await service.abandonAttempt(message));
        default:
          throw requestInvalid("The route accepts worker requests only.", [
            "/messageType",
          ]);
      }
    } catch (error) {
      const failure = asCaptureServiceError(error);
      return workerJsonResponse(workerError(failure, requestId), failure.status);
    }
  };
}
