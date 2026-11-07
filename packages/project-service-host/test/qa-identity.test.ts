import { createHash, randomBytes } from "node:crypto";
import { chmod, link, mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { loadQaIdentity, QaIdentityRefusal } from "../src/qa-identity.js";

const dirs: string[] = [];
const issuer = "urn:vera:stt:development-qa";
const token = randomBytes(32).toString("hex");
const digest = createHash("sha256").update(token).digest("hex");
const actor = { tokenSha256: digest, issuer, subject: "qa-producer" };
const config = { version: 1, credentials: [actor] };
const url = "http://127.0.0.1:15555/v1/projects";

async function fixture(value: unknown = config): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "stt-159-qa-identity-"));
  dirs.push(dir);
  const path = join(dir, "private.json");
  await writeFile(path, JSON.stringify(value), { mode: 0o600 });
  await chmod(path, 0o600);
  return path;
}
afterEach(async () => { for (const dir of dirs.splice(0)) await rm(dir, { recursive: true, force: true }); });

describe("trusted local QA identity verifier", () => {
  it("uses only a matching high-entropy bearer token, not claimed actor, role or proxy headers", async () => {
    const provider = await loadQaIdentity(await fixture());
    const request = (authorization?: string, other: Record<string, string> = {}) =>
      new Request(url, { headers: { ...(authorization ? { authorization } : {}), ...other } });
    await expect(provider.authenticate(request(`Bearer ${token}`, {
      "X-Test-Suite-Identity": "admin", "X-Forwarded-User": "admin",
      "X-Actor-Id": "admin", "X-Role": "producer",
    }))).resolves.toEqual({ issuer, subject: "qa-producer" });
    for (const bad of [undefined, "", "Bearer short", `Basic ${token}`,
      `Bearer ${randomBytes(32).toString("hex")}`, `Bearer ${token}, Bearer ${token}`]) {
      await expect(provider.authenticate(request(bad, { "X-Test-Suite-Identity": "qa-producer" })))
        .rejects.toMatchObject({ status: 401, code: "authentication_required" });
    }
  });

  it("refuses absent, symlinked, hardlinked and incorrectly permissioned files", async () => {
    const path = await fixture();
    await expect(loadQaIdentity(`${path}-missing`)).rejects.toThrow(QaIdentityRefusal);
    const linked = `${path}.symlink`;
    await symlink(path, linked);
    await expect(loadQaIdentity(linked)).rejects.toThrow(QaIdentityRefusal);
    const hard = `${path}.hardlink`;
    await link(path, hard);
    await expect(loadQaIdentity(path)).rejects.toThrow(QaIdentityRefusal);
    await rm(hard);
    await chmod(path, 0o644);
    await expect(loadQaIdentity(path)).rejects.toThrow(QaIdentityRefusal);
    await chmod(path, 0o400);
    await expect(loadQaIdentity(path)).rejects.toThrow(QaIdentityRefusal);
  });

  it("refuses a symlinked parent that redirects a private-looking path into the checkout", async () => {
    const initial = await fixture();
    const dir = initial.slice(0, initial.lastIndexOf("/"));
    const repo = join(dir, "checkout");
    await mkdir(repo);
    await writeFile(join(repo, "identity.json"), JSON.stringify(config), { mode: 0o600 });
    const alias = join(dir, "outside-alias");
    await symlink(repo, alias);
    await expect(loadQaIdentity(join(alias, "identity.json"), repo)).rejects.toThrow(QaIdentityRefusal);
  });

  it("refuses secrets in the main repository even when the worktree is elsewhere", async () => {
    const initial = await fixture();
    const dir = initial.slice(0, initial.lastIndexOf("/"));
    const mainRepo = join(dir, "main-repository");
    const worktree = join(dir, "external-worktree");
    await mkdir(mainRepo);
    await mkdir(worktree);
    const file = join(mainRepo, "qa-identity.json");
    await writeFile(file, JSON.stringify(config), { mode: 0o600 });
    await expect(loadQaIdentity(file, [worktree, mainRepo])).rejects.toThrow(QaIdentityRefusal);
  });

  it.each([
    ["empty", { version: 1, credentials: [] }],
    ["unknown root field", { ...config, plaintextToken: token }],
    ["raw token", { version: 1, credentials: [{ ...actor, token }] }],
    ["digest missing", { version: 1, credentials: [{ issuer, subject: "qa-producer" }] }],
    ["short digest", { version: 1, credentials: [{ ...actor, tokenSha256: "bad" }] }],
    ["duplicate digest", { version: 1, credentials: [actor, { ...actor, subject: "other" }] }],
    ["duplicate actor", { version: 1, credentials: [actor, { ...actor, tokenSha256: "a".repeat(64) }] }],
    ["wrong issuer", { version: 1, credentials: [{ ...actor, issuer: "trusted-admin" }] }],
    ["unexpected version", { ...config, version: 2 }],
  ])("refuses %s without reproducing supplied values", async (_name, data) => {
    const path = await fixture(data);
    await expect(loadQaIdentity(path)).rejects.toThrowError(new QaIdentityRefusal());
  });

  it("refuses oversize file and doesn't echo private text in errors", async () => {
    const path = await fixture();
    await writeFile(path, `private-${token}-` + "x".repeat(70_000), { mode: 0o600 });
    await expect(loadQaIdentity(path)).rejects.toThrowError(new QaIdentityRefusal());
    try { await loadQaIdentity(path); } catch (error) {
      expect(String(error)).not.toContain(token);
      expect(String(error)).not.toContain(path);
    }
  });

  it("refuses an obviously weak 64-hex credential even if its hash was configured", async () => {
    const weak = "0".repeat(64);
    const file = await fixture({ version: 1, credentials: [{ ...actor,
      tokenSha256: createHash("sha256").update(weak).digest("hex") }] });
    const identity = await loadQaIdentity(file);
    await expect(identity.authenticate(new Request(url, {
      headers: { Authorization: `Bearer ${weak}` },
    }))).rejects.toMatchObject({ status: 401, code: "authentication_required" });
  });
});
