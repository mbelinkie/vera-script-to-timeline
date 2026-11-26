import { execFile } from "node:child_process";

export const DIRECT_IMAGE_MAX_BYTES = 56 * 1024 * 1024;

export interface DecodedDirectStill {
  readonly mimeType: "image/png" | "image/jpeg";
  /** Display dimensions after applying orientation. */
  readonly width: number;
  readonly height: number;
  readonly orientation: number;
  readonly frameCount: 1;
}

export interface DirectImageInspector {
  readonly profile: string;
  inspect(bytes: Buffer): Promise<unknown>;
}

export class DirectImageInspectorUnavailable extends Error {}

/** Use the Python interpreter from the installed local agent environment. */
export function pillowDirectImageInspector(pythonExecutable: string): DirectImageInspector {
  return {
    profile: "pillow-direct-image/v1",
    inspect: (bytes) => new Promise((resolve, reject) => {
      const child = execFile(pythonExecutable, ["-I", "-m", "vera_timeline_agent.direct_image_inspect"], {
        timeout: 10_000,
        killSignal: "SIGKILL",
        maxBuffer: 4096,
      }, (error, stdout) => {
        if (error) {
          reject(error.code === 2 ? new Error("invalid image") : new DirectImageInspectorUnavailable());
          return;
        }
        try { resolve(JSON.parse(stdout) as unknown); }
        catch { reject(new DirectImageInspectorUnavailable()); }
      });
      // A decoder may refuse input and exit before consuming all of stdin.
      child.stdin?.on("error", () => {});
      child.stdin?.end(bytes);
    }),
  };
}

export function isDecodedDirectStill(value: unknown): value is DecodedDirectStill {
  if (typeof value !== "object" || value === null) return false;
  const { mimeType, width, height, frameCount, orientation } = value as Partial<DecodedDirectStill>;
  return (mimeType === "image/png" || mimeType === "image/jpeg") &&
    typeof width === "number" && Number.isInteger(width) && width > 0 && width <= 8192 &&
    typeof height === "number" && Number.isInteger(height) && height > 0 && height <= 8192 &&
    width * height <= 16_777_216 && frameCount === 1 &&
    typeof orientation === "number" && Number.isInteger(orientation) && orientation >= 1 && orientation <= 8;
}
