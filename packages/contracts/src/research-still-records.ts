import type { ResearchStillSnapshotV2 } from "./generated/contracts-v2.js";

type StillItem = Omit<ResearchStillSnapshotV2, "original" | "provenance">;
type Asset = ResearchStillSnapshotV2["original"];
type Provenance = ResearchStillSnapshotV2["provenance"];
export type ResearchStillChoice = Pick<StillItem, "itemId" | "itemVersion" | "title" | "credit">;
export class UnsupportedKeptStillError extends Error {}

const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
const SHA256 = /^[0-9a-f]{64}$/u;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

function positiveInteger(value: unknown, max = Number.MAX_SAFE_INTEGER): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 && value <= max;
}

function optionalText(value: unknown, max: number): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || [...value].length > max || /[\0\p{Surrogate}]/u.test(value)) {
    throw new Error("Research returned invalid saved still metadata.");
  }
  return value;
}

function optionalUrl(value: unknown): string | undefined {
  const text = optionalText(value, 8192);
  if (text === undefined) return undefined;
  const url = URL.parse(text);
  if (!url || !["https:", "http:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("Research returned an invalid still provenance URL.");
  }
  return text;
}

export function readStillItem(value: unknown, projectId: string, itemId?: string): StillItem {
  if (!record(value) || value.kind !== "still" || !uuid(value.projectId) ||
      value.projectId.toLowerCase() !== projectId.toLowerCase() || !uuid(value.id) ||
      (itemId !== undefined && value.id.toLowerCase() !== itemId.toLowerCase()) ||
      !uuid(value.sourceId) || !positiveInteger(value.version) || !record(value.content)) {
    throw new Error("Research returned an invalid or different saved still.");
  }
  const { content } = value;
  const title = optionalText(content.title, 500)?.trim() || "Saved still";
  const credit = optionalText(content.credit, 2000)?.trim() || undefined;
  const licence = optionalText(content.licence, 2000)?.trim() || undefined;
  const usageNote = optionalText(content.usageNote, 20_000);
  return { researchProjectId: value.projectId.toLowerCase(), itemId: value.id.toLowerCase(),
    itemVersion: value.version, sourceId: value.sourceId.toLowerCase(), title,
    ...(credit === undefined ? {} : { credit }), ...(licence === undefined ? {} : { licence }),
    ...(usageNote === undefined ? {} : { usageNote }) };
}

function readAsset(value: unknown, maxBytes: number, maxEdge: number): Asset {
  if (!record(value) || typeof value.versionId !== "string" || !value.versionId.trim() ||
      optionalText(value.versionId, 1024) === undefined ||
      typeof value.sha256 !== "string" || !SHA256.test(value.sha256) ||
      !positiveInteger(value.byteCount, maxBytes) || !positiveInteger(value.width, maxEdge) ||
      !positiveInteger(value.height, maxEdge) || value.width * value.height > 25_000_000 ||
      (value.mimeType !== "image/jpeg" && value.mimeType !== "image/png" && value.mimeType !== "image/webp")) {
    throw new Error("Research returned an invalid kept still asset.");
  }
  const { versionId, sha256, byteCount, mimeType, width, height } = value;
  return { versionId, sha256, byteCount, mimeType, width, height };
}

function readProvenance(value: unknown): Provenance {
  if (!record(value) ||
      (value.kind !== "url" && value.kind !== "file" && value.kind !== "page_picture" && value.kind !== "still_crop") ||
      typeof value.inputSha256 !== "string" || !SHA256.test(value.inputSha256) ||
      (value.parentItemId !== undefined && !uuid(value.parentItemId))) {
    throw new Error("Research returned invalid kept still provenance.");
  }
  const { kind, inputSha256, parentItemId } = value;
  const sourceUrl = optionalUrl(value.sourceUrl);
  const resolvedUrl = optionalUrl(value.resolvedUrl);
  const pageUrl = optionalUrl(value.pageUrl);
  const altText = optionalText(value.altText, 2000);
  const provenance: Provenance = { kind, inputSha256,
    ...(sourceUrl === undefined ? {} : { sourceUrl }), ...(resolvedUrl === undefined ? {} : { resolvedUrl }),
    ...(pageUrl === undefined ? {} : { pageUrl }), ...(altText === undefined ? {} : { altText }),
    ...(parentItemId === undefined ? {} : { parentItemId }) };
  if (value.crop !== undefined) {
    if (!record(value.crop)) throw new Error("Research returned invalid still crop provenance.");
    const { x, y, width, height } = value.crop;
    if (typeof x !== "number" || typeof y !== "number" || typeof width !== "number" || typeof height !== "number" ||
        ![x, y, width, height].every(Number.isFinite) || x < 0 || y < 0 || width <= 0 || height <= 0 ||
        x + width > 1 || y + height > 1) throw new Error("Research returned invalid still crop provenance.");
    provenance.crop = { x, y, width, height };
  }
  return provenance;
}

export function readKeptStillManifest(value: unknown) {
  if (!record(value) || !record(value.assets)) throw new Error("Research returned an invalid kept still manifest.");
  const original = readAsset(value.assets.original, 20 * 1024 * 1024, 25_000_000);
  // Match Timeline's ordinary still-preparation raster limits.
  if (original.width > 8192 || original.height > 8192 || original.width * original.height > 16_777_216) {
    throw new UnsupportedKeptStillError("The kept image exceeds Timeline's still size limits.");
  }
  return { original,
    thumbnail: readAsset(value.assets.thumbnail, 1024 * 1024, 320),
    provenance: readProvenance(value.provenance) };
}
