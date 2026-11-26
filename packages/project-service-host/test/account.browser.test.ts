import { chromium, type BrowserContext, type Page } from "playwright";
import { expect, it } from "vitest";
import { accountFixture } from "./account-fixture.js";

it("Chromium: account roles, Producer management, demotion/discard/promotion without replay, access-ended and signed-out states", async () => {
  const h = await accountFixture();
  const browser = await chromium.launch({ headless: true });
  const contexts: BrowserContext[] = [];
  const errors: string[] = [];
  const pageFor = async (who?: string) => {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } }); contexts.push(context);
    if (who) await context.addCookies([{ name: "qa_account", value: h.cookies[who]!.slice(11),
      url: h.origin, httpOnly: true, sameSite: "Strict" }]);
    const page = await context.newPage(); page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(h.origin + `/?project=${h.projectId}`);
    return page;
  };
  const visible = async (page: Page, selector: string) => {
    await page.locator(selector).waitFor({ state: "visible", timeout: 15_000 });
  };
  try {
    const owner = await pageFor("owner");
    await visible(owner, "#authoring-view");
    await owner.getByRole("button", { name: "Manage access", exact: true }).click();
    await visible(owner, "#account-member-code");
    await expect.poll(() => owner.locator(".account-panel__dialog li").count()).toBe(3);
    await owner.getByLabel("Member code", { exact: true }).fill(h.actors.outsider!.principalId);
    await owner.getByLabel("New member role").selectOption("viewer");
    await owner.getByRole("button", { name: "Add member", exact: true }).click();
    await expect.poll(() => owner.locator(".account-panel__dialog li").count()).toBe(4);
    const outsiderRow = owner.locator(".account-panel__dialog li").filter({ hasText: h.actors.outsider!.principalId });
    await outsiderRow.locator("select").selectOption("editor");
    await outsiderRow.getByRole("button", { name: "Change role", exact: true }).click();
    await expect.poll(async () => {
      const response = await h.request(`/authoring/projects/${h.projectId}/access`, "outsider");
      return (await response.json() as { role: string }).role;
    }).toBe("editor");
    owner.once("dialog", (dialog) => { void dialog.accept(); });
    await outsiderRow.getByRole("button", { name: "Remove", exact: true }).click();
    await expect.poll(() => owner.locator(".account-panel__dialog li").count()).toBe(3);
    await owner.keyboard.press("Escape");
    await expect.poll(() => owner.getByRole("button", { name: "Manage access", exact: true }).evaluate((e) => e === document.activeElement)).toBe(true);
    const viewer = await pageFor("viewer");
    await visible(viewer, "#authoring-view");
    expect(await viewer.locator("#account-panel").innerText()).toContain("Viewer · read only");
    expect(await viewer.locator('[contenteditable="true"]').count()).toBe(0);
    await viewer.setViewportSize({ width: 1024, height: 768 });
    expect(await viewer.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await viewer.locator("#account-panel").innerText()).toContain("Viewer · read only");
    expect(await viewer.getByRole("button", { name: "Manage access", exact: true }).count()).toBe(0);
    expect(await viewer.getByRole("button", { name: "Sort rows", exact: true }).count()).toBe(0);
    const editor = await pageFor("editor"); await visible(editor, '[data-narration-editor]');
    expect(await editor.getByRole("button", { name: "Manage access", exact: true }).count()).toBe(0);
    const text = editor.locator('[data-narration-editor]').first();
    const original = await text.innerText();
    // Hold a real outgoing command while the Producer changes current authority.
    let release!: () => void;
    let arrived!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    const commandArrived = new Promise<void>((resolve) => { arrived = resolve; });
    await editor.route("**/authoring/command", async (route) => { arrived(); await held; await route.continue(); });
    await text.fill(original + " REFUSED SYNTHETIC TEXT");
    await commandArrived;
    const memberPath = `/authoring/projects/${h.projectId}/members/${h.actors.editor!.principalId}`;
    const change = async (role: string | null) => {
      const response = await h.request(memberPath, "owner", { method: "PATCH",
        headers: { "content-type": "application/json" }, body: JSON.stringify({ role }) });
      expect(response.status).toBe(200);
    };
    await change("viewer");
    await visible(editor, "#account-notice");
    release();
    await expect.poll(async () => await editor.locator('[contenteditable="true"]').count()).toBe(0);
    expect(await text.innerText()).toContain("REFUSED SYNTHETIC TEXT");
    await change("editor");
    // Promotion must not remove the explicit-discard barrier.
    await expect.poll(async () => await editor.locator("#account-panel").innerText()).toContain("Editor");
    expect(await editor.locator('[contenteditable="true"]').count()).toBe(0);
    await editor.getByRole("button", { name: "Discard unsaved edits" }).click();
    await editor.locator("#account-notice").waitFor({ state: "hidden" });
    await visible(editor, '[data-narration-editor]');
    expect(await editor.locator("#script-rows").innerText()).not.toContain("REFUSED SYNTHETIC TEXT");
    expect(JSON.stringify((await h.documents.getDocument(h.projectId, h.actors.owner!)).document)).not.toContain("REFUSED SYNTHETIC TEXT");
    // Hide both role changes from the polling UI and hold an actual document PUT.
    let releasePoll!: () => void;
    const pollGate = new Promise<void>((resolve) => { releasePoll = resolve; });
    await editor.route("**/access", async (route) => { await pollGate; await route.continue(); });
    let releasePut!: () => void, putArrived!: () => void;
    const putGate = new Promise<void>((resolve) => { releasePut = resolve; });
    const putting = new Promise<void>((resolve) => { putArrived = resolve; });
    await editor.route("**/document", async (route) => {
      if (route.request().method() === "PUT") { putArrived(); await putGate; }
      await route.continue();
    });
    const pendingEditor = editor.locator('[data-narration-editor]').first();
    await pendingEditor.fill((await pendingEditor.innerText()) + " OLD LEASE TEXT");
    await putting;
    await change("viewer"); await change("editor");
    const refused = editor.waitForResponse((response) => response.request().method() === "PUT" && response.status() === 403);
    releasePut(); await refused; releasePoll();
    await visible(editor, "#account-notice");
    expect(JSON.stringify((await h.documents.getDocument(h.projectId, h.actors.owner!)).document)).not.toContain("OLD LEASE TEXT");
    await editor.getByRole("button", { name: "Discard unsaved edits" }).click();
    await editor.locator("#account-notice").waitFor({ state: "hidden" });
    expect(await editor.locator("#script-rows").innerText()).not.toContain("OLD LEASE TEXT");
    await change(null);
    await visible(editor, "#account-access-ended");
    expect(await editor.locator("#authoring-view").isVisible()).toBe(false);
    await editor.reload(); await visible(editor, "#account-access-ended");
    const outsider = await pageFor("outsider"); await visible(outsider, "#account-access-ended");
    const signedOut = await pageFor();
    await visible(signedOut, "#account-panel");
    expect(await signedOut.locator("#account-panel").innerText()).toContain("Signed out");
    expect(await signedOut.getByRole("button", { name: "Sign in", exact: true }).isVisible()).toBe(true);
    expect(await viewer.evaluate(() => localStorage.getItem("vera.authoring.sessionProof"))).toBeNull();
    const stored = await viewer.evaluate(() => JSON.stringify(localStorage));
    for (const secret of Object.values(h.bearers)) expect(stored).not.toContain(secret.slice(7));
    expect(errors).toEqual([]);
    await viewer.screenshot({ path: "/tmp/vera-72-viewer.png", fullPage: true });
  } finally {
    for (const context of contexts) await context.close();
    await browser.close(); await h.stop();
  }
}, 120_000);


it("Chromium: unconfigured account provider shows an honest unavailable state", async () => {
  const h = await accountFixture(true);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(h.origin);
    await page.waitForFunction(() => document.querySelector("#account-panel")?.textContent?.includes("Account sign-in unavailable"));
    expect(await page.getByRole("button", { name: "Sign in", exact: true }).count()).toBe(0);
    expect(await page.locator("#authoring-view").isVisible()).toBe(false);
  } finally { await browser.close(); await h.stop(); }
}, 90_000);
