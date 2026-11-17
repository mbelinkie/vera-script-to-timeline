import { execFile as execFileCallback } from "node:child_process";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { chmod, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
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
import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
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
  return { document, firstRowText: narration.text };
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
    await thumbnailSize.focus();
    await page.keyboard.press("Tab");
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
    await openPage.goto(origin);
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
    await execFile("npm", ["run", "export:script", "--", projectId, exportedPath], {
      cwd: REPOSITORY_ROOT,
      env,
      timeout: 60_000,
      maxBuffer: 4 * 1024 * 1024,
    });
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
});
