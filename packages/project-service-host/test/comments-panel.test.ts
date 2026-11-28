import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { expect, it } from "vitest";
import {
  applyCommentOperationV2, createCommentStateV2, validateScriptDocumentV2,
  type CommentAnchorV2, type CommentOperationV2,
} from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import type { CommentView } from "../../project-documents/src/comments.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const author = "synthetic-author";
const viewer = "synthetic-viewer";
const literal = "<b>Literal comment</b>";
function fixture() {
  const { document } = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
  const first = document.activeDraft.blocks[0] as NarrationBlockV2;
  const words = "When the harbor opens nobody has to wait alone.".split(" ");
  first.text = words.join(" ");
  let offset = 0;
  first.tokens = words.map((value, i) => {
    const token = { id: id(101 + i), value, startOffset: offset, endOffset: offset + value.length };
    offset += value.length + 1;
    return token;
  });
  const second: NarrationBlockV2 = {
    ...structuredClone(first), id: id(200), orderKey: "b0", text: "other row",
    tokens: [{ id: id(201), value: "other", startOffset: 0, endOffset: 5 }, { id: id(202), value: "row", startOffset: 6, endOffset: 9 }],
    primaryVisualSequence: { id: id(203), version: 1, slots: [{
      id: id(204), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
  };
  document.activeDraft.blocks.push(second);
  expect(validateScriptDocumentV2(document).valid).toBe(true);
  const cardId = first.primaryVisualSequence!.slots[0]!.id;
  const anchors: CommentAnchorV2[] = [
    { kind: "text", blockId: first.id, startTokenId: id(102), endTokenId: id(103) },
    { kind: "card", blockId: first.id, cardId },
    { kind: "block", blockId: second.id },
    { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id },
    { kind: "card", blockId: first.id, cardId },
  ];
  let state = createCommentStateV2(document);
  const apply = (op: CommentOperationV2) => {
    const result = applyCommentOperationV2(state, state.revision, op);
    if (!result.ok) throw new Error(result.error);
    state = result.state;
  };
  anchors.forEach((anchor, i) => apply({
    kind: "create", id: "op-" + i, actorId: author, threadId: "thread-" + i,
    messageId: "message-" + i, anchor, body: literal, mentionActorIds: [viewer],
  }));
  apply({ kind: "reply", id: "reply", actorId: viewer, threadId: "thread-1", messageId: "reply-1", body: "A reply", mentionActorIds: [] });
  apply({ kind: "resolve", id: "resolve", actorId: author, threadId: "thread-4" });
  const view: CommentView = { projectId: document.projectId, documentRevision: 1, commentRevision: state.revision, threads: state.threads };
  const revised = structuredClone(state.document);
  revised.activeDraft.blocks.reverse();
  // Preserve a valid ordered draft while moving the rows apart.
  revised.activeDraft.blocks[0]!.orderKey = "a0";
  revised.activeDraft.blocks[1]!.orderKey = "b0";
  apply({ kind: "replace_document", id: "move", actorId: author, document: revised });
  const stale: CommentView = { ...view, documentRevision: 2, commentRevision: state.revision, threads: state.threads };
  expect(stale.threads[3]!.attachment.status).toBe("stale");
  return { document, view, stale, anchors, cardId, blockId: first.id };
}

type Intent = { kind: string; body?: string; threadId?: string; anchor?: CommentAnchorV2 };
type Panel = {
  update(next: { view?: CommentView | null; error?: boolean; canComment?: boolean; canEdit?: boolean; labelForAnchor?: (anchor: CommentAnchorV2) => string | null }): void;
  beginCreate(anchor: CommentAnchorV2): boolean;
  openThread(id: string): boolean;
  acknowledgeDraft(intent: Intent): void;
};
type Module = {
  mountCommentsPanel(options: {
    root: Element; view: CommentView; canComment: boolean; canEdit: boolean;
    labelForActor: (actor: string) => string; labelForAnchor: (anchor: CommentAnchorV2) => string | null;
    focusTarget: (anchor: CommentAnchorV2, threadId: string) => void; onAction: (intent: Intent) => void;
  }): Panel;
  scriptCommentLabel(document: ScriptDocumentV2, anchor: CommentAnchorV2, label: () => string): string | null;
  commentRowLabel(text: string): string;
  cardCommentCount(view: CommentView, blockId: string, cardId: string, research: boolean): number;
};
type Harness = Window & { panel: Panel; comments: Module; actions: Intent[]; focused: string[] };

it("projects real anchored threads, roles, draft retention, counts and keyboard navigation in Chromium", async () => {
  const data = fixture();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
    const source = readFileSync(new URL("../browser/comments-panel.js", import.meta.url), "utf8");
    const css = readFileSync(new URL("../browser/comments-panel.css", import.meta.url), "utf8");
    await page.route("https://comments.test/**", async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/comments-panel.js") await route.fulfill({ contentType: "text/javascript", body: source });
      else if (path === "/comments-panel.css") await route.fulfill({ contentType: "text/css", body: css });
      else await route.fulfill({ contentType: "text/html", body: '<link rel="stylesheet" href="/comments-panel.css"><main style="width:340px" id="root"></main>' });
    });
    await page.goto("https://comments.test/");
    await page.evaluate(async ({ data, author, viewer }) => {
      const h = window as Harness;
      const url = "/comments-panel.js";
      const comments = await import(url) as Module;
      h.comments = comments;
      h.actions = [];
      h.focused = [];
      h.panel = comments.mountCommentsPanel({
        root: document.querySelector("#root")!, view: data.view, canComment: true, canEdit: false,
        labelForActor: actor => actor === author ? "Alex" : actor === viewer ? "Jonah" : actor,
        labelForAnchor: anchor => comments.scriptCommentLabel(data.document, anchor, () => "Harbor footage"),
        focusTarget: (_anchor, threadId) => h.focused.push(threadId),
        onAction: intent => h.actions.push(intent),
      });
    }, { data, author, viewer });
    expect(await page.getByRole("heading", { name: "Active (4)" }).count()).toBe(1);
    expect(await page.getByText("Words in “When the harbor… nobody has to wait alone.”", { exact: false }).count()).toBe(1);
    expect(await page.getByText("Gap before “other row”", { exact: false }).count()).toBe(1);
    expect(await page.getByText("Whole row · “other row”", { exact: false }).count()).toBe(1);
    const card = page.locator('[data-comment-thread="thread-1"]');
    await card.focus();
    await page.keyboard.press("Enter");
    expect(await page.evaluate(() => (window as Harness).focused)).toEqual(["thread-1"]);
    expect(await page.getByLabel("Reply").evaluate(el => el === document.activeElement)).toBe(true);
    expect(await page.getByText("Alex", { exact: true }).count()).toBe(1);
    expect(await page.getByText("Jonah", { exact: true }).count()).toBe(1);
    expect(await page.getByText(literal, { exact: true }).count()).toBe(1);
    expect(await page.locator("#root b").count()).toBe(0);
    expect(await page.getByRole("button", { name: "Resolve", exact: true }).count()).toBe(0);
    expect(await page.locator("[data-comments-action-slot]").count()).toBe(1);
    await page.getByLabel("Reply").fill("saved draft");
    await page.getByRole("button", { name: "Post reply" }).click();
    expect(await page.evaluate(() => (window as Harness).actions)).toEqual([{ kind: "reply", threadId: "thread-1", body: "saved draft" }]);
    await page.keyboard.press("Escape");
    expect(await card.evaluate(el => el === document.activeElement)).toBe(true);
    await page.locator('[data-comment-thread="thread-0"]').click();
    await page.getByLabel("Reply").fill("different draft");
    await page.getByRole("button", { name: "Back to all comments" }).click();
    await card.click();
    expect(await page.getByLabel("Reply").inputValue()).toBe("saved draft");
    await page.getByLabel("Reply").fill("newer draft");
    await page.evaluate(() => {
      const h = window as Harness;
      h.panel.acknowledgeDraft(h.actions[0]!);
    });
    expect(await page.getByLabel("Reply").inputValue()).toBe("newer draft");
    await page.evaluate(() => (window as Harness).panel.update({ error: true }));
    expect(await page.getByRole("status").innerText()).toContain("unavailable");
    expect(await page.getByLabel("Reply").count()).toBe(0);
    await page.evaluate(() => (window as Harness).panel.update({ error: false }));
    expect(await page.getByLabel("Reply").inputValue()).toBe("newer draft");
    await page.getByRole("button", { name: "Back to all comments" }).click();

    expect(await page.evaluate(({ view, blockId, cardId }) => {
      const m = (window as Harness).comments;
      return [
        m.cardCommentCount({ ...view, threads: [...view.threads, view.threads[1]!] }, blockId, cardId, true),
        m.cardCommentCount(view, blockId, cardId, false),
        m.commentRowLabel("one two three four five six seven eight"),
      ];
    }, data)).toEqual([2, 1, "one two three four five six seven eight"]);

    expect(await page.evaluate(anchors => (window as Harness).panel.beginCreate(anchors[0]!), data.anchors)).toBe(true);
    await page.getByLabel("New comment").fill("viewer creates");
    await page.getByRole("button", { name: "Post", exact: true }).click();
    expect(await page.evaluate(() => (window as Harness).actions.at(-1))).toEqual({ kind: "create", anchor: data.anchors[0], body: "viewer creates" });
    await page.keyboard.press("Escape");
    expect(await page.evaluate(anchors => (window as Harness).panel.beginCreate(anchors[3]!), data.anchors)).toBe(false);
    await page.evaluate(stale => (window as Harness).panel.update({ view: stale, canEdit: true }), data.stale);
    const orphaned = page.getByRole("button", { name: "Orphaned comments (1)" });
    expect(await orphaned.getAttribute("aria-expanded")).toBe("false");
    await orphaned.click();
    await page.locator('[data-comment-thread="thread-3"]').click();
    expect(await page.getByText("Orphaned · target unavailable", { exact: true }).count()).toBe(1);
    expect(await page.getByRole("button", { name: "Go to target" }).count()).toBe(0);
    await page.getByRole("button", { name: "Reattach…" }).click();
    expect(await page.evaluate(() => (window as Harness).actions.at(-1))).toEqual({ kind: "reattach", threadId: "thread-3" });
    await page.getByRole("button", { name: "Resolve", exact: true }).click();
    expect(await page.evaluate(() => (window as Harness).actions.at(-1))).toEqual({ kind: "resolve", threadId: "thread-3" });
    expect(await page.evaluate(() => (window as Harness).focused.includes("thread-3"))).toBe(false);
    await page.getByRole("button", { name: "Back to all comments" }).click();
    await page.getByRole("button", { name: "Resolved (1)" }).click();
    await page.locator('[data-comment-thread="thread-4"]').click();
    await page.getByRole("button", { name: "Reopen" }).click();
    expect(await page.evaluate(() => (window as Harness).actions.at(-1))).toEqual({ kind: "reopen", threadId: "thread-4" });

    await page.evaluate(view => (window as Harness).panel.update({ view, labelForAnchor: () => null, canComment: false, canEdit: false }), data.view);
    expect(await page.getByText("Orphaned · target unavailable", { exact: false }).count()).toBe(1);
    expect(await page.getByRole("button", { name: "Go to target" }).count()).toBe(0);
    expect(await page.getByLabel("Reply").count()).toBe(0);
    await page.evaluate(view => (window as Harness).panel.update({ view: { ...view, threads: [] } }), data.view);
    expect(await page.getByText("No open discussions.").count()).toBe(1);
  } finally { await browser.close(); }
}, 30_000);
