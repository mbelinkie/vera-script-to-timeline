import { randomUUID } from "node:crypto";

import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2 } from "@vera/contracts/v2";
import { ProjectDocumentError } from "@vera/project-documents";
import { afterEach, describe, expect, it } from "vitest";
import * as Y from "yjs";

import { CollaborationClient } from "../src/client.js";
import { CLOSE_ACCESS_REMOVED } from "../src/hub.js";
import { sameJson, type JsonObject } from "../src/tree.js";
import { editRow, harness, link, rowText, server, settle } from "./helpers.js";

const clients: CollaborationClient[] = [];
function client(): CollaborationClient {
  const created = new CollaborationClient({ undoCaptureMs: 0 });
  clients.push(created);
  return created;
}
afterEach(() => { for (const item of clients.splice(0)) item.destroy(); });

const LIVE = ["liveHeadSequence", "liveStateVector", "liveContentHash"];
function content(document: unknown): JsonObject {
  const copy = { ...(document as JsonObject) };
  for (const key of LIVE) delete copy[key];
  return copy;
}
const documentOf = (item: CollaborationClient) => (item.read() as unknown as { document: ScriptDocumentV2 }).document;

describe("live collaboration", () => {
  it("merges two people typing in the same paragraph at once and saves the result", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    expect([a.state, b.state]).toEqual(["synced", "synced"]);

    // Both type before either has seen the other's change.
    editRow(a, row, (text) => text.replace("hello", "hello there"));
    editRow(b, row, (text) => text + " and goodbye");
    expect(a.state).toBe("local changes");
    await settle(la, lb);

    expect(rowText(a, row)).toBe("hello there world and goodbye");
    expect(sameJson(a.read(), b.read())).toBe(true);
    expect([a.state, b.state]).toEqual(["synced", "synced"]);
    expect(a.status?.materialization).toBe("current");
    expect(a.status?.buildable).toBe(true);

    // The saved script is the merged text, as an ordinary new revision.
    const saved = await h.documents.getDocument(h.projectId, h.viewer);
    expect(saved.revision).toBe(a.status?.documentRevision);
    expect(sameJson(content(saved.document), content(documentOf(a)))).toBe(true);
    expect(saved.document.liveHeadSequence).toBe(a.status?.liveSequence);

    // Each change is attributed to the signed-in person who made it.
    const runs = await h.collaboration.authorship(h.projectId, h.owner, row);
    expect(runs.map((run) => run.text).join("")).toBe("hello there world and goodbye");
    expect(runs.find((run) => run.text.includes("there"))?.actorId).toBe(h.owner.principalId);
    expect(runs.find((run) => run.text.includes("goodbye"))?.actorId).toBe(h.editor.principalId);
  });

  it("merges edits made while disconnected, including deletions, when the client returns", async () => {
    const h = await harness(["one two three"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    let la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);

    la.drop();
    expect(a.state).toBe("offline");
    editRow(a, row, (text) => text.replace("one ", "") + " four");
    expect(a.hasUnsyncedChanges).toBe(true);
    editRow(b, row, (text) => text.replace("two", "2"));
    await settle(lb);
    expect(rowText(b, row)).toBe("one 2 three");

    la = await link(h.hub, h.projectId, h.owner, a);
    await settle(la, lb);
    expect(rowText(a, row)).toBe("2 three four");
    expect(sameJson(a.read(), b.read())).toBe(true);
    expect([a.state, b.state]).toEqual(["synced", "synced"]);
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect((saved.document.activeDraft.blocks[1] as NarrationBlockV2).text).toBe("2 three four");
  });

  it("undoes only the person's own change", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    editRow(a, row, (text) => "A " + text);
    await settle(la, lb);
    editRow(b, row, (text) => text + " B");
    await settle(la, lb);
    expect(rowText(a, row)).toBe("A hello world B");

    a.undo();
    await settle(la, lb);
    expect(rowText(a, row)).toBe("hello world B");
    expect(rowText(b, row)).toBe("hello world B");
    a.redo();
    b.undo();
    await settle(la, lb);
    expect(rowText(b, row)).toBe("A hello world");
    expect(sameJson(a.read(), b.read())).toBe(true);
  });

  it("lets a viewer watch but refuses a viewer's change", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const v = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lv = await link(h.hub, h.projectId, h.viewer, v);
    await settle(la, lv);
    expect([a.canEdit, v.canEdit]).toEqual([true, false]);

    editRow(a, row, (text) => text + "!");
    await settle(la, lv);
    expect(rowText(v, row)).toBe("hello world!");
    const before = await h.documents.getDocument(h.projectId, h.owner);

    editRow(v, row, () => "vandalised");
    await settle(la, lv);
    expect(v.state).toBe("sync failed");
    expect(v.failure).toBe("action_not_allowed");
    expect(v.hasUnsyncedChanges).toBe(true);
    expect(rowText(a, row)).toBe("hello world!");
    expect(await h.documents.getDocument(h.projectId, h.owner)).toEqual(before);
  });

  it("disconnects a removed member and refuses their later changes", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    const before = await h.documents.getDocument(h.projectId, h.owner);

    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, null);
    // Their change races the removal: it is refused inside the storing transaction.
    editRow(b, row, (text) => text + " sneaky");
    await settle(la, lb);
    expect(b.failure).toBe("action_not_allowed");
    expect(lb.closedWith).toBe(CLOSE_ACCESS_REMOVED);
    expect(b.state).toBe("offline");
    expect(rowText(a, row)).toBe("hello world");
    expect(await h.documents.getDocument(h.projectId, h.owner)).toEqual(before);
    await expect(link(h.hub, h.projectId, h.editor, b)).rejects.toMatchObject({ code: "action_not_allowed" });

    // A member who is removed while idle is disconnected by the periodic recheck.
    const v = client();
    const lv = await link(h.hub, h.projectId, h.viewer, v);
    await settle(lv);
    await h.auth.changeMembership(h.projectId, h.owner, h.viewer.principalId, null);
    await h.hub.revalidate(h.projectId);
    expect(lv.closedWith).toBe(CLOSE_ACCESS_REMOVED);
  });

  it("keeps editing when a person's role changes mid-session", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const b = client();
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(lb);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "producer");
    editRow(b, row, (text) => text + " still here");
    await settle(lb);
    expect(b.state).toBe("synced");
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "viewer");
    editRow(b, row, (text) => text + " not any more");
    await settle(lb);
    expect(b.state).toBe("sync failed");
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect((saved.document.activeDraft.blocks[1] as NarrationBlockV2).text).toBe("hello world still here");

    // A refused edit is never counted as stored: once they may edit again, it goes up with the next change.
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "editor");
    await h.hub.revalidate(h.projectId);
    editRow(b, row, (text) => text + "!");
    await settle(lb);
    expect(b.state).toBe("synced");
    const later = await h.documents.getDocument(h.projectId, h.owner);
    expect((later.document.activeDraft.blocks[1] as NarrationBlockV2).text)
      .toBe("hello world still here not any more!");
  });

  it("reopens after a restart with the merged text and every change's author", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    editRow(a, row, (text) => "Well, " + text);
    editRow(b, row, (text) => text + " again");
    await settle(la, lb);
    await h.hub.close();

    const restarted = server(h.db);
    const c = client();
    const lc = await link(restarted.hub, h.projectId, h.viewer, c);
    await settle(lc);
    expect(rowText(c, row)).toBe("Well, hello world again");
    expect(sameJson(c.read(), a.read())).toBe(true);

    const history = await restarted.collaboration.history(h.projectId, h.owner);
    expect(history.map((entry) => entry.origin)).toEqual(["seed", "client", "client"]);
    expect(history.slice(1).map((entry) => entry.actorId).sort())
      .toEqual([h.owner.principalId, h.editor.principalId].sort());
    const runs = await restarted.collaboration.authorship(h.projectId, h.owner, row);
    expect(runs.find((run) => run.text.includes("Well"))?.actorId).toBe(h.owner.principalId);
    expect(runs.find((run) => run.text.includes("again"))?.actorId).toBe(h.editor.principalId);
    expect(runs.find((run) => run.text.includes("hello"))?.actorId).toBe(h.owner.principalId);
  });

  it("keeps a merge that fails validation, reports it as not buildable, and loses no text", async () => {
    const h = await harness(["hello world", "second row"]);
    const [row, other] = h.rowIds as [string, string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    const word = (documentOf(a).activeDraft.blocks[1] as NarrationBlockV2).tokens[1]!;

    // Each edit is valid alone. Together: a citation pinned to a word that no longer exists.
    editRow(a, row, () => "hello");
    b.change((root) => {
      const anchor = { kind: "word" as const, anchor: { blockId: row, tokenId: word.id,
        affinity: "before" as const, quotedWord: word.value, anchorVersion: 1 } };
      const citation: SupportingItemV2 = { id: randomUUID(), role: "citation", version: 1, orderKey: "a",
        content: "Source for world", placement: { kind: "point", anchor }, displayAttachment: anchor };
      (root as unknown as { document: ScriptDocumentV2 }).document.activeDraft.supportingItems.push(citation);
    });
    editRow(b, other, (text) => text + " kept");
    await settle(la, lb);

    expect(sameJson(a.read(), b.read())).toBe(true);
    expect(a.status?.buildable).toBe(false);
    expect(a.status?.diagnostics.length).toBeGreaterThan(0);
    // Nothing either person wrote was removed to make the script valid.
    expect(rowText(a, row)).toBe("hello");
    expect(rowText(a, other)).toBe("second row kept");
    expect(documentOf(a).activeDraft.supportingItems.map((item) => item.content)).toEqual(["Source for world"]);

    // Typing the word again makes a new word (a new ID), so the citation stays
    // flagged until someone re-points or removes it; removing it clears the flag.
    editRow(a, row, () => "hello world");
    await settle(la, lb);
    expect(a.status?.buildable).toBe(false);
    b.change((root) => { (root as unknown as { document: ScriptDocumentV2 }).document.activeDraft.supportingItems = []; });
    await settle(la, lb);
    expect(a.status?.buildable).toBe(true);
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect(sameJson(content(saved.document), content(documentOf(b)))).toBe(true);
  });

  it("holds the last good saved revision while a merge cannot be saved as a script at all", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    const start = await h.documents.getDocument(h.projectId, h.owner);

    editRow(a, row, () => "world");
    editRow(b, row, () => "hello ");
    await settle(la, lb);
    // Both deletions merge into a narration row with no words: not a storable script.
    expect(rowText(a, row).trim()).toBe("");
    expect(a.status?.materialization).toBe("unstorable");
    expect(a.status?.buildable).toBe(false);
    expect(a.status?.diagnostics.length).toBeGreaterThan(0);
    const held = await h.documents.getDocument(h.projectId, h.owner);
    expect(held.revision).toBeGreaterThanOrEqual(start.revision);
    expect((held.document.activeDraft.blocks[1] as NarrationBlockV2).tokens.length).toBeGreaterThan(0);
    expect(a.status?.documentRevision).toBe(held.revision);

    editRow(b, row, (text) => text + "back again");
    await settle(la, lb);
    expect(a.status?.materialization).toBe("current");
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect((saved.document.activeDraft.blocks[1] as NarrationBlockV2).text).toBe(rowText(a, row));
    expect(rowText(a, row)).toContain("back again");
  });

  it("folds a whole-document save into the live document without overwriting live edits", async () => {
    const h = await harness(["first row", "second row"]);
    const [first, second] = h.rowIds as [string, string];
    const a = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    await settle(la);
    editRow(a, first, (text) => text + " live");
    await settle(la);

    // Someone saves the whole script the old way, based on the current revision.
    const head = await h.documents.getDocument(h.projectId, h.editor);
    const next = structuredClone(head.document);
    const target = next.activeDraft.blocks.find((block) => block.id === second) as NarrationBlockV2;
    target.text = "second row saved";
    target.tokens = [...target.tokens, { id: randomUUID(), value: "saved", startOffset: 11, endOffset: 16 }];
    const receipt = await h.documents.putDocument(h.projectId, h.editor,
      { expectedRevision: head.revision, clientMutationId: randomUUID(), document: next });
    // A second save based on the old revision is still refused, exactly as before.
    await expect(h.documents.putDocument(h.projectId, h.editor,
      { expectedRevision: head.revision, clientMutationId: randomUUID(), document: next }))
      .rejects.toBeInstanceOf(ProjectDocumentError);

    // The live editor types before hearing about the save.
    editRow(a, first, (text) => text + " edit");
    await h.collaboration.flush(h.projectId);
    await settle(la);
    expect(rowText(a, first)).toBe("first row live edit");
    expect(rowText(a, second)).toBe("second row saved");
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect(saved.revision).toBeGreaterThan(receipt.revision);
    expect(sameJson(content(saved.document), content(documentOf(a)))).toBe(true);
    // The token the saver supplied keeps the ID they gave it.
    expect((saved.document.activeDraft.blocks[2] as NarrationBlockV2).tokens.at(-1)?.id).toBe(target.tokens.at(-1)?.id);
    const history = await h.collaboration.history(h.projectId, h.owner);
    expect(history.find((entry) => entry.origin === "document_save")?.actorId).toBe(h.editor.principalId);
  });

  it("syncs Ideas as part of the same shared document", async () => {
    const h = await harness(["hello world"]);
    const a = client();
    const b = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lb = await link(h.hub, h.projectId, h.editor, b);
    await settle(la, lb);
    const idea = (text: string) => ({ id: randomUUID(), parentId: null, orderKey: "a", text,
      state: "open", linkedDraftBlockIds: [], collapsed: false, version: 1 });
    a.change((root) => { ((root.ideas as JsonObject).items as JsonObject[]).push(idea("Open on the harbour")); });
    b.change((root) => { ((root.ideas as JsonObject).items as JsonObject[]).push(idea("End on the bridge")); });
    await settle(la, lb);
    expect(sameJson(a.read(), b.read())).toBe(true);
    const ideas = await h.documents.getIdeas(h.projectId, h.viewer);
    expect(ideas.ideas.items.map((item) => item.text).sort()).toEqual(["End on the bridge", "Open on the harbour"]);
    expect(ideas.ideasRevision).toBe(a.status?.ideasRevision);

    const versionBefore = ideas.ideas.items.find((item) => item.text.startsWith("Open"))!.version;
    b.change((root) => {
      const items = (root.ideas as JsonObject).items as { text: string }[];
      items.find((item) => item.text.startsWith("Open"))!.text = "Open on the harbour at dawn";
    });
    await settle(la, lb);
    const edited = (await h.documents.getIdeas(h.projectId, h.viewer)).ideas.items
      .find((item) => item.text.endsWith("dawn"));
    expect(edited?.version).toBe(versionBefore + 1);
    expect(a.status?.materialization).toBe("current");
  });

  it("shares presence without saving it or touching the script", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const v = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    const lv = await link(h.hub, h.projectId, h.viewer, v);
    await settle(la, lv);
    const before = await h.documents.getDocument(h.projectId, h.owner);
    const sequence = a.status?.liveSequence;

    a.setPresence({ selectedRowId: row, cursor: 5 });
    v.setPresence({ selectedRowId: row });
    await settle(la, lv);
    expect(v.awareness.getStates().get(a.doc.clientID)).toEqual({ selectedRowId: row, cursor: 5 });
    expect(a.roster.map((entry) => [entry.actorId, entry.canEdit]).sort()).toEqual(
      [[h.owner.principalId, true], [h.viewer.principalId, false]].sort());
    expect(h.hub.presence(h.projectId).find((entry) => entry.actorId === h.viewer.principalId)?.states)
      .toEqual([{ selectedRowId: row }]);

    lv.drop();
    await settle(la);
    expect(a.roster.map((entry) => entry.actorId)).toEqual([h.owner.principalId]);
    expect(a.awareness.getStates().has(v.doc.clientID)).toBe(false);
    expect(await h.documents.getDocument(h.projectId, h.owner)).toEqual(before);
    expect(a.status?.liveSequence).toBe(sequence);
  });

  it("refuses a change written under another person's Yjs identity", async () => {
    const h = await harness(["hello world"]);
    const [row] = h.rowIds as [string];
    const a = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    await settle(la);
    editRow(a, row, (text) => text + " mine");
    await settle(la);

    const forged = new Y.Doc();
    Y.applyUpdate(forged, Y.encodeStateAsUpdate(a.doc));
    const vector = Y.encodeStateVector(forged);
    forged.clientID = a.doc.clientID;
    forged.getMap("vera").set("forged", true);
    const session = await h.collaboration.open(h.projectId, h.editor);
    await expect(h.collaboration.applyUpdate(h.projectId, h.editor, session.writeSessionId!,
      Y.encodeStateAsUpdate(forged, vector))).rejects.toMatchObject({ code: "client_identity_conflict" });
    expect(a.read().forged).toBeUndefined();
  });

  it("can delay writing saved revisions and still be current the moment something asks", async () => {
    const h = await harness(["hello world"], { materializeDelayMs: 60_000 });
    const [row] = h.rowIds as [string];
    const a = client();
    const la = await link(h.hub, h.projectId, h.owner, a);
    await settle(la);
    const start = await h.documents.getDocument(h.projectId, h.owner);
    for (const word of ["one", "two", "three"]) {
      editRow(a, row, (text) => `${text} ${word}`);
      await settle(la);
    }
    expect(a.state).toBe("synced");
    expect(a.status?.materialization).toBe("pending");
    expect((await h.documents.getDocument(h.projectId, h.owner)).revision).toBe(start.revision);

    await h.collaboration.flush(h.projectId);
    await settle(la);
    const saved = await h.documents.getDocument(h.projectId, h.owner);
    expect(saved.revision).toBe(start.revision + 1);
    expect((saved.document.activeDraft.blocks[1] as NarrationBlockV2).text).toBe("hello world one two three");
    expect(a.status?.materialization).toBe("current");
    await h.hub.close();
  });
});
