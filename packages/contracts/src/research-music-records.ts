import type { ResearchMusicSelectionV2 } from "./generated/contracts-v2.js";
import { readResearchLibraryItem } from "./research-library-records.js";

export const MAX_RESEARCH_AUDIO_BYTES = 50 * 1024 * 1024;
const MAX_DURATION_MS = 30 * 60_000;
const audioMimeTypes = new Set(["audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg", "audio/flac", "audio/webm"]);

export type MusicSelection = Omit<ResearchMusicSelectionV2, "sourceVersion" | "playbackHash">;
export type ResearchMusicChoice =
  | { status: "candidate"; selection: ResearchMusicSelectionV2 }
  | { status: "relink_required" | "unavailable"; selection: MusicSelection };

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function milliseconds(value: unknown, minimum: number): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= minimum && value <= MAX_DURATION_MS;
}

export function readMusicSelection(value: unknown, projectId: string, itemId: string): MusicSelection | null {
  const item = readResearchLibraryItem(value, projectId, itemId, "audio");
  const { role, title, startMs, endMs } = item.content;
  if (role !== "music" || typeof title !== "string" || !title.trim() || title.length > 500 ||
      /[\0\p{Surrogate}]/u.test(title) || !milliseconds(startMs, 0) || !milliseconds(endMs, 1) || endMs <= startMs) return null;
  return {
    researchProjectId: projectId.toLowerCase(), sourceId: item.sourceId, itemId: itemId.toLowerCase(),
    itemVersion: item.version, title, startMs, endMs,
  };
}

export function readMusicAsset(value: unknown, selection: MusicSelection) {
  if (!record(value) || !record(value.origin) ||
      !milliseconds(value.durationMs, 1) || selection.endMs > value.durationMs ||
      !milliseconds(value.playbackDurationMs, 1) || typeof value.mimeType !== "string" ||
      !audioMimeTypes.has(value.mimeType) || typeof value.playbackSha256 !== "string" ||
      !/^[0-9a-f]{64}$/u.test(value.playbackSha256)) return { status: "unavailable" } as const;
  if (value.origin.kind === "file") return { status: "relink_required" } as const;
  if (value.origin.kind !== "url" || value.playbackDurationMs !== value.durationMs) {
    return { status: "unavailable" } as const;
  }
  return { status: "candidate", mimeType: value.mimeType, playbackHash: "sha256:" + value.playbackSha256 } as const;
}
