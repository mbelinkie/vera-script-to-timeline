/**
 * Opt-in synthetic-only local acceptance harness. Unlike the offline service
 * unit tests, this starts separate CLI host processes and exercises real HTTP,
 * actual PostgreSQL and the real private pg_dump/pg_restore scripts.
 *
 * Run ONLY with newly provisioned empty, owner-scoped QA source and restore
 * databases. No database creation, cleanup, admin route or automatic teardown.
 */
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import {
  chmodSync, copyFileSync, createWriteStream, mkdirSync, openSync, readFileSync,
  readSync, realpathSync, closeSync, rmSync, writeSync,
} from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { ProjectAuthorizationService } from "@vera/project-authorization";
import type { SqlClient } from "@vera/project-authorization";

import { loadQaIdentity } from "./qa-identity.js";
import { assertQaDatabaseTarget } from "./migrate.js";
import { createQaPgPool } from "./pg-pool.js";
import { parseQaConfig, type QaConfig } from "./qa-config.js";
import {
  assertCompleteCases, QaSmokeRefusal, requireEqual, requireStatus, requireTrue,
} from "./qa-smoke-checks.js";

const ROOT = fileURLToPath(new URL("../../../", import.meta.url));
const ISSUER = "urn:vera:stt:development-qa";
const TOKEN = /^[0-9a-f]{64}$/u;
const SHA = /^[0-9a-f]{40}$/u;
const RESTORE = /^vera_stt_qa_restore_[a-z0-9][a-z0-9_]{2,40}$/u;
// Only static labels from this source are ever emitted on failure.
let stage = "initial-preflight";
const sleep = async (ms: number): Promise<void> => {
  await new Promise<void>((resolve) => { setTimeout(resolve, ms); });
};

interface Tokens { readonly producer: string; readonly editor: string; readonly viewer: string }
interface HttpResult { readonly status: number; readonly body: Record<string, unknown> }
type Snapshot = Record<string, unknown>;

function safeObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new QaSmokeRefusal();
  return value as Record<string, unknown>;
}

function secretTokens(env: NodeJS.ProcessEnv): Tokens {
  const producer = env.VERA_STT_QA_SMOKE_PRODUCER_TOKEN;
  const editor = env.VERA_STT_QA_SMOKE_EDITOR_TOKEN;
  const viewer = env.VERA_STT_QA_SMOKE_VIEWER_TOKEN;
  if (![producer, editor, viewer].every((value) => TOKEN.test(value ?? "")) ||
      new Set([producer, editor, viewer]).size !== 3) throw new QaSmokeRefusal();
  return { producer: producer!, editor: editor!, viewer: viewer! };
}

async function preflightEmpty(config: QaConfig): Promise<void> {
  const pool = createQaPgPool(config);
  try {
    const db = await pool.connect();
    try {
      await assertQaDatabaseTarget(db, config);
      const rows = await db.query<{ owner: string; objects: number; clients: number }>(
        "SELECT pg_get_userbyid(d.datdba) AS owner, " +
        "(SELECT count(*)::int FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid " +
        "WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') " +
        "AND n.nspname NOT LIKE 'pg_temp_%' AND n.nspname NOT LIKE 'pg_toast_temp_%') AS objects, " +
        "(SELECT count(*)::int FROM pg_stat_activity " +
        "WHERE datname=current_database() AND pid<>pg_backend_pid()) AS clients " +
        "FROM pg_database d WHERE d.datname=current_database()",
      );
      const state = rows.rows[0];
      requireTrue(rows.rows.length === 1 && state?.owner === config.databaseUser &&
        state.objects === 0 && state.clients === 0);
    } finally {
      db.release?.();
    }
  } finally {
    await pool.close();
  }
}

function hostEnvironment(env: NodeJS.ProcessEnv, config: QaConfig): NodeJS.ProcessEnv {
  return {
    ...env, VERA_STT_MODE: "development-qa", VERA_STT_QA_HOST: "127.0.0.1",
    VERA_STT_QA_PORT: String(config.port), VERA_STT_QA_DATABASE_URL: config.databaseUrl,
    VERA_STT_SOURCE_SHA: config.sourceSha, VERA_STT_QA_IDENTITY_FILE: config.identityFile,
  };
}

async function http(config: QaConfig, token: string, path: string, method = "GET",
  data?: unknown, extraHeaders: Record<string, string> = {}): Promise<HttpResult> {
  try {
    const response = await fetch("http://127.0.0.1:" + config.port + "/v1/projects" + path, {
      method, signal: AbortSignal.timeout(7_000),
      headers: {
        Authorization: "Bearer " + token,
        ...(data === undefined ? {} : { "Content-Type": "application/json" }),
        ...extraHeaders,
      },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    });
    requireTrue(response.headers.get("cache-control") === "no-store");
    return { status: response.status, body: safeObject(await response.json() as unknown) };
  } catch {
    throw new QaSmokeRefusal();
  }
}

async function checkedHttp(config: QaConfig, token: string, path: string,
  status: number, method = "GET", data?: unknown,
  extraHeaders?: Record<string, string>): Promise<Record<string, unknown>> {
  const result = await http(config, token, path, method, data, extraHeaders);
  requireStatus(result.status, status);
  return result.body;
}

async function agentHttp(config: QaConfig, token: string, path: string,
  status: number, method = "GET", data?: unknown): Promise<Record<string, unknown>> {
  try {
    const response = await fetch(`http://127.0.0.1:${config.port}${path}`, {
      method, signal: AbortSignal.timeout(7_000),
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Agent-Credential-Version": "1",
        ...(data === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    });
    requireStatus(response.status, status);
    requireTrue(response.headers.get("Cache-Control") === "no-store");
    return safeObject(await response.json() as unknown);
  } catch { throw new QaSmokeRefusal(); }
}

async function launch(config: QaConfig, env: NodeJS.ProcessEnv, token: string): Promise<ChildProcess> {
  // Start the real operator CLI, not startQaServer's injectable test seam.
  const child = spawn(join(ROOT, "node_modules/.bin/tsx"),
    ["packages/project-service-host/src/serve.ts"], {
      cwd: ROOT, env: hostEnvironment(env, config), stdio: "ignore",
    });
  try {
    const start = Date.now();
    while (Date.now() - start < 20_000) {
      if (child.exitCode !== null || child.signalCode !== null) throw new QaSmokeRefusal();
      try {
        const result = await http(config, token, "/" + randomUUID());
        if (result.status === 403) {
          await sleep(250);
          requireTrue(child.exitCode === null && child.signalCode === null);
          return child;
        }
      } catch { /* An unopened loopback socket is expected until startup. */ }
      await sleep(150);
    }
    throw new QaSmokeRefusal();
  } catch {
    await stop(child).catch(() => undefined);
    throw new QaSmokeRefusal();
  }
}

async function stop(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new QaSmokeRefusal());
    }, 10_000);
    child.once("exit", () => { clearTimeout(timer); resolve(); });
    child.once("error", () => { clearTimeout(timer); reject(new QaSmokeRefusal()); });
    child.kill("SIGTERM");
  });
}

async function withDb<T>(config: QaConfig, work: (db: SqlClient) => Promise<T>): Promise<T> {
  const pool = createQaPgPool(config);
  try {
    const db = await pool.connect();
    try { return await work(db); }
    finally { db.release?.(); }
  } finally {
    await pool.close();
  }
}

/** Stable DB readback; IDs and exact JSON are compared but never printed. */
async function snapshot(config: QaConfig, projectId: string): Promise<Snapshot> {
  return await withDb(config, async (db) => {
    const query = async (sql: string): Promise<readonly Record<string, unknown>[]> =>
      (await db.query<Record<string, unknown>>(sql, [projectId])).rows;
    return {
      project: await query("SELECT id,title,project_version,created_by FROM stt_projects WHERE id=$1"),
      head: await query("SELECT document_id,revision,content_digest,document_json " +
        "FROM stt_document_heads WHERE project_id=$1"),
      revisions: await query("SELECT revision,expected_revision,document_id,content_digest,client_mutation_id " +
        "FROM stt_document_revisions WHERE project_id=$1 ORDER BY revision"),
      settings: await query("SELECT settings_id,settings_revision,content_digest,settings_json " +
        "FROM stt_project_settings WHERE project_id=$1"),
      settingsHistory: await query("SELECT settings_revision,content_digest " +
        "FROM stt_settings_revisions WHERE project_id=$1 ORDER BY settings_revision"),
      memberships: await query("SELECT a.subject,m.role,m.active,m.version " +
        "FROM vera_project_members m JOIN vera_identity_actors a ON a.id=m.actor_id " +
        "WHERE m.project_id=$1 ORDER BY a.subject"),
      sessions: await query("SELECT a.subject,s.id,s.membership_version,(s.revoked_at IS NOT NULL) AS revoked " +
        "FROM vera_project_write_sessions s JOIN vera_identity_actors a ON a.id=s.actor_id " +
        "WHERE s.project_id=$1 ORDER BY s.id"),
      audit: await query("SELECT a.change_kind,a.old_role,a.new_role,a.membership_version,a.target_actor_id " +
        "FROM vera_project_membership_audit a WHERE a.project_id=$1 ORDER BY a.occurred_at,a.id"),
      builds: await query("SELECT id,target_id,build_class,mode,expected_revision,document_digest," +
        "settings_digest,snapshot_digest FROM stt_build_submissions WHERE project_id=$1 ORDER BY id"),
      dispatches: await query("SELECT job_id,status,lease_epoch,reason_code,assigned_agent_id " +
        "FROM stt_build_dispatches WHERE project_id=$1 ORDER BY job_id"),
      buildEvents: await query("SELECT id,job_id,lease_epoch,status,stage_key,evidence_kind,reason_code " +
        "FROM stt_build_events WHERE project_id=$1 ORDER BY id"),
      selectedPins: await query("SELECT job_id,source_id,source_revision,source_digest " +
        "FROM stt_build_source_pins WHERE project_id=$1 ORDER BY job_id,source_id"),
      agents: await query("SELECT id,credential_version,protocol_version,revoked_at IS NOT NULL AS revoked " +
        "FROM stt_project_build_agents WHERE project_id=$1 ORDER BY id"),
      offers: await query("SELECT id,consumed_at IS NOT NULL AS consumed " +
        "FROM stt_build_pairing_offers WHERE project_id=$1 ORDER BY id"),
      migrations: (await db.query<Record<string, unknown>>(
        "SELECT migration_name,schema_version,encode(checksum,'hex') AS checksum " +
        "FROM vera_schema_migrations ORDER BY migration_name")).rows,
      postgres: (await db.query<{ server_version: string }>("SHOW server_version")).rows[0]?.server_version,
    };
  });
}

async function provisionAndSession(config: QaConfig, projectId: string): Promise<string> {
  const pool = createQaPgPool(config);
  try {
    const auth = new ProjectAuthorizationService(pool);
    const producer = await auth.resolveActor({ issuer: ISSUER, subject: "synthetic-producer" });
    const editor = await auth.resolveActor({ issuer: ISSUER, subject: "synthetic-editor" });
    const viewer = await auth.resolveActor({ issuer: ISSUER, subject: "synthetic-viewer" });
    await auth.changeMembership(projectId, producer, editor.principalId, "editor");
    await auth.changeMembership(projectId, producer, viewer.principalId, "viewer");
    return await auth.openWriteSession(projectId, editor);
  } finally {
    await pool.close();
  }
}

async function revoke(config: QaConfig, projectId: string, sessionId: string): Promise<void> {
  const pool = createQaPgPool(config);
  try {
    const auth = new ProjectAuthorizationService(pool);
    const producer = await auth.resolveActor({ issuer: ISSUER, subject: "synthetic-producer" });
    const editor = await auth.resolveActor({ issuer: ISSUER, subject: "synthetic-editor" });
    await auth.changeMembership(projectId, producer, editor.principalId, null);
    await deniedSession(auth, projectId, editor.principalId, sessionId);
  } finally {
    await pool.close();
  }
}

async function deniedSession(auth: ProjectAuthorizationService, projectId: string,
  actorId: string, sessionId: string): Promise<void> {
  try {
    await auth.authorizeRequest(projectId,
      { principalKind: "user", principalId: actorId }, "edit_document", sessionId);
  } catch (error) {
    if (error && typeof error === "object" && "status" in error && error.status === 403) return;
  }
  throw new QaSmokeRefusal();
}

async function verifySessionDenied(config: QaConfig, projectId: string, sessionId: string): Promise<void> {
  await withDb(config, async (db) => {
    const actor = await db.query<{ id: string }>(
      "SELECT id FROM vera_identity_actors WHERE issuer=$1 AND subject=$2",
      [ISSUER, "synthetic-editor"],
    );
    requireTrue(actor.rows.length === 1);
    const pool = createQaPgPool(config);
    try {
      await deniedSession(new ProjectAuthorizationService(pool), projectId, actor.rows[0]!.id, sessionId);
    } finally { await pool.close(); }
  });
}

function verifySnapshot(value: Snapshot): void {
  const rows = (key: string): Record<string, unknown>[] => {
    const result = value[key];
    if (!Array.isArray(result)) throw new QaSmokeRefusal();
    return result as Record<string, unknown>[];
  };
  const memberships = rows("memberships");
  requireTrue(rows("project").length === 1 && rows("head").length === 1 &&
    rows("revisions").length === 3 && rows("settings").length === 1 &&
    rows("settingsHistory").length === 2 && rows("audit").length === 4 &&
    rows("sessions").length === 1 && rows("migrations").length === 4);
  requireTrue(Number(rows("head")[0]?.revision) === 2 &&
    Number(rows("settings")[0]?.settings_revision) === 2 &&
    Number(rows("project")[0]?.project_version) === 2);
  requireEqual(memberships.map((row) => [row.subject, row.role, row.active]),
    [["synthetic-editor", "editor", false], ["synthetic-producer", "producer", true],
      ["synthetic-viewer", "viewer", true]]);
  requireTrue(rows("sessions")[0]?.revoked === true &&
    rows("audit").some((row) => row.change_kind === "revoke"));
  requireTrue(rows("builds").length === 1 && rows("dispatches").length === 1 &&
    rows("buildEvents").length === 4 && rows("selectedPins").length === 0 &&
    rows("agents").length === 1 && rows("offers").length === 1 &&
    rows("dispatches")[0]?.status === "waiting_reconcile" &&
    Number(rows("dispatches")[0]?.lease_epoch) === 1 &&
    rows("agents")[0]?.revoked === false && rows("offers")[0]?.consumed === true &&
    rows("buildEvents").every((event) => event.evidence_kind === "untrusted_report"));
  requireTrue(typeof value.postgres === "string" && value.postgres.length > 0);
}

async function readback(config: QaConfig, tokens: Tokens, projectId: string,
  expectedDocument: Record<string, unknown>, expectedSettings: Record<string, unknown>,
  previousMutation: Record<string, unknown>, sessionId: string): Promise<void> {
  const p = "/" + projectId;
  const head = await checkedHttp(config, tokens.producer, p + "/document", 200);
  requireEqual(head.document, expectedDocument);
  requireTrue(head.revision === 2 && typeof head.digest === "string");
  const viewer = await checkedHttp(config, tokens.viewer, p + "/document", 200);
  requireEqual(viewer, head);
  const settings = await checkedHttp(config, tokens.viewer, p + "/settings", 200);
  requireEqual(settings.settings, expectedSettings);
  requireTrue(settings.settingsRevision === 2);
  const project = await checkedHttp(config, tokens.producer, p, 200);
  requireTrue(safeObject(project.project).projectVersion === 2 &&
    safeObject(project.project).title === "QA renamed");
  await checkedHttp(config, tokens.editor, p + "/document", 403);
  await checkedHttp(config, tokens.editor, p + "/document", 403, "PUT", previousMutation);
  await checkedHttp(config, tokens.editor, p + "/document", 403, "PUT",
    { expectedRevision: 2, clientMutationId: randomUUID(), document: expectedDocument, writeSessionId: sessionId });
  await checkedHttp(config, tokens.viewer, p + "/document", 403, "PUT",
    { expectedRevision: 2, clientMutationId: randomUUID(), document: expectedDocument });
  await checkedHttp(config, tokens.viewer, p, 403, "PATCH",
    { expectedProjectVersion: 2, clientMutationId: randomUUID(), title: "No" });
  await checkedHttp(config, tokens.editor, p, 403, "GET", undefined,
    { "X-Test-Suite-Identity": "synthetic-producer", "X-User-Role": "producer" });
  await verifySessionDenied(config, projectId, sessionId);
}

function runOperator(script: string, env: NodeJS.ProcessEnv, expectedSuccess: boolean): void {
  const result = spawnSync("bash", [join(ROOT, "scripts", script)], {
    cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"], timeout: 120_000,
    maxBuffer: 1024 * 1024,
  });
  requireTrue(!result.error && (expectedSuccess ? result.status === 0 : result.status !== 0));
}

function tamperCopy(dir: string): string {
  const other = dir + "-tampered-" + randomUUID();
  mkdirSync(other, { mode: 0o700 });
  for (const filename of ["qa.dump", "manifest.json"]) {
    const destination = join(other, filename);
    copyFileSync(join(dir, filename), destination);
    chmodSync(destination, 0o600);
  }
  const fd = openSync(join(other, "qa.dump"), "r+");
  try {
    const bytes = Buffer.alloc(1);
    requireTrue(readSync(fd, bytes, 0, 1, 32) === 1);
    bytes[0] = bytes[0]! ^ 1;
    writeSync(fd, bytes, 0, 1, 32);
  } finally { closeSync(fd); }
  return other; // Intentionally private; do not try to clean up other user files.
}

async function run(): Promise<void> {
  const env = process.env;
  stage = "opt-in-and-checkout";
  requireTrue(env.VERA_STT_QA_SMOKE === "synthetic-disposable");
  const rev = spawnSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" });
  const status = spawnSync("git", ["status", "--porcelain", "--untracked-files=normal"],
    { cwd: ROOT, encoding: "utf8" });
  requireTrue(rev.status === 0 && status.status === 0 && status.stdout.trim() === "" &&
    SHA.test(rev.stdout.trim()) && rev.stdout.trim() === env.VERA_STT_SOURCE_SHA);
  stage = "config";
  const source = parseQaConfig(env, rev.stdout.trim(), ROOT);
  const target = parseQaConfig({ ...env, VERA_STT_QA_DATABASE_URL: env.VERA_STT_QA_RESTORE_DATABASE_URL },
    rev.stdout.trim(), ROOT);
  requireTrue(RESTORE.test(target.databaseName) && source.databaseName !== target.databaseName);
  stage = "tokens-and-identity";
  const tokens = secretTokens(env);
  const identity = await loadQaIdentity(source.identityFile, ROOT);
  for (const role of ["producer", "editor", "viewer"] as const) {
    const verified = await identity.authenticate(new Request("http://127.0.0.1", {
      headers: { authorization: "Bearer " + tokens[role] },
    }));
    requireEqual(verified, { issuer: ISSUER, subject: "synthetic-" + role });
  }
  stage = "archive-path";
  const archiveDir = env.VERA_STT_QA_ARCHIVE_DIR;
  requireTrue(typeof archiveDir === "string" && archiveDir.startsWith("/") &&
    !archiveDir.includes("\0") && !archiveDir.startsWith(ROOT + "/") &&
    relative(realpathSync(join(ROOT, "../../")), archiveDir).startsWith("../"));
  stage = "source-database-preflight";
  await preflightEmpty(source);
  stage = "restore-database-preflight";
  await preflightEmpty(target);
  const cases: string[] = [];
  let running: ChildProcess | undefined;
  const projectId = randomUUID();
  const initialDocument: Record<string, unknown> = {
    schemaVersion: "script-document/v2", id: randomUUID(), projectId, title: "First draft",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 4, liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
  const initialSettings: Record<string, unknown> = {
    schemaVersion: "authoring-project-settings/v1", id: randomUUID(), projectId,
    version: 1, settingsHash: "sha256:" + "b".repeat(64),
  };
  const updatedSettings = { ...initialSettings, version: 2, settingsHash: "sha256:" + "c".repeat(64) };
  const document1 = { ...initialDocument, title: "Producer revision" };
  const document2 = { ...initialDocument, title: "Editor revision" };
  const creation = { projectId, title: "Synthetic QA", clientRequestId: randomUUID(),
    document: initialDocument, settings: initialSettings };
  const previousMutation = { expectedRevision: 1, clientMutationId: randomUUID(),
    document: document2 };
  let sessionId: string;
  try {
    stage = "initial-host";
    running = await launch(source, env, tokens.producer);
    await checkedHttp(source, randomBytes(32).toString("hex"), "", 401, "POST", creation);
    await checkedHttp(source, tokens.viewer, "/" + projectId, 403, "GET", undefined,
      { "X-Test-Suite-Identity": "synthetic-producer", "X-User-Role": "producer" });
    cases.push("loopback-auth");
    const created = await checkedHttp(source, tokens.producer, "", 201, "POST", creation);
    requireTrue(created.documentRevision === 0 && created.duplicateDelivery === false);
    const replayed = await checkedHttp(source, tokens.producer, "", 200, "POST", creation);
    requireTrue(replayed.duplicateDelivery === true && replayed.documentDigest === created.documentDigest);
    cases.push("create-replay");
    stage = "mutations-and-provisioning";
    const producerMutation = { expectedRevision: 0, clientMutationId: randomUUID(), document: document1 };
    const first = await checkedHttp(source, tokens.producer, "/" + projectId + "/document",
      200, "PUT", producerMutation);
    requireTrue(first.revision === 1 && first.duplicateDelivery === false);
    requireTrue((await checkedHttp(source, tokens.producer, "/" + projectId + "/document",
      200, "PUT", producerMutation)).duplicateDelivery === true);
    sessionId = await provisionAndSession(source, projectId);
    const second = await checkedHttp(source, tokens.editor, "/" + projectId + "/document",
      200, "PUT", { ...previousMutation, writeSessionId: sessionId });
    requireTrue(second.revision === 2 && second.duplicateDelivery === false);
    requireTrue((await checkedHttp(source, tokens.editor, "/" + projectId + "/document",
      200, "PUT", { ...previousMutation, writeSessionId: sessionId })).duplicateDelivery === true);
    const stale = await checkedHttp(source, tokens.editor, "/" + projectId + "/document", 409,
      "PUT", { expectedRevision: 1, clientMutationId: randomUUID(), document: document2 });
    requireTrue(stale.currentRevision === 2);
    cases.push("document-cas-replay");
    await checkedHttp(source, tokens.viewer, "/" + projectId + "/document", 200);
    await checkedHttp(source, tokens.viewer, "/" + projectId + "/document", 403, "PUT",
      { expectedRevision: 2, clientMutationId: randomUUID(), document: document2 });
    await checkedHttp(source, tokens.viewer, "/" + projectId + "/settings", 403, "PUT",
      { expectedSettingsRevision: 1, clientMutationId: randomUUID(), settings: updatedSettings });
    cases.push("viewer-read-refusal");
    await checkedHttp(source, tokens.editor, "/" + projectId + "/settings", 403, "PUT",
      { expectedSettingsRevision: 1, clientMutationId: randomUUID(), settings: updatedSettings });
    await checkedHttp(source, tokens.editor, "/" + projectId, 403, "PATCH",
      { expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "No" });
    cases.push("editor-write-producer-refusal");
    stage = "producer-settings";
    requireTrue((await checkedHttp(source, tokens.producer, "/" + projectId + "/settings", 200, "PUT",
      { expectedSettingsRevision: 1, clientMutationId: randomUUID(), settings: updatedSettings })).revision === 2);
    requireTrue(safeObject((await checkedHttp(source, tokens.producer, "/" + projectId, 200, "PATCH",
      { expectedProjectVersion: 1, clientMutationId: randomUUID(), title: "QA renamed" })).project).projectVersion === 2);
    cases.push("producer-settings-title");
    stage = "editor-revocation";
    await revoke(source, projectId, sessionId);
    await checkedHttp(source, tokens.editor, "/" + projectId + "/document", 403);
    await checkedHttp(source, tokens.editor, "/" + projectId + "/document", 403, "PUT",
      { ...previousMutation, writeSessionId: sessionId });
    cases.push("editor-revocation");
    stage = "build-freeze-and-replay";
    const initialBuildSnapshot = await snapshot(source, projectId);
    const currentHead = (initialBuildSnapshot.head as Array<Record<string, unknown>>)[0];
    requireTrue(typeof currentHead?.content_digest === "string");
    const intent = {
      buildClass: "preview", mode: "free", expectedRevision: 2,
      expectedDigest: currentHead.content_digest, idempotencyKey: randomUUID(),
      selectedSources: [], render: false, delivery: false,
    };
    await checkedHttp(source, tokens.viewer, "/" + projectId + "/builds", 403, "POST", intent);
    await checkedHttp(source, tokens.editor, "/" + projectId + "/builds", 403, "POST", intent);
    const submission = await checkedHttp(source, tokens.producer,
      "/" + projectId + "/builds", 202, "POST", intent);
    requireTrue(submission.status === "queued" && submission.duplicateDelivery === false &&
      typeof submission.jobId === "string" && typeof submission.snapshotDigest === "string");
    const jobId = submission.jobId;
    const replay = await checkedHttp(source, tokens.producer,
      "/" + projectId + "/builds", 202, "POST", intent);
    requireTrue(replay.jobId === jobId && replay.duplicateDelivery === true);
    await checkedHttp(source, tokens.producer, "/" + projectId + "/builds", 409,
      "POST", { ...intent, mode: "studio" });
    const initiallyQueued = await checkedHttp(source, tokens.viewer,
      "/" + projectId + "/builds/" + jobId, 200);
    requireTrue(initiallyQueued.status === "queued" && initiallyQueued.snapshotDigest === submission.snapshotDigest);
    cases.push("build-freeze-and-replay");

    stage = "agent-lease-partial";
    const offer = await checkedHttp(source, tokens.producer,
      "/" + projectId + "/agent-pairing-offers", 201, "POST",
      { agentLabel: "synthetic-only-qa", protocolVersion: "stt-build-agent/v1" });
    requireTrue(typeof offer.offerToken === "string");
    const consumed = await agentHttp(source, "unused-pairing-not-bearer",
      "/v1/agent-pairing/consume", 201, "POST",
      { projectId, offerToken: offer.offerToken,
        protocolVersion: "stt-build-agent/v1", capabilities: ["free_package_v1"] });
    requireTrue(typeof consumed.agentToken === "string" && consumed.credentialVersion === 1);
    const agentToken = consumed.agentToken;
    await agentHttp(source, agentToken, "/v1/agent-pairing/consume", 401,
      "POST", { projectId, offerToken: offer.offerToken,
        protocolVersion: "stt-build-agent/v1", capabilities: ["free_package_v1"] });
    const agentPath = "/v1/agent/projects/" + projectId;
    await agentHttp(source, "sttag_" + "z".repeat(43), agentPath + "/queue", 401);
    const queue = await agentHttp(source, agentToken, agentPath + "/queue", 200);
    requireTrue(Array.isArray(queue.jobIds) && queue.jobIds.length === 1 && queue.jobIds[0] === jobId);
    const claim = await agentHttp(source, agentToken, agentPath + "/jobs/" + jobId + "/claim", 200, "POST");
    requireTrue(claim.leaseEpoch === 1 && claim.snapshotDigest === submission.snapshotDigest);
    const leasePath = agentPath + "/jobs/" + jobId + "/leases/1";
    const frozen = await agentHttp(source, agentToken, leasePath + "/frozen", 200);
    requireTrue(frozen.documentDigest === currentHead.content_digest && frozen.mode === "free" &&
      frozen.settingsRevision === 2 && Array.isArray(frozen.selectedSources) &&
      frozen.selectedSources.length === 0);
    await agentHttp(source, agentToken, agentPath + "/jobs/" + jobId + "/leases/2/frozen", 409);
    await agentHttp(source, agentToken, leasePath + "/progress", 400, "POST",
      { status: "verified_native", stageKey: "generating_speech", receiptDigest: null, reasonCode: null });
    await agentHttp(source, agentToken, leasePath + "/progress", 202, "POST",
      { status: "running", stageKey: "generating_speech", receiptDigest: null, reasonCode: null });
    await agentHttp(source, agentToken, leasePath + "/progress", 202, "POST",
      { status: "waiting_reconcile", stageKey: "generating_speech",
        receiptDigest: null, reasonCode: "synthetic_uncertain" });
    const waiting = await checkedHttp(source, tokens.viewer, "/" + projectId + "/builds/" + jobId, 200);
    requireTrue(waiting.status === "waiting_reconcile" && waiting.leaseEpoch === 1 &&
      Array.isArray(waiting.events) && waiting.events.length === 4 &&
      Array.isArray(waiting.evidence) && waiting.evidence.length === 0);
    await agentHttp(source, agentToken, leasePath + "/frozen", 409);
    cases.push("agent-lease-partial");
    stage = "source-snapshot";
    const before = await snapshot(source, projectId);
    verifySnapshot(before);
    await readback(source, tokens, projectId, document2, updatedSettings, previousMutation, sessionId);
    stage = "source-stop";
    await stop(running); running = undefined;

    stage = "source-restart";
    running = await launch(source, env, tokens.producer);
    await readback(source, tokens, projectId, document2, updatedSettings, previousMutation, sessionId);
    requireTrue((await checkedHttp(source, tokens.viewer, "/" + projectId + "/builds/" + jobId, 200))
      .status === "waiting_reconcile");
    requireEqual(await snapshot(source, projectId), before);
    cases.push("source-restart");
    // Startup re-applies all four checksum-verified migrations to populated data.
    requireTrue((before.migrations as unknown[]).length === 4);
    cases.push("populated-migration");
    stage = "backup";
    await stop(running); running = undefined;
    runOperator("stt-qa-backup.sh", env, true);
    stage = "tamper-refusal";
    const tampered = tamperCopy(archiveDir);
    try {
      runOperator("stt-qa-restore.sh",
        { ...env, VERA_STT_QA_ARCHIVE_DIR: tampered }, false);
    } finally {
      // This directory was newly created by this invocation, not user data.
      rmSync(tampered, { recursive: true });
    }
    await preflightEmpty(target);
    cases.push("tampered-archive-refusal");
    stage = "fresh-restore";
    runOperator("stt-qa-restore.sh", env, true);
    cases.push("fresh-restore");
    runOperator("stt-qa-restore.sh", env, false);
    cases.push("existing-restore-refusal");

    stage = "restore-restart";
    running = await launch(target, env, tokens.producer);
    await readback(target, tokens, projectId, document2, updatedSettings, previousMutation, sessionId);
    requireTrue((await checkedHttp(target, tokens.viewer, "/" + projectId + "/builds/" + jobId, 200))
      .status === "waiting_reconcile");
    const restored = await snapshot(target, projectId);
    verifySnapshot(restored);
    requireEqual(restored, before);
    await stop(running); running = undefined;
    // The source remains byte-equivalent after backup and restore.
    requireEqual(await snapshot(source, projectId), before);
    cases.push("restored-restart");
    assertCompleteCases(cases);

    stage = "evidence";
    const manifest = safeObject(JSON.parse(readFileSync(join(archiveDir, "manifest.json"), "utf8")) as unknown);
    const summary = {
      deploymentMode: "development-qa", verifiedAtUtc: new Date().toISOString(),
      sourceSha: rev.stdout.trim(), sourceDatabase: source.databaseName,
      restoreDatabase: target.databaseName, postgresVersion: before.postgres,
      nodeVersion: process.version, host: "127.0.0.1", cases,
      documentHeadRevision: 2, immutableDocumentRevisions: 3,
      settingsRevision: 2, membershipAudits: 4, revokedWriteSessions: 1,
      migrationReceipts: before.migrations, archiveSha256: manifest.archiveSha256,
      archiveBytes: manifest.archiveBytes,
      manifestSha256: createHash("sha256").update(readFileSync(join(archiveDir, "manifest.json"))).digest("hex"),
      snapshotSha256: createHash("sha256").update(JSON.stringify(before)).digest("hex"),
      archiveInventory: manifest.inventory,
    };
    const path = join(archiveDir, "smoke-evidence.json");
    const fd = openSync(path, "wx", 0o600);
    try {
      // No project document, tokens, host logs, connection strings or user data.
      const writer = createWriteStream(path, { fd, autoClose: false });
      writer.end(JSON.stringify(summary, null, 2) + "\n");
      await new Promise<void>((resolve, reject) => {
        writer.once("finish", resolve); writer.once("error", reject);
      });
    } finally { closeSync(fd); }
    process.stdout.write("STT development-QA real HTTP/PostgreSQL/recovery smoke passed (15 scenarios)\n");
  } finally {
    if (running) await stop(running).catch(() => undefined);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) {
  void run().catch(() => {
    // No data, credentials, paths or potentially sensitive driver errors.
    process.stderr.write("STT development-QA real smoke unverified/refused at " + stage + "\n");
    process.exitCode = 1;
  });
}
