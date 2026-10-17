import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import type {
  AuthorizationDecisionRef,
  CommitAttemptRequest,
  CommitAttemptResponse,
  DraftOccurrenceReference,
  LeaseAssignment,
  LeaseProof,
  PrincipalRef,
} from "@vera/contracts";

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
} from "./authorization.js";
import { CapabilitySigner, sha256 } from "./crypto.js";
import {
  applyPublicCaptureMigration,
  SingleClientCaptureDatabase,
} from "./database.js";
import { RestrictedRequestCipher } from "./envelope.js";
import { CaptureServiceError } from "./errors.js";
import { MemoryImmutableObjectStore } from "./object-store.js";
import {
  type DnsResolver,
  type PinnedTransport,
  PublicEgressGuard,
  type TransportRequest,
  type TransportResponse,
} from "./policy.js";
import {
  CAPTURE_PROFILE_V1,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "./profile.js";
import { CaptureService } from "./service.js";
import {
  type CaptureWorkerProtocolPort,
  LocalPublicPageCaptureWorker,
} from "./worker.js";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const PRINCIPAL: PrincipalRef = {
  principalKind: "user",
  principalId: "dddddddd-dddd-4ddd-8ddd-ddddddddddd2",
};
const WORKER_ID = "18181818-1818-4818-8818-181818181818";

class AcceptanceClock {
  private value = new Date("2026-09-08T20:00:00.000Z");

  readonly now = (): Date => new Date(this.value);

  advance(milliseconds: number): void {
    this.value = new Date(this.value.getTime() + milliseconds);
  }
}

class SyntheticResolver implements DnsResolver {
  resolve(host: string): Promise<readonly { address: string; family: 4 }[]> {
    return Promise.resolve([
      {
        address:
          host === "blocked.example.org" ? "127.0.0.1" : "93.184.216.34",
        family: 4,
      },
    ]);
  }
}

class SyntheticTransport implements PinnedTransport {
  contentVersion: "baseline" | "changed" = "baseline";
  privateRedirect = false;
  requestCount = 0;

  request(request: TransportRequest): Promise<TransportResponse> {
    this.requestCount += 1;
    const { pathname } = request.url;
    const redirect =
      this.privateRedirect &&
      request.host === "unsafe.example.org" &&
      pathname === "/story";
    const content =
      this.contentVersion === "baseline"
        ? "Synthetic public capture baseline"
        : "Synthetic public capture changed";
    const body =
      pathname === "/asset.txt"
        ? "synthetic asset"
        : pathname === "/frame"
          ? "<!doctype html><html><body>Guarded synthetic frame</body></html>"
          : `<!doctype html><html><head><title>${content}</title></head>
             <body style="margin:0;background:#fff;color:#111;font-family:sans-serif">
               <h1>${content}</h1>
               <iframe src="/frame"></iframe><img src="/asset.txt">
               <script>
                 document.cookie = "attempt=ephemeral";
                 localStorage.setItem("acceptance", "ephemeral");
               </script>
             </body></html>`;
    return Promise.resolve({
      status: redirect ? 302 : 200,
      headers: redirect
        ? { location: "https://blocked.example.org/internal" }
        : {
            "content-type":
              pathname === "/asset.txt" ? "text/plain" : "text/html",
          },
      body: Buffer.from(redirect ? "" : body, "utf8"),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "unavailable",
        protocol: null,
        cipher: null,
        peerCertificateSha256: null,
        unavailableReason: "Synthetic transport opened no socket.",
      },
    });
  }
}

class LostCommitResponseProtocol implements CaptureWorkerProtocolPort {
  commitCalls = 0;
  committedResponse: CommitAttemptResponse | null = null;
  request: CommitAttemptRequest | null = null;
  private readonly service: CaptureService;

  constructor(service: CaptureService) {
    this.service = service;
  }

  abandonAttempt(
    request: Parameters<CaptureService["abandonAttempt"]>[0],
  ): ReturnType<CaptureService["abandonAttempt"]> {
    return this.service.abandonAttempt(request);
  }

  claimLease(
    request: Parameters<CaptureService["claimLease"]>[0],
  ): ReturnType<CaptureService["claimLease"]> {
    return this.service.claimLease(request);
  }

  async commitAttempt(request: CommitAttemptRequest): Promise<CommitAttemptResponse> {
    this.commitCalls += 1;
    this.request = request;
    this.committedResponse = await this.service.commitAttempt(request);
    throw new Error("Synthetic commit response was lost.");
  }

  failAttempt(
    request: Parameters<CaptureService["failAttempt"]>[0],
  ): ReturnType<CaptureService["failAttempt"]> {
    return this.service.failAttempt(request);
  }

  recordNavigationStart(
    request: Parameters<CaptureService["recordNavigationStart"]>[0],
  ): ReturnType<CaptureService["recordNavigationStart"]> {
    return this.service.recordNavigationStart(request);
  }

  renewLease(
    request: Parameters<CaptureService["renewLease"]>[0],
  ): ReturnType<CaptureService["renewLease"]> {
    return this.service.renewLease(request);
  }

  requestStagingGrants(
    request: Parameters<CaptureService["requestStagingGrants"]>[0],
  ): ReturnType<CaptureService["requestStagingGrants"]> {
    return this.service.requestStagingGrants(request);
  }

  stageObject(
    rawGrant: string,
    workerInstallationId: string,
    bytes: Buffer,
  ): ReturnType<CaptureService["stageObject"]> {
    return this.service.stageObject(rawGrant, workerInstallationId, bytes);
  }

  startAttempt(
    request: Parameters<CaptureService["startAttempt"]>[0],
  ): ReturnType<CaptureService["startAttempt"]> {
    return this.service.startAttempt(request);
  }
}

function ensure(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Acceptance failed: ${message}`);
}

function errorCode(error: unknown): string {
  return error instanceof CaptureServiceError ? error.code : "unexpected_error";
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

function captureWorker(
  protocol: CaptureWorkerProtocolPort,
  clock: AcceptanceClock,
  resolver: DnsResolver,
  transport: PinnedTransport,
): LocalPublicPageCaptureWorker {
  return new LocalPublicPageCaptureWorker({
    protocol,
    guardFactory: (profile) =>
      new PublicEgressGuard(resolver, transport, {
        maxDnsAnswers: profile.limits.dnsAnswers,
        maxRedirects: profile.limits.redirects,
        maxResponseBytes: profile.limits.responseBytes,
        timeoutMilliseconds: profile.limits.navigationMilliseconds,
      }),
    runtime: {
      browserBuild: "chromium-playwright-1.63",
      evidenceClass: "synthetic",
      installationId: WORKER_ID,
      os: "synthetic-acceptance",
      resolverName: "synthetic-no-socket-v1",
      sandbox: "synthetic_fixture",
      workerBuildDigest: sha256("issue-39-synthetic-acceptance-worker"),
      workerBuildId: "issue-39-synthetic-acceptance-worker",
    },
    delay: () => Promise.resolve(),
    now: clock.now,
  });
}

async function createCapture(
  service: CaptureService,
  requestedUrl: string,
): Promise<Awaited<ReturnType<CaptureService["createCapture"]>>> {
  return await service.createCapture(
    {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "create_capture",
      projectId: PROJECT_ID,
      clientRequestId: randomUUID(),
      idempotencyKey: randomUUID(),
      requestedUrl,
      regionIntent: { kind: "full_viewport" },
      acquisitionPolicy: { kind: "now" },
      captureProfileId: CAPTURE_PROFILE_V1.profileId,
      captureProfileVersion: CAPTURE_PROFILE_V1.profileVersion,
    },
    PRINCIPAL,
  );
}

async function queueCapture(
  service: CaptureService,
  captureId: string,
  expectedCaptureRowVersion: number,
  idempotencyKey: string,
): Promise<{
  readonly request: Parameters<CaptureService["requestCaptureJob"]>[0];
  readonly response: Awaited<ReturnType<CaptureService["requestCaptureJob"]>>;
}> {
  const request: Parameters<CaptureService["requestCaptureJob"]>[0] = {
    schemaVersion: "public-page-capture-api/v1",
    messageType: "request_capture_job",
    projectId: PROJECT_ID,
    captureId,
    clientRequestId: randomUUID(),
    idempotencyKey,
    expectedCaptureRowVersion,
    trigger: {
      kind: "now",
      commandId: randomUUID(),
      selectionIntent: { kind: "none" },
    },
  };
  return { request, response: await service.requestCaptureJob(request, PRINCIPAL) };
}

export async function runAcceptance(): Promise<void> {
  const database = new PGlite();
  await database.waitReady;
  try {
    await applyPublicCaptureMigration(database);
    await database.query(
      `UPDATE public_page_capture_settings
          SET enabled = true
        WHERE setting_name = 'public_page_capture_execution'`,
    );
    const clock = new AcceptanceClock();
    const objects = new MemoryImmutableObjectStore();
    const authorization: ProjectAuthorizationPort = {
      authorize(projectId, principal, action): Promise<AuthorizationDecisionRef> {
        return Promise.resolve({
          decisionId: randomUUID(),
          action,
          principal,
          projectId,
          role: "producer",
          membershipVersion: 1,
          decidedAt: clock.now().toISOString(),
          recheckMode:
            action === "capture_commit" ? "commit_time" : "every_request",
        });
      },
    };
    const references: AuthoringReferencePort = {
      validate: () => Promise.resolve(),
    };
    const service = new CaptureService({
      authorization,
      capabilities: new CapabilitySigner(Buffer.alloc(32, 2)),
      cipher: new RestrictedRequestCipher(Buffer.alloc(32, 1)),
      database: new SingleClientCaptureDatabase(database),
      denialFingerprintKey: Buffer.alloc(32, 3),
      objects,
      references,
      workerAuthorization: {
        authorize(workerInstallationId): Promise<void> {
          return workerInstallationId === WORKER_ID
            ? Promise.resolve()
            : Promise.reject(new Error("Unknown synthetic worker."));
        },
      },
      now: clock.now,
    });
    const resolver = new SyntheticResolver();
    const transport = new SyntheticTransport();

    const safeCapture = await createCapture(
      service,
      "https://capture.example.org/story?edition=public",
    );
    const initialJob = await queueCapture(
      service,
      safeCapture.capture.captureId,
      safeCapture.capture.rowVersion,
      "acceptance-safe-initial-0001",
    );
    const duplicate = await service.requestCaptureJob(
      initialJob.request,
      PRINCIPAL,
    );
    ensure(
      duplicate.job.jobId === initialJob.response.job.jobId &&
        duplicate.job.duplicateDelivery,
      "duplicate delivery did not recover the original job",
    );

    const initial = await captureWorker(
      service,
      clock,
      resolver,
      transport,
    ).runOnce();
    ensure(initial.kind === "committed", "initial capture did not commit");
    ensure(
      initial.response.revision.artifact.width === OUTPUT_WIDTH &&
        initial.response.revision.artifact.height === OUTPUT_HEIGHT,
      "initial raster was not 3840x2160",
    );

    let currentCapture = await service.getCapture(
      PROJECT_ID,
      safeCapture.capture.captureId,
      PRINCIPAL,
    );
    await queueCapture(
      service,
      safeCapture.capture.captureId,
      currentCapture.capture.rowVersion,
      "acceptance-safe-same-0002",
    );
    const same = await captureWorker(
      service,
      clock,
      resolver,
      transport,
    ).runOnce();
    ensure(same.kind === "committed", "same-byte recapture did not commit");
    ensure(
      same.response.revision.changeSignal.signal === "same_exact_bytes" &&
        same.response.revision.artifact.artifactId ===
          initial.response.revision.artifact.artifactId,
      "same bytes did not reuse the immutable raster artifact",
    );

    transport.contentVersion = "changed";
    currentCapture = await service.getCapture(
      PROJECT_ID,
      safeCapture.capture.captureId,
      PRINCIPAL,
    );
    await queueCapture(
      service,
      safeCapture.capture.captureId,
      currentCapture.capture.rowVersion,
      "acceptance-safe-changed-0003",
    );
    const changed = await captureWorker(
      service,
      clock,
      resolver,
      transport,
    ).runOnce();
    ensure(changed.kind === "committed", "changed recapture did not commit");
    ensure(
      changed.response.revision.changeSignal.signal === "different_exact_bytes" &&
        changed.response.revision.artifact.artifactId !==
          same.response.revision.artifact.artifactId,
      "changed bytes did not create a distinct immutable raster artifact",
    );

    const target: DraftOccurrenceReference = {
      projectId: PROJECT_ID,
      kind: "draft_occurrence",
      resourceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc2",
      resourceVersionDigest: `sha256:${"cd".repeat(32)}`,
      occurrenceId: "cccccccc-cccc-4ccc-8ccc-ccccccccccc3",
    };
    const pin = await service.addExplicitPin(
      {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "add_explicit_pin",
        projectId: PROJECT_ID,
        revisionId: initial.response.revision.revisionId,
        clientRequestId: randomUUID(),
        idempotencyKey: "acceptance-explicit-pin-0001",
        source: target,
      },
      PRINCIPAL,
    );
    await service.selectRevision(
      {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "select_revision",
        projectId: PROJECT_ID,
        revisionId: initial.response.revision.revisionId,
        clientRequestId: randomUUID(),
        idempotencyKey: "acceptance-selection-0001",
        target,
        expectedPreviousSelectionId: null,
        reason: "manual",
        requiredUseDecisionId: null,
      },
      PRINCIPAL,
    );
    await service.releaseExplicitPin(
      {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "release_explicit_pin",
        projectId: PROJECT_ID,
        pinId: pin.effectId,
        clientRequestId: randomUUID(),
        idempotencyKey: "acceptance-explicit-release-0001",
        reason: "Synthetic acceptance release preserves selection protection.",
      },
      PRINCIPAL,
    );
    const protections = await database.query<{
      reason: string;
      released: boolean;
    }>(
      `SELECT p.reason,
              EXISTS (
                SELECT 1 FROM capture_protection_releases r
                 WHERE r.project_id = p.project_id
                   AND r.protection_id = p.protection_id
              ) AS released
         FROM capture_revision_protections p
        WHERE p.project_id = $1 AND p.revision_id = $2
        ORDER BY p.reason`,
      [PROJECT_ID, initial.response.revision.revisionId],
    );
    ensure(
      protections.rows.some(
        ({ reason, released }) => reason === "draft_selection" && !released,
      ) &&
        protections.rows.some(
          ({ reason, released }) => reason === "explicit_pin" && released,
        ),
      "releasing an explicit pin did not preserve selection protection",
    );

    transport.contentVersion = "baseline";
    transport.privateRedirect = true;
    const unsafeCapture = await createCapture(
      service,
      "https://unsafe.example.org/story",
    );
    await queueCapture(
      service,
      unsafeCapture.capture.captureId,
      unsafeCapture.capture.rowVersion,
      "acceptance-unsafe-redirect-0001",
    );
    const unsafe = await captureWorker(
      service,
      clock,
      resolver,
      transport,
    ).runOnce();
    ensure(
      unsafe.kind === "failed" &&
        unsafe.denial.code === "dns_not_public" &&
        !unsafe.isolation.browserLaunched &&
        !unsafe.isolation.navigationStarted &&
        unsafe.isolation.realConnectionCount === 0,
      "private redirect was not denied before browser navigation",
    );
    const unsafeCounts = await database.query<{
      revisions: number;
      terminal_evidence: number;
    }>(
      `SELECT
         (SELECT count(*)::int FROM capture_revisions
           WHERE project_id = $1 AND capture_id = $2) AS revisions,
         (SELECT count(*)::int FROM capture_provenance_manifests
           WHERE project_id = $1 AND capture_id = $2
             AND evidence_type = 'terminal_attempt_evidence') AS terminal_evidence`,
      [PROJECT_ID, unsafeCapture.capture.captureId],
    );
    ensure(
      unsafeCounts.rows[0]?.revisions === 0 &&
        unsafeCounts.rows[0]?.terminal_evidence === 1,
      "unsafe denial published output or omitted terminal evidence",
    );

    transport.privateRedirect = false;
    const recoveryCapture = await createCapture(
      service,
      "https://recovery.example.org/story",
    );
    const recoveryJob = await queueCapture(
      service,
      recoveryCapture.capture.captureId,
      recoveryCapture.capture.rowVersion,
      "acceptance-recovery-0001",
    );
    const stale = await service.claimLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "claim_lease",
      clientRequestId: randomUUID(),
      workerInstallationId: WORKER_ID,
      supportedProfileDigests: [CAPTURE_PROFILE_V1.profileDigest],
    });
    const staleAttempt = await service.startAttempt({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "start_attempt",
      clientRequestId: randomUUID(),
      lease: proof(stale.assignment, null),
      cleanProfileId: randomUUID(),
      browserBuild: "chromium-playwright-1.63",
      adapterVersion: CAPTURE_PROFILE_V1.adapterVersion,
      securityPolicyVersion: CAPTURE_PROFILE_V1.securityPolicyVersion,
    });
    const staleProof = proof(stale.assignment, staleAttempt.attemptId);
    clock.advance(CAPTURE_PROFILE_V1.limits.leaseMilliseconds);

    const lostProtocol = new LostCommitResponseProtocol(service);
    let workerObservedLostResponse = false;
    try {
      await captureWorker(
        lostProtocol,
        clock,
        resolver,
        transport,
      ).runOnce();
    } catch {
      workerObservedLostResponse = true;
    }
    ensure(
      workerObservedLostResponse &&
        lostProtocol.commitCalls === 1 &&
        lostProtocol.request !== null &&
        lostProtocol.committedResponse !== null,
      "the synthetic lost-response boundary was not reached exactly once",
    );
    const recovered = await service.commitAttempt({
      ...lostProtocol.request,
      clientRequestId: randomUUID(),
    });
    ensure(
      recovered.recoveredExistingOutcome &&
        recovered.revision.revisionId ===
          lostProtocol.committedResponse.revision.revisionId,
      "lost commit response did not recover the stored revision",
    );
    let staleError = "none";
    try {
      await service.renewLease({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "renew_lease",
        clientRequestId: randomUUID(),
        lease: staleProof,
      });
    } catch (error) {
      staleError = errorCode(error);
    }
    ensure(
      staleError === "job_not_committable",
      "the stale lease epoch remained usable after recovery",
    );
    const recoveryCounts = await database.query<{
      abandoned_attempts: number;
      committed_attempts: number;
      revisions: number;
    }>(
      `SELECT
         (SELECT count(*)::int FROM capture_revisions
           WHERE project_id = $1 AND capture_id = $2) AS revisions,
         (SELECT count(*)::int FROM capture_attempts
           WHERE project_id = $1 AND capture_id = $2
             AND state = 'abandoned' AND terminal_code = 'lease_expired')
           AS abandoned_attempts,
         (SELECT count(*)::int FROM capture_attempts
           WHERE project_id = $1 AND capture_id = $2 AND state = 'committed')
           AS committed_attempts`,
      [PROJECT_ID, recoveryCapture.capture.captureId],
    );
    ensure(
      recoveryCounts.rows[0]?.revisions === 1 &&
        recoveryCounts.rows[0]?.abandoned_attempts === 1 &&
        recoveryCounts.rows[0]?.committed_attempts === 1 &&
        recovered.job.jobId === recoveryJob.response.job.jobId,
      "lease-loss recovery did not retain one abandoned attempt and one winner",
    );

    const audit = await service.getAuditEvents(
      PROJECT_ID,
      safeCapture.capture.captureId,
      PRINCIPAL,
    );
    const rasterCount = await database.query<{ count: number }>(
      `SELECT count(*)::int AS count
         FROM capture_artifacts
        WHERE project_id = $1 AND kind = 'capture_raster'`,
      [PROJECT_ID],
    );
    ensure(
      initial.isolation.initialCookieCount === 0 &&
        initial.isolation.finalCookieCount === 0 &&
        initial.isolation.persistedStateDiscarded &&
        !initial.isolation.importedState &&
        initial.isolation.realConnectionCount === 0,
      "the disposable browser retained or imported ambient state",
    );

    process.stdout.write(
      `${JSON.stringify(
        {
          acceptance: "issue-39-public-page-capture",
          status: "passed",
          profile: {
            cssViewport: "1920x1080",
            deviceScaleFactor: 2,
            raster: `${OUTPUT_WIDTH}x${OUTPUT_HEIGHT}`,
          },
          transport: {
            evidenceClass: "synthetic",
            tlsEvidence: "unavailable",
            realSocketsOpened: 0,
            guardedRequests: transport.requestCount,
          },
          safeCapture: {
            duplicateDeliveryRecovered: true,
            revisionNumbers: [
              initial.response.revision.revisionNumber,
              same.response.revision.revisionNumber,
              changed.response.revision.revisionNumber,
            ],
            changeSignals: [
              initial.response.revision.changeSignal.signal,
              same.response.revision.changeSignal.signal,
              changed.response.revision.changeSignal.signal,
            ],
            exactRasterReuse: true,
            changedRasterCreated: true,
            immutableRasterArtifacts: rasterCount.rows[0]?.count,
            auditEvents: audit.events.length,
            zeroAmbientState: true,
          },
          unsafeRedirect: {
            deniedCode: unsafe.kind === "failed" ? unsafe.denial.code : null,
            browserLaunched: false,
            navigationStarted: false,
            revisionsPublished: 0,
            terminalEvidence: 1,
          },
          recovery: {
            expiredEpoch: stale.assignment.leaseEpoch,
            winningEpoch: lostProtocol.request.lease.leaseEpoch,
            abandonedAttempts: 1,
            committedAttempts: 1,
            revisionsPublished: 1,
            lateEpochDenied: staleError,
            storedCommitRecovered: recovered.recoveredExistingOutcome,
            browserCommitCalls: lostProtocol.commitCalls,
          },
          appendOnlyHistory: {
            explicitPinReleased: true,
            selectionProtectionPreserved: true,
          },
        },
        null,
        2,
      )}\n`,
    );
  } finally {
    await database.close();
  }
}
