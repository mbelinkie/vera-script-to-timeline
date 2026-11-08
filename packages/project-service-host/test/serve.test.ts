import { createHash, randomBytes, randomUUID } from "node:crypto";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { SqlClient } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { parseQaConfig, type QaConfig } from "../src/qa-config.js";
import { type QaPgPool } from "../src/pg-pool.js";
import { startQaServer, QaStartupRefusal, type QaRunningServer } from "../src/serve.js";
import { unusedLoopbackPort } from "./loopback-port.js";

const dirs: string[] = [];
const running: QaRunningServer[] = [];
const sha = "a".repeat(40);
const privateToken = randomBytes(32).toString("hex");
const subject = "synthetic-owner";
const privateUrl = "postgresql://qa_test_actor:hidden-password@127.0.0.1:5432/vera_stt_qa_fake";

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
  it("authenticates only trusted bearer identities through existing API and authorization service", async () => {
    const config = await setup();
    const h = infra();
    const server = await startQaServer(config, h);
    running.push(server);
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
