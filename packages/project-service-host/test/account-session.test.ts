import { randomUUID } from "node:crypto";
import { expect, it } from "vitest";
import { CollaborationClient, connectCollaborationSocket } from "@vera/project-collaboration";
import { accountFixture } from "./account-fixture.js";

it("isolates identities over real HTTP, rejects forgery/CSRF/cross-origin, and promptly revokes live sockets", async () => {
  const h = await accountFixture(); 
  const client = new CollaborationClient();
  let socket: Awaited<ReturnType<typeof connectCollaborationSocket>> | undefined;
  try {
    const route = `/authoring/projects/${h.projectId}`;
    for (const who of ["owner", "editor", "viewer"]) {
      const response = await h.request("/authoring/account", who);
      expect(await response.json()).toMatchObject({ actorId: h.actors[who]!.principalId });
      expect((await h.request(route + "/access", who)).status).toBe(200);
    }
    expect((await h.request(route, "outsider")).status).toBe(403);
    expect((await h.request(route, "owner", { headers: { cookie: "forged", authorization: h.bearers.owner!,
      "x-vera-session": h.qaToken } })).status).toBe(401);
    expect((await h.request(route, "owner", { headers: { "x-vera-csrf": "forged" } })).status).toBe(403);
    expect((await h.request(route, "owner", { headers: { origin: "https://evil.test" } })).status).toBe(403);
    expect((await h.request(route, "owner", { headers: { "sec-fetch-site": "cross-site" } })).status).toBe(403);
    expect((await h.request("/authoring/session", "owner", { method: "POST" })).status).toBe(404);
    expect((await fetch(h.origin + `/v1/projects/${h.projectId}`, { headers: { cookie: h.cookies.owner! } })).status).toBe(401);
    const lease = await h.request(route + "/write-session", "editor", { method: "POST",
      headers: { "content-type": "application/json" }, body: "{}" });
    const { writeSessionId } = await lease.json() as { writeSessionId: string };
    const before = await h.documents.getDocument(h.projectId, h.actors.owner!);
    expect((await h.request(route + "/document", "viewer", { method: "PUT",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expectedRevision: before.revision,
        clientMutationId: randomUUID(), document: before.document }) })).status).toBe(403);
    // Both role changes can happen between browser polls; the old lease must stay invalid.
    await h.auth.changeMembership(h.projectId, h.actors.owner!, h.actors.editor!.principalId, "viewer");
    await h.auth.changeMembership(h.projectId, h.actors.owner!, h.actors.editor!.principalId, "editor");
    expect((await h.request(route + "/document", "editor", { method: "PUT", headers: {
      "content-type": "application/json", "x-vera-write-session": writeSessionId },
      body: JSON.stringify({ expectedRevision: before.revision, clientMutationId: randomUUID(),
        document: before.document, writeSessionId }) })).status).toBe(403);
    
    // An account cookie cannot authenticate a raw WebSocket upgrade.
    await expect(connectCollaborationSocket(client, h.origin.replace("http:", "ws:") +
      `/v1/projects/${h.projectId}/collaboration`, { cookie: h.cookies.owner!, origin: "https://evil.test" }))
      .rejects.toThrow();
    socket = await connectCollaborationSocket(client, h.origin.replace("http:", "ws:") +
      `/v1/projects/${h.projectId}/collaboration`, { authorization: h.bearers.editor! });
    await expect.poll(() => client.canEdit).toBe(true); 
    const member = route + `/members/${h.actors.editor!.principalId}`;
    expect((await h.request(member, "owner", { method: "PATCH", headers: { "content-type": "application/json" },
      body: JSON.stringify({ role: "viewer" }) })).status).toBe(200);
    await expect.poll(() => client.roster.find((entry) => entry.actorId === h.actors.editor!.principalId)?.canEdit).toBe(false);
    expect((await h.documents.getDocument(h.projectId, h.actors.owner!)).revision).toBe(before.revision);
    expect((await h.request(member, "owner", { method: "PATCH", headers: { "content-type": "application/json" },
      body: JSON.stringify({ role: null }) })).status).toBe(200);
    expect(await socket.closed).toBe(4403);
    expect((await h.request(route, "editor")).status).toBe(403);
    expect((await h.request("/authoring/account/sign-out", "owner", { method: "POST" })).status).toBe(200);
    expect((await h.request(route, "owner")).status).toBe(401);
  } finally { socket?.close(); if (socket) await socket.closed; client.destroy(); await h.stop(); }
}, 90_000);

it("fails closed when account mode has no provider, without falling back to QA", async () => {
  const h = await accountFixture(true);
  try {
    expect((await h.request("/authoring/account")).status).toBe(503);
    expect((await h.request(`/authoring/projects/${h.projectId}`)).status).toBe(503);
    expect(h.host.authoringLaunchCode).toBeUndefined();
  } finally { await h.stop(); }
}, 90_000);
