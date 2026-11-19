import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
  applyRowEditV2, applyVisualSequenceEditV2, createRowEditSessionV2,
  projectPrimarySequenceV2, validateScriptDocumentV2,
  type RowEditCommandV2, type VisualSequenceEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import type { createResearchClient } from "@vera/contracts/research-clip-client";
import {
  insertResearchClipBrowserV2, type ResearchClipBrowserInsertV2,
} from "@vera/contracts/research-clip-browser-insert";
import { ProjectAuthError } from "@vera/project-authorization";

export const DEFAULT_AUTHORING_PORT = "38429";

const ASSETS = new Map<string, readonly [string, string]>([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/authoring.css", ["authoring.css", "text/css; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/research-panel.js", ["research-panel.js", "text/javascript; charset=utf-8"]],
  ["/research-search.js", ["research-search.js", "text/javascript; charset=utf-8"]],
  ["/view.js", ["view.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.js", ["rows-editor.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.css", ["rows-editor.css", "text/css; charset=utf-8"]],
  ["/narration-editor.js", ["narration-editor.js", "text/javascript; charset=utf-8"]],
  ["/range-proposal.js", ["range-proposal.js", "text/javascript; charset=utf-8"]],
  ["/narration-editor.css", ["narration-editor.css", "text/css; charset=utf-8"]],
  ["/visual-selection.js", ["visual-selection.js", "text/javascript; charset=utf-8"]],
  ["/visual-only-actions.js", ["visual-only-actions.js", "text/javascript; charset=utf-8"]],
]);
const PROJECT = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(\/document)?$/u;
const RESEARCH = /^\/research\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/projects(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\/clips(?:\/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}))?)?$/iu;
const MUSIC_WARNINGS = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/music-warnings$/u;
const PROOF = /^[0-9a-f]{64}$/u;
const RESEARCH_INSERT = "/research-insert";
// #66 is allowed to change ranges and OC framing, not to create/move/delete
// pictures. Other visual operations belong to separate browser stories.
const AUTHORING_VISUAL_KINDS = new Set<VisualSequenceEditCommandV2["kind"]>([
  "set_visual_range", "swap_ranges", "set_on_camera_framing",
]);

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function id(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 256;
}

function uuid(value: unknown): value is string {
  return typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(value);
}

/** Reject client-supplied Research records, frame bindings and arbitrary row commands. */
function researchInsertRequest(value: unknown): (ResearchClipBrowserInsertV2 & { timelineProjectId: string;
  document: ScriptDocumentV2 }) | null {
  if (!record(value) || !exact(value, ["timelineProjectId", "document", "researchProjectId", "clipId",
    "clipVersion", "expectedDocumentRevision", "placement"]) ||
    !uuid(value.timelineProjectId) || !uuid(value.researchProjectId) || !uuid(value.clipId) ||
    !Number.isSafeInteger(value.clipVersion) || (value.clipVersion as number) < 1 ||
    !Number.isSafeInteger(value.expectedDocumentRevision) || (value.expectedDocumentRevision as number) < 0 ||
    !validateScriptDocumentV2(value.document).valid ||
    (value.document as ScriptDocumentV2).projectId?.toLowerCase() !== value.timelineProjectId.toLowerCase() ||
    !record(value.placement)) return null;
  const placement = value.placement;
  if (placement.kind === "gap") {
    const destination = placement.destination;
    if (!exact(placement, ["kind", "destination"]) || !record(destination) ||
        !exact(destination, ["sectionId", "afterRowId", "beforeRowId"]) ||
        !["sectionId", "afterRowId", "beforeRowId"].every((key) =>
          destination[key] === null || uuid(destination[key]))) return null;
  } else if (placement.kind === "unattached" || placement.kind === "selected_words") {
    if (!exact(placement, placement.kind === "unattached"
      ? ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion"]
      : ["kind", "rowId", "expectedRowVersion", "expectedSequenceVersion", "startTokenId", "endTokenId"]) ||
      !uuid(placement.rowId) || !Number.isSafeInteger(placement.expectedRowVersion) ||
      (placement.expectedRowVersion as number) < 0 ||
      !Number.isSafeInteger(placement.expectedSequenceVersion) ||
      (placement.expectedSequenceVersion as number) < 0 ||
      (placement.kind === "selected_words" && (!uuid(placement.startTokenId) || !uuid(placement.endTokenId)))) return null;
  } else return null;
  return value as unknown as ResearchClipBrowserInsertV2 & {
    timelineProjectId: string; document: ScriptDocumentV2;
  };
}

const VISUAL_KINDS = new Set([
  "add_visual_on_selection", "change_visual_type", "delete_visual",
  "set_visual_range", "set_on_camera_framing", "move_visual_to_row", "attach_visual_to_words",
]);
const WORDLESS_ROW_KINDS = new Set([
  "add_visual_to_wordless_row", "move_wordless_visual", "reorder_visual_only", "set_visual_only_hold",
]);

/** Only the commands this browser editor can issue, with exact JSON shapes. */
function visualCommand(value: unknown): VisualSequenceEditCommandV2 | null {
  if (!record(value) || !VISUAL_KINDS.has(String(value.kind)) || !id(value.blockId) || !id(value.slotId)) return null;
  switch (value.kind) {
    case "move_visual_to_row": {
      const keys = ["kind", "blockId", "slotId", "destinationBlockId"];
      if (Object.hasOwn(value, "expectedDestinationRowVersion")) keys.push("expectedDestinationRowVersion");
      if (!exact(value, keys) || !uuid(value.blockId) || !uuid(value.slotId) ||
          !uuid(value.destinationBlockId) ||
          (Object.hasOwn(value, "expectedDestinationRowVersion") &&
            (!Number.isSafeInteger(value.expectedDestinationRowVersion) ||
              (value.expectedDestinationRowVersion as number) < 0))) return null;
      break;
    }
    case "attach_visual_to_words":
      if (!exact(value, ["kind", "blockId", "slotId", "startTokenId", "endTokenId"]) ||
          !uuid(value.blockId) || !uuid(value.slotId) ||
          !uuid(value.startTokenId) || !uuid(value.endTokenId)) return null;
      break;
    case "add_visual_on_selection":
      if (!exact(value, ["kind", "blockId", "slotId", "payloadId", "startTokenId", "endTokenId", "visualType"]) ||
          !id(value.payloadId) || !id(value.startTokenId) || !id(value.endTokenId) ||
          !["onscreen_placeholder", "need_to_find", "visual_undefined"].includes(String(value.visualType))) return null;
      break;
    case "set_visual_range":
      if (!exact(value, ["kind", "blockId", "slotId", "startTokenId", "endTokenId"]) ||
          !id(value.startTokenId) || !id(value.endTokenId)) return null;
      break;
    case "set_on_camera_framing":
      if (!exact(value, ["kind", "blockId", "slotId", "framing"]) ||
          (value.framing !== "wide" && value.framing !== "tight")) return null;
      break;
    case "delete_visual":
      if (!exact(value, ["kind", "blockId", "slotId"])) return null;
      break;
    case "change_visual_type": {
      if (!exact(value, ["kind", "blockId", "slotId", "to"]) || !record(value.to)) return null;
      const to = value.to;
      if (to.type === "visual_undefined") {
        if (!exact(to, ["type"])) return null;
      } else if (to.type === "onscreen_placeholder" || to.type === "need_to_find") {
        const optional = to.type === "onscreen_placeholder" ? "text" : "description";
        if (!exact(to, Object.hasOwn(to, optional) ? ["type", optional] : ["type"]) ||
            (Object.hasOwn(to, optional) && (typeof to[optional] !== "string" || to[optional].length > 4096))) return null;
      } else return null; // Media-bearing type changes wait for the media-picker issues.
      break;
    }
  }
  return value as VisualSequenceEditCommandV2;
}

/** Strictly bounded Draft wordless operations; the model still owns all state changes/refusals. */
function wordlessRowCommand(value: unknown): RowEditCommandV2 | null {
  if (!record(value) || !WORDLESS_ROW_KINDS.has(String(value.kind))) return null;
  switch (value.kind) {
    case "add_visual_to_wordless_row":
      if (!exact(value, ["kind", "rowId", "payloadId", "slotId", "visualType"]) ||
          !uuid(value.rowId) || !uuid(value.payloadId) || !uuid(value.slotId) ||
          (value.visualType !== "onscreen_placeholder" && value.visualType !== "need_to_find")) return null;
      break;
    case "move_wordless_visual": {
      const keys = ["kind", "sourceRowId", "payloadId", "destinationRowId"];
      for (const optional of ["destinationSlotId", "replacementPayloadId", "expectedDestinationSequenceVersion"]) {
        if (Object.hasOwn(value, optional)) keys.push(optional);
      }
      if (!exact(value, keys) || !uuid(value.sourceRowId) || !uuid(value.payloadId) ||
          !uuid(value.destinationRowId) ||
          (Object.hasOwn(value, "destinationSlotId") && !uuid(value.destinationSlotId)) ||
          (Object.hasOwn(value, "replacementPayloadId") && !uuid(value.replacementPayloadId)) ||
          (Object.hasOwn(value, "expectedDestinationSequenceVersion") &&
            (!Number.isSafeInteger(value.expectedDestinationSequenceVersion) ||
              (value.expectedDestinationSequenceVersion as number) < 0))) return null;
      break;
    }
    case "reorder_visual_only":
      if (!exact(value, ["kind", "rowId", "payloadIds"]) || !uuid(value.rowId) ||
          !Array.isArray(value.payloadIds) || !value.payloadIds.every(uuid)) return null;
      break;
    case "set_visual_only_hold":
      if (!exact(value, ["kind", "rowId", "payloadId", "holdSeconds"]) ||
          !uuid(value.rowId) || !uuid(value.payloadId) ||
          typeof value.holdSeconds !== "number" || !Number.isFinite(value.holdSeconds)) return null;
      break;
  }
  return value as RowEditCommandV2;
}

function matchesProof(value: string | null | undefined, expected: Buffer): boolean {
  return !!value && PROOF.test(value) && timingSafeEqual(Buffer.from(value, "hex"), expected);
}

/** No quote mutation, request transport or bearer crosses this browser-facing seam. */
export type AuthoringReadOnlyResearchCatalog = Pick<ReturnType<typeof createResearchClient>,
  "projects" | "clips" | "clip">;

export interface AuthoringResearchAccess {
  catalog: AuthoringReadOnlyResearchCatalog;
  /** A Research read needs view permission; a script insertion needs edit permission. */
  authorizeTimelineProject(projectId: string, action?: "view_document" | "edit_document"): Promise<void>;
}

const RESEARCH_HEADERS = {
  "Cache-Control": "no-store", "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
};

function researchResponse(status: number, body: unknown): Response {
  return Response.json(body, { status, headers: RESEARCH_HEADERS });
}

/** Project-scoped transcript DTO only: upstream extras never reach the browser. */
function publicResearchClip(candidate: Awaited<ReturnType<AuthoringReadOnlyResearchCatalog["clip"]>>) {
  const { id, projectId, catalogVideoId, version, createdBy, createdAt, updatedAt,
    englishText, originalText } = candidate;
  const { youtubeVideoId, canonicalUrl, title, channel, sourceLanguage } = candidate.video;
  const { trackId, transcriptVersion, firstSegmentId, lastSegmentId, firstTokenId, lastTokenId,
    transcriptStartMs, transcriptEndMs, exportStartMs, exportEndMs, text, timingPrecision } = candidate.selection;
  return {
    id, projectId, catalogVideoId, version,
    ...(createdBy === undefined ? {} : { createdBy }),
    ...(createdAt === undefined ? {} : { createdAt }),
    ...(updatedAt === undefined ? {} : { updatedAt }),
    video: { youtubeVideoId, canonicalUrl, title,
      ...(channel === undefined ? {} : { channel }),
      ...(sourceLanguage === undefined ? {} : { sourceLanguage }) },
    selection: { trackId, transcriptVersion, firstSegmentId, lastSegmentId,
      ...(firstTokenId === undefined ? {} : { firstTokenId }),
      ...(lastTokenId === undefined ? {} : { lastTokenId }),
      transcriptStartMs, transcriptEndMs, exportStartMs, exportEndMs, text, timingPrecision },
    englishText, ...(originalText === undefined ? {} : { originalText }),
  };
}

/** Same-origin access to only the single-writer project/document routes. */
export function createAuthoringHandler(
  origin: string,
  authorization: string,
  projects: (request: Request) => Promise<Response>,
  research?: AuthoringResearchAccess,
) {
  const launchProof = randomBytes(32);
  // Keep the enrolled browser working after host restart. Tie it to the
  // configured identity and port without giving the browser the API token.
  const browserProof = createHmac("sha256", authorization).update(`vera-authoring:${origin}`).digest();
  // D124 is session history, not a property of the submitted document. Keep
  // exactly one server-owned split and require its opaque proof and *whole*
  // resulting document before using the model's exact restoration path.
  let lastSplit: {
    proof: string;
    rowId: string;
    newRowId: string;
    documentJson: string;
    session: ReturnType<typeof createRowEditSessionV2>;
  } | null = null;
  const handle = async (request: Request): Promise<Response | undefined> => {
    const url = new URL(request.url);
    const asset = request.method === "GET" ? ASSETS.get(url.pathname) : undefined;
    if (asset) {
      const [file, mime] = asset;
      const contents = await readFile(new URL(`../browser/${file}`, import.meta.url), "utf8");
      return new Response(contents, { headers: {
        "Content-Type": mime,
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; " +
          "connect-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; " +
          "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Referrer-Policy": "no-referrer",
      } });
    }
    if (!url.pathname.startsWith("/authoring/")) return undefined;
    const path = url.pathname.slice("/authoring".length);
    const route = PROJECT.exec(path);
    const researchRoute = RESEARCH.exec(path);
    const musicWarnings = MUSIC_WARNINGS.test(path);
    const startsSession = path === "/session" && request.method === "POST";
    const isCommand = path === "/command" && request.method === "POST";
    const isVisualCommand = path === "/visual-command" && request.method === "POST";
    const isVisualPreview = path === "/visual-preview" && request.method === "POST";
    const isProjection = path === "/projection" && request.method === "POST";
    const isResearchInsert = path === RESEARCH_INSERT && request.method === "POST";
    const allowed = path === "/projects" ? request.method === "POST" :
      (route && (request.method === "GET" || request.method === (route[1] ? "PUT" : "PATCH"))) ||
      (musicWarnings && request.method === "GET") ||
      (researchRoute && request.method === "GET" && request.body === null);
    if ((!allowed && !startsSession && !isCommand && !isVisualCommand && !isVisualPreview && !isProjection && !isResearchInsert) || url.search) {
      return Response.json({ error: "not_found" }, { status: 404 });
    }

    // Cross-origin browser code cannot set this header without a successful
    // CORS preflight. Fetch Metadata also excludes other sites and local ports.
    const suppliedOrigin = request.headers.get("origin");
    if (request.headers.get("sec-fetch-site") !== "same-origin" ||
        request.headers.get("x-vera-authoring") !== "1" ||
        (suppliedOrigin !== null && suppliedOrigin !== origin)) {
      return Response.json({ error: "same_origin_required" }, { status: 403 });
    }
    if (startsSession && matchesProof(request.headers.get("x-vera-launch"), launchProof)) {
      return Response.json({ sessionProof: browserProof.toString("hex") });
    }
    if (startsSession || !matchesProof(request.headers.get("x-vera-session"), browserProof)) {
      return Response.json({ error: "authoring_browser_required" }, { status: 401 });
    }
    if (researchRoute) {
      if (!research) return researchResponse(503, { error: "research_unavailable" });
      const timelineProjectId = researchRoute[1]!;
      const researchProjectId = researchRoute[2];
      const clipId = researchRoute[3];
      // The browser session proves only that this is the local editor. It never
      // substitutes for a fresh Timeline membership/permission check.
      try {
        await research.authorizeTimelineProject(timelineProjectId);
      } catch (error) {
        if (error instanceof ProjectAuthError) {
          return researchResponse(error.status, { error: error.code });
        }
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      try {
        // Independently recheck Research visibility on EVERY catalog/clip read;
        // neither a UUID supplied by the browser nor a previous list is proof.
        const visible = await research.catalog.projects();
        if (!researchProjectId) {
          return researchResponse(200, { projects: visible.map(({ id, name }) => ({ id, name })) });
        }
        if (!visible.some(({ id }) => id.toLowerCase() === researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        if (clipId) {
          return researchResponse(200, { clip: publicResearchClip(
            await research.catalog.clip(researchProjectId, clipId),
          ) });
        }
        return researchResponse(200, { clips: (await research.catalog.clips(researchProjectId))
          .map(publicResearchClip) });
      } catch {
        // Research's errors and headers can contain user data or credentials.
        return researchResponse(503, { error: "research_unavailable" });
      }
    }
    if (isResearchInsert) {
      let body: ReturnType<typeof researchInsertRequest>;
      try { body = researchInsertRequest(await request.json()); } catch { body = null; }
      if (!body) return researchResponse(400, { error: "invalid_research_insert" });
      if (!research) return researchResponse(503, { error: "research_unavailable" });
      try {
        await research.authorizeTimelineProject(body.timelineProjectId, "edit_document");
      } catch (error) {
        if (error instanceof ProjectAuthError) return researchResponse(error.status, { error: error.code });
        return researchResponse(503, { error: "timeline_authorization_unavailable" });
      }
      let candidate: Awaited<ReturnType<AuthoringReadOnlyResearchCatalog["clip"]>>;
      try {
        // A previous GET/list is never sufficient authorization to mutate a script.
        const projects = await research.catalog.projects();
        if (!projects.some(({ id }) => id.toLowerCase() === body.researchProjectId.toLowerCase())) {
          return researchResponse(403, { error: "research_project_forbidden" });
        }
        candidate = await research.catalog.clip(body.researchProjectId, body.clipId);
      } catch {
        return researchResponse(503, { error: "research_unavailable" });
      }
      const result = insertResearchClipBrowserV2(body.document, candidate, body);
      if (result.ok) lastSplit = null;
      return researchResponse(200, result);
    }
    if (isProjection) {
      try {
        const body: unknown = await request.json();
        if (!record(body) || !exact(body, ["document"]) ||
            !validateScriptDocumentV2(body.document).valid) {
          return Response.json({ error: "invalid_projection" }, { status: 400 });
        }
        // Read-only: a projection cannot create, redeem or invalidate D124 split context.
        return Response.json({ projection: projectPrimarySequenceV2(body.document) });
      } catch {
        return Response.json({ error: "invalid_projection" }, { status: 400 });
      }
    }
    if (isCommand) {
      try {
        const body = await request.json() as { document: ScriptDocumentV2; command: RowEditCommandV2;
          splitProof?: string; expectedSequenceVersion?: unknown; expectedRowEditRevision?: unknown };
        const { command, document, splitProof } = body;
        if (record(command) && VISUAL_KINDS.has(String(command.kind))) {
          const visual = visualCommand(command);
          if (!visual || !record(body) || !exact(body, ["document", "command", "expectedSequenceVersion"]) ||
              !Number.isSafeInteger(body.expectedSequenceVersion) ||
              (body.expectedSequenceVersion as number) < 0 ||
              !validateScriptDocumentV2(document).valid) {
            return Response.json({ error: "invalid_command" }, { status: 400 });
          }
          const result = applyVisualSequenceEditV2(document, body.expectedSequenceVersion as number, visual);
          if (result.ok) lastSplit = null; // Any successful visual edit breaks immediate split restoration.
          return Response.json(result);
        }
        if (record(command) && WORDLESS_ROW_KINDS.has(String(command.kind))) {
          const rowCommand = wordlessRowCommand(command);
          if (!rowCommand || !record(body) || !exact(body, ["document", "command", "expectedRowEditRevision"]) ||
              !Number.isSafeInteger(body.expectedRowEditRevision) || (body.expectedRowEditRevision as number) < 0 ||
              !validateScriptDocumentV2(document).valid) {
            return Response.json({ error: "invalid_command" }, { status: 400 });
          }
          const result = applyRowEditV2(document, body.expectedRowEditRevision as number, rowCommand);
          if (result.ok) lastSplit = null;
          return Response.json(result);
        }
        if (!record(command) || typeof command.kind !== "string" ||
            Object.hasOwn(body, "expectedSequenceVersion") || Object.hasOwn(body, "expectedRowEditRevision")) {
          return Response.json({ error: "invalid_command" }, { status: 400 });
        }
        if (splitProof !== undefined) {
          const validProof = typeof splitProof === "string" && PROOF.test(splitProof) && lastSplit &&
            timingSafeEqual(Buffer.from(splitProof, "hex"), Buffer.from(lastSplit.proof, "hex"));
          const validJoin = command?.kind === "join_rows" && command.direction === "previous" &&
            command.rowId === lastSplit?.newRowId && command.words === null;
          const validDocument = lastSplit && JSON.stringify(document) === lastSplit.documentJson &&
            document.rowEditRevision === lastSplit.session.revision;
          if (!validProof || !validJoin || !validDocument) {
            return Response.json({ ok: false, document, diagnostics: [{
              code: "ROW_SPLIT_CONTEXT_STALE", jsonPath: "/activeDraft",
              message: "The immediate split restoration is no longer available.",
            }] });
          }
          const session = lastSplit!.session;
          lastSplit = null;
          return Response.json(session.apply(command));
        }
        if (command?.kind === "split_row") {
          const session = createRowEditSessionV2(document);
          const result = session.apply(command);
          if (!result.ok) return Response.json(result);
          const proof = randomBytes(32).toString("hex");
          lastSplit = {
            proof, rowId: command.rowId, newRowId: command.newRowId,
            documentJson: JSON.stringify(result.document), session,
          };
          return Response.json({ ...result, splitProof: proof });
        }
        const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
        if (result.ok) lastSplit = null;
        return Response.json(result);
      } catch {
        return Response.json({ error: "invalid_command" }, { status: 400 });
      }
    }
    if (isVisualCommand || isVisualPreview) {
      try {
        const body = await request.json() as {
          document?: ScriptDocumentV2;
          command?: VisualSequenceEditCommandV2;
          expectedSequenceVersion?: number;
        };
        const { document, command, expectedSequenceVersion } = body;
        if (!record(body) || !exact(body, ["document", "command", "expectedSequenceVersion"]) ||
            !document || !validateScriptDocumentV2(document).valid || !record(command) ||
            !AUTHORING_VISUAL_KINDS.has(command.kind) ||
            !Number.isSafeInteger(expectedSequenceVersion) || expectedSequenceVersion! < 0) {
          return Response.json({ error: "invalid_visual_command" }, { status: 400 });
        }
        const result = applyVisualSequenceEditV2(document, expectedSequenceVersion!, command);
        // Read-only Reselect previews must not consume the one-time proof for
        // immediately restoring a split. Only a committed edit breaks it.
        if (result.ok && isVisualCommand) lastSplit = null;
        return Response.json(result.ok ? { ...result, projection: projectPrimarySequenceV2(result.document) } : result);
      } catch {
        return Response.json({ error: "invalid_visual_command" }, { status: 400 });
      }
    }
    const headers = new Headers({ authorization });
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    return await projects(new Request(`${origin}/v1${path}`, {
      method: request.method,
      headers,
      body: request.body ? await request.arrayBuffer() : null,
    }));
  };
  return { launchCode: launchProof.toString("hex"), handle };
}
