import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

import type {
  AbandonAttemptRequest,
  AbandonAttemptResponse,
  CaptureJobView,
  CaptureRevisionView,
  ClaimLeaseResponse,
  CommitAttemptRequest,
  CommitAttemptResponse,
  FailAttemptRequest,
  FailAttemptResponse,
  LeaseAssignment,
  RecordNavigationStartRequest,
  RecordNavigationStartResponse,
  RenewLeaseRequest,
  RenewLeaseResponse,
  RequestStagingGrantsRequest,
  RequestStagingGrantsResponse,
  StartAttemptRequest,
  StartAttemptResponse,
} from "@vera/contracts";
import { describe, expect, it } from "vitest";

import { validateProvenance } from "../src/contracts.js";
import { sha256 } from "../src/crypto.js";
import type { StagedObject } from "../src/object-store.js";
import {
  PublicEgressGuard,
  type DnsResolver,
  type PinnedTransport,
  type TransportRequest,
  type TransportResponse,
} from "../src/policy.js";
import {
  CAPTURE_PROFILE_V1,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "../src/profile.js";
import { verifyPng } from "../src/raster.js";
import {
  LocalPublicPageCaptureWorker,
  type CaptureWorkerProtocolPort,
} from "../src/worker.js";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const CAPTURE_ID = "22222222-2222-4222-8222-222222222222";
const JOB_ID = "44444444-4444-4444-8444-444444444441";
const LEASE_ID = "44444444-4444-4444-8444-444444444442";
const ATTEMPT_ID = "55555555-5555-4555-8555-555555555551";
const WORKER_ID = "18181818-1818-4818-8818-181818181818";
const NOW = new Date("2026-09-08T19:00:00.000Z");

const readyRevision = JSON.parse(
  readFileSync(
    new URL(
      "../../../tests/data/issue_39_public_page_capture/api-ready-revision.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as { readonly revision: CaptureRevisionView };
const readyJob = JSON.parse(
  readFileSync(
    new URL(
      "../../../tests/data/issue_39_public_page_capture/api-duplicate-recovery.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as { readonly job: CaptureJobView };

function assignment(url = "https://capture.example.org/story"): LeaseAssignment {
  return {
    projectId: PROJECT_ID,
    captureId: CAPTURE_ID,
    configurationVersion: 1,
    jobId: JOB_ID,
    leaseId: LEASE_ID,
    leaseEpoch: 1,
    attemptId: null,
    leaseCapability: "signed-test-lease-capability",
    capabilityJtiDigest: `sha256:${"11".repeat(32)}`,
    capabilityScopeDigest: `sha256:${"12".repeat(32)}`,
    commitNonce: "commit-nonce-test",
    issuedAt: NOW.toISOString(),
    expiresAt: new Date(NOW.getTime() + 30_000).toISOString(),
    exactRequestedUrl: url,
    settingsDigest: `sha256:${"33".repeat(32)}`,
    profile: CAPTURE_PROFILE_V1,
  };
}

class FixtureProtocol implements CaptureWorkerProtocolPort {
  readonly events: string[] = [];
  readonly staged = new Map<string, Buffer>();
  readonly cleanProfileIds: string[] = [];
  committedProvenance: unknown;
  committedRaster: Buffer | null = null;
  failedProvenance: unknown;

  constructor(private readonly claimedAssignment: LeaseAssignment) {}

  claimLease(): Promise<ClaimLeaseResponse> {
    this.events.push("claim");
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "lease_claimed",
      requestId: randomUUID(),
      assignment: this.claimedAssignment,
    });
  }

  startAttempt(request: StartAttemptRequest): Promise<StartAttemptResponse> {
    this.events.push("start");
    this.cleanProfileIds.push(request.cleanProfileId);
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_started",
      requestId: request.clientRequestId,
      attemptId: ATTEMPT_ID,
      jobId: JOB_ID,
      leaseId: LEASE_ID,
      leaseEpoch: 1,
      startedAt: NOW.toISOString(),
      browserLaunchAuthorized: true,
    });
  }

  recordNavigationStart(
    request: RecordNavigationStartRequest,
  ): Promise<RecordNavigationStartResponse> {
    this.events.push("navigate");
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "navigation_start_recorded",
      requestId: request.clientRequestId,
      attemptId: ATTEMPT_ID,
      recordedAt: NOW.toISOString(),
    });
  }

  renewLease(request: RenewLeaseRequest): Promise<RenewLeaseResponse> {
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "lease_renewed",
      requestId: request.clientRequestId,
      leaseId: LEASE_ID,
      leaseEpoch: 1,
      expiresAt: new Date(NOW.getTime() + 30_000).toISOString(),
      renewedAt: NOW.toISOString(),
    });
  }

  requestStagingGrants(
    request: RequestStagingGrantsRequest,
  ): Promise<RequestStagingGrantsResponse> {
    const issuedAt = NOW.toISOString();
    const expiresAt = new Date(NOW.getTime() + 10_000).toISOString();
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "staging_grants_issued",
      requestId: request.clientRequestId,
      grants: [
        {
          grantId: randomUUID(),
          purpose: "raster",
          rawGrant: "fixture-raster-grant",
          grantDigest: `sha256:${"41".repeat(32)}`,
          attemptId: ATTEMPT_ID,
          leaseEpoch: 1,
          maxBytes: CAPTURE_PROFILE_V1.limits.rasterBytes,
          mimeType: "image/png",
          issuedAt,
          expiresAt,
        },
        {
          grantId: randomUUID(),
          purpose: "provenance",
          rawGrant: "fixture-provenance-grant",
          grantDigest: `sha256:${"42".repeat(32)}`,
          attemptId: ATTEMPT_ID,
          leaseEpoch: 1,
          maxBytes: CAPTURE_PROFILE_V1.limits.rasterBytes,
          mimeType: "application/json",
          issuedAt,
          expiresAt,
        },
      ],
    });
  }

  stageObject(
    rawGrant: string,
    _workerInstallationId: string,
    bytes: Buffer,
  ): Promise<StagedObject> {
    const purpose = rawGrant.includes("raster") ? "raster" : "provenance";
    const stagingObjectId = randomUUID();
    this.staged.set(stagingObjectId, Buffer.from(bytes));
    return Promise.resolve({
      stagingObjectId,
      grantId: randomUUID(),
      projectId: PROJECT_ID,
      jobId: JOB_ID,
      attemptId: ATTEMPT_ID,
      leaseEpoch: 1,
      purpose,
      mimeType: purpose === "raster" ? "image/png" : "application/json",
      byteLength: bytes.byteLength,
      digest: sha256(bytes),
    });
  }

  commitAttempt(request: CommitAttemptRequest): Promise<CommitAttemptResponse> {
    this.events.push("commit");
    this.committedRaster = this.staged.get(request.raster.stagingObjectId) ?? null;
    const provenance = this.staged.get(
      request.provenanceObject.stagingObjectId,
    );
    this.committedProvenance = provenance
      ? JSON.parse(provenance.toString("utf8"))
      : null;
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_committed",
      requestId: request.clientRequestId,
      job: { ...readyJob.job, jobId: JOB_ID, captureId: CAPTURE_ID },
      revision: {
        ...readyRevision.revision,
        jobId: JOB_ID,
        captureId: CAPTURE_ID,
      },
      recoveredExistingOutcome: false,
    });
  }

  failAttempt(request: FailAttemptRequest): Promise<FailAttemptResponse> {
    this.events.push("fail");
    const provenance = this.staged.get(
      request.terminalEvidenceObject.stagingObjectId,
    );
    this.failedProvenance = provenance
      ? JSON.parse(provenance.toString("utf8"))
      : null;
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_failed",
      requestId: request.clientRequestId,
      jobId: JOB_ID,
      attemptId: ATTEMPT_ID,
      jobState: "failed",
      recordedAt: NOW.toISOString(),
    });
  }

  abandonAttempt(
    request: AbandonAttemptRequest,
  ): Promise<AbandonAttemptResponse> {
    return Promise.resolve({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_abandoned",
      requestId: request.clientRequestId,
      jobId: JOB_ID,
      attemptId: ATTEMPT_ID,
      recordedAt: NOW.toISOString(),
    });
  }
}

class FixtureResolver implements DnsResolver {
  constructor(private readonly blocked = false) {}

  resolve(host: string): Promise<readonly { address: string; family: 4 }[]> {
    return Promise.resolve([
      {
        address:
          this.blocked && host === "blocked.example.org"
            ? "127.0.0.1"
            : "93.184.216.34",
        family: 4,
      },
    ]);
  }
}

class FixtureTransport implements PinnedTransport {
  readonly requests: TransportRequest[] = [];

  constructor(private readonly redirectToPrivate = false) {}

  request(request: TransportRequest): Promise<TransportResponse> {
    this.requests.push(request);
    const path = request.url.pathname;
    const html =
      path === "/frame"
        ? "<!doctype html><html><body>Guarded frame</body></html>"
        : `<!doctype html><html><head><title>Synthetic public story</title></head>
           <body style="margin:0;background:#fff;color:#111">
             <h1>VERA synthetic capture</h1>
             <iframe src="/frame"></iframe><img src="/asset.txt">
             <script>document.cookie='attempt=ephemeral'; localStorage.setItem('x','1');</script>
           </body></html>`;
    const redirect = this.redirectToPrivate && path === "/story";
    return Promise.resolve({
      status: redirect ? 302 : 200,
      headers: redirect
        ? { location: "https://blocked.example.org/internal" }
        : {
            "content-type": path === "/asset.txt" ? "text/plain" : "text/html",
          },
      body: Buffer.from(path === "/asset.txt" ? "asset" : html, "utf8"),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "not_applicable",
        protocol: null,
        cipher: null,
        peerCertificateSha256: null,
        unavailableReason: "Synthetic transport opened no socket.",
      },
    });
  }
}

function worker(
  protocol: FixtureProtocol,
  resolver: DnsResolver,
  transport: PinnedTransport,
): LocalPublicPageCaptureWorker {
  return new LocalPublicPageCaptureWorker({
    protocol,
    guardFactory: (profile) => {
      expect(protocol.events).toEqual(["claim", "start"]);
      return new PublicEgressGuard(resolver, transport, {
        maxDnsAnswers: profile.limits.dnsAnswers,
        maxRedirects: profile.limits.redirects,
        maxResponseBytes: profile.limits.responseBytes,
        timeoutMilliseconds: profile.limits.navigationMilliseconds,
      });
    },
    runtime: {
      browserBuild: "chromium-fixture",
      evidenceClass: "synthetic",
      installationId: WORKER_ID,
      os: "test",
      resolverName: "synthetic-fixture-v1",
      sandbox: "process",
      workerBuildDigest: `sha256:${"17".repeat(32)}`,
      workerBuildId: "capture-worker-test",
    },
    delay: () => Promise.resolve(),
    now: () => new Date(NOW),
  });
}

describe("LocalPublicPageCaptureWorker browser boundary", () => {
  it("renders a guarded isolated synthetic page as a 3840x2160 PNG", async () => {
    const protocol = new FixtureProtocol(assignment());
    const transport = new FixtureTransport();

    const result = await worker(
      protocol,
      new FixtureResolver(),
      transport,
    ).runOnce();

    expect(result.kind).toBe("committed");
    expect(result.isolation).toEqual({
      browserLaunched: true,
      directNetworkFallback: false,
      finalCookieCount: 0,
      importedState: false,
      initialCookieCount: 0,
      navigationStarted: true,
      persistedStateDiscarded: true,
      realConnectionCount: 0,
    });
    const committedRaster = protocol.committedRaster;
    expect(committedRaster).not.toBeNull();
    if (!committedRaster) throw new Error("Expected a committed raster.");
    expect(
      verifyPng(committedRaster, {
        expectedWidth: OUTPUT_WIDTH,
        expectedHeight: OUTPUT_HEIGHT,
        maxBytes: CAPTURE_PROFILE_V1.limits.rasterBytes,
        maxPixels: CAPTURE_PROFILE_V1.limits.outputPixels,
      }),
    ).toMatchObject({ width: 3840, height: 2160 });
    validateProvenance(protocol.committedProvenance);
    expect(protocol.committedProvenance).toMatchObject({
      network: {
        actualConnectionCount: 0,
        evidenceClass: "synthetic",
      },
      runtime: {
        browser: "chromium",
        finalCookieCount: 0,
        importedState: false,
        initialCookieCount: 0,
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 2,
      },
      output: { width: 3840, height: 2160 },
    });
    expect(transport.requests.map(({ url }) => url.pathname)).toEqual(
      expect.arrayContaining(["/story", "/frame", "/asset.txt"]),
    );
  }, 30_000);

  it("denies a redirect to a private peer before Chromium launches", async () => {
    const protocol = new FixtureProtocol(assignment());
    const transport = new FixtureTransport(true);

    const result = await worker(
      protocol,
      new FixtureResolver(true),
      transport,
    ).runOnce();

    expect(result).toMatchObject({
      kind: "failed",
      denial: { code: "dns_not_public", navigationStarted: false, phase: "dns" },
      isolation: {
        browserLaunched: false,
        navigationStarted: false,
        realConnectionCount: 0,
      },
    });
    expect(transport.requests).toHaveLength(1);
    validateProvenance(protocol.failedProvenance);
    expect(protocol.events).toEqual(["claim", "start", "fail"]);
  }, 20_000);
});
