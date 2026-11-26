import { timingSafeEqual } from "node:crypto";
import { ProjectAuthError, type ProjectAuthorizationService, type SuiteIdentityPort } from "@vera/project-authorization";
import { createAuthoringHandler } from "./authoring.js";

/** Host-owned trusted login integration. Never construct this from browser JSON/headers.
 * The bearer is independently verified by SuiteIdentityPort on every request.
 * Session IDs and CSRF tokens must be random, server-owned and rotated on login.
 * Cookie adapters must use HttpOnly, SameSite cookies (Secure on HTTPS).
 */
export interface BrowserAccountPort {
  session(request: Request): Promise<{
    sessionId: string; authorization: string; csrfToken: string;
  } | null>;
  signIn(request: Request): Promise<Response>;
  signOut(request: Request): Promise<Response>;
}
export interface AccountMode {
  identity: SuiteIdentityPort;
  sessions?: BrowserAccountPort;
}
function reply(status: number, body: unknown): Response {
  return Response.json(body, { status, headers: {
    "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
  } });
}
function matches(a: string | null, b: string): boolean {
  return a !== null && Buffer.byteLength(a) === Buffer.byteLength(b) &&
    timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

/** Separate opt-in boundary; never enrolls a browser into the shared local identity. */
export function createAccountAuthoringHandler(
  origin: string, mode: AccountMode, auth: ProjectAuthorizationService,
  projects: (request: Request) => Promise<Response>,
) {
  const handlers = new Map<string, { authorization: string; handler: ReturnType<typeof createAuthoringHandler> }>();
  const assets = createAuthoringHandler(origin, "unused-account-assets", projects);
  return async (request: Request): Promise<Response | undefined> => {
    const url = new URL(request.url);
    const account = url.pathname === "/authoring/account";
    const signIn = url.pathname === "/authoring/account/sign-in";
    const signOut = url.pathname === "/authoring/account/sign-out";
    if (!url.pathname.startsWith("/authoring/")) return await assets.handle(request);
    if (url.origin !== origin || url.search || request.headers.get("sec-fetch-site") !== "same-origin" ||
        request.headers.get("x-vera-authoring") !== "1" ||
        (request.headers.get("origin") !== null && request.headers.get("origin") !== origin) ||
        (request.method !== "GET" && request.headers.get("origin") !== origin)) {
      return reply(403, { error: "same_origin_required" });
    }
    if ((account && request.method !== "GET") || ((signIn || signOut) && request.method !== "POST")) {
      return reply(404, { error: "not_found" });
    }
    if (!mode.sessions) return reply(503, { mode: "account", error: "account_provider_unavailable" });
    try {
      // Sign-in is unauthenticated but still requires exact origin and a custom header.
      if (signIn) return await mode.sessions.signIn(request);
      const session = await mode.sessions.session(request);
      if (!session) return reply(401, { mode: "account", error: "authentication_required" });
      if (!session.sessionId || !/^Bearer \S+$/u.test(session.authorization) ||
          !/^[a-zA-Z0-9_-]{32,256}$/u.test(session.csrfToken)) {
        return reply(503, { error: "account_provider_unavailable" });
      }
      const principal = await auth.authenticateRequest(new Request(origin, {
        headers: { authorization: session.authorization },
      }), mode.identity);
      if (account) return reply(200, { mode: "account", actorId: principal.principalId, csrfToken: session.csrfToken });
      if (!matches(request.headers.get("x-vera-csrf"), session.csrfToken)) {
        return reply(403, { error: "csrf_required" });
      }
      if (signOut) {
        handlers.delete(session.sessionId);
        return await mode.sessions.signOut(request);
      }
      let cached = handlers.get(session.sessionId);
      if (!cached || cached.authorization !== session.authorization) {
        // Bound transient per-session editor state; an eviction only loses Undo/split proof.
        if (handlers.size >= 1000) handlers.delete(handlers.keys().next().value!);
        cached = { authorization: session.authorization,
          handler: createAuthoringHandler(origin, session.authorization, projects, undefined, true) };
        handlers.set(session.sessionId, cached);
      }
      return await cached.handler.handle(request);
    } catch (error) {
      if (error instanceof ProjectAuthError) return reply(error.status, { error: error.code });
      return reply(503, { error: "account_provider_unavailable" });
    }
  };
}
