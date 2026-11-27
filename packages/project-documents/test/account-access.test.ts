import { randomUUID } from "node:crypto";
import { expect, it } from "vitest";
import { createProjectApiHandler } from "../src/api.js";
import { harness, initialProject } from "./helpers.js";

it("exposes only current access and Producer roster; validates membership mutations and revokes sessions", async () => {
  const h = await harness();
  try {
    const identity = { authenticate: (req: Request) => Promise.resolve({ issuer: "https://trusted.suite.test",
      subject: req.headers.get("authorization")?.slice(7) ?? "unknown" }) };
    const api = createProjectApiHandler({ identity, authorization: h.auth, documents: h.service });
    const project = initialProject();
    await h.service.createProject(h.owner, project);
    const id = project.projectId;
    const req = (path: string, method = "GET", who = "owner", data?: unknown) => api(new Request(
      `https://test.invalid/v1/projects/${id}${path}`, { method,
        headers: { authorization: `Bearer ${who}`, "content-type": "application/json" },
        ...(data === undefined ? {} : { body: JSON.stringify(data) }),
      }));
    expect(await (await req("/access")).json()).toEqual({ actorId: h.owner.principalId,
      role: "producer", membershipVersion: 1 });
    expect((await req(`/members/${h.editor.principalId}`, "PATCH", "owner", { role: "editor" })).status).toBe(200);
    expect((await req(`/members/${h.viewer.principalId}`, "PATCH", "owner", { role: "viewer" })).status).toBe(200);
    const roster = await req("/members");
    expect(roster.headers.get("cache-control")).toBe("no-store");
    expect((await roster.json() as { members: unknown[] }).members).toHaveLength(3);
    for (const who of ["editor", "viewer", "unknown"]) {
      expect((await req("/members", "GET", who)).status).toBe(403);
      expect((await req(`/members/${h.viewer.principalId}`, "PATCH", who, { role: "producer" })).status).toBe(403);
    }
    for (const data of [{ role: "owner" }, { role: 3 }, { role: "viewer", actorId: h.owner.principalId }, {}]) {
      expect((await req(`/members/${h.viewer.principalId}`, "PATCH", "owner", data)).status).toBe(400);
    }
    expect((await req(`/members/${randomUUID()}`, "PATCH", "owner", { role: "editor" })).status).toBe(403);
    expect((await req(`/members/${h.owner.principalId}`, "PATCH", "owner", { role: null })).status).toBe(403);
    expect((await req("/access?role=producer")).status).toBe(400);
    expect((await req("/members/nope", "PATCH", "owner", { role: "viewer" })).status).toBe(400);
    const session = await h.auth.openWriteSession(id, h.editor);
    const before = await h.service.getDocument(id, h.owner);
    expect((await req(`/members/${h.editor.principalId}`, "PATCH", "owner", { role: "viewer" })).status).toBe(200);
    await expect(h.auth.authorizeRequest(id, h.editor, "edit_document", session)).rejects.toMatchObject({ status: 403 });
    expect((await req("/document", "PUT", "editor", { expectedRevision: before.revision,
      clientMutationId: randomUUID(), document: before.document })).status).toBe(403);
    expect((await h.service.getDocument(id, h.owner)).revision).toBe(before.revision);
    await req(`/members/${h.editor.principalId}`, "PATCH", "owner", { role: "editor" });
    await expect(h.auth.authorizeRequest(id, h.editor, "edit_document", session)).rejects.toMatchObject({ status: 403 });
    await req(`/members/${h.editor.principalId}`, "PATCH", "owner", { role: null });
    expect((await req("/access", "GET", "editor")).status).toBe(403);
    await req(`/members/${h.editor.principalId}`, "PATCH", "owner", { role: "producer" });
    const ownerLease = await h.auth.openWriteSession(id, h.owner);
    await req(`/members/${h.owner.principalId}`, "PATCH", "owner", { role: "editor" });
    await h.auth.changeMembership(id, h.editor, h.owner.principalId, "producer");
    expect((await req("", "PATCH", "owner", { expectedProjectVersion: 1,
      clientMutationId: randomUUID(), title: "Old refused title", writeSessionId: ownerLease })).status).toBe(403);
    expect((await h.service.getProject(id, h.owner)).title).toBe(project.title);

  } finally { await h.db.close(); }
}, 90_000);
