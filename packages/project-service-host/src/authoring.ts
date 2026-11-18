import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import { applyRowEditV2, type RowEditCommandV2 } from "@vera/contracts/authoring-v2";
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
]);
const PROJECT = /^\/projects\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(\/document)?$/u;
const PROOF = /^[0-9a-f]{64}$/u;

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
    const allowed = path === "/projects" ? request.method === "POST" :
      route && (request.method === "GET" || request.method === (route[1] ? "PUT" : "PATCH"));
    if ((!allowed && !startsSession && !isCommand) || url.search) return Response.json({ error: "not_found" }, { status: 404 });

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
        const body = await request.json() as { document: ScriptDocumentV2; command: RowEditCommandV2 };
        return Response.json(applyRowEditV2(body.document, body.document.rowEditRevision ?? 0, body.command));
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
