/* eslint-disable @typescript-eslint/require-await -- intentionally async mock ports. */
import { randomUUID } from "node:crypto";

import { ProjectAuthError, type ProjectAuthorizationService } from "@vera/project-authorization";
import { describe, expect, it, vi } from "vitest";

import { createProjectBuildHttpHandler } from "../src/http-builds.js";
import { BuildServiceError, type ProjectBuildSubmissionService } from "../src/submission.js";
import { type ProjectBuildStatusService } from "../src/status.js";

const projectId = randomUUID();
const jobId = randomUUID();
const machineToken = "sttag_" + "A".repeat(43);
const userToken = "private-user-fixture";
const principal = { principalKind: "user" as const, principalId: randomUUID() };

function harness() {
  const authenticateRequest = vi.fn(async (request: Request) => {
    if (request.headers.get("authorization") !== `Bearer ${userToken}`) {
      throw new ProjectAuthError("authentication_required", 401);
    }
    return principal;
  });
  const submit = vi.fn(async () => ({ jobId, status: "queued" }));
  const get = vi.fn(async () => ({ jobId, status: "queued" }));
  const cancel = vi.fn(async () => "cancelled");
  const pollQueued = vi.fn(async () => [jobId]);
  const claim = vi.fn(async () => ({ jobId, leaseEpoch: 1 }));
  const frozenForAgent = vi.fn(async () => ({ jobId, documentJson: "{}" }));
  const appendProgress = vi.fn(async () => "5");
  const handler = createProjectBuildHttpHandler({
    identity: { authenticate: async () => ({ issuer: "test", subject: "synthetic" }) },
    authorization: { authenticateRequest } as unknown as ProjectAuthorizationService,
    submissions: { submit } as unknown as ProjectBuildSubmissionService,
    status: { get, cancel, pollQueued, claim, frozenForAgent, appendProgress } as unknown as ProjectBuildStatusService,
  });
  function send(path: string, method = "GET", token = userToken, payload?: unknown,
    version = "1"): Promise<Response> {
    const body = payload === undefined ? undefined : JSON.stringify(payload);
    return handler(new Request("http://127.0.0.1:45383" + path, {
      method, headers: { Authorization: `Bearer ${token}`, "X-Agent-Credential-Version": version,
        ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body } : {}),
    }));
  }
  return { send, authenticateRequest, submit, get, cancel, pollQueued, claim, frozenForAgent, appendProgress };
}

describe("#382 private build transport boundary", () => {
  it("authenticates producer/editor user before accepting JSON, with no anonymous alternate path", async () => {
    const h = harness();
    const route = `/v1/projects/${projectId}/builds`;
    const denied = await h.send(route, "POST", "wrong", { hello: "bad" });
    expect(denied.status).toBe(401);
    expect(h.submit).not.toHaveBeenCalled();
    const ok = await h.send(route, "POST", userToken, { intent: "snapshot" });
    expect(ok.status).toBe(202);
    expect(h.submit).toHaveBeenCalledWith(projectId, principal, { intent: "snapshot" });
    const bad = await h.send(route, "POST", userToken, [1, 2, 3]);
    // Parsed input is validated by ProjectBuildSubmissionService, not an unsafe handler shortcut.
    expect(bad.status).toBe(202);
    expect(h.authenticateRequest).toHaveBeenCalledTimes(3);
  });

  it("isolates user read/cancel from agent endpoints and rejects URL queries", async () => {
    const h = harness();
    expect((await h.send(`/v1/projects/${projectId}/builds/${jobId}`)).status).toBe(200);
    expect(h.get).toHaveBeenCalledWith(projectId, principal, jobId);
    expect((await h.send(`/v1/projects/${projectId}/builds/${jobId}/cancel`, "POST")).status).toBe(200);
    expect(h.cancel).toHaveBeenCalledWith(projectId, principal, jobId);
    expect((await h.send(`/v1/projects/${projectId}/builds/${jobId}?spoof=1`)).status).toBe(400);
    expect((await h.send(`/v1/projects/${projectId}/builds/${jobId}`, "GET", machineToken)).status).toBe(401);
  });

  it("passes the exact scoped token and epoch only to independently authenticating agent methods", async () => {
    const h = harness();
    const root = `/v1/agent/projects/${projectId}`;
    expect((await h.send(root + "/queue", "GET", machineToken)).status).toBe(200);
    expect(h.pollQueued).toHaveBeenCalledWith({ projectId, agentToken: machineToken, credentialVersion: 1 });
    expect((await h.send(root + `/jobs/${jobId}/claim`, "POST", machineToken)).status).toBe(200);
    expect(h.claim).toHaveBeenCalledWith({ projectId, agentToken: machineToken, credentialVersion: 1 }, jobId);
    expect((await h.send(root + `/jobs/${jobId}/leases/1/frozen`, "GET", machineToken)).status).toBe(200);
    expect(h.frozenForAgent).toHaveBeenCalledWith({ projectId, agentToken: machineToken, credentialVersion: 1 }, jobId, 1);
    const progress = { status: "waiting_reconcile", stageKey: "compiling", receiptDigest: null, reasonCode: "uncertain" };
    expect((await h.send(root + `/jobs/${jobId}/leases/1/progress`, "POST", machineToken, progress)).status).toBe(202);
    expect(h.appendProgress).toHaveBeenCalledWith({ projectId, agentToken: machineToken, credentialVersion: 1 },
      jobId, { leaseEpoch: 1, ...progress });
    expect((await h.send(root + `/jobs/${jobId}/leases/0/frozen`, "GET", machineToken)).status).toBe(404);
    expect((await h.send(root + `/jobs/${jobId}/leases/1/inspect`, "POST", machineToken)).status).toBe(404);
    expect(h.authenticateRequest).not.toHaveBeenCalled();
  });

  it("does not echo SQL/tokens, and requires strict progress body", async () => {
    const h = harness();
    const route = `/v1/agent/projects/${projectId}/jobs/${jobId}/leases/1/progress`;
    const secret = "private-do-not-leak";
    h.appendProgress.mockRejectedValueOnce(new Error(secret));
    const body = { status: "running", stageKey: "compiling", receiptDigest: null, reasonCode: null };
    const failure = await h.send(route, "POST", machineToken, body);
    expect(failure.status).toBe(503);
    expect(await failure.text()).not.toContain(secret);
    expect((await h.send(route, "POST", machineToken, { ...body, arbitrary: "role" })).status).toBe(400);
    expect((await h.send(route, "POST", machineToken, { ...body, status: "verified_native" })).status).toBe(400);
    h.appendProgress.mockRejectedValueOnce(new BuildServiceError("invalid_build_request", 400));
    expect((await h.send(route, "POST", machineToken, body)).status).toBe(400);
  });
});
