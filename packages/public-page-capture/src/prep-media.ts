/**
 * #394: opt-in Prep Media boundary for authored public-page stills.
 *
 * No browser or HTTP client lives here. Capture admission, egress, project
 * authorization and immutable provenance stay with #39's CaptureService.
 * The host must still qualify the returned local still as an occurrence media
 * descriptor before passing it to the existing #174/#173 compiler pipeline.
 */
import { createHash, randomUUID } from "node:crypto";
import { mkdir, mkdtemp, readFile, lstat, rename, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import type { DraftOccurrenceReference, PrincipalRef } from "@vera/contracts";
import type {
  NarratedVisualPayloadV2,
  ScriptDocumentV2,
  StandaloneVisualPayloadV2,
} from "@vera/contracts/v2";

import { CaptureDenied, inspectPublicUrl } from "./policy.js";
import { requestPublicPagePictures } from "./page-pictures.js";
import { CAPTURE_PROFILE_V1, CAPTURE_PROFILE_V2 } from "./profile.js";
import type { CaptureService } from "./service.js";

type CapturePort = Pick<CaptureService,
  "createCapture" | "getCapture" | "requestCaptureJob" | "getRevision" | "selectRevision" | "readRasterArtifact"
>;
type VisualPayload = NarratedVisualPayloadV2 | StandaloneVisualPayloadV2;
type CaptureUrl = Extract<VisualPayload["source"], { kind: "url" }>;

export interface WebpageCaptureResult {
  readonly payloadId: string;
  readonly label: string;
  readonly status: "ready" | "reused" | "pending" | "failed" | "review_required";
  readonly reason: string | null;
  readonly rasterPath: string | null;
  readonly captureId: string | null;
  readonly revisionId: string | null;
  readonly artifactDigest: string | null;
}

export interface WebpagePrepMediaOptions {
  readonly projectId: string;
  /** Trusted project root, not a path supplied by the authored URL. */
  readonly projectRoot: string;
  readonly principal: PrincipalRef;
  /** The current authorized, versioned authored occurrence. */
  readonly reference: DraftOccurrenceReference;
  readonly service: CapturePort;
}

export interface WebpagePrepMediaOutcome {
  /** Build-only projection; the authored document is never rewritten. */
  readonly document: ScriptDocumentV2;
  /** Pass ready rasterPaths to the existing trusted still/occurrence binder. */
  readonly captures: readonly WebpageCaptureResult[];
}

interface StoredStill {
  schemaVersion: "webpage-capture-still/v1";
  projectId: string;
  canonicalUrlDigest: string;
  captureId: string;
  revisionId: string;
  artifactId: string;
  digest: string;
  byteLength: number;
}

const digest = (value: string | Buffer): string =>
  `sha256:${createHash("sha256").update(value).digest("hex")}`;
function validateStored(value: unknown, projectId: string, urlDigest: string): StoredStill {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid webpage still receipt");
  const record = value as Partial<StoredStill>;
  if (record.schemaVersion !== "webpage-capture-still/v1" ||
      record.projectId !== projectId || record.canonicalUrlDigest !== urlDigest ||
      typeof record.captureId !== "string" || typeof record.revisionId !== "string" ||
      typeof record.artifactId !== "string" ||
      typeof record.digest !== "string" || !/^sha256:[a-f0-9]{64}$/u.test(record.digest) ||
      !Number.isSafeInteger(record.byteLength) || (record.byteLength ?? 0) < 1 ||
      Object.keys(record).sort().join(",") !== ["artifactId", "byteLength", "canonicalUrlDigest", "captureId", "digest", "projectId", "revisionId", "schemaVersion"].sort().join(",")) {
    throw new Error("invalid webpage still receipt");
  }
  return record as StoredStill;
}

export class ProjectWebpageStillStore {
  constructor(private readonly projectRoot: string) {
    if (!resolve(projectRoot).startsWith("/") || !projectRoot.startsWith("/")) {
      throw new TypeError("trusted project root must be absolute");
    }
  }

  private directory(urlDigest: string): string {
    if (!/^sha256:[a-f0-9]{64}$/u.test(urlDigest)) throw new Error("invalid URL digest");
    return join(this.projectRoot, "Webpage Captures", urlDigest.slice(7));
  }

  async read(projectId: string, urlDigest: string): Promise<{ record: StoredStill; path: string } | null> {
    const directory = this.directory(urlDigest);
    let directoryStat;
    try { directoryStat = await lstat(directory); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
    if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink()) throw new Error("unsafe webpage still directory");
    const metadata = join(directory, "receipt.json");
    const raster = join(directory, "capture.png");
    if (!(await lstat(metadata)).isFile() || !(await lstat(raster)).isFile()) throw new Error("unsafe webpage still file");
    const record = validateStored(JSON.parse(await readFile(metadata, "utf8")) as unknown, projectId, urlDigest);
    const bytes = await readFile(raster);
    if (bytes.byteLength !== record.byteLength || digest(bytes) !== record.digest) {
      throw new Error("cached webpage still failed immutable byte verification");
    }
    return { record, path: raster };
  }

  async publish(record: StoredStill, bytes: Buffer): Promise<string> {
    validateStored(record, record.projectId, record.canonicalUrlDigest);
    if (bytes.byteLength !== record.byteLength || digest(bytes) !== record.digest) {
      throw new Error("capture artifact bytes do not match verified descriptor");
    }
    const existing = await this.read(record.projectId, record.canonicalUrlDigest);
    if (existing) {
      if (JSON.stringify(existing.record) !== JSON.stringify(record)) throw new Error("webpage still identity conflict");
      return existing.path;
    }
    const root = join(this.projectRoot, "Webpage Captures");
    await mkdir(root, { recursive: true, mode: 0o700 });
    if (!(await lstat(root)).isDirectory() || (await lstat(root)).isSymbolicLink()) {
      throw new Error("unsafe webpage still store root");
    }
    const scratch = await mkdtemp(join(root, ".staging-"));
    try {
      await writeFile(join(scratch, "capture.png"), bytes, { flag: "wx", mode: 0o600 });
      await writeFile(join(scratch, "receipt.json"), JSON.stringify(record), { flag: "wx", mode: 0o600 });
      try {
        await rename(scratch, this.directory(record.canonicalUrlDigest));
      } catch (error) {
        if (!["EEXIST", "ENOTEMPTY"].includes((error as NodeJS.ErrnoException).code ?? "")) throw error;
        const winner = await this.read(record.projectId, record.canonicalUrlDigest);
        if (!winner || JSON.stringify(winner.record) !== JSON.stringify(record)) throw new Error("webpage still identity conflict", { cause: error });
      }
    } finally {
      await rm(scratch, { recursive: true, force: true });
    }
    const published = await this.read(record.projectId, record.canonicalUrlDigest);
    if (!published) throw new Error("webpage still publication missing");
    return published.path;
  }
}

async function prepareUrl(
  payload: VisualPayload & { source: CaptureUrl },
  options: WebpagePrepMediaOptions,
  store: ProjectWebpageStillStore,
): Promise<WebpageCaptureResult> {
  const base = { payloadId: payload.payloadId };
  const occurrenceReference: DraftOccurrenceReference = {
    ...options.reference,
    occurrenceId: payload.payloadId,
  };
  let inspected;
  try { inspected = inspectPublicUrl(payload.source.url); } catch (error) {
    if (!(error instanceof CaptureDenied)) throw error;
    return { ...base, label: "Blocked webpage", status: "failed", reason: error.safeMessage,
      rasterPath: null, captureId: null, revisionId: null, artifactDigest: null };
  }
  const label = inspected.redactedUrl;
  const urlDigest = digest(inspected.canonicalUrl);
  const cached = await store.read(options.projectId, urlDigest);
  const job = cached ? null : (await requestPublicPagePictures(
    options.service, options.projectId, options.principal, inspected.canonicalUrl,
  )).top;
  const captureId = cached?.record.captureId ?? job?.captureId;
  if (!captureId) throw new Error("webpage capture is missing its source");
  let revisionId = cached?.record.revisionId ?? null;
  // Always reauthorize reads, including cache hits; a local receipt is not a
  // substitute for current membership or the selected occurrence authority.
  const capture = await options.service.getCapture(options.projectId, captureId, options.principal);
  if (capture.capture.projectId !== options.projectId ||
      capture.capture.lifecycle !== "active" ||
      capture.capture.configuration.requestedUrl.canonicalDigest !== urlDigest ||
      capture.capture.configuration.captureProfileId !== CAPTURE_PROFILE_V1.profileId ||
      !(capture.capture.configuration.captureProfileVersion === CAPTURE_PROFILE_V2.profileVersion ||
        (cached && capture.capture.configuration.captureProfileVersion === CAPTURE_PROFILE_V1.profileVersion))) {
    throw new Error("webpage capture is not the authorized source/profile");
  }
  if (job) {
    if (job.state === "failed" || job.state === "rejected" || job.state === "cancelled") {
      return { ...base, label, status: "failed", reason: `Webpage capture ${job.state}`,
        rasterPath: null, captureId, revisionId: null, artifactDigest: null };
    }
    if (job.state === "committed_review_required") {
      return { ...base, label, status: "review_required", reason: "Webpage capture requires review",
        rasterPath: null, captureId, revisionId: job.outputRevisionId, artifactDigest: null };
    }
    if (job.state !== "committed_ready" || !job.outputRevisionId) {
      return { ...base, label, status: "pending", reason: "Webpage capture has not completed",
        rasterPath: null, captureId, revisionId: null, artifactDigest: null };
    }
    revisionId = job.outputRevisionId;
  }
  if (!revisionId) throw new Error("webpage capture is missing its revision");
  const revision = (await options.service.getRevision(options.projectId, revisionId, options.principal)).revision;
  if (revision.status !== "ready") {
    return { ...base, label, status: "review_required", reason: "Webpage capture requires review",
      rasterPath: null, captureId, revisionId, artifactDigest: null };
  }
  const descriptor = revision.artifact;
  if (revision.projectId !== options.projectId || revision.captureId !== captureId ||
      descriptor.projectId !== options.projectId || descriptor.kind !== "capture_raster" ||
      descriptor.mimeType !== "image/png" || descriptor.accessClass !== "project_visual" ||
      !/^sha256:[0-9a-f]{64}$/u.test(descriptor.digest) || !Number.isSafeInteger(descriptor.byteLength) ||
      descriptor.byteLength <= 0 || !descriptor.width || !descriptor.height ||
      (cached && (cached.record.revisionId !== revisionId || cached.record.artifactId !== descriptor.artifactId ||
        cached.record.digest !== descriptor.digest || cached.record.byteLength !== descriptor.byteLength))) {
    throw new Error("webpage capture revision/provenance mismatch");
  }
  // A successful job is NOT itself a grant to read its raster. #39 requires
  // an actual selection, protection or use decision for this visible source.
  // A ready revision may be auto-selected for the explicitly authored URL;
  // warning-bearing revisions cannot bypass their separate review decision.
  try {
    await options.service.selectRevision({
      schemaVersion: "public-page-capture-api/v1", messageType: "select_revision",
      projectId: options.projectId, revisionId, clientRequestId: randomUUID(),
      idempotencyKey: `webpage-prep/select/${digest(JSON.stringify(occurrenceReference))}/${revisionId}`,
      target: occurrenceReference, expectedPreviousSelectionId: null,
      reason: "capture_and_use", requiredUseDecisionId: null,
    }, options.principal);
  } catch (error) {
    // Another authorized invocation may already have selected the *same*
    // revision for this target. The raster read below independently proves
    // that fact; it refuses if the competing selection names another revision.
    if (!(error instanceof Error) || !("code" in error) || error.code !== "selection_conflict") throw error;
  }
  // The service re-checks the source's current project and visible authored
  // reference on every reuse, even when the bytes are safely cached on disk.
  const raster = await options.service.readRasterArtifact(
    options.projectId, revisionId, occurrenceReference, options.principal,
  );
  if (raster.descriptor.artifactId !== descriptor.artifactId ||
      raster.descriptor.digest !== descriptor.digest || raster.descriptor.byteLength !== descriptor.byteLength ||
      raster.bytes.byteLength !== descriptor.byteLength || digest(raster.bytes) !== descriptor.digest) {
    throw new Error("webpage raster does not match immutable capture revision");
  }
  const record: StoredStill = { schemaVersion: "webpage-capture-still/v1", projectId: options.projectId,
    canonicalUrlDigest: urlDigest, captureId, revisionId,
    artifactId: descriptor.artifactId, digest: descriptor.digest, byteLength: descriptor.byteLength };
  const rasterPath = cached?.path ?? await store.publish(record, raster.bytes);
  return { ...base, label, status: cached ? "reused" : "ready", reason: null,
    rasterPath, captureId, revisionId, artifactDigest: descriptor.digest };
}

/**
 * This does not synthesize compiler source snapshots, P5 receipts or still
 * cadence. The trusted Prep Media host must probe/qualify the returned PNG and
 * bind it to the exact occurrence before the normal build; it may not treat
 * this projection as a ready compiler dependency on its own.
 */
export async function preparePublicWebpageVisuals(
  authored: ScriptDocumentV2,
  options: WebpagePrepMediaOptions,
): Promise<WebpagePrepMediaOutcome> {
  if (authored.projectId !== options.projectId || options.reference.projectId !== options.projectId ||
      options.reference.resourceId !== authored.id ||
      options.reference.resourceVersionDigest !== authored.liveContentHash ||
      options.reference.kind !== "draft_occurrence") {
    throw new Error("webpage preparation requires the frozen project and authored reference");
  }
  const document = structuredClone(authored);
  const store = new ProjectWebpageStillStore(options.projectRoot);
  const captures: WebpageCaptureResult[] = [];
  const preparePayload = async (payload: VisualPayload): Promise<void> => {
    if (payload.pictureKind !== "capture" || payload.source.kind !== "url") return;
    // Every occurrence needs its own authorized selection, even if another
    // occurrence already requested this URL. #39 deduplicates capture jobs;
    // the verified disk cache deduplicates bytes.
    const result = await prepareUrl(payload as VisualPayload & { source: CaptureUrl }, options, store);
    captures.push(result);
    if ((result.status === "ready" || result.status === "reused") && result.captureId && result.revisionId) {
      payload.source = { kind: "capture_revision", captureId: result.captureId, revisionId: result.revisionId };
    } else {
      payload.pictureKind = "intentional_placeholder";
      payload.source = { kind: "intentional_placeholder", text: `Webpage ${result.label}: ${result.reason ?? "Unavailable"}` };
      payload.audioPolicy = "mute";
      if ("sourceUsage" in payload) payload.sourceUsage = null;
      if ("selectedSourceRange" in payload) delete payload.selectedSourceRange;
      if ("imageMotion" in payload) delete payload.imageMotion;
    }
  };
  for (const block of document.activeDraft.blocks) {
    if (block.type === "visual_only") await preparePayload(block.payload);
    if (block.type === "narration" && block.state === "active") {
      for (const slot of block.primaryVisualSequence?.slots ?? []) {
        if (slot.kind === "content" && slot.payload.kind === "visual") await preparePayload(slot.payload);
      }
      for (const overlay of block.overlayEvents) await preparePayload(overlay.payload);
    }
  }
  return { document, captures };
}
