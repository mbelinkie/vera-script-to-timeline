import { randomUUID } from "node:crypto";

import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler, MAX_PROJECT_API_BODY_BYTES } from "../src/api.js";
import { documentFor, harness, initialProject, settingsFor } from "./helpers.js";

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
  return { ...h, api: createProjectApiHandler({ identity, authorization: h.auth, documents: h.service }) };
}
afterEach(async () => { for (const cleanup of cleaners.splice(0)) await cleanup(); });

describe("authenticated and bounded project-document API", () => {
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
});
