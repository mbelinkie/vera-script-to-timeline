import {
  ProjectAuthError,
  type ProjectAuthorizationService,
  type SuiteIdentityPort,
} from "@vera/project-authorization";

import {
  AgentAuthenticationError,
  type ProjectAgentAuthenticationService,
} from "./agent-auth.js";
import { PairingError, type ProjectAgentPairingService } from "./pairing.js";

export const MAX_PAIRING_API_BODY_BYTES = 4 * 1024;
const HEADERS = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
};

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: HEADERS });
}

function failed(error: unknown): Response {
  if (error instanceof ProjectAuthError || error instanceof PairingError ||
      error instanceof AgentAuthenticationError) {
    return response(error.status, { error: error.code });
  }
  // Never echo token/body, SQL errors or private filesystem paths.
  return response(503, { error: "service_unavailable" });
}

function invalid(): never {
  throw new PairingError("invalid_pairing_request", 400);
}

function exactFields(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return invalid();
  const record = value as Record<string, unknown>;
  if (Object.keys(record).length !== keys.length ||
      keys.some((key) => !Object.hasOwn(record, key))) return invalid();
  return record;
}

async function readBody(request: Request): Promise<unknown> {
  if (!/^application\/json(?:\s*;|\s*$)/iu.test(request.headers.get("content-type") ?? "")) {
    return invalid();
  }
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/u.test(length) || Number(length) > MAX_PAIRING_API_BODY_BYTES)) {
    return invalid();
  }
  const reader = request.body?.getReader();
  if (!reader) return invalid();
  let size = 0;
  const chunks: Uint8Array[] = [];
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_PAIRING_API_BODY_BYTES) {
        await reader.cancel().catch(() => undefined);
        return invalid();
      }
      chunks.push(next.value);
    }
  } catch {
    return invalid();
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown;
  } catch {
    return invalid();
  }
}

function machineCredential(request: Request, projectId: string) {
  const match = /^Bearer (sttag_[A-Za-z0-9_-]{43})$/u.exec(request.headers.get("authorization") ?? "");
  const version = request.headers.get("x-agent-credential-version") ?? "";
  return {
    projectId,
    agentToken: match?.[1],
    credentialVersion: /^[1-9]\d{0,14}$/u.test(version) ? Number(version) : undefined,
  };
}

export interface PairingApiDependencies {
  /** Trusted suite identity adapter; never derive a user from client role headers. */
  readonly identity?: SuiteIdentityPort;
  readonly authorization: ProjectAuthorizationService;
  readonly pairing: ProjectAgentPairingService;
  readonly agents: ProjectAgentAuthenticationService;
}

/** Unmounted private /v1 handler. Phase 4's QA host enforces loopback/Host/body transport. */
export function createProjectBuildPairingApiHandler(deps: PairingApiDependencies):
  (request: Request) => Promise<Response> {
  return async (request: Request) => {
    try {
      const url = new URL(request.url);
      if (url.search) return invalid();
      const path = url.pathname;
      if (path === "/v1/agent-pairing/consume" && request.method === "POST") {
        const fields = exactFields(await readBody(request),
          ["projectId", "offerToken", "protocolVersion", "capabilities"]);
        return response(201, await deps.pairing.consumeOffer({
          projectId: fields.projectId, offerToken: fields.offerToken,
          protocolVersion: fields.protocolVersion, capabilities: fields.capabilities,
        }));
      }

      const agent = /^\/v1\/agent\/projects\/([^/]+)\/(jobs|heartbeat)$/u.exec(path);
      if (agent && (request.method === "GET" || request.method === "POST")) {
        if (agent[2] === "jobs" && request.method === "GET") {
          return response(200, { jobs: await deps.agents.pollAssignedJobs(machineCredential(request, agent[1]!)) });
        }
        if (agent[2] === "heartbeat" && request.method === "POST" && request.body === null) {
          return response(200, await deps.agents.heartbeat(machineCredential(request, agent[1]!)));
        }
        return response(404, { error: "not_found" });
      }

      const pairingOffer = /^\/v1\/projects\/([^/]+)\/agent-pairing-offers$/u.exec(path);
      const pairingOfferRevoke = /^\/v1\/projects\/([^/]+)\/agent-pairing-offers\/([^/]+)$/u.exec(path);
      const readiness = /^\/v1\/projects\/([^/]+)\/agent-readiness$/u.exec(path);
      const agentManage = /^\/v1\/projects\/([^/]+)\/agents\/([^/]+)(\/rotate)?$/u.exec(path);
      if (!pairingOffer && !pairingOfferRevoke && !readiness && !agentManage) {
        return response(404, { error: "not_found" });
      }
      if (!deps.identity) throw new ProjectAuthError("authentication_required", 401);
      // User authentication runs before parsing even malformed or oversized JSON.
      const principal = await deps.authorization.authenticateRequest(request, deps.identity);
      if (pairingOffer && request.method === "POST") {
        const fields = exactFields(await readBody(request), ["agentLabel", "protocolVersion"]);
        return response(201, await deps.pairing.createOffer(pairingOffer[1]!, principal, {
          agentLabel: fields.agentLabel,
          protocolVersion: fields.protocolVersion,
        }));
      }
      if (pairingOfferRevoke && request.method === "DELETE" && request.body === null) {
        await deps.pairing.revokeOffer(pairingOfferRevoke[1]!, principal, pairingOfferRevoke[2]!);
        return response(200, { revoked: true });
      }
      if (readiness && request.method === "GET") {
        return response(200, await deps.pairing.readiness(readiness[1]!, principal));
      }
      if (agentManage && request.body === null) {
        if (agentManage[3] === "/rotate" && request.method === "POST") {
          return response(200, await deps.pairing.rotateAgent(agentManage[1]!, principal, agentManage[2]!));
        }
        if (!agentManage[3] && request.method === "DELETE") {
          await deps.pairing.revokeAgent(agentManage[1]!, principal, agentManage[2]!);
          return response(200, { revoked: true });
        }
      }
      return response(404, { error: "not_found" });
    } catch (error) {
      return failed(error);
    }
  };
}
