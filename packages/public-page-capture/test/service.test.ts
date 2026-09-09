import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type {
  AuthorizationDecisionRef,
  CreateCaptureRequest,
  PrincipalRef,
  RequestCaptureJobRequest,
} from "@vera/contracts";
import { afterEach, describe, expect, it } from "vitest";

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
  WorkerAuthorizationPort,
} from "../src/authorization.js";
import { AuthorizationUnavailable } from "../src/authorization.js";
import {
  createCaptureApiHandler,
  createCaptureWorkerProtocolHandler,
} from "../src/api.js";
import { validateApiMessage, validateWorkerMessage } from "../src/contracts.js";
import { CapabilitySigner } from "../src/crypto.js";
import {
  applyPublicCaptureMigration,
  SingleClientCaptureDatabase,
} from "../src/database.js";
import { RestrictedRequestCipher } from "../src/envelope.js";
import { CaptureServiceError } from "../src/errors.js";
import { MemoryImmutableObjectStore } from "../src/object-store.js";
import { CAPTURE_PROFILE_V1 } from "../src/profile.js";
import { CaptureService } from "../src/service.js";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const WORKER_ID = "18181818-1818-4818-8818-181818181818";
const PRINCIPAL: PrincipalRef = {
  principalKind: "user",
  principalId: "dddddddd-dddd-4ddd-8ddd-ddddddddddd2",
};
const NOW = new Date("2026-09-08T16:00:00.000Z");
const databases: PGlite[] = [];

/* eslint-disable @typescript-eslint/require-await -- Test doubles implement async ports. */

class AllowAuthorization implements ProjectAuthorizationPort {
  readonly actions: string[] = [];
  failure: CaptureServiceError | null = null;

  async authorize(
    projectId: string,
    principal: PrincipalRef,
    action: string,
  ): Promise<AuthorizationDecisionRef> {
    this.actions.push(action);
    if (this.failure) throw this.failure;
    return {
      decisionId: randomUUID(),
      action,
      principal,
      projectId,
      role: "producer",
      membershipVersion: 1,
      decidedAt: NOW.toISOString(),
      recheckMode: action === "capture_commit" ? "commit_time" : "every_request",
    };
  }
}

class AllowReferences implements AuthoringReferencePort {
  readonly actions: string[] = [];

  async validate(
    projectId: string,
    reference: Parameters<AuthoringReferencePort["validate"]>[1],
    action: Parameters<AuthoringReferencePort["validate"]>[2],
  ): Promise<void> {
    expect(projectId).toBe(PROJECT_ID);
    expect(reference.projectId).toBe(PROJECT_ID);
    this.actions.push(action);
  }
}

const allowWorker: WorkerAuthorizationPort = {
  authorize: async () => undefined,
};
const workerBoundary = {
  authenticate: async () => WORKER_ID,
};

interface Harness {
  readonly authorization: AllowAuthorization;
  readonly cipher: RestrictedRequestCipher;
  readonly db: PGlite;
  readonly references: AllowReferences;
  readonly service: CaptureService;
}

async function harness(
  authorization: ProjectAuthorizationPort = new AllowAuthorization(),
): Promise<Harness> {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyPublicCaptureMigration(db);
  const cipher = new RestrictedRequestCipher(Buffer.alloc(32, 1));
  const references = new AllowReferences();
  const allow = authorization as AllowAuthorization;
  return {
    authorization: allow,
    cipher,
    db,
    references,
    service: new CaptureService({
      authorization,
      capabilities: new CapabilitySigner(Buffer.alloc(32, 2)),
      cipher,
      database: new SingleClientCaptureDatabase(db),
      denialFingerprintKey: Buffer.alloc(32, 3),
      objects: new MemoryImmutableObjectStore(),
      references,
      workerAuthorization: allowWorker,
      now: () => new Date(NOW),
    }),
  };
}

function createRequest(
  overrides: Partial<CreateCaptureRequest> = {},
): CreateCaptureRequest {
  return {
    schemaVersion: "public-page-capture-api/v1",
    messageType: "create_capture",
    projectId: PROJECT_ID,
    clientRequestId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
    idempotencyKey: "capture-create-0001",
    requestedUrl: "https://capture.example.org/story?edition=public",
    regionIntent: { kind: "full_viewport" },
    acquisitionPolicy: { kind: "now" },
    captureProfileId: CAPTURE_PROFILE_V1.profileId,
    captureProfileVersion: CAPTURE_PROFILE_V1.profileVersion,
    ...overrides,
  };
}

function nowJobRequest(
  captureId: string,
  overrides: Partial<RequestCaptureJobRequest> = {},
): RequestCaptureJobRequest {
  return {
    schemaVersion: "public-page-capture-api/v1",
    messageType: "request_capture_job",
    projectId: PROJECT_ID,
    captureId,
    clientRequestId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
    idempotencyKey: "capture-now-000001",
    expectedCaptureRowVersion: 1,
    trigger: {
      kind: "now",
      commandId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
      selectionIntent: { kind: "none" },
    },
    ...overrides,
  };
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map(async (db) => await db.close()));
});

describe("CaptureService authoring boundary", () => {
  it("creates one redacted, encrypted capture for duplicate delivery", async () => {
    const { cipher, db, service } = await harness();
    const request = createRequest();

    const first = await service.createCapture(request, PRINCIPAL);
    const duplicate = await service.createCapture(request, PRINCIPAL);

    expect(duplicate.capture.captureId).toBe(first.capture.captureId);
    expect(first.capture.configuration.requestedUrl).toMatchObject({
      display: "https://capture.example.org/story?edition=%5BREDACTED%5D",
      queryKeys: ["edition"],
    });
    expect(JSON.stringify(first)).not.toContain("edition=public");
    const stored = await db.query<{
      canonical_url_digest: Uint8Array;
      configuration_version: number;
      restricted_request_envelope: Uint8Array;
    }>(
      `SELECT canonical_url_digest, configuration_version,
              restricted_request_envelope
         FROM capture_configurations`,
    );
    expect(stored.rows).toHaveLength(1);
    const row = stored.rows[0]!;
    expect(Buffer.from(row.restricted_request_envelope).toString("utf8")).not.toContain(
      "edition=public",
    );
    expect(
      cipher.decrypt(Buffer.from(row.restricted_request_envelope), {
        projectId: PROJECT_ID,
        captureId: first.capture.captureId,
        configurationVersion: Number(row.configuration_version),
        canonicalUrlDigest: first.capture.configuration.requestedUrl.canonicalDigest,
      }),
    ).toBe(request.requestedUrl);
    expect(
      await db.query("SELECT 1 FROM capture_audit_events WHERE event_type = 'capture_created'"),
    ).toMatchObject({ rows: [{ "?column?": 1 }] });
  }, 20_000);

  it("rejects an idempotency key reused with changed request bytes", async () => {
    const { service } = await harness();
    const request = createRequest();
    await service.createCapture(request, PRINCIPAL);

    await expect(
      service.createCapture(
        { ...request, requestedUrl: "https://capture.example.org/other" },
        PRINCIPAL,
      ),
    ).rejects.toMatchObject({ code: "idempotency_key_reused" });
  }, 20_000);

  it("creates immutable configuration versions with optimistic concurrency", async () => {
    const { db, service } = await harness();
    const created = await service.createCapture(createRequest(), PRINCIPAL);

    const updated = await service.createConfigurationVersion(
      {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "create_configuration_version",
        projectId: PROJECT_ID,
        captureId: created.capture.captureId,
        clientRequestId: randomUUID(),
        idempotencyKey: "configuration-0001",
        expectedCaptureRowVersion: 1,
        requestedUrl: "https://capture.example.org/story?edition=second",
        regionIntent: { kind: "full_viewport" },
        acquisitionPolicy: { kind: "on_build" },
        captureProfileId: CAPTURE_PROFILE_V1.profileId,
        captureProfileVersion: CAPTURE_PROFILE_V1.profileVersion,
      },
      PRINCIPAL,
    );

    expect(updated.capture).toMatchObject({
      currentConfigurationVersion: 2,
      rowVersion: 2,
      configuration: {
        acquisitionPolicy: { kind: "on_build" },
        configurationVersion: 2,
      },
    });
    expect(
      await db.query("SELECT configuration_version FROM capture_configurations ORDER BY configuration_version"),
    ).toMatchObject({ rows: [{ configuration_version: 1 }, { configuration_version: 2 }] });
    await expect(
      service.createConfigurationVersion(
        {
          schemaVersion: "public-page-capture-api/v1",
          messageType: "create_configuration_version",
          projectId: PROJECT_ID,
          captureId: created.capture.captureId,
          clientRequestId: randomUUID(),
          idempotencyKey: "configuration-0002",
          expectedCaptureRowVersion: 1,
          requestedUrl: "https://capture.example.org/story",
          regionIntent: { kind: "full_viewport" },
          acquisitionPolicy: { kind: "now" },
          captureProfileId: CAPTURE_PROFILE_V1.profileId,
          captureProfileVersion: CAPTURE_PROFILE_V1.profileVersion,
        },
        PRINCIPAL,
      ),
    ).rejects.toMatchObject({ code: "version_conflict" });
  }, 20_000);

  it("queues Now jobs idempotently with a frozen 4K raster profile", async () => {
    const { db, service } = await harness();
    const capture = await service.createCapture(createRequest(), PRINCIPAL);
    const request = nowJobRequest(capture.capture.captureId);

    const first = await service.requestCaptureJob(request, PRINCIPAL);
    const duplicate = await service.requestCaptureJob(request, PRINCIPAL);

    expect(first.job).toMatchObject({
      state: "queued",
      duplicateDelivery: false,
      trigger: request.trigger,
      captureProfileId: CAPTURE_PROFILE_V1.profileId,
      captureProfileVersion: 1,
    });
    expect(duplicate.job).toMatchObject({
      jobId: first.job.jobId,
      duplicateDelivery: true,
    });
    const profile = await db.query<{ capture_profile_json: unknown }>(
      "SELECT capture_profile_json FROM capture_jobs",
    );
    expect(profile.rows[0]?.capture_profile_json).toMatchObject({
      render: {
        viewportWidth: 1920,
        viewportHeight: 1080,
        deviceScaleFactor: 2,
      },
      limits: { outputPixels: 8_294_400 },
    });
  }, 20_000);

  it("deduplicates On build by an immutable build snapshot", async () => {
    const { references, service } = await harness();
    const capture = await service.createCapture(createRequest(), PRINCIPAL);
    const request: RequestCaptureJobRequest = {
      ...nowJobRequest(capture.capture.captureId),
      clientRequestId: randomUUID(),
      idempotencyKey: "capture-build-0001",
      trigger: {
        kind: "on_build",
        buildSnapshot: {
          projectId: PROJECT_ID,
          kind: "preview_build",
          resourceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc1",
          resourceVersionDigest: `sha256:${"cc".repeat(32)}`,
        },
      },
    };

    const first = await service.requestCaptureJob(request, PRINCIPAL);
    const duplicate = await service.requestCaptureJob(
      {
        ...request,
        clientRequestId: randomUUID(),
        idempotencyKey: "capture-build-0002",
      },
      PRINCIPAL,
    );

    expect(duplicate.job.jobId).toBe(first.job.jobId);
    expect(duplicate.job.duplicateDelivery).toBe(true);
    expect(references.actions).toEqual(["build", "build"]);
  }, 20_000);

  it("authorizes before inspecting an unsafe URL", async () => {
    const authorization: ProjectAuthorizationPort = {
      authorize: async () => {
        throw new CaptureServiceError(
          "authentication_required",
          "Authentication is required.",
        );
      },
    };
    const { service } = await harness(authorization);

    await expect(
      service.createCapture(
        createRequest({ requestedUrl: "http://127.0.0.1/admin" }),
        PRINCIPAL,
      ),
    ).rejects.toMatchObject({
      code: "authentication_required",
      denialFingerprint: undefined,
    });
  }, 20_000);

  it("makes known and unknown resources indistinguishable after role removal", async () => {
    const { authorization, service } = await harness();
    const created = await service.createCapture(createRequest(), PRINCIPAL);
    authorization.failure = new CaptureServiceError(
      "action_not_allowed",
      "The requested resource is unavailable.",
    );

    for (const captureId of [created.capture.captureId, randomUUID()]) {
      await expect(
        service.getCapture(PROJECT_ID, captureId, PRINCIPAL),
      ).rejects.toMatchObject({
        code: "action_not_allowed",
        safeMessage: "The requested resource is unavailable.",
        fieldPaths: [],
      });
    }

    authorization.failure = new AuthorizationUnavailable();
    await expect(
      service.getCapture(PROJECT_ID, created.capture.captureId, PRINCIPAL),
    ).rejects.toMatchObject({
      code: "authorization_unavailable",
      retryable: true,
    });
  }, 20_000);
});

describe("capture HTTP boundaries", () => {
  it("authenticates the registered worker before parsing protocol JSON", async () => {
    const { service } = await harness();
    const handler = createCaptureWorkerProtocolHandler({
      boundary: {
        authenticate: () =>
          Promise.reject(
            new CaptureServiceError(
              "authentication_required",
              "Worker authentication is required.",
            ),
          ),
      },
      service,
    });
    const response = await handler(
      new Request(
        "https://api.example.test/v1/capture-worker/leases/claim",
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: "{not-json",
        },
      ),
    );
    const body: unknown = await response.json();

    expect(response.status).toBe(401);
    validateWorkerMessage(body);
    expect(body).toMatchObject({
      messageType: "worker_error",
      code: "authentication_required",
      fieldPaths: [],
    });
  }, 20_000);

  it("returns a closed retryable worker error when no lease can be issued", async () => {
    const { service } = await harness();
    const handler = createCaptureWorkerProtocolHandler({
      boundary: workerBoundary,
      service,
    });
    const response = await handler(
      new Request(
        "https://api.example.test/v1/capture-worker/leases/claim",
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            schemaVersion: "public-page-capture-worker/v1",
            messageType: "claim_lease",
            clientRequestId: randomUUID(),
            workerInstallationId: WORKER_ID,
            supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
          }),
        },
      ),
    );
    const body: unknown = await response.json();

    expect(response.status).toBe(503);
    validateWorkerMessage(body);
    expect(body).toMatchObject({
      messageType: "worker_error",
      code: "capture_worker_unavailable",
      retryable: true,
    });
  }, 20_000);

  it("authenticates before parsing and returns a closed sanitized API error", async () => {
    const { db, service } = await harness();
    const handler = createCaptureApiHandler({
      service,
      boundary: {
        authenticate: () =>
          Promise.reject(
            new CaptureServiceError(
              "authentication_required",
              "Authentication is required.",
            ),
          ),
        visibleReference: () => Promise.reject(new Error("not reached")),
      },
    });

    const response = await handler(
      new Request(`https://api.example.test/v1/projects/${PROJECT_ID}/captures`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{not-json",
      }),
    );
    const body: unknown = await response.json();

    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    validateApiMessage(body);
    expect(body).toMatchObject({
      schemaVersion: "public-page-capture-api/v1",
      messageType: "error",
      code: "authentication_required",
      safeMessage: "Authentication is required.",
      retryable: false,
      fieldPaths: [],
    });
    expect(await db.query("SELECT count(*)::int AS count FROM captures")).toMatchObject({
      rows: [{ count: 0 }],
    });
  }, 20_000);

  it("serves project-scoped routes without exposing restricted request bytes", async () => {
    const { service } = await harness();
    const boundary = {
      authenticate: () => Promise.resolve(PRINCIPAL),
      visibleReference: () => Promise.reject(new Error("not reached")),
    };
    const handler = createCaptureApiHandler({ service, boundary });
    const request = createRequest();
    const created = await handler(
      new Request(`https://api.example.test/v1/projects/${PROJECT_ID}/captures`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      }),
    );
    const createdBody: unknown = await created.json();

    expect(created.status).toBe(201);
    expect(created.headers.get("x-content-type-options")).toBe("nosniff");
    validateApiMessage(createdBody);
    expect(JSON.stringify(createdBody)).not.toContain("edition=public");
    if (
      !createdBody ||
      typeof createdBody !== "object" ||
      !("capture" in createdBody) ||
      !createdBody.capture ||
      typeof createdBody.capture !== "object" ||
      !("captureId" in createdBody.capture) ||
      typeof createdBody.capture.captureId !== "string"
    ) {
      throw new Error("Expected a capture response.");
    }
    const captureId = createdBody.capture.captureId;
    const fetched = await handler(
      new Request(
        `https://api.example.test/v1/projects/${PROJECT_ID}/captures/${captureId}`,
      ),
    );
    expect(fetched.status).toBe(200);
    validateApiMessage(await fetched.json());

    const mismatch = await handler(
      new Request(`https://api.example.test/v1/projects/${PROJECT_ID}/captures`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          ...request,
          projectId: "99999999-9999-4999-8999-999999999999",
          clientRequestId: randomUUID(),
          idempotencyKey: "capture-create-mismatch",
        }),
      }),
    );
    expect(mismatch.status).toBe(400);
    expect(await mismatch.json()).toMatchObject({ code: "request_invalid" });

    const malformedPath = await handler(
      new Request("https://api.example.test/v1/projects/%GG/captures"),
    );
    expect(malformedPath.status).toBe(404);
  }, 20_000);

  it("rejects an invalid staging capability before consuming upload bytes", async () => {
    const { service } = await harness();
    const handler = createCaptureWorkerProtocolHandler({
      boundary: workerBoundary,
      service,
    });
    let bodyRead = false;
    const request = {
      url: "https://api.example.test/v1/capture-worker/staging",
      method: "PUT",
      headers: new Headers({
        authorization: "Bearer not-a-capability",
        "content-type": "image/png",
      }),
      get body(): ReadableStream<Uint8Array> {
        bodyRead = true;
        throw new Error("The body must not be consumed.");
      },
    } as unknown as Request;

    const response = await handler(request);
    const body: unknown = await response.json();

    expect(response.status).toBe(401);
    expect(bodyRead).toBe(false);
    validateWorkerMessage(body);
    expect(body).toMatchObject({
      messageType: "worker_error",
      code: "invalid_or_expired_job_capability",
      safeMessage: "The worker capability is invalid or expired.",
    });
    expect(JSON.stringify(body)).not.toContain("not-a-capability");
  }, 20_000);
});
