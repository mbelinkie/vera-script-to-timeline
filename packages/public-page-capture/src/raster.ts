import { PNG } from "pngjs";

import { sha256 } from "./crypto.js";

export class RasterVerificationError extends Error {
  override readonly name = "RasterVerificationError";

  constructor(readonly code: string) {
    super("The staged raster failed strict verification.");
  }
}

export interface RasterLimits {
  readonly expectedWidth: number;
  readonly expectedHeight: number;
  readonly maxBytes: number;
  readonly maxPixels: number;
}

/** Bounds for a raster whose viewport is supplied by a trusted host. */
export interface BoundedRasterLimits {
  readonly maxWidth: number;
  readonly maxHeight: number;
  readonly maxBytes: number;
  readonly maxPixels: number;
}

export interface VerifiedRaster {
  readonly width: number;
  readonly height: number;
  readonly encoding: "png";
  readonly color: "srgb";
  readonly alpha: "opaque" | "present";
  readonly byteLength: number;
  readonly digest: string;
  readonly verifierProfile: "png_strict";
  readonly verifierVersion: 1;
}

const pngSignature = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);

function preflightDimensions(
  bytes: Buffer,
  limits: BoundedRasterLimits,
): { readonly width: number; readonly height: number } {
  if (bytes.byteLength < pngSignature.byteLength ||
      !bytes.subarray(0, pngSignature.byteLength).equals(pngSignature) ||
      bytes.byteLength < 33 ||
      bytes.readUInt32BE(8) !== 13 ||
      !bytes.subarray(12, 16).equals(Buffer.from("IHDR", "ascii"))) {
    throw new RasterVerificationError("invalid_png");
  }
  const width = bytes.readUInt32BE(16);
  const height = bytes.readUInt32BE(20);
  if (width <= 0 || height <= 0 || width > limits.maxWidth || height > limits.maxHeight) {
    throw new RasterVerificationError("dimension_limit_exceeded");
  }
  if (width > Math.floor(limits.maxPixels / height)) {
    throw new RasterVerificationError("pixel_limit_exceeded");
  }
  return { width, height };
}

function verifyPngWithBounds(
  bytes: Buffer,
  limits: BoundedRasterLimits,
  expected: { readonly width?: number; readonly height?: number } = {},
): VerifiedRaster {
  if (bytes.byteLength > limits.maxBytes) {
    throw new RasterVerificationError("raster_too_large");
  }
  const dimensions = preflightDimensions(bytes, limits);
  if (expected.width !== undefined && expected.height !== undefined &&
      (dimensions.width !== expected.width || dimensions.height !== expected.height)) {
    throw new RasterVerificationError("dimension_mismatch");
  }

  let decoded: PNG;
  try {
    decoded = PNG.sync.read(bytes, {
      checkCRC: true,
      skipRescale: false,
    });
  } catch {
    throw new RasterVerificationError("invalid_png");
  }
  if (
    decoded.width <= 0 ||
    decoded.height <= 0 ||
    decoded.width > limits.maxWidth ||
    decoded.height > limits.maxHeight ||
    decoded.width > Math.floor(limits.maxPixels / decoded.height)
  ) {
    throw new RasterVerificationError("pixel_limit_exceeded");
  }
  if (expected.width !== undefined && expected.height !== undefined &&
      (decoded.width !== expected.width || decoded.height !== expected.height)) {
    throw new RasterVerificationError("dimension_mismatch");
  }

  let alpha: VerifiedRaster["alpha"] = "opaque";
  for (let index = 3; index < decoded.data.length; index += 4) {
    if (decoded.data[index] !== 255) {
      alpha = "present";
      break;
    }
  }
  return {
    width: decoded.width,
    height: decoded.height,
    encoding: "png",
    color: "srgb",
    alpha,
    byteLength: bytes.byteLength,
    digest: sha256(bytes),
    verifierProfile: "png_strict",
    verifierVersion: 1,
  };
}

export function verifyPng(bytes: Buffer, limits: RasterLimits): VerifiedRaster {
  return verifyPngWithBounds(bytes, {
    maxWidth: limits.expectedWidth,
    maxHeight: limits.expectedHeight,
    maxBytes: limits.maxBytes,
    maxPixels: limits.maxPixels,
  }, { width: limits.expectedWidth, height: limits.expectedHeight });
}

/** Decode and verify a PNG without assuming the fixed capture profile viewport. */
export function verifyPngWithinBounds(
  bytes: Buffer,
  limits: BoundedRasterLimits,
): VerifiedRaster {
  return verifyPngWithBounds(bytes, limits);
}
