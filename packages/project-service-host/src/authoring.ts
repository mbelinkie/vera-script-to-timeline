import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
  applyRowEditV2, applyVisualSequenceEditV2, createRowEditSessionV2,
  projectPrimarySequenceV2, validateScriptDocumentV2,
  type RowEditCommandV2, type VisualSequenceEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";

export const DEFAULT_AUTHORING_PORT = "38429";

const ASSETS = new Map<string, readonly [string, string]>([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/authoring.css", ["authoring.css", "text/css; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/view.js", ["view.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.js", ["rows-editor.js", "text/javascript; charset=utf-8"]],
  ["/rows-editor.css", ["rows-editor.css", "text/css; charset=utf-8"]],
  ["/narration-editor.js", ["narration-editor.js", "text/javascript; charset=utf-8"]],
  ["/narration-editor.css", ["narration-editor.css", "text/css; charset=utf-8"]],
  ["/visual-selection.js", ["visual-selection.js", "text/javascript; charset=utf-8"]],
]);
const PROJECT = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(\/document)?$/u;
const MUSIC_WARNINGS = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/music-warnings$/u;
const PROOF = /^[0-9a-f]{64}$/u;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function id(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 256;
}

const VISUAL_KINDS = new Set([
  "add_visual_on_selection", "change_visual_type", "delete_visual",
  "set_visual_range", "set_on_camera_framing",
]);

/** Only the commands this browser editor can issue, with exact JSON shapes. */
function visualCommand(value: unknown): VisualSequenceEditCommandV2 | null {
  if (!record(value) || !VISUAL_KINDS.has(String(value.kind)) || !id(value.blockId) || !id(value.slotId)) return null;
  switch (value.kind) {
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

function matchesProof(value: string | null | undefined, expected: Buffer): boolean {
  return !!value && PROOF.test(value) && timingSafeEqual(Buffer.from(value, "hex"), expected);
}

/** Same-origin access to only the single-writer project/document routes. */
export function createAuthoringHandler(
  origin: string,
  authorization: string,
  projects: (request: Request) => Promise<Response>,
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
    const musicWarnings = MUSIC_WARNINGS.test(path);
    const startsSession = path === "/session" && request.method === "POST";
    const isCommand = path === "/command" && request.method === "POST";
    const isProjection = path === "/projection" && request.method === "POST";
    const allowed = path === "/projects" ? request.method === "POST" :
      (route && (request.method === "GET" || request.method === (route[1] ? "PUT" : "PATCH"))) ||
      (musicWarnings && request.method === "GET");
    if ((!allowed && !startsSession && !isCommand && !isProjection) || url.search) return Response.json({ error: "not_found" }, { status: 404 });

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
        const body = await request.json() as { document: ScriptDocumentV2; command: RowEditCommandV2; splitProof?: string; expectedSequenceVersion?: unknown };
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
        if (!record(command) || typeof command.kind !== "string" ||
            Object.hasOwn(body, "expectedSequenceVersion")) {
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
