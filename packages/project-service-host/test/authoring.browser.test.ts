import { execFile as execFileCallback } from "node:child_process";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { chmod, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { PGlite } from "@electric-sql/pglite";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { applyProjectAuthorizationMigration, type SqlClient } from "@vera/project-authorization";
import { applyProjectBuildsMigration } from "@vera/project-builds";
import {
  applyProjectCommentsMigration,
  applyProjectDocumentsMigration,
  applyProjectHistoryMigration,
  applyProjectIdeasMigration,
  applyProjectSubtitleCopiesMigration,
} from "@vera/project-documents";
import { applyProjectCollaborationMigration } from "@vera/project-collaboration";
import { chromium, type Browser, type BrowserContext, type Locator, type Page } from "playwright";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import type { QaConfig } from "../src/qa-config.js";
import type { QaPgPool } from "../src/pg-pool.js";
import { startQaServer, type QaHostInfrastructure, type QaRunningServer } from "../src/serve.js";
import { unusedLoopbackPort } from "./loopback-port.js";
import { pasteParagraphBlocks } from "../browser/narration-editor.js";

const execFile = promisify(execFileCallback);
const REPOSITORY_ROOT = fileURLToPath(new URL("../../../", import.meta.url));
const DOCUMENT_FIXTURE = new URL(
  "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json",
  import.meta.url,
);
const VISUAL_ONLY_FIXTURE = new URL(
  "../../../tests/data/authoring_v2/issue_173/compiler/visual-only-image-still-25fps-default.input.golden.json",
  import.meta.url,
);

interface ApiResult {
  readonly status: number;
  readonly body: unknown;
}

interface SavedDocument {
  readonly document: ScriptDocumentV2;
  readonly revision: number;
}

interface BrowserVisualTestApi {
  queueVisualCommand(intent: unknown, label: string): Promise<boolean>;
  projectedPrimaryRow(rowId: string): { brackets: Array<{ endTokenIndexExclusive: number }> } | null;
}

declare global {
  interface Window { __veraVisualTest?: BrowserVisualTestApi }
}

// Browser app.js is a real ESM script. Expose its existing exports only in
// tests; Vitest otherwise rewrites import() inside page.evaluate into a
// server-side loader that does not exist in Chromium.
async function exposeVisualTestApi(page: Page): Promise<void> {
  await page.route("**/app.js", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, body: `${await response.text()}\nwindow.__veraVisualTest = { queueVisualCommand, projectedPrimaryRow };` });
  });
}

/* The host speaks PostgreSQL through this pool port; serialize PGlite's single session. */
function pglitePool(database: PGlite): QaPgPool {
  let previous = Promise.resolve();
  return {
    connect: async () => {
      const waiting = previous;
      let unlock: () => void = () => undefined;
      previous = new Promise<void>((resolve) => { unlock = resolve; });
      await waiting;
      let released = false;
      const client: SqlClient = {
        query: async <R>(sql: string, parameters?: readonly unknown[]) => {
          const result = await database.query<R>(sql, parameters ? [...parameters] : []);
          return { rows: result.rows };
        },
        exec: async (sql: string) => await database.exec(sql),
        release: () => {
          if (released) return;
          released = true;
          unlock();
        },
      };
      return client;
    },
    close: async () => await database.close(),
  };
}

/* Use the production SQL migrations while omitting only Postgres role/database identity checks. */
const migratePGlite: NonNullable<QaHostInfrastructure["migrate"]> = async (pool) => {
  const db = await pool.connect();
  try {
    await applyProjectAuthorizationMigration(db);
    await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db);
    await applyProjectHistoryMigration(db);
    await applyProjectIdeasMigration(db);
    await applyProjectSubtitleCopiesMigration(db);
    await applyProjectBuildsMigration(db);
    await applyProjectCollaborationMigration(db);
    return [];
  } finally {
    db.release?.();
  }
};

function documentFixture(projectId: string): { document: ScriptDocumentV2; firstRowText: string } {
  const source = JSON.parse(readFileSync(DOCUMENT_FIXTURE, "utf8")) as {
    document: ScriptDocumentV2;
  };
  const document = structuredClone(source.document);
  document.id = randomUUID();
  document.projectId = projectId;
  document.title = "Browser saved script";
  const narration = document.activeDraft.blocks.find((block) => block.type === "narration");
  if (!narration) throw new Error("browser document fixture has no narration row");
  const visualSource = JSON.parse(readFileSync(VISUAL_ONLY_FIXTURE, "utf8")) as { document: ScriptDocumentV2 };
  const row = visualSource.document.activeDraft.blocks.find((block) => block.type === "visual_only");
  if (!row) throw new Error("browser visual fixture has no visual-only row");
  document.activeDraft.blocks.push({
    ...row, id: randomUUID(), orderKey: "z", payload: { ...row.payload, payloadId: randomUUID() },
    additionalVisuals: [{
      payload: { ...row.payload, payloadId: randomUUID(), pictureKind: "clip" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 25 } },
    }],
  });
  return { document, firstRowText: narration.text };
}

function narrationWords(text: string): Array<{ id: string; value: string; startOffset: number; endOffset: number }> {
  return [...text.matchAll(/[^\s[\]]+/gu)].map((match) => ({
    id: randomUUID(), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
  }));
}

function editableDocumentFixture(
  projectId: string,
  text: string,
  withSecondVisual = false,
): { document: ScriptDocumentV2; firstRowText: string; rowId: string; anchorTokenId?: string } {
  const seeded = documentFixture(projectId);
  const row = seeded.document.activeDraft.blocks.find((block) => block.type === "narration");
  if (!row || row.type !== "narration") throw new Error("browser document fixture has no narration row");
  const tokens = narrationWords(text);
  row.text = text;
  row.tokens = tokens;

  let anchorTokenId: string | undefined;
  if (withSecondVisual) {
    const sequence = row.primaryVisualSequence;
    const firstSlot = sequence?.slots[0];
    const anchorToken = tokens[4];
    if (!sequence || !firstSlot || firstSlot.kind !== "content" || firstSlot.payload.kind !== "visual" || !anchorToken) {
      throw new Error("browser narration fixture cannot add its repeated-word visual");
    }
    anchorTokenId = anchorToken.id;
    sequence.slots = [firstSlot, {
      ...firstSlot,
      id: randomUUID(),
      relation: { kind: "sequential" },
      boundaryBefore: {
        kind: "spoken_word",
        anchor: {
          blockId: row.id, tokenId: anchorToken.id, affinity: "before",
          quotedWord: anchorToken.value, anchorVersion: 1,
        },
      },
      payload: { ...firstSlot.payload, payloadId: randomUUID() },
    }];
  }
  return { document: seeded.document, firstRowText: text, rowId: row.id, ...(anchorTokenId ? { anchorTokenId } : {}) };
}

/** Model-shaped r29 examples; the page must render the model's projection, not the stored slot list. */
function onCameraDocumentFixture(projectId: string, arrangement: "after-still" | "return" | "different-shot") {
  const seeded = editableDocumentFixture(projectId, "one two three four five six seven eight nine");
  const row = seeded.document.activeDraft.blocks.find((item) => item.id === seeded.rowId);
  if (row?.type !== "narration" || !row.primaryVisualSequence) throw new Error("missing narration sequence");
  const original = row.primaryVisualSequence.slots[0];
  if (!original || original.kind !== "content") throw new Error("missing base visual");
  const anchor = (index: number) => ({
    kind: "spoken_word" as const,
    anchor: {
      blockId: row.id, tokenId: row.tokens[index]!.id, affinity: "before" as const,
      quotedWord: row.tokens[index]!.value, anchorVersion: 1,
    },
  });
  const camera = (index: number, framing?: "wide" | "tight") => ({
    ...original, id: randomUUID(), relation: { kind: "sequential" as const },
    boundaryBefore: anchor(index),
    payload: { kind: "on_camera" as const, presenterChoiceId: null, ...(framing ? { framing } : {}) },
  });
  const still = { ...original, relation: { kind: "sequential" as const }, boundaryBefore: anchor(3) };
  if (arrangement === "after-still") {
    const after = camera(3);
    row.primaryVisualSequence.slots = [original, after];
    return { ...seeded, firstCameraSlotId: after.id };
  }
  const first = { ...camera(3), relation: { kind: "base" as const }, boundaryBefore: { kind: "row_start" as const } };
  const last = camera(6, arrangement === "different-shot" ? "tight" : undefined);
  row.primaryVisualSequence.slots = [first, still, last];
  return { ...seeded, firstCameraSlotId: first.id, lastCameraSlotId: last.id };
}

function foldedLetterRangeFixture(projectId: string) {
  const seeded = editableDocumentFixture(projectId,
    "A folded letter sat inside the sleeve for months. I think this was meant for whoever came next. The archivist placed a blank card beside it.");
  const row = seeded.document.activeDraft.blocks.find((item) => item.id === seeded.rowId);
  if (row?.type !== "narration" || !row.primaryVisualSequence) throw new Error("missing narration sequence");
  const first = row.primaryVisualSequence.slots[0];
  if (first?.kind !== "content" || first.payload.kind !== "visual") throw new Error("missing first still");
  const anchor = (index: number) => ({
    kind: "spoken_word" as const,
    anchor: { blockId: row.id, tokenId: row.tokens[index]!.id, affinity: "before" as const,
      quotedWord: row.tokens[index]!.value, anchorVersion: 1 },
  });
  const oc = { ...first, id: randomUUID(), relation: { kind: "sequential" as const },
    boundaryBefore: anchor(9), payload: { kind: "on_camera" as const, presenterChoiceId: null, framing: "tight" as const } };
  const second = { ...first, id: randomUUID(), relation: { kind: "sequential" as const },
    boundaryBefore: anchor(18), payload: { ...first.payload, payloadId: randomUUID() } };
  row.primaryVisualSequence.slots = [first, oc, second];
  return { ...seeded, firstSlotId: first.id, cameraSlotId: oc.id, secondSlotId: second.id };
}

function multiNarrationDocumentFixture(
  projectId: string,
  texts: readonly string[],
): { document: ScriptDocumentV2; rowIds: string[] } {
  if (texts.length < 2) throw new Error("browser row fixture needs at least two narration rows");
  const seeded = documentFixture(projectId);
  const first = seeded.document.activeDraft.blocks.find((block) => block.type === "narration");
  if (!first || first.type !== "narration") throw new Error("browser document fixture has no narration row");
  first.text = texts[0]!;
  first.tokens = narrationWords(first.text);
  const rows = [first];
  for (const text of texts.slice(1)) {
    const row = structuredClone(first);
    row.id = randomUUID();
    row.orderKey = `row-${row.id}`;
    row.text = text;
    row.tokens = narrationWords(text);
    if (row.primaryVisualSequence) {
      row.primaryVisualSequence.id = randomUUID();
      row.primaryVisualSequence.slots = row.primaryVisualSequence.slots.map((slot) => {
        if (slot.kind !== "content") return { ...slot, id: randomUUID() };
        const payload = slot.payload.kind === "visual" && slot.payload.source.kind === "media_reference"
          ? { ...slot.payload, payloadId: randomUUID(), source: { ...slot.payload.source, mediaReferenceId: randomUUID() } }
          : { ...slot.payload, payloadId: randomUUID() };
        return {
          ...slot,
          id: randomUUID(),
          relation: { kind: "base" },
          boundaryBefore: { kind: "row_start" },
          payload,
        };
      });
    }
    rows.push(row);
  }
  const visualOnlyIndex = seeded.document.activeDraft.blocks.findIndex((block) => block.type === "visual_only");
  seeded.document.activeDraft.blocks.splice(visualOnlyIndex < 0 ? seeded.document.activeDraft.blocks.length : visualOnlyIndex, 0, ...rows.slice(1));
  return { document: seeded.document, rowIds: rows.map((row) => row.id) };
}

async function appRequest(
  page: Page,
  path: string,
  method = "GET",
  body?: unknown,
): Promise<ApiResult> {
  return await page.evaluate(async ({ requestPath, requestMethod, requestBody }) => {
    const response = await fetch(requestPath, {
      method: requestMethod,
      headers: {
        "X-VERA-Authoring": "1",
        "X-VERA-Session": localStorage.getItem("vera.authoring.sessionProof") ?? "",
        ...(requestBody === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(requestBody === undefined ? {} : { body: JSON.stringify(requestBody) }),
    });
    return { status: response.status, body: await response.json() as unknown };
  }, { requestPath: path, requestMethod: method, requestBody: body });
}

async function createProject(page: Page, origin: string, title: string): Promise<string> {
  await page.goto(origin);
  await page.locator("#new-project-title").fill(title);
  await page.locator("#new-project-form button[type=submit]").click();
  await page.locator("#script-rows").waitFor({ state: "visible" });
  const id = new URL(page.url()).searchParams.get("project");
  if (!id) throw new Error("new project did not open a project URL");
  return id;
}

async function saveDocumentFixture(page: Page, projectId: string, document: ScriptDocumentV2): Promise<void> {
  const initial = await appRequest(page, `/authoring/projects/${projectId}/document`);
  expect(initial.status).toBe(200);
  const saved = initial.body as SavedDocument;
  document.id = saved.document.id;
  document.projectId = projectId;
  const response = await appRequest(page, `/authoring/projects/${projectId}/document`, "PUT", {
    expectedRevision: saved.revision,
    clientMutationId: randomUUID(),
    document,
  });
  expect(response.status).toBe(200);
}

async function narrationRowFromApi(page: Page, projectId: string, rowId: string): Promise<Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }> | null> {
  const response = await appRequest(page, `/authoring/projects/${projectId}/document`);
  if (response.status !== 200) return null;
  const document = (response.body as SavedDocument).document;
  const row = document.activeDraft.blocks.find((block) => block.id === rowId);
  return row?.type === "narration" ? row : null;
}

async function narrationRowsFromApi(page: Page, projectId: string): Promise<Array<Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }>>> {
  const response = await appRequest(page, `/authoring/projects/${projectId}/document`);
  if (response.status !== 200) return [];
  return (response.body as SavedDocument).document.activeDraft.blocks.filter(
    (block): block is Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }> => block.type === "narration",
  );
}

async function waitForNarrationText(page: Page, projectId: string, rowId: string, text: string): Promise<void> {
  await expect.poll(async () => (await narrationRowFromApi(page, projectId, rowId))?.text ?? null).toBe(text);
}

async function waitForNarrationCount(page: Page, projectId: string, count: number): Promise<void> {
  await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).length).toBe(count);
}

async function editorText(editor: Locator): Promise<string> {
  return await editor.evaluate((element) =>
    element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement ? element.value : element.textContent ?? "");
}

async function placeCaret(editor: Locator, offset: number): Promise<void> {
  await editor.focus();
  await editor.evaluate((element, wanted) => {
    const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    let remaining = wanted;
    while (node && remaining > (node.textContent?.length ?? 0)) {
      remaining -= node.textContent?.length ?? 0;
      node = walker.nextNode();
    }
    const range = element.ownerDocument.createRange();
    if (node) range.setStart(node, Math.min(remaining, node.textContent?.length ?? 0));
    else {
      range.selectNodeContents(element);
      range.collapse(false);
    }
    range.collapse(true);
    const selection = element.ownerDocument.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, offset);
}

async function selectText(editor: Locator, from: number, to: number): Promise<void> {
  await editor.focus();
  await editor.evaluate((element, { from, to }) => {
    const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node as Text);
    const point = (offset: number): [Node, number] => {
      let left = offset;
      for (const current of nodes) {
        if (left <= current.length) return [current, left];
        left -= current.length;
      }
      return [nodes.at(-1) ?? element, nodes.length ? nodes.at(-1)!.length : 0];
    };
    const selection = element.ownerDocument.getSelection();
    const range = element.ownerDocument.createRange();
    const [startNode, startOffset] = point(from);
    const [endNode, endOffset] = point(to);
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset);
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, { from, to });
}

async function dispatchPlainPaste(editor: Locator, text: string): Promise<void> {
  await editor.evaluate((element, plain) => {
    const data = new DataTransfer();
    data.setData("text/plain", plain);
    data.setData("text/html", `<strong>Ignored formatted ${plain.length}</strong>`);
    const event = new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: data });
    element.dispatchEvent(event);
    if (!event.defaultPrevented) throw new Error("Plain-text paste escaped the editor");
  }, text);
}

describe("pure plain clipboard grouping", () => {
  it.each([
    ["a", ["a"]], ["a\nb", ["a\nb"]], ["a\nb\n\nc", ["a\nb", "c"]],
    ["a\r\nb\r\n\r\nc", ["a\nb", "c"]], ["a\n", ["a\n"]],
    ["a\n\n", ["a", ""]], ["\n\nb", ["", "b"]],
    ["a\n\n\nb", ["a", "b"]], ["", [""]],
  ])("preserves paragraph and row boundaries in %j", (source, expected) => {
    expect(pasteParagraphBlocks(source)).toEqual(expected);
  });
});

async function setSlider(page: Page, selector: string, value: number): Promise<void> {
  await page.locator(selector).evaluate((element, nextValue) => {
    const input = element as HTMLInputElement;
    input.value = String(nextValue);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}

describe("browser authoring over the local project service", () => {
  let directory: string;
  let databaseDirectory: string;
  let browser: Browser;
  let context: BrowserContext;
  let database: PGlite;
  let host: QaRunningServer | undefined;
  let config: QaConfig;
  let authoringToken: string;

  async function startHost(): Promise<void> {
    database = new PGlite({ dataDir: databaseDirectory });
    await database.waitReady;
    const pool = pglitePool(database);
    host = await startQaServer(config, { createPool: () => pool, migrate: migratePGlite });
  }

  async function restartHostAndDatabase(): Promise<void> {
    await host?.stop();
    host = undefined;
    await startHost();
  }

  beforeAll(async () => {
    directory = await mkdtemp(join(tmpdir(), "vera-authoring-browser-"));
    databaseDirectory = join(directory, "pglite");
    authoringToken = randomBytes(32).toString("hex");
    const identityFile = join(directory, "identity.json");
    const subject = "browser-authoring-test-owner";
    await writeFile(identityFile, JSON.stringify({ version: 1, credentials: [{
      tokenSha256: createHash("sha256").update(authoringToken).digest("hex"),
      issuer: "urn:vera:stt:development-qa",
      subject,
    }] }), { mode: 0o600 });
    await chmod(identityFile, 0o600);
    config = {
      deploymentMode: "development-qa",
      bindHost: "127.0.0.1",
      port: await unusedLoopbackPort(),
      sourceSha: "a".repeat(40),
      databaseUrl: "postgresql://qa_test:synthetic@127.0.0.1:5432/vera_stt_qa_authoring_browser",
      databaseName: "vera_stt_qa_authoring_browser",
      databaseUser: "qa_test",
      identityFile,
      authoringToken,
    };
    await startHost();
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`http://127.0.0.1:${config.port}/#launch=${host!.authoringLaunchCode!}`);
    await page.waitForFunction(() => localStorage.getItem("vera.authoring.sessionProof")?.length === 64);
    expect(new URL(page.url()).hash).toBe("");
    await page.close();
  }, 60_000);

  afterAll(async () => {
    await context?.close();
    await browser?.close();
    await host?.stop();
    await rm(directory, { recursive: true, force: true });
  });

  it("protects pure projection and range commands with the browser session and exact sequence version", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Visual command authorization");
    const seeded = editableDocumentFixture(projectId, "alpha beta gamma delta echo foxtrot");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const row = seeded.document.activeDraft.blocks.find((block) => block.id === seeded.rowId);
    if (!row || row.type !== "narration" || !row.primaryVisualSequence) throw new Error("missing visual sequence");
    const slot = row.primaryVisualSequence.slots[0]!;
    const original = structuredClone(seeded.document);
    const body = {
      document: original, expectedSequenceVersion: row.primaryVisualSequence.version,
      command: { kind: "set_visual_range", blockId: row.id, slotId: slot.id,
        startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[2]!.id },
    };
    const proof = await page.evaluate(() => localStorage.getItem("vera.authoring.sessionProof"));
    for (const path of ["visual-command", "projection"]) {
      const payload = path === "projection" ? { document: original } : body;
      const withoutSession = await fetch(`${origin}/authoring/${path}`, {
        method: "POST", headers: { "sec-fetch-site": "same-origin", "x-vera-authoring": "1", "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      expect(withoutSession.status).toBe(401);
      const crossSite = await fetch(`${origin}/authoring/${path}`, {
        method: "POST", headers: { "sec-fetch-site": "cross-site", "origin": "https://untrusted.example",
          "x-vera-authoring": "1", "x-vera-session": proof!, "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      expect(crossSite.status).toBe(403);
      expect((await appRequest(page, `/authoring/${path}`, "GET")).status).toBe(404);
    }
    const projection = await appRequest(page, "/authoring/projection", "POST", { document: original });
    expect(projection.status).toBe(200);
    expect((projection.body as { projection: { rows: Array<{ blockId: string }> } }).projection.rows[0]?.blockId).toBe(row.id);
    expect((await appRequest(page, "/authoring/visual-command", "POST", {
      ...body, command: { kind: "delete_slot", blockId: row.id, slotId: slot.id },
    })).status).toBe(400);

    const stale = await appRequest(page, "/authoring/visual-command", "POST", {
      ...body, expectedSequenceVersion: row.primaryVisualSequence.version + 1,
    });
    expect(stale.status).toBe(200);
    expect(stale.body).toMatchObject({ ok: false, document: original, diagnostics: [{ code: "SEQUENCE_VERSION_STALE" }] });
    const refused = await appRequest(page, "/authoring/visual-command", "POST", {
      ...body, command: { ...body.command, endTokenId: randomUUID() },
    });
    expect(refused.body).toMatchObject({ ok: false, document: original, diagnostics: [{ code: "RANGE_OUTSIDE_ROW" }] });
    const accepted = await appRequest(page, "/authoring/visual-command", "POST", body);
    expect(accepted.status).toBe(200);
    const result = accepted.body as { ok: boolean; document: ScriptDocumentV2; projection: {
      rows: Array<{ brackets: Array<{ slotId: string; endTokenIndexExclusive: number }> }>;
    } };
    expect(result.ok).toBe(true);
    expect(result.document).not.toEqual(original);
    expect(result.projection.rows[0]?.brackets).toEqual(expect.arrayContaining([
      expect.objectContaining({ slotId: slot.id, endTokenIndexExclusive: 3 }),
    ]));
    // These two routes are pure: the browser must explicitly save a successful edit.
    const saved = await appRequest(page, `/authoring/projects/${projectId}/document`);
    expect((saved.body as SavedDocument).document).toEqual(original);
    await page.close();
  }, 90_000);

  it("queues a visual intent against current tokens, saves one snapshot Undo and refuses without history", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Serialized visual edits");
    const seeded = editableDocumentFixture(projectId, "alpha beta gamma delta echo foxtrot");
    await saveDocumentFixture(page, projectId, seeded.document);
    await exposeVisualTestApi(page);
    await page.goto(`${origin}/?project=${projectId}`);
    const oldRow = seeded.document.activeDraft.blocks.find((block) => block.id === seeded.rowId);
    if (oldRow?.type !== "narration" || !oldRow.primaryVisualSequence) throw new Error("missing visual row");
    const originalVersion = oldRow.primaryVisualSequence.version;
    const slotId = oldRow.primaryVisualSequence.slots[0]!.id;
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    let releaseFirst: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { releaseFirst = resolve; });
    let beganFirst: () => void = () => undefined;
    const started = new Promise<void>((resolve) => { beganFirst = resolve; });
    await page.route("**/authoring/command", async (route) => {
      beganFirst();
      await gate;
      await route.continue();
    });
    await editor.fill("fresh alpha beta gamma delta echo foxtrot");
    await started;
    const pendingVisual = page.evaluate(async ({ rowId, slotId: visualSlot }) => {
      return await window.__veraVisualTest!.queueVisualCommand((document: ScriptDocumentV2) => {
        const row = document.activeDraft.blocks.find((block) => block.id === rowId);
        if (row?.type !== "narration") throw new Error("missing updated tokens");
        return { kind: "set_visual_range", blockId: rowId, slotId: visualSlot,
          startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[2]!.id };
      }, "Set visual range");
    }, { rowId: seeded.rowId, slotId });
    releaseFirst();
    expect(await pendingVisual).toBe(true);
    // The preceding retokenization also advances the sequence. The visual
    // edit must use that current revision, not the pre-typing revision.
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))?.primaryVisualSequence?.version)
      .toBe(originalVersion + 2);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Set visual range", "Edit narration"]);
    await expect.poll(async () => await page.evaluate((rowId) => {
      return window.__veraVisualTest!.projectedPrimaryRow(rowId)?.brackets[0]?.endTokenIndexExclusive;
    }, seeded.rowId)).toBe(3);

    const failed = await page.evaluate(async (rowId) => {
      return await window.__veraVisualTest!.queueVisualCommand({ kind: "set_visual_range", blockId: rowId, slotId: crypto.randomUUID(),
        startTokenId: crypto.randomUUID(), endTokenId: crypto.randomUUID() }, "Refused range");
    }, seeded.rowId);
    expect(failed).toBe(false);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Set visual range", "Edit narration"]);
    await page.getByRole("button", { name: "Undo Set visual range" }).click();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))?.primaryVisualSequence?.version)
      .toBe(originalVersion + 1);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Edit narration"]);
    await page.close();
  }, 90_000);

  it("draws model-projected cards: first OC after still is full, and only real returns are compact", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    for (const arrangement of ["after-still", "return", "different-shot"] as const) {
      const projectId = await createProject(page, origin, `Projected cards ${arrangement}`);
      const seeded = onCameraDocumentFixture(projectId, arrangement);
      await saveDocumentFixture(page, projectId, seeded.document);
      const result = await appRequest(page, "/authoring/projection", "POST", { document: seeded.document });
      expect(result.status).toBe(200);
      const projected = result.body as { projection: { rows: Array<{ blockId: string; renderable: boolean;
        cards: Array<{ kind: string; compact: boolean; slotId: string; startTokenIndex: number }> }> } };
      const modelCards = projected.projection.rows.find((row) => row.blockId === seeded.rowId);
      expect(modelCards?.renderable).toBe(true);
      await page.goto(`${origin}/?project=${projectId}`);
      const stack = page.locator(`[data-row-id="${seeded.rowId}"] .visuals-list`);
      await expect.poll(async () => await stack.locator("[data-slot-id]").count()).toBe(modelCards?.cards.length);
      const visible = await stack.locator("[data-slot-id]").evaluateAll((items) => items.map((item) => ({
        slotId: (item as HTMLElement).dataset.slotId,
        compact: item.classList.contains("visual-return"),
      })));
      expect(visible).toEqual(modelCards?.cards.map((card) => ({ slotId: card.slotId, compact: card.compact })));
      if (arrangement === "after-still") {
        expect(await stack.locator(".visual-card").count()).toBe(2);
        expect(await stack.locator(".visual-card[data-kind='on-camera']").count()).toBe(1);
        expect(await stack.locator(".visual-return").count()).toBe(0);
        expect(modelCards?.cards[1]).toMatchObject({ kind: "on_camera", compact: false, startTokenIndex: 3 });
      } else if (arrangement === "return") {
        expect(await stack.locator(".visual-card[data-kind='on-camera']").count()).toBe(1);
        expect(await stack.locator(".visual-return[data-kind='on_camera']").innerText()).toContain("OC resumes");
      } else {
        expect(await stack.locator(".visual-card[data-kind='on-camera']").count()).toBe(2);
        expect(await stack.locator(".visual-return").count()).toBe(0);
      }
      // Visual-only rows and their thumbnail previews do not depend on narrated projection.
      expect(await page.locator('[data-row-kind="visual_only"] .visual-card').count()).toBe(2);
      expect(await page.locator('[data-row-kind="visual_only"] .visual-card__preview').count()).toBe(2);
    }
    await page.close();
  }, 90_000);

  it("stores per-passage Wide/Tight with one Undo, reload, and no-op refusal", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "On Camera framing controls");
    const seeded = onCameraDocumentFixture(projectId, "after-still");
    await saveDocumentFixture(page, projectId, seeded.document);
    await exposeVisualTestApi(page);
    await page.goto(`${origin}/?project=${projectId}`);
    const stack = page.locator(`[data-row-id="${seeded.rowId}"] .visuals-list`);
    const oc = stack.locator(`.visual-card[data-slot-id="${seeded.firstCameraSlotId}"]`);
    const wide = oc.getByRole("button", { name: "Wide" });
    const tight = oc.getByRole("button", { name: "Tight" });
    await tight.waitFor({ state: "visible" });
    expect(await wide.getAttribute("aria-pressed")).toBe("true");
    await tight.click();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))
      ?.primaryVisualSequence?.slots.find((item) => item.id === seeded.firstCameraSlotId && item.kind === "content")
    ).toMatchObject({ payload: { kind: "on_camera", framing: "tight" } });
    expect(await tight.getAttribute("aria-pressed")).toBe("true");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Set On Camera Tight"]);
    await tight.click();
    await expect.poll(async () => await page.locator("#save-status").textContent()).toContain("already Tight");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Set On Camera Tight"]);
    await page.getByRole("button", { name: "Undo Set On Camera Tight" }).click();
    await expect.poll(async () => await wide.getAttribute("aria-pressed")).toBe("true");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Nothing to undo in this session"]);
    await tight.click();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))
      ?.primaryVisualSequence?.slots.find((item) => item.id === seeded.firstCameraSlotId && item.kind === "content")
    ).toMatchObject({ payload: { kind: "on_camera", framing: "tight" } });
    await page.reload();
    await expect.poll(async () => await stack.locator('.visual-card__framing-choice[aria-pressed="true"]').textContent()).toBe("Tight");
    await page.close();
  }, 90_000);

  it("updates projected OC coverage after a range change without manufacturing a compact return", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Uncovered words get OC");
    const seeded = onCameraDocumentFixture(projectId, "after-still");
    await saveDocumentFixture(page, projectId, seeded.document);
    await exposeVisualTestApi(page);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator(`[data-row-id="${seeded.rowId}"]`).waitFor({ state: "visible" });
    const row = seeded.document.activeDraft.blocks.find((item) => item.id === seeded.rowId);
    if (row?.type !== "narration" || !row.primaryVisualSequence) throw new Error("missing narration row");
    const still = row.primaryVisualSequence.slots[0]!;
    const rangeAccepted = await page.evaluate(async ({ rowId, slotId, first, last }) =>
      await window.__veraVisualTest!.queueVisualCommand({
        kind: "set_visual_range", blockId: rowId, slotId, startTokenId: first, endTokenId: last,
      }, "Set visual range"), {
      rowId: seeded.rowId, slotId: still.id, first: row.tokens[0]!.id, last: row.tokens[1]!.id,
    });
    expect(rangeAccepted).toBe(true);
    const stack = page.locator(`[data-row-id="${seeded.rowId}"] .visuals-list`);
    await expect.poll(async () => await stack.locator("[data-slot-id]").count()).toBe(2);
    expect(await stack.locator(".visual-card[data-kind='on-camera']").count()).toBe(1);
    expect(await stack.locator(".visual-return").count()).toBe(0);
    await expect.poll(async () => await page.evaluate((rowId) =>
      window.__veraVisualTest!.projectedPrimaryRow(rowId)?.brackets[0]?.endTokenIndexExclusive, seeded.rowId)).toBe(2);
    await page.getByRole("button", { name: "Undo Set visual range" }).click();
    await expect.poll(async () => await page.evaluate((rowId) =>
      window.__veraVisualTest!.projectedPrimaryRow(rowId)?.brackets[0]?.endTokenIndexExclusive, seeded.rowId)).toBe(3);
    await page.close();
  }, 90_000);

  it("discards a delayed projection from before a visual edit", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Stale projection test");
    const seeded = editableDocumentFixture(projectId, "one two three four five six");
    await saveDocumentFixture(page, projectId, seeded.document);
    await exposeVisualTestApi(page);
    let releaseOld: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { releaseOld = resolve; });
    let oldStarted: () => void = () => undefined;
    const started = new Promise<void>((resolve) => { oldStarted = resolve; });
    let first = true;
    await page.route("**/authoring/projection", async (route) => {
      if (first) { first = false; oldStarted(); await gate; }
      await route.continue();
    });
    await page.goto(`${origin}/?project=${projectId}`);
    await started;
    const slotId = (seeded.document.activeDraft.blocks.find((block) => block.id === seeded.rowId) as
      Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }>).primaryVisualSequence!.slots[0]!.id;
    const ok = await page.evaluate(async ({ rowId, slotId: id }) => {
      return await window.__veraVisualTest!.queueVisualCommand((doc: ScriptDocumentV2) => {
        const row = doc.activeDraft.blocks.find((block) => block.id === rowId);
        if (row?.type !== "narration") throw new Error("missing row");
        return { kind: "set_visual_range", blockId: rowId, slotId: id,
          startTokenId: row.tokens[0]!.id, endTokenId: row.tokens[2]!.id };
      }, "Set visual range");
    }, { rowId: seeded.rowId, slotId });
    expect(ok).toBe(true);
    const oldResponse = page.waitForResponse((response) => response.url().endsWith("/authoring/projection"));
    releaseOld();
    expect((await oldResponse).status()).toBe(200);
    await expect.poll(async () => await page.evaluate((rowId) => {
      return window.__veraVisualTest!.projectedPrimaryRow(rowId)?.brackets[0]?.endTokenIndexExclusive;
    }, seeded.rowId)).toBe(3);
    await page.close();
  }, 90_000);

  it("adds, renames and deletes a section break with inline cancel/no-op and exact Undo", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Section command controls");
    const seeded = multiNarrationDocumentFixture(projectId, ["Opening\nparagraph", "Middle scene", "Closing scene"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const divider = page.locator(`[data-after-row-id="${seeded.rowIds[0]}"][data-before-row-id="${seeded.rowIds[1]}"]`);
    const addSection = async () => {
      await divider.locator("[data-row-add-options]").click();
      await divider.getByRole("menuitem", { name: "Add section" }).click();
    };
    expect(await page.locator("[data-section-add]").count()).toBe(3);
    expect(await page.locator("[data-section-add]").first().getAttribute("aria-label")).toBe("Add section");
    await divider.locator("[data-row-add-options]").click();
    await divider.getByRole("menuitem", { name: "Add section" }).press("Escape");
    expect(await divider.getByRole("menuitem", { name: "Add section" }).isVisible()).toBe(false);
    await addSection();
    await page.getByRole("textbox", { name: "New section title" }).press("Escape");
    expect(await page.locator(".script-section-heading").count()).toBe(0);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Nothing to undo in this session"]);

    await addSection();
    await page.getByRole("textbox", { name: "New section title" }).press("Enter");
    expect(await page.locator(".script-section-heading").count()).toBe(0);
    expect(await page.locator("[data-section-title-form]").count()).toBe(0);

    await addSection();
    const newTitle = page.getByRole("textbox", { name: "New section title" });
    await newTitle.fill("  Act I  ");
    await newTitle.press("Enter");
    await expect.poll(async () => await page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act I"]);
    expect(await page.locator("[data-section-add]").count()).toBe(2);
    const actions = page.getByRole("button", { name: /Section actions for/u });
    await actions.click();
    await page.getByRole("menuitem", { name: "Rename section" }).click();
    const rename = page.getByRole("textbox", { name: "Rename section title" });
    await rename.fill("Discarded");
    await rename.press("Escape");
    expect(await page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act I"]);

    await actions.click();
    await page.getByRole("menuitem", { name: "Rename section" }).click();
    await rename.press("Enter"); // unchanged title is not a model command
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Add section"]);
    await actions.click();
    await page.getByRole("menuitem", { name: "Rename section" }).click();
    await rename.fill("  Act II ");
    await rename.press("Enter");
    await expect.poll(async () => await page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act II"]);
    await actions.click();
    await page.getByRole("menuitem", { name: "Delete section break" }).click();
    await expect.poll(async () => page.locator(".script-section-heading").count()).toBe(0);
    expect(await page.locator(".script-row").count()).toBe(4); // three narration rows + seeded visual-only row
    expect(await page.locator("#undo-history li").allTextContents()).toEqual([
      "Delete section break", "Rename section", "Add section",
    ]);

    await page.getByRole("button", { name: "Undo Delete section break" }).click();
    await expect.poll(async () => page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act II"]);
    await page.getByRole("button", { name: "Undo Rename section" }).click();
    await expect.poll(async () => page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act I"]);
    await expect.poll(async () => page.locator("#save-status").textContent()).toBe("Saved");
    const saved = await appRequest(page, `/authoring/projects/${projectId}/document`);
    const savedBlocks = (saved.body as SavedDocument).document.activeDraft.blocks;
    const heading = savedBlocks.find((block) => block.type === "section");
    expect(heading?.type === "section" ? heading.title : null).toBe("Act I");
    const firstNarration = savedBlocks.find((block) => block.id === seeded.rowIds[0]);
    expect(firstNarration?.type === "narration" ? firstNarration.text : null)
      .toBe("Opening\nparagraph");

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    expect(await page.locator(".script-section-heading__title").allTextContents()).toEqual(["Act I"]);
    const outputFile = `sections-${randomUUID()}.json`;
    await execFile("npm", ["--prefix", REPOSITORY_ROOT, "run", "export:script", "--", projectId, outputFile], {
      cwd: directory,
      env: { ...process.env, VERA_STT_QA_PORT: String(config.port), VERA_STT_QA_AUTHORING_TOKEN: authoringToken },
      timeout: 60_000,
      maxBuffer: 4 * 1024 * 1024,
    });
    const exported = JSON.parse(await readFile(join(directory, outputFile), "utf8")) as ScriptDocumentV2;
    expect(exported.activeDraft.blocks).toEqual(savedBlocks);
    await page.close();
  }, 90_000);

  it("keeps an opening section's Delete break absent", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Opening section");
    const seeded = multiNarrationDocumentFixture(projectId, ["First", "Second"]);
    seeded.document.activeDraft.blocks.unshift({ type: "section", id: randomUUID(), title: "Opening", orderKey: "opening", version: 1 });
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator(".script-section-heading").waitFor();
    await page.getByRole("button", { name: /Section actions for/u }).click();
    expect(await page.locator("[data-section-delete]").count()).toBe(0);
    await page.close();
  }, 90_000);

  it("coalesces adjacent typing and backspace but separates pauses and cursor movements", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Useful typing history");
    const seeded = editableDocumentFixture(projectId, "sun");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, 3);
    await page.keyboard.type(" moon", { delay: 0 });
    await waitForNarrationText(page, projectId, seeded.rowId, "sun moon");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Edit narration"]);
    await page.waitForTimeout(1150);
    await page.keyboard.type("lit", { delay: 0 });
    await waitForNarrationText(page, projectId, seeded.rowId, "sun moonlit");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Edit narration", "Edit narration"]);

    await editor.press("ArrowLeft");
    await editor.press("ArrowRight"); // return to same caret, but start a separate history step
    await page.keyboard.type("!", { delay: 0 });
    await waitForNarrationText(page, projectId, seeded.rowId, "sun moonlit!");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual([
      "Edit narration", "Edit narration", "Edit narration",
    ]);
    await page.getByRole("button", { name: "Undo Edit narration" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "sun moonlit");
    await page.getByRole("button", { name: "Undo Edit narration" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "sun moon");
    await page.getByRole("button", { name: "Undo Edit narration" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "sun");

    await placeCaret(editor, 3);
    await editor.press("Backspace");
    await editor.press("Backspace");
    await waitForNarrationText(page, projectId, seeded.rowId, "s");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Edit narration"]);
    await page.getByRole("button", { name: "Undo Edit narration" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "sun");
    await page.close();
  }, 90_000);

  it.each([1024, 1280])("keeps the header and native authoring slider stationary at %i px", async (width) => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    await page.setViewportSize({ width, height: 768 });
    const projectId = await createProject(page, origin, `Stationary slider ${width}`);
    const seeded = editableDocumentFixture(projectId, "Long narration ".repeat(380));
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const slider = page.locator("#authoring-size");
    await setSlider(page, "#authoring-size", 100);
    const before = await slider.boundingBox();
    const barBefore = await page.locator(".app-bar").boundingBox();
    if (!before || !barBefore) throw new Error("Slider/header absent");
    const centerY = before.y + before.height / 2;
    await page.mouse.move(before.x + 2, centerY);
    await page.mouse.down();
    await page.mouse.move(before.x + before.width - 2, centerY, { steps: 12 });
    await page.mouse.up();
    expect(Number(await slider.inputValue())).toBeGreaterThanOrEqual(145);
    for (const percent of [80, 100, 150]) {
      await setSlider(page, "#authoring-size", percent);
      const after = await slider.boundingBox();
      const header = await page.locator(".app-bar").boundingBox();
      if (!after || !header) throw new Error("Slider/header disappeared while dragging");
      expect(Math.abs(after.x - before.x)).toBeLessThan(1);
      expect(Math.abs(after.y - before.y)).toBeLessThan(1);
      expect(Math.abs(after.width - before.width)).toBeLessThan(1);
      expect(Math.abs(header.height - barBefore.height)).toBeLessThan(1);
      expect(await page.locator(".script-paper").evaluate((el) => getComputedStyle(el).zoom)).toBe(String(percent / 100));
    }
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await expect.poll(async () => page.evaluate(() => scrollY)).toBeGreaterThan(0);
    const scrolledBar = await page.locator(".app-bar").boundingBox();
    expect(Math.abs((scrolledBar?.y ?? -100) - barBefore.y)).toBeLessThan(1);
    // Context pages share localStorage; leave the original view default for
    // the existing persistence test's fresh-project expectation.
    await setSlider(page, "#authoring-size", 100);
    await page.close();
  }, 90_000);

  it.each([
    ["a\nb\n\nc", ["front a\nb", "cback"]],
    ["a\r\nb\r\n\r\nc", ["front a\nb", "cback"]],
    ["a\n\nb\n", ["front a", "b\nback"]],
    ["a\n\nb\n\nc", ["front a", "b", "cback"]],
  ])("pastes plain %j into the middle as a single Undo step", async (clipboard, expected) => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Plain clipboard rows");
    const seeded = editableDocumentFixture(projectId, "front back");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, "front ".length);
    await dispatchPlainPaste(editor, clipboard);
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(expected);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Paste text"]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(["front back"]);
    await page.close();
  }, 90_000);

  it("keeps a single LF and terminal LF inside one row, with no HTML pasted", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Clipboard paragraph");
    const seeded = editableDocumentFixture(projectId, "hello world");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, "hello world".length);
    await dispatchPlainPaste(editor, "\r\nnext\r\n");
    await waitForNarrationText(page, projectId, seeded.rowId, "hello world\nnext\n");
    expect((await narrationRowsFromApi(page, projectId)).length).toBe(1);
    expect(await editorText(editor)).toBe("hello world\nnext\n");
    await page.close();
  }, 90_000);

  it("keeps the original suffix word IDs and anchored visuals on the pasted row", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Paste visual anchor");
    const seeded = editableDocumentFixture(projectId, "alpha beta gamma delta echo foxtrot", true);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, "alpha beta gamma delta ".length);
    await dispatchPlainPaste(editor, "a\nb\n\nc ");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "alpha beta gamma delta a\nb", "c echo foxtrot",
    ]);
    const rows = await narrationRowsFromApi(page, projectId);
    expect(rows[1]?.tokens.find((token) => token.value === "echo")?.id).toBe(seeded.anchorTokenId);
    expect(JSON.stringify(rows[1]?.primaryVisualSequence)).toContain(seeded.anchorTokenId);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "alpha beta gamma delta echo foxtrot");
    expect((await narrationRowFromApi(page, projectId, seeded.rowId))?.primaryVisualSequence)
      .toEqual((seeded.document.activeDraft.blocks.find((block) => block.id === seeded.rowId) as
        Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }>).primaryVisualSequence);
    await page.close();
  }, 90_000);

  it("does not merge a preceding edit's Undo with a paste, including selection replacement and Unicode", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Prior edit and paste");
    const seeded = editableDocumentFixture(projectId, "one two three");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await editor.fill("one two three edited");
    await waitForNarrationText(page, projectId, seeded.rowId, "one two three edited");
    await selectText(editor, "one ".length, "one two".length);
    await dispatchPlainPaste(editor, "😀\n\nnext");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "one 😀", "next three edited",
    ]);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Paste text", "Edit narration"]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "one two three edited");
    await page.getByRole("button", { name: "Undo Edit narration" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "one two three");
    await page.close();
  }, 90_000);

  it("pastes after an emoji without splitting its UTF-16 surrogate pair", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "UTF-16 clipboard boundary");
    const seeded = editableDocumentFixture(projectId, "hello 😀 world");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, "hello 😀".length);
    await dispatchPlainPaste(editor, " waves\n\nthen");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "hello 😀 waves", "then world",
    ]);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Paste text"]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "hello 😀 world");
    await page.close();
  }, 90_000);

  it("uses exact row gaps for leading and trailing blank clipboard blocks", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Paste blank blocks");
    const seeded = editableDocumentFixture(projectId, "start end");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, 0);
    await dispatchPlainPaste(editor, "\n\nnew ");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "", "new start end",
    ]);
    await expect.poll(async () => await page.locator(".script-row").count()).toBeGreaterThanOrEqual(3);
    await page.close();
  }, 90_000);

  it("creates an empty row for a trailing blank line at the end of the script", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Trailing blank clipboard block");
    const seeded = editableDocumentFixture(projectId, "first row");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, "first row".length);
    await dispatchPlainPaste(editor, "\n\n");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "first row", "",
    ]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(["first row"]);
    await page.close();
  }, 90_000);

  it("inserts all pasted rows inside their existing section without moving the next heading", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Clipboard within section");
    const seeded = multiNarrationDocumentFixture(projectId, ["before section", "after section"]);
    const sectionId = randomUUID();
    seeded.document.activeDraft.blocks.splice(1, 0, {
      type: "section", id: sectionId, orderKey: `section-${sectionId}`, title: "Section two", version: 1,
    });
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowIds[0]}"] [data-narration-editor]`);
    await placeCaret(editor, "before section".length);
    await dispatchPlainPaste(editor, " first\n\nsecond");
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "before section first", "second", "after section",
    ]);
    const saved = (await appRequest(page, `/authoring/projects/${projectId}/document`)).body as SavedDocument;
    expect(saved.document.activeDraft.blocks.slice(0, 4).map((block) => block.type)).toEqual([
      "narration", "narration", "section", "narration",
    ]);
    expect(saved.document.activeDraft.blocks[2]?.id).toBe(sectionId);
    expect(saved.document.activeDraft.blocks[3]?.id).toBe(seeded.rowIds[1]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "before section", "after section",
    ]);
    await page.close();
  }, 90_000);

  it("serializes a paste behind a pending text edit without reading invented word IDs", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Queued typing before paste");
    const seeded = editableDocumentFixture(projectId, "first second");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    let requests = 0;
    let started!: () => void;
    const firstStarted = new Promise<void>((resolve) => { started = resolve; });
    let release!: () => void;
    const firstReleased = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/authoring/command", async (route) => {
      if (route.request().method() !== "POST") return await route.continue();
      requests += 1;
      if (requests === 1) { started(); await firstReleased; }
      await route.continue();
    });
    await editor.fill("first second typed");
    await firstStarted;
    await placeCaret(editor, "first ".length);
    await dispatchPlainPaste(editor, "a\n\nb");
    await page.waitForTimeout(40);
    expect(requests).toBe(1);
    release();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      "first a", "bsecond typed",
    ]);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Paste text", "Edit narration"]);
    await page.getByRole("button", { name: "Undo Paste text" }).click();
    await waitForNarrationText(page, projectId, seeded.rowId, "first second typed");
    await page.close();
  }, 90_000);

  it("rolls back a refused later paste substep, preserving the visible draft without save or Undo", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Refused paste rollback");
    const seeded = editableDocumentFixture(projectId, "start finish");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    let requests = 0;
    await page.route("**/authoring/command", async (route) => {
      if (route.request().method() !== "POST") return await route.continue();
      requests += 1;
      if (requests === 2) {
        await route.fulfill({ status: 200, contentType: "application/json",
          body: JSON.stringify({ ok: false, diagnostics: [{ message: "Deliberate second-step refusal" }] }) });
        return;
      }
      await route.continue();
    });
    await placeCaret(editor, "start ".length);
    await dispatchPlainPaste(editor, "a\n\nb");
    await expect.poll(async () => await page.locator("#save-status").textContent())
      .toContain("Deliberate second-step refusal");
    expect(requests).toBe(2);
    expect(await editorText(editor)).toBe("start a\n\nbfinish");
    expect((await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(["start finish"]);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Nothing to undo in this session"]);
    await page.locator("#discard-edit").waitFor({ state: "visible" });
    page.once("dialog", async (dialog) => await dialog.accept());
    await page.locator("#discard-edit").click();
    expect(await editorText(editor)).toBe("start finish");
    await page.close();
  }, 90_000);

  it("uses Return for saved paragraph breaks and paragraph Backspace without creating rows", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Paragraph keyboard project");
    const seeded = editableDocumentFixture(projectId, "alpha beta gamma");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, 6);
    await editor.press("Enter");
    await waitForNarrationText(page, projectId, seeded.rowId, "alpha \nbeta gamma");
    expect(await narrationRowsFromApi(page, projectId)).toHaveLength(1);
    await placeCaret(editor, 7);
    await editor.press("Backspace");
    await waitForNarrationText(page, projectId, seeded.rowId, "alpha beta gamma");
    await placeCaret(editor, "alpha beta gamma".length);
    await editor.press("Enter");
    await waitForNarrationText(page, projectId, seeded.rowId, "alpha beta gamma\n");
    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    expect(await editorText(editor)).toBe("alpha beta gamma\n");
    await page.close();
  }, 90_000);

  it("Tab splits and focuses the new row; immediate Backspace restores exact clipped visuals", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "D124 keyboard project");
    const text = "the harbor sleeps the harbor wakes";
    const seeded = editableDocumentFixture(projectId, text, true);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await placeCaret(editor, 18);
    await editor.press("Tab");
    await waitForNarrationCount(page, projectId, 2);
    const splitRows = await narrationRowsFromApi(page, projectId);
    expect(splitRows.map((row) => row.text)).toEqual(["the harbor sleeps", "the harbor wakes"]);
    const newRowId = splitRows[1]!.id;
    await expect.poll(async () => await page.evaluate(() =>
      document.activeElement?.closest("[data-row-id]")?.getAttribute("data-row-id"))).toBe(newRowId);
    await page.locator(`[data-row-id="${newRowId}"] [data-narration-editor]`).press("Backspace");
    await waitForNarrationCount(page, projectId, 1);
    const restored = await narrationRowFromApi(page, projectId, seeded.rowId);
    const initial = seeded.document.activeDraft.blocks.find((row) => row.id === seeded.rowId);
    expect(restored?.text).toBe(text);
    expect(restored?.tokens).toEqual(initial?.type === "narration" ? initial.tokens : []);
    expect(restored?.primaryVisualSequence).toEqual(initial?.type === "narration" ? initial.primaryVisualSequence : null);
    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.click();
    await waitForNarrationCount(page, projectId, 2);
    await undo.click();
    await waitForNarrationCount(page, projectId, 1);
    await page.close();
  }, 90_000);

  it("Tab at the end makes a valid blank row, and Backspace cannot join across a section", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Tab and section project");
    const seeded = multiNarrationDocumentFixture(projectId, ["first line", "second line"]);
    const sectionId = randomUUID();
    seeded.document.activeDraft.blocks.splice(1, 0, {
      type: "section", id: sectionId, orderKey: `section-${sectionId}`, title: "Second act", version: 1,
    });
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const first = page.locator(`[data-row-id="${seeded.rowIds[0]}"] [data-narration-editor]`);
    await placeCaret(first, "first line".length);
    await first.press("Tab");
    await waitForNarrationCount(page, projectId, 3);
    const rows = await narrationRowsFromApi(page, projectId);
    const blank = rows[1];
    expect(blank?.text).toBe("");
    expect(blank?.primaryVisualSequence?.slots[0]?.kind).toBe("content");
    await expect.poll(async () => await page.evaluate(() =>
      document.activeElement?.closest("[data-row-id]")?.getAttribute("data-row-id"))).toBe(blank?.id);
    await page.getByRole("button", { name: /^Undo\b/u }).click();
    await waitForNarrationCount(page, projectId, 2);
    const second = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await placeCaret(second, 0);
    await second.press("Backspace");
    await expect.poll(async () => await page.locator("#save-status").textContent())
      .toContain("Rows cannot be joined across a section break");
    expect((await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(["first line", "second line"]);
    await page.close();
  }, 90_000);

  it("requires an authentic immediately current server split proof for D124 replay", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "D124 server proof project");
    const seeded = editableDocumentFixture(projectId, "the harbor sleeps the harbor wakes", true);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const document = (await appRequest(page, `/authoring/projects/${projectId}/document`)).body as SavedDocument;
    const row = document.document.activeDraft.blocks.find((block) => block.id === seeded.rowId);
    if (!row || row.type !== "narration") throw new Error("missing D124 source row");
    const newRowId = randomUUID();
    const splitCommand = { kind: "split_row", rowId: row.id, newRowId, at: { beforeTokenId: row.tokens[3]!.id } };
    const split = (await appRequest(page, "/authoring/command", "POST", { document: document.document, command: splitCommand })).body as {
      ok: boolean; document: ScriptDocumentV2; splitProof: string;
    };
    expect(split.ok).toBe(true);
    expect(split.splitProof).toMatch(/^[0-9a-f]{64}$/u);
    const join = { kind: "join_rows", rowId: newRowId, direction: "previous", words: null };
    const forged = (await appRequest(page, "/authoring/command", "POST", {
      document: split.document, command: join, splitProof: "f".repeat(64),
    })).body as { ok: boolean; diagnostics: Array<{ code: string }> };
    expect(forged.ok).toBe(false);
    expect(forged.diagnostics[0]?.code).toBe("ROW_SPLIT_CONTEXT_STALE");
    const tampered = structuredClone(split.document);
    const tamperedRow = tampered.activeDraft.blocks.find((block) => block.id === seeded.rowId);
    if (!tamperedRow || tamperedRow.type !== "narration") throw new Error("missing split replay source row");
    tamperedRow.text += " forged";
    const changedDocument = (await appRequest(page, "/authoring/command", "POST", {
      document: tampered, command: join, splitProof: split.splitProof,
    })).body as { ok: boolean; diagnostics: Array<{ code: string }> };
    expect(changedDocument.ok).toBe(false);
    expect(changedDocument.diagnostics[0]?.code).toBe("ROW_SPLIT_CONTEXT_STALE");
    const changedRevisionDocument = structuredClone(split.document);
    changedRevisionDocument.rowEditRevision = (changedRevisionDocument.rowEditRevision ?? 0) + 1;
    const changedRevision = (await appRequest(page, "/authoring/command", "POST", {
      document: changedRevisionDocument, command: join, splitProof: split.splitProof,
    })).body as { ok: boolean; diagnostics: Array<{ code: string }> };
    expect(changedRevision.ok).toBe(false);
    expect(changedRevision.diagnostics[0]?.code).toBe("ROW_SPLIT_CONTEXT_STALE");
    const exact = (await appRequest(page, "/authoring/command", "POST", {
      document: split.document, command: join, splitProof: split.splitProof,
    })).body as { ok: boolean; document: ScriptDocumentV2 };
    expect(exact.ok).toBe(true);
    expect(exact.document.activeDraft.blocks).toEqual(document.document.activeDraft.blocks);

    const second = (await appRequest(page, "/authoring/command", "POST", {
      document: document.document, command: { ...splitCommand, newRowId: randomUUID() },
    })).body as { ok: boolean; document: ScriptDocumentV2; splitProof: string };
    expect(second.ok).toBe(true);
    const changed = (await appRequest(page, "/authoring/command", "POST", {
      document: second.document,
      command: { kind: "edit_narration_text", rowId: seeded.rowId, startOffset: 0, endOffset: 0,
        insertedText: "fresh ", editId: randomUUID() },
    })).body as { ok: boolean; document: ScriptDocumentV2 };
    expect(changed.ok).toBe(true);
    const stale = (await appRequest(page, "/authoring/command", "POST", {
      document: changed.document, command: { ...join, rowId: second.document.activeDraft.blocks.find(
        (block) => block.id !== seeded.rowId && block.type === "narration")?.id }, splitProof: second.splitProof,
    })).body as { ok: boolean; diagnostics: Array<{ code: string }> };
    expect(stale.ok).toBe(false);
    expect(stale.diagnostics[0]?.code).toBe("ROW_SPLIT_CONTEXT_STALE");
    await page.close();
  }, 90_000);

  it("creates, saves, reloads, restarts, exports, and preserves view settings", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const oldLaunchCode = host!.authoringLaunchCode!;
    const projectId = await createProject(page, origin, "Browser created project");
    const seeded = documentFixture(projectId);
    const initial = await appRequest(page, `/authoring/projects/${projectId}/document`);
    expect(initial.status).toBe(200);
    seeded.document.id = (initial.body as SavedDocument).document.id;
    const saved = await appRequest(page, `/authoring/projects/${projectId}/document`, "PUT", {
      expectedRevision: 0,
      clientMutationId: randomUUID(),
      document: seeded.document,
    });
    expect(saved.status).toBe(200);
    const savedAgain = await appRequest(page, `/authoring/projects/${projectId}/document`);
    expect((savedAgain.body as SavedDocument).document).toEqual(seeded.document);
    const staleSave = await appRequest(page, `/authoring/projects/${projectId}/document`, "PUT", {
      expectedRevision: 0,
      clientMutationId: randomUUID(),
      document: { ...seeded.document, title: "Stale script write" },
    });
    expect(staleSave.status).toBe(409);
    const afterConflict = await appRequest(page, `/authoring/projects/${projectId}/document`);
    expect((afterConflict.body as SavedDocument).document).toEqual(seeded.document);

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    expect(await page.locator("#script-rows").innerText()).toContain(seeded.firstRowText);
    expect(await page.locator("#script-title").textContent()).toBe("Browser saved script");
    expect(await page.locator('[data-row-kind="visual_only"] .visual-card__type').allTextContents())
      .toEqual(["Still image", "Footage"]);

    const authoringSize = page.locator("#authoring-size");
    const thumbnailSize = page.locator("#thumbnail-size");
    expect(await authoringSize.inputValue()).toBe("100");
    expect(await thumbnailSize.inputValue()).toBe("22");
    await setSlider(page, "#authoring-size", 150);
    await setSlider(page, "#thumbnail-size", 50);
    expect(await authoringSize.inputValue()).toBe("150");
    expect(await thumbnailSize.inputValue()).toBe("50");
    expect(await page.evaluate(() => getComputedStyle(document.documentElement)
      .getPropertyValue("--authoring-zoom").trim())).toBe("1.5");
    // Zoom applies only to the paper; the bar/slider retain the root rem scale.
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe("16px");
    expect(await page.evaluate(() => getComputedStyle(document.documentElement)
      .getPropertyValue("--thumbnail-scale").trim())).toBe("0.5");
    const thumbnail = page.locator(".visual-card__image").first();
    const thumbnailWidth = async () => await thumbnail.evaluate((element) => element.getBoundingClientRect().width);
    const halfWidth = await thumbnailWidth();
    expect(halfWidth).toBeGreaterThan(0);
    await setSlider(page, "#thumbnail-size", 100);
    await expect.poll(thumbnailWidth).toBeGreaterThan(halfWidth);
    await setSlider(page, "#thumbnail-size", 0);
    await expect.poll(thumbnailWidth).toBe(0);
    const card = page.locator(".visual-card[data-previewable='true']").first();
    await card.hover();
    const preview = card.locator(".visual-card__preview");
    await preview.waitFor({ state: "visible" });
    await page.mouse.move(0, 0);
    await preview.waitFor({ state: "hidden" });
    await card.focus();
    await preview.waitFor({ state: "visible" });
    await setSlider(page, "#thumbnail-size", 50);

    await page.locator("#project-title").fill("Saved project name");
    await page.locator("#project-title").blur();
    await expect.poll(async () => await page.locator("#save-status").textContent()).toBe("Saved");

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    expect(await authoringSize.inputValue()).toBe("150");
    expect(await thumbnailSize.inputValue()).toBe("50");
    expect(await page.locator("#project-title").inputValue()).toBe("Saved project name");
    expect(await page.locator("#script-rows").innerText()).toContain(seeded.firstRowText);

    await restartHostAndDatabase();
    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    expect(await page.locator("#project-title").inputValue()).toBe("Saved project name");
    expect(await page.locator("#script-rows").innerText()).toContain(seeded.firstRowText);

    const openPage = await context.newPage();
    const oldLaunchResponse = openPage.waitForResponse(response => response.url() === `${origin}/authoring/session`);
    await openPage.goto(`${origin}/#launch=${oldLaunchCode}`);
    expect((await oldLaunchResponse).status()).toBe(401);
    await openPage.locator("#open-script-link").fill(page.url());
    await openPage.locator("#open-project-form button[type=submit]").click();
    await openPage.locator("#script-rows").waitFor({ state: "visible" });
    expect(await openPage.locator("#script-title").textContent()).toBe("Browser saved script");
    expect(await openPage.locator("#script-rows").innerText()).toContain(seeded.firstRowText);

    const exportedPath = join(directory, "browser-export.json");
    const env = {
      ...process.env,
      VERA_STT_QA_PORT: String(config.port),
      VERA_STT_QA_AUTHORING_TOKEN: authoringToken,
    };
    const exportCommand = ["--prefix", REPOSITORY_ROOT, "run", "export:script", "--", projectId, "browser-export.json"];
    const exportOptions = {
      cwd: directory,
      env,
      timeout: 60_000,
      maxBuffer: 4 * 1024 * 1024,
    };
    await execFile("npm", exportCommand, exportOptions);
    await expect(execFile("npm", exportCommand, exportOptions)).rejects.toMatchObject({ code: 73 });
    expect((await readdir(directory)).some((entry) => entry.startsWith(".vera-export-"))).toBe(false);
    const persisted = await appRequest(page, `/authoring/projects/${projectId}/document`);
    expect(persisted.status).toBe(200);
    expect(JSON.parse(await readFile(exportedPath, "utf8"))).toEqual(
      (persisted.body as SavedDocument).document,
    );
    await execFile("npm", ["run", "validate:script", "--", exportedPath], {
      cwd: REPOSITORY_ROOT,
      env,
      timeout: 60_000,
      maxBuffer: 4 * 1024 * 1024,
    });
  }, 120_000);

  it("shows a failed save with its draft intact, retries the same mutation, and exposes stale-tab conflicts", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const firstPage = await context.newPage();
    const conflictPage = await context.newPage();
    const projectId = await createProject(firstPage, origin, "Conflict test project");
    const projectUrl = `${origin}/?project=${projectId}`;
    await conflictPage.goto(projectUrl);
    await conflictPage.locator("#script-rows").waitFor({ state: "visible" });

    await firstPage.locator("#project-title").fill("Name saved in first tab");
    await firstPage.locator("#project-title").blur();
    await expect.poll(async () => await firstPage.locator("#save-status").textContent()).toBe("Saved");
    const unsavedName = "Typed in stale tab";
    await conflictPage.locator("#project-title").fill(unsavedName);
    await conflictPage.locator("#project-title").blur();
    await expect.poll(async () => await conflictPage.locator("#save-status").textContent())
      .toBe("A newer project name was saved elsewhere. Your unsaved name is still here.");
    expect(await conflictPage.locator("#project-title").inputValue()).toBe(unsavedName);
    await conflictPage.locator("#conflict-open-saved").waitFor({ state: "visible" });

    const retryPage = await context.newPage();
    const retryProjectId = await createProject(retryPage, origin, "Failed save project");
    const mutationIds: string[] = [];
    await retryPage.route(`**/authoring/projects/${retryProjectId}`, async (route) => {
      const request = route.request();
      if (request.method() !== "PATCH") return await route.continue();
      const body = request.postDataJSON() as { clientMutationId: string };
      mutationIds.push(body.clientMutationId);
      if (mutationIds.length === 1) {
        return await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ error: "service_unavailable" }),
        });
      }
      return await route.continue();
    });
    const failedDraft = "Keep this name until the retry works";
    await retryPage.locator("#project-title").fill(failedDraft);
    await retryPage.locator("#project-title").blur();
    await expect.poll(async () => await retryPage.locator("#save-status").textContent())
      .toBe("Couldn’t save the project name. Your unsaved name is still here.");
    expect(await retryPage.locator("#project-title").inputValue()).toBe(failedDraft);
    await retryPage.locator("#retry-save").waitFor({ state: "visible" });
    await retryPage.locator("#retry-save").click();
    await expect.poll(async () => await retryPage.locator("#save-status").textContent()).toBe("Saved");
    expect(mutationIds).toHaveLength(2);
    expect(mutationIds[1]).toBe(mutationIds[0]);
    expect(await retryPage.locator("#project-title").inputValue()).toBe(failedDraft);
  }, 90_000);

  it("edits repeated and Unicode narration, keeps visual anchors, undoes by keyboard and button, and reloads", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Narration editing project");
    const initialText = "the harbor sleeps the harbor wakes";
    const seeded = editableDocumentFixture(projectId, initialText, true);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    await editor.waitFor({ state: "visible" });
    expect(await editorText(editor)).toBe(initialText);

    const repeatedEdit = "the harbor sleeps the old harbor wakes";
    await editor.fill(repeatedEdit);
    await waitForNarrationText(page, projectId, seeded.rowId, repeatedEdit);
    const repeatedRow = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(repeatedRow?.tokens.map((token) => token.value)).toEqual([
      "the", "harbor", "sleeps", "the", "old", "harbor", "wakes",
    ]);
    const secondVisual = repeatedRow?.primaryVisualSequence?.slots[1];
    expect(secondVisual?.kind).toBe("content");
    if (secondVisual?.kind === "content") {
      expect(secondVisual.boundaryBefore).toMatchObject({
        kind: "spoken_word",
        anchor: { tokenId: seeded.anchorTokenId, quotedWord: "harbor" },
      });
    }

    const unicodeEdit = `${repeatedEdit} שלום 東京`;
    await editor.fill(unicodeEdit);
    await waitForNarrationText(page, projectId, seeded.rowId, unicodeEdit);
    const unicodeRow = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(unicodeRow?.tokens.map((token) => token.value).slice(-2)).toEqual(["שלום", "東京"]);

    await editor.press(process.platform === "darwin" ? "Meta+Z" : "Control+Z");
    await waitForNarrationText(page, projectId, seeded.rowId, repeatedEdit);
    expect(await editorText(editor)).toBe(repeatedEdit);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationText(page, projectId, seeded.rowId, initialText);
    expect(await editorText(editor)).toBe(initialText);

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const reloadedRow = page.locator(`[data-row-id="${seeded.rowId}"]`);
    await expect.poll(async () => await editorText(reloadedRow.locator("[data-narration-editor]"))).toBe(initialText);
    expect(await reloadedRow.locator(".visual-card").count()).toBe(2);
    await page.close();
  }, 90_000);

  it("adjusts Folded Letter brackets by keyboard and pointer; whole OC crosses in one Undo", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    await page.setViewportSize({ width: 1024, height: 768 });
    const projectId = await createProject(page, origin, "Folded Letter bracket controls");
    const seeded = foldedLetterRangeFixture(projectId);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    const end = row.locator(`[data-range-slot="${seeded.firstSlotId}"][data-range-edge="end"]`);
    const second = row.locator(`[data-range-slot="${seeded.secondSlotId}"][data-range-edge="start"]`);
    await expect(end).toHaveAttribute("data-word-index", "9");
    await expect(second).toHaveAttribute("data-word-index", "18");
    expect(await editorText(editor)).toBe(seeded.firstRowText);
    expect(await row.locator(".narration-range-overlay").getAttribute("contenteditable")).toBe("false");
    const originalRow = await narrationRowFromApi(page, projectId, seeded.rowId);
    if (!originalRow?.primaryVisualSequence) throw new Error("missing original Folded Letter sequence");
    const originalSequence = originalRow.primaryVisualSequence;

    // Keyboard arrows only preview. Enter sends exactly one range command.
    await end.focus();
    await end.press("ArrowLeft");
    await expect(end).toHaveAttribute("data-word-index", "8");
    expect(await narrationRowFromApi(page, projectId, seeded.rowId)).toEqual(originalRow);
    await end.press("Enter");
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))
      ?.primaryVisualSequence?.version).toBe(originalSequence.version + 1);
    const narrowed = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(narrowed?.primaryVisualSequence?.slots.find((slot) => slot.id === seeded.secondSlotId))
      .toEqual(originalSequence.slots.find((slot) => slot.id === seeded.secondSlotId));
    const saved = (await appRequest(page, `/authoring/projects/${projectId}/document`)).body as SavedDocument;
    const projected = await appRequest(page, "/authoring/projection", "POST", { document: saved.document });
    const projectedRow = (projected.body as { projection: { rows: Array<{ blockId: string; cards: Array<{
      kind: string; framing: string | null; startTokenIndex: number | null; endTokenIndexExclusive: number | null;
    }> }> } }).projection.rows.find((item) => item.blockId === seeded.rowId);
    expect(projectedRow?.cards.map((item) => [item.kind, item.startTokenIndex, item.endTokenIndexExclusive]))
      .toEqual([["visual", 0, 8], ["on_camera", 8, 18], ["visual", 18, 26]]);
    expect(projectedRow?.cards[1]?.framing).toBe("tight");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Adjust visual range"]);
    await page.getByRole("button", { name: "Undo Adjust visual range" }).click();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))?.primaryVisualSequence)
      .toEqual(originalSequence);
    await expect(end).toHaveAttribute("data-word-index", "9");

    // Pointer snapping reaches the last OC word; the model removes that whole
    // passage without shifting the untouched second still.
    const target = await editor.evaluate((node, offset) => {
      const walker = node.ownerDocument.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      let remaining = offset;
      let text = walker.nextNode();
      while (text && remaining > (text.textContent?.length ?? 0)) {
        remaining -= text.textContent?.length ?? 0;
        text = walker.nextNode();
      }
      if (!text) throw new Error("missing target word");
      const range = node.ownerDocument.createRange();
      range.setStart(text, remaining);
      range.collapse(true);
      const rect = range.getBoundingClientRect();
      return { x: rect.x, y: rect.y + rect.height / 2 };
    }, originalRow.tokens[17]!.endOffset);
    const bounds = await end.boundingBox();
    if (!bounds) throw new Error("bracket has no pointer target");
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    await page.mouse.down();
    await page.mouse.move(target.x, target.y, { steps: 10 });
    await expect(end).toHaveAttribute("data-word-index", "18");
    await page.mouse.up();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))
      ?.primaryVisualSequence?.version).toBe(originalSequence.version + 1);
    const expanded = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(expanded?.primaryVisualSequence?.slots.some((slot) => slot.id === seeded.cameraSlotId)).toBe(false);
    expect(expanded?.primaryVisualSequence?.slots.find((slot) => slot.id === seeded.secondSlotId))
      .toEqual(originalSequence.slots.find((slot) => slot.id === seeded.secondSlotId));
    expect(await row.locator('.visual-card[data-kind="on-camera"]').count()).toBe(0);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Adjust visual range"]);
    await page.getByRole("button", { name: "Undo Adjust visual range" }).click();
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))?.primaryVisualSequence)
      .toEqual(originalSequence);
    expect(await editorText(editor)).toBe(seeded.firstRowText);

    // Bracket decorations don't enter the editable UTF-16 text or selection.
    await selectText(editor, 2, 15);
    expect(await editor.evaluate((node) => node.ownerDocument.getSelection()?.toString())).toBe("folded letter");
    expect(await editorText(editor)).toBe(seeded.firstRowText);
    await page.close();
  }, 90_000);

  it("keeps punctuation and UTF-16 caret offsets editable underneath non-text brackets", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Unicode bracket narration");
    const text = "Raincoat 🧥 glows. The child found a chalk-crescent beside the workbench!";
    const seeded = editableDocumentFixture(projectId, text);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    const lastHandle = row.locator('[data-range-edge="end"]');
    await lastHandle.waitFor({ state: "visible" });
    expect(await editorText(editor)).toBe(text);
    const emojiStart = text.indexOf("🧥");
    await selectText(editor, emojiStart, emojiStart + 2);
    expect(await editor.evaluate((node) => node.ownerDocument.getSelection()?.toString())).toBe("🧥");
    await lastHandle.focus();
    await lastHandle.press("ArrowLeft");
    await lastHandle.press("Escape");
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Nothing to undo in this session"]);
    await placeCaret(editor, emojiStart + 2);
    await editor.press("x");
    const changed = text.slice(0, emojiStart + 2) + "x" + text.slice(emojiStart + 2);
    await waitForNarrationText(page, projectId, seeded.rowId, changed);
    expect(await editorText(editor)).toBe(changed);
    await page.close();
  }, 90_000);

  it("clears narration without deleting its row or visual, then restores both with Undo after reload", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Clear narration project");
    const initialText = "clear this narration";
    const seeded = editableDocumentFixture(projectId, initialText);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    await editor.fill("");
    await waitForNarrationText(page, projectId, seeded.rowId, "");
    await expect.poll(async () => await editorText(editor)).toBe("");
    expect(await page.locator(`[data-row-id="${seeded.rowId}"]`).count()).toBe(1);
    expect(await row.locator(".visual-card").count()).toBe(1);
    const cleared = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(cleared?.tokens).toEqual([]);
    expect(cleared?.primaryVisualSequence?.slots).toHaveLength(1);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationText(page, projectId, seeded.rowId, initialText);
    expect(await editorText(editor)).toBe(initialText);
    expect(await row.locator(".visual-card").count()).toBe(1);

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const reloadedRow = page.locator(`[data-row-id="${seeded.rowId}"]`);
    await expect.poll(async () => await editorText(reloadedRow.locator("[data-narration-editor]"))).toBe(initialText);
    expect(await reloadedRow.locator(".visual-card").count()).toBe(1);
    await page.close();
  }, 90_000);

  it("keeps a cleared multi-visual row editable after reload and retyping without changing visual identity or order", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Clear multi-visual narration project");
    const initialText = "clear this multi visual narration";
    const seeded = editableDocumentFixture(projectId, initialText, true);
    const seededRow = seeded.document.activeDraft.blocks.find((block) => block.id === seeded.rowId);
    if (!seededRow || seededRow.type !== "narration" || !seededRow.primaryVisualSequence) {
      throw new Error("browser multi-visual fixture has no narration sequence");
    }
    const visualSlots = seededRow.primaryVisualSequence.slots.filter(
      (slot) => slot.kind === "content" && slot.payload.kind === "visual",
    );
    if (visualSlots.length !== 2 || visualSlots.some((slot) => slot.kind !== "content" || slot.payload.kind !== "visual")) {
      throw new Error("browser multi-visual fixture did not create two visual slots");
    }
    visualSlots.forEach((slot, index) => {
      if (slot.kind !== "content" || slot.payload.kind !== "visual") return;
      const startFrame = index * 25;
      slot.payload.selectedSourceRange = { startFrame, durationFrames: 25 };
      slot.payload.sourceUsage = { ...slot.payload.sourceUsage, sourceInFrame: startFrame };
    });
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    await editor.waitFor({ state: "visible" });
    const initial = await narrationRowFromApi(page, projectId, seeded.rowId);
    if (!initial?.primaryVisualSequence) throw new Error("saved multi-visual fixture did not load");
    const initialVisualIds = initial.primaryVisualSequence.slots.flatMap((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" ? [slot.payload.payloadId] : []);
    expect(initialVisualIds).toHaveLength(2);

    const rowFromDocument = async () => {
      const response = await appRequest(page, `/authoring/projects/${projectId}/document`);
      if (response.status !== 200) return null;
      return (response.body as SavedDocument).document.activeDraft.blocks.find((block) => block.id === seeded.rowId) ?? null;
    };
    const visualOnlyIds = (block: ScriptDocumentV2["activeDraft"]["blocks"][number]) =>
      block.type === "visual_only"
        ? [block.payload.payloadId, ...(block.additionalVisuals ?? []).map((visual) => visual.payload.payloadId)]
        : [];

    await editor.fill("");
    await expect.poll(async () => (await rowFromDocument())?.type ?? null).toBe("visual_only");
    const cleared = await rowFromDocument();
    if (!cleared || cleared.type !== "visual_only") throw new Error("cleared narration did not become a visual-only row");
    expect(cleared.clearedNarration).toBeTruthy();
    expect(visualOnlyIds(cleared)).toEqual(initialVisualIds);
    expect(await row.locator(".visual-card").count()).toBe(2);

    await page.reload();
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const reloadedRow = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const reloadedEditor = reloadedRow.locator("[data-narration-editor]");
    await expect.poll(async () => await editorText(reloadedEditor)).toBe("");
    expect(await reloadedRow.locator(".visual-card").count()).toBe(2);
    const reloaded = await rowFromDocument();
    if (!reloaded || reloaded.type !== "visual_only") throw new Error("cleared row did not survive reload");
    expect(reloaded.clearedNarration).toBeTruthy();
    expect(visualOnlyIds(reloaded)).toEqual(initialVisualIds);

    const retypedText = "retyped after clear";
    await reloadedEditor.fill(retypedText);
    await waitForNarrationText(page, projectId, seeded.rowId, retypedText);
    const retyped = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(retyped?.text).toBe(retypedText);
    const retypedVisualIds = [...(retyped?.primaryVisualSequence?.slots.flatMap((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" ? [slot.payload.payloadId] : []) ?? []),
    ...(retyped?.unattachedVisuals ?? []).map((visual) => visual.payload.payloadId)];
    expect(retypedVisualIds).toEqual(initialVisualIds);
    await reloadedEditor.blur();
    await expect.poll(async () => await reloadedRow.locator(".visual-card").count()).toBe(3);
    await page.close();
  }, 90_000);

  it("keeps a refused narration draft visible, then recovers after explicit discard", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Narration refusal recovery project");
    const initialText = "keep the original narration";
    const seeded = editableDocumentFixture(projectId, initialText);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    let commandRequests = 0;
    await page.route("**/authoring/command", async (route) => {
      if (route.request().method() !== "POST") return await route.continue();
      commandRequests += 1;
      if (commandRequests === 1) {
        return await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: false,
            diagnostics: [{ code: "TEST_REFUSAL", message: "The test narration edit was refused." }],
          }),
        });
      }
      return await route.continue();
    });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    const refusedText = "this draft must remain visible";
    await editor.fill(refusedText);
    await expect.poll(async () => await page.locator("#save-status").textContent()).toContain("The test narration edit was refused.");
    const discard = page.getByRole("button", { name: "Discard unsaved text" });
    await discard.waitFor({ state: "visible" });
    await expect.poll(async () => await discard.isEnabled()).toBe(true);
    expect(await editorText(editor)).toBe(refusedText);
    expect(commandRequests).toBe(1);

    page.once("dialog", async (dialog) => await dialog.accept());
    await discard.click();
    await discard.waitFor({ state: "hidden" });
    await expect.poll(async () => await editorText(editor)).toBe(initialText);
    await expect.poll(async () => await page.locator("#save-status").textContent()).toBe("Saved");

    const recoveredText = "editing works after discard";
    await editor.fill(recoveredText);
    await waitForNarrationText(page, projectId, seeded.rowId, recoveredText);
    expect(await editorText(editor)).toBe(recoveredText);
    expect(commandRequests).toBe(2);
    await page.close();
  }, 90_000);

  it("moves focus to the row's preview card when Escape leaves an edited narration cell", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Narration Escape focus project");
    const seeded = editableDocumentFixture(projectId, "focus starts here");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    const preview = row.locator(".visual-card").first();
    await editor.fill("edited before Escape");
    await waitForNarrationText(page, projectId, seeded.rowId, "edited before Escape");
    await editor.focus();
    await editor.press("Escape");
    await expect.poll(async () => await page.evaluate(() => document.activeElement?.matches(".visual-card") ?? false)).toBe(true);
    expect(await preview.evaluate((element) => document.activeElement === element)).toBe(true);
    await page.close();
  }, 90_000);

  it("hides a stale stage-direction toolbar when the narration selection collapses", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Collapsed narration selection project");
    const seeded = editableDocumentFixture(projectId, "select this passage");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await editor.waitFor({ state: "visible" });
    const stageButton = page.getByRole("button", { name: /^Make stage direction\b/u });
    await editor.evaluate((element) => {
      const selection = element.ownerDocument.getSelection();
      const range = element.ownerDocument.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
      element.ownerDocument.dispatchEvent(new Event("selectionchange", { bubbles: true }));
    });
    await stageButton.waitFor({ state: "visible" });

    await editor.evaluate((element) => {
      const selection = element.ownerDocument.getSelection();
      selection?.collapse(element, 0);
      element.ownerDocument.dispatchEvent(new Event("selectionchange", { bubbles: true }));
    });
    await stageButton.waitFor({ state: "hidden" });
    await page.close();
  }, 90_000);

  it("keeps a stale tab's narration draft visible when another tab saves first", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const firstPage = await context.newPage();
    const stalePage = await context.newPage();
    const projectId = await createProject(firstPage, origin, "Narration conflict project");
    const seeded = editableDocumentFixture(projectId, "shared starting narration");
    await saveDocumentFixture(firstPage, projectId, seeded.document);
    const projectUrl = `${origin}/?project=${projectId}`;
    await firstPage.goto(projectUrl);
    await firstPage.locator("#script-rows").waitFor({ state: "visible" });
    await stalePage.goto(projectUrl);
    await stalePage.locator("#script-rows").waitFor({ state: "visible" });

    const firstEditor = firstPage.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    const staleEditor = stalePage.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await firstEditor.waitFor({ state: "visible" });
    await staleEditor.waitFor({ state: "visible" });
    const savedText = "saved by the first tab";
    await firstEditor.fill(savedText);
    await waitForNarrationText(firstPage, projectId, seeded.rowId, savedText);

    const staleText = "kept in the stale tab";
    await staleEditor.fill(staleText);
    await expect.poll(async () => await stalePage.locator("#save-status").textContent())
      .toBe("A newer script was saved elsewhere. Your unsaved changes are still here.");
    expect(await editorText(staleEditor)).toBe(staleText);
    expect(await stalePage.locator("#conflict-open-saved").isVisible()).toBe(true);
    await waitForNarrationText(firstPage, projectId, seeded.rowId, savedText);
    await firstPage.close();
    await stalePage.close();
  }, 90_000);

  it("refuses a stale cross-row save without losing the second tab's narration draft", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const firstPage = await context.newPage();
    const stalePage = await context.newPage();
    const projectId = await createProject(firstPage, origin, "Cross-row conflict project");
    const seeded = multiNarrationDocumentFixture(projectId, ["first row starts here", "second row starts here"]);
    await saveDocumentFixture(firstPage, projectId, seeded.document);
    const projectUrl = `${origin}/?project=${projectId}`;
    await firstPage.goto(projectUrl);
    await firstPage.locator("#script-rows").waitFor({ state: "visible" });
    await stalePage.goto(projectUrl);
    await stalePage.locator("#script-rows").waitFor({ state: "visible" });

    const firstEditor = firstPage.locator(`[data-row-id="${seeded.rowIds[0]}"] [data-narration-editor]`);
    const staleEditor = stalePage.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await firstEditor.waitFor({ state: "visible" });
    await staleEditor.waitFor({ state: "visible" });
    const firstText = "first tab saved row one";
    await firstEditor.fill(firstText);
    await waitForNarrationText(firstPage, projectId, seeded.rowIds[0]!, firstText);

    const staleText = "stale tab kept row two";
    await staleEditor.fill(staleText);
    await expect.poll(async () => await stalePage.locator("#save-status").textContent())
      .toBe("A newer script was saved elsewhere. Your unsaved changes are still here.");
    expect(await editorText(staleEditor)).toBe(staleText);
    const persistedRows = await narrationRowsFromApi(firstPage, projectId);
    expect(persistedRows.map((row) => row.text)).toEqual([firstText, "second row starts here"]);
    await firstPage.close();
    await stalePage.close();
  }, 90_000);

  it("serializes cross-row edits while the first command is held, then undoes only the latest edit", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Held command project");
    const initialTexts = ["row A starts here", "row B starts here"] as const;
    const seeded = multiNarrationDocumentFixture(projectId, initialTexts);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const firstEditor = page.locator(`[data-row-id="${seeded.rowIds[0]}"] [data-narration-editor]`);
    const secondEditor = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await firstEditor.waitFor({ state: "visible" });
    await secondEditor.waitFor({ state: "visible" });

    let commandCount = 0;
    let firstCommandStartedResolve: () => void = () => {};
    const firstCommandStarted = new Promise<void>((resolve) => { firstCommandStartedResolve = resolve; });
    let releaseFirstCommand: () => void = () => {};
    const firstCommandReleased = new Promise<void>((resolve) => { releaseFirstCommand = resolve; });
    await page.route("**/authoring/command", async (route) => {
      if (route.request().method() !== "POST") return await route.continue();
      commandCount += 1;
      if (commandCount === 1) {
        firstCommandStartedResolve();
        await firstCommandReleased;
      }
      await route.continue();
    });

    const firstText = "row A saved first";
    const secondText = "row B queued second";
    await firstEditor.fill(firstText);
    await firstCommandStarted;
    expect(commandCount).toBe(1);
    await secondEditor.fill(secondText);
    // The second edit is queued behind the held command, not applied to the
    // stale pre-command document or silently dropped while the first is open.
    await page.waitForTimeout(25);
    expect(commandCount).toBe(1);

    releaseFirstCommand();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      firstText, secondText,
    ]);
    expect(await editorText(firstEditor)).toBe(firstText);
    expect(await editorText(secondEditor)).toBe(secondText);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual([
      firstText, initialTexts[1],
    ]);
    await page.close();
  }, 90_000);

  it("commits rapid sequential keystrokes and waits for IME composition to end", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Rapid narration project");
    const seeded = editableDocumentFixture(projectId, "rapid");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const row = page.locator(`[data-row-id="${seeded.rowId}"]`);
    let editor = row.locator("[data-narration-editor]");
    await editor.waitFor({ state: "visible" });
    await editor.click();
    await editor.press("End");
    await page.keyboard.type(" fast input", { delay: 0 });
    const rapidText = "rapid fast input";
    await expect.poll(async () => (await narrationRowFromApi(page, projectId, seeded.rowId))?.text ?? null,
      { timeout: 10_000 }).toBe(rapidText);

    editor = row.locator("[data-narration-editor]");
    await editor.evaluate((element) => {
      element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
      element.textContent = `${element.textContent ?? ""} 東京`;
      element.dispatchEvent(new InputEvent("input", {
        bubbles: true, inputType: "insertCompositionText", data: " 東京", isComposing: true,
      }));
    });
    await page.waitForTimeout(50);
    expect((await narrationRowFromApi(page, projectId, seeded.rowId))?.text).toBe(rapidText);

    await editor.evaluate((element) => {
      element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: " 東京" }));
    });
    await waitForNarrationText(page, projectId, seeded.rowId, `${rapidText} 東京`);
    await page.close();
  }, 90_000);

  it("replaces one emoji with another through IME without splitting its surrogate pair", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Emoji composition project");
    const initialText = "say 😀 now";
    const seeded = editableDocumentFixture(projectId, initialText);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await editor.waitFor({ state: "visible" });
    await editor.evaluate((element) => {
      const document = element.ownerDocument;
      const before = element.textContent ?? "";
      const oldEmoji = "😀";
      const start = before.indexOf(oldEmoji);
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let textNode = walker.nextNode();
      let cursor = 0;
      while (textNode && (start < cursor || start + oldEmoji.length > cursor + (textNode.textContent?.length ?? 0))) {
        cursor += textNode.textContent?.length ?? 0;
        textNode = walker.nextNode();
      }
      if (!textNode || start < 0) throw new Error("emoji fixture text was not rendered");
      const selection = document.getSelection();
      const range = document.createRange();
      range.setStart(textNode, start - cursor);
      range.setEnd(textNode, start - cursor + oldEmoji.length);
      selection?.removeAllRanges();
      selection?.addRange(range);
      element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
      element.textContent = before.replace(oldEmoji, "😃");
      element.dispatchEvent(new InputEvent("input", {
        bubbles: true, inputType: "insertCompositionText", data: "😃", isComposing: true,
      }));
      element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: "😃" }));
    });
    await waitForNarrationText(page, projectId, seeded.rowId, "say 😃 now");
    const saved = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(saved?.tokens.map((token) => token.value)).toEqual(["say", "😃", "now"]);
    await page.close();
  }, 90_000);

  it("adds and deletes rows, with one Undo restoring each row operation", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Row operation project");
    const seeded = editableDocumentFixture(projectId, "keep this row");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    await waitForNarrationCount(page, projectId, 1);

    const addRow = page.getByRole("button", { name: "Add row" }).last();
    await addRow.scrollIntoViewIfNeeded();
    await addRow.hover();
    await addRow.click();
    await waitForNarrationCount(page, projectId, 2);
    let rows = await narrationRowsFromApi(page, projectId);
    let addedRowId = rows.find((row) => row.id !== seeded.rowId)?.id;
    expect(addedRowId).toBeTruthy();

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationCount(page, projectId, 1);

    const secondAddRow = page.getByRole("button", { name: "Add row" }).last();
    await secondAddRow.scrollIntoViewIfNeeded();
    await secondAddRow.hover();
    await secondAddRow.click();
    await waitForNarrationCount(page, projectId, 2);
    rows = await narrationRowsFromApi(page, projectId);
    addedRowId = rows.find((row) => row.id !== seeded.rowId)?.id;
    expect(addedRowId).toBeTruthy();
    if (!addedRowId) return;

    const addedRow = page.locator(`[data-row-id="${addedRowId}"]`);
    const rowActions = addedRow.locator("[data-row-action-trigger]");
    await addedRow.hover();
    await rowActions.click();
    const deleteRow = addedRow.getByRole("menuitem", { name: "Delete row" });
    await deleteRow.waitFor({ state: "visible" });
    page.once("dialog", async (dialog) => await dialog.accept());
    await deleteRow.click();
    await waitForNarrationCount(page, projectId, 1);

    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationCount(page, projectId, 2);
    rows = await narrationRowsFromApi(page, projectId);
    expect(rows.map((row) => row.id)).toContain(addedRowId);
    await page.close();
  }, 90_000);

  it("selects a contiguous row range, deletes it, and restores the range with Undo", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Range selection project");
    const seeded = multiNarrationDocumentFixture(projectId, ["first row", "second row", "third row"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    await waitForNarrationCount(page, projectId, seeded.rowIds.length);

    const firstRow = page.locator(`[data-row-id="${seeded.rowIds[0]}"]`);
    const secondRow = page.locator(`[data-row-id="${seeded.rowIds[1]}"]`);
    await firstRow.hover();
    await firstRow.locator("[data-row-action-trigger]").click();
    await firstRow.getByRole("menuitem", { name: "Select range" }).click();
    await secondRow.locator(".narration-cell").click();

    const deleteGroup = page.getByRole("button", { name: "Delete selected rows" });
    await deleteGroup.waitFor({ state: "visible" });
    page.once("dialog", async (dialog) => await dialog.accept());
    await deleteGroup.click();
    await waitForNarrationCount(page, projectId, 1);
    expect((await narrationRowsFromApi(page, projectId)).map((row) => row.id)).toEqual([seeded.rowIds[2]]);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationCount(page, projectId, seeded.rowIds.length);
    expect((await narrationRowsFromApi(page, projectId)).map((row) => row.id)).toEqual(seeded.rowIds);
    await page.close();
  }, 90_000);

  it("reorders rows by dragging the row handle and restores their order with Undo", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Row reorder project");
    const seeded = multiNarrationDocumentFixture(projectId, ["first row", "second row", "third row"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    await waitForNarrationCount(page, projectId, seeded.rowIds.length);

    const sourceRow = page.locator(`[data-row-id="${seeded.rowIds[1]}"]`);
    const targetRow = page.locator(`[data-row-id="${seeded.rowIds[0]}"]`);
    await sourceRow.hover();
    const sourceHandle = sourceRow.locator("[data-row-action-trigger]");
    await sourceHandle.dragTo(targetRow, { targetPosition: { x: 20, y: 2 } });
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.id)).toEqual([
      seeded.rowIds[1], seeded.rowIds[0], seeded.rowIds[2],
    ]);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.id)).toEqual(seeded.rowIds);
    await page.close();
  }, 90_000);

  it("offers selection structure actions in accepted order for first, last, whole and interior words", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Selection menu availability");
    const seeded = multiNarrationDocumentFixture(projectId, ["previous words", "alpha beta gamma delta", "following words"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    const visible = () => page.locator(`[data-row-id="${seeded.rowIds[1]}"] .narration-editor__actions button:visible`).allTextContents();

    await selectText(editor, 0, "alpha beta".length);
    await expect.poll(visible).toEqual(["Make stage direction", "Split into new row", "Join to previous row"]);
    await selectText(editor, "gamma".length + "alpha beta ".length, "alpha beta gamma delta".length);
    await expect.poll(visible).toEqual(["Make stage direction", "Split into new row", "Join to next row"]);
    await selectText(editor, 0, "alpha beta gamma delta".length);
    await expect.poll(visible).toEqual(["Make stage direction", "Join to previous row", "Join to next row"]);
    await selectText(editor, "alpha ".length, "alpha beta gamma".length);
    await expect.poll(visible).toEqual(["Make stage direction"]);
    await page.close();
  }, 90_000);

  it.each([
    ["first", 0, "alpha beta".length, ["previous words", "alpha beta", "gamma delta", "following words"]],
    ["last", "alpha beta ".length, "alpha beta gamma delta".length, ["previous words", "alpha beta", "gamma delta", "following words"]],
  ])("splits selected %s words with one Undo and focuses the new row", async (_edge, start, end, expected) => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Selection split and focus");
    const seeded = multiNarrationDocumentFixture(projectId, ["previous words", "alpha beta gamma delta", "following words"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await selectText(editor, start, end);
    await page.getByRole("button", { name: "Split into new row" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(expected);
    const rows = await narrationRowsFromApi(page, projectId);
    const newId = rows.find((row) => !seeded.rowIds.includes(row.id))!.id;
    await expect.poll(async () => page.locator(`[data-row-id="${newId}"] [data-narration-editor]`)
      .evaluate((element) => element === element.ownerDocument.activeElement)).toBe(true);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Split selection"]);
    await page.getByRole("button", { name: "Undo Split selection" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text))
      .toEqual(["previous words", "alpha beta gamma delta", "following words"]);
    await page.close();
  }, 90_000);

  it.each([
    ["previous", 0, "alpha beta".length, ["previous words alpha beta", "gamma delta", "following words"]],
    ["next", "alpha beta ".length, "alpha beta gamma delta".length, ["previous words", "alpha beta", "gamma delta following words"]],
    ["whole", 0, "alpha beta gamma delta".length, ["previous words alpha beta gamma delta", "following words"]],
  ])("joins selected %s words with one Undo", async (direction, start, end, expected) => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Selection partial join");
    const seeded = multiNarrationDocumentFixture(projectId, ["previous words", "alpha beta gamma delta", "following words"]);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await selectText(editor, start, end);
    await page.getByRole("button", { name: `Join to ${direction === "next" ? "next" : "previous"} row` }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text)).toEqual(expected);
    await expect.poll(async () => page.locator(`[data-row-id="${seeded.rowIds[direction === "next" ? 2 : 0]}"] [data-narration-editor]`)
      .evaluate((element) => element === element.ownerDocument.activeElement)).toBe(true);
    expect(await page.locator("#undo-history li").allTextContents()).toEqual(["Join selected words"]);
    await page.getByRole("button", { name: "Undo Join selected words" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text))
      .toEqual(["previous words", "alpha beta gamma delta", "following words"]);
    await page.close();
  }, 90_000);

  it("disables a join across a section break with an explanation and leaves Undo untouched", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Cross section selection");
    const seeded = multiNarrationDocumentFixture(projectId, ["before heading", "alpha beta gamma", "after words"]);
    const sectionId = randomUUID();
    seeded.document.activeDraft.blocks.splice(1, 0, {
      type: "section", id: sectionId, orderKey: `section-${sectionId}`, title: "Another section", version: 1,
    });
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowIds[1]}"] [data-narration-editor]`);
    await selectText(editor, 0, "alpha beta".length);
    const join = page.getByRole("button", { name: /Join to previous row/u });
    await expect.poll(async () => join.isVisible()).toBe(true);
    expect(await join.isDisabled()).toBe(true);
    expect(await join.getAttribute("title")).toBe("Rows cannot be joined across a section break.");
    expect(await page.locator("#undo").isDisabled()).toBe(true);
    await page.getByRole("button", { name: "Split into new row" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text))
      .toEqual(["before heading", "alpha beta", "gamma", "after words"]);
    await page.getByRole("button", { name: "Undo Split selection" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text))
      .toEqual(["before heading", "alpha beta gamma", "after words"]);
    await page.close();
  }, 90_000);

  it("carries the anchored visual once and keeps stage directions at their start-word boundary", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Visual selection carry");
    const seeded = editableDocumentFixture(projectId, "alpha beta gamma delta echo foxtrot", true);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await selectText(editor, 0, "alpha beta gamma delta echo".length);
    await page.getByRole("button", { name: "Split into new row" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).map((row) => row.text))
      .toEqual(["alpha beta gamma delta echo", "foxtrot"]);
    const rows = await narrationRowsFromApi(page, projectId);
    const anchored = rows.filter((row) => row.primaryVisualSequence?.slots.some((slot) =>
      slot.kind === "content" && slot.boundaryBefore?.kind === "spoken_word" && slot.boundaryBefore.anchor.tokenId === seeded.anchorTokenId));
    expect(anchored).toHaveLength(1);
    expect(anchored[0]?.text).toBe("alpha beta gamma delta echo");
    const visualIds = rows.flatMap((row) => row.primaryVisualSequence?.slots
      .filter((slot) => slot.kind === "content").map((slot) => slot.id) ?? []);
    expect(new Set(visualIds).size).toBe(visualIds.length);
    await page.getByRole("button", { name: "Undo Split selection" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(page, projectId)).length).toBe(1);
    await page.close();

    const stagePage = await context.newPage();
    const stageId = await createProject(stagePage, origin, "Stage selection boundary");
    const stage = multiNarrationDocumentFixture(stageId, ["before row", "alpha [quiet wind] omega", "after row"]);
    const stageRow = stage.document.activeDraft.blocks.find((block) => block.id === stage.rowIds[1]);
    if (!stageRow || stageRow.type !== "narration") throw new Error("missing stage row");
    stageRow.tokens = stageRow.tokens.map((token) => ({ ...token, ...(token.value === "quiet" || token.value === "wind" ? { spoken: false } : {}) }));
    await saveDocumentFixture(stagePage, stageId, stage.document);
    await stagePage.goto(`${origin}/?project=${stageId}`);
    const stageEditor = stagePage.locator(`[data-row-id="${stage.rowIds[1]}"] [data-narration-editor]`);
    await selectText(stageEditor, 0, "alpha [quiet".length);
    await stagePage.getByRole("button", { name: "Split into new row" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(stagePage, stageId)).map((row) => row.text))
      .toEqual(["before row", "alpha [quiet wind]", "omega", "after row"]);
    const moved = (await narrationRowsFromApi(stagePage, stageId))[1]!;
    expect(moved.tokens.filter((token) => token.spoken === false).map((token) => token.value)).toEqual(["quiet", "wind"]);
    await stagePage.getByRole("button", { name: "Undo Split selection" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(stagePage, stageId)).length).toBe(3);
    await selectText(stageEditor, "alpha [quiet ".length, "alpha [quiet wind] omega".length);
    await stagePage.getByRole("button", { name: "Split into new row" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(stagePage, stageId)).map((row) => row.text))
      .toEqual(["before row", "alpha [quiet wind]", "omega", "after row"]);
    const unchanged = await narrationRowFromApi(stagePage, stageId, stage.rowIds[1]!);
    expect(unchanged?.text).toBe("alpha [quiet wind]");
    expect(unchanged?.tokens.filter((token) => token.spoken === false).map((token) => token.value)).toEqual(["quiet", "wind"]);
    await stagePage.getByRole("button", { name: "Undo Split selection" }).click();
    await expect.poll(async () => (await narrationRowsFromApi(stagePage, stageId)).length).toBe(3);
    await stagePage.close();
  }, 90_000);

  it("converts a selected narration passage to a stage direction and undoes it", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Stage direction project");
    const initialText = "spoken aside";
    const seeded = editableDocumentFixture(projectId, initialText);
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await editor.waitFor({ state: "visible" });
    await editor.evaluate((element) => {
      const selection = element.ownerDocument.getSelection();
      const range = element.ownerDocument.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
      element.ownerDocument.dispatchEvent(new Event("selectionchange", { bubbles: true }));
    });
    const stageButton = page.getByRole("button", { name: /^Make stage direction\b/u });
    await stageButton.waitFor({ state: "visible" });
    await stageButton.click();
    await waitForNarrationText(page, projectId, seeded.rowId, `[${initialText}]`);
    const direction = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(direction?.tokens.every((token) => token.spoken === false)).toBe(true);

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationText(page, projectId, seeded.rowId, initialText);
    const restored = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(restored?.tokens.some((token) => token.spoken === false)).toBe(false);
    await page.close();
  }, 90_000);

  it("types a bracketed cue into an empty row, then classifies its selected cue as a stage direction", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Empty bracketed cue project");
    const seeded = editableDocumentFixture(projectId, "existing row");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const addRow = page.getByRole("button", { name: "Add row" }).last();
    await addRow.scrollIntoViewIfNeeded();
    await addRow.hover();
    await addRow.click();
    await waitForNarrationCount(page, projectId, 2);
    const rows = await narrationRowsFromApi(page, projectId);
    const emptyRowId = rows.find((row) => row.id !== seeded.rowId)?.id;
    expect(emptyRowId).toBeTruthy();
    if (!emptyRowId) return;

    const row = page.locator(`[data-row-id="${emptyRowId}"]`);
    const editor = row.locator("[data-narration-editor]");
    await editor.waitFor({ state: "visible" });
    await editor.click();
    let typed = "";
    for (const character of ["[", "c", "u", "e", "]"]) {
      await page.keyboard.type(character);
      typed += character;
      await waitForNarrationText(page, projectId, emptyRowId, typed);
    }
    expect(await editorText(editor)).toBe("[cue]");

    await editor.evaluate((element) => {
      const selection = element.ownerDocument.getSelection();
      const range = element.ownerDocument.createRange();
      const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      let cursor = 0;
      const point = (wanted: number) => {
        while (node && wanted > cursor + (node.textContent?.length ?? 0)) {
          cursor += node.textContent?.length ?? 0;
          node = walker.nextNode();
        }
        if (!node) throw new Error("cue selection exceeded rendered editor text");
        return { node, offset: wanted - cursor };
      };
      const start = point(1);
      const end = point(4);
      range.setStart(start.node, start.offset);
      range.setEnd(end.node, end.offset);
      selection?.removeAllRanges();
      selection?.addRange(range);
      element.ownerDocument.dispatchEvent(new Event("selectionchange", { bubbles: true }));
    });
    const stageButton = page.getByRole("button", { name: /^Make stage direction\b/u });
    await stageButton.waitFor({ state: "visible" });
    await stageButton.click();
    await waitForNarrationText(page, projectId, emptyRowId, "[cue]");
    const classified = await narrationRowFromApi(page, projectId, emptyRowId);
    expect(classified?.tokens.map((token) => [token.value, token.spoken])).toEqual([["cue", false]]);
    await expect.poll(async () => await editor.locator(".narration-token--direction").allTextContents()).toEqual(["cue"]);
    await page.close();
  }, 90_000);

  it("uses text/plain dataTransfer for native replacement input", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Native replacement project");
    const seeded = editableDocumentFixture(projectId, "replace this passage");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });

    const editor = page.locator(`[data-row-id="${seeded.rowId}"] [data-narration-editor]`);
    await editor.waitFor({ state: "visible" });
    await editor.click();
    await editor.evaluate((element) => {
      const selection = element.ownerDocument.getSelection();
      const range = element.ownerDocument.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
      const dataTransfer = new DataTransfer();
      dataTransfer.setData("text/plain", "native replacement");
      const event = new InputEvent("beforeinput", {
        bubbles: true,
        cancelable: true,
        inputType: "insertReplacementText",
        data: null,
      });
      Object.defineProperty(event, "dataTransfer", { configurable: true, value: dataTransfer });
      element.dispatchEvent(event);
      if (!event.defaultPrevented) throw new Error("native replacement was not intercepted");
    });
    await waitForNarrationText(page, projectId, seeded.rowId, "native replacement");
    const saved = await narrationRowFromApi(page, projectId, seeded.rowId);
    expect(saved?.tokens.map((token) => token.value)).toEqual(["native", "replacement"]);
    expect(await editorText(editor)).toBe("native replacement");
    await page.close();
  }, 90_000);
});
