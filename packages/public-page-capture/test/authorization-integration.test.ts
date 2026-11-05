import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type {
  LeaseAssignment,
  LeaseProof,
  PublicPageCaptureProvenanceV1,
  StagedObjectDescriptor,
} from "@vera/contracts";
import {
  applyProjectAuthorizationMigration,
  ProjectAuthorizationService,
  type ProjectAuthError,
  type SqlPool,
} from "@vera/project-authorization";
import { PNG } from "pngjs";
import { afterEach, describe, expect, it, vi } from "vitest";

// The independent PGlite WASM fixture is cold-started for every case; CI
// filesystem/CPU contention can exceed Vitest's 5s default without a defect.
vi.setConfig({ testTimeout: 20_000 });

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
} from "../src/authorization.js";
import { createCaptureApiHandler } from "../src/api.js";
import { validateApiMessage, validateWorkerMessage } from "../src/contracts.js";
import {
  canonicalJson,
  CapabilitySigner,
  sha256,
  type JsonValue,
} from "../src/crypto.js";
import {
  applyPublicCaptureMigration,
  SingleClientCaptureDatabase,
} from "../src/database.js";
import { RestrictedRequestCipher } from "../src/envelope.js";
import { captureConfigurationVersionId } from "../src/identities.js";
import { MemoryImmutableObjectStore } from "../src/object-store.js";
import {
  CAPTURE_PROFILE_V1,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "../src/profile.js";
import { CaptureService } from "../src/service.js";

/* eslint-disable @typescript-eslint/require-await -- Test doubles implement async ports. */

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const WORKER_ID = "18181818-1818-4818-8818-181818181818";
const FIXTURE = JSON.parse(
  readFileSync(
    new URL(
      "../../../tests/data/issue_39_public_page_capture/provenance-revision-observation.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as PublicPageCaptureProvenanceV1;
const databases: PGlite[] = [];

const references: AuthoringReferencePort = {
  validate: async () => undefined,
};

interface Harness {
  readonly auth: ProjectAuthorizationService;
  readonly db: PGlite;
  readonly objects: MemoryImmutableObjectStore;
  readonly service: CaptureService;
  readonly adminId: string;
  readonly editorId: string;
  readonly viewerId: string;
}

async function harness(): Promise<Harness> {
  // Both schemas share one database, mirroring production: the commit-time
  // membership recheck then runs on the publish transaction's own client.
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyPublicCaptureMigration(db);
  await applyProjectAuthorizationMigration(db);
  await db.query(
    `UPDATE public_page_capture_settings SET enabled = true
      WHERE setting_name = 'public_page_capture_execution'`,
  );
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const admin = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "capture-producer",
  });
  const editor = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "capture-editor",
  });
  const viewer = await auth.resolveActor({
    issuer: "https://suite.example.test", subject: "capture-viewer",
  });
  await db.query("BEGIN");
  try {
    await auth.provisionFirstProducerInProjectTransaction(db, PROJECT_ID, admin);
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK");
    throw error;
  }
  await auth.changeMembership(PROJECT_ID, admin, editor.principalId, "editor");
  await auth.changeMembership(PROJECT_ID, admin, viewer.principalId, "viewer");
  const objects = new MemoryImmutableObjectStore();
  const service = new CaptureService({
    authorization: auth,
    capabilities: new CapabilitySigner(Buffer.alloc(32, 2)),
    cipher: new RestrictedRequestCipher(Buffer.alloc(32, 1)),
    database: new SingleClientCaptureDatabase(db),
    denialFingerprintKey: Buffer.alloc(32, 3),
    objects,
    references,
    workerAuthorization: {
      authorize: async (workerInstallationId) => {
        if (workerInstallationId !== WORKER_ID) throw new Error("unknown worker");
      },
    },
    now: () => new Date("2026-09-08T16:00:05.000Z"),
  });
  return {
    auth,
    db,
    objects,
    service,
    adminId: admin.principalId,
    editorId: editor.principalId,
    viewerId: viewer.principalId,
  };
}

function createCaptureRequest() {
  return {
    schemaVersion: "public-page-capture-api/v1",
    messageType: "create_capture",
    projectId: PROJECT_ID,
    clientRequestId: randomUUID(),
    idempotencyKey: randomUUID(),
    requestedUrl: "https://capture.example.org/story?edition=public",
    regionIntent: { kind: "full_viewport" },
    acquisitionPolicy: { kind: "now" },
    captureProfileId: CAPTURE_PROFILE_V1.profileId,
    captureProfileVersion: CAPTURE_PROFILE_V1.profileVersion,
  } as const;
}

async function createCapture(
  service: CaptureService,
  principalId: string,
): Promise<string> {
  const result = await service.createCapture(createCaptureRequest(), {
    principalKind: "user",
    principalId,
  });
  return result.capture.captureId;
}

async function queue(
  service: CaptureService,
  captureId: string,
  principalId: string,
): Promise<void> {
  await service.requestCaptureJob(
    {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "request_capture_job",
      projectId: PROJECT_ID,
      captureId,
      clientRequestId: randomUUID(),
      idempotencyKey: randomUUID(),
      expectedCaptureRowVersion: 1,
      trigger: {
        kind: "now",
        commandId: randomUUID(),
        selectionIntent: { kind: "none" },
      },
    },
    { principalKind: "user", principalId },
  );
}

function raster(): Buffer {
  const png = new PNG({ width: OUTPUT_WIDTH, height: OUTPUT_HEIGHT, colorType: 6 });
  png.data.fill(255);
  png.data[0] = 200;
  return PNG.sync.write(png, { colorType: 6 });
}

function provenanceBytes(
  assignment: LeaseAssignment,
  attemptId: string,
  revisionId: string,
  rasterBytes: Buffer,
): Buffer {
  const value = structuredClone(FIXTURE);
  value.identity = {
    projectId: assignment.projectId,
    captureId: assignment.captureId,
    configurationVersionId: captureConfigurationVersionId(
      assignment.projectId,
      assignment.captureId,
      assignment.configurationVersion,
    ),
    jobId: assignment.jobId,
    leaseEpoch: assignment.leaseEpoch,
    attemptId,
    revisionId,
  };
  value.request.settingsDigest = assignment.settingsDigest;
  value.request.captureProfileDigest = assignment.profile.profileDigest;
  value.runtime.installationId = WORKER_ID;
  value.output!.raster = {
    artifactId: randomUUID(),
    digest: sha256(rasterBytes),
    byteLength: rasterBytes.byteLength,
    mediaType: "image/png",
  };
  value.output!.width = OUTPUT_WIDTH as 3840;
  value.output!.height = OUTPUT_HEIGHT as 2160;
  value.output!.capturedRegion = {
    x: 0,
    y: 0,
    width: OUTPUT_WIDTH,
    height: OUTPUT_HEIGHT,
  };
  return Buffer.from(canonicalJson(value as unknown as JsonValue), "utf8");
}

async function stageForCommit(
  service: CaptureService,
  rasterBytes: Buffer,
): Promise<Parameters<CaptureService["commitAttempt"]>[0]> {
  const claimed = await service.claimLease({
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "claim_lease",
    clientRequestId: randomUUID(),
    workerInstallationId: WORKER_ID,
    supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
  });
  const started = await service.startAttempt({
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "start_attempt",
    clientRequestId: randomUUID(),
    lease: {
      workerInstallationId: WORKER_ID,
      jobId: claimed.assignment.jobId,
      leaseId: claimed.assignment.leaseId,
      leaseEpoch: claimed.assignment.leaseEpoch,
      attemptId: null,
      leaseCapability: claimed.assignment.leaseCapability,
    },
    cleanProfileId: randomUUID(),
    browserBuild: "chromium-test-1",
    adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
    securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
  });
  const lease: LeaseProof = {
    workerInstallationId: WORKER_ID,
    jobId: claimed.assignment.jobId,
    leaseId: claimed.assignment.leaseId,
    leaseEpoch: claimed.assignment.leaseEpoch,
    attemptId: started.attemptId,
    leaseCapability: claimed.assignment.leaseCapability,
  };
  const grants = await service.requestStagingGrants({
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "request_staging_grants",
    clientRequestId: randomUUID(),
    lease,
    purposes: ["raster", "provenance"],
  });
  const stagedRaster = await service.stageObject(
    grants.grants[0].rawGrant,
    WORKER_ID,
    rasterBytes,
  );
  const stagedProvenance = await service.stageObject(
    grants.grants[1].rawGrant,
    WORKER_ID,
    provenanceBytes(
      claimed.assignment,
      started.attemptId,
      randomUUID(),
      rasterBytes,
    ),
  );
  const rasterDescriptor: StagedObjectDescriptor = {
    stagingObjectId: stagedRaster.stagingObjectId,
    grantId: stagedRaster.grantId,
    purpose: "raster",
    digest: stagedRaster.digest,
    byteLength: stagedRaster.byteLength,
    mimeType: "image/png",
    width: OUTPUT_WIDTH,
    height: OUTPUT_HEIGHT,
    encoding: "png",
    color: "srgb",
    alpha: "opaque",
  };
  const provenanceDescriptor: StagedObjectDescriptor = {
    stagingObjectId: stagedProvenance.stagingObjectId,
    grantId: stagedProvenance.grantId,
    purpose: "provenance",
    digest: stagedProvenance.digest,
    byteLength: stagedProvenance.byteLength,
    mimeType: "application/json",
    encoding: "json",
  };
  return {
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "commit_attempt",
    clientRequestId: randomUUID(),
    lease,
    commitNonce: claimed.assignment.commitNonce,
    raster: rasterDescriptor,
    provenanceObject: provenanceDescriptor,
    warningCodes: [],
    reviewClassification: "ready",
  };
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map(async (db) => await db.close()));
});

describe("capture service against the project authorization service", () => {
  it("structurally implements the capture ProjectAuthorizationPort", async () => {
    const { auth } = await harness();
    // Compile-time proof: the real service satisfies the existing port.
    const port: ProjectAuthorizationPort = auth;
    expect(port).toBe(auth);
  });

  it("authorizes the create flow for an Editor and stamps attribution", async () => {
    const { db, service, editorId } = await harness();
    const captureId = await createCapture(service, editorId);
    const created = await db.query<{ created_by_id: string }>(
      "SELECT created_by_id FROM captures WHERE capture_id=$1",
      [captureId],
    );
    expect(created.rows[0]?.created_by_id).toBe(editorId);
  });

  it("refuses capture creation for a Viewer", async () => {
    const { service, viewerId } = await harness();
    await expect(createCapture(service, viewerId)).rejects.toMatchObject({
      name: "ProjectAuthError",
      code: "action_not_allowed",
      status: 403,
    } satisfies Partial<ProjectAuthError>);
  });

  it("maps authorization refusals to closed API errors at the HTTP boundary", async () => {
    const { service, viewerId } = await harness();
    const handler = createCaptureApiHandler({
      service,
      boundary: {
        authenticate: () =>
          Promise.resolve({ principalKind: "user", principalId: viewerId }),
        visibleReference: () => Promise.reject(new Error("not reached")),
      },
    });
    const response = await handler(
      new Request(`https://api.example.test/v1/projects/${PROJECT_ID}/captures`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(createCaptureRequest()),
      }),
    );
    const body: unknown = await response.json();
    expect(response.status).toBe(403);
    validateApiMessage(body);
    expect(body).toMatchObject({
      schemaVersion: "public-page-capture-api/v1",
      messageType: "error",
      code: "action_not_allowed",
      retryable: false,
    });
  });

  it("maps every capture action the service calls onto the closed role matrix", async () => {
    const { auth, adminId, editorId, viewerId } = await harness();
    const editor = { principalKind: "user", principalId: editorId } as const;
    const viewer = { principalKind: "user", principalId: viewerId } as const;
    const producer = { principalKind: "user", principalId: adminId } as const;
    const editorActions = [
      "capture_create", "capture_configure", "capture_request_now",
      "capture_request_on_build", "capture_commit", "capture_select",
      "capture_use_preview",
    ];
    for (const action of editorActions) {
      await expect(auth.authorize(PROJECT_ID, editor, action)).resolves.toBeTruthy();
      await expect(auth.authorize(PROJECT_ID, viewer, action))
        .rejects.toMatchObject({ code: "action_not_allowed" });
    }
    await expect(auth.authorize(PROJECT_ID, viewer, "capture_read"))
      .resolves.toMatchObject({ role: "viewer" });
    for (const action of ["capture_pin", "capture_use_release"]) {
      await expect(auth.authorize(PROJECT_ID, producer, action)).resolves.toBeTruthy();
      await expect(auth.authorize(PROJECT_ID, editor, action))
        .rejects.toMatchObject({ code: "action_not_allowed" });
    }
  });

  it("commits an Editor-initiated job with a fresh membership check at commit time", async () => {
    const { db, service, editorId } = await harness();
    const captureId = await createCapture(service, editorId);
    await queue(service, captureId, editorId);
    const request = await stageForCommit(service, raster());
    const response = await service.commitAttempt(request);
    validateWorkerMessage(response);
    expect(response).toMatchObject({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_committed",
      job: { state: "committed_ready" },
    });
    // The authorization service reports every_request, the stronger recheck
    // mode, and the capture service persists that provenance faithfully.
    const job = await db.query<{ commit_recheck_mode: string }>(
      "SELECT commit_recheck_mode FROM capture_jobs",
    );
    expect(job.rows[0]?.commit_recheck_mode).toBe("every_request");
  });

  it("publishes nothing when the initiating Editor is revoked before commit", async () => {
    const { auth, db, service, adminId, editorId } = await harness();
    const captureId = await createCapture(service, editorId);
    await queue(service, captureId, editorId);
    const request = await stageForCommit(service, raster());
    await auth.changeMembership(PROJECT_ID, {
      principalKind: "user", principalId: adminId,
    }, editorId, null);
    await expect(service.commitAttempt(request)).rejects.toMatchObject({
      name: "ProjectAuthError",
      code: "action_not_allowed",
    });
    const published = await db.query<{ total: string }>(
      "SELECT count(*)::text AS total FROM capture_revisions",
    );
    expect(Number(published.rows[0]?.total)).toBe(0);
  });
});
