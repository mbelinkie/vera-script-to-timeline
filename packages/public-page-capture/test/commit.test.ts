import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type {
  AuthorizationDecisionRef,
  CommitAttemptResponse,
  DraftOccurrenceReference,
  LeaseAssignment,
  LeaseProof,
  PrincipalRef,
  PublicPageCaptureProvenanceV1,
  StagedObjectDescriptor,
} from "@vera/contracts";
import { PNG } from "pngjs";
import { afterEach, describe, expect, it } from "vitest";

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
} from "../src/authorization.js";
import { validateProvenance, validateWorkerMessage } from "../src/contracts.js";
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
import { CaptureServiceError } from "../src/errors.js";
import { captureConfigurationVersionId } from "../src/identities.js";
import { MemoryImmutableObjectStore } from "../src/object-store.js";
import {
  CAPTURE_PROFILE_V1,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "../src/profile.js";
import { CaptureService } from "../src/service.js";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const WORKER_ID = "18181818-1818-4818-8818-181818181818";
const PRINCIPAL: PrincipalRef = {
  principalKind: "user",
  principalId: "dddddddd-dddd-4ddd-8ddd-ddddddddddd2",
};
const FIXTURE = JSON.parse(
  readFileSync(
    new URL(
      "../../../tests/data/issue_39_public_page_capture/provenance-revision-observation.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as PublicPageCaptureProvenanceV1;
const TERMINAL_FIXTURE = JSON.parse(
  readFileSync(
    new URL(
      "../../../tests/data/issue_39_public_page_capture/provenance-terminal-denial.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as PublicPageCaptureProvenanceV1;
const databases: PGlite[] = [];

/* eslint-disable @typescript-eslint/require-await -- Test doubles implement async ports. */

const authorization: ProjectAuthorizationPort = {
  async authorize(projectId, principal, action): Promise<AuthorizationDecisionRef> {
    return {
      decisionId: randomUUID(),
      action,
      principal,
      projectId,
      role: "producer",
      membershipVersion: 1,
      decidedAt: "2026-09-08T16:00:05.000Z",
      recheckMode: action === "capture_commit" ? "commit_time" : "every_request",
    };
  },
};

const references: AuthoringReferencePort = {
  validate: async () => undefined,
};

interface Harness {
  readonly db: PGlite;
  readonly objects: MemoryImmutableObjectStore;
  readonly service: CaptureService;
}

async function harness(
  now: () => Date = () => new Date("2026-09-08T16:00:05.000Z"),
  projectAuthorization: ProjectAuthorizationPort = authorization,
): Promise<Harness> {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyPublicCaptureMigration(db);
  await db.query(
    `UPDATE public_page_capture_settings SET enabled = true
      WHERE setting_name = 'public_page_capture_execution'`,
  );
  const objects = new MemoryImmutableObjectStore();
  const service = new CaptureService({
    authorization: projectAuthorization,
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
    now,
  });
  return { db, objects, service };
}

function raster(red = 255): Buffer {
  const png = new PNG({ width: OUTPUT_WIDTH, height: OUTPUT_HEIGHT, colorType: 6 });
  png.data.fill(255);
  png.data[0] = red;
  return PNG.sync.write(png, { colorType: 6 });
}

function proof(assignment: LeaseAssignment, attemptId: string | null): LeaseProof {
  return {
    workerInstallationId: WORKER_ID,
    jobId: assignment.jobId,
    leaseId: assignment.leaseId,
    leaseEpoch: assignment.leaseEpoch,
    attemptId,
    leaseCapability: assignment.leaseCapability,
  };
}

async function createCapture(service: CaptureService): Promise<string> {
  const result = await service.createCapture(
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
  return result.capture.captureId;
}

async function queue(
  service: CaptureService,
  captureId: string,
  expectedCaptureRowVersion: number,
): Promise<void> {
  await service.requestCaptureJob(
    {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "request_capture_job",
      projectId: PROJECT_ID,
      captureId,
      clientRequestId: randomUUID(),
      idempotencyKey: randomUUID(),
      expectedCaptureRowVersion,
      trigger: {
        kind: "now",
        commandId: randomUUID(),
        selectionIntent: { kind: "none" },
      },
    },
    PRINCIPAL,
  );
}

function provenanceBytes(
  assignment: LeaseAssignment,
  attemptId: string,
  revisionId: string,
  rasterBytes: Buffer,
  warningCodes: readonly string[] = [],
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
  value.honesty.warnings = warningCodes.map((code) => ({
    code,
    message: "A bounded browser capability or resource was blocked.",
  }));
  value.honesty.classification = warningCodes.length === 0 ? "complete" : "partial";
  value.honesty.partialReason =
    warningCodes.length === 0 ? null : "Capture warnings require explicit review.";
  if (value.change) value.change.reviewRequired = warningCodes.length > 0;
  return Buffer.from(canonicalJson(value as unknown as JsonValue), "utf8");
}

function terminalBytes(
  assignment: LeaseAssignment,
  attemptId: string,
  terminalCode: string,
): Buffer {
  const value = structuredClone(TERMINAL_FIXTURE);
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
    revisionId: null,
  };
  value.request.triggerKind = "now";
  value.request.settingsDigest = assignment.settingsDigest;
  value.request.captureProfileDigest = assignment.profile.profileDigest;
  value.runtime.installationId = WORKER_ID;
  value.terminal = {
    outcome: "denied",
    code: terminalCode,
    sanitizedMessage: "The capture attempt was denied by public-only policy.",
    phase: "dns",
    retryable: false,
    navigationStarted: false,
    leaseDisposition: "consumed",
  };
  return Buffer.from(
    canonicalJson(value as unknown as JsonValue),
    "utf8",
  );
}

async function stageForCommit(
  service: CaptureService,
  rasterBytes: Buffer,
  warningCodes: readonly string[] = [],
): Promise<{
  readonly assignment: LeaseAssignment;
  readonly proof: LeaseProof;
  readonly request: Parameters<CaptureService["commitAttempt"]>[0];
}> {
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
  const lease = proof(claimed.assignment, started.attemptId);
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
  const revisionId = randomUUID();
  const stagedProvenance = await service.stageObject(
    grants.grants[1].rawGrant,
    WORKER_ID,
    provenanceBytes(
      claimed.assignment,
      started.attemptId,
      revisionId,
      rasterBytes,
      warningCodes,
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
  const request: Parameters<CaptureService["commitAttempt"]>[0] = {
    schemaVersion: "public-page-capture-worker/v1",
    messageType: "commit_attempt",
    clientRequestId: randomUUID(),
    lease,
    commitNonce: claimed.assignment.commitNonce,
    raster: rasterDescriptor,
    provenanceObject: provenanceDescriptor,
    warningCodes: [...warningCodes],
    reviewClassification: warningCodes.length === 0 ? "ready" : "review_required",
  };
  return { assignment: claimed.assignment, proof: lease, request };
}

async function runAndCommit(
  service: CaptureService,
  rasterBytes: Buffer,
  warningCodes: readonly string[] = [],
): Promise<{
  readonly assignment: LeaseAssignment;
  readonly proof: LeaseProof;
  readonly response: CommitAttemptResponse;
  readonly request: Parameters<CaptureService["commitAttempt"]>[0];
}> {
  const staged = await stageForCommit(service, rasterBytes, warningCodes);
  const response = await service.commitAttempt(staged.request);
  return { ...staged, response };
}

afterEach(async () => {
  await Promise.all(databases.splice(0).map(async (db) => await db.close()));
});

describe("atomic capture commit", () => {
  it("publishes one complete 4K revision and recovers a lost response", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    await queue(service, captureId, 1);

    const committed = await runAndCommit(service, raster());
    validateWorkerMessage(committed.response);
    expect(committed.response).toMatchObject({
      recoveredExistingOutcome: false,
      job: { state: "committed_ready" },
      revision: {
        captureId,
        revisionNumber: 1,
        status: "ready",
        artifact: { width: 3840, height: 2160, mimeType: "image/png" },
        changeSignal: { signal: "initial_observation" },
      },
    });
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revisions) AS revisions,
           (SELECT count(*)::int FROM capture_change_signals) AS changes,
           (SELECT count(*)::int FROM capture_provenance_manifests) AS provenance`,
      ),
    ).toMatchObject({ rows: [{ revisions: 1, changes: 1, provenance: 1 }] });

    const recovered = await service.commitAttempt({
      ...committed.request,
      clientRequestId: randomUUID(),
    });
    expect(recovered).toMatchObject({
      recoveredExistingOutcome: true,
      revision: { revisionId: committed.response.revision.revisionId },
    });
    expect(
      await db.query("SELECT count(*)::int AS count FROM capture_revisions"),
    ).toMatchObject({ rows: [{ count: 1 }] });
  }, 60_000);

  it("rechecks the initiating principal at commit and publishes nothing after role removal", async () => {
    let denyCommit = false;
    const revocable: ProjectAuthorizationPort = {
      async authorize(projectId, principal, action): Promise<AuthorizationDecisionRef> {
        if (denyCommit && action === "capture_commit") {
          throw new CaptureServiceError(
            "action_not_allowed",
            "The initiating principal no longer has capture commit authority.",
          );
        }
        return {
          decisionId: randomUUID(),
          action,
          principal,
          projectId,
          role: "producer",
          membershipVersion: denyCommit ? 2 : 1,
          decidedAt: "2026-09-08T16:00:05.000Z",
          recheckMode:
            action === "capture_commit" ? "commit_time" : "every_request",
        };
      },
    };
    const { db, service } = await harness(undefined, revocable);
    const captureId = await createCapture(service);
    await queue(service, captureId, 1);
    const staged = await stageForCommit(service, raster());

    denyCommit = true;
    await expect(service.commitAttempt(staged.request)).rejects.toMatchObject({
      code: "action_not_allowed",
    });
    const counts = await db.query<{
      artifacts: number;
      changes: number;
      provenance: number;
      revisions: number;
    }>(
      `SELECT
         (SELECT count(*)::int FROM capture_artifacts) AS artifacts,
         (SELECT count(*)::int FROM capture_change_signals) AS changes,
         (SELECT count(*)::int FROM capture_provenance_manifests) AS provenance,
         (SELECT count(*)::int FROM capture_revisions) AS revisions`,
    );
    expect(counts.rows).toEqual([
      { artifacts: 0, changes: 0, provenance: 0, revisions: 0 },
    ]);
  }, 60_000);

  it("rejects a late epoch after a replacement attempt wins the job", async () => {
    let currentTime = new Date("2026-09-08T16:00:05.000Z");
    const { db, service } = await harness(() => new Date(currentTime));
    const captureId = await createCapture(service);
    await queue(service, captureId, 1);
    const stale = await stageForCommit(service, raster());

    currentTime = new Date(
      currentTime.getTime() + CAPTURE_PROFILE_V1.limits.leaseMilliseconds,
    );
    const winner = await runAndCommit(service, raster(0));

    expect(winner.assignment.leaseEpoch).toBe(2);
    await expect(service.commitAttempt(stale.request)).rejects.toMatchObject({
      code: "job_not_committable",
    });
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revisions) AS revisions,
           (SELECT count(*)::int FROM capture_attempts
             WHERE state = 'committed') AS committed_attempts,
           (SELECT count(*)::int FROM capture_attempts
             WHERE state = 'abandoned' AND terminal_code = 'lease_expired')
             AS abandoned_attempts`,
      ),
    ).toMatchObject({
      rows: [
        { revisions: 1, committed_attempts: 1, abandoned_attempts: 1 },
      ],
    });
  }, 90_000);

  it("creates a new observation while reusing exact raster bytes", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    const bytes = raster();
    await queue(service, captureId, 1);
    const first = await runAndCommit(service, bytes);
    await queue(service, captureId, 2);

    const second = await runAndCommit(service, bytes);

    expect(second.response.revision).toMatchObject({
      revisionNumber: 2,
      changeSignal: {
        signal: "same_exact_bytes",
        baselineRevisionId: first.response.revision.revisionId,
      },
      artifact: { artifactId: first.response.revision.artifact.artifactId },
    });
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revisions) AS revisions,
           (SELECT count(*)::int FROM capture_artifacts
             WHERE kind = 'capture_raster') AS rasters,
           (SELECT count(*)::int FROM capture_provenance_manifests) AS provenance`,
      ),
    ).toMatchObject({ rows: [{ revisions: 2, rasters: 1, provenance: 2 }] });
  }, 90_000);

  it("serializes simultaneous same-byte commits into two observations and one artifact", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    const bytes = raster();
    await queue(service, captureId, 1);
    await queue(service, captureId, 1);
    const first = await stageForCommit(service, bytes);
    const second = await stageForCommit(service, bytes);

    const committed = await Promise.all([
      service.commitAttempt(first.request),
      service.commitAttempt(second.request),
    ]);

    expect(committed.map(({ revision }) => revision.revisionNumber).sort()).toEqual([
      1, 2,
    ]);
    expect(committed[0].revision.artifact.artifactId).toBe(
      committed[1].revision.artifact.artifactId,
    );
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revisions) AS revisions,
           (SELECT count(*)::int FROM capture_artifacts
             WHERE kind = 'capture_raster') AS rasters,
           (SELECT count(*)::int FROM capture_attempts
             WHERE state = 'committed') AS committed_attempts`,
      ),
    ).toMatchObject({
      rows: [{ revisions: 2, rasters: 1, committed_attempts: 2 }],
    });
  }, 120_000);

  it("keeps selection and protection history append-only while gating reads", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    const rasterBytes = raster();
    await queue(service, captureId, 1);
    const committed = await runAndCommit(service, rasterBytes);
    const revisionId = committed.response.revision.revisionId;
    const target: DraftOccurrenceReference = {
      projectId: PROJECT_ID,
      kind: "draft_occurrence",
      resourceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc2",
      resourceVersionDigest: `sha256:${"cd".repeat(32)}`,
      occurrenceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc3",
    };

    await expect(
      service.readRasterArtifact(PROJECT_ID, revisionId, target, PRINCIPAL),
    ).rejects.toMatchObject({ code: "resource_not_found" });

    const pinRequest = {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "add_explicit_pin",
      projectId: PROJECT_ID,
      revisionId,
      clientRequestId: randomUUID(),
      idempotencyKey: "explicit-pin-0001",
      source: target,
    } as const;
    const pin = await service.addExplicitPin(pinRequest, PRINCIPAL);
    expect(pin.duplicateDelivery).toBe(false);
    expect(
      await service.addExplicitPin(pinRequest, PRINCIPAL),
    ).toMatchObject({ effectId: pin.effectId, duplicateDelivery: true });

    const rasterRead = await service.readRasterArtifact(
      PROJECT_ID,
      revisionId,
      target,
      PRINCIPAL,
    );
    expect(rasterRead.bytes).toEqual(rasterBytes);
    expect(rasterRead.descriptor).toMatchObject({
      artifactId: committed.response.revision.artifact.artifactId,
      accessClass: "project_visual",
      width: 3840,
      height: 2160,
    });
    expect(JSON.stringify(rasterRead.descriptor)).not.toContain("objectStore");
    const provenanceRead = await service.readRestrictedProvenance(
      PROJECT_ID,
      revisionId,
      target,
      PRINCIPAL,
    );
    const provenance: unknown = JSON.parse(provenanceRead.bytes.toString("utf8"));
    validateProvenance(provenance);
    expect(provenance).toMatchObject({
      identity: { projectId: PROJECT_ID, revisionId },
      recordType: "revision_observation",
    });

    const selection = await service.selectRevision(
      {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "select_revision",
        projectId: PROJECT_ID,
        revisionId,
        clientRequestId: randomUUID(),
        idempotencyKey: "selection-0001",
        target,
        expectedPreviousSelectionId: null,
        reason: "manual",
        requiredUseDecisionId: null,
      },
      PRINCIPAL,
    );
    await expect(
      service.selectRevision(
        {
          schemaVersion: "public-page-capture-api/v1",
          messageType: "select_revision",
          projectId: PROJECT_ID,
          revisionId,
          clientRequestId: randomUUID(),
          idempotencyKey: "selection-0002",
          target,
          expectedPreviousSelectionId: null,
          reason: "manual",
          requiredUseDecisionId: null,
        },
        PRINCIPAL,
      ),
    ).rejects.toMatchObject({ code: "selection_conflict" });

    const releaseRequest = {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "release_explicit_pin",
      projectId: PROJECT_ID,
      pinId: pin.effectId,
      clientRequestId: randomUUID(),
      idempotencyKey: "explicit-pin-release-0001",
      reason: "Producer no longer needs the explicit pin.",
    } as const;
    const release = await service.releaseExplicitPin(releaseRequest, PRINCIPAL);
    expect(
      await service.releaseExplicitPin(releaseRequest, PRINCIPAL),
    ).toMatchObject({ effectId: release.effectId, duplicateDelivery: true });
    expect(
      await service.readRasterArtifact(
        PROJECT_ID,
        revisionId,
        target,
        PRINCIPAL,
      ),
    ).toMatchObject({ bytes: rasterBytes });
    expect(
      await db.query(
        `SELECT p.reason,
                EXISTS (
                  SELECT 1 FROM capture_protection_releases r
                   WHERE r.project_id = p.project_id
                     AND r.protection_id = p.protection_id
                ) AS released
           FROM capture_revision_protections p
          WHERE p.project_id = $1 AND p.revision_id = $2
          ORDER BY p.reason`,
        [PROJECT_ID, revisionId],
      ),
    ).toMatchObject({
      rows: [
        { reason: "draft_selection", released: false },
        { reason: "explicit_pin", released: true },
      ],
    });
    expect(selection.effectId).not.toBe(pin.effectId);
  }, 90_000);

  it("requires a target-matched use decision before selecting review output", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    await queue(service, captureId, 1);
    const committed = await runAndCommit(service, raster(), ["blocked_web_font"]);
    const revisionId = committed.response.revision.revisionId;
    const target = {
      projectId: PROJECT_ID,
      kind: "preview_build",
      resourceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc4",
      resourceVersionDigest: `sha256:${"ce".repeat(32)}`,
    } as const;
    const selection = {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "select_revision",
      projectId: PROJECT_ID,
      revisionId,
      clientRequestId: randomUUID(),
      idempotencyKey: "review-selection-0001",
      target,
      expectedPreviousSelectionId: null,
      reason: "manual",
      requiredUseDecisionId: null,
    } as const;

    expect(committed.response.revision.status).toBe("review_required");
    await expect(service.selectRevision(selection, PRINCIPAL)).rejects.toMatchObject({
      code: "revision_requires_review",
    });
    const decisionRequest = {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "record_revision_use_decision",
      projectId: PROJECT_ID,
      revisionId,
      clientRequestId: randomUUID(),
      idempotencyKey: "review-decision-0001",
      context: target,
      decision: "preview_acknowledged",
    } as const;
    const decision = await service.recordRevisionUseDecision(
      decisionRequest,
      PRINCIPAL,
    );
    expect(
      await service.recordRevisionUseDecision(decisionRequest, PRINCIPAL),
    ).toMatchObject({ effectId: decision.effectId, duplicateDelivery: true });
    const selected = await service.selectRevision(
      { ...selection, requiredUseDecisionId: decision.effectId },
      PRINCIPAL,
    );

    expect(selected.duplicateDelivery).toBe(false);
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revision_use_decisions) AS decisions,
           (SELECT count(*)::int FROM capture_revision_selections) AS selections,
           (SELECT count(*)::int FROM capture_revision_protections
             WHERE reason = 'preview_build') AS protections`,
      ),
    ).toMatchObject({
      rows: [{ decisions: 1, selections: 1, protections: 1 }],
    });
  }, 90_000);

  it("publishes terminal evidence without creating a revision", async () => {
    const { db, service } = await harness();
    const captureId = await createCapture(service);
    await queue(service, captureId, 1);
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
    const lease = proof(claimed.assignment, started.attemptId);
    const grants = await service.requestStagingGrants({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "request_staging_grants",
      clientRequestId: randomUUID(),
      lease,
      purposes: ["raster", "provenance"],
    });
    const staged = await service.stageObject(
      grants.grants[1].rawGrant,
      WORKER_ID,
      terminalBytes(claimed.assignment, started.attemptId, "blocked_destination"),
    );
    const request: Parameters<CaptureService["failAttempt"]>[0] = {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "fail_attempt",
      clientRequestId: randomUUID(),
      lease,
      terminalCode: "blocked_destination",
      navigationStarted: false,
      retryable: false,
      terminalEvidenceObject: {
        stagingObjectId: staged.stagingObjectId,
        grantId: staged.grantId,
        purpose: "provenance",
        digest: staged.digest,
        byteLength: staged.byteLength,
        mimeType: "application/json",
        encoding: "json",
      },
    };

    const failed = await service.failAttempt(request);
    validateWorkerMessage(failed);
    expect(failed).toMatchObject({
      attemptId: started.attemptId,
      jobId: claimed.assignment.jobId,
      jobState: "failed",
    });
    expect(
      await db.query(
        `SELECT
           (SELECT count(*)::int FROM capture_revisions) AS revisions,
           (SELECT count(*)::int FROM capture_provenance_manifests
             WHERE evidence_type = 'terminal_attempt_evidence') AS terminal_evidence`,
      ),
    ).toMatchObject({ rows: [{ revisions: 0, terminal_evidence: 1 }] });
    const duplicate = await service.failAttempt({
      ...request,
      clientRequestId: randomUUID(),
    });
    expect(duplicate).toMatchObject({
      attemptId: started.attemptId,
      jobState: "failed",
    });
  }, 60_000);
});
