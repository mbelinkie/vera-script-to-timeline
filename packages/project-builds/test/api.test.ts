import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import {
  applyProjectAuthorizationMigration, ProjectAuthorizationService,
  type SqlPool, type SuiteIdentityPort,
} from "@vera/project-authorization";
import { applyProjectDocumentsMigration } from "@vera/project-documents";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectAgentAuthenticationService } from "../src/agent-auth.js";
import { createProjectBuildPairingApiHandler, MAX_PAIRING_API_BODY_BYTES } from "../src/api.js";
import { applyProjectBuildsMigration } from "../src/migration.js";
import { AGENT_PROTOCOL_VERSION, ProjectAgentPairingService } from "../src/pairing.js";

/* eslint-disable @typescript-eslint/require-await -- Test-only verified identity adapter and PGlite port. */
vi.setConfig({ testTimeout: 120_000 });
const databases: PGlite[] = [];
const identity: SuiteIdentityPort = {
  authenticate: async (request) => {
    const subject = request.headers.get("x-synthetic-suite-subject");
    if (!subject) throw new Error("unverified");
    return { issuer: "test.suite", subject };
  },
};
const BASE = "http://127.0.0.1/v1";
type Api = ReturnType<typeof createProjectBuildPairingApiHandler>;

function req(path: string, method: string, subject?: string, body?: unknown,
  extra?: Record<string, string>): Request {
  return new Request(BASE + path, {
    method,
    headers: {
      ...(subject ? { "x-synthetic-suite-subject": subject } : {}),
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
      ...extra,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
}

async function json(response: Response): Promise<Record<string, unknown>> {
  const parsed: unknown = await response.json();
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not object");
  return parsed as Record<string, unknown>;
}

async function setup() {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  await applyProjectBuildsMigration(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const users = ["owner", "editor", "viewer"] as const;
  const actors = await Promise.all(users.map(async (subject) =>
    await auth.resolveActor({ issuer: "test.suite", subject })));
  const project = randomUUID();
  const foreign = randomUUID();
  for (const id of [project, foreign]) {
    await db.query(
      "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
        "VALUES ($1,'Synthetic',$2,$3,$4)",
      [id, actors[0]!.principalId, randomUUID(), "sha256:" + "a".repeat(64)],
    );
    for (let i = 0; i < users.length; i++) {
      await db.query(
        "INSERT INTO vera_project_members(project_id,actor_id,role) VALUES($1,$2,$3)",
        [id, actors[i]!.principalId, users[i] === "owner" ? "producer" : users[i]],
      );
    }
  }
  const clock = { ms: Date.parse("2026-11-08T16:00:00Z") };
  const now = () => new Date(clock.ms);
  const pairing = new ProjectAgentPairingService(pool, auth, now);
  const agents = new ProjectAgentAuthenticationService(pool, auth, now);
  const api = createProjectBuildPairingApiHandler({ identity, authorization: auth, pairing, agents });
  return { db, api, auth, pairing, agents, project, foreign, clock };
}

function offerRequest(project: string, subject = "owner") {
  return req(`/projects/${project}/agent-pairing-offers`, "POST", subject,
    { agentLabel: "Local Mac", protocolVersion: AGENT_PROTOCOL_VERSION });
}
function consumeRequest(offerToken: unknown, projectId: string) {
  return req("/agent-pairing/consume", "POST", undefined, {
    projectId, offerToken, protocolVersion: AGENT_PROTOCOL_VERSION,
    capabilities: ["free_package_v1"],
  });
}
function agentHeaders(token: unknown, version = 1): Record<string, string> {
  return { authorization: `Bearer ${String(token)}`,
    "x-agent-credential-version": String(version) };
}

afterEach(async () => { for (const db of databases.splice(0)) await db.close(); });

describe("private pairing API identity boundary", () => {
  it("reauthenticates producer and rejects viewer/editor/header spoofing before body parse", async () => {
    const h = await setup();
    const unauthenticated = req(`/projects/${h.project}/agent-pairing-offers`, "POST",
      undefined, { agentLabel: "Mac", protocolVersion: AGENT_PROTOCOL_VERSION },
      { "x-claimed-role": "producer", "x-actor-id": "owner" });
    expect((await h.api(unauthenticated)).status).toBe(401);
    expect((await h.api(offerRequest(h.project, "editor"))).status).toBe(403);
    expect((await h.api(offerRequest(h.project, "viewer"))).status).toBe(403);
    const created = await h.api(offerRequest(h.project));
    expect(created.status).toBe(201);
    expect(created.headers.get("cache-control")).toBe("no-store");
    const payload = await json(created);
    expect(String(payload.offerToken)).toMatch(/^stto_[A-Za-z0-9_-]{43}$/u);
    const noAdapter: Api = createProjectBuildPairingApiHandler({
      authorization: h.auth, pairing: h.pairing, agents: h.agents,
    });
    expect((await noAdapter(offerRequest(h.project))).status).toBe(401);
    expect((await noAdapter(consumeRequest(payload.offerToken, h.project))).status).toBe(201);
    // A one-use token cannot be consumed again, including by another adapter.
    const repeat = await h.api(consumeRequest(payload.offerToken, h.project));
    expect(repeat.status).toBe(401);
    expect(JSON.stringify(await json(repeat))).not.toContain(String(payload.offerToken));
  });

  it("separates agent credential from suite user auth, reconnects and revokes via producer", async () => {
    const h = await setup();
    const offer = await json(await h.api(offerRequest(h.project)));
    const pairedResponse = await h.api(consumeRequest(offer.offerToken, h.project));
    expect(pairedResponse.status).toBe(201);
    const paired = await json(pairedResponse);
    const route = `/agent/projects/${h.project}`;
    const headers = agentHeaders(paired.agentToken);
    const jobPoll = await h.api(req(route + "/jobs", "GET", undefined, undefined, headers));
    expect(jobPoll.status).toBe(200);
    expect(await json(jobPoll)).toEqual({ jobs: [] });
    const heartbeat = await h.api(req(route + "/heartbeat", "POST", undefined, undefined, headers));
    expect(heartbeat.status).toBe(200);
    expect(await json(heartbeat)).toMatchObject({ authenticated: true, agentId: paired.agentId });
    const ready = await json(await h.api(req(`/projects/${h.project}/agent-readiness`, "GET", "viewer")));
    expect(ready).toMatchObject({ canBuild: false, nativeVerified: false });
    expect(JSON.stringify(ready)).not.toContain(String(paired.agentToken));
    expect((await h.api(req(`/agent/projects/${h.foreign}/jobs`, "GET", undefined,
      undefined, headers))).status).toBe(401);
    const forgedUserRequest = req(`/projects/${h.project}/agent-readiness`, "GET", undefined,
      undefined, { ...headers, "x-claimed-role": "producer" });
    expect((await h.api(forgedUserRequest)).status).toBe(401);
    expect((await h.api(req(`/projects/${h.project}/agents/${String(paired.agentId)}/rotate`,
      "POST", "editor"))).status).toBe(403);
    const rotated = await json(await h.api(req(`/projects/${h.project}/agents/${String(paired.agentId)}/rotate`,
      "POST", "owner")));
    expect(rotated.credentialVersion).toBe(2);
    expect((await h.api(req(route + "/heartbeat", "POST", undefined, undefined, headers))).status).toBe(401);
    expect((await h.api(req(route + "/heartbeat", "POST", undefined, undefined,
      agentHeaders(rotated.agentToken, 2)))).status).toBe(200);
    expect((await h.api(req(`/projects/${h.project}/agents/${String(paired.agentId)}`,
      "DELETE", "owner"))).status).toBe(200);
    expect((await h.api(req(route + "/jobs", "GET", undefined, undefined,
      agentHeaders(rotated.agentToken, 2)))).status).toBe(401);
  });

  it("fails closed on malformed/oversized input, query strings, unsupported protocol and stale roles", async () => {
    const h = await setup();
    const route = `/projects/${h.project}/agent-pairing-offers`;
    const badJson = new Request(BASE + route, {
      method: "POST", headers: { "content-type": "application/json", "x-synthetic-suite-subject": "owner" },
      body: "{malformed",
    });
    expect((await h.api(badJson)).status).toBe(400);
    expect((await h.api(req(route, "POST", "owner", {
      agentLabel: "Mac", protocolVersion: AGENT_PROTOCOL_VERSION, role: "producer",
    }))).status).toBe(400);
    expect((await h.api(req(route + "?role=producer", "POST", "owner", {
      agentLabel: "Mac", protocolVersion: AGENT_PROTOCOL_VERSION,
    }))).status).toBe(400);
    expect((await h.api(req(route, "POST", "owner", {
      agentLabel: "Mac", protocolVersion: "unsupported/agent",
    }))).status).toBe(400);
    const tooBig = req(route, "POST", "owner", {}, {
      "content-length": String(MAX_PAIRING_API_BODY_BYTES + 1),
    });
    expect((await h.api(tooBig)).status).toBe(400);
    const streamed = new Request(BASE + route, {
      method: "POST",
      headers: { "content-type": "application/json", "x-synthetic-suite-subject": "owner",
        "content-length": "1" },
      body: JSON.stringify({ agentLabel: "Mac", protocolVersion: AGENT_PROTOCOL_VERSION }) +
        " ".repeat(MAX_PAIRING_API_BODY_BYTES),
    });
    expect((await h.api(streamed)).status).toBe(400);
    expect((await h.db.query("SELECT * FROM stt_build_pairing_offers")).rows).toHaveLength(0);
    const offer = await json(await h.api(offerRequest(h.project)));
    await h.db.query("UPDATE vera_project_members SET active=false WHERE project_id=$1 " +
      "AND role='producer'", [h.project]);
    expect((await h.api(offerRequest(h.project))).status).toBe(403);
    expect((await h.api(req(`/projects/${h.project}/agent-readiness`, "GET", "owner"))).status).toBe(403);
    // An offer issued earlier also ceases to work once its Producer loses authority.
    const consumed = await h.api(consumeRequest(offer.offerToken, h.project));
    expect(consumed.status).toBe(401);
  });

  it("cancels an unconsumed offer and denies stale machine credential version", async () => {
    const h = await setup();
    const issued = await json(await h.api(offerRequest(h.project)));
    const canceled = await h.api(req(`/projects/${h.project}/agent-pairing-offers/${String(issued.offerId)}`,
      "DELETE", "owner"));
    expect(canceled.status).toBe(200);
    expect((await h.api(consumeRequest(issued.offerToken, h.project))).status).toBe(401);
    expect((await h.api(req(`/projects/${h.project}/agent-pairing-offers/${String(issued.offerId)}`,
      "DELETE", "owner"))).status).toBe(404);
    const second = await json(await h.api(offerRequest(h.project)));
    const paired = await json(await h.api(consumeRequest(second.offerToken, h.project)));
    const route = `/agent/projects/${h.project}/jobs`;
    expect((await h.api(req(route, "GET", undefined, undefined,
      agentHeaders(paired.agentToken, 2)))).status).toBe(401);
    expect((await h.api(req(route, "GET", undefined, undefined,
      { authorization: `Bearer ${String(paired.agentToken)}`, "x-agent-credential-version": "1e2" })))
      .status).toBe(401);
  });
});
