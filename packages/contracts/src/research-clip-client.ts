/**
 * Development-only bridge to the local Research API.
 * The bearer is deliberately confined to loopback HTTP requests and is never
 * included in errors or returned values.
 */
import { createHash } from "node:crypto";
import type { ResearchClipSnapshotV2, ResearchQuotePictureV2, ResearchStillAssetV2 } from "./generated/contracts-v2.js";
import {
  snapshotResearchCandidateV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";
import { readResearchLibraryItem, readResearchLibrarySource, type ResearchLibraryItemKind } from "./research-library-records.js";
import { describeResearchQuote, readResearchQuote, type ResearchQuoteRecord } from "./research-quote-records.js";
import {
  readKeptOriginalAsset, readKeptStillManifest, readStillItem,
  UnsupportedKeptStillError, type ResearchStillChoice,
} from "./research-still-records.js";

export { publicResearchQuote, type ResearchQuoteChoice, type ResearchQuoteRecord } from "./research-quote-records.js";

export interface ResearchProject {
  id: string;
  name: string;
}

const UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);
const DEFAULT_ORIGIN = "http://127.0.0.1:43111";
const STILL_PAGE_SIZE = 12;
const QUOTE_PAGE_SIZE = 20;
const MAX_LIBRARY_OFFSET = 100_000;
const EXTENSION_CAPTURE_PAGE_SIZE = 50;

function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function validId(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

async function readKeptImage(response: Response, asset: ResearchStillAssetV2): Promise<Uint8Array> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Research returned an empty kept image.");
  const bytes = new Uint8Array(asset.byteCount);
  let offset = 0;
  try {
    const length = response.headers.get("content-length");
    if (response.status !== 200 || response.headers.get("content-type") !== asset.mimeType ||
        (length !== null && length !== String(asset.byteCount))) throw new Error("Invalid Research image headers.");
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (offset + value.length > bytes.length) throw new Error("Research image exceeds its kept size.");
      bytes.set(value, offset);
      offset += value.length;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
  if (offset !== bytes.length || createHash("sha256").update(bytes).digest("hex") !== asset.sha256) {
    throw new Error("Research image does not match the kept copy.");
  }
  return bytes;
}

export class ResearchReadError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type LibraryUpdate = { expectedVersion: number } & ({ content: object } | { latestDisplayText: string });

export function isResearchId(value: string): boolean {
  return UUID.test(value);
}

/** Refuse remote, credential-bearing, or path-extended service URLs. */
export function researchOrigin(raw = DEFAULT_ORIGIN): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("Research URL must be a bare loopback HTTP origin.");
  }
  if (
    (url.protocol !== "http:" && url.protocol !== "https:") ||
    !LOOPBACK_HOSTS.has(url.hostname) ||
    url.username !== "" || url.password !== "" ||
    url.pathname !== "/" || url.search !== "" || url.hash !== ""
  ) {
    throw new Error("Research URL must be a bare loopback HTTP origin.");
  }
  return url.origin;
}

function safeProjectLabel(project: ResearchProject): string {
  // API data can become CLI output, so never emit control characters/ANSI escapes.
  const name = [...project.name].map((char) => {
    const code = char.codePointAt(0)!;
    return code < 32 || (code >= 127 && code <= 159) ||
      /[\p{Cf}\p{Zl}\p{Zp}]/u.test(char) ? " " : char;
  }).join("");
  return `${name} (${project.id})`;
}

/** A UUID is passed straight to the server (which enforces project access). */
export function resolveProjectName(nameOrId: string, visible: readonly ResearchProject[]): string {
  if (UUID.test(nameOrId)) return nameOrId.toLowerCase();
  const matches = visible.filter((project) =>
    project.name.toLocaleLowerCase("en-US") === nameOrId.toLocaleLowerCase("en-US"));
  if (matches.length === 1) return matches[0]!.id;
  const choices = (matches.length > 0 ? matches : visible).map(safeProjectLabel).join(", ") || "(none)";
  if (matches.length > 1) {
    throw new Error(`Several Research projects have that name; use an ID: ${choices}.`);
  }
  throw new Error(`No visible Research project matches that name; visible projects: ${choices}.`);
}

export function createResearchClient(options: {
  bearer: string | undefined;
  url?: string;
  request?: typeof fetch;
}) {
  const origin = researchOrigin(options.url);
  const bearer = options.bearer;
  if (!bearer?.trim() || /[\r\n]/.test(bearer)) {
    throw new Error("Set VERA_RESEARCH_BEARER before accessing Research.");
  }
  const request = options.request ?? fetch;

  async function send(path: string, accept: string, update?: LibraryUpdate): Promise<Response> {
    let response: Response;
    try {
      response = await request(new URL(path, origin), {
        method: update ? "PATCH" : "GET",
        redirect: "manual",
        headers: {
          Accept: accept, Authorization: `Bearer ${bearer}`,
          ...(update ? { "Content-Type": "application/json" } : {}),
        },
        ...(update ? { body: JSON.stringify(update) } : {}),
        signal: AbortSignal.timeout(10_000),
      });
    } catch {
      // Fetch errors may embed the full request URL or headers, including secrets.
      throw new Error(update ? "Research could not confirm the quote edit. Reload the quote to check its current version."
        : "Research is unavailable on this Mac.");
    }
    if (response.status >= 300 && response.status < 400 || response.redirected) {
      throw new Error(update ? "Research redirected the edit; no redirect was followed."
        : "Research redirected the read-only request; no redirect was followed.");
    }
    if (response.status === 401 || response.status === 403) {
      throw new ResearchReadError(response.status, "Research refused the credential or project access.");
    }
    if (response.status === 404) {
      throw new ResearchReadError(404, path.includes("/clips") ? "Research project or clip was not found."
        : "Research project or record was not found.");
    }
    if (update && response.status === 409) {
      throw new ResearchReadError(409, "Research quote changed before the edit was saved. Reload the quote and retry.");
    }
    if (!response.ok) {
      throw new Error(update ? "Research could not confirm the quote edit. Reload the quote to check its current version."
        : "Research could not complete this read-only request.");
    }
    return response;
  }

  async function requestJson(path: string, update?: LibraryUpdate): Promise<unknown> {
    const response = await send(path, "application/json", update);
    try {
      return await response.json() as unknown;
    } catch {
      throw new Error("Research returned invalid JSON.");
    }
  }

  const get = (path: string) => requestJson(path);

  const manifest = async (projectId: string, itemId: string) =>
    readKeptStillManifest(await get(`${libraryPath(projectId, "stills", itemId)}/assets`));

  async function keptStill(projectId: string, itemId: string, version: number) {
    const item = readStillItem(await get(libraryPath(projectId, "items", itemId)), projectId, itemId);
    if (item.itemVersion !== version) throw new ResearchReadError(409, "The saved still has changed.");
    try {
      return { item, kept: await manifest(projectId, itemId) };
    } catch (error) {
      if (error instanceof UnsupportedKeptStillError) throw new ResearchReadError(422, error.message);
      throw error;
    }
  }

  function validatedCandidate(input: unknown): ResearchLoggedCandidateInputV2 {
    try {
      snapshotResearchCandidateV2(input as ResearchLoggedCandidateInputV2);
      return input as ResearchLoggedCandidateInputV2;
    } catch {
      // Never forward upstream data or validation errors to CLI stderr.
      throw new Error("Research returned an invalid logged clip.");
    }
  }

  async function item(projectId: string, itemId: string, kind: ResearchLibraryItemKind) {
    const path = libraryPath(projectId, "items", itemId);
    return readResearchLibraryItem(await get(path), projectId, itemId, kind);
  }

  // Active published workspace only; no acquisition, historical read, or
  // guessed word timing. Keep the response bounded before parsing JSON.
  async function matchedClipCues(pin: ResearchClipSnapshotV2): Promise<ResearchClipCue[] | null> {
    if (!UUID.test(pin.researchProjectId) || !UUID.test(pin.catalogVideoId)) return null;
    const response = await send(
      `/api/projects/${pin.researchProjectId}/videos/${pin.catalogVideoId}/transcript?preferredLanguage=en`,
      "application/json",
    );
    const reader = response.body?.getReader();
    if (!reader) return null;
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > 4 * 1024 * 1024) {
          await reader.cancel();
          return null;
        }
        chunks.push(part.value);
      }
      return matchingResearchClipCues(JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown, pin);
    } catch {
      return null;
    } finally {
      reader.releaseLock();
    }
  }

  async function source(projectId: string, sourceId: string) {
    return readResearchLibrarySource(
      await get(libraryPath(projectId, "sources", sourceId)), projectId, sourceId,
    );
  }

  async function quotePicture(projectId: string, quote: ResearchQuoteRecord, thumbnail = false) {
    if (!validId(projectId) || projectId.toLowerCase() !== quote.researchProjectId ||
        !validId(quote.sourceId) || !validId(quote.itemId)) {
      throw new Error("Research picture owner does not match the quote.");
    }
    projectId = projectId.toLowerCase();
    const project = `/api/projects/${projectId}`;
    // Pictures are optional. A permission failure still refuses the operation.
    async function optional<T>(read: () => T | Promise<T>): Promise<T | null> {
      try { return await read(); } catch (error) {
        if (error instanceof ResearchReadError && [401, 403].includes(error.status)) throw error;
        return null;
      }
    }

    async function top(): Promise<ResearchQuotePictureV2 | null> {
      const path = `${project}/sources/${quote.sourceId}/extension-captures`;
      for (let offset = 0; offset <= MAX_LIBRARY_OFFSET; offset += EXTENSION_CAPTURE_PAGE_SIZE) {
        const page = await optional(() => get(`${path}?offset=${offset}`));
        if (page === null) return null;
        if (!Array.isArray(page) || page.length > EXTENSION_CAPTURE_PAGE_SIZE) {
          throw new Error("Invalid Research article picture list.");
        }
        for (const receipt of page as unknown[]) {
          if (!record(receipt) || receipt.sourceId !== quote.sourceId || !validId(receipt.captureId) ||
              !Array.isArray(receipt.assets)) throw new Error("Research article picture has a different source.");
          const asset = (receipt.assets as unknown[]).find((candidate): candidate is Record<string, unknown> =>
            record(candidate) && candidate.role === "top");
          if (!asset) continue;
          if (!validId(asset.revisionId) || asset.mimeType !== "image/png" ||
              !record(asset.provenance) || asset.provenance.kind !== "user_supplied" ||
              asset.provenance.source !== "browser_extension") throw new Error("Invalid Research article picture revision.");
          const original = await optional(() => readKeptOriginalAsset(asset));
          if (original) return { researchProjectId: projectId, ownerKind: "web_capture",
            ownerId: receipt.captureId.toLowerCase(), revisionId: asset.revisionId.toLowerCase(), original };
        }
        if (page.length < EXTENSION_CAPTURE_PAGE_SIZE) return null;
      }
      return null;
    }

    async function reference(ownerKind: "source" | "quote", ownerId: string) {
      const path = `${project}/library-reference-pictures/${ownerKind}/${ownerId}`;
      return optional(async () => {
        const manifest = await get(path);
        if (!record(manifest) || !validId(manifest.revisionId) || !record(manifest.assets)) {
          throw new Error("Invalid Research attached picture revision.");
        }
        const picture: ResearchQuotePictureV2 = { researchProjectId: projectId, ownerKind, ownerId,
          revisionId: manifest.revisionId.toLowerCase(), original: readKeptOriginalAsset(manifest.assets.original) };
        const asset = thumbnail ? readKeptOriginalAsset(manifest.assets.thumbnail) : picture.original;
        const bytes = await readKeptImage(
          await send(`${path}/${thumbnail ? "thumbnail" : "original"}`, asset.mimeType), asset,
        );
        const after = await get(path);
        if (!record(after) || after.revisionId !== manifest.revisionId || !record(after.assets) ||
            JSON.stringify(readKeptOriginalAsset(after.assets.original)) !== JSON.stringify(picture.original)) {
          throw new Error("The attached picture changed while its kept bytes were read.");
        }
        return { picture, bytes, mimeType: asset.mimeType };
      });
    }

    if (quote.sourceKind === "web_page") {
      const picture = await optional(top);
      if (picture) {
        const { ownerId, revisionId, original } = picture;
        const retained = await optional(async () => ({ picture, mimeType: original.mimeType,
          bytes: await readKeptImage(
            await send(`${project}/extension-captures/${ownerId}/assets/top?revisionId=${revisionId}`, original.mimeType),
            original,
          ) }));
        if (retained) return retained;
      }
    }
    return await reference("quote", quote.itemId) ?? reference("source", quote.sourceId);
  }

  return {
    item,
    matchedClipCues,
    source,
    readQuotePicture: quotePicture,

    async quotes(projectId: string, offset: number): Promise<{ quotes: ResearchQuoteRecord[]; nextOffset: number | null }> {
      if (!UUID.test(projectId) || !Number.isSafeInteger(offset) || offset < 0 || offset > MAX_LIBRARY_OFFSET) {
        throw new Error("Invalid Research quote page.");
      }
      const params = new URLSearchParams({ kind: "quote", limit: String(QUOTE_PAGE_SIZE + 1), offset: String(offset) });
      const page = await get(`/api/projects/${projectId}/items?${params}`);
      if (!Array.isArray(page) || page.length > QUOTE_PAGE_SIZE + 1) throw new Error("Invalid Research quote page.");
      const choices = page.slice(0, QUOTE_PAGE_SIZE).map((value: unknown) => readResearchQuote(value, projectId));
      const sources = new Map([...new Set(choices.map(({ sourceId }) => sourceId))]
        .map((sourceId) => [sourceId, source(projectId, sourceId)]));
      const quotes = await Promise.all(choices.map(async (choice) =>
        describeResearchQuote(choice, await sources.get(choice.sourceId)!)));
      const more = offset + QUOTE_PAGE_SIZE;
      return { quotes, nextOffset: page.length > QUOTE_PAGE_SIZE && more <= MAX_LIBRARY_OFFSET ? more : null };
    },

    async quote(projectId: string, quoteId: string): Promise<ResearchQuoteRecord> {
      const quote = readResearchQuote(await get(libraryPath(projectId, "items", quoteId)), projectId, quoteId);
      return describeResearchQuote(quote, await source(projectId, quote.sourceId));
    },

    async setQuoteDisplayText(projectId: string, quoteId: string, expectedVersion: number, latestDisplayText: string) {
      if (!Number.isSafeInteger(expectedVersion) || expectedVersion < 1 ||
          typeof latestDisplayText !== "string" || latestDisplayText.length > 20_000 ||
          /[\0\p{Surrogate}]/u.test(latestDisplayText)) {
        throw new Error("Research display text is invalid or too long.");
      }
      const response = await requestJson(libraryPath(projectId, "items", quoteId), { expectedVersion, latestDisplayText });
      const saved = readResearchLibraryItem(response, projectId, quoteId, "quote");
      if (saved.version <= expectedVersion || saved.content.latestDisplayText !== latestDisplayText) {
        throw new Error("Research could not confirm the quote display edit.");
      }
    },

    async setQuoteCitation(projectId: string, quoteId: string, text: string | undefined) {
      if (text !== undefined && (text.length > 20_000 || /[\0\p{Surrogate}]/u.test(text))) {
        throw new Error("Research citation text is invalid or too long.");
      }
      const quote = await item(projectId, quoteId, "quote");
      if (text === quote.content.citationOverride) return;
      const content = { ...quote.content };
      delete content.latestDisplayText;
      if (text === undefined) delete content.citationOverride;
      else content.citationOverride = text;
      const result = await requestJson(libraryPath(projectId, "items", quoteId), {
        expectedVersion: quote.version, content,
      });
      const saved = readResearchLibraryItem(result, projectId, quoteId, "quote");
      if (saved.sourceId !== quote.sourceId || saved.content.citationOverride !== text) {
        throw new Error("Research could not confirm the quote edit. Reload the quote to check its current citation.");
      }
    },

    async projects(): Promise<ResearchProject[]> {
      const result = await get("/api/projects");
      if (!Array.isArray(result) || !result.every((project: unknown) =>
        project !== null && typeof project === "object" && !Array.isArray(project) &&
        UUID.test(String((project as ResearchProject).id)) &&
        typeof (project as ResearchProject).name === "string" &&
        (project as ResearchProject).name.trim().length > 0)) {
        throw new Error("Research returned an invalid project list.");
      }
      return result as ResearchProject[];
    },

    async clips(projectId: string): Promise<ResearchLoggedCandidateInputV2[]> {
      if (!UUID.test(projectId)) throw new Error("Research project ID must be a UUID.");
      const result = await get(`/api/projects/${projectId}/clips`);
      if (!Array.isArray(result)) throw new Error("Research returned an invalid clip list.");
      return result.map((item: unknown) => {
        const clip = validatedCandidate(item);
        if (clip.projectId.toLowerCase() !== projectId.toLowerCase()) {
          throw new Error("Research returned a clip from another project.");
        }
        return clip;
      });
    },

    async clip(projectId: string, clipId: string): Promise<ResearchLoggedCandidateInputV2> {
      if (!UUID.test(projectId) || !UUID.test(clipId)) {
        throw new Error("Research project and clip IDs must be UUIDs.");
      }
      const clip = validatedCandidate(await get(`/api/projects/${projectId}/clips/${clipId}`));
      if (clip.projectId.toLowerCase() !== projectId.toLowerCase() ||
          clip.id.toLowerCase() !== clipId.toLowerCase()) {
        throw new Error("Research returned a different clip identity.");
      }
      return clip;
    },

    async stills(projectId: string, offset: number): Promise<{ stills: ResearchStillChoice[]; nextOffset: number | null }> {
      if (!UUID.test(projectId) || !Number.isSafeInteger(offset) || offset < 0 || offset > 100_000) {
        throw new Error("Invalid Research still page.");
      }
      const items = await get(`/api/projects/${projectId}/items?kind=still&limit=${STILL_PAGE_SIZE + 1}&offset=${offset}`);
      if (!Array.isArray(items) || items.length > STILL_PAGE_SIZE + 1) throw new Error("Invalid Research still page.");
      const choices = await Promise.all(items.slice(0, STILL_PAGE_SIZE).map(async (entry: unknown) => {
        const item = readStillItem(entry, projectId);
        try {
          await manifest(projectId, item.itemId);
          const { itemId, itemVersion, title, credit } = item;
          return { itemId, itemVersion, title, ...(credit === undefined ? {} : { credit }) };
        } catch (error) {
          if (error instanceof UnsupportedKeptStillError || error instanceof ResearchReadError && error.status === 404) return null;
          throw error;
        }
      }));
      const more = offset + STILL_PAGE_SIZE;
      return { stills: choices.filter((choice) => choice !== null),
        nextOffset: items.length > STILL_PAGE_SIZE && more <= 100_000 ? more : null };
    },

    async still(projectId: string, itemId: string, version: number) {
      const { item, kept } = await keptStill(projectId, itemId, version);
      return { ...item, original: kept.original, provenance: kept.provenance };
    },

    async stillThumbnail(projectId: string, itemId: string, version: number) {
      const { kept: { thumbnail } } = await keptStill(projectId, itemId, version);
      const response = await send(`${libraryPath(projectId, "stills", itemId)}/assets/thumbnail`, thumbnail.mimeType);
      return { bytes: await readKeptImage(response, thumbnail), mimeType: thumbnail.mimeType };
    },
  };
}

function libraryPath(projectId: string, kind: "items" | "sources" | "stills", recordId: string): string {
  if (!UUID.test(projectId) || !UUID.test(recordId)) {
    throw new Error("Research project and record IDs must be UUIDs.");
  }
  return `/api/projects/${projectId}/${kind}/${recordId}`;
}


export interface ResearchClipCue {
  startMs: number;
  endMs: number;
  text: string;
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** The local-agent workspace identifies the active catalog video and track.
 * Return only the logged English clip's overlapping caption intervals.
 * Never interpret token starts/derived ends as exact word evidence. */
export function matchingResearchClipCues(value: unknown, pin: ResearchClipSnapshotV2): ResearchClipCue[] | null {
  if (!object(value) || value.schemaVersion !== 1 || value.catalogState !== "active_verified" ||
      value.projectId !== pin.researchProjectId || value.catalogVideoId !== pin.catalogVideoId ||
      value.youtubeVideoId !== pin.video.youtubeVideoId || !object(value.english)) return null;
  const { track, segments } = value.english;
  const selection = pin.loggedSelection;
  if (!object(track) || track.id !== selection.trackId || track.version !== selection.transcriptVersion ||
      track.videoId !== pin.video.youtubeVideoId || track.kind !== "english" ||
      typeof track.language !== "string" || !/^en(?:-|$)/i.test(track.language) ||
      (track.timingPrecision !== "cue" && track.timingPrecision !== "word") ||
      !Array.isArray(segments) || segments.length > 50_000) return null;
  const cues: ResearchClipCue[] = [];
  const ids = new Set<string>();
  for (const segment of segments as unknown[]) {
    if (!object(segment) || typeof segment.id !== "string" || !UUID.test(segment.id) ||
        ids.has(segment.id) || segment.trackId !== track.id ||
        !Number.isSafeInteger(segment.startMs) || !Number.isSafeInteger(segment.endMs) ||
        (segment.startMs as number) < 0 || (segment.endMs as number) <= (segment.startMs as number) ||
        typeof segment.text !== "string" || !segment.text.trim() || segment.text.length > 20_000) return null;
    ids.add(segment.id);
    const startMs = segment.startMs as number;
    const endMs = segment.endMs as number;
    if (startMs < selection.transcriptEndMs && endMs > selection.transcriptStartMs) {
      cues.push({ startMs, endMs, text: segment.text });
    }
  }
  if (!ids.has(selection.firstSegmentId) || !ids.has(selection.lastSegmentId) ||
      !cues.length || cues.length > 1000) return null;
  return cues.sort((a, b) => a.startMs - b.startMs || a.endMs - b.endMs);
}
