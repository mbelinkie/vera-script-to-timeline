// The shell supplies acknowledged saved head and current authorization; the service
// remains authoritative for every read and write. No live document is checkpointed.
export function createHistoryControls({ api, makeId = () => crypto.randomUUID(), pageSize = 20, onChange = () => {} }) {
  let context = { projectId: null, capabilities: [], savedHead: null };
  let epoch = 0;
  let pending = null;
  const emptyPage = () => ({ items: [], cursor: undefined, loading: false, error: null });
  let history = emptyPage(), checkpoints = emptyPage();
  let mutation = { busy: false, error: null };
  const allowed = (action) => context.capabilities.includes(action);
  const canCreate = () => allowed("create_checkpoint") && Number.isSafeInteger(context.savedHead) && context.savedHead >= 0;
  const canApprove = (id) => allowed("approve_checkpoint") && checkpoints.items.some(c => c.checkpointId === id && !c.approval);
  const snapshot = () => ({
    context: { ...context, capabilities: [...context.capabilities] },
    history: { ...history, items: [...history.items] }, checkpoints: { ...checkpoints, items: [...checkpoints.items] },
    mutation: { ...mutation, pending: pending && { kind: pending.kind, name: pending.input.name, checkpointId: pending.id } },
    canCreate: canCreate(), canApprove: allowed("approve_checkpoint"), canRestore: allowed("edit_document"),
  });
  const notify = () => onChange(snapshot());
  function setContext(next) {
    const changed = next.projectId !== context.projectId ||
      next.capabilities.includes("view_history") !== allowed("view_history");
    const lostWrite = ["create_checkpoint", "approve_checkpoint"].some(a => allowed(a) && !next.capabilities.includes(a));
    if (changed || lostWrite) {
      epoch++;
      history = emptyPage(); checkpoints = emptyPage();
      pending = null; mutation = { busy: false, error: null };
    }
    context = { ...next, capabilities: [...next.capabilities] };
    notify();
  }
  async function load(kind) {
    if (!context.projectId || !allowed("view_history")) return;
    const isHistory = kind === "history";
    const page = isHistory ? history : checkpoints;
    if (page.loading || page.cursor === null) return;
    const projectId = context.projectId, started = epoch;
    page.loading = true; page.error = null; notify();
    try {
      const query = { limit: pageSize, ...(page.cursor === undefined ? {} :
        { [isHistory ? "beforeRevision" : "beforeCheckpointId"]: page.cursor }) };
      const response = await (isHistory ? api.listDocumentRevisions(projectId, query) : api.listCheckpoints(projectId, query));
      if (started !== epoch) return;
      if (response.projectId !== projectId) throw new Error("Unexpected project");
      const key = isHistory ? "revision" : "checkpointId";
      const incoming = isHistory ? response.revisions : response.checkpoints;
      const combined = new Map(page.items.map(item => [item[key], item]));
      for (const item of incoming) combined.set(item[key], item);
      page.items = [...combined.values()];
      page.cursor = isHistory ? response.nextBeforeRevision : response.nextBeforeCheckpointId;
    } catch {
      if (started === epoch) page.error = "Couldn’t load " + (isHistory ? "revisions" : "checkpoints") + ". Try again.";
    } finally {
      if (started === epoch) { page.loading = false; notify(); }
    }
  }
  async function refresh() {
    if (mutation.busy || pending) return;
    epoch++; history = emptyPage(); checkpoints = emptyPage(); notify();
    await Promise.all([load("history"), load("checkpoints")]);
  }
  async function submit(attempt) {
    if (mutation.busy || !context.projectId || !allowed("view_history")) return;
    if (attempt.kind === "create" ? !canCreate() : !canApprove(attempt.id)) return;
    const started = epoch, projectId = context.projectId;
    pending = attempt; mutation = { busy: true, error: null }; notify();
    try {
      const receipt = await (attempt.kind === "create" ?
        api.createCheckpoint(projectId, attempt.input) : api.approveCheckpoint(projectId, attempt.id, attempt.input));
      if (started !== epoch) return;
      if (receipt.projectId !== projectId || receipt.checkpointId !== attempt.id ||
          receipt.clientMutationId !== attempt.input.clientMutationId) throw new Error("Unexpected receipt");
      pending = null;
      // A create replay's receipt intentionally has approval:null; use the
      // authoritative paged read rather than replacing a newer approval.
      mutation = { busy: false, error: null };
      await refresh();
    } catch (error) {
      if (started !== epoch) return;
      mutation = { busy: false, error: "Couldn’t " + (attempt.kind === "create" ? "save checkpoint" : "approve checkpoint") + ". Try again." };
      // A confirmed conflict is not an uncertain delivery. Reconcile first,
      // then require a new explicit submission (with a fresh mutation ID).
      if (Number.isInteger(error?.status) && error.status >= 400 && error.status < 500) {
        pending = null;
        await refresh();
      }
    } finally { if (started === epoch) notify(); }
  }
  async function create(name) {
    if (!canCreate() || pending || mutation.busy) return;
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 120 || /\p{Cc}/u.test(trimmed)) {
      mutation = { busy: false, error: "Use a checkpoint name of 1–120 non-control characters." }; notify(); return;
    }
    const id = makeId();
    await submit({ kind: "create", id, input: { checkpointId: id, clientMutationId: makeId(), name: trimmed, sourceRevision: context.savedHead } });
  }
  async function approve(id) {
    if (!canApprove(id) || pending || mutation.busy) return;
    await submit({ kind: "approve", id, input: { clientMutationId: makeId() } });
  }
  async function retry() { if (pending) await submit(pending); }
  return { snapshot, setContext, loadHistory: () => load("history"), loadCheckpoints: () => load("checkpoints"), refresh, create, approve, retry };
}

export function mountHistoryPanel({ root, api, makeId, pageSize, onCompare, onRestore }) {
  const node = (tag, text = "") => {
    const element = root.ownerDocument.createElement(tag);
    element.textContent = text;
    return element;
  };
  const button = (text, action) => {
    const el = node("button", text); el.type = "button"; el.onclick = action; return el;
  };
  root.classList.add("history-panel");
  const heading = node("h2", "History");
  const body = node("div"); body.className = "history-panel__body";
  const compareMount = node("div"); compareMount.className = "history-panel__comparison";
  root.replaceChildren(heading, body, compareMount);
  let name = "", priorProject = null, comparisonEpoch = 0;
  let previouslyEditable = false;
  const controls = createHistoryControls({ api, makeId, pageSize, onChange: render });
  const chooseComparison = async (state, checkpoint) => {
    const current = controls.snapshot();
    if (current.context.projectId !== state.context.projectId || current.context.savedHead !== state.context.savedHead ||
        !current.context.capabilities.includes("view_history")) return;
    const request = ++comparisonEpoch;
    compareMount.replaceChildren(node("p", "Loading saved comparison…"));
    try {
      const saved = await api.getCheckpoint(state.context.projectId, checkpoint.checkpointId);
      if (request !== comparisonEpoch) return;
      if (saved.projectId !== state.context.projectId || saved.checkpointId !== checkpoint.checkpointId ||
          saved.sourceRevision !== checkpoint.sourceRevision || saved.sourceDigest !== checkpoint.sourceDigest) throw new Error();
      compareMount.replaceChildren();
      onCompare?.({ mount: compareMount, checkpoint: saved, toRevision: state.context.savedHead });
    } catch { if (request === comparisonEpoch) compareMount.replaceChildren(node("p", "Couldn’t load saved checkpoint. Try again.")); }
  };
  function render(state) {
    const { context, history, checkpoints, mutation } = state;
    const editable = context.capabilities.includes("create_checkpoint");
    if (previouslyEditable && !editable) name = "";
    previouslyEditable = editable;
    if (priorProject !== context.projectId || !context.capabilities.includes("view_history")) {
      name = ""; priorProject = context.projectId; comparisonEpoch++; compareMount.replaceChildren();
    }
    const focused = root.ownerDocument.activeElement;
    const focusKey = body.contains(focused) ? focused.dataset.historyFocus : undefined;
    body.replaceChildren();
    if (!context.projectId || !context.capabilities.includes("view_history")) {
      body.append(node("p", "History unavailable.")); return;
    }
    const sameProject = () => controls.snapshot().context.projectId === context.projectId;
    const mark = (el, key) => { el.dataset.historyFocus = key; return el; };
    body.append(node("p", context.savedHead === null ? "No acknowledged saved revision." : "Saved revision " + context.savedHead));
    body.append(mark(button("Refresh history", () => { void controls.refresh(); }), "refresh"));
    if (context.capabilities.includes("create_checkpoint")) {
      const form = node("form"), label = node("label", state.canCreate ? "Name a checkpoint of revision " + context.savedHead : "Save your edits before naming a checkpoint");
      const input = mark(node("input"), "name"); input.value = name; input.required = true; input.maxLength = 120; input.placeholder = "e.g. Cut for Dana";
      input.oninput = () => { name = input.value; };
      input.disabled = !state.canCreate || mutation.busy || !!mutation.pending;
      label.append(input);
      const save = mark(node("button", "Save checkpoint"), "save"); save.type = "submit"; save.disabled = input.disabled;
      form.append(label, save);
      form.onsubmit = async (event) => { event.preventDefault(); if (!sameProject()) return; await controls.create(name); const next = controls.snapshot(); if (!next.mutation.error && !next.mutation.pending && next.context.projectId === context.projectId) { name = ""; render(next); } };
      body.append(form);
    }
    if (mutation.error) {
      const error = node("p", mutation.error); error.setAttribute("role", "alert"); body.append(error);
      if (mutation.pending) body.append(mark(button("Try again", async () => { if (!sameProject()) return; await controls.retry(); const next = controls.snapshot(); if (!next.mutation.error && !next.mutation.pending && next.context.projectId === context.projectId) { name = ""; render(next); } }), "retry"));
    }
    function list(title, page, load, renderItem) {
      const section = node("section"); section.append(node("h3", title));
      const entries = node("ul"); for (const item of page.items) entries.append(renderItem(item)); section.append(entries);
      if (page.loading || page.error || !page.items.length) {
        const status = node("p", page.loading ? "Loading…" : page.error ?? (page.cursor === null ? "No " + title.toLowerCase() + "." : title + " not loaded."));
        status.setAttribute("role", page.error ? "alert" : "status"); section.append(status);
      }
      if (!page.loading && page.cursor !== null) section.append(mark(button(page.error ? "Try again" : (page.cursor === undefined ? "Load " : "Load more ") + title.toLowerCase(), () => { void load(); }), title));
      body.append(section);
    }
    list("Checkpoints", checkpoints, controls.loadCheckpoints, c => {
      const li = node("li"); li.dataset.checkpointId = c.checkpointId;
      li.append(node("strong", c.name), node("p", "Revision " + c.sourceRevision + " · " + c.createdBy + " · " + c.createdAt),
        node("p", c.approval ? "Approved · " + c.approval.approvedBy + " · " + c.approval.approvedAt : "Not approved"));
      if (Number.isSafeInteger(context.savedHead) && onCompare) li.append(mark(button("Compare with now", () => { void chooseComparison(state, c); }), "compare-" + c.checkpointId));
      if (state.canApprove && !c.approval) {
        const approve = mark(button("Approve", () => { if (sameProject()) void controls.approve(c.checkpointId); }), "approve-" + c.checkpointId);
        approve.disabled = mutation.busy || !!mutation.pending; li.append(approve);
      }
      if (state.canRestore && onRestore) li.append(mark(button("Restore", () => {
        const now = controls.snapshot();
        if (now.context.projectId === context.projectId && now.canRestore && now.checkpoints.items.some(item => item.checkpointId === c.checkpointId)) onRestore({ projectId: context.projectId, checkpointId: c.checkpointId });
      }), "restore-" + c.checkpointId));
      return li;
    });
    list("Revisions", history, controls.loadHistory, revision => {
      const li = node("li"); li.dataset.revision = String(revision.revision);
      li.append(node("strong", "Revision " + revision.revision), node("p", revision.actorId + " · " + revision.createdAt));
      if (revision.restoreOrigin) li.append(node("p", "Restored checkpoint " + revision.restoreOrigin.checkpointId + " · revision " + revision.restoreOrigin.sourceRevision));
      return li;
    });
    if (focusKey) [...body.querySelectorAll("[data-history-focus]")].find(el => el.dataset.historyFocus === focusKey)?.focus();
  }
  return {
    comparisonMount: compareMount,
    async setContext(context) {
      const before = controls.snapshot().context;
      if (before.projectId !== context.projectId || before.savedHead !== context.savedHead || !context.capabilities.includes("view_history")) { comparisonEpoch++; compareMount.replaceChildren(); }
      controls.setContext(context);
      await Promise.all([controls.loadHistory(), controls.loadCheckpoints()]);
    },
    refresh: controls.refresh,
    destroy() { controls.setContext({ projectId: null, capabilities: [], savedHead: null }); root.replaceChildren(); },
  };
}
