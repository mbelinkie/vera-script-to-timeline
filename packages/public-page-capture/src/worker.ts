import { randomUUID } from "node:crypto";
import { performance } from "node:perf_hooks";

import type {
  AbandonAttemptResponse,
  CaptureProfileV1,
  CommitAttemptResponse,
  FailAttemptResponse,
  LeaseAssignment,
  LeaseProof,
  PublicPageCaptureProvenanceV1,
  StagedObjectDescriptor,
  StagingGrant,
} from "@vera/contracts";
import {
  chromium,
  type Browser,
  type BrowserContext,
  type Page,
  type Route,
} from "playwright";

import { validateProvenance } from "./contracts.js";
import { canonicalJson, sha256, type JsonValue } from "./crypto.js";
import { captureConfigurationVersionId } from "./identities.js";
import type { StagedObject } from "./object-store.js";
import {
  CaptureDenied,
  inspectPublicUrl,
  PublicEgressGuard,
  type GuardedResponse,
} from "./policy.js";
import {
  CAPTURE_PROFILE_V1_DIGEST,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "./profile.js";
import type { CaptureService } from "./service.js";

export type CaptureWorkerProtocolPort = Pick<
  CaptureService,
  | "abandonAttempt"
  | "claimLease"
  | "commitAttempt"
  | "failAttempt"
  | "recordNavigationStart"
  | "renewLease"
  | "requestStagingGrants"
  | "stageObject"
  | "startAttempt"
>;

export interface CaptureWorkerRuntime {
  readonly browserBuild: string;
  readonly evidenceClass: "live" | "synthetic";
  readonly installationId: string;
  readonly os: string;
  readonly resolverName: string;
  readonly sandbox: "container" | "process" | "synthetic_fixture";
  readonly workerBuildDigest: string;
  readonly workerBuildId: string;
}

export interface LocalCaptureWorkerDependencies {
  readonly guardFactory: (profile: CaptureProfileV1) => PublicEgressGuard;
  readonly protocol: CaptureWorkerProtocolPort;
  readonly runtime: CaptureWorkerRuntime;
  readonly browserType?: typeof chromium;
  readonly delay?: (milliseconds: number) => Promise<void>;
  readonly id?: () => string;
  readonly now?: () => Date;
}

export interface WorkerIsolationReceipt {
  readonly browserLaunched: boolean;
  readonly directNetworkFallback: false;
  readonly finalCookieCount: 0;
  readonly importedState: false;
  readonly initialCookieCount: 0;
  readonly navigationStarted: boolean;
  readonly persistedStateDiscarded: true;
  readonly realConnectionCount: number;
}

export type CaptureWorkerRunResult =
  | {
      readonly kind: "committed";
      readonly response: CommitAttemptResponse;
      readonly isolation: WorkerIsolationReceipt;
    }
  | {
      readonly kind: "failed";
      readonly response: FailAttemptResponse | AbandonAttemptResponse;
      readonly denial: {
        readonly code: string;
        readonly navigationStarted: boolean;
        readonly phase: CaptureDenied["phase"];
      };
      readonly isolation: WorkerIsolationReceipt;
    };

interface BrowserObservation {
  readonly raster: Buffer;
  readonly title: string | null;
  readonly warnings: readonly string[];
}

interface NetworkObservation {
  readonly frames: readonly JsonValue[];
  readonly responses: readonly GuardedResponse[];
  readonly subresources: readonly JsonValue[];
  readonly topLevel: GuardedResponse;
}

interface RouteCounters {
  frameRequests: number;
  subresourceRequests: number;
  topLevelRequests: number;
  totalBytes: number;
  totalRequests: number;
}

interface BrowserRouteState {
  consumedTopLevel: boolean;
  readonly counters: RouteCounters;
  readonly diagnostics: JsonValue[];
  fatal: CaptureDenied | null;
  readonly frames: JsonValue[];
  readonly responses: GuardedResponse[];
  readonly subresources: JsonValue[];
  tail: Promise<void>;
  readonly warnings: Set<string>;
}

const blockedCapabilities = [
  "downloads",
  "file_access",
  "forms",
  "local_network",
  "permissions",
  "popups",
  "printing",
  "web_rtc",
  "web_sockets",
  "write_clipboard",
] as const;

function leaseProof(
  assignment: LeaseAssignment,
  workerInstallationId: string,
  attemptId: string | null,
): LeaseProof {
  return {
    workerInstallationId,
    jobId: assignment.jobId,
    leaseId: assignment.leaseId,
    leaseEpoch: assignment.leaseEpoch,
    attemptId,
    leaseCapability: assignment.leaseCapability,
  };
}

function stagedDescriptor(staged: StagedObject): StagedObjectDescriptor {
  if (staged.purpose === "raster") {
    return {
      stagingObjectId: staged.stagingObjectId,
      grantId: staged.grantId,
      purpose: "raster",
      digest: staged.digest,
      byteLength: staged.byteLength,
      mimeType: "image/png",
      width: OUTPUT_WIDTH,
      height: OUTPUT_HEIGHT,
      encoding: "png",
      color: "srgb",
      alpha: "opaque",
    };
  }
  return {
    stagingObjectId: staged.stagingObjectId,
    grantId: staged.grantId,
    purpose: "provenance",
    digest: staged.digest,
    byteLength: staged.byteLength,
    mimeType: "application/json",
    encoding: "json",
  };
}

function grantFor(
  grants: readonly StagingGrant[],
  purpose: "provenance" | "raster",
): StagingGrant {
  const grant = grants.find((candidate) => candidate.purpose === purpose);
  if (!grant) throw new Error(`Missing ${purpose} staging grant.`);
  return grant;
}

function safeTitle(value: string): string | null {
  const normalized = value
    // eslint-disable-next-line no-control-regex -- Strip C0 and DEL from untrusted titles.
    .replace(/[\u0000-\u001f\u007f]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 512);
  return normalized || null;
}

function safeResponseHeaders(
  headers: Readonly<Record<string, string>>,
): Record<string, string> {
  const blocked = new Set([
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
  ]);
  return Object.fromEntries(
    Object.entries(headers).filter(([name]) => !blocked.has(name.toLowerCase())),
  );
}

function routeKind(route: Route): "frame" | "subresource" | "top_level" {
  const request = route.request();
  if (!request.isNavigationRequest()) return "subresource";
  try {
    return request.frame().parentFrame() === null ? "top_level" : "frame";
  } catch {
    return "subresource";
  }
}

function routeFrameDepth(route: Route): number {
  let depth = 0;
  try {
    let frame = route.request().frame().parentFrame();
    while (frame) {
      depth += 1;
      frame = frame.parentFrame();
    }
    return depth;
  } catch {
    return Number.MAX_SAFE_INTEGER;
  }
}

function workerAuthorization(
  runtime: CaptureWorkerRuntime,
  decisionId: string,
  at: Date,
): PublicPageCaptureProvenanceV1["authorization"] {
  return {
    principal: {
      principalKind: "service",
      principalId: runtime.installationId,
    },
    role: "service",
    action: "capture.commit",
    decisionId,
    decision: "allowed",
    decidedAt: at.toISOString(),
    commitRecheck: true,
    originReference: null,
  };
}

function workerRequest(
  assignment: LeaseAssignment,
  at: Date,
): PublicPageCaptureProvenanceV1["request"] {
  const inspected = inspectPublicUrl(assignment.exactRequestedUrl);
  return {
    triggerKind: "now",
    requestedUrl: inspected.canonicalUrl,
    redactedRequestedUrl: inspected.redactedUrl,
    requestedUrlDigest: sha256(inspected.canonicalUrl),
    requestedUrlFingerprint: sha256(inspected.canonicalUrl).replace(
      "sha256:",
      "hmac-sha256:",
    ),
    queryKeyNames: [...inspected.queryKeys],
    settingsDigest: assignment.settingsDigest,
    captureProfileId: "vera-public-page-capture-v1",
    captureProfileDigest: assignment.profile.profileDigest,
    regionIntent: { kind: "full_viewport" },
    idempotencyScopeDigest: sha256(assignment.jobId),
    idempotencyKeyDigest: sha256(assignment.leaseId),
    requestedAt: assignment.issuedAt,
    enqueuedAt: at.toISOString(),
  };
}

function runtimeRecord(
  runtime: CaptureWorkerRuntime,
  profile: CaptureProfileV1,
  cleanProfileId: string,
): PublicPageCaptureProvenanceV1["runtime"] {
  return {
    workerBuildId: runtime.workerBuildId,
    workerBuildDigest: runtime.workerBuildDigest,
    installationId: runtime.installationId,
    os: runtime.os,
    sandbox: runtime.sandbox,
    browser: "chromium",
    browserVersion: runtime.browserBuild,
    adapterVersion: profile.adapterVersion,
    policyDigest: profile.profileDigest,
    cleanProfileId,
    importedState: false,
    initialCookieCount: 0,
    finalCookieCount: 0,
    persistedStateDiscarded: true,
    javascriptMode: profile.render.javaScript,
    locale: "en-US",
    timezone: "UTC",
    userAgentProfile: "vera-public-page-capture-v1",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
    colorProfile: "srgb",
    outputFormat: "png",
    blockedCapabilities: [...blockedCapabilities],
  };
}

interface RevisionProvenanceInput {
  readonly assignment: LeaseAssignment;
  readonly attemptId: string;
  readonly cleanProfileId: string;
  readonly decisionId: string;
  readonly finishedAt: Date;
  readonly network: NetworkObservation;
  readonly observation: BrowserObservation;
  readonly revisionId: string;
  readonly runtime: CaptureWorkerRuntime;
  readonly startedMonotonic: number;
}

interface TerminalProvenanceInput {
  readonly assignment: LeaseAssignment;
  readonly attemptId: string;
  readonly cleanProfileId: string;
  readonly decisionId: string;
  readonly denial: CaptureDenied;
  readonly finishedAt: Date;
  readonly runtime: CaptureWorkerRuntime;
  readonly startedMonotonic: number;
}

function elapsedMilliseconds(startedMonotonic: number): number {
  return Math.max(0, Math.round(performance.now() - startedMonotonic));
}

function revisionNetwork(
  input: RevisionProvenanceInput,
): PublicPageCaptureProvenanceV1["network"] {
  const { finishedAt, network, observation, runtime } = input;
  const top = network.topLevel;
  const dnsAdmissions = network.responses
    .flatMap((response) => response.trace.dnsAdmissions)
    .slice(0, 128)
    .map((admission) => ({
      host: admission.host,
      resolver: runtime.resolverName,
      resolvedAt: finishedAt.toISOString(),
      answers: admission.answers.map((answer) => ({ ...answer })),
      admitted: admission.admitted,
    }));
  const peerConnections =
    runtime.evidenceClass === "synthetic"
      ? []
      : network.responses
          .flatMap((response) => response.trace.peerConnections)
          .slice(0, 512)
          .map((peer) => ({
            ...peer,
            addressClass: "public" as const,
            connectedAt: finishedAt.toISOString(),
          }));
  return {
    evidenceClass: runtime.evidenceClass,
    dnsAdmissions,
    peerConnections,
    tls: top.trace.tls,
    redirectChain: top.trace.redirectChain.map((hop) => ({
      sequence: hop.sequence,
      url: hop.canonicalUrl,
      redactedUrl: hop.redactedUrl,
      urlDigest: sha256(hop.canonicalUrl),
      status: hop.status,
      locationDigest: null,
      admitted: hop.admitted,
    })) as PublicPageCaptureProvenanceV1["network"]["redirectChain"],
    finalUrl: top.finalUrl,
    redactedFinalUrl: top.redactedFinalUrl,
    response: {
      status: top.status,
      contentType: top.headers["content-type"] ?? null,
      contentLength: top.body.byteLength,
      title: observation.title,
      headerDigest: sha256(top.headers),
    },
    frameManifestDigest: sha256(network.frames),
    subresourceManifestDigest: sha256(network.subresources),
    actualConnectionCount: peerConnections.length,
    denial: null,
  } as unknown as PublicPageCaptureProvenanceV1["network"];
}

function provenanceTiming(
  assignment: LeaseAssignment,
  runtime: CaptureWorkerRuntime,
  finishedAt: Date,
  durationMilliseconds: number,
  terminal: boolean,
): PublicPageCaptureProvenanceV1["timing"] {
  return {
    serverStartedAt: assignment.issuedAt,
    workerStartedAt: assignment.issuedAt,
    workerFinishedAt: finishedAt.toISOString(),
    durationMilliseconds,
    settleOutcome: terminal ? "not_reached" : "quiet_window",
    settleMilliseconds: terminal
      ? 0
      : assignment.profile.stability.settleMilliseconds,
    navigationDeadlineMilliseconds:
      assignment.profile.limits.navigationMilliseconds,
    jobDeadlineMilliseconds:
      assignment.profile.stability.hardDeadlineMilliseconds,
    retryNumber: assignment.leaseEpoch - 1,
    retryBudget: 2,
    leaseHistory: [
      {
        event: "claimed",
        leaseEpoch: assignment.leaseEpoch,
        at: assignment.issuedAt,
        deadline: assignment.expiresAt,
        workerInstallationId: runtime.installationId,
      },
      {
        event: terminal ? "failed" : "started",
        leaseEpoch: assignment.leaseEpoch,
        at: finishedAt.toISOString(),
        deadline: assignment.expiresAt,
        workerInstallationId: runtime.installationId,
      },
    ],
    milestones: [
      {
        name: "lease_claimed",
        wallAt: assignment.issuedAt,
        monotonicMilliseconds: 0,
      },
      {
        name: terminal ? "terminal" : "rasterized",
        wallAt: finishedAt.toISOString(),
        monotonicMilliseconds: durationMilliseconds,
      },
    ],
    captureInstant: terminal ? null : finishedAt.toISOString(),
  };
}

function buildRevisionProvenance(
  input: RevisionProvenanceInput,
): PublicPageCaptureProvenanceV1 {
  const {
    assignment,
    attemptId,
    cleanProfileId,
    decisionId,
    finishedAt,
    observation,
    revisionId,
    runtime,
    startedMonotonic,
  } = input;
  const duration = elapsedMilliseconds(startedMonotonic);
  const warnings = observation.warnings.map((code) => ({
    code,
    message: "The capture policy blocked or bounded a page behavior.",
  }));
  const value = {
    schemaVersion: "public-page-capture-provenance/v1",
    recordType: "revision_observation",
    identity: {
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
    },
    authorization: workerAuthorization(runtime, decisionId, finishedAt),
    request: workerRequest(assignment, finishedAt),
    network: revisionNetwork(input),
    runtime: runtimeRecord(runtime, assignment.profile, cleanProfileId),
    timing: provenanceTiming(
      assignment,
      runtime,
      finishedAt,
      duration,
      false,
    ),
    output: {
      raster: {
        artifactId: randomUUID(),
        digest: sha256(observation.raster),
        byteLength: observation.raster.byteLength,
        mediaType: "image/png",
      },
      encoding: "png",
      width: OUTPUT_WIDTH,
      height: OUTPUT_HEIGHT,
      capturedRegion: {
        x: 0,
        y: 0,
        width: OUTPUT_WIDTH,
        height: OUTPUT_HEIGHT,
      },
      decoder: "pngjs-7",
      byteIdentity: "new_raster",
      baselineRevisionId: null,
      reusedRasterArtifactId: null,
      stagedAt: finishedAt.toISOString(),
      committedAt: finishedAt.toISOString(),
    },
    change: {
      classification: "first_observation",
      baselineRevisionId: null,
      pixelChanged: null,
      byteChanged: null,
      reviewRequired: warnings.length > 0,
      signals: [],
    },
    honesty: {
      statement:
        "Observed facts and unavailable facts are explicitly distinguished.",
      classification: warnings.length === 0 ? "complete" : "partial",
      partialReason:
        warnings.length === 0
          ? null
          : "One or more public page resources or capabilities were blocked.",
      warnings,
      unavailableObservations:
        runtime.evidenceClass === "synthetic"
          ? [
              {
                field: "network.tls",
                reason: "Synthetic transport does not create a real connection.",
              },
            ]
          : [],
      redactionPolicyVersion: "vera-url-redaction-v1",
    },
    terminal: null,
  } as unknown as PublicPageCaptureProvenanceV1;
  validateProvenance(value);
  return value;
}

function buildTerminalProvenance(
  input: TerminalProvenanceInput,
): PublicPageCaptureProvenanceV1 {
  const {
    assignment,
    attemptId,
    cleanProfileId,
    decisionId,
    denial,
    finishedAt,
    runtime,
    startedMonotonic,
  } = input;
  const inspected = inspectPublicUrl(assignment.exactRequestedUrl);
  const outcome = denial.phase === "response" ? "failed" : "denied";
  const terminalPhase =
    denial.phase === "url_parse"
      ? "policy"
      : denial.phase === "redirect"
        ? "navigation"
        : denial.phase === "frame" ||
            denial.phase === "subresource" ||
            denial.phase === "response"
          ? "render"
          : denial.phase;
  const value = {
    schemaVersion: "public-page-capture-provenance/v1",
    recordType: "terminal_attempt_evidence",
    identity: {
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
    },
    authorization: workerAuthorization(runtime, decisionId, finishedAt),
    request: workerRequest(assignment, finishedAt),
    network: {
      evidenceClass: runtime.evidenceClass,
      dnsAdmissions: [],
      peerConnections: [],
      tls: {
        availability: "unavailable",
        protocol: null,
        cipher: null,
        peerCertificateSha256: null,
        unavailableReason:
          "The attempt ended before a verified TLS observation was retained.",
      },
      redirectChain: [
        {
          sequence: 0,
          url: inspected.canonicalUrl,
          redactedUrl: inspected.redactedUrl,
          urlDigest: sha256(inspected.canonicalUrl),
          status: null,
          locationDigest: null,
          admitted: false,
        },
      ],
      finalUrl: null,
      redactedFinalUrl: null,
      response: null,
      frameManifestDigest: null,
      subresourceManifestDigest: null,
      actualConnectionCount: 0,
      denial: {
        phase: denial.phase,
        code: denial.code,
        sanitizedMessage: denial.safeMessage,
        navigationStarted: denial.navigationStarted,
      },
    },
    runtime: runtimeRecord(runtime, assignment.profile, cleanProfileId),
    timing: provenanceTiming(
      assignment,
      runtime,
      finishedAt,
      elapsedMilliseconds(startedMonotonic),
      true,
    ),
    output: null,
    change: null,
    honesty: {
      statement:
        "Observed facts and unavailable facts are explicitly distinguished.",
      classification: outcome === "denied" ? "terminal_denial" : "terminal_failure",
      partialReason: denial.safeMessage,
      warnings: [],
      unavailableObservations: [
        {
          field: "network.response",
          reason: "The attempt ended before a committable response was observed.",
        },
      ],
      redactionPolicyVersion: "vera-url-redaction-v1",
    },
    terminal: {
      outcome,
      code: denial.code,
      sanitizedMessage: denial.safeMessage,
      phase: terminalPhase,
      retryable: denial.code === "browser_failure",
      navigationStarted: denial.navigationStarted,
      leaseDisposition: "consumed",
    },
  } as unknown as PublicPageCaptureProvenanceV1;
  validateProvenance(value);
  return value;
}

export class LocalPublicPageCaptureWorker {
  private readonly browserType: typeof chromium;
  private readonly delay: (milliseconds: number) => Promise<void>;
  private readonly id: () => string;
  private readonly now: () => Date;
  private active = 0;

  constructor(private readonly dependencies: LocalCaptureWorkerDependencies) {
    this.browserType = dependencies.browserType ?? chromium;
    this.delay =
      dependencies.delay ??
      (async (milliseconds) =>
        await new Promise<void>((resolve) => setTimeout(resolve, milliseconds)));
    this.id = dependencies.id ?? randomUUID;
    this.now = dependencies.now ?? (() => new Date());
  }

  async runOnce(): Promise<CaptureWorkerRunResult> {
    if (this.active >= 2) {
      throw new Error("The worker concurrency limit is already reached.");
    }
    this.active += 1;
    try {
      return await this.executeOnce();
    } finally {
      this.active -= 1;
    }
  }

  private async executeOnce(): Promise<CaptureWorkerRunResult> {
    const { protocol, runtime } = this.dependencies;
    const claimed = await protocol.claimLease({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "claim_lease",
      clientRequestId: this.id(),
      workerInstallationId: runtime.installationId,
      supportedProfileDigests: [CAPTURE_PROFILE_V1_DIGEST],
    });
    const assignment = claimed.assignment;
    if (assignment.profile.profileDigest !== CAPTURE_PROFILE_V1_DIGEST) {
      throw new Error("The claimed capture profile is not supported.");
    }
    const cleanProfileId = this.id();
    const started = await protocol.startAttempt({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "start_attempt",
      clientRequestId: this.id(),
      lease: leaseProof(assignment, runtime.installationId, null),
      cleanProfileId,
      browserBuild: runtime.browserBuild,
      adapterVersion: assignment.profile.adapterVersion,
      securityPolicyVersion: assignment.profile.securityPolicyVersion,
    });
    const proof = leaseProof(
      assignment,
      runtime.installationId,
      started.attemptId,
    );
    const startedMonotonic = performance.now();
    let browser: Browser | null = null;
    let context: BrowserContext | null = null;
    let browserLaunched = false;
    let navigationStarted = false;
    let realConnectionCount = 0;
    let heartbeatFailure: unknown;
    const heartbeat = setInterval(() => {
      void protocol
        .renewLease({
          schemaVersion: "public-page-capture-worker/v1",
          messageType: "renew_lease",
          clientRequestId: this.id(),
          lease: proof,
        })
        .catch((error: unknown) => {
          heartbeatFailure = error;
        });
    }, assignment.profile.limits.heartbeatMilliseconds);
    heartbeat.unref();

    try {
      const guard = this.dependencies.guardFactory(assignment.profile);
      // Fetch and validate every redirect before untrusted bytes reach Chromium.
      const topLevel = await guard.fetch(assignment.exactRequestedUrl);
      if (runtime.evidenceClass === "live") {
        realConnectionCount += topLevel.trace.actualConnectionCount;
      }
      this.assertWithinDeadline(startedMonotonic, assignment.profile);
      if (heartbeatFailure) {
        throw heartbeatFailure instanceof Error
          ? heartbeatFailure
          : new Error("Lease heartbeat failed.");
      }

      browser = await this.browserType.launch({
        chromiumSandbox: true,
        env: { LANG: "en_US.UTF-8", LC_ALL: "en_US.UTF-8", TZ: "UTC" },
        args: [
          "--disable-background-networking",
          "--disable-component-update",
          "--disable-default-apps",
          "--disable-extensions",
          "--disable-features=MediaRouter",
          "--disable-sync",
          "--force-color-profile=srgb",
          "--no-default-browser-check",
          "--no-first-run",
          "--renderer-process-limit=6",
        ],
      });
      browserLaunched = true;
      context = await browser.newContext({
        acceptDownloads: false,
        bypassCSP: false,
        colorScheme: "light",
        deviceScaleFactor: assignment.profile.render.deviceScaleFactor,
        javaScriptEnabled:
          assignment.profile.render.javaScript === "sandboxed_bounded",
        locale: "en-US",
        permissions: [],
        reducedMotion: "reduce",
        serviceWorkers: "block",
        timezoneId: "UTC",
        userAgent: assignment.profile.render.userAgent,
        viewport: {
          width: assignment.profile.render.viewportWidth,
          height: assignment.profile.render.viewportHeight,
        },
      });
      if ((await context.cookies()).length !== 0) {
        throw new CaptureDenied(
          "ambient_state_detected",
          "The disposable browser did not start empty.",
          "response",
        );
      }
      const captured = await this.captureInBrowser(
        context,
        guard,
        assignment,
        proof,
        topLevel,
        () => {
          navigationStarted = true;
        },
      );
      if (runtime.evidenceClass === "live") {
        realConnectionCount += captured.network.responses
          .slice(1)
          .reduce(
            (total, response) =>
              total + response.trace.actualConnectionCount,
            0,
          );
      }
      if (heartbeatFailure) {
        throw heartbeatFailure instanceof Error
          ? heartbeatFailure
          : new Error("Lease heartbeat failed.");
      }
      this.assertWithinDeadline(startedMonotonic, assignment.profile);
      await context.close();
      context = null;
      await browser.close();
      browser = null;

      const finishedAt = this.now();
      const provenance = this.revisionProvenance(
        assignment,
        started.attemptId,
        cleanProfileId,
        captured.observation,
        captured.network,
        startedMonotonic,
        finishedAt,
      );
      const grants = await protocol.requestStagingGrants({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "request_staging_grants",
        clientRequestId: this.id(),
        lease: proof,
        purposes: ["raster", "provenance"],
      });
      const rasterStaged = await protocol.stageObject(
        grantFor(grants.grants, "raster").rawGrant,
        runtime.installationId,
        captured.observation.raster,
      );
      const provenanceStaged = await protocol.stageObject(
        grantFor(grants.grants, "provenance").rawGrant,
        runtime.installationId,
        Buffer.from(canonicalJson(provenance as unknown as JsonValue), "utf8"),
      );
      const response = await protocol.commitAttempt({
        schemaVersion: "public-page-capture-worker/v1",
        messageType: "commit_attempt",
        clientRequestId: this.id(),
        lease: proof,
        commitNonce: assignment.commitNonce,
        raster: stagedDescriptor(rasterStaged),
        provenanceObject: stagedDescriptor(provenanceStaged),
        warningCodes: [...captured.observation.warnings],
        reviewClassification:
          captured.observation.warnings.length === 0
            ? "ready"
            : "review_required",
      });
      return {
        kind: "committed",
        response,
        isolation: this.isolationReceipt(
          browserLaunched,
          navigationStarted,
          realConnectionCount,
        ),
      };
    } catch (error) {
      const denial =
        error instanceof CaptureDenied
          ? error
          : new CaptureDenied(
              "browser_failure",
              "The isolated browser could not complete the capture.",
              "response",
              navigationStarted,
            );
      const response = await this.reportFailure(
        assignment,
        proof,
        cleanProfileId,
        denial,
        startedMonotonic,
      );
      return {
        kind: "failed",
        response,
        denial: {
          code: denial.code,
          navigationStarted: denial.navigationStarted,
          phase: denial.phase,
        },
        isolation: this.isolationReceipt(
          browserLaunched,
          navigationStarted,
          realConnectionCount,
        ),
      };
    } finally {
      clearInterval(heartbeat);
      await context?.close().catch(() => undefined);
      await browser?.close().catch(() => undefined);
    }
  }

  private async captureInBrowser(
    context: BrowserContext,
    guard: PublicEgressGuard,
    assignment: LeaseAssignment,
    proof: LeaseProof,
    topLevel: GuardedResponse,
    markNavigationStarted: () => void,
  ): Promise<{
    readonly network: NetworkObservation;
    readonly observation: BrowserObservation;
  }> {
    const { profile } = assignment;
    const page = await context.newPage();
    page.setDefaultNavigationTimeout(profile.limits.navigationMilliseconds);
    page.setDefaultTimeout(profile.limits.scriptCpuMilliseconds);
    await page.addInitScript(() => {
      const blocked = (): never => {
        throw new DOMException("Blocked by capture policy", "SecurityError");
      };
      Object.defineProperty(window, "open", { value: () => null });
      Object.defineProperty(window, "print", { value: blocked });
      Object.defineProperty(window, "WebSocket", { value: blocked });
      Object.defineProperty(window, "RTCPeerConnection", { value: blocked });
      Object.defineProperty(window, "webkitRTCPeerConnection", {
        value: blocked,
      });
      document.addEventListener("submit", (event) => event.preventDefault(), true);
    });

    const state: BrowserRouteState = {
      consumedTopLevel: false,
      counters: {
        frameRequests: 0,
        subresourceRequests: 0,
        topLevelRequests: 1,
        totalBytes: topLevel.body.byteLength,
        totalRequests: 1,
      },
      diagnostics: [],
      fatal: null,
      frames: [],
      responses: [topLevel],
      subresources: [],
      tail: Promise.resolve(),
      warnings: new Set<string>(),
    };

    await context.routeWebSocket("**/*", async (socket) => {
      state.warnings.add("blocked_web_socket");
      await socket.close({ code: 1008, reason: "Blocked by capture policy" });
    });
    context.on("page", (popup) => {
      if (popup !== page) {
        state.warnings.add("blocked_popup");
        void popup.close();
      }
    });
    context.on("requestfailed", (request) => {
      if (state.diagnostics.length >= profile.limits.diagnostics) return;
      state.diagnostics.push({
        failure:
          request
            .failure()
            ?.errorText.slice(0, profile.limits.diagnosticFieldBytes) ??
          "request_failed",
        resourceType: request.resourceType(),
      });
    });

    await this.installRoutes(
      context,
      guard,
      assignment,
      topLevel,
      state,
    );

    return await this.finishBrowserCapture(
      context,
      page,
      assignment,
      proof,
      state,
      markNavigationStarted,
    );
  }

  private async installRoutes(
    context: BrowserContext,
    guard: PublicEgressGuard,
    assignment: LeaseAssignment,
    topLevel: GuardedResponse,
    state: BrowserRouteState,
  ): Promise<void> {
    await context.route("**/*", async (route) => {
      state.tail = state.tail.then(
        async () => await this.handleRoute(route, guard, assignment, topLevel, state),
      );
      await state.tail;
    });
  }

  private async handleRoute(
    route: Route,
    guard: PublicEgressGuard,
    assignment: LeaseAssignment,
    topLevel: GuardedResponse,
    state: BrowserRouteState,
  ): Promise<void> {
    const request = route.request();
    const kind = routeKind(route);
    const resourceType = request.resourceType();
    try {
      if (state.fatal) {
        await route.abort("blockedbyclient");
        return;
      }
      if (request.method() !== "GET" && request.method() !== "HEAD") {
        state.warnings.add("blocked_mutation_method");
        await route.abort("blockedbyclient");
        return;
      }
      if (resourceType === "font" || resourceType === "media") {
        state.warnings.add(
          resourceType === "font" ? "blocked_web_font" : "blocked_media",
        );
        await route.abort("blockedbyclient");
        return;
      }
      if (
        kind === "frame" &&
        routeFrameDepth(route) > assignment.profile.limits.frameDepth
      ) {
        throw new CaptureDenied(
          "resource_limit",
          "The page exceeded the permitted frame depth.",
          "frame",
          true,
        );
      }
      const initialTopLevel =
        kind === "top_level" &&
        !state.consumedTopLevel &&
        inspectPublicUrl(request.url()).canonicalUrl ===
          inspectPublicUrl(topLevel.finalUrl).canonicalUrl;
      if (initialTopLevel) {
        state.consumedTopLevel = true;
        await route.fulfill({
          status: topLevel.status,
          headers: safeResponseHeaders(topLevel.headers),
          body: topLevel.body,
        });
        return;
      }
      state.counters.totalRequests += 1;
      if (kind === "top_level") state.counters.topLevelRequests += 1;
      else if (kind === "frame") state.counters.frameRequests += 1;
      else state.counters.subresourceRequests += 1;
      this.assertRouteCounters(state.counters, assignment.profile);
      const response = await guard.fetch(
        request.url(),
        request.method() as "GET" | "HEAD",
      );
      state.counters.totalBytes += response.body.byteLength;
      this.assertRouteCounters(state.counters, assignment.profile);
      state.responses.push(response);
      const record = {
        digest: sha256(request.url()),
        kind,
        resourceType,
        status: response.status,
      } as unknown as JsonValue;
      if (kind === "frame") state.frames.push(record);
      else if (kind === "subresource") state.subresources.push(record);
      await route.fulfill({
        status: response.status,
        headers: safeResponseHeaders(response.headers),
        body: response.body,
      });
    } catch (error) {
      const denial =
        error instanceof CaptureDenied
          ? error
          : new CaptureDenied(
              "guard_failure",
              "The browser request could not be verified safely.",
              kind === "frame" ? "frame" : "subresource",
              true,
            );
      if (
        kind === "top_level" ||
        assignment.profile.warningPolicy.hardFailureCodes.includes(denial.code)
      ) {
        state.fatal = denial;
      } else {
        state.warnings.add(
          kind === "frame" ? "blocked_frame" : "blocked_subresource",
        );
      }
      await route.abort("blockedbyclient");
    }
  }

  private async finishBrowserCapture(
    context: BrowserContext,
    page: Page,
    assignment: LeaseAssignment,
    proof: LeaseProof,
    state: BrowserRouteState,
    markNavigationStarted: () => void,
  ): Promise<{
    readonly network: NetworkObservation;
    readonly observation: BrowserObservation;
  }> {
    const { profile } = assignment;
    const topLevel = state.responses[0];
    if (!topLevel) {
      throw new Error("The admitted top-level response is unavailable.");
    }
    await this.dependencies.protocol.recordNavigationStart({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "record_navigation_start",
      clientRequestId: this.id(),
      lease: proof,
      navigationStartedAt: this.now().toISOString(),
      initialUrlDigest: sha256(
        inspectPublicUrl(assignment.exactRequestedUrl).canonicalUrl,
      ),
    });
    markNavigationStarted();
    try {
      await page.goto(topLevel.finalUrl, {
        waitUntil: "domcontentloaded",
        timeout: profile.limits.navigationMilliseconds,
      });
    } catch (error) {
      if (state.fatal !== null) throw state.fatal;
      throw error;
    }
    await state.tail;
    if (state.fatal !== null) throw state.fatal;
    await page.addStyleTag({
      content:
        "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}",
    });
    await this.delay(profile.stability.settleMilliseconds);
    const title = safeTitle(await page.title());
    const screenshot = await page.screenshot({
      animations: "disabled",
      caret: "hide",
      fullPage: false,
      omitBackground: false,
      scale: "device",
      type: "png",
    });
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    if ((await context.cookies()).length !== 0) {
      throw new CaptureDenied(
        "ambient_state_detected",
        "The disposable browser state could not be discarded.",
        "response",
        true,
      );
    }
    return {
      network: {
        frames: state.frames,
        responses: state.responses,
        subresources: state.subresources,
        topLevel,
      },
      observation: {
        raster: Buffer.from(screenshot),
        title,
        warnings: [...state.warnings].sort(),
      },
    };
  }

  private revisionProvenance(
    assignment: LeaseAssignment,
    attemptId: string,
    cleanProfileId: string,
    observation: BrowserObservation,
    network: NetworkObservation,
    startedMonotonic: number,
    finishedAt: Date,
  ): PublicPageCaptureProvenanceV1 {
    return buildRevisionProvenance({
      assignment,
      attemptId,
      cleanProfileId,
      decisionId: this.id(),
      finishedAt,
      network,
      observation,
      runtime: this.dependencies.runtime,
      startedMonotonic,
      revisionId: this.id(),
    });
  }

  private async reportFailure(
    assignment: LeaseAssignment,
    proof: LeaseProof,
    cleanProfileId: string,
    denial: CaptureDenied,
    startedMonotonic: number,
  ): Promise<FailAttemptResponse | AbandonAttemptResponse> {
    const provenance = buildTerminalProvenance({
      assignment,
      attemptId: proof.attemptId!,
      cleanProfileId,
      decisionId: this.id(),
      denial,
      finishedAt: this.now(),
      runtime: this.dependencies.runtime,
      startedMonotonic,
    });
    const grants = await this.dependencies.protocol.requestStagingGrants({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "request_staging_grants",
      clientRequestId: this.id(),
      lease: proof,
      purposes: ["raster", "provenance"],
    });
    const staged = await this.dependencies.protocol.stageObject(
      grantFor(grants.grants, "provenance").rawGrant,
      this.dependencies.runtime.installationId,
      Buffer.from(canonicalJson(provenance as unknown as JsonValue), "utf8"),
    );
    return await this.dependencies.protocol.failAttempt({
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "fail_attempt",
      clientRequestId: this.id(),
      lease: proof,
      terminalCode: denial.code,
      navigationStarted: denial.navigationStarted,
      retryable: denial.code === "browser_failure",
      terminalEvidenceObject: stagedDescriptor(staged),
    });
  }

  private assertRouteCounters(
    counters: RouteCounters,
    profile: CaptureProfileV1,
  ): void {
    const { limits } = profile;
    if (
      counters.topLevelRequests > limits.topLevelRequests ||
      counters.frameRequests > limits.frameRequests ||
      counters.subresourceRequests > limits.subresourceRequests ||
      counters.totalRequests > limits.totalRequests ||
      counters.totalBytes > limits.totalBytes
    ) {
      throw new CaptureDenied(
        "resource_limit",
        "The page exceeded the frozen capture resource profile.",
        "response",
        true,
      );
    }
  }

  private assertWithinDeadline(
    startedMonotonic: number,
    profile: CaptureProfileV1,
  ): void {
    if (
      performance.now() - startedMonotonic >=
      profile.stability.hardDeadlineMilliseconds
    ) {
      throw new CaptureDenied(
        "attempt_deadline",
        "The capture exceeded its hard deadline.",
        "response",
      );
    }
  }

  private isolationReceipt(
    browserLaunched: boolean,
    navigationStarted: boolean,
    realConnectionCount: number,
  ): WorkerIsolationReceipt {
    return {
      browserLaunched,
      directNetworkFallback: false,
      finalCookieCount: 0,
      importedState: false,
      initialCookieCount: 0,
      navigationStarted,
      persistedStateDiscarded: true,
      realConnectionCount,
    };
  }
}
