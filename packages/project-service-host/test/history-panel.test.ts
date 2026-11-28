import { afterEach, describe, expect, it, vi } from "vitest";
import { canPerformProjectAction, type ProjectAction, type ProjectRole } from "@vera/project-authorization";
import { createProjectApiHandler, type DocumentHistoryPage, type CheckpointPage,
  type CreateCheckpointInput, type ApproveCheckpointInput, type CheckpointCreateReceipt } from "@vera/project-documents";
import { harness, initialProject } from "../../project-documents/test/helpers.js";
import { createHistoryControls, type HistoryApi } from "../browser/history-panel.js";

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
    expect(controls.snapshot().history.items[1]).toMatchObject({ digest: f.first.digest, createdAt: expect.stringMatching(/Z$/u) });
    expect(controls.snapshot().checkpoints.cursor).toBeNull();
    expect(controls.snapshot().canCreate).toBe(false);
    await controls.create("Viewer not allowed"); await controls.approve(id(100));
    expect(createCalls).toHaveLength(0); expect(approveCalls).toHaveLength(0);

    set("editor", null); expect(controls.snapshot().canCreate).toBe(false);
    await controls.create("Unsaved"); expect(createCalls).toHaveLength(0);
    set("editor", 1); await controls.create("Cut for Dana");
    expect(controls.snapshot().mutation).toMatchObject({ busy: false, error: expect.any(String), pending: { kind: "create", checkpointId: id(100) } });
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
    expect(controls.snapshot().checkpoints.items.find(c => c.checkpointId === id(100))?.approval)
      .toMatchObject({ approvedBy: f.owner.principalId, approvedAt: expect.stringMatching(/Z$/u) });
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
    const changing = createHistoryControls({ api: { ...f.api, createCheckpoint: () => heldMutation }, makeId: (() => {
      let next = 200; return () => id(next++);
    })() });
    changing.setContext({ projectId: project, capabilities: capabilities("producer"), savedHead: 2 });
    const creating = changing.create("Old project");
    expect(changing.snapshot().mutation.busy).toBe(true);
    changing.setContext({ projectId: other.projectId, capabilities: capabilities("producer"), savedHead: 0 });
    await changing.refresh();
    deliver(await f.api.createCheckpoint(project, { checkpointId: id(200), clientMutationId: id(201), name: "Old project", sourceRevision: 2 }));
    await creating;
    expect(changing.snapshot().context.projectId).toBe(other.projectId);
    expect(changing.snapshot().mutation).toMatchObject({ busy: false, pending: null, error: null });
    expect(changing.snapshot().checkpoints.items).toEqual([]);
  });
});
