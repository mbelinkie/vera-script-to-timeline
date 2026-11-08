import {
  ProjectAuthError, type ProjectAuthorizationService, type SuiteIdentityPort,
} from "@vera/project-authorization";

import { AgentAuthenticationError, type AgentCredentialInput } from "./agent-auth.js";
import { BuildInputRefusal } from "./model.js";
import { BuildServiceError, type ProjectBuildSubmissionService } from "./submission.js";
import { type ProjectBuildStatusService, type StageProgress } from "./status.js";

const HEADERS = { "Cache-Control": "no-store", "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff" };
const MAX_BODY = 64 * 1024;

function reply(status: number, value: unknown): Response {
  return new Response(JSON.stringify(value), { status, headers: HEADERS });
}
function invalid(): never { throw new BuildServiceError("invalid_build_request", 400); }
function object(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  const obj = value as Record<string, unknown>;
  if (Object.keys(obj).length !== keys.length || keys.some((key) => !Object.hasOwn(obj, key))) {
    return invalid();
  }
  return obj;
}
async function body(request: Request): Promise<unknown> {
  if (!/^application\/json(?:\s*;|\s*$)/iu.test(request.headers.get("content-type") ?? "")) return invalid();
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/u.test(length) || Number(length) > MAX_BODY)) return invalid();
  if (!request.body) return invalid();
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.length;
      if (size > MAX_BODY) { await reader.cancel().catch(() => undefined); return invalid(); }
      chunks.push(item.value);
    }
  } catch { return invalid(); }
  finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown; }
  catch { return invalid(); }
}
function machine(request: Request, projectId: string): AgentCredentialInput {
  const bearer = /^Bearer (sttag_[A-Za-z0-9_-]{43})$/u.exec(request.headers.get("authorization") ?? "");
  const rawVersion = request.headers.get("x-agent-credential-version") ?? "";
  return { projectId, agentToken: bearer?.[1], credentialVersion:
    /^[1-9]\d{0,14}$/u.test(rawVersion) ? Number(rawVersion) : undefined };
}

export interface BuildHttpDependencies {
  readonly identity: SuiteIdentityPort;
  readonly authorization: ProjectAuthorizationService;
  readonly submissions: ProjectBuildSubmissionService;
  readonly status: ProjectBuildStatusService;
}

/** Private backend transport. No request path can grant native write permission. */
export function createProjectBuildHttpHandler(deps: BuildHttpDependencies):
  (request: Request) => Promise<Response> {
  return async (request) => {
    try {
      const url = new URL(request.url);
      if (url.search) return invalid();
      const path = url.pathname;
      const userList = /^\/v1\/projects\/([^/]+)\/builds$/u.exec(path);
      const userJob = /^\/v1\/projects\/([^/]+)\/builds\/([^/]+)(\/cancel)?$/u.exec(path);
      const agentClaim = /^\/v1\/agent\/projects\/([^/]+)\/jobs\/([^/]+)\/claim$/u.exec(path);
      const agentQueue = /^\/v1\/agent\/projects\/([^/]+)\/queue$/u.exec(path);
      const agentLease = /^\/v1\/agent\/projects\/([^/]+)\/jobs\/([^/]+)\/leases\/([1-9]\d*)\/(frozen|progress)$/u.exec(path);
      if (userList || userJob) {
        const principal = await deps.authorization.authenticateRequest(request, deps.identity);
        if (userList && request.method === "POST") {
          return reply(202, await deps.submissions.submit(userList[1]!, principal, await body(request)));
        }
        if (userJob && request.method === "GET" && !userJob[3] && request.body === null) {
          return reply(200, await deps.status.get(userJob[1]!, principal, userJob[2]!));
        }
        if (userJob && request.method === "POST" && userJob[3] === "/cancel" && request.body === null) {
          return reply(200, { status: await deps.status.cancel(userJob[1]!, principal, userJob[2]!) });
        }
      }
      if (agentClaim && request.method === "POST" && request.body === null) {
        return reply(200, await deps.status.claim(machine(request, agentClaim[1]!), agentClaim[2]!));
      }
      if (agentQueue && request.method === "GET" && request.body === null) {
        return reply(200, { jobIds: await deps.status.pollQueued(machine(request, agentQueue[1]!)) });
      }
      if (agentLease) {
        const epoch = Number(agentLease[3]);
        if (!Number.isSafeInteger(epoch)) return invalid();
        const credential = machine(request, agentLease[1]!);
        if (agentLease[4] === "frozen" && request.method === "GET" && request.body === null) {
          return reply(200, await deps.status.frozenForAgent(credential, agentLease[2]!, epoch));
        }
        if (agentLease[4] === "progress" && request.method === "POST") {
          const fields = object(await body(request), ["status", "stageKey", "receiptDigest", "reasonCode"]);
          if (!["running", "needs_action", "waiting_reconcile", "failed"].includes(fields.status as string)) {
            return invalid();
          }
          const report: StageProgress = { leaseEpoch: epoch,
            status: fields.status as StageProgress["status"],
            stageKey: fields.stageKey as string, receiptDigest: fields.receiptDigest as string | null,
            reasonCode: fields.reasonCode as string | null };
          return reply(202, { eventId: await deps.status.appendProgress(credential, agentLease[2]!, report) });
        }
      }
      return reply(404, { error: "not_found" });
    } catch (error) {
      if (error instanceof ProjectAuthError || error instanceof AgentAuthenticationError ||
          error instanceof BuildServiceError || error instanceof BuildInputRefusal) {
        return reply(error.status, { error: error instanceof BuildInputRefusal ? "invalid_build_intent" :
          error instanceof ProjectAuthError ? error.code : error instanceof BuildServiceError ? error.code :
            error.code });
      }
      return reply(503, { error: "service_unavailable" });
    }
  };
}
