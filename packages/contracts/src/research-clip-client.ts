/**
 * Development-only bridge to the local Research API.
 * The bearer is deliberately confined to loopback HTTP requests and is never
 * included in errors or returned values.
 */
import { createHash } from "node:crypto";
import {
  snapshotResearchCandidateV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";
import { readResearchLibraryItem, readResearchLibrarySource, type ResearchLibraryItemKind } from "./research-library-records.js";
import { describeResearchQuote, readResearchQuote, type ResearchQuoteRecord } from "./research-quote-records.js";
import { readKeptStillManifest, readStillItem, UnsupportedKeptStillError, type ResearchStillChoice } from "./research-still-records.js";

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

export class ResearchReadError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

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

  async function send(path: string, accept: string, update?: { expectedVersion: number; content: object }): Promise<Response> {
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
      throw new Error(update ? "Research could not confirm the quote edit. Reload the quote to check its current citation."
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
      throw new Error("Research quote changed before the edit was saved. Reload the quote and retry.");
    }
    if (!response.ok) {
      throw new Error(update ? "Research could not confirm the quote edit. Reload the quote to check its current citation."
        : "Research could not complete this read-only request.");
    }
    return response;
  }

  async function requestJson(path: string, update?: { expectedVersion: number; content: object }): Promise<unknown> {
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

  async function source(projectId: string, sourceId: string) {
    return readResearchLibrarySource(
      await get(libraryPath(projectId, "sources", sourceId)), projectId, sourceId,
    );
  }

  return {
    item,
    source,

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
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Research returned an empty thumbnail.");
      const bytes = new Uint8Array(thumbnail.byteCount);
      let offset = 0;
      try {
        const length = response.headers.get("content-length");
        if (response.status !== 200 || response.headers.get("content-type") !== thumbnail.mimeType ||
            (length !== null && length !== String(thumbnail.byteCount))) throw new Error("Invalid Research thumbnail headers.");
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          if (offset + value.length > bytes.length) throw new Error("Research thumbnail exceeds its kept size.");
          bytes.set(value, offset);
          offset += value.length;
        }
      } finally {
        await reader.cancel().catch(() => undefined);
      }
      if (offset !== bytes.length || createHash("sha256").update(bytes).digest("hex") !== thumbnail.sha256) {
        throw new Error("Research thumbnail does not match the kept copy.");
      }
      return { bytes, mimeType: thumbnail.mimeType };
    },
  };
}

function libraryPath(projectId: string, kind: "items" | "sources" | "stills", recordId: string): string {
  if (!UUID.test(projectId) || !UUID.test(recordId)) {
    throw new Error("Research project and record IDs must be UUIDs.");
  }
  return `/api/projects/${projectId}/${kind}/${recordId}`;
}
