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

export function verifyPng(bytes: Buffer, limits: RasterLimits): VerifiedRaster {
  if (bytes.byteLength > limits.maxBytes) {
    throw new RasterVerificationError("raster_too_large");
  }
  if (
    bytes.byteLength < pngSignature.byteLength ||
    !bytes.subarray(0, pngSignature.byteLength).equals(pngSignature)
  ) {
    throw new RasterVerificationError("invalid_png");
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
    decoded.width * decoded.height > limits.maxPixels
  ) {
    throw new RasterVerificationError("pixel_limit_exceeded");
  }
  if (
    decoded.width !== limits.expectedWidth ||
    decoded.height !== limits.expectedHeight
  ) {
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
