import { randomUUID } from "node:crypto";

import { sha256 } from "./crypto.js";

/* eslint-disable @typescript-eslint/require-await -- In-memory async port adapter. */

export type StagingPurpose = "provenance" | "raster";

export interface VerifiedStagingGrant {
  readonly grantId: string;
  readonly projectId: string;
  readonly jobId: string;
  readonly attemptId: string;
  readonly leaseEpoch: number;
  readonly purpose: StagingPurpose;
  readonly mimeType: "application/json" | "image/png";
  readonly maxBytes: number;
  readonly expiresAt: string;
}

export interface StagedObject {
  readonly stagingObjectId: string;
  readonly grantId: string;
  readonly projectId: string;
  readonly jobId: string;
  readonly attemptId: string;
  readonly leaseEpoch: number;
  readonly purpose: StagingPurpose;
  readonly mimeType: "application/json" | "image/png";
  readonly byteLength: number;
  readonly digest: string;
}

export interface PromotedObject {
  readonly objectStoreId: string;
  readonly projectId: string;
  readonly kind: "capture_provenance" | "capture_raster";
  readonly byteLength: number;
  readonly digest: string;
  readonly mimeType: "application/json" | "image/png";
}

export class ObjectStoreError extends Error {
  override readonly name = "ObjectStoreError";

  constructor(readonly code: string) {
    super("Immutable object staging or verification failed.");
  }
}

interface StoredStaging {
  readonly descriptor: StagedObject;
  readonly bytes: Buffer;
}

interface StoredPromoted {
  readonly descriptor: PromotedObject;
  readonly bytes: Buffer;
}

export interface ImmutableObjectStorePort {
  stage(grant: VerifiedStagingGrant, bytes: Buffer, now: Date): Promise<StagedObject>;
  describeStaged(stagingObjectId: string): Promise<StagedObject>;
  readStaged(stagingObjectId: string): Promise<Buffer>;
  promote(
    stagingObjectId: string,
    projectId: string,
    kind: PromotedObject["kind"],
  ): Promise<PromotedObject>;
  read(objectStoreId: string): Promise<Buffer>;
  bytesEqual(objectStoreId: string, bytes: Buffer): Promise<boolean>;
}

export class MemoryImmutableObjectStore implements ImmutableObjectStorePort {
  private readonly consumedGrants = new Set<string>();
  private readonly staged = new Map<string, StoredStaging>();
  private readonly promoted = new Map<string, StoredPromoted>();
  private readonly promotedByStaging = new Map<string, PromotedObject>();

  async stage(
    grant: VerifiedStagingGrant,
    bytes: Buffer,
    now: Date,
  ): Promise<StagedObject> {
    if (this.consumedGrants.has(grant.grantId)) {
      throw new ObjectStoreError("staging_grant_consumed");
    }
    const expiresAt = new Date(grant.expiresAt);
    if (
      !Number.isFinite(expiresAt.getTime()) ||
      now.getTime() >= expiresAt.getTime()
    ) {
      throw new ObjectStoreError("staging_grant_expired");
    }
    if (bytes.byteLength > grant.maxBytes) {
      throw new ObjectStoreError("staging_limit_exceeded");
    }
    const expectedMime =
      grant.purpose === "raster" ? "image/png" : "application/json";
    if (grant.mimeType !== expectedMime) {
      throw new ObjectStoreError("staging_scope_mismatch");
    }

    const descriptor: StagedObject = {
      stagingObjectId: randomUUID(),
      grantId: grant.grantId,
      projectId: grant.projectId,
      jobId: grant.jobId,
      attemptId: grant.attemptId,
      leaseEpoch: grant.leaseEpoch,
      purpose: grant.purpose,
      mimeType: grant.mimeType,
      byteLength: bytes.byteLength,
      digest: sha256(bytes),
    };
    this.consumedGrants.add(grant.grantId);
    this.staged.set(descriptor.stagingObjectId, {
      descriptor,
      bytes: Buffer.from(bytes),
    });
    return descriptor;
  }

  async readStaged(stagingObjectId: string): Promise<Buffer> {
    const value = this.staged.get(stagingObjectId);
    if (!value) throw new ObjectStoreError("staged_object_not_found");
    return Buffer.from(value.bytes);
  }

  async describeStaged(stagingObjectId: string): Promise<StagedObject> {
    const value = this.staged.get(stagingObjectId);
    if (!value) throw new ObjectStoreError("staged_object_not_found");
    return { ...value.descriptor };
  }

  async promote(
    stagingObjectId: string,
    projectId: string,
    kind: PromotedObject["kind"],
  ): Promise<PromotedObject> {
    const existing = this.promotedByStaging.get(stagingObjectId);
    if (existing) {
      if (existing.projectId !== projectId || existing.kind !== kind) {
        throw new ObjectStoreError("promotion_scope_mismatch");
      }
      return existing;
    }
    const source = this.staged.get(stagingObjectId);
    if (!source) throw new ObjectStoreError("staged_object_not_found");
    const expectedPurpose = kind === "capture_raster" ? "raster" : "provenance";
    if (
      source.descriptor.projectId !== projectId ||
      source.descriptor.purpose !== expectedPurpose
    ) {
      throw new ObjectStoreError("promotion_scope_mismatch");
    }
    const descriptor: PromotedObject = {
      objectStoreId: randomUUID(),
      projectId,
      kind,
      byteLength: source.descriptor.byteLength,
      digest: source.descriptor.digest,
      mimeType: source.descriptor.mimeType,
    };
    this.promoted.set(descriptor.objectStoreId, {
      descriptor,
      bytes: Buffer.from(source.bytes),
    });
    this.promotedByStaging.set(stagingObjectId, descriptor);
    return descriptor;
  }

  async read(objectStoreId: string): Promise<Buffer> {
    const value = this.promoted.get(objectStoreId);
    if (!value) throw new ObjectStoreError("object_not_found");
    return Buffer.from(value.bytes);
  }

  async bytesEqual(objectStoreId: string, bytes: Buffer): Promise<boolean> {
    const value = this.promoted.get(objectStoreId);
    if (!value) throw new ObjectStoreError("object_not_found");
    return value.bytes.equals(bytes);
  }

  inspectCounts(): { readonly promoted: number; readonly staged: number } {
    return {
      staged: this.staged.size,
      promoted: this.promoted.size,
    };
  }
}
