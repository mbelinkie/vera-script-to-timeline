import { randomBytes } from "node:crypto";

import { PNG } from "pngjs";
import { describe, expect, it } from "vitest";

import {
  CapabilityError,
  CapabilitySigner,
  canonicalJson,
  sha256,
} from "../src/crypto.js";
import {
  MemoryImmutableObjectStore,
  ObjectStoreError,
  type VerifiedStagingGrant,
} from "../src/object-store.js";
import {
  CAPTURE_PROFILE_V1,
  CAPTURE_PROFILE_V1_DIGEST,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "../src/profile.js";
import { RasterVerificationError, verifyPng } from "../src/raster.js";

function smallPng(width = 2, height = 1): Buffer {
  const png = new PNG({ width, height, colorType: 6 });
  png.data.fill(255);
  return PNG.sync.write(png, { colorType: 6 });
}

describe("canonical fingerprints and capabilities", () => {
  it("canonicalizes objects independently of insertion order", () => {
    expect(canonicalJson({ z: 1, nested: { b: true, a: null }, a: [2, 1] })).toBe(
      '{"a":[2,1],"nested":{"a":null,"b":true},"z":1}',
    );
    expect(sha256({ b: 2, a: 1 })).toBe(sha256({ a: 1, b: 2 }));
  });

  it("signs scoped capabilities and rejects tampering, expiry, and wrong scope", () => {
    const signer = new CapabilitySigner(Buffer.alloc(32, 7));
    const issued = signer.issue(
      {
        purpose: "lease",
        projectId: "11111111-1111-4111-8111-111111111111",
        jobId: "44444444-4444-4444-8444-444444444441",
        leaseEpoch: 3,
      },
      new Date("2026-09-08T17:00:00Z"),
      new Date("2026-09-08T17:01:00Z"),
    );

    expect(issued.token).not.toContain("11111111-1111");
    expect(issued.tokenDigest).toMatch(/^sha256:[0-9a-f]{64}$/u);
    expect(
      signer.verify(issued.token, new Date("2026-09-08T17:00:59Z"), {
        purpose: "lease",
        projectId: "11111111-1111-4111-8111-111111111111",
        jobId: "44444444-4444-4444-8444-444444444441",
        leaseEpoch: 3,
      }).jti,
    ).toBe(issued.claims.jti);

    expect(() =>
      signer.verify(
        `${issued.token.slice(0, -1)}x`,
        new Date("2026-09-08T17:00:10Z"),
      ),
    ).toThrow(CapabilityError);
    expect(() =>
      signer.verify(issued.token, new Date("2026-09-08T17:01:00Z")),
    ).toThrowError(expect.objectContaining({ code: "capability_expired" }));
    expect(() =>
      signer.verify(issued.token, new Date("2026-09-08T17:00:10Z"), {
        purpose: "lease",
        projectId: "11111111-1111-4111-8111-111111111111",
        jobId: "44444444-4444-4444-8444-444444444441",
        leaseEpoch: 4,
      }),
    ).toThrowError(expect.objectContaining({ code: "capability_scope_mismatch" }));
  });
});

describe("frozen 4K profile", () => {
  it("uses a desktop CSS viewport rendered at 2x", () => {
    expect(CAPTURE_PROFILE_V1.render).toMatchObject({
      viewportWidth: 1920,
      viewportHeight: 1080,
      deviceScaleFactor: 2,
    });
    expect([OUTPUT_WIDTH, OUTPUT_HEIGHT]).toEqual([3840, 2160]);
    expect(CAPTURE_PROFILE_V1.limits.outputPixels).toBe(8_294_400);
    expect(CAPTURE_PROFILE_V1.profileDigest).toBe(CAPTURE_PROFILE_V1_DIGEST);
    expect(Object.isFrozen(CAPTURE_PROFILE_V1)).toBe(true);
  });
});

describe("raster verification", () => {
  it("fully decodes a bounded PNG and records verified metadata", () => {
    const bytes = smallPng();
    expect(
      verifyPng(bytes, {
        expectedWidth: 2,
        expectedHeight: 1,
        maxBytes: 4096,
        maxPixels: 2,
      }),
    ).toEqual({
      width: 2,
      height: 1,
      encoding: "png",
      color: "srgb",
      alpha: "opaque",
      byteLength: bytes.byteLength,
      digest: sha256(bytes),
      verifierProfile: "png_strict",
      verifierVersion: 1,
    });
  });

  it("rejects dimensions, bounds, signatures, and CRC corruption", () => {
    const bytes = smallPng();
    expect(() =>
      verifyPng(bytes, {
        expectedWidth: 3,
        expectedHeight: 1,
        maxBytes: 4096,
        maxPixels: 3,
      }),
    ).toThrowError(expect.objectContaining({ code: "dimension_mismatch" }));
    expect(() =>
      verifyPng(bytes, {
        expectedWidth: 2,
        expectedHeight: 1,
        maxBytes: 16,
        maxPixels: 2,
      }),
    ).toThrowError(expect.objectContaining({ code: "raster_too_large" }));
    expect(() =>
      verifyPng(Buffer.from("not png"), {
        expectedWidth: 2,
        expectedHeight: 1,
        maxBytes: 4096,
        maxPixels: 2,
      }),
    ).toThrow(RasterVerificationError);

    const corrupted = Buffer.from(bytes);
    const corruptAt = corrupted.length - 5;
    corrupted[corruptAt] = corrupted[corruptAt]! ^ 0xff;
    expect(() =>
      verifyPng(corrupted, {
        expectedWidth: 2,
        expectedHeight: 1,
        maxBytes: 4096,
        maxPixels: 2,
      }),
    ).toThrowError(expect.objectContaining({ code: "invalid_png" }));
  });
});

describe("immutable staging", () => {
  const grant: VerifiedStagingGrant = {
    grantId: "abababab-abab-4bab-8bab-abababababab",
    projectId: "11111111-1111-4111-8111-111111111111",
    jobId: "44444444-4444-4444-8444-444444444441",
    attemptId: "55555555-5555-4555-8555-555555555551",
    leaseEpoch: 1,
    purpose: "raster",
    mimeType: "image/png",
    maxBytes: 4096,
    expiresAt: "2026-09-08T18:00:00Z",
  };

  it("stages once, copies caller bytes, and promotes idempotently", async () => {
    const store = new MemoryImmutableObjectStore();
    const callerBytes = smallPng();
    const staged = await store.stage(
      grant,
      callerBytes,
      new Date("2026-09-08T17:00:00Z"),
    );
    callerBytes.fill(0);

    await expect(
      store.stage(grant, smallPng(), new Date("2026-09-08T17:00:01Z")),
    ).rejects.toMatchObject({ code: "staging_grant_consumed" });
    expect(await store.readStaged(staged.stagingObjectId)).toEqual(smallPng());

    const first = await store.promote(
      staged.stagingObjectId,
      grant.projectId,
      "capture_raster",
    );
    const recovered = await store.promote(
      staged.stagingObjectId,
      grant.projectId,
      "capture_raster",
    );
    expect(recovered).toEqual(first);
    expect(await store.read(first.objectStoreId)).toEqual(smallPng());
    expect(await store.bytesEqual(first.objectStoreId, smallPng())).toBe(true);
    expect(
      await store.bytesEqual(first.objectStoreId, randomBytes(smallPng().length)),
    ).toBe(false);
  });

  it("rejects expired, mismatched, and oversized staging without retaining bytes", async () => {
    const store = new MemoryImmutableObjectStore();
    await expect(
      store.stage(grant, smallPng(), new Date("2026-09-08T18:00:00Z")),
    ).rejects.toMatchObject({ code: "staging_grant_expired" });
    await expect(
      store.stage(
        { ...grant, grantId: "abababab-abab-4bab-8bab-abababababac", maxBytes: 1 },
        smallPng(),
        new Date("2026-09-08T17:00:00Z"),
      ),
    ).rejects.toMatchObject({ code: "staging_limit_exceeded" });
    await expect(
      store.stage(
        {
          ...grant,
          grantId: "abababab-abab-4bab-8bab-abababababad",
          purpose: "provenance",
        },
        smallPng(),
        new Date("2026-09-08T17:00:00Z"),
      ),
    ).rejects.toBeInstanceOf(ObjectStoreError);
    expect(store.inspectCounts()).toEqual({ staged: 0, promoted: 0 });
  });
});
