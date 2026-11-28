/** r29 row label: preserve short rows and keep the selected quotation separate. */
export function commentRowLabel(text) {
  const words = String(text ?? "").replace(/\[[^\]]*\]/g, " ").trim().split(/\s+/).filter(Boolean);
  if (words.length <= 8) return words.join(" ");
  return words.slice(0, 3).join(" ").replace(/[,;:.]+$/, "") + "… " + words.slice(-5).join(" ");
}

/** A single card marker counts distinct active, attached discussions, plus one available Research thread. */
export function cardCommentCount(view, blockId, cardId, hasResearchThread = false) {
  const ids = new Set((view?.threads ?? []).filter(({ attachment, resolved }) =>
    !resolved && attachment.status === "attached" && attachment.anchor.kind === "card" &&
    attachment.anchor.blockId === blockId && attachment.anchor.cardId === cardId).map(({ id }) => id));
  return ids.size + (hasResearchThread ? 1 : 0);
}

/**
 * Project the real current document, never guess a target from quoted prose.
 * The caller supplies its existing card label (or null for an unavailable target).
 */
export function scriptCommentLabel(document, anchor, cardLabel = () => "Visual") {
  const blocks = document?.activeDraft?.blocks ?? [];
  const block = blocks.find(row => row.id === (anchor.kind === "between_blocks" ? anchor.beforeBlockId : anchor.blockId));
  if (!block) return null;
  if (anchor.kind === "between_blocks" &&
      blocks[blocks.indexOf(block) - 1]?.id !== anchor.afterBlockId) return null;
  if (anchor.kind === "text") {
    if (block.type !== "narration") return null;
    const start = block.tokens.findIndex(token => token.id === anchor.startTokenId);
    const end = block.tokens.findIndex(token => token.id === anchor.endTokenId);
    if (start < 0 || end < start) return null;
  }
  if (anchor.kind === "card") {
    const card = block.type === "narration"
      ? block.primaryVisualSequence?.slots.find(slot => slot.kind === "content" && slot.id === anchor.cardId) ??
        block.unattachedVisuals?.find(visual => visual.slotId === anchor.cardId)
      : block.type === "visual_only"
        ? (block.payload.payloadId === anchor.cardId ? block : block.additionalVisuals?.find(visual => visual.payload.payloadId === anchor.cardId))
        : null;
    return card ? cardLabel(card, block) : null;
  }
  return commentRowLabel(block.text) || (block.type === "visual_only" ? "Visuals-only row" : "Whole row");
}

function targetTitle(anchor, label) {
  if (anchor.kind === "card") return "Visual · " + label;
  if (anchor.kind === "between_blocks") return "Gap before “" + label + "”";
  return (anchor.kind === "text" ? "Words in " : "Whole row · ") + "“" + label + "”";
}

/**
 * Standalone projection, with no transport or shared shell dependencies.
 * view is the delivered CommentView; null means not loaded. labelForAnchor returns
 * a current label or null if untargetable. onAction receives an intent, not a
 * public mutation: the next slice owns IDs, mentions, revision and submission.
 * Call acknowledgeDraft only after confirmed acceptance; a refresh never discards it.
 */
export function mountCommentsPanel({ root, ...initial }) {
  const doc = root.ownerDocument;
  const drafts = new Map();
  const groups = { orphaned: false, resolved: false };
  let props = initial, selected = null, creating = null, actionSlot = null;
  let projectId = props.view?.projectId;
  const node = (tag, text, className) => {
    const el = doc.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const button = (text, action) => {
    const el = node("button", text);
    el.type = "button";
    el.addEventListener("click", action);
    return el;
  };
  const labelForActor = actorId => props.labelForActor?.(actorId) || actorId;
  const currentLabel = anchor => props.labelForAnchor?.(anchor) || null;
  const target = thread => thread.attachment.status === "attached" ? currentLabel(thread.attachment.anchor) : null;
  const groupFor = thread => thread.resolved ? "resolved" : target(thread) ? "active" : "orphaned";
  const threadKey = id => JSON.stringify(["reply", id]);
  const createKey = anchor => JSON.stringify(["create", anchor.kind, anchor.blockId, anchor.cardId,
    anchor.startTokenId, anchor.endTokenId, anchor.afterBlockId, anchor.beforeBlockId]);
  const threads = () => props.view?.threads ?? [];
  const selectedThread = () => threads().find(thread => thread.id === selected);
  const summaryTitle = thread => {
    const label = target(thread);
    return label ? targetTitle(thread.attachment.anchor, label) : "Original " +
      ({ text: "words", card: "visual", block: "row", between_blocks: "gap" }[thread.attachment.anchor.kind]);
  };
  const statusFor = thread => target(thread) ? (thread.resolved ? "Resolved" : "Open") :
    (thread.resolved ? "Resolved · " : "") + "Orphaned · target unavailable";
  const canCompose = () => !!props.view && !props.error && props.canComment;
  function dispatch(intent) { props.onAction?.(intent); }

  function closeThread() {
    const thread = selectedThread();
    const id = selected;
    if (thread) {
      const group = groupFor(thread);
      if (group !== "active") groups[group] = true;
    }
    selected = null;
    creating = null;
    render();
    const item = [...root.querySelectorAll("[data-comment-thread]")].find(el => el.dataset.commentThread === id);
    (item ?? root.querySelector("[data-comments-heading]"))?.focus();
  }

  function openThread(id) {
    const thread = threads().find(item => item.id === id);
    if (!thread) return false;
    selected = id;
    creating = null;
    render();
    if (target(thread)) props.focusTarget?.(thread.attachment.anchor, thread.id);
    (root.querySelector("textarea") ?? root.querySelector("[data-discussion-heading]"))?.focus();
    return true;
  }

  function composer(parent, key, intent, isReply) {
    const form = node("form", undefined, "comments-panel__composer");
    const label = node("label", isReply ? "Reply" : "New comment");
    const input = node("textarea");
    input.rows = 3;
    input.value = drafts.get(key) ?? "";
    label.append(input);
    const post = node("button", isReply ? "Post reply" : "Post");
    post.type = "submit";
    post.disabled = !input.value.trim();
    input.addEventListener("input", () => {
      drafts.set(key, input.value);
      post.disabled = !input.value.trim();
    });
    form.addEventListener("submit", event => {
      event.preventDefault();
      if (!canCompose() || !input.value.trim()) return;
      // No client-supplied attribution. Never clear an uncertain or rejected submission.
      dispatch({ ...intent, body: input.value });
    });
    form.append(label, post);
    parent.append(form);
  }

  function renderList() {
    const sections = [["active", "Active"], ["orphaned", "Orphaned comments"], ["resolved", "Resolved"]];
    for (const [key, title] of sections) {
      const list = threads().filter(thread => groupFor(thread) === key);
      if (key !== "active" && !list.length) continue;
      const group = node("section", undefined, "comments-panel__group");
      const heading = node("h3");
      const open = key === "active" || groups[key];
      if (key === "active") heading.textContent = title + " (" + list.length + ")";
      else {
        const toggle = button(title + " (" + list.length + ")", () => {
          groups[key] = !groups[key];
          render();
          root.querySelector('[data-comment-group="' + key + '"]')?.focus();
        });
        toggle.dataset.commentGroup = key;
        toggle.setAttribute("aria-expanded", String(open));
        heading.append(toggle);
      }
      group.append(heading);
      if (open) {
        if (!list.length) group.append(node("p", "No open discussions."));
        for (const thread of list) {
          const last = thread.messages.at(-1);
          const item = button(summaryTitle(thread), () => openThread(thread.id));
          item.className = "comments-panel__thread";
          item.dataset.commentThread = thread.id;
          item.append(node("span", statusFor(thread), "comments-panel__status"),
            node("span", thread.attachment.quotedText || last?.body || "No comments yet"),
            node("span", thread.messages.length + (thread.messages.length === 1 ? " comment" : " comments") +
              (last ? " · last " + labelForActor(last.actorId) : "") +
              (drafts.get(threadKey(thread.id))?.trim() ? " · Draft" : ""), "comments-panel__status"));
          group.append(item);
        }
      }
      root.append(group);
    }
  }

  function renderDiscussion(thread) {
    root.append(button("Back to all comments", closeThread));
    const heading = node("h3", summaryTitle(thread));
    heading.tabIndex = -1;
    heading.dataset.discussionHeading = "";
    root.append(heading, node("p", statusFor(thread), "comments-panel__status"));
    if (thread.attachment.quotedText !== null) root.append(node("blockquote", thread.attachment.quotedText));
    if (target(thread)) root.append(button("Go to target", () => {
      if (target(thread)) props.focusTarget?.(thread.attachment.anchor, thread.id);
    }));
    const messages = node("ol", undefined, "comments-panel__messages");
    for (const message of thread.messages) {
      const entry = node("li");
      entry.append(node("strong", labelForActor(message.actorId)), node("p", message.body));
      if (message.mentionActorIds.length) entry.append(node("span",
        "Mentions: " + message.mentionActorIds.map(labelForActor).join(", "), "comments-panel__status"));
      messages.append(entry);
    }
    root.append(messages);
    if (canCompose()) composer(root, threadKey(thread.id), { kind: "reply", threadId: thread.id }, true);
    if (props.view && !props.error && props.canEdit) {
      root.append(button(thread.resolved ? "Reopen" : "Resolve",
        () => dispatch({ kind: thread.resolved ? "reopen" : "resolve", threadId: thread.id })));
      if (thread.attachment.status === "stale") root.append(button("Reattach…",
        () => dispatch({ kind: "reattach", threadId: thread.id })));
    }
    // Z74-B can mount its action feedback or mention controls here.
    const slot = node("div");
    slot.dataset.commentsActionSlot = "";
    root.append(slot);
    actionSlot = slot;
  }

  function render() {
    root.classList.add("comments-panel");
    root.setAttribute("aria-label", "Comments");
    root.replaceChildren();
    actionSlot = null;
    const heading = node("h2", "Comments");
    heading.tabIndex = -1;
    heading.dataset.commentsHeading = "";
    root.append(heading);
    if (props.error || !props.view) {
      const status = node("p", props.error ? "Comments unavailable. Try again." : "Loading comments…");
      status.setAttribute("role", "status");
      root.append(status);
      return;
    }
    const thread = selectedThread();
    if (thread) return renderDiscussion(thread);
    if (creating) {
      root.append(button("Back to all comments", closeThread));
      const label = currentLabel(creating);
      if (label && canCompose()) {
        root.append(node("h3", targetTitle(creating, label)));
        composer(root, createKey(creating), { kind: "create", anchor: structuredClone(creating) }, false);
        const slot = node("div");
        slot.dataset.commentsActionSlot = "";
        root.append(slot);
        actionSlot = slot;
      } else root.append(node("p", "Comment target unavailable or commenting not permitted."));
      return;
    }
    renderList();
  }

  root.addEventListener("keydown", event => {
    if (event.key === "Escape" && (selected !== null || creating)) {
      event.stopPropagation();
      event.preventDefault();
      closeThread();
    }
  });
  render();
  return {
    update(next) {
      props = { ...props, ...next };
      if (props.view && projectId !== props.view.projectId) {
        if (projectId !== undefined) { drafts.clear(); selected = null; creating = null; groups.orphaned = groups.resolved = false; }
        projectId = props.view.projectId;
      }
      if (props.view && selected && !selectedThread()) selected = null;
      render();
    },
    openThread,
    closeThread,
    beginCreate(anchor) {
      if (!canCompose() || anchor.kind === "between_blocks" || !currentLabel(anchor)) return false;
      creating = structuredClone(anchor);
      selected = null;
      render();
      root.querySelector("textarea")?.focus();
      return true;
    },
    acknowledgeDraft(intent) {
      const key = intent.kind === "create" ? createKey(intent.anchor) : threadKey(intent.threadId);
      if (drafts.get(key) === intent.body) { drafts.delete(key); render(); }
    },
    get actionSlot() { return actionSlot; },
  };
}
