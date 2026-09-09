import { stableUuid } from "./crypto.js";

export function captureConfigurationVersionId(
  projectId: string,
  captureId: string,
  configurationVersion: number,
): string {
  return stableUuid([
    "capture_configuration",
    projectId,
    captureId,
    configurationVersion,
  ]);
}

export function captureRasterArtifactId(
  projectId: string,
  digest: string,
  byteLength: number,
  width: number,
  height: number,
  alpha: "opaque" | "present",
): string {
  return stableUuid([
    "capture_raster",
    projectId,
    digest,
    byteLength,
    "image/png",
    width,
    height,
    "png",
    "srgb",
    alpha,
    "png_strict",
    1,
  ]);
}
