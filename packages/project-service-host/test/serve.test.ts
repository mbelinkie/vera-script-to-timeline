import { createHash, randomBytes, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { SqlClient } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";
import { projectPrimarySequenceV2 } from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";

import { parseQaConfig, type QaConfig } from "../src/qa-config.js";
import { type QaPgPool } from "../src/pg-pool.js";
import { startQaServer, QaStartupRefusal, type QaRunningServer } from "../src/serve.js";
import { createAuthoringHandler } from "../src/authoring.js";
import { unusedLoopbackPort } from "./loopback-port.js";

const dirs: string[] = [];
const running: QaRunningServer[] = [];
const sha = "a".repeat(40);
const privateToken = randomBytes(32).toString("hex");
const subject = "synthetic-owner";
const privateUrl = "postgresql://qa_test_actor:hidden-password@127.0.0.1:5432/vera_stt_qa_fake";

const sourceFixture = JSON.parse(readFileSync(new URL(
  "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url,
), "utf8")) as { document: ScriptDocumentV2 };

async function setup(): Promise<QaConfig> {
  const dir = await mkdtemp(join(tmpdir(), "stt159-server-"));
  dirs.push(dir);
  const file = join(dir, "identity.json");
  await writeFile(file, JSON.stringify({ version: 1, credentials: [{
    tokenSha256: createHash("sha256").update(privateToken).digest("hex"),
    issuer: "urn:vera:stt:development-qa", subject,
  }] }), { mode: 0o600 });
  await chmod(file, 0o600);
  return parseQaConfig({ VERA_STT_MODE: "development-qa", VERA_STT_QA_HOST: "127.0.0.1",
    VERA_STT_QA_PORT: String(await unusedLoopbackPort()), VERA_STT_SOURCE_SHA: sha,
    VERA_STT_QA_IDENTITY_FILE: file, VERA_STT_QA_DATABASE_URL: privateUrl }, sha, "/work/fake-repo");
}

function infra() {
  const query = vi.fn((sql: string) => {
    if (/^(BEGIN|ROLLBACK|COMMIT)/u.test(sql)) return Promise.resolve({ rows: [] });
    if (sql.includes("INSERT INTO vera_identity_actors")) return Promise.resolve({ rows: [{
      id: randomUUID(), disabled_at: null,
    }] });
    if (sql.includes("SELECT m.role")) return Promise.resolve({ rows: [] });
    // Startup recovery (#384): nothing was left waiting to be written back.
    if (sql.includes("FROM stt_live_heads WHERE materialization='pending'")) return Promise.resolve({ rows: [] });
    return Promise.reject(new Error(`unexpected SQL: ${sql}`));
  });
  const release = vi.fn();
  const connect = vi.fn(() => Promise.resolve({ query, release } as unknown as SqlClient));
  const close = vi.fn(() => Promise.resolve());
  const pool: QaPgPool = { connect, close };
  const createPool = vi.fn((config: QaConfig, onIdleError: () => void) => {
    if (!config.databaseName || typeof onIdleError !== "function") throw new Error("bad pool inputs");
    return pool;
  });
  const migrate = vi.fn(() => Promise.resolve([]));
  return { createPool, migrate, query, connect, close };
}

afterEach(async () => {
  for (const server of running.splice(0)) await server.stop();
  for (const dir of dirs.splice(0)) await rm(dir, { recursive: true, force: true });
});

describe("development QA service bootstrap and shutdown", () => {
  it("protects visual commands and projections with the same browser session and exact envelopes", async () => {
    const origin = "http://127.0.0.1:38429";
    const projects = vi.fn(() => Promise.resolve(Response.json({ error: "unexpected_project_route" }, { status: 500 })));
    const host = createAuthoringHandler(origin, `Bearer ${privateToken}`, projects);
    const document = structuredClone(sourceFixture.document);
    const row = document.activeDraft.blocks.find((block) => block.type === "narration");
    if (!row?.primaryVisualSequence || row.tokens.length < 1) throw new Error("missing visual fixture row");
    const command = {
      kind: "add_visual_on_selection", blockId: row.id, slotId: randomUUID(), payloadId: randomUUID(),
      startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[0]!.id, visualType: "need_to_find",
    };
    const request = async (path: string, body: unknown, opts: {
      origin?: string; session?: string; site?: string; launch?: string;
    } = {}) => await host.handle(new Request(`${origin}/authoring/${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json", "X-VERA-Authoring": "1",
        "Sec-Fetch-Site": opts.site ?? "same-origin", Origin: opts.origin ?? origin,
        ...(opts.session ? { "X-VERA-Session": opts.session } : {}),
        ...(opts.launch ? { "X-VERA-Launch": opts.launch } : {}),
      },
      body: JSON.stringify(body),
    })) as Response;
    const session = await request("session", {}, { launch: host.launchCode });
    expect(session.status).toBe(200);
    const { sessionProof } = await session.json() as { sessionProof: string };
    const valid = { document, command, expectedSequenceVersion: row.primaryVisualSequence.version };
    for (const path of ["command", "projection"]) {
      const envelope = path === "command" ? valid : { document };
      expect((await request(path, envelope)).status).toBe(401);
      expect((await request(path, envelope, { session: "a".repeat(64) })).status).toBe(401);
      expect((await request(path, envelope, { origin: "http://127.0.0.1:10", session: sessionProof })).status).toBe(403);
      expect((await request(path, envelope, { site: "cross-site", session: sessionProof })).status).toBe(403);
    }
    const malformed = [
      { ...valid, expectedSequenceVersion: "0" },
      { ...valid, expectedSequenceVersion: -1 },
      { ...valid, expectedSequenceVersion: 1.2 },
      { document, command },
      { ...valid, splitProof: "f".repeat(64) },
      { ...valid, command: { ...command, visualType: "footage" } },
      { ...valid, command: { ...command, extra: true } },
      { ...valid, command: { ...command, kind: "arbitrary_visual" } },
      { ...valid, command: { kind: "change_visual_type", blockId: row.id,
        slotId: command.slotId, to: { type: "need_to_find", source: { secret: true } } } },
    ];
    for (const envelope of malformed) {
      const response = await request("command", envelope, { session: sessionProof });
      expect(response.status, JSON.stringify(envelope.command)).toBe(400);
    }
    const noDocument = await request("projection", { document: {} }, { session: sessionProof });
    expect(noDocument.status).toBe(400);
    const forgedOptions = await request("projection", { document, options: { secret: true } }, { session: sessionProof });
    expect(forgedOptions.status).toBe(400);
    const projection = await request("projection", { document }, { session: sessionProof });
    expect(projection.status).toBe(200);
    const projectionBody = await projection.json() as { projection: ReturnType<typeof projectPrimarySequenceV2> };
    expect(projectionBody.projection).toEqual(projectPrimarySequenceV2(document));
    expect(projectionBody.projection.rows.flatMap((item) => item.cards).map((card) => card.startTokenIndex)
      .filter((item): item is number => item !== null)).toEqual(
        [...projectionBody.projection.rows.flatMap((item) => item.cards).map((card) => card.startTokenIndex)
          .filter((item): item is number => item !== null)].sort((a, b) => a - b),
      );
    expect(JSON.stringify(projectionBody)).not.toContain(privateToken);
    const applied = await request("command", valid, { session: sessionProof });
    expect(applied.status).toBe(200);
    const outcome = await applied.json() as { ok: boolean; document: ScriptDocumentV2; diagnostics: Array<{ code: string }> };
    expect(outcome.ok, JSON.stringify(outcome.diagnostics)).toBe(true);
    const stale = await request("command", { ...valid, document: outcome.document }, { session: sessionProof });
    expect(stale.status).toBe(200);
    expect((await stale.json() as { diagnostics: Array<{ code: string }> }).diagnostics[0]?.code).toBe("SEQUENCE_VERSION_STALE");
    const changed = await request("command", { document: outcome.document,
      expectedSequenceVersion: row.primaryVisualSequence.version + 1,
      command: { kind: "change_visual_type", blockId: row.id, slotId: command.slotId,
        to: { type: "onscreen_placeholder" } },
    }, { session: sessionProof });
    expect(changed.status).toBe(200);
    const changedBody = await changed.json() as { ok: boolean; document: ScriptDocumentV2;
      diagnostics: Array<{ code: string }> };
    expect(changedBody.ok, JSON.stringify(changedBody.diagnostics)).toBe(true);
    const deleted = await request("command", { document: changedBody.document,
      expectedSequenceVersion: row.primaryVisualSequence.version + 2,
      command: { kind: "delete_visual", blockId: row.id, slotId: command.slotId },
    }, { session: sessionProof });
    expect(deleted.status).toBe(200);
    const deletedBody = await deleted.json() as { ok: boolean; diagnostics: Array<{ code: string }> };
    expect(deletedBody.ok, JSON.stringify(deletedBody.diagnostics)).toBe(true);
    expect(projects).not.toHaveBeenCalled();
  });
  it("authenticates only trusted bearer identities through existing API and authorization service", async () => {
    const config = await setup();
    const h = infra();
    const server = await startQaServer(config, h);
    running.push(server);
    // Startup itself reads the database once for live-collaboration recovery;
    // what matters below is that a forged request never reaches it.
    h.connect.mockClear();
    expect(server.server.address()).toMatchObject({ address: "127.0.0.1", port: config.port });
    const url = `http://127.0.0.1:${config.port}/v1/projects/${randomUUID()}/document`;
    const forged = await fetch(url, { headers: { "X-Test-Suite-Identity": subject,
      "X-Forwarded-User": subject, "X-Role": "producer" } });
    expect(forged.status).toBe(401);
    expect(h.connect).not.toHaveBeenCalled();
    const verified = await fetch(url, { headers: { Authorization: `Bearer ${privateToken}`,
      "X-Test-Suite-Identity": "different-user", "X-Role": "admin" } });
    expect(verified.status).toBe(403); // Valid actor but not a project member.
    expect(h.connect).toHaveBeenCalled();
    expect(h.query).toHaveBeenCalledWith(expect.stringContaining("INSERT INTO vera_identity_actors"),
      expect.arrayContaining(["urn:vera:stt:development-qa", subject]));
    const commentUrl = `http://127.0.0.1:${config.port}/v1/projects/${randomUUID()}/comments`;
    expect((await fetch(commentUrl, { headers: { "X-Test-Suite-Identity": subject } })).status).toBe(401);
    expect((await fetch(commentUrl, { headers: { Authorization: `Bearer ${privateToken}` } })).status).toBe(403);
    expect((await fetch(`${commentUrl}/operations`, { method: "POST", headers: {
      Authorization: `Bearer ${privateToken}`, "Content-Type": "application/json",
    }, body: "{}" })).status).toBe(400);
    const extrasUrl = `http://127.0.0.1:${config.port}/v1/projects/${randomUUID()}/document/extras-operations`;
    expect((await fetch(extrasUrl, { method: "POST", headers: {
      "Content-Type": "application/json", "X-Forwarded-User": "producer",
    }, body: "{}" })).status).toBe(401);
    expect((await fetch(extrasUrl, { method: "POST", headers: {
      Authorization: `Bearer ${privateToken}`, "Content-Type": "application/json",
    }, body: "{}" })).status).toBe(400); // Strict operation envelope; no backend bypass.
    const subtitleUrl = `http://127.0.0.1:${config.port}/v1/projects/${randomUUID()}` +
      `/subtitle-copies/${randomUUID()}`;
    expect((await fetch(subtitleUrl, { headers: { "X-Test-Suite-Identity": subject } })).status).toBe(401);
    expect((await fetch(subtitleUrl, { headers: { Authorization: `Bearer ${privateToken}` } })).status)
      .toBe(403); // Mounted route checks real project membership, no ambient Research bearer.
    expect((await fetch(subtitleUrl + "/revisions", {
      headers: { Authorization: `Bearer ${privateToken}` },
    })).status).toBe(403);
    expect((await fetch(subtitleUrl + "/derive", { method: "POST", headers: {
      Authorization: `Bearer ${privateToken}`, "Content-Type": "application/json",
    }, body: JSON.stringify({ expectedSourceDigest: "forged", clientMutationId: randomUUID(),
      expectedDocumentRevision: 0, expectedDocumentDigest: "forged", source: { secret: true } }) })).status)
      .toBe(400); // No caller-supplied source or Research credentials.
    expect((await fetch(subtitleUrl, { method: "DELETE", headers: {
      Authorization: `Bearer ${privateToken}` },
    })).status).toBe(404);
    const anonymousBuild = await fetch(`http://127.0.0.1:${config.port}/v1/projects/${randomUUID()}/builds`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    expect(anonymousBuild.status).toBe(401);
    const anonymousAgent = await fetch(`http://127.0.0.1:${config.port}/v1/agent/projects/${randomUUID()}/queue`);
    expect(anonymousAgent.status).toBe(401);
    await server.stop();
    await server.stop();
    expect(h.close).toHaveBeenCalledOnce();
    expect(server.server.listening).toBe(false);
  });

  it("routes the inspection request to scoped agent authentication without trusting its evidence kind", async () => {
    const config = await setup();
    const h = infra();
    const inspect = vi.fn(() => Promise.resolve(null));
    // A genuine adapter may be supplied by a trusted host, not by a request.
    // This QA host has none by default; neither route grants native authority.
    const server = await startQaServer(config, { ...h, evidenceInspector: { inspect } });
    running.push(server);
    const url = `http://127.0.0.1:${config.port}/v1/agent/projects/${randomUUID()}` +
      `/jobs/${randomUUID()}/leases/1/inspect`;
    const body = JSON.stringify({ stageKey: "verifying_timeline",
      receiptDigest: "sha256:" + "a".repeat(64), kind: "native_readback" });
    const anonymous = await fetch(url, { method: "POST", headers: {
      "Content-Type": "application/json",
    }, body });
    expect(anonymous.status).toBe(400);
    expect(inspect).not.toHaveBeenCalled();
    const forged = await fetch(url, { method: "POST", headers: {
      "Content-Type": "application/json", Authorization: `Bearer ${privateToken}`,
      "X-Agent-Credential-Version": "1",
    }, body: JSON.stringify({ stageKey: "verifying_timeline",
      receiptDigest: "sha256:" + "a".repeat(64) }) });
    expect(forged.status).toBe(401); // User token is not a paired agent token.
    expect(inspect).not.toHaveBeenCalled();
  });

  it("refuses missing identity before DB access and all unsafe bind/mode combinations", async () => {
    const config = await setup();
    const h = infra();
    await expect(startQaServer({ ...config, bindHost: "0.0.0.0" } as unknown as QaConfig, h))
      .rejects.toThrow(QaStartupRefusal);
    await expect(startQaServer({ ...config, deploymentMode: "hosted-release" } as unknown as QaConfig, h))
      .rejects.toThrow(QaStartupRefusal);
    await expect(startQaServer({ ...config, port: 0 }, h)).rejects.toThrow(QaStartupRefusal);
    await expect(startQaServer({ ...config, identityFile: `${config.identityFile}.missing` }, h))
      .rejects.toThrow(QaStartupRefusal);
    await expect(startQaServer({ ...config, authoringToken: randomBytes(32).toString("hex") }, h))
      .rejects.toThrow(QaStartupRefusal);
    expect(h.createPool).not.toHaveBeenCalled();
  });

  it("refuses failed migrations without binding and without revealing secrets", async () => {
    const config = await setup();
    const h = infra();
    h.migrate.mockRejectedValueOnce(new Error(`${privateToken} ${privateUrl}`));
    await expect(startQaServer(config, h)).rejects.toThrowError(new QaStartupRefusal());
    expect(h.close).toHaveBeenCalledOnce();
    const got = await fetch(`http://127.0.0.1:${config.port}/v1/projects`).catch(() => null);
    expect(got).toBeNull();
  });

  it("limits the browser identity to same-origin project and document routes", async () => {
    const config = await setup();
    const h = infra();
    const server = await startQaServer({ ...config, authoringToken: privateToken }, h);
    running.push(server);
    h.connect.mockClear();
    const origin = `http://127.0.0.1:${config.port}`;
    const route = `${origin}/authoring/projects/${randomUUID()}`;
    expect((await fetch(route)).status).toBe(403);
    expect((await fetch(route, { headers: {
      "X-VERA-Authoring": "1", "Sec-Fetch-Site": "same-origin", Origin: "http://127.0.0.1:2",
    } })).status).toBe(403);
    expect((await fetch(route, { headers: {
      "X-VERA-Authoring": "1", "Sec-Fetch-Site": "same-origin", Origin: origin,
    } })).status).toBe(401);
    const deniedSession = await fetch(`${origin}/authoring/session`, { method: "POST", headers: {
      "X-VERA-Authoring": "1", "Sec-Fetch-Site": "same-origin", Origin: origin,
      "X-VERA-Launch": randomBytes(32).toString("hex"),
    } });
    expect(deniedSession.status).toBe(401);
    expect(await deniedSession.json()).toEqual({ error: "authoring_browser_required" });
    expect((await fetch(route + "/builds", { headers: {
      "X-VERA-Authoring": "1", "Sec-Fetch-Site": "same-origin", Origin: origin,
    } })).status).toBe(404);
    expect(h.connect).not.toHaveBeenCalled();
  });

  it("refuses a competing listener and closes its database pool", async () => {
    const config = await setup();
    const first = infra();
    const app = await startQaServer(config, first);
    running.push(app);
    const other = infra();
    await expect(startQaServer(config, other)).rejects.toThrow(QaStartupRefusal);
    expect(other.close).toHaveBeenCalledOnce();
    expect(app.server.listening).toBe(true);
  });

  it("stops accepting requests and closes the pool on an idle database fault", async () => {
    const config = await setup();
    const h = infra();
    const app = await startQaServer(config, h);
    running.push(app);
    h.createPool.mock.calls[0]![1]();
    await vi.waitFor(() => { expect(h.close).toHaveBeenCalledOnce(); });
    expect(app.server.listening).toBe(false);
  });
});
