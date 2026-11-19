import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
  applyRowEditV2, applyVisualSequenceEditV2, createRowEditSessionV2, projectPrimarySequenceV2,
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
  ["/range-proposal.js", ["range-proposal.js", "text/javascript; charset=utf-8"]],
  ["/narration-editor.css", ["narration-editor.css", "text/css; charset=utf-8"]],
]);
const PROJECT = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(\/document)?$/u;
const PROOF = /^[0-9a-f]{64}$/u;
// #66 is allowed to change ranges and OC framing, not to create/move/delete
// pictures. Other visual operations belong to separate browser stories.
const AUTHORING_VISUAL_KINDS = new Set<VisualSequenceEditCommandV2["kind"]>([
  "set_visual_range", "swap_ranges", "set_on_camera_framing",
]);

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
    const startsSession = path === "/session" && request.method === "POST";
    const isCommand = path === "/command" && request.method === "POST";
    const isVisualCommand = path === "/visual-command" && request.method === "POST";
    const isVisualPreview = path === "/visual-preview" && request.method === "POST";
    const isProjection = path === "/projection" && request.method === "POST";
    const allowed = path === "/projects" ? request.method === "POST" :
      route && (request.method === "GET" || request.method === (route[1] ? "PUT" : "PATCH"));
    if ((!allowed && !startsSession && !isCommand && !isVisualCommand && !isVisualPreview && !isProjection) || url.search) {
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
    if (isCommand) {
      try {
        const body = await request.json() as { document: ScriptDocumentV2; command: RowEditCommandV2; splitProof?: string };
        const { command, document, splitProof } = body;
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
        if (!document || !command || !AUTHORING_VISUAL_KINDS.has(command.kind) ||
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
    if (isProjection) {
      try {
        const body = await request.json() as { document?: ScriptDocumentV2 };
        if (!body?.document || typeof body.document !== "object" || Array.isArray(body.document)) {
          return Response.json({ error: "invalid_projection_request" }, { status: 400 });
        }
        // A projection reads only the supplied snapshot, never another user's
        // project or a server-side document store.
        return Response.json({ projection: projectPrimarySequenceV2(body.document) });
      } catch {
        return Response.json({ error: "invalid_projection_request" }, { status: 400 });
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
