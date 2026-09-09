import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type {
  AuthorizationDecisionRef,
  LeaseProof,
  PrincipalRef,
} from "@vera/contracts";
import { afterEach, describe, expect, it } from "vitest";

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
} from "../src/authorization.js";
import { validateWorkerMessage } from "../src/contracts.js";
import { CapabilitySigner } from "../src/crypto.js";
import {
  applyPublicCaptureMigration,
  SingleClientCaptureDatabase,
} from "../src/database.js";
import { RestrictedRequestCipher } from "../src/envelope.js";
import { MemoryImmutableObjectStore } from "../src/object-store.js";
import { CAPTURE_PROFILE_V1 } from "../src/profile.js";
import { CaptureService } from "../src/service.js";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const WORKER_ID = "18181818-1818-4818-8818-181818181818";
const PRINCIPAL: PrincipalRef = {
  principalKind: "user",
  principalId: "dddddddd-dddd-4ddd-8ddd-ddddddddddd2",
};
const databases: PGlite[] = [];

/* eslint-disable @typescript-eslint/require-await -- Test doubles implement async ports. */

class Clock {
  value = new Date("2026-09-08T16:00:00.000Z");

  now = (): Date => new Date(this.value);

  advance(milliseconds: number): void {
    this.value = new Date(this.value.getTime() + milliseconds);
  }
}

const authorization: ProjectAuthorizationPort = {
  async authorize(projectId, principal, action): Promise<AuthorizationDecisionRef> {
    return {
      decisionId: randomUUID(),
      action,
      principal,
      projectId,
      role: "producer",
      membershipVersion: 1,
      decidedAt: "2026-09-08T16:00:00.000Z",
      recheckMode: action === "capture_commit" ? "commit_time" : "every_request",
    };
  },
};

const references: AuthoringReferencePort = {
  validate: async () => undefined,
};

interface Harness {
  readonly clock: Clock;
  readonly db: PGlite;
  readonly objects: MemoryImmutableObjectStore;
  readonly service: CaptureService;
}

async function harness(): Promise<Harness> {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyPublicCaptureMigration(db);
  await db.query(
    `UPDATE public_page_capture_settings SET enabled = true
      WHERE setting_name = 'public_page_capture_execution'`,
  );
  const clock = new Clock();
  const objects = new MemoryImmutableObjectStore();
  const service = new CaptureService({
    authorization,
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
    now: clock.now,
  });
  return { clock, db, objects, service };
}

async function queuedJob(service: CaptureService): Promise<string> {
  const capture = await service.createCapture(
    {
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
    },
    PRINCIPAL,
  );
  const job = await service.requestCaptureJob(
    {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "request_capture_job",
      projectId: PROJECT_ID,
      captureId: capture.capture.captureId,
      clientRequestId: randomUUID(),
      idempotencyKey: randomUUID(),
      expectedCaptureRowVersion: capture.capture.rowVersion,
      trigger: {
        kind: "now",
        commandId: randomUUID(),
        selectionIntent: { kind: "none" },
      },
    },
    PRINCIPAL,
  );
  return job.job.jobId;
}

function proof(
  assignment: Awaited<ReturnType<CaptureService["claimLease"]>>["assignment"],
  attemptId: string | null,
): LeaseProof {
  return {
    workerInstallationId: WORKER_ID,
    jobId: assignment.jobId,
    leaseId: assignment.leaseId,
    leaseEpoch: assignment.leaseEpoch,
    attemptId,
    leaseCapability: assignment.leaseCapability,
  };
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map(async (db) => await db.close()));
});

describe("capture worker lease lifecycle", () => {
  it("persists claim and attempt start before authorizing browser launch", async () => {
    const { db, service } = await harness();
    const jobId = await queuedJob(service);

    const claimed = await service.claimLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "claim_lease",
      clientRequestId: randomUUID(),
      workerInstallationId: WORKER_ID,
      supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
    });
    validateWorkerMessage(claimed);
    expect(claimed.assignment).toMatchObject({
      jobId,
      leaseEpoch: 1,
      attemptId: null,
      exactRequestedUrl: "https://capture.example.org/story?edition=public",
      profile: {
        render: {
          viewportWidth: 1920,
          viewportHeight: 1080,
          deviceScaleFactor: 2,
        },
      },
    });
    const leaseRows = await db.query<{
      capability_jti_digest: Uint8Array;
      capability_scope_digest: Uint8Array;
    }>("SELECT capability_jti_digest, capability_scope_digest FROM capture_leases");
    expect(leaseRows.rows[0]?.capability_jti_digest).toBeInstanceOf(Uint8Array);
    expect(leaseRows.rows[0]?.capability_scope_digest).toBeInstanceOf(Uint8Array);
    const storedText = JSON.stringify(
      (await db.query("SELECT * FROM capture_leases")).rows,
    );
    expect(storedText).not.toContain(claimed.assignment.leaseCapability);
    expect(storedText).not.toContain(claimed.assignment.commitNonce);

    const started = await service.startAttempt({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "start_attempt",
      clientRequestId: randomUUID(),
      lease: proof(claimed.assignment, null),
      cleanProfileId: randomUUID(),
      browserBuild: "chromium-test-1",
      adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
      securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
    });
    validateWorkerMessage(started);
    expect(started.browserLaunchAuthorized).toBe(true);
    expect(
      await db.query(
        "SELECT attempt_id, state FROM capture_attempts WHERE job_id = $1",
        [jobId],
      ),
    ).toMatchObject({
      rows: [{ attempt_id: started.attemptId, state: "started" }],
    });
  }, 20_000);

  it("allows only one simultaneous lease claim to win a queued job", async () => {
    const { db, service } = await harness();
    const jobId = await queuedJob(service);
    const claim = () =>
      service.claimLease({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "claim_lease",
        clientRequestId: randomUUID(),
        workerInstallationId: WORKER_ID,
        supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
      });

    const results = await Promise.allSettled([claim(), claim()]);
    const winner = results.find(
      (result): result is PromiseFulfilledResult<
        Awaited<ReturnType<typeof claim>>
      > => result.status === "fulfilled",
    );
    const loser = results.find(
      (result): result is PromiseRejectedResult => result.status === "rejected",
    );

    expect(winner?.value.assignment.jobId).toBe(jobId);
    expect(loser?.reason).toMatchObject({
      code: "capture_worker_unavailable",
      retryable: true,
    });
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_leases WHERE job_id = $1) AS leases,
           (SELECT state FROM capture_jobs WHERE job_id = $1) AS job_state`,
        [jobId],
      ),
    ).toMatchObject({ rows: [{ leases: 1, job_state: "leased" }] });
  }, 20_000);

  it("records navigation, renews, and issues single-use scoped staging grants", async () => {
    const { clock, service } = await harness();
    await queuedJob(service);
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
      lease: proof(claimed.assignment, null),
      cleanProfileId: randomUUID(),
      browserBuild: "chromium-test-1",
      adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
      securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
    });
    const activeProof = proof(claimed.assignment, started.attemptId);
    const job = await service.getJob(
      PROJECT_ID,
      claimed.assignment.jobId,
      PRINCIPAL,
    );
    const capture = await service.getCapture(
      PROJECT_ID,
      job.job.captureId,
      PRINCIPAL,
    );
    const navigation = await service.recordNavigationStart({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "record_navigation_start",
      clientRequestId: randomUUID(),
      lease: activeProof,
      navigationStartedAt: clock.now().toISOString(),
      initialUrlDigest: capture.capture.configuration.requestedUrl.canonicalDigest,
    });
    validateWorkerMessage(navigation);

    clock.advance(4_000);
    const renewed = await service.renewLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "renew_lease",
      clientRequestId: randomUUID(),
      lease: activeProof,
    });
    validateWorkerMessage(renewed);
    expect(new Date(renewed.expiresAt).getTime()).toBeGreaterThan(
      new Date(claimed.assignment.expiresAt).getTime(),
    );

    const grants = await service.requestStagingGrants({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "request_staging_grants",
      clientRequestId: randomUUID(),
      lease: activeProof,
      purposes: ["raster", "provenance"],
    });
    validateWorkerMessage(grants);
    expect(grants.grants.map(({ purpose }) => purpose)).toEqual([
      "raster",
      "provenance",
    ]);
    const provenanceGrant = grants.grants[1];
    const staged = await service.stageObject(
      provenanceGrant.rawGrant,
      WORKER_ID,
      Buffer.from("{}"),
    );
    expect(staged).toMatchObject({
      attemptId: started.attemptId,
      purpose: "provenance",
      mimeType: "application/json",
    });
    await expect(
      service.stageObject(
        provenanceGrant.rawGrant,
        WORKER_ID,
        Buffer.from("{}"),
      ),
    ).rejects.toMatchObject({ code: "invalid_or_expired_job_capability" });
  }, 20_000);

  it("expires a lost lease, abandons its attempt, and advances the epoch", async () => {
    const { clock, db, service } = await harness();
    const jobId = await queuedJob(service);
    const first = await service.claimLease({
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
      lease: proof(first.assignment, null),
      cleanProfileId: randomUUID(),
      browserBuild: "chromium-test-1",
      adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
      securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
    });
    const staleProof = proof(first.assignment, started.attemptId);

    clock.advance(CAPTURE_PROFILE_V1.limits.leaseMilliseconds);
    const second = await service.claimLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "claim_lease",
      clientRequestId: randomUUID(),
      workerInstallationId: WORKER_ID,
      supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
    });

    expect(second.assignment).toMatchObject({ jobId, leaseEpoch: 2 });
    expect(second.assignment.leaseId).not.toBe(first.assignment.leaseId);
    expect(
      await db.query(
        `SELECT state, terminal_code
           FROM capture_attempts
          WHERE project_id = $1 AND attempt_id = $2`,
        [PROJECT_ID, started.attemptId],
      ),
    ).toMatchObject({
      rows: [{ state: "abandoned", terminal_code: "lease_expired" }],
    });
    expect(
      await db.query(
        `SELECT epoch, state
           FROM capture_leases
          WHERE project_id = $1 AND job_id = $2
          ORDER BY epoch`,
        [PROJECT_ID, jobId],
      ),
    ).toMatchObject({
      rows: [
        { epoch: 1, state: "expired" },
        { epoch: 2, state: "issued" },
      ],
    });
    await expect(
      service.renewLease({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "renew_lease",
        clientRequestId: randomUUID(),
        lease: staleProof,
      }),
    ).rejects.toMatchObject({ code: "job_not_committable" });
  }, 20_000);

  it("does not reveal whether a tampered lease names a real job", async () => {
    const { service } = await harness();
    await queuedJob(service);
    const claimed = await service.claimLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "claim_lease",
      clientRequestId: randomUUID(),
      workerInstallationId: WORKER_ID,
      supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
    });
    const validLease = proof(claimed.assignment, null);
    const lease: LeaseProof = {
      ...validLease,
      leaseCapability: `${validLease.leaseCapability.slice(0, -1)}x`,
    };

    await expect(
      service.startAttempt({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "start_attempt",
        clientRequestId: randomUUID(),
        lease,
        cleanProfileId: randomUUID(),
        browserBuild: "chromium-test-1",
        adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
        securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
      }),
    ).rejects.toMatchObject({
      code: "invalid_or_expired_job_capability",
      safeMessage: "The worker capability is invalid or expired.",
    });
  }, 20_000);
});
