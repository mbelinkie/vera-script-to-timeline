import { createHash, randomBytes, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { SqlClient } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";
import { projectPrimarySequenceV2, validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import { checkedDocument } from "@vera/project-documents";

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

/** Three independent Draft rows: a visual source, narrated receiver and blank receiver. */
function pictureMoveFixture() {
  const document = structuredClone(sourceFixture.document);
  const source = document.activeDraft.blocks[0];
  if (source?.type !== "narration" || !source.primaryVisualSequence) throw new Error("missing source row");
  const narrated = structuredClone(source);
  narrated.id = randomUUID();
  narrated.orderKey = "b0";
  narrated.tokens = [{ ...source.tokens[0]!, id: randomUUID() }];
  narrated.primaryVisualSequence!.id = randomUUID();
  narrated.primaryVisualSequence!.slots = [{
    id: randomUUID(), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
    payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1,
  }];
  const blank = structuredClone(narrated);
  blank.id = randomUUID();
  blank.orderKey = "c0";
  blank.text = "";
  blank.tokens = [];
  blank.primaryVisualSequence!.id = randomUUID();
  blank.primaryVisualSequence!.slots[0]!.id = randomUUID();
  document.activeDraft.blocks.push(narrated, blank);
  expect(validateScriptDocumentV2(document).valid).toBe(true);
  return { document, source, narrated, blank };
}

async function authoringRequests(projects: (request: Request) => Promise<Response> = vi.fn(() =>
  Promise.resolve(Response.json({ error: "unexpected_project_route" }, { status: 500 })))) {
  const origin = "http://127.0.0.1:38429";
  const host = createAuthoringHandler(origin, `Bearer ${privateToken}`, projects);
  const request = async (path: string, body: unknown, opts: { session?: string; origin?: string; site?: string } = {}) =>
    await host.handle(new Request(`${origin}/authoring/${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json", "X-VERA-Authoring": "1",
        "Sec-Fetch-Site": opts.site ?? "same-origin", Origin: opts.origin ?? origin,
        ...(opts.session ? { "X-VERA-Session": opts.session } : {}),
        ...(path === "session" ? { "X-VERA-Launch": host.launchCode } : {}),
      },
      body: JSON.stringify(body),
    })) as Response;
  const session = await request("session", {});
  expect(session.status).toBe(200);
  const { sessionProof } = await session.json() as { sessionProof: string };
  const authorized = (path: string, body: unknown, opts: { session?: string; origin?: string; site?: string } = {}) =>
    request(path, body, { session: sessionProof, ...opts });
  return { request, authorized, sessionProof, projects, host };
}

describe("saved prompter export HTTP boundary", () => {
  const origin = "http://127.0.0.1:38429";
  const saved = checkedDocument(sourceFixture.document, sourceFixture.document.projectId);
  const projectId = saved.document.projectId;
  const path = `projects/${projectId}/prompter-export`;
  const view = { projectId, revision: 7, digest: saved.digest, document: saved.document };
  const settings = { includeSectionNavigation: false, includeBeatNumbers: false };
  const body = { expectedRevision: view.revision, expectedDigest: view.digest, settings };

  it("delegates exactly one authorized GET of the current saved head and returns a pinned, no-store pair", async () => {
    const projects = vi.fn((request: Request) => {
      expect(request.method).toBe("GET");
      expect(request.url).toBe(`${origin}/v1/projects/${projectId}/document`);
      expect(request.headers.get("authorization")).toBe(`Bearer ${privateToken}`);
      expect(request.headers.get("x-vera-session")).toBeNull();
      expect(request.body).toBeNull();
      return Promise.resolve(Response.json(view));
    });
    const { authorized } = await authoringRequests(projects);
    const first = await authorized(path, body);
    const second = await authorized(path, body);
    expect(first.status).toBe(200);
    expect(first.headers.get("cache-control")).toBe("no-store");
    expect(first.headers.get("x-content-type-options")).toBe("nosniff");
    expect(second.status).toBe(200);
    const pair = await first.json() as { projectId: string; revision: number; digest: string;
      text: string; sidecarJson: string; textSha256: string; sidecarSha256: string;
      sourceDocument: { liveHeadSequence: number } };
    expect(pair).toMatchObject({ projectId, revision: 7, digest: view.digest });
    expect(pair.text).toContain("hello");
    expect(pair.sidecarJson).toContain("prompter");
    expect(pair.textSha256).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(pair.sidecarSha256).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(await second.json()).toEqual(pair);
    const defaultSettings = await authorized(path, {
      expectedRevision: view.revision, expectedDigest: view.digest,
    });
    expect(defaultSettings.status).toBe(200);
    expect(await defaultSettings.json()).toEqual(pair);
    expect(JSON.stringify(pair)).not.toContain(privateToken);
    expect(projects).toHaveBeenCalledTimes(3);
  });

  it("refuses missing enrollment, other origins/sites, wrong paths and forged input before any saved read", async () => {
    const { request, authorized, projects, sessionProof, host } = await authoringRequests();
    for (const response of [
      await request(path, body),
      await authorized(path, body, { session: "a".repeat(64) }),
      await authorized(path, body, { origin: "http://127.0.0.1:38430" }),
      await authorized(path, body, { site: "cross-site" }),
    ]) {
      expect([401, 403]).toContain(response.status);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    }
    const bad = [
      null, [], {}, { ...body, expectedRevision: -1 }, { ...body, expectedRevision: 1.5 },
      { ...body, expectedRevision: "7" }, { ...body, expectedDigest: "sha256:bad" },
      { ...body, expectedDigest: view.digest.toUpperCase() },
      { ...body, document: view.document }, { ...body, projectId }, { ...body, extra: true },
      { ...body, settings: null }, { ...body, settings: {} },
      { ...body, settings: { ...settings, extra: 1 } },
      { ...body, settings: { ...settings, includeBeatNumbers: "false" } },
      { ...body, settings: { includeBeatNumbers: true } },
    ];
    for (const invalid of bad) {
      const response = await authorized(path, invalid);
      expect(response.status, JSON.stringify(invalid)).toBe(400);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(await response.json()).toEqual({ error: "invalid_prompter_export" });
    }
    const raw = async (url: string, method: string, payload = JSON.stringify(body), contentType = "application/json") =>
      await host.handle(new Request(url, {
        method, headers: { Origin: origin, "Sec-Fetch-Site": "same-origin", "X-VERA-Authoring": "1",
          "X-VERA-Session": sessionProof, "Content-Type": contentType }, body: method === "POST" ? payload : null,
      })) as Response;
    for (const url of [
      `${origin}/authoring/${path}?debug=1`, `${origin}/authoring/${path}/`,
      `${origin}/authoring/projects/not-uuid/prompter-export`,
    ]) expect((await raw(url, "POST")).status).toBe(404);
    expect((await raw(`${origin}/authoring/${path}`, "GET")).status).toBe(404);
    expect((await raw(`${origin}/authoring/${path}`, "POST", "{not json")).status).toBe(400);
    expect((await raw(`${origin}/authoring/${path}`, "POST", JSON.stringify(body), "text/plain")).status).toBe(400);
    expect(projects).not.toHaveBeenCalled();
  });

  it("preserves permission denials and refuses stale, inaccessible or corrupted saved heads without output", async () => {
    let upstream: Response = Response.json(view);
    const projects = vi.fn(() => Promise.resolve(upstream.clone()));
    const { authorized } = await authoringRequests(projects);
    for (const invalid of [
      { ...body, expectedRevision: 6 }, { ...body, expectedDigest: `sha256:${"0".repeat(64)}` },
    ]) {
      const response = await authorized(path, invalid);
      expect(response.status).toBe(409);
      expect(await response.json()).toEqual({ error: "saved_script_changed" });
    }
    for (const status of [401, 403, 404]) {
      upstream = Response.json({ error: "private information", document: view.document }, { status });
      const response = await authorized(path, body);
      expect(response.status).toBe(status);
      expect(await response.json()).not.toHaveProperty("document");
      expect(JSON.stringify(await authorized(path, body).then((r) => r.json()))).not.toContain("private information");
    }
    for (const invalid of [
      { ...view, digest: `sha256:${"0".repeat(64)}` },
      { ...view, document: { ...view.document, title: "tampered" } },
      { ...view, projectId: randomUUID() },
      { ...view, document: { ...view.document, activeDraft: null } },
    ]) {
      upstream = Response.json(invalid);
      const response = await authorized(path, body);
      expect(response.status).toBe(503);
      expect(await response.json()).not.toHaveProperty("text");
    }
    upstream = new Response("broken", { status: 200, headers: { "Content-Type": "application/json" } });
    expect((await authorized(path, body)).status).toBe(503);
    const unexportable = structuredClone(view.document);
    const row = unexportable.activeDraft.blocks[0];
    if (row?.type !== "narration" || !row.primaryVisualSequence) throw new Error("missing fixture narration");
    row.primaryVisualSequence.slots = [];
    const savedInvalid = checkedDocument(unexportable, projectId);
    upstream = Response.json({ ...view, digest: savedInvalid.digest, document: savedInvalid.document });
    const refused = await authorized(path, { ...body, expectedDigest: savedInvalid.digest });
    expect(refused.status).toBe(422);
    const validation = await refused.json() as { error: string; diagnostics: Array<{ code: string }>;
      text?: string; sidecarJson?: string };
    expect(validation.error).toBe("prompter_validation_failed");
    expect(validation.diagnostics.map(({ code }) => code)).toContain("PRIMARY_SEQUENCE_EMPTY");
    expect(validation).not.toHaveProperty("text");
    expect(validation).not.toHaveProperty("sidecarJson");
    expect(projects).toHaveBeenCalled();
  });
});

type CommandResult = { ok: boolean; document: ScriptDocumentV2; diagnostics: Array<{ code: string }>;
  evidence?: { kind: string; blockIds: string[]; payloadIds: string[] } };

async function commandResult(response: Response): Promise<CommandResult> {
  expect(response.status).toBe(200);
  return await response.json() as CommandResult;
}

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
  it("authorizes exact move/Attach commands, checks source sequence and preserves refusals", async () => {
    const { document, source, narrated } = pictureMoveFixture();
    const { request, authorized, projects } = await authoringRequests();
    const slotId = source.primaryVisualSequence!.slots[0]!.id;
    const command = { kind: "move_visual_to_row", blockId: source.id, slotId,
      destinationBlockId: narrated.id };
    const envelope = { document, command, expectedSequenceVersion: 1 };
    for (const path of ["command", "projection"]) {
      const body = path === "command" ? envelope : { document };
      expect((await request(path, body)).status).toBe(401);
      expect((await authorized(path, body, { session: "f".repeat(64) })).status).toBe(401);
      expect((await authorized(path, body, { origin: "http://127.0.0.1:38430" })).status).toBe(403);
      expect((await authorized(path, body, { site: "cross-site" })).status).toBe(403);
    }
    for (const bad of [
      { ...envelope, command: { ...command, unexpected: true } },
      { ...envelope, command: { ...command, destinationBlockId: "not-uuid" } },
      { ...envelope, command: { ...command, blockId: "not-uuid" } },
      { ...envelope, command: { ...command, slotId: "" } },
      { ...envelope, command: { ...command, expectedDestinationRowVersion: "1" } },
      { ...envelope, command: { ...command, expectedDestinationRowVersion: -1 } },
      { ...envelope, expectedSequenceVersion: undefined },
      { ...envelope, expectedSequenceVersion: 1, splitProof: "f".repeat(64) },
    ]) expect((await authorized("command", bad)).status).toBe(400);
    expect((await authorized("visual-command", envelope)).status).toBe(400); // No broad /visual-command bypass.
    for (const refused of [
      await commandResult(await authorized("command", { ...envelope, expectedSequenceVersion: 0 })),
      await commandResult(await authorized("command", { ...envelope, command: { ...command, blockId: randomUUID() } })),
      await commandResult(await authorized("command", { ...envelope, command: { ...command, destinationBlockId: randomUUID() } })),
    ]) {
      expect(refused.ok).toBe(false);
      expect(refused.document).toEqual(document);
    }
    const moved = await commandResult(await authorized("command", envelope));
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(moved.evidence).toMatchObject({ kind: "move_visual_to_row", blockIds: [source.id, narrated.id] });
    const destinationAfter = moved.document.activeDraft.blocks.find((row) => row.id === narrated.id) as NarrationBlockV2;
    expect(destinationAfter.unattachedVisuals?.[0]?.slotId).toBe(slotId);
    expect(destinationAfter.unattachedVisuals?.[0]?.payload).toEqual((source.primaryVisualSequence!.slots[0] as { payload: unknown }).payload);
    expect(moved.document.activeDraft.blocks.find((row) => row.id === source.id)).not.toEqual(source);

    const attach = { kind: "attach_visual_to_words", blockId: narrated.id, slotId,
      startTokenId: narrated.tokens[0]!.id, endTokenId: narrated.tokens[0]!.id };
    for (const bad of [
      { ...attach, missingToken: true }, { ...attach, endTokenId: "invalid" },
      { ...attach, startTokenId: undefined }, { ...attach, slotId: randomUUID(), extras: "no" },
    ]) expect((await authorized("command", {
      document: moved.document, command: bad, expectedSequenceVersion: destinationAfter.primaryVisualSequence!.version,
    })).status).toBe(400);
    const stale = await commandResult(await authorized("command", {
      document: moved.document, command: attach, expectedSequenceVersion: 1,
    }));
    expect(stale).toMatchObject({ ok: false, document: moved.document });
    expect(stale.diagnostics[0]?.code).toBe("SEQUENCE_VERSION_STALE");
    const attached = await commandResult(await authorized("command", {
      document: moved.document, command: attach, expectedSequenceVersion: destinationAfter.primaryVisualSequence!.version,
    }));
    expect(attached.ok, JSON.stringify(attached.diagnostics)).toBe(true);
    expect(attached.evidence?.kind).toBe("attach_visual_to_words");
    const attachedRow = attached.document.activeDraft.blocks.find((row) => row.id === narrated.id) as NarrationBlockV2;
    expect(attachedRow.unattachedVisuals ?? []).toHaveLength(0);
    expect(projects).not.toHaveBeenCalled();
  });

  it("routes wordless add, reorder, Hold and move through exact row revisions and model refusals", async () => {
    const { document, source, blank } = pictureMoveFixture();
    const { authorized, projects } = await authoringRequests();
    const firstPayloadId = randomUUID();
    const secondPayloadId = randomUUID();
    const first = { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: firstPayloadId, slotId: randomUUID(), visualType: "onscreen_placeholder" };
    const firstEnvelope = { document, command: first, expectedRowEditRevision: 0 };
    for (const bad of [
      { ...firstEnvelope, expectedRowEditRevision: undefined },
      { ...firstEnvelope, expectedSequenceVersion: 0 },
      { ...firstEnvelope, extra: true },
      { ...firstEnvelope, command: { ...first, unexpected: true } },
      { ...firstEnvelope, command: { ...first, rowId: "not-a-uuid" } },
      { ...firstEnvelope, command: { ...first, slotId: "" } },
      { ...firstEnvelope, command: { ...first, visualType: "footage" } },
      { ...firstEnvelope, expectedRowEditRevision: -1 },
      { ...firstEnvelope, expectedRowEditRevision: 1.5 },
    ]) expect((await authorized("command", bad)).status).toBe(400);
    const added = await commandResult(await authorized("command", firstEnvelope));
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    const wordless = added.document.activeDraft.blocks.find((row) => row.id === blank.id);
    expect(wordless).toMatchObject({ type: "visual_only", payload: { payloadId: firstPayloadId },
      visualOnlyTiming: { durationOverrideMs: 4000 } });
    const staleRow = await commandResult(await authorized("command", {
      document: added.document, command: { ...first, payloadId: randomUUID(), slotId: randomUUID() }, expectedRowEditRevision: 0,
    }));
    expect(staleRow).toMatchObject({ ok: false, document: added.document });
    expect(staleRow.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    const second = await commandResult(await authorized("command", {
      document: added.document, expectedRowEditRevision: 1,
      command: { ...first, payloadId: secondPayloadId, slotId: randomUUID(), visualType: "need_to_find" },
    }));
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const wrongOrder = await commandResult(await authorized("command", {
      document: second.document, expectedRowEditRevision: 2,
      command: { kind: "reorder_visual_only", rowId: blank.id, payloadIds: [firstPayloadId, firstPayloadId] },
    }));
    expect(wrongOrder).toMatchObject({ ok: false, document: second.document });
    const reordered = await commandResult(await authorized("command", {
      document: second.document, expectedRowEditRevision: 2,
      command: { kind: "reorder_visual_only", rowId: blank.id, payloadIds: [secondPayloadId, firstPayloadId] },
    }));
    expect(reordered.ok, JSON.stringify(reordered.diagnostics)).toBe(true);
    const held = await commandResult(await authorized("command", {
      document: reordered.document, expectedRowEditRevision: 3,
      command: { kind: "set_visual_only_hold", rowId: blank.id, payloadId: firstPayloadId, holdSeconds: 6 },
    }));
    expect(held.ok, JSON.stringify(held.diagnostics)).toBe(true);
    const invalidHold = await commandResult(await authorized("command", {
      document: held.document, expectedRowEditRevision: 4,
      command: { kind: "set_visual_only_hold", rowId: blank.id, payloadId: firstPayloadId, holdSeconds: -2 },
    }));
    expect(invalidHold).toMatchObject({ ok: false, document: held.document });
    expect(invalidHold.diagnostics[0]?.code).toBe("VISUAL_HOLD_INVALID");
    const oldProjection = await authorized("projection", { document: held.document });
    expect(oldProjection.status).toBe(200);
    expect((await oldProjection.json() as { projection: unknown }).projection)
      .toEqual(projectPrimarySequenceV2(held.document));

    const move = { kind: "move_wordless_visual", sourceRowId: blank.id,
      payloadId: secondPayloadId, destinationRowId: source.id, destinationSlotId: randomUUID(),
      expectedDestinationSequenceVersion: source.primaryVisualSequence!.version };
    for (const bad of [
      { ...move, destinationRowId: "bad-id" },
      { ...move, expectedDestinationSequenceVersion: -1 },
      { ...move, strange: "secret" },
    ]) expect((await authorized("command", {
      document: held.document, expectedRowEditRevision: 4, command: bad,
    })).status).toBe(400);
    for (const bad of [
      { ...move, destinationRowId: randomUUID() },
      { ...move, sourceRowId: randomUUID() },
      { ...move, expectedDestinationSequenceVersion: source.primaryVisualSequence!.version + 1 },
    ]) {
      const refused = await commandResult(await authorized("command", {
        document: held.document, expectedRowEditRevision: 4, command: bad,
      }));
      expect(refused.ok).toBe(false);
      expect(refused.document).toEqual(held.document);
    }
    const moved = await commandResult(await authorized("command", {
      document: held.document, expectedRowEditRevision: 4, command: move,
    }));
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    const receiving = moved.document.activeDraft.blocks.find((row) => row.id === source.id) as NarrationBlockV2;
    expect(receiving.unattachedVisuals?.[0]?.payload).toMatchObject({ payloadId: secondPayloadId });
    expect(moved.document.activeDraft.blocks.find((row) => row.id === blank.id)).toMatchObject({
      type: "visual_only", payload: { payloadId: firstPayloadId }, visualOnlyTiming: { durationOverrideMs: 6000 },
    });
    expect(projects).not.toHaveBeenCalled();
  });

  it("requires the destination wordless row revision when moving a narrated visual", async () => {
    const { document, source, blank } = pictureMoveFixture();
    const { authorized } = await authoringRequests();
    const originalSlot = source.primaryVisualSequence!.slots[0]!;
    if (originalSlot.kind !== "content") throw new Error("missing visual source");
    // This move deliberately uses a source-free picture. The model separately
    // refuses untrimmed footage to a wordless hold rather than guessing timing.
    originalSlot.payload = { kind: "visual", payloadId: randomUUID(), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "Harbour" }, sourceUsage: null,
      audioPolicy: "mute", framingPolicy: "contain" };
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const added = await commandResult(await authorized("command", {
      document, expectedRowEditRevision: 0, command: { kind: "add_visual_to_wordless_row",
        rowId: blank.id, payloadId: randomUUID(), slotId: randomUUID(), visualType: "onscreen_placeholder" },
    }));
    expect(added.ok).toBe(true);
    const target = added.document.activeDraft.blocks.find((row) => row.id === blank.id);
    if (target?.type !== "visual_only") throw new Error("expected visual-only destination");
    const command = { kind: "move_visual_to_row", blockId: source.id, slotId: originalSlot.id,
      destinationBlockId: blank.id };
    for (const malformed of [{ ...command, expectedDestinationRowVersion: "2" },
      { ...command, expectedDestinationRowVersion: -1 }, { ...command, nonsense: "extra" }]) {
      expect((await authorized("command", { document: added.document, command: malformed,
        expectedSequenceVersion: source.primaryVisualSequence!.version })).status).toBe(400);
    }
    for (const staleVersion of [undefined, target.version - 1, target.version + 1]) {
      const refused = await commandResult(await authorized("command", {
        document: added.document, expectedSequenceVersion: source.primaryVisualSequence!.version,
        command: { ...command, ...(staleVersion === undefined ? {} : { expectedDestinationRowVersion: staleVersion }) },
      }));
      expect(refused.ok).toBe(false);
      expect(refused.document).toEqual(added.document);
      expect(refused.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    }
    const moved = await commandResult(await authorized("command", {
      document: added.document, expectedSequenceVersion: source.primaryVisualSequence!.version,
      command: { ...command, expectedDestinationRowVersion: target.version },
    }));
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    const receiving = moved.document.activeDraft.blocks.find((row) => row.id === blank.id);
    expect(receiving).toMatchObject({ type: "visual_only", additionalVisuals: [{
      payload: { payloadId: originalSlot.payload.payloadId }, visualOnlyTiming: { durationOverrideMs: 4000 },
    }] });
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
