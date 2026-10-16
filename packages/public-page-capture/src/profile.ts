import type { CaptureProfileV1 } from "@vera/contracts";

import { sha256 } from "./crypto.js";

const profileWithoutDigest = {
  profileId: "33333333-3333-4333-8333-333333333333",
  profileVersion: 1,
  adapterVersion: "playwright_v1",
  securityPolicyVersion: "egress_v1",
  network: {
    schemes: ["http", "https"],
    ports: [80, 443],
    methods: ["GET", "HEAD"],
    idna: "uts46_nontransitional",
    rejectMixedDns: true,
    pinResolvedAddresses: true,
    verifyActualPeer: true,
    revalidateRedirects: true,
    revalidateFrames: true,
    revalidateSubresources: true,
    directBrowserNetworkFallback: false,
    webSocket: "blocked",
    webRtc: "blocked",
    referrer: "none",
  },
  isolation: {
    disposableContext: true,
    importedState: false,
    cookies: "empty_and_discarded",
    storage: "empty_and_discarded",
    cache: "ephemeral",
    extensions: "blocked",
    downloads: "blocked",
    permissions: "none",
    filesystem: "page_inaccessible",
    localNetwork: "blocked",
    inboundListeners: "blocked",
    attachedBrowser: false,
    credentialEnvironment: "allowlist_only",
  },
  render: {
    javaScript: "sandboxed_bounded",
    viewportWidth: 1920,
    viewportHeight: 1080,
    deviceScaleFactor: 2,
    region: { kind: "full_viewport" },
    encoding: "png",
    color: "srgb",
    background: "opaque_white",
    locale: "en-US",
    timezone: "UTC",
    userAgent: "VERA Public Page Capture/1",
    animations: "disabled",
    reducedMotion: "reduce",
    fonts: "system_only_no_webfonts",
    media: "blocked",
    popups: "blocked",
    forms: "blocked",
    interaction: "none",
  },
  stability: {
    waitUntil: "domcontentloaded",
    settleMilliseconds: 3000,
    hardDeadlineMilliseconds: 30_000,
  },
  warningPolicy: {
    anyWarningRequiresReview: true,
    hardFailureCodes: [
      "blocked_destination",
      "resource_limit",
      "invalid_raster",
    ],
  },
  limits: {
    urlBytes: 2048,
    redirects: 10,
    dnsAnswers: 16,
    connectionAttemptsPerRequest: 4,
    topLevelRequests: 2,
    frameRequests: 16,
    subresourceRequests: 128,
    totalRequests: 256,
    responseBytes: 8 * 1024 * 1024,
    totalBytes: 32 * 1024 * 1024,
    frameDepth: 4,
    popups: 0,
    navigationMilliseconds: 15_000,
    stabilityMilliseconds: 3000,
    scriptCpuMilliseconds: 5000,
    attemptMilliseconds: 30_000,
    memoryMiB: 512,
    processes: 8,
    workerConcurrency: 2,
    outputPixels: 3840 * 2160,
    rasterBytes: 16 * 1024 * 1024,
    diagnostics: 64,
    diagnosticFieldBytes: 512,
    retries: 2,
    leaseMilliseconds: 30_000,
    heartbeatMilliseconds: 5000,
  },
} as const;

export const CAPTURE_PROFILE_V1_DIGEST = sha256(
  profileWithoutDigest,
);

function deepFreeze<T>(value: T): Readonly<T> {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
}

export const CAPTURE_PROFILE_V1 = deepFreeze({
  ...profileWithoutDigest,
  profileDigest: CAPTURE_PROFILE_V1_DIGEST,
}) as unknown as Readonly<CaptureProfileV1>;

export const OUTPUT_WIDTH =
  profileWithoutDigest.render.viewportWidth *
  profileWithoutDigest.render.deviceScaleFactor;
export const OUTPUT_HEIGHT =
  profileWithoutDigest.render.viewportHeight *
  profileWithoutDigest.render.deviceScaleFactor;
