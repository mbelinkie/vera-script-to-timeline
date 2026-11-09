import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler, MAX_PROJECT_API_BODY_BYTES } from "../src/api.js";
import { ProjectCommentService } from "../src/comments.js";
import { documentFor, extrasDocumentFor, harness, initialProject, settingsFor } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Injected fake suite identity for HTTP tests only. */
vi.setConfig({ testTimeout: 90_000 });
const cleaners: Array<() => Promise<void>> = [];
const base = "https://local.stt.test/v1/projects";

async function body(response: Response): Promise<Record<string, unknown>> {
  const value: unknown = await response.json();
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Expected JSON object");
  return value as Record<string, unknown>;
}

// This is a TEST DOUBLE for a trusted suite adapter, not a production header
// authentication mechanism. Production must inject a verified provider.
const identity: SuiteIdentityPort = {
  authenticate: async (req) => {
    const subject = req.headers.get("X-Test-Suite-Identity");
    if (!subject) throw new Error("unverified");
    return { issuer: "https://trusted.suite.test", subject };
  },
};

function request(path: string, method: string, subject: string, json?: unknown, headers?: Record<string, string>): Request {
  return new Request(base + path, {
    method,
    headers: {
      "X-Test-Suite-Identity": subject,
      ...(json === undefined ? {} : { "content-type": "application/json" }),
      ...headers,
    },
    ...(json === undefined ? {} : { body: JSON.stringify(json) }),
  });
}
async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const comments = new ProjectCommentService(h.pool, h.auth);
  return { ...h, comments, api: createProjectApiHandler({ identity, authorization: h.auth,
    documents: h.service, comments }) };
}
afterEach(async () => { for (const cleanup of cleaners.splice(0)) await cleanup(); });

describe("authenticated and bounded project-document API", () => {
  it("enforces strict Extras HTTP shapes, Editor lease, opaque failures, CAS and idempotent replay", async () => {
    const { api, auth, owner, editor, viewer, service } = await setup();
    const projectId = randomUUID();
    const { document, rowId, sectionId } = extrasDocumentFor(projectId);
    expect((await api(request("", "POST", "owner", {
      projectId, title: "Extras API", clientRequestId: randomUUID(), document,
    }))).status).toBe(201);
    await auth.changeMembership(projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(projectId, owner, viewer.principalId, "viewer");
    const route = `/${projectId}/document/extras-operations`;
    const writeSessionId = await auth.openWriteSession(projectId, editor);
    const operation = { kind: "stash_rows", rowIds: [rowId], bundleId: randomUUID() };
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(), writeSessionId, operation };
    expect((await api(request(route, "GET", "editor"))).status).toBe(404);
    expect((await api(request(route + "?x=1", "POST", "editor", mutation))).status).toBe(400);
    expect((await api(request(route, "POST", "viewer", mutation))).status).toBe(403);
    expect((await api(request(`/${randomUUID()}/document/extras-operations`, "POST", "editor", mutation))).status)
      .toBe(403);
    expect((await api(request(route, "POST", "editor", {
      ...mutation, writeSessionId: randomUUID(),
    }))).status).toBe(403);
    for (const bad of [
      { ...mutation, role: "producer" },
      { ...mutation, operation: { ...operation, actorId: owner.principalId } },
      { ...mutation, operation: { kind: "delete_rows", rowIds: [rowId] } },
      { ...mutation, operation: { ...operation, rowIds: [rowId, rowId] } },
      { ...mutation, operation: null },
      { ...mutation, expectedRevision: "0" },
      { clientMutationId: randomUUID(), operation },
    ]) {
      const rejected = await api(request(route, "POST", "editor", bad));
      expect(rejected.status).toBe(400);
    }
    expect((await api(request(route, "POST", "editor", mutation, {
      "content-length": String(MAX_PROJECT_API_BODY_BYTES + 1),
    }))).status).toBe(400);
    expect((await api(new Request(base + route, { method: "POST",
      headers: { "content-type": "application/json" }, body: "{invalid" }))).status).toBe(401);
    expect((await api(new Request(base + route, { method: "POST", headers: {
      "content-type": "application/json", "X-Test-Suite-Identity": "editor",
    }, body: "{invalid" }))).status).toBe(400);
    expect((await service.getDocument(projectId, viewer)).revision).toBe(0);

    const written = await api(request(route, "POST", "editor", mutation));
    expect(written.status).toBe(200);
    const receipt = await body(written);
    expect(receipt).toMatchObject({ revision: 1, duplicateDelivery: false });
    expect(await body(await api(request(route, "POST", "editor", mutation))))
      .toMatchObject({ ...receipt, duplicateDelivery: true });
    expect((await api(request(route, "POST", "editor", { ...mutation,
      operation: { ...operation, bundleId: randomUUID() } }))).status).toBe(409);
    const stale = await body(await api(request(route, "POST", "editor", {
      ...mutation, clientMutationId: randomUUID(),
    })));
    expect(stale).toMatchObject({ error: "version_conflict", currentRevision: 1 });
    const refused = await body(await api(request(route, "POST", "editor", {
      ...mutation, expectedRevision: 1, clientMutationId: randomUUID(),
      operation: { kind: "restore_stash", bundleId: operation.bundleId,
        destination: { sectionId, afterRowId: randomUUID(), beforeRowId: null } },
    })));
    expect(refused).toMatchObject({ error: "invalid_request", operationCode: "ROW_DESTINATION_INVALID" });
    const current = await service.getDocument(projectId, viewer);
    expect(current.revision).toBe(1);
    await auth.changeMembership(projectId, owner, editor.principalId, null);
    expect((await api(request(route, "POST", "editor", mutation))).status).toBe(403);
    expect(await service.getDocument(projectId, viewer)).toEqual(current);
  });

  it("serves strict authorized Ideas GET/PUT and atomic Draft promotion with stable replay", async () => {
    const { api, auth, owner, editor, viewer, service } = await setup();
    const initial = initialProject();
    const other = initialProject();
    expect((await api(request("", "POST", "owner", initial))).status).toBe(201);
    expect((await api(request("", "POST", "owner", other))).status).toBe(201);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    const url = `/${initial.projectId}/ideas`;
    const empty = await api(request(url, "GET", "viewer"));
    expect(empty.status).toBe(200);
    expect(empty.headers.get("cache-control")).toBe("no-store");
    expect(await body(empty)).toMatchObject({ projectId: initial.projectId, ideasRevision: 0,
      ideas: { schemaVersion: "stt-idea-outline/v1", documentId: initial.document.id, items: [] } });
    const idea = { id: randomUUID(), parentId: null, orderKey: "a", text: "  exact\nIdea  ",
      state: "open", linkedDraftBlockIds: [], collapsed: false, version: 1 };
    const put = { expectedIdeasRevision: 0, clientMutationId: randomUUID(),
      ideas: { schemaVersion: "stt-idea-outline/v1", documentId: initial.document.id, items: [idea] } };
    expect((await api(request(url, "PUT", "viewer", put))).status).toBe(403);
    const created = await api(request(url, "PUT", "editor", put));
    expect(created.status).toBe(200);
    expect(await body(created)).toMatchObject({ ideasRevision: 1, duplicateDelivery: false });
    expect(await body(await api(request(url, "PUT", "editor", put))))
      .toMatchObject({ ideasRevision: 1, duplicateDelivery: true });
    expect((await api(request(url, "PUT", "editor", { ...put, ideas: {
      ...put.ideas, items: [{ ...idea, text: "changed" }],
    } }))).status).toBe(409);
    expect((await api(request(url, "PUT", "editor", {
      ...put, clientMutationId: randomUUID(),
    }))).status).toBe(409);
    expect((await api(request(url, "GET", "viewer"))).status).toBe(200);
    expect((await body(await api(request(url, "GET", "viewer")))).ideas)
      .toEqual(put.ideas);

    const promote = { expectedIdeasRevision: 1, expectedRevision: 0,
      clientMutationId: randomUUID(), ideaId: idea.id, draftBlockId: randomUUID(),
      orderKey: "a", destination: { sectionId: null, afterRowId: null, beforeRowId: null } };
    expect((await api(request(url + "/promotions", "POST", "viewer", promote))).status).toBe(403);
    expect((await api(request(url + "/promotions", "POST", "editor", {
      ...promote, expectedRevision: 1,
    }))).status).toBe(409);
    const promoted = await api(request(url + "/promotions", "POST", "editor", promote));
    expect(promoted.status).toBe(200);
    expect(await body(promoted)).toMatchObject({ ideasRevision: 2, documentRevision: 1,
      duplicateDelivery: false });
    expect(await body(await api(request(url + "/promotions", "POST", "editor", promote))))
      .toMatchObject({ ideasRevision: 2, documentRevision: 1, duplicateDelivery: true });
    expect((await api(request(url + "/promotions", "POST", "editor", {
      ...promote, clientMutationId: randomUUID(),
    }))).status).toBe(409);
    const after = await service.getDocument(initial.projectId, owner);
    expect(after.document.activeDraft.blocks).toEqual([{
      type: "note_draft", id: promote.draftBlockId, orderKey: "a", text: idea.text,
      state: "excluded", version: 1,
    }]);
    expect(after.document.ideaOutline).toEqual([]);
    expect((await body(await api(request(url, "GET", "viewer")))).ideas)
      .toMatchObject({ items: [{ ...idea, state: "incorporated", version: 2,
        linkedDraftBlockIds: [promote.draftBlockId] }] });

    // Authentication precedes body decoding, and neither auth nor parsing can be bypassed.
    expect((await api(new Request(base + url, { method: "PUT", headers:
      { "content-type": "application/json" }, body: "{broken" }))).status).toBe(401);
    expect((await api(new Request(base + url + "/promotions", { method: "POST", headers:
      { "content-type": "application/json", "X-Test-Suite-Identity": "editor" },
    body: "{broken" }))).status).toBe(400);
    expect((await api(request(url, "PUT", "editor", { ...put, role: "producer" }))).status).toBe(400);
    expect((await api(request(url + "/promotions", "POST", "editor", {
      ...promote, actorId: editor.principalId,
    }))).status).toBe(400);
    expect((await api(request(url + "/promotions", "POST", "editor", {
      ...promote, destination: { ...promote.destination, role: "producer" },
    }))).status).toBe(400);
    expect((await api(request(url + "/promotions?actorId=x", "POST", "editor", promote))).status).toBe(400);
    expect((await api(request(url + "?includeDraft=true", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(url, "POST", "owner", put))).status).toBe(404);
    expect((await api(request(url + "/promotions", "GET", "owner"))).status).toBe(404);
    expect((await api(request(`/${other.projectId}/ideas`, "GET", "editor"))).status).toBe(403);
    expect((await api(request(`/${other.projectId}/ideas/promotions`, "POST", "editor", promote))).status).toBe(403);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, null);
    expect((await api(request(url, "PUT", "editor", put))).status).toBe(403);
    expect((await api(request(url + "/promotions", "POST", "editor", promote))).status).toBe(403);
  });

  it("exposes trusted attributed history and bounded typed comparisons without relaxing other routes", async () => {
    const { api, auth, owner, editor, viewer } = await setup();
    const initial = initialProject();
    expect((await api(request("", "POST", "owner", initial))).status).toBe(201);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    const id = "/" + initial.projectId;
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "Second version" } };
    expect((await api(request(id + "/document", "PUT", "editor", mutation))).status).toBe(200);
    const page = await api(request(id + "/history?limit=1", "GET", "viewer"));
    expect(page.status).toBe(200);
    expect(page.headers.get("cache-control")).toBe("no-store");
    expect(page.headers.get("x-content-type-options")).toBe("nosniff");
    expect(await body(page)).toMatchObject({ nextBeforeRevision: 1,
      revisions: [{ revision: 1, actorId: editor.principalId,
        clientMutationId: mutation.clientMutationId, expectedRevision: 0 }] });
    expect(await body(await api(request(id + "/history?beforeRevision=1", "GET", "viewer"))))
      .toMatchObject({ revisions: [{ revision: 0, expectedRevision: null }],
        nextBeforeRevision: null });
    expect(await body(await api(request(id + "/history/0", "GET", "viewer"))))
      .toMatchObject({ revision: 0, document: initial.document });
    const compared = await body(await api(request(
      id + "/history/compare?fromRevision=0&toRevision=1", "GET", "viewer")));
    expect(compared).toMatchObject({ totalChanges: 1, truncated: false,
      changes: [{ surface: "document", kind: "modified", fields: ["title"] }] });
    expect((await api(request(id + "/history/99", "GET", "viewer"))).status).toBe(404);
    expect((await api(request(id + "/history?limit=101", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history?limit=1&limit=2", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history?beforeRevision=-1", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history?beforeRevision=9007199254740993", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history?actorId=" + owner.principalId, "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history/compare?fromRevision=0", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history/0?limit=1", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(id + "/history", "POST", "owner", {}))).status).toBe(404);
    expect((await api(request(id + "/document?limit=1", "GET", "viewer"))).status).toBe(400);
    expect((await api(request("/" + randomUUID() + "/history", "GET", "viewer"))).status).toBe(403);
  });

  it("creates/approves/restores checkpoints via strict HTTP with auth-before-body and foreign-project denial", async () => {
    const { api, auth, owner, editor, viewer } = await setup();
    const project = initialProject();
    const other = initialProject();
    await api(request("", "POST", "owner", project));
    await api(request("", "POST", "owner", other));
    await auth.changeMembership(project.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(project.projectId, owner, viewer.principalId, "viewer");
    const path = "/" + project.projectId + "/checkpoints";
    const checkpointId = randomUUID();
    const create = { checkpointId, clientMutationId: randomUUID(), name: "First snapshot", sourceRevision: 0 };
    expect((await api(request(path, "POST", "viewer", create))).status).toBe(403);
    const created = await api(request(path, "POST", "editor", create));
    expect(created.status).toBe(201);
    expect((await body(created)).approval).toBeNull();
    expect((await body(await api(request(path, "POST", "editor", create)))).duplicateDelivery).toBe(true);
    expect((await api(request(path, "POST", "editor", {
      ...create, clientMutationId: randomUUID(), name: "FIRST SNAPSHOT",
    }))).status).toBe(409);
    const list = await api(request(path + "?limit=1", "GET", "viewer"));
    expect(await body(list)).toMatchObject({ checkpoints: [{ checkpointId, approval: null }] });
    expect(await body(await api(request(path + "/" + checkpointId, "GET", "viewer"))))
      .toMatchObject({ name: create.name, sourceRevision: 0, document: project.document });
    const approve = { clientMutationId: randomUUID() };
    expect((await api(request(path + "/" + checkpointId + "/approve", "POST", "editor", approve))).status).toBe(403);
    expect((await api(request(path + "/" + checkpointId + "/approve", "POST", "owner", approve))).status).toBe(201);
    expect((await api(request(path + "/" + checkpointId + "/approve", "POST", "owner", approve))).status).toBe(200);
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...project.document, title: "Changed" } };
    expect((await api(request("/" + project.projectId + "/document", "PUT", "editor", mutation))).status).toBe(200);
    const restore = { expectedRevision: 1, clientMutationId: randomUUID() };
    expect((await api(request(path + "/" + checkpointId + "/restore", "POST", "viewer", restore))).status).toBe(403);
    const first = await api(request(path + "/" + checkpointId + "/restore", "POST", "editor", restore));
    expect(first.status).toBe(200);
    expect(await body(first)).toMatchObject({ revision: 2, duplicateDelivery: false });
    expect(await body(await api(request(path + "/" + checkpointId + "/restore", "POST", "editor", restore))))
      .toMatchObject({ revision: 2, duplicateDelivery: true });
    expect(await body(await api(request("/" + project.projectId + "/history/2", "GET", "viewer"))))
      .toMatchObject({ attribution: { restoreOrigin: { checkpointId, sourceRevision: 0 } } });
    expect((await api(request(path + "/" + checkpointId + "/restore", "POST", "editor",
      { ...restore, expectedRevision: 2, clientMutationId: randomUUID() }))).status).toBe(200);
    expect((await api(request("/" + other.projectId + "/checkpoints/" + checkpointId, "GET", "owner"))).status).toBe(404);
    expect((await api(request("/" + other.projectId + "/checkpoints/" + checkpointId +
      "/restore", "POST", "owner", restore))).status).toBe(404);
    expect((await api(request(path + "?beforeCheckpointId=bad", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(path + "/bad", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(path + "?limit=0", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(path + "/extra/extra/extra", "GET", "viewer"))).status).toBe(404);
    expect((await api(request(path + "/" + checkpointId + "/restore", "GET", "editor"))).status).toBe(404);
    expect((await api(request(path + "/" + checkpointId + "/restore", "POST", "owner",
      { ...restore, actorId: owner.principalId }))).status).toBe(400);
    expect((await api(request(path + "/" + checkpointId + "/restore", "POST", "owner",
      { ...restore, approved: true }))).status).toBe(400);
    expect((await api(request(path + "/" + checkpointId + "/approve", "POST", "owner",
      { ...approve, role: "producer" }))).status).toBe(400);
    expect((await api(request(path, "POST", "editor", {
      ...create, approval: { approvedBy: editor.principalId },
    }))).status).toBe(400);
    expect((await api(request(path + "/" + checkpointId + "/restore?actorId=x",
      "POST", "editor", restore))).status).toBe(400);
    expect((await api(request(path + "/" + checkpointId + "/restore", "POST", "editor", restore,
      { "content-length": String(MAX_PROJECT_API_BODY_BYTES + 1) }))).status).toBe(400);
    const streamed = new Request(base + path + "/" + checkpointId + "/restore", {
      method: "POST", headers: { "content-type": "application/json",
        "X-Test-Suite-Identity": "editor", "content-length": "1" },
      body: JSON.stringify(restore) + " ".repeat(MAX_PROJECT_API_BODY_BYTES),
    });
    expect((await api(streamed)).status).toBe(400);
    const anonymous = new Request(base + path + "/" + checkpointId + "/restore", {
      method: "POST", headers: { "content-type": "application/json" }, body: "{broken",
    });
    expect((await api(anonymous)).status).toBe(401);
    const malformed = new Request(base + path + "/" + checkpointId + "/restore", {
      method: "POST", headers: { "content-type": "application/json",
        "X-Test-Suite-Identity": "editor" }, body: "{broken",
    });
    expect((await api(malformed)).status).toBe(400);
  });
  it("creates, reads, updates and refuses other identities without leaking a head", async () => {
    const { api } = await setup();
    const initial = initialProject();
    const create = await api(request("", "POST", "owner", initial));
    expect(create.status).toBe(201);
    expect(create.headers.get("Cache-Control")).toBe("no-store");
    expect((await body(create)).documentRevision).toBe(0);
    expect((await api(request("", "POST", "owner", initial))).status).toBe(200);
    const get = await api(request(`/${initial.projectId}/document`, "GET", "owner"));
    expect(get.status).toBe(200);
    expect((await body(get)).document).toEqual(initial.document);
    expect((await api(request(`/${initial.projectId}`, "GET", "owner"))).status).toBe(200);
    expect((await api(request(`/${initial.projectId}/document`, "GET", "viewer"))).status).toBe(403);
    expect((await api(request(`/${randomUUID()}/document`, "GET", "viewer"))).status).toBe(403);
    expect((await api(request(`/${initial.projectId}/settings`, "GET", "owner"))).status).toBe(404);
    const mutation = { expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...initial.document, title: "New title" } };
    expect((await api(request(`/${initial.projectId}/document`, "PUT", "owner", mutation))).status).toBe(200);
    const repeated = await api(request(`/${initial.projectId}/document`, "PUT", "owner", mutation));
    expect((await body(repeated)).duplicateDelivery).toBe(true);
    const stale = await api(request(`/${initial.projectId}/document`, "PUT", "owner",
      { ...mutation, clientMutationId: randomUUID() }));
    expect(stale.status).toBe(409);
    expect((await body(stale)).currentRevision).toBe(1);
    const wrongIdentity = await api(request(`/${initial.projectId}/document`, "PUT", "owner",
      { ...mutation, clientMutationId: randomUUID(), expectedRevision: 1,
        document: documentFor(randomUUID()) }));
    expect(wrongIdentity.status).toBe(400);
  });

  it("keeps producer setup separate from Research access and blocks unwanted fields", async () => {
    const { api, auth, owner, editor, viewer } = await setup();
    const initial = initialProject();
    const injected = { ...initial, linkedResearchProjectIds: [randomUUID()] };
    expect((await api(request("", "POST", "owner", injected))).status).toBe(400);
    expect((await api(request("", "POST", "owner", initial))).status).toBe(201);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    const settings = { expectedSettingsRevision: 0, clientMutationId: randomUUID(),
      settings: settingsFor(initial.projectId) };
    expect((await api(request(`/${initial.projectId}/settings`, "PUT", "editor", settings))).status).toBe(403);
    expect((await api(request(`/${initial.projectId}/settings`, "PUT", "owner", settings))).status).toBe(200);
    expect((await api(request(`/${initial.projectId}/settings`, "GET", "viewer"))).status).toBe(200);
    expect((await api(request(`/${initial.projectId}`, "PATCH", "editor",
      { expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "No" }))).status).toBe(403);
    const patch = await api(request(`/${initial.projectId}`, "PATCH", "owner",
      { expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "Updated" }));
    expect(patch.status).toBe(200);
    expect((await body(patch)).project).toMatchObject({ projectVersion: 2 });
    const read = await api(request(`/${initial.projectId}`, "GET", "viewer"));
    expect((await body(read)).project).toMatchObject({ linkedResearchProjectIds: [] });
    // Research IDs never become readable through STT membership.
    await expect(auth.authorizeRequest(initial.projectId, viewer, "read_research"))
      .rejects.toMatchObject({ status: 403 });
  });

  it("authenticates before parsing and fails closed on oversize/invalid/missing identity", async () => {
    const { api, auth, service } = await setup();
    const noAdapter = createProjectApiHandler({ authorization: auth, documents: service });
    const huge = request("", "POST", "owner", {}, {
      "content-length": String(MAX_PROJECT_API_BODY_BYTES + 1),
    });
    expect((await api(huge)).status).toBe(400);
    expect((await noAdapter(request("", "POST", "owner", {}))).status).toBe(401);
    const invalid = new Request(base, { method: "POST", body: "{not-json", headers: {
      "content-type": "application/json",
    } });
    expect((await api(invalid)).status).toBe(401);
    expect((await api(new Request(base, { method: "POST", body: "{bad", headers: {
      "X-Test-Suite-Identity": "owner", "content-type": "application/json",
    } }))).status).toBe(400);
    expect((await api(request("", "POST", "owner", { actorId: randomUUID(), role: "producer" }))).status).toBe(400);
    expect((await api(request("/not-a-valid-route/extra", "GET", "owner"))).status).toBe(404);
  });

  it("limits actual streamed bytes even if Content-Length claims the body is small", async () => {
    const { api, service, owner } = await setup();
    const initial = initialProject();
    // Deliberately valid JSON plus ignored whitespace: without the streaming
    // byte guard this would create a project, not merely fail JSON parsing.
    const payload = JSON.stringify(initial) + " ".repeat(MAX_PROJECT_API_BODY_BYTES);
    const streamed = new Request(base, {
      method: "POST",
      headers: {
        "X-Test-Suite-Identity": "owner",
        "content-type": "application/json",
        "content-length": "1",
      },
      body: payload,
    });
    const result = await api(streamed);
    expect(result.status).toBe(400);
    expect((await body(result)).error).toBe("invalid_request");
    await expect(service.getProject(initial.projectId, owner)).rejects.toMatchObject({ status: 403 });
  });

  it("exposes a bounded comment-only view and trusted create/replay/resolve routes", async () => {
    const { api, auth, owner, editor, viewer, db } = await setup();
    const initial = initialProject();
    const fixture = JSON.parse(readFileSync(new URL(
      "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
    ), "utf8")) as { document: ScriptDocumentV2 };
    const block = structuredClone(fixture.document.activeDraft.blocks[0]!);
    initial.document.activeDraft.blocks.push(block);
    expect((await api(request("", "POST", "owner", initial))).status).toBe(201);
    await auth.changeMembership(initial.projectId, owner, editor.principalId, "editor");
    await auth.changeMembership(initial.projectId, owner, viewer.principalId, "viewer");
    const url = `/${initial.projectId}/comments`;
    const empty = await api(request(url, "GET", "viewer"));
    expect(empty.status).toBe(200);
    expect(await body(empty)).toEqual({ projectId: initial.projectId, documentRevision: 0,
      commentRevision: 0, threads: [] });
    const threadId = randomUUID();
    const payload = { expectedCommentRevision: 0, clientMutationId: randomUUID(), operation: {
      kind: "create", threadId, messageId: randomUUID(), body: "Unique comment-only secret 385",
      mentionActorIds: [owner.principalId], anchor: { kind: "block", blockId: block.id },
    } };
    expect((await api(request(`${url}/operations`, "POST", "viewer", payload))).status).toBe(403);
    const created = await api(request(`${url}/operations`, "POST", "editor", payload));
    expect(created.status).toBe(200);
    expect(await body(created)).toMatchObject({ commentRevision: 1, duplicateDelivery: false });
    expect(await body(await api(request(`${url}/operations`, "POST", "editor", payload))))
      .toMatchObject({ commentRevision: 1, duplicateDelivery: true });
    const view = await body(await api(request(url, "GET", "viewer")));
    expect(view.commentRevision).toBe(1);
    expect(view).not.toHaveProperty("initialDocument");
    expect(view).not.toHaveProperty("history");
    expect(JSON.stringify(view)).not.toContain("operations");
    expect(JSON.stringify(view)).toContain("Unique comment-only secret 385");
    expect((await db.query<{ n: number }>("SELECT count(*)::integer AS n FROM stt_comment_events"))
      .rows[0]?.n).toBe(1);
    const resolved = await api(request(`${url}/operations`, "POST", "owner", {
      expectedCommentRevision: 1, clientMutationId: randomUUID(), operation: { kind: "resolve", threadId },
    }));
    expect((await body(resolved)).commentRevision).toBe(2);
    expect((await api(request(`${url}/operations`, "POST", "viewer", payload))).status).toBe(403);
  });

  it("rejects cross-tenant comment reads/writes, spoofed actors, arbitrary fields and query strings", async () => {
    const { api, auth, owner, editor } = await setup();
    const first = initialProject();
    const other = initialProject();
    expect((await api(request("", "POST", "owner", first))).status).toBe(201);
    expect((await api(request("", "POST", "owner", other))).status).toBe(201);
    await auth.changeMembership(first.projectId, owner, editor.principalId, "editor");
    const foreign = `/${other.projectId}/comments`;
    const operation = { expectedCommentRevision: 0, clientMutationId: randomUUID(), operation: {
      kind: "resolve", threadId: randomUUID(),
    } };
    expect((await api(request(foreign, "GET", "editor"))).status).toBe(403);
    expect((await api(request(`${foreign}/operations`, "POST", "editor", operation))).status).toBe(403);
    expect((await api(request(`/${randomUUID()}/comments`, "GET", "editor"))).status).toBe(403);
    const own = `/${first.projectId}/comments`;
    expect((await api(request(`${own}?actorId=${owner.principalId}`, "GET", "editor"))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "POST", "editor", {
      ...operation, actorId: editor.principalId,
    }))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "POST", "editor", {
      ...operation, operation: { ...operation.operation, actorId: editor.principalId },
    }))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "POST", "editor", {
      ...operation, operation: { kind: "replace_document", document: first.document },
    }))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "POST", "editor", {
      ...operation, operation: { kind: "reply", threadId: randomUUID(), messageId: randomUUID(),
        body: "spoof", mentionActorIds: [randomUUID()] },
    }))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "POST", "editor", operation, {
      "content-length": String(MAX_PROJECT_API_BODY_BYTES + 1),
    }))).status).toBe(400);
    expect((await api(request(`${own}/operations`, "GET", "editor"))).status).toBe(404);
    expect((await api(request(`${own}`, "POST", "editor", operation))).status).toBe(404);
    expect((await api(request(`${own}/operations/extra`, "POST", "editor", operation))).status).toBe(404);
    const anonymous = new Request(base + `${own}/operations`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{broken",
    });
    expect((await api(anonymous)).status).toBe(401);
  });
});
