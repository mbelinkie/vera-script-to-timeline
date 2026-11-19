import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { AuthorizationDecisionRef, PrincipalRef } from "@vera/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PNG } from "pngjs";

import {
  intakeSuppliedPicture,
  ProjectSuppliedPictureStore,
  readSuppliedPicture,
  type SuppliedPicturePin,
  type SuppliedPictureReference,
} from "../src/supplied-picture.js";
import { verifyPngWithinBounds } from "../src/raster.js";

const PROJECT = "00000000-0000-4000-8000-000000000641";
const CAPTURE = "64164164-1641-4641-8641-641641641641";
const ACTOR: PrincipalRef = { principalKind: "user", principalId: "user-641" };
const reference: SuppliedPictureReference = {
  kind: "draft_occurrence", projectId: PROJECT, resourceId: "doc-641",
  resourceVersionDigest: `sha256:${"a".repeat(64)}`, occurrenceId: "quote-641",
};
const directories: string[] = [];

function raster(width = 4, height = 3): Buffer {
  const png = new PNG({ width, height, colorType: 6 });
  png.data.fill(255);
  return PNG.sync.write(png, { colorType: 6 });
}

function hash(value: Buffer): string {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

async function root(): Promise<string> {
  const value = await mkdtemp(join(tmpdir(), "vera-641-supplied-"));
  directories.push(value);
  return value;
}

function ports() {
  return {
    authorization: {
      authorize: vi.fn((): Promise<AuthorizationDecisionRef> => Promise.resolve({
        decisionId: "decision-641", action: "capture_read", principal: ACTOR, projectId: PROJECT,
        role: "editor", decidedAt: "2026-11-18T20:00:00Z", recheckMode: "every_request",
      })),
    },
    references: {
      validate: vi.fn(() => Promise.resolve()),
      validatePicturePin: vi.fn((project: string, pinReference: SuppliedPictureReference, pin: SuppliedPicturePin) => {
        void project;
        void pinReference;
        void pin;
        return Promise.resolve();
      }),
    },
  };
}

afterEach(async () => {
  vi.restoreAllMocks();
  for (const path of directories.splice(0)) await rm(path, { recursive: true, force: true });
});

describe("supplied picture intake", () => {
  it("rejects duplicate IHDR chunks and unsupported interlace modes before decode", () => {
    const bytes = raster();
    const ihdr = bytes.subarray(8, 33);
    const duplicateIhdr = Buffer.concat([bytes.subarray(0, 33), ihdr, bytes.subarray(33)]);
    expect(() => verifyPngWithinBounds(duplicateIhdr, new ProjectSuppliedPictureStore("/tmp").limits))
      .toThrowError(expect.objectContaining({ code: "invalid_png" }));
    const unsupportedInterlace = Buffer.from(bytes);
    unsupportedInterlace[28] = 2;
    expect(() => verifyPngWithinBounds(unsupportedInterlace, new ProjectSuppliedPictureStore("/tmp").limits))
      .toThrowError(expect.objectContaining({ code: "invalid_png" }));
  });

  it("stores a checked passage PNG with user provenance and reads the exact pinned revision", async () => {
    const bytes = raster();
    const projectRoot = await root();
    const store = new ProjectSuppliedPictureStore(projectRoot);
    const port = ports();
    const first = await intakeSuppliedPicture({
      projectId: PROJECT, principal: ACTOR, reference, bytes, pictureKind: "passage",
      highlightRects: [{ x: 1, y: 1, width: 2, height: 1 }], now: new Date("2026-11-18T20:00:00Z"),
      ...port, store,
    });
    expect(first.metadata).toMatchObject({
      projectId: PROJECT, pictureKind: "passage", highlightRects: [{ x: 1, y: 1, width: 2, height: 1 }],
      raster: { width: 4, height: 3, digest: hash(bytes) },
      provenance: { kind: "user_supplied", source: "browser_extension", principal: ACTOR },
    });
    expect(first.metadata.captureId).toMatch(/^[0-9a-f-]{36}$/u);
    expect(first.metadata.revisionId).toMatch(/^[0-9a-f-]{36}$/u);
    expect(await readFile(first.rasterPath)).toEqual(bytes);
    const read = await readSuppliedPicture({
      projectId: PROJECT, captureId: first.metadata.captureId, revisionId: first.metadata.revisionId,
      principal: ACTOR, reference, ...port, store,
    });
    expect(read).toMatchObject({ rasterPath: first.rasterPath, digest: hash(bytes), metadata: first.metadata });
    expect(port.authorization.authorize).toHaveBeenCalledWith(PROJECT, ACTOR, "capture_read");
    expect(port.references.validate).toHaveBeenCalledWith(PROJECT, reference, "read");
  });

  it("requires passage geometry, keeps top pictures rect-free, and makes each upload a new revision", async () => {
    const projectRoot = await root();
    const store = new ProjectSuppliedPictureStore(projectRoot);
    const port = ports();
    await expect(intakeSuppliedPicture({ projectId: PROJECT, principal: ACTOR, reference, bytes: raster(), pictureKind: "passage", ...port, store }))
      .rejects.toThrow("require a highlight rectangle");
    const top = await intakeSuppliedPicture({ projectId: PROJECT, principal: ACTOR, reference, captureId: CAPTURE, bytes: raster(), pictureKind: "top", ...port, store });
    const second = await intakeSuppliedPicture({ projectId: PROJECT, principal: ACTOR, reference, captureId: CAPTURE, bytes: raster(), pictureKind: "top", ...port, store });
    expect(top.metadata.captureId).toBe(second.metadata.captureId);
    expect(top.metadata.revisionId).not.toBe(second.metadata.revisionId);
    expect(top.metadata.highlightRects).toEqual([]);
    const portrait = await intakeSuppliedPicture({
      projectId: PROJECT, principal: ACTOR, reference, bytes: raster(1600, 2400), pictureKind: "top", ...port, store,
    });
    expect(portrait.metadata.raster).toMatchObject({ width: 1600, height: 2400 });
  }, 20_000);

  it("rejects out-of-bounds geometry, stale references, and tampered bytes", async () => {
    const projectRoot = await root();
    const store = new ProjectSuppliedPictureStore(projectRoot);
    const port = ports();
    port.references.validatePicturePin = vi.fn((project: string, pinReference: SuppliedPictureReference, pin: SuppliedPicturePin) => {
      void project;
      void pin;
      if (pinReference.resourceVersionDigest !== reference.resourceVersionDigest) throw new Error("not pinned");
      return Promise.resolve();
    });
    const result = await intakeSuppliedPicture({
      projectId: PROJECT, principal: ACTOR, reference, bytes: raster(), pictureKind: "passage",
      highlightRects: [{ x: 0, y: 0, width: 4, height: 3 }], ...port, store,
    });
    await expect(intakeSuppliedPicture({
      projectId: PROJECT, principal: ACTOR, reference, bytes: raster(), pictureKind: "passage",
      highlightRects: [{ x: 3, y: 2, width: 2, height: 1 }], ...port, store,
    })).rejects.toThrow("outside the raster");
    const stale = { ...reference, resourceVersionDigest: `sha256:${"b".repeat(64)}` };
    await expect(readSuppliedPicture({
      projectId: PROJECT, captureId: result.metadata.captureId, revisionId: result.metadata.revisionId,
      principal: ACTOR, reference: stale, ...port, store,
    })).rejects.toThrow("not pinned");
    await writeFile(result.rasterPath, Buffer.alloc((await readFile(result.rasterPath)).byteLength, 0x41));
    await expect(store.read(PROJECT, result.metadata.captureId, result.metadata.revisionId))
      .rejects.toThrow("immutable raster verification");
  });
});

