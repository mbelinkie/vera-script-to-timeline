import type { MlaSource } from "./mla-citation.js";
import type { ResearchQuoteCitationDetails } from "./research-quote-citations.js";

export type ResearchLibrarySource = MlaSource & { id: string; projectId: string };

export interface ResearchLibraryItem {
  sourceId: string;
  version: number;
  content: ResearchQuoteCitationDetails & Record<string, unknown>;
}

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
const kinds = new Set(["youtube", "web_page", "pdf", "offline", "image", "audio", "local_video", "provider_video"]);

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function matchesId(value: unknown, expected: string): boolean {
  return typeof value === "string" && value.toLowerCase() === expected.toLowerCase();
}

function validOptionalText(value: unknown): boolean {
  return value === undefined || typeof value === "string" && !/[\0\p{Surrogate}]/u.test(value);
}

export function readResearchLibraryItem(
  value: unknown, projectId: string, itemId: string, kind: "quote" | "clip",
): ResearchLibraryItem {
  if (!record(value) || !matchesId(value.projectId, projectId) || !matchesId(value.id, itemId) ||
      value.kind !== kind || typeof value.sourceId !== "string" || !uuid.test(value.sourceId) ||
      typeof value.version !== "number" || !Number.isSafeInteger(value.version) || value.version < 1 ||
      !record(value.content) || kind === "quote" && (
        typeof value.content.text !== "string" || !validOptionalText(value.content.location) ||
        !validOptionalText(value.content.citationOverride)
      )) {
    throw new Error("Research returned an invalid or different Library item.");
  }
  return { sourceId: value.sourceId.toLowerCase(), version: value.version, content: value.content };
}

export function readResearchLibrarySource(value: unknown, projectId: string, sourceId: string): ResearchLibrarySource {
  if (!record(value) || !matchesId(value.projectId, projectId) || !matchesId(value.id, sourceId) ||
      typeof value.kind !== "string" || !kinds.has(value.kind) || !record(value.bibliography) ||
      !record(value.details) || (
        value.sourceIdentity !== undefined && (!record(value.sourceIdentity) ||
          !validOptionalText(value.sourceIdentity.provider) || !validOptionalText(value.sourceIdentity.canonicalUrl))
      )) {
    throw new Error("Research returned an invalid or different Library source.");
  }
  for (const key of ["subtype", "channel", "accessedDate", "submittedUrl"] as const) {
    if (!validOptionalText(value.details[key])) throw new Error("Research returned invalid source details.");
  }
  for (const key of ["title", "authors", "publication", "publisher", "date", "url", "credit"] as const) {
    const field = value.bibliography[key];
    if (field === undefined) continue;
    if (!record(field) || (key === "authors"
      ? !Array.isArray(field.value) || !field.value.every((author) => typeof author === "string" && validOptionalText(author))
      : typeof field.value !== "string" || !validOptionalText(field.value))) {
      throw new Error("Research returned invalid bibliography fields.");
    }
  }
  return { ...value, id: sourceId.toLowerCase(), projectId: projectId.toLowerCase() } as ResearchLibrarySource;
}
