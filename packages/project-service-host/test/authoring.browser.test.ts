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
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe("24px");
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
    await waitForNarrationText(page, projectId, seeded.rowId, rapidText);

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

  it("adds and deletes rows, with one Undo restoring each row operation", async () => {
    const origin = `http://127.0.0.1:${config.port}`;
    const page = await context.newPage();
    const projectId = await createProject(page, origin, "Row operation project");
    const seeded = editableDocumentFixture(projectId, "keep this row");
    await saveDocumentFixture(page, projectId, seeded.document);
    await page.goto(`${origin}/?project=${projectId}`);
    await page.locator("#script-rows").waitFor({ state: "visible" });
    await waitForNarrationCount(page, projectId, 1);

    await page.getByRole("button", { name: "Add row" }).first().click();
    await waitForNarrationCount(page, projectId, 2);
    let rows = await narrationRowsFromApi(page, projectId);
    let addedRowId = rows.find((row) => row.id !== seeded.rowId)?.id;
    expect(addedRowId).toBeTruthy();

    const undo = page.getByRole("button", { name: /^Undo\b/u });
    await undo.waitFor({ state: "visible" });
    expect(await undo.isEnabled()).toBe(true);
    await undo.click();
    await waitForNarrationCount(page, projectId, 1);

    await page.getByRole("button", { name: "Add row" }).first().click();
    await waitForNarrationCount(page, projectId, 2);
    rows = await narrationRowsFromApi(page, projectId);
    addedRowId = rows.find((row) => row.id !== seeded.rowId)?.id;
    expect(addedRowId).toBeTruthy();
    if (!addedRowId) return;

    const addedRow = page.locator(`[data-row-id="${addedRowId}"]`);
    await addedRow.locator("[data-row-action-trigger]").click();
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
});
