import type { ScriptDocumentV2, AuthoringProjectSettingsV1 } from "@vera/contracts/v2";
import {
  ProjectAuthError,
  type ProjectAuthorizationService,
  type SuiteIdentityPort,
} from "@vera/project-authorization";

import {
  ProjectDocumentError,
  ProjectDocumentInputError,
  requireObject,
} from "./model.js";
import type { ProjectCommentService } from "./comments.js";
import type { ProjectDocumentService } from "./service.js";

/** Max request bytes, including a full typed ScriptDocumentV2. */
export const MAX_PROJECT_API_BODY_BYTES = 512 * 1024;
const headers = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
};

function response(status: number, value: unknown): Response {
  return new Response(JSON.stringify(value), { status, headers });
}

function fail(error: unknown): Response {
  if (error instanceof ProjectAuthError) {
    return response(error.status, { error: error.code });
  }
  if (error instanceof ProjectDocumentError) {
    return response(error.status, { error: error.code, ...(error.metadata ?? {}) });
  }
  return response(503, { error: "service_unavailable" });
}

function fields(value: unknown, allowed: readonly string[], required: readonly string[]): Record<string, unknown> {
  const record = requireObject(value);
  if (Object.keys(record).some((key) => !allowed.includes(key)) ||
      required.some((key) => !Object.hasOwn(record, key))) {
    throw new ProjectDocumentInputError("Unexpected or missing request fields.");
  }
  return record;
}

async function jsonBody(request: Request): Promise<Record<string, unknown>> {
  if (!/^application\/json(?:\s*;|\s*$)/iu.test(request.headers.get("content-type") ?? "")) {
    throw new ProjectDocumentInputError("Content-Type must be application/json.");
  }
  const length = request.headers.get("content-length");
  if (length !== null && Number(length) > MAX_PROJECT_API_BODY_BYTES) {
    throw new ProjectDocumentInputError("Request body is too large.");
  }
  const reader = request.body?.getReader();
  if (!reader) throw new ProjectDocumentInputError("Missing JSON body.");
  const parts: Uint8Array[] = [];
  let count = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      count += next.value.byteLength;
      if (count > MAX_PROJECT_API_BODY_BYTES) {
        await reader.cancel().catch(() => undefined);
        throw new ProjectDocumentInputError("Request body is too large.");
      }
      parts.push(next.value);
    }
  } catch (error) {
    if (error instanceof ProjectDocumentInputError) throw error;
    throw new ProjectDocumentInputError("Could not read request body.");
  } finally {
    reader.releaseLock();
  }
  try {
    const bytes = new Uint8Array(count);
    let offset = 0;
    for (const part of parts) {
      bytes.set(part, offset);
      offset += part.byteLength;
    }
    const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    return requireObject(parsed);
  } catch {
    throw new ProjectDocumentInputError("Invalid JSON object.");
  }
}

export interface ProjectApiDependencies {
  /** Existing trusted suite identity adapter; no user/role values come from JSON or headers. */
  identity?: SuiteIdentityPort;
  authorization: ProjectAuthorizationService;
  documents: ProjectDocumentService;
  comments?: ProjectCommentService;
}

/** Unmounted Request -> Response handler. Hosting and identity implementation are outside #380. */
export function createProjectApiHandler(deps: ProjectApiDependencies): (request: Request) => Promise<Response> {
  return async (request: Request): Promise<Response> => {
    try {
      if (!deps.identity) throw new ProjectAuthError("authentication_required", 401);
      // Authenticate even for malformed or oversize bodies: no anonymous bypass.
      const principal = await deps.authorization.authenticateRequest(request, deps.identity);
      const url = new URL(request.url);
      if (url.search) throw new ProjectDocumentInputError("Query parameters are not supported.");
      const path = url.pathname;
      if (path === "/v1/projects" && request.method === "POST") {
        const body = fields(await jsonBody(request),
          ["clientRequestId", "projectId", "title", "document", "settings"],
          ["clientRequestId", "projectId", "title", "document"]);
        const result = await deps.documents.createProject(principal, {
          clientRequestId: body.clientRequestId as string,
          projectId: body.projectId as string,
          title: body.title as string,
          document: body.document as ScriptDocumentV2,
          ...(Object.hasOwn(body, "settings") ? { settings: body.settings as AuthoringProjectSettingsV1 } : {}),
        });
        return response(result.duplicateDelivery ? 200 : 201, result);
      }
      const commentPath = /^\/v1\/projects\/([^/]+)\/comments(?:\/(operations))?$/u.exec(path);
      if (commentPath) {
        if (!deps.comments) throw new ProjectDocumentError("service_unavailable", 503);
        const projectId = commentPath[1]!;
        if (request.method === "GET" && !commentPath[2]) {
          return response(200, await deps.comments.getComments(projectId, principal));
        }
        if (request.method === "POST" && commentPath[2] === "operations") {
          const input = fields(await jsonBody(request),
            ["expectedCommentRevision", "clientMutationId", "operation"],
            ["expectedCommentRevision", "clientMutationId", "operation"]);
          return response(200, await deps.comments.applyOperation(projectId, principal, {
            expectedCommentRevision: input.expectedCommentRevision as number,
            clientMutationId: input.clientMutationId as string,
            operation: input.operation,
          }));
        }
        return response(404, { error: "not_found" });
      }
      const project = /^\/v1\/projects\/([^/]+)(?:\/(document|settings))?$/u.exec(path);
      if (!project) return response(404, { error: "not_found" });
      const id = project[1]!;
      const resource = project[2];
      if (request.method === "GET") {
        if (resource === "document") return response(200, await deps.documents.getDocument(id, principal));
        if (resource === "settings") return response(200, await deps.documents.getSettings(id, principal));
        if (!resource) return response(200, { project: await deps.documents.getProject(id, principal) });
      }
      if (request.method === "PATCH" && !resource) {
        const body = fields(await jsonBody(request),
          ["expectedProjectVersion", "clientMutationId", "title"],
          ["expectedProjectVersion", "clientMutationId", "title"]);
        return response(200, await deps.documents.patchProject(id, principal, {
          expectedProjectVersion: body.expectedProjectVersion as number,
          clientMutationId: body.clientMutationId as string,
          title: body.title as string,
        }));
      }
      if (request.method === "PUT" && resource === "document") {
        const body = fields(await jsonBody(request),
          ["expectedRevision", "clientMutationId", "document", "writeSessionId"],
          ["expectedRevision", "clientMutationId", "document"]);
        return response(200, await deps.documents.putDocument(id, principal, {
          expectedRevision: body.expectedRevision as number,
          clientMutationId: body.clientMutationId as string,
          document: body.document as ScriptDocumentV2,
          ...(Object.hasOwn(body, "writeSessionId") ? { writeSessionId: body.writeSessionId as string } : {}),
        }));
      }
      if (request.method === "PUT" && resource === "settings") {
        const body = fields(await jsonBody(request),
          ["expectedSettingsRevision", "clientMutationId", "settings"],
          ["expectedSettingsRevision", "clientMutationId", "settings"]);
        return response(200, await deps.documents.putSettings(id, principal, {
          expectedSettingsRevision: body.expectedSettingsRevision as number,
          clientMutationId: body.clientMutationId as string,
          settings: body.settings as AuthoringProjectSettingsV1,
        }));
      }
      return response(404, { error: "not_found" });
    } catch (error) {
      return fail(error);
    }
  };
}
