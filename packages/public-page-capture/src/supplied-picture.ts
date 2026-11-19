import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, readFile, lstat, rename, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import type { DraftOccurrenceReference, PrincipalRef, VersionedExternalReference } from "@vera/contracts";

import type { AuthoringReferencePort, ProjectAuthorizationPort } from "./authorization.js";
import { canonicalJson, sha256, type JsonValue } from "./crypto.js";
import { CAPTURE_PROFILE_V2 } from "./profile.js";
import { verifyPngWithinBounds, type BoundedRasterLimits, type VerifiedRaster } from "./raster.js";

export type SuppliedPictureReference = DraftOccurrenceReference | VersionedExternalReference;
export type SuppliedPictureKind = "top" | "passage";

export interface PictureRect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface SuppliedPictureProvenance {
  readonly kind: "user_supplied";
  readonly source: "browser_extension";
  readonly principal: PrincipalRef;
  readonly suppliedAt: string;
  readonly sourceUrlDigest: string | null;
}

export interface SuppliedPictureMetadata {
  readonly schemaVersion: "supplied-picture/v1";
  readonly projectId: string;
  readonly captureId: string;
  readonly revisionId: string;
  readonly pictureKind: SuppliedPictureKind;
  readonly highlightRects: readonly PictureRect[];
  readonly reference: SuppliedPictureReference;
  readonly referenceDigest: string;
  readonly raster: VerifiedRaster;
  readonly provenance: SuppliedPictureProvenance;
}

export interface SuppliedPictureUpload {
  readonly projectId: string;
  readonly principal: PrincipalRef;
  readonly reference: SuppliedPictureReference;
  readonly bytes: Buffer;
  readonly pictureKind: SuppliedPictureKind;
  /** A stable source identity may be supplied when top and passage uploads share a source. */
  readonly captureId?: string;
  readonly highlightRects?: readonly PictureRect[];
  readonly sourceUrlDigest?: string | null;
  readonly now?: Date;
}

export interface SuppliedPictureIntakeResult {
  readonly rasterPath: string;
  readonly digest: string;
  readonly metadata: SuppliedPictureMetadata;
}

export type SuppliedPictureAuthorizationPort = Pick<ProjectAuthorizationPort, "authorize">;

export interface SuppliedPicturePin {
  readonly captureId: string;
  readonly revisionId: string;
}

export interface SuppliedPictureReferencePort extends Pick<AuthoringReferencePort, "validate"> {
  /** Required before file access: prove the authored source still names this exact pin. */
  validatePicturePin(
    projectId: string,
    reference: SuppliedPictureReference,
    pin: SuppliedPicturePin,
  ): Promise<void>;
}

export interface SuppliedPictureReadOptions {
  readonly projectId: string;
  readonly captureId: string;
  readonly revisionId: string;
  readonly principal: PrincipalRef;
  readonly reference: SuppliedPictureReference;
  readonly authorization: SuppliedPictureAuthorizationPort;
  readonly references: SuppliedPictureReferencePort;
  readonly store: ProjectSuppliedPictureStore;
}

export interface SuppliedPictureIntakeOptions extends SuppliedPictureUpload {
  readonly authorization: SuppliedPictureAuthorizationPort;
  readonly references: SuppliedPictureReferencePort;
  readonly store: ProjectSuppliedPictureStore;
}

/** Conservative limits for extension images; callers may use stricter store limits. */
export const SUPPLIED_PICTURE_LIMITS: Readonly<BoundedRasterLimits> = Object.freeze({
  // Extension windows are not constrained to the capture browser's aspect ratio.
  maxWidth: 16_384,
  maxHeight: 16_384,
  maxBytes: CAPTURE_PROFILE_V2.limits.rasterBytes,
  maxPixels: CAPTURE_PROFILE_V2.limits.outputPixels,
});

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const digest = /^sha256:[0-9a-f]{64}$/u;

function asJson(value: unknown): JsonValue {
  return value as JsonValue;
}

function referenceDigest(reference: SuppliedPictureReference): string {
  return sha256(asJson(reference));
}

function recordKeys(value: object): string {
  return Object.keys(value).sort().join(",");
}

function checkPrincipal(value: unknown): asserts value is PrincipalRef {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid supplied-picture principal");
  const principal = value as Partial<PrincipalRef>;
  if ((principal.principalKind !== "user" && principal.principalKind !== "service") ||
      typeof principal.principalId !== "string" || principal.principalId.length === 0) {
    throw new Error("invalid supplied-picture principal");
  }
}

function checkReference(reference: SuppliedPictureReference, projectId: string): void {
  if (!reference || typeof reference !== "object" || Array.isArray(reference) || reference.projectId !== projectId ||
      typeof reference.resourceId !== "string" || reference.resourceId.length === 0 ||
      typeof reference.resourceVersionDigest !== "string" || !digest.test(reference.resourceVersionDigest)) {
    throw new Error("supplied picture reference is not project-scoped");
  }
  if (reference.kind === "draft_occurrence" &&
      (typeof reference.occurrenceId !== "string" || reference.occurrenceId.length === 0)) {
    throw new Error("supplied picture occurrence is invalid");
  }
}

function checkRect(value: unknown, width: number, height: number): PictureRect {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid supplied picture rectangle");
  const rect = value as Partial<PictureRect>;
  if (![rect.x, rect.y, rect.width, rect.height].every((part) =>
    typeof part === "number" && Number.isSafeInteger(part))) {
    throw new Error("supplied picture rectangle must use integer image pixels");
  }
  if (rect.x! < 0 || rect.y! < 0 || rect.width! <= 0 || rect.height! <= 0 ||
      rect.x! + rect.width! > width || rect.y! + rect.height! > height) {
    throw new Error("supplied picture rectangle is outside the raster");
  }
  return { x: rect.x!, y: rect.y!, width: rect.width!, height: rect.height! };
}

function checkRects(value: unknown, width: number, height: number, required: boolean): readonly PictureRect[] {
  if (!Array.isArray(value) || (required && value.length === 0)) {
    throw new Error(required ? "passage pictures require a highlight rectangle" : "invalid supplied picture rectangles");
  }
  return value.map((rect) => checkRect(rect, width, height));
}

function checkRecord(value: unknown, projectId: string, limits: BoundedRasterLimits): SuppliedPictureMetadata {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid supplied picture receipt");
  const record = value as Partial<SuppliedPictureMetadata>;
  if (record.schemaVersion !== "supplied-picture/v1" ||
      recordKeys(record) !== "captureId,highlightRects,pictureKind,projectId,provenance,raster,reference,referenceDigest,revisionId,schemaVersion" ||
      record.projectId !== projectId || typeof record.captureId !== "string" || !uuid.test(record.captureId) ||
      typeof record.revisionId !== "string" || !uuid.test(record.revisionId) ||
      (record.pictureKind !== "top" && record.pictureKind !== "passage") ||
      typeof record.referenceDigest !== "string" || !digest.test(record.referenceDigest) ||
      record.referenceDigest !== referenceDigest(record.reference as SuppliedPictureReference)) {
    throw new Error("invalid supplied picture receipt");
  }
  const reference = record.reference;
  if (!reference) throw new Error("invalid supplied picture reference");
  checkReference(reference, projectId);
  const raster = record.raster;
  if (!raster || typeof raster !== "object" || Array.isArray(raster) ||
      recordKeys(raster) !== "alpha,byteLength,color,digest,encoding,height,verifierProfile,verifierVersion,width" ||
      raster.encoding !== "png" || raster.color !== "srgb" ||
      (raster.alpha !== "opaque" && raster.alpha !== "present") ||
      raster.verifierProfile !== "png_strict" || raster.verifierVersion !== 1 ||
      !Number.isSafeInteger(raster.width) || !Number.isSafeInteger(raster.height) ||
      !Number.isSafeInteger(raster.byteLength) || raster.byteLength <= 0 ||
      typeof raster.digest !== "string" || !digest.test(raster.digest)) {
    throw new Error("invalid supplied picture raster receipt");
  }
  checkRects(record.highlightRects, raster.width, raster.height, record.pictureKind === "passage");
  if (!record.provenance || typeof record.provenance !== "object" || Array.isArray(record.provenance)) {
    throw new Error("invalid supplied picture provenance");
  }
  const provenance = record.provenance as Partial<SuppliedPictureProvenance>;
  if (recordKeys(provenance) !== "kind,principal,source,sourceUrlDigest,suppliedAt" ||
      provenance.kind !== "user_supplied" || provenance.source !== "browser_extension" ||
      typeof provenance.suppliedAt !== "string" || Number.isNaN(Date.parse(provenance.suppliedAt)) ||
      new Date(provenance.suppliedAt).toISOString() !== provenance.suppliedAt ||
      (provenance.sourceUrlDigest !== null &&
        (typeof provenance.sourceUrlDigest !== "string" || !digest.test(provenance.sourceUrlDigest)))) {
    throw new Error("invalid supplied picture provenance");
  }
  checkPrincipal(provenance.principal);
  if (raster.width > limits.maxWidth || raster.height > limits.maxHeight ||
      raster.width > Math.floor(limits.maxPixels / raster.height) || raster.byteLength > limits.maxBytes) {
    throw new Error("supplied picture exceeds configured bounds");
  }
  return record as SuppliedPictureMetadata;
}

function sameRecord(left: SuppliedPictureMetadata, right: SuppliedPictureMetadata): boolean {
  return canonicalJson(asJson(left)) === canonicalJson(asJson(right));
}

export class ProjectSuppliedPictureStore {
  readonly limits: Readonly<BoundedRasterLimits>;

  constructor(private readonly projectRoot: string, limits: BoundedRasterLimits = SUPPLIED_PICTURE_LIMITS) {
    if (!projectRoot.startsWith("/") || resolve(projectRoot) !== projectRoot) {
      throw new TypeError("trusted project root must be absolute and normalized");
    }
    this.limits = Object.freeze({ ...limits });
  }

  private directory(projectId: string, captureId: string, revisionId: string): string {
    if (!projectId || !uuid.test(captureId) || !uuid.test(revisionId)) throw new Error("invalid supplied picture identity");
    return join(this.projectRoot, "Supplied Pictures", sha256(projectId).slice(7), captureId, revisionId);
  }

  private async checkedDirectory(path: string, label: string): Promise<void> {
    let stat;
    try { stat = await lstat(path); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") throw new Error(`missing supplied picture ${label}`, { cause: error });
      throw error;
    }
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`unsafe supplied picture ${label}`);
  }

  private async checkedFile(path: string, label: string): Promise<void> {
    let stat;
    try { stat = await lstat(path); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") throw new Error(`missing supplied picture ${label}`, { cause: error });
      throw error;
    }
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`unsafe supplied picture ${label}`);
  }

  async read(projectId: string, captureId: string, revisionId: string): Promise<{ readonly record: SuppliedPictureMetadata; readonly path: string } | null> {
    const directory = this.directory(projectId, captureId, revisionId);
    const root = join(this.projectRoot, "Supplied Pictures");
    let rootStat;
    try { rootStat = await lstat(root); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
    if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) throw new Error("unsafe supplied picture store root");
    const projectDirectory = join(root, sha256(projectId).slice(7));
    let projectStat;
    try { projectStat = await lstat(projectDirectory); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
    if (!projectStat.isDirectory() || projectStat.isSymbolicLink()) throw new Error("unsafe supplied picture project directory");
    const captureDirectory = join(projectDirectory, captureId);
    let captureStat;
    try { captureStat = await lstat(captureDirectory); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
    if (!captureStat.isDirectory() || captureStat.isSymbolicLink()) throw new Error("unsafe supplied picture capture directory");
    let directoryStat;
    try { directoryStat = await lstat(directory); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
    if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink()) throw new Error("unsafe supplied picture revision");
    const metadataPath = join(directory, "receipt.json");
    const rasterPath = join(directory, "capture.png");
    await this.checkedFile(metadataPath, "receipt");
    await this.checkedFile(rasterPath, "raster");
    const record = checkRecord(JSON.parse(await readFile(metadataPath, "utf8")) as unknown, projectId, this.limits);
    if (record.captureId !== captureId || record.revisionId !== revisionId) {
      throw new Error("supplied picture receipt does not match the pinned revision");
    }
    const bytes = await readFile(rasterPath);
    let verified: VerifiedRaster;
    try {
      verified = verifyPngWithinBounds(bytes, this.limits);
    } catch (cause) {
      throw new Error("supplied picture failed immutable raster verification", { cause });
    }
    if (canonicalJson(asJson(verified)) !== canonicalJson(asJson(record.raster))) {
      throw new Error("supplied picture failed immutable raster verification");
    }
    return { record, path: rasterPath };
  }

  async publish(record: SuppliedPictureMetadata, bytes: Buffer): Promise<string> {
    const checked = checkRecord(record, record.projectId, this.limits);
    const verified = verifyPngWithinBounds(bytes, this.limits);
    if (canonicalJson(asJson(verified)) !== canonicalJson(asJson(checked.raster))) {
      throw new Error("supplied picture bytes do not match verified descriptor");
    }
    const existing = await this.read(record.projectId, record.captureId, record.revisionId);
    if (existing) {
      if (!sameRecord(existing.record, record)) throw new Error("supplied picture identity conflict");
      return existing.path;
    }
    const root = join(this.projectRoot, "Supplied Pictures");
    await mkdir(root, { recursive: true, mode: 0o700 });
    await this.checkedDirectory(root, "store root");
    const projectDirectory = join(root, sha256(record.projectId).slice(7));
    await mkdir(projectDirectory, { recursive: true, mode: 0o700 });
    await this.checkedDirectory(projectDirectory, "project directory");
    const captureDirectory = join(projectDirectory, record.captureId);
    await mkdir(captureDirectory, { recursive: true, mode: 0o700 });
    await this.checkedDirectory(captureDirectory, "capture directory");
    const scratch = await mkdtemp(join(root, ".staging-"));
    const target = this.directory(record.projectId, record.captureId, record.revisionId);
    try {
      await writeFile(join(scratch, "capture.png"), Buffer.from(bytes), { flag: "wx", mode: 0o600 });
      await writeFile(join(scratch, "receipt.json"), `${JSON.stringify(record)}\n`, { flag: "wx", mode: 0o600 });
      try {
        await rename(scratch, target);
      } catch (error) {
        if (!["EEXIST", "ENOTEMPTY"].includes((error as NodeJS.ErrnoException).code ?? "")) throw error;
        const winner = await this.read(record.projectId, record.captureId, record.revisionId);
        if (!winner || !sameRecord(winner.record, record)) throw new Error("supplied picture identity conflict", { cause: error });
      }
    } finally {
      await rm(scratch, { recursive: true, force: true });
    }
    return join(target, "capture.png");
  }
}

function prepareRecord(input: SuppliedPictureUpload, limits: BoundedRasterLimits): SuppliedPictureMetadata {
  if (!input.projectId || input.reference.projectId !== input.projectId) throw new Error("supplied picture project mismatch");
  checkReference(input.reference, input.projectId);
  checkPrincipal(input.principal);
  const captureId = input.captureId ?? randomUUID();
  if (!uuid.test(captureId)) throw new Error("supplied picture captureId must be a UUID");
  const suppliedAt = (input.now ?? new Date()).toISOString();
  const raster = verifyPngWithinBounds(input.bytes, limits);
  const checkedRects = checkRects(input.highlightRects ?? [], raster.width, raster.height, input.pictureKind === "passage");
  return {
    schemaVersion: "supplied-picture/v1",
    projectId: input.projectId,
    captureId,
    revisionId: randomUUID(),
    pictureKind: input.pictureKind,
    highlightRects: checkedRects,
    reference: input.reference,
    referenceDigest: referenceDigest(input.reference),
    raster,
    provenance: {
      kind: "user_supplied",
      source: "browser_extension",
      principal: input.principal,
      suppliedAt,
      sourceUrlDigest: input.sourceUrlDigest ?? null,
    },
  };
}

export async function intakeSuppliedPicture(options: SuppliedPictureIntakeOptions): Promise<SuppliedPictureIntakeResult> {
  await options.authorization.authorize(options.projectId, options.principal, "capture_commit");
  await options.references.validate(options.projectId, options.reference, "select");
  const metadata = prepareRecord(options, options.store.limits);
  const rasterPath = await options.store.publish(metadata, options.bytes);
  return { rasterPath, digest: metadata.raster.digest, metadata };
}

export async function readSuppliedPicture(options: SuppliedPictureReadOptions): Promise<SuppliedPictureIntakeResult> {
  await options.authorization.authorize(options.projectId, options.principal, "capture_read");
  await options.references.validate(options.projectId, options.reference, "read");
  await options.references.validatePicturePin(options.projectId, options.reference, {
    captureId: options.captureId,
    revisionId: options.revisionId,
  });
  const stored = await options.store.read(options.projectId, options.captureId, options.revisionId);
  if (!stored) throw new Error("supplied picture revision not found");
  return { rasterPath: stored.path, digest: stored.record.raster.digest, metadata: stored.record };
}

