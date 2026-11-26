import { randomUUID } from "node:crypto";

import type { PrincipalRef } from "@vera/contracts";

import { sha256 } from "./crypto.js";
import {
  DIRECT_IMAGE_MAX_BYTES,
  DirectImageInspectorUnavailable,
  isDecodedDirectStill,
  type DirectImageInspector,
} from "./direct-image-inspection.js";
import {
  type DirectImageFailure,
  type DirectImageReceipt,
  type ProjectDirectImageStore,
} from "./direct-image-store.js";
import {
  CaptureDenied,
  inspectPublicUrl,
  NodePinnedTransport,
  PublicEgressGuard,
  SystemDnsResolver,
  type DnsResolver,
  type GuardedResponse,
  type PinnedTransport,
} from "./policy.js";

export interface DirectImageIntent {
  readonly projectId: string;
  readonly principal: PrincipalRef;
  readonly documentRevisionId: string;
  readonly occurrenceId: string;
  readonly approvedUrl: string;
  readonly retryAttemptId?: string;
}

export type DirectImageResult =
  | { readonly status: "ready" | "reused"; readonly mediaReferenceId: string;
      readonly buildQualification: "unqualified" }
  | DirectImageFailure
  | { readonly status: "denied" | "refused" | "needs_inspection"; readonly code: string };

export interface DirectImageAcquisitionOptions {
  readonly store: ProjectDirectImageStore;
  readonly inspector: DirectImageInspector;
  /** The trusted caller must authorize edit_document and verify the current project revision and occurrence. */
  readonly authorizeEdit: (intent: DirectImageIntent) => Promise<boolean>;
  readonly resolver?: DnsResolver;
  readonly transport?: PinnedTransport;
}

const denied = { status: "denied", code: "project_or_occurrence_denied" } as const;
const uncertain = { status: "needs_inspection", code: "storage_state_uncertain" } as const;
const transient = new Set(["dns_unavailable", "dns_no_answers", "connection_failed", "connection_timeout"]);

function isAuthorized(intent: DirectImageIntent, options: DirectImageAcquisitionOptions): Promise<boolean> {
  return Promise.resolve().then(() => options.authorizeEdit(intent)).then(
    (allowed) => allowed === true, () => false,
  );
}

function reference(status: "ready" | "reused", mediaReferenceId: string): DirectImageResult {
  return { status, mediaReferenceId, buildQualification: "unqualified" };
}

function imageType(bytes: Buffer): string | null {
  if (bytes.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) return "image/png";
  if (bytes.subarray(0, 3).equals(Buffer.from("ffd8ff", "hex"))) return "image/jpeg";
  return null;
}

async function fetchImage(url: string, options: DirectImageAcquisitionOptions): Promise<GuardedResponse> {
  const guard = new PublicEgressGuard(
    options.resolver ?? new SystemDnsResolver(),
    options.transport ?? new NodePinnedTransport(),
    { maxResponseBytes: DIRECT_IMAGE_MAX_BYTES, maxRedirects: 5 },
  );
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      guard.fetch(url, "GET", { signal: controller.signal, accept: "image/png,image/jpeg" }),
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => {
          const error = new CaptureDenied("connection_timeout", "Image acquisition timed out.", "connect");
          reject(error);
          controller.abort(error);
        }, 15_000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function fetchAndVerify(
  url: ReturnType<typeof inspectPublicUrl>,
  mediaReferenceId: string,
  attemptId: string,
  options: DirectImageAcquisitionOptions,
): Promise<DirectImageFailure | { receipt: DirectImageReceipt; bytes: Buffer }> {
  const failure = (code: string, retryable = false): DirectImageFailure =>
    ({ status: retryable ? "retryable" : "refused", code, attemptId });
  let response: GuardedResponse;
  try { response = await fetchImage(url.canonicalUrl, options); }
  catch (error) {
    if (error instanceof CaptureDenied) return failure(error.code, transient.has(error.code));
    return failure("connection_failed", true);
  }
  if (response.status !== 200) {
    return failure("image_http_status", response.status === 429 || (response.status >= 500 && response.status < 600));
  }
  const bytes = Buffer.from(response.body);
  const mimeType = imageType(bytes);
  if (!mimeType) return failure("unsupported_image");
  const declared = response.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase();
  if (declared && declared !== "application/octet-stream" && declared !== mimeType) {
    return failure("image_type_mismatch");
  }
  let facts: unknown;
  try { facts = await options.inspector.inspect(Buffer.from(bytes)); }
  catch (error) {
    return error instanceof DirectImageInspectorUnavailable ?
      failure("inspector_unavailable", true) : failure("image_decode");
  }
  if (!isDecodedDirectStill(facts) || facts.mimeType !== mimeType) return failure("image_decode");

  return {
    bytes,
    receipt: {
      version: 1, mediaReferenceId, attemptId,
      mimeType, width: facts.width, height: facts.height, orientation: facts.orientation, frameCount: 1,
      requestedUrlDigest: sha256(url.canonicalUrl),
      finalUrlDigest: sha256(response.finalUrl),
      requestedOrigin: url.url.origin,
      finalOrigin: new URL(response.finalUrl).origin,
      contentHash: sha256(bytes),
      byteLength: bytes.length,
      acquiredAt: new Date().toISOString(),
      inspectorProfile: options.inspector.profile,
    },
  };
}

/** Trusted local intake. A retry must name the last retryable attempt for this project and URL. */
export async function acquireDirectImage(
  input: DirectImageIntent,
  options: DirectImageAcquisitionOptions,
): Promise<DirectImageResult> {
  const intent = Object.freeze({ ...input, principal: Object.freeze({ ...input.principal }) });
  const authorize = () => isAuthorized(intent, options);
  if (!await authorize()) return denied;

  let url: ReturnType<typeof inspectPublicUrl>;
  try { url = inspectPublicUrl(intent.approvedUrl); }
  catch (error) {
    return { status: "refused", code: error instanceof CaptureDenied ? error.code : "invalid_url" };
  }

  try {
    const source = await options.store.source(intent.projectId, sha256(url.canonicalUrl));
    const reuse = async () => await authorize() ? reference("reused", source.mediaReferenceId) : denied;
    if (await source.read()) return await reuse();
    if (!await source.claim()) return await source.read() ? await reuse() : uncertain;
    // Recheck after locking. An earlier caller may have published or recorded a failure.
    if (await source.read()) {
      await source.release();
      return await reuse();
    }
    const previous = await source.readFailure();
    if (previous ? previous.status !== "retryable" || intent.retryAttemptId !== previous.attemptId : intent.retryAttemptId) {
      await source.release();
      return previous ?? { status: "refused", code: "unknown_retry_attempt" };
    }
    if (!await authorize()) {
      await source.release();
      return denied;
    }
    const result = await fetchAndVerify(url, source.mediaReferenceId, randomUUID(), options);
    if ("status" in result) {
      const allowed = await authorize();
      if (allowed) await source.recordFailure(result);
      await source.release();
      return allowed ? result : denied;
    }

    const published = await source.publish(result.receipt, result.bytes, authorize);
    await source.release();
    return published ? reference("ready", source.mediaReferenceId) : denied;
  } catch {
    // Unknown or incomplete writes keep their lock for inspection. Never re-fetch over them.
    return uncertain;
  }
}
