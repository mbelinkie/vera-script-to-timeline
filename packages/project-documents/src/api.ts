import type { ScriptDocumentV2, AuthoringProjectSettingsV1 } from "@vera/contracts/v2";
import {
  ProjectAuthError,
  type ProjectAuthorizationService,
  type SuiteIdentityPort,
} from "@vera/project-authorization";

import {
  ProjectDocumentError,
  ProjectDocumentInputError,
  requireHistoryLimit,
  requireObject,
  requireRevision,
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

/** Whitelist unique query keys rather than silently taking the first duplicate. */
function queryFields(url: URL, allowed: readonly string[], required: readonly string[] = []): Record<string, string> {
  const found: Record<string, string> = Object.create(null) as Record<string, string>;
  for (const [key, value] of url.searchParams) {
    if (!allowed.includes(key) || Object.hasOwn(found, key) || !value) {
      throw new ProjectDocumentInputError("Invalid query parameters.");
    }
    found[key] = value;
  }
  if (required.some((key) => !Object.hasOwn(found, key))) {
    throw new ProjectDocumentInputError("Missing query parameter.");
  }
  return found;
}

function numericParam(value: string): number {
  if (!/^(?:0|[1-9][0-9]*)$/u.test(value)) throw new ProjectDocumentInputError("Invalid revision.");
  return requireRevision(Number(value));
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
      const path = url.pathname;
      const history = /^\/v1\/projects\/([^/]+)\/history(?:\/(compare|[^/]+))?$/u.exec(path);
      if (history && request.method === "GET") {
        const id = history[1]!;
        if (!history[2]) {
          const query = queryFields(url, ["limit", "beforeRevision"]);
          return response(200, await deps.documents.listDocumentRevisions(id, principal, {
            ...(query.limit === undefined ? {} : { limit: requireHistoryLimit(numericParam(query.limit)) }),
            ...(query.beforeRevision === undefined ? {} : { beforeRevision: numericParam(query.beforeRevision) }),
          }));
        }
        if (history[2] === "compare") {
          const query = queryFields(url, ["fromRevision", "toRevision"], ["fromRevision", "toRevision"]);
          return response(200, await deps.documents.compareDocumentRevisions(id, principal,
            numericParam(query.fromRevision!), numericParam(query.toRevision!)));
        }
        queryFields(url, []);
        return response(200, await deps.documents.getDocumentRevision(id, principal, numericParam(history[2])));
      }
      const checkpoint = /^\/v1\/projects\/([^/]+)\/checkpoints(?:\/([^/]+)(?:\/(approve|restore))?)?$/u.exec(path);
      if (checkpoint) {
        const id = checkpoint[1]!;
        const checkpointId = checkpoint[2];
        const operation = checkpoint[3];
        if (request.method === "GET" && !operation) {
          if (checkpointId) {
            queryFields(url, []);
            return response(200, await deps.documents.getCheckpoint(id, principal, checkpointId));
          }
          const query = queryFields(url, ["limit", "beforeCheckpointId"]);
          return response(200, await deps.documents.listCheckpoints(id, principal, {
            ...(query.limit === undefined ? {} : { limit: requireHistoryLimit(numericParam(query.limit)) }),
            ...(query.beforeCheckpointId === undefined ? {} : { beforeCheckpointId: query.beforeCheckpointId }),
          }));
        }
        if (request.method === "POST") {
          queryFields(url, []);
          if (!checkpointId) {
            const data = fields(await jsonBody(request),
              ["checkpointId", "clientMutationId", "name", "sourceRevision"],
              ["checkpointId", "clientMutationId", "name", "sourceRevision"]);
            const created = await deps.documents.createCheckpoint(id, principal, {
              checkpointId: data.checkpointId as string,
              clientMutationId: data.clientMutationId as string,
              name: data.name as string,
              sourceRevision: data.sourceRevision as number,
            });
            return response(created.duplicateDelivery ? 200 : 201, created);
          }
          if (operation === "approve") {
            const data = fields(await jsonBody(request), ["clientMutationId"], ["clientMutationId"]);
            const approved = await deps.documents.approveCheckpoint(id, principal, checkpointId,
              { clientMutationId: data.clientMutationId as string });
            return response(approved.duplicateDelivery ? 200 : 201, approved);
          }
          if (operation === "restore") {
            const data = fields(await jsonBody(request),
              ["expectedRevision", "clientMutationId", "writeSessionId"],
              ["expectedRevision", "clientMutationId"]);
            return response(200, await deps.documents.restoreCheckpoint(id, principal, checkpointId, {
              expectedRevision: data.expectedRevision as number,
              clientMutationId: data.clientMutationId as string,
              ...(Object.hasOwn(data, "writeSessionId") ? { writeSessionId: data.writeSessionId as string } : {}),
            }));
          }
        }
        return response(404, { error: "not_found" });
      }
      if (url.search) throw new ProjectDocumentInputError("Query parameters are not supported.");
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
      const ideasPath = /^\/v1\/projects\/([^/]+)\/ideas(?:\/(promotions))?$/u.exec(path);
      if (ideasPath) {
        const projectId = ideasPath[1]!;
        if (request.method === "GET" && !ideasPath[2]) {
          return response(200, await deps.documents.getIdeas(projectId, principal));
        }
        if (request.method === "PUT" && !ideasPath[2]) {
          const input = fields(await jsonBody(request),
            ["expectedIdeasRevision", "clientMutationId", "ideas", "writeSessionId"],
            ["expectedIdeasRevision", "clientMutationId", "ideas"]);
          return response(200, await deps.documents.putIdeas(projectId, principal, {
            expectedIdeasRevision: input.expectedIdeasRevision as number,
            clientMutationId: input.clientMutationId as string,
            ideas: input.ideas as Parameters<ProjectDocumentService["putIdeas"]>[2]["ideas"],
            ...(Object.hasOwn(input, "writeSessionId") ? { writeSessionId: input.writeSessionId as string } : {}),
          }));
        }
        if (request.method === "POST" && ideasPath[2] === "promotions") {
          const input = fields(await jsonBody(request),
            ["expectedIdeasRevision", "expectedRevision", "clientMutationId", "ideaId",
              "draftBlockId", "orderKey", "destination", "writeSessionId"],
            ["expectedIdeasRevision", "expectedRevision", "clientMutationId", "ideaId",
              "draftBlockId", "orderKey", "destination"]);
          return response(200, await deps.documents.promoteIdea(projectId, principal, {
            expectedIdeasRevision: input.expectedIdeasRevision as number,
            expectedRevision: input.expectedRevision as number,
            clientMutationId: input.clientMutationId as string,
            ideaId: input.ideaId as string,
            draftBlockId: input.draftBlockId as string,
            orderKey: input.orderKey as string,
            destination: input.destination as Parameters<ProjectDocumentService["promoteIdea"]>[2]["destination"],
            ...(Object.hasOwn(input, "writeSessionId") ? { writeSessionId: input.writeSessionId as string } : {}),
          }));
        }
        return response(404, { error: "not_found" });
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
      const extras = /^\/v1\/projects\/([^/]+)\/document\/extras-operations$/u.exec(path);
      if (extras) {
        if (request.method !== "POST") return response(404, { error: "not_found" });
        queryFields(url, []);
        const data = fields(await jsonBody(request),
          ["expectedRevision", "clientMutationId", "operation", "writeSessionId"],
          ["expectedRevision", "clientMutationId", "operation"]);
        return response(200, await deps.documents.applyExtrasOperation(extras[1]!, principal, {
          expectedRevision: data.expectedRevision as number,
          clientMutationId: data.clientMutationId as string,
          operation: data.operation,
          ...(Object.hasOwn(data, "writeSessionId") ? { writeSessionId: data.writeSessionId as string } : {}),
        }));
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
