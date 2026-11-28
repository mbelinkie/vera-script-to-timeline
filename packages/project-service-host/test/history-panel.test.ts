import { afterEach, describe, expect, it, vi } from "vitest";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright";
import { canPerformProjectAction, type ProjectAction, type ProjectRole } from "@vera/project-authorization";
import { createProjectApiHandler, type DocumentHistoryPage, type CheckpointPage,
  type CreateCheckpointInput, type ApproveCheckpointInput, type CheckpointCreateReceipt } from "@vera/project-documents";
import { harness, initialProject } from "../../project-documents/test/helpers.js";
import { createHistoryControls, type HistoryApi, type HistoryContext } from "../browser/history-panel.js";

vi.setConfig({ testTimeout: 90_000 });
const cleanups: Array<() => Promise<void>> = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0)) await cleanup(); });
const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}` as const;
const actions: ProjectAction[] = ["view_history", "edit_document", "create_checkpoint", "approve_checkpoint"];
const capabilities = (role: ProjectRole) => actions.filter(action => canPerformProjectAction(role, action));

async function fixture() {
  const h = await harness();
  cleanups.push(async () => { await h.db.close(); });
  const initial = initialProject(id(1));
  initial.document.id = id(2); initial.clientRequestId = id(3);
  await h.service.createProject(h.owner, initial);
  await h.auth.changeMembership(initial.projectId, h.owner, h.editor.principalId, "editor");
  await h.auth.changeMembership(initial.projectId, h.owner, h.viewer.principalId, "viewer");
  const first = await h.service.putDocument(initial.projectId, h.editor, {
    expectedRevision: 0, clientMutationId: id(4), document: { ...initial.document, title: "Editor revision" },
  });
  await h.service.putDocument(initial.projectId, h.owner, {
    expectedRevision: 1, clientMutationId: id(5), document: { ...initial.document, title: "Producer revision" },
  });
  const handler = createProjectApiHandler({ authorization: h.auth, documents: h.service,
    identity: { authenticate: (request) => Promise.resolve({
      issuer: "https://trusted.suite.test", subject: request.headers.get("x-test-subject")!,
    }) } });
  let subject = "viewer";
  async function request<T>(path: string, input?: unknown): Promise<T> {
    const response = await handler(new Request("https://synthetic.test/v1/projects/" + path, {
      method: input === undefined ? "GET" : "POST",
      headers: { "x-test-subject": subject, "content-type": "application/json" },
      ...(input === undefined ? {} : { body: JSON.stringify(input) }),
    }));
    if (!response.ok) throw Object.assign(new Error("HTTP " + response.status), { status: response.status });
    return await response.json() as T;
  }
  const api: HistoryApi = {
    listDocumentRevisions: (project, query) => request(project + "/history?limit=" + query.limit +
      (query.beforeRevision === undefined ? "" : "&beforeRevision=" + query.beforeRevision)),
    listCheckpoints: (project, query) => request(project + "/checkpoints?limit=" + query.limit +
      (query.beforeCheckpointId === undefined ? "" : "&beforeCheckpointId=" + query.beforeCheckpointId)),
    getCheckpoint: (project, checkpoint) => request(project + "/checkpoints/" + checkpoint),
    createCheckpoint: (project, input) => request(project + "/checkpoints", input),
    approveCheckpoint: (project, checkpoint, input) => request(project + "/checkpoints/" + checkpoint + "/approve", input),
  };
  return { ...h, initial, first, api, as: (next: string) => { subject = next; } };
}

describe("history controls using stored, attributed HTTP fixtures", () => {
  it("mounts the standalone controls in Chromium and hands exact saved selections to the child callbacks", async () => {
    const f = await fixture();
    const projectId = f.initial.projectId;
    f.as("editor");
    await f.api.createCheckpoint(projectId, { checkpointId: id(40), clientMutationId: id(41), name: "First cut", sourceRevision: 1 });
    const browser = await chromium.launch({ headless: true });
    try {
      const page = await browser.newPage({ viewport: { width: 380, height: 800 } });
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.exposeFunction("listRevisions", f.api.listDocumentRevisions.bind(f.api));
      await page.exposeFunction("listCheckpoints", f.api.listCheckpoints.bind(f.api));
      await page.exposeFunction("getCheckpoint", f.api.getCheckpoint.bind(f.api));
      await page.exposeFunction("createCheckpoint", f.api.createCheckpoint.bind(f.api));
      await page.exposeFunction("approveCheckpoint", f.api.approveCheckpoint.bind(f.api));
      const selections: unknown[] = [], restores: unknown[] = [];
      await page.exposeFunction("recordComparison", (selection: unknown) => { selections.push(selection); });
      await page.exposeFunction("recordRestore", (selection: unknown) => { restores.push(selection); });
      await page.route("http://localhost/**", async route => {
        const path = new URL(route.request().url()).pathname;
        if (path === "/history-panel.js" || path === "/history-panel.css") {
          await route.fulfill({ contentType: path.endsWith(".js") ? "text/javascript" : "text/css", body: await readFile(new URL("../browser" + path, import.meta.url), "utf8") });
        } else {
          await route.fulfill({ contentType: "text/html", body: `<!doctype html><link rel="stylesheet" href="/history-panel.css"><main id="panel"></main>
            <script type="module">
              import { mountHistoryPanel } from '/history-panel.js';
              const api = { listDocumentRevisions: listRevisions, listCheckpoints, getCheckpoint, createCheckpoint, approveCheckpoint };
              window.panel = mountHistoryPanel({ root: document.querySelector('#panel'), api, pageSize: 1,
                onCompare: ({mount, checkpoint, toRevision}) => { mount.textContent = 'Comparison child'; void recordComparison({checkpoint, toRevision}); },
                onRestore: selection => { void recordRestore(selection); } });
            </script>` });
        }
      });
      await page.goto("http://localhost/");
      const set = async (role: ProjectRole, savedHead: number | null) => {
        f.as(role === "producer" ? "owner" : role);
        await page.evaluate(async context => {
          await (window as unknown as {panel: {setContext(context: HistoryContext): Promise<void>}}).panel.setContext(context);
        }, { projectId, capabilities: capabilities(role), savedHead });
      };
      await set("viewer", 2);
      const checkpoint = page.locator(`[data-checkpoint-id="${id(40)}"]`);
      expect(await checkpoint.innerText()).toContain("First cut");
      expect(await checkpoint.innerText()).toContain(f.editor.principalId);
      expect(await checkpoint.innerText()).toContain("Not approved");
      expect(await page.getByRole("button", { name: "Save checkpoint" }).count()).toBe(0);
      expect(await page.getByRole("button", { name: "Approve", exact: true }).count()).toBe(0);
      expect(await page.getByRole("button", { name: "Restore", exact: true }).count()).toBe(0);
      await page.getByRole("button", { name: "Load more revisions" }).click();
      await expect.poll(() => page.locator("[data-revision]").count()).toBe(2);
      expect(await page.locator('[data-revision="2"]').innerText()).toContain(f.owner.principalId);
      expect(await page.locator('[data-revision="1"]').innerText()).toContain(f.editor.principalId);
      await checkpoint.getByRole("button", { name: "Compare with now" }).click();
      await expect.poll(() => selections.length).toBe(1);
      expect(selections[0]).toMatchObject({ checkpoint: { checkpointId: id(40), sourceRevision: 1, sourceDigest: f.first.digest, document: { title: "Editor revision" } }, toRevision: 2 });
      expect(await page.locator(".history-panel__comparison").innerText()).toBe("Comparison child");
      await set("editor", null);
      expect(await page.locator(".history-panel__comparison").innerText()).toBe("");
      expect(await page.getByRole("button", { name: "Save checkpoint" }).isDisabled()).toBe(true);
      await set("editor", 2);
      await checkpoint.getByRole("button", { name: "Restore" }).click();
      await expect.poll(() => restores.length).toBe(1);
      expect(restores[0]).toEqual({ projectId, checkpointId: id(40) });
      expect((await f.service.getDocument(projectId, f.editor)).revision).toBe(2);
      await page.getByRole("textbox").fill("Second cut");
      await page.getByRole("button", { name: "Save checkpoint" }).click();
      await expect.poll(() => page.locator("[data-checkpoint-id]").first().innerText()).toContain("Second cut");
      expect(await page.getByRole("button", { name: "Approve", exact: true }).count()).toBe(0);
      await set("producer", 2);
      const newest = page.locator("[data-checkpoint-id]").first();
      await newest.getByRole("button", { name: "Approve", exact: true }).click();
      await expect.poll(() => newest.innerText()).toContain("Approved · " + f.owner.principalId);
      expect(await newest.getByRole("button", { name: "Approve", exact: true }).count()).toBe(0);
      // Seed an already-restored revision through the real fixture service;
      // this panel only reads its provenance and never performs a restore.
      await f.service.restoreCheckpoint(projectId, f.editor, id(40), { expectedRevision: 2, clientMutationId: id(42) });
      await set("producer", 3);
      await page.getByRole("button", { name: "Refresh history" }).click();
      await expect.poll(() => page.locator('[data-revision="3"]').innerText()).toContain("Restored checkpoint " + id(40) + " · revision 1");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(errors).toEqual([]);
    } finally { await browser.close(); }
  });

  it("pages stable identities, gates actions and retries an identical committed checkpoint/approval after a lost response", async () => {
    const f = await fixture();
    const projectId = f.initial.projectId;
    let nextId = 100;
    const createCalls: CreateCheckpointInput[] = [], approveCalls: ApproveCheckpointInput[] = [];
    const controls = createHistoryControls({ pageSize: 1, makeId: () => id(nextId++), api: {
      ...f.api,
      createCheckpoint: async (project, input) => {
        createCalls.push(structuredClone(input));
        const receipt = await f.api.createCheckpoint(project, input);
        if (createCalls.length === 1) throw new Error("Lost response");
        return receipt;
      },
      approveCheckpoint: async (project, checkpoint, input) => {
        approveCalls.push(structuredClone(input));
        const receipt = await f.api.approveCheckpoint(project, checkpoint, input);
        if (approveCalls.length === 1) throw new Error("Lost response");
        return receipt;
      },
    } });
    const set = (role: ProjectRole, savedHead: number | null) => {
      f.as(role === "producer" ? "owner" : role);
      controls.setContext({ projectId, capabilities: capabilities(role), savedHead });
    };
    set("viewer", 2);
    await controls.refresh();
    expect(controls.snapshot().history.items.map(r => [r.revision, r.actorId])).toEqual([[2, f.owner.principalId]]);
    expect(controls.snapshot().history.cursor).toBe(2);
    await controls.loadHistory();
    expect(controls.snapshot().history.items.map(r => [r.revision, r.actorId])).toEqual([[2, f.owner.principalId], [1, f.editor.principalId]]);
    expect(controls.snapshot().history.items[1]?.digest).toBe(f.first.digest);
    expect(controls.snapshot().history.items[1]?.createdAt).toMatch(/Z$/u);
    expect(controls.snapshot().checkpoints.cursor).toBeNull();
    expect(controls.snapshot().canCreate).toBe(false);
    await controls.create("Viewer not allowed"); await controls.approve(id(100));
    expect(createCalls).toHaveLength(0); expect(approveCalls).toHaveLength(0);

    set("editor", null); expect(controls.snapshot().canCreate).toBe(false);
    await controls.create("Unsaved"); expect(createCalls).toHaveLength(0);
    set("editor", 1); await controls.create("Cut for Dana");
    expect(controls.snapshot().mutation).toMatchObject({ busy: false, pending: { kind: "create", checkpointId: id(100) } });
    expect(controls.snapshot().mutation.error).toContain("Try again");
    expect(createCalls[0]).toEqual({ checkpointId: id(100), clientMutationId: id(101), name: "Cut for Dana", sourceRevision: 1 });
    set("editor", 2);
    await controls.retry();
    expect(createCalls[1]).toEqual(createCalls[0]);
    expect(controls.snapshot().mutation).toMatchObject({ error: null, pending: null });
    const saved = await f.api.getCheckpoint(projectId, id(100));
    expect(saved).toMatchObject({ sourceRevision: 1, sourceDigest: f.first.digest, document: { title: "Editor revision" }, approval: null });
    await controls.create("Later cut");
    expect(controls.snapshot().checkpoints.items.map(c => c.checkpointId)).toEqual([id(102)]);
    expect(controls.snapshot().checkpoints.cursor).toBe(id(102));
    await controls.loadCheckpoints();
    expect(controls.snapshot().checkpoints.items.map(c => c.checkpointId)).toEqual([id(102), id(100)]);
    expect(controls.snapshot().checkpoints.cursor).toBeNull();
    await controls.approve(id(100)); expect(approveCalls).toHaveLength(0);

    set("producer", 2);
    await controls.approve(id(100));
    expect(controls.snapshot().mutation.pending?.checkpointId).toBe(id(100));
    await controls.retry();
    expect(approveCalls[1]).toEqual(approveCalls[0]);
    await controls.loadCheckpoints();
    const approval = controls.snapshot().checkpoints.items.find(c => c.checkpointId === id(100))?.approval;
    expect(approval?.approvedBy).toBe(f.owner.principalId);
    expect(approval?.approvedAt).toMatch(/Z$/u);
    await controls.approve(id(100)); expect(approveCalls).toHaveLength(2);
    const approved = await f.api.getCheckpoint(projectId, id(100));
    expect(approved.document).toEqual(saved.document); expect(approved.sourceDigest).toBe(saved.sourceDigest);
    await f.service.putDocument(projectId, f.editor, {
      expectedRevision: 2, clientMutationId: id(6), document: { ...f.initial.document, title: "Later live edit" },
    });
    expect((await f.service.getDocument(projectId, f.owner)).revision).toBe(3);
    const afterEdit = await f.api.getCheckpoint(projectId, id(100));
    expect(afterEdit).toEqual(approved);
  });

  it("ignores delayed prior project pages and mutations; shows bounded read errors and retries", async () => {
    const f = await fixture();
    const project = f.initial.projectId;
    const other = initialProject(id(20));
    await f.service.createProject(f.owner, other);
    f.as("owner");
    let release!: (page: DocumentHistoryPage) => void;
    const oldPage = new Promise<DocumentHistoryPage>(resolve => { release = resolve; });
    let fail = true;
    const controls = createHistoryControls({ api: {
      ...f.api,
      listDocumentRevisions: (p, query) => p === project ? oldPage : f.api.listDocumentRevisions(p, query),
      listCheckpoints: (p, query) => {
        if (fail) { fail = false; return Promise.reject(new Error("offline")); }
        return f.api.listCheckpoints(p, query);
      },
    } });
    controls.setContext({ projectId: project, capabilities: capabilities("producer"), savedHead: 2 });
    const loading = controls.loadHistory();
    expect(controls.snapshot().history.loading).toBe(true);
    controls.setContext({ projectId: other.projectId, capabilities: capabilities("producer"), savedHead: 0 });
    await controls.refresh();
    expect(controls.snapshot().checkpoints.error).toMatch(/Couldn’t load/u);
    await controls.loadCheckpoints();
    expect(controls.snapshot().checkpoints).toMatchObject({ cursor: null, items: [], error: null });
    release(await f.api.listDocumentRevisions(project, { limit: 20 }));
    await loading;
    expect(controls.snapshot().history.items.map(r => r.revision)).toEqual([0]);
    expect(controls.snapshot().context.projectId).toBe(other.projectId);

    let finish!: (page: CheckpointPage) => void;
    const delayed = new Promise<CheckpointPage>(resolve => { finish = resolve; });
    const stale = createHistoryControls({ api: { ...f.api, listCheckpoints: () => delayed } });
    stale.setContext({ projectId: project, capabilities: capabilities("viewer"), savedHead: 2 });
    const reading = stale.loadCheckpoints();
    stale.setContext({ projectId: null, capabilities: [], savedHead: null });
    finish({ projectId: project, checkpoints: [], nextBeforeCheckpointId: null });
    await reading;
    expect(stale.snapshot().checkpoints.cursor).toBeUndefined();

    let deliver!: (receipt: CheckpointCreateReceipt) => void;
    const heldMutation = new Promise<CheckpointCreateReceipt>(resolve => { deliver = resolve; });
    let deliverNew!: (receipt: CheckpointCreateReceipt) => void;
    const newMutation = new Promise<CheckpointCreateReceipt>(resolve => { deliverNew = resolve; });
    const changing = createHistoryControls({ api: { ...f.api, createCheckpoint: p => p === project ? heldMutation : newMutation }, makeId: (() => {
      let next = 200; return () => id(next++);
    })() });
    changing.setContext({ projectId: project, capabilities: capabilities("producer"), savedHead: 2 });
    const creating = changing.create("Old project");
    expect(changing.snapshot().mutation.busy).toBe(true);
    changing.setContext({ projectId: other.projectId, capabilities: capabilities("producer"), savedHead: 0 });
    await changing.refresh();
    const creatingNew = changing.create("New project");
    deliver(await f.api.createCheckpoint(project, { checkpointId: id(200), clientMutationId: id(201), name: "Old project", sourceRevision: 2 }));
    await creating;
    expect(changing.snapshot().context.projectId).toBe(other.projectId);
    expect(changing.snapshot().mutation).toMatchObject({ busy: true, pending: { checkpointId: id(202) } });
    expect(changing.snapshot().checkpoints.items).toEqual([]);
    deliverNew(await f.api.createCheckpoint(other.projectId, { checkpointId: id(202), clientMutationId: id(203), name: "New project", sourceRevision: 0 }));
    await creatingNew;
    expect(changing.snapshot().mutation).toMatchObject({ busy: false, pending: null, error: null });
    expect(changing.snapshot().checkpoints.items.map(c => c.checkpointId)).toEqual([id(202)]);
  });
});
