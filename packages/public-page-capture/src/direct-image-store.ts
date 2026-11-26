import { randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { lstat, mkdir, open, rename, rm, rmdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { sha256, stableUuid } from "./crypto.js";
import {
  DIRECT_IMAGE_MAX_BYTES,
  isDecodedDirectStill,
  type DecodedDirectStill,
} from "./direct-image-inspection.js";

export interface DirectImageReceipt extends DecodedDirectStill {
  readonly version: 1;
  readonly mediaReferenceId: string;
  readonly requestedUrlDigest: string;
  readonly finalUrlDigest: string;
  readonly requestedOrigin: string;
  readonly finalOrigin: string;
  readonly contentHash: string;
  readonly byteLength: number;
  readonly attemptId: string;
  readonly acquiredAt: string;
  readonly inspectorProfile: string;
}

export interface DirectImageFailure {
  readonly status: "refused" | "retryable";
  readonly code: string;
  readonly attemptId: string;
}

const digest = /^sha256:[a-f0-9]{64}$/u;
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/u;
const safeCode = /^[a-z][a-z0-9_]{0,63}$/u;
const profile = /^[a-z0-9][a-z0-9/_.-]{0,79}$/u;
const missing = (error: unknown): boolean => (error as NodeJS.ErrnoException).code === "ENOENT";

function isOrigin(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const url = new URL(value);
  return (url.protocol === "https:" || url.protocol === "http:") && url.origin === value;
}

function checkPrivate(stat: { uid: number; mode: number }): void {
  if (stat.uid !== process.getuid?.() || (stat.mode & 0o077) !== 0) {
    throw new Error("direct image storage is not owner-private");
  }
}

async function directory(path: string, create: boolean): Promise<boolean> {
  if (create) {
    try { await mkdir(path, { mode: 0o700 }); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    }
  }
  try {
    const stat = await lstat(path);
    if (!stat.isDirectory()) throw new Error("unsafe direct image directory");
    checkPrivate(stat);
    return true;
  } catch (error) {
    if (missing(error)) return false;
    throw error;
  }
}

async function readPrivate(path: string, limit: number): Promise<Buffer> {
  const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = await file.stat();
    checkPrivate(stat);
    if (!stat.isFile() || stat.nlink !== 1 || stat.size <= 0 || stat.size > limit) {
      throw new Error("unsafe direct image file");
    }
    const bytes = Buffer.alloc(stat.size + 1);
    let offset = 0;
    while (offset < bytes.length) {
      const { bytesRead } = await file.read(bytes, offset, bytes.length - offset, null);
      if (bytesRead === 0) break;
      offset += bytesRead;
    }
    if (offset !== stat.size) throw new Error("direct image file changed while reading");
    return bytes.subarray(0, offset);
  } finally {
    await file.close();
  }
}

async function writePrivate(path: string, value: string | Buffer): Promise<void> {
  await writeFile(path, value, { mode: 0o600, flag: "wx", flush: true });
}

/** The trusted root is pre-created by the local agent in its owner-private storage. */
export class ProjectDirectImageStore {
  constructor(private readonly root: string) {
    if (!root.startsWith("/") || resolve(root) !== root) {
      throw new TypeError("direct image storage must use an absolute normalized root");
    }
  }

  async source(projectId: string, requestedUrlDigest: string): Promise<DirectImageSource> {
    if (!digest.test(requestedUrlDigest) || !projectId) throw new Error("invalid direct image identity");
    if (!await directory(this.root, false)) throw new Error("missing direct image storage root");
    const project = join(this.root, sha256(projectId).slice(7));
    if (!await directory(project, true)) throw new Error("missing direct image project directory");
    const source = join(project, requestedUrlDigest.slice(7));
    if (!await directory(source, true)) throw new Error("missing direct image source directory");
    return new DirectImageSource(source, requestedUrlDigest,
      stableUuid(["direct-image/v1", sha256(projectId), requestedUrlDigest]));
  }
}

class DirectImageSource {
  private readonly committed: string;
  private readonly lock: string;
  private readonly failure: string;
  private readonly publication: string;

  constructor(
    private readonly path: string,
    private readonly urlDigest: string,
    readonly mediaReferenceId: string,
  ) {
    this.committed = join(path, "original");
    this.lock = join(path, "pending");
    this.failure = join(path, "failure.json");
    this.publication = join(path, "publication");
  }

  async read(): Promise<DirectImageReceipt | null> {
    let publication: string;
    try { publication = (await readPrivate(this.publication, 128)).toString(); }
    catch (error) {
      if (missing(error) && !await directory(this.committed, false)) return null;
      throw error;
    }
    if (!await directory(this.committed, false)) throw new Error("incomplete direct image publication");
    const receipt = await readPrivate(join(this.committed, "receipt.json"), 8192);
    if (publication !== sha256(receipt)) throw new Error("direct image receipt failed integrity verification");
    const raw = JSON.parse(receipt.toString()) as unknown;
    if (!isDecodedDirectStill(raw)) throw new Error("invalid direct image receipt");
    const record = raw as DirectImageReceipt;
    if (record.version !== 1 || record.requestedUrlDigest !== this.urlDigest ||
        record.mediaReferenceId !== this.mediaReferenceId || !digest.test(record.finalUrlDigest) ||
        !digest.test(record.contentHash) || !uuid.test(record.attemptId) ||
        !profile.test(record.inspectorProfile) ||
        new Date(record.acquiredAt).toISOString() !== record.acquiredAt ||
        !isOrigin(record.requestedOrigin) || !isOrigin(record.finalOrigin)) {
      throw new Error("invalid direct image receipt");
    }
    const bytes = await readPrivate(join(this.committed, "image"), DIRECT_IMAGE_MAX_BYTES);
    if (bytes.length !== record.byteLength || sha256(bytes) !== record.contentHash) {
      throw new Error("direct image original failed integrity verification");
    }
    return record;
  }

  async claim(): Promise<boolean> {
    try {
      await mkdir(this.lock, { mode: 0o700 });
      return true;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      return false;
    }
  }

  async release(): Promise<void> {
    await rmdir(this.lock);
  }

  async readFailure(): Promise<DirectImageFailure | null> {
    let raw: string;
    try { raw = (await readPrivate(this.failure, 1024)).toString(); }
    catch (error) {
      if (missing(error)) return null;
      throw error;
    }
    const { status, code, attemptId } = JSON.parse(raw) as DirectImageFailure;
    if ((status !== "refused" && status !== "retryable") || !safeCode.test(code) || !uuid.test(attemptId)) {
      throw new Error("invalid direct image failure state");
    }
    return { status, code, attemptId };
  }

  async recordFailure(failure: DirectImageFailure): Promise<void> {
    const staging = join(this.lock, "failure.json");
    await writePrivate(staging, JSON.stringify(failure));
    await rename(staging, this.failure);
  }

  async publish(receipt: DirectImageReceipt, bytes: Buffer, authorize: () => Promise<boolean>): Promise<boolean> {
    const staging = join(this.lock, randomUUID());
    await mkdir(staging, { mode: 0o700 });
    await writePrivate(join(staging, "image"), bytes);
    const metadata = JSON.stringify(receipt);
    await writePrivate(join(staging, "receipt.json"), metadata);
    if (!await authorize()) {
      await rm(staging, { recursive: true });
      return false;
    }
    // The per-source lock serializes all writers, and a committed directory is never empty.
    if (await directory(this.committed, false)) throw new Error("direct image original already exists");
    await writePrivate(this.publication, sha256(metadata));
    await rename(staging, this.committed);
    return true;
  }
}
