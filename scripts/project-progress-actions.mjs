import { REPOS } from "./chat-review-current.mjs";

export const PRIMARY_ACTION_KINDS = Object.freeze([
  "none",
  "review-chat",
  "prepare-deepseek",
  "review-blocker",
  "start-codex",
  "continue-owner",
  "pair-owner",
  "notify-owner",
  "finish-owner",
  "review-producer",
  "ask-owner-prepare",
  "check-status",
  "open-queue",
]);

export const SECONDARY_ACTION_KINDS = Object.freeze([]);

const EVENT_ID = /^[0-9a-f]{64}$/;
const QUEUE_CONTROL_URL = "https://github.com/mbelinkie/vera-script-to-timeline/issues/361";
const NO_CLAIM_REASON = "No active issue claim was found.";

function issueUrl(value) {
  if (typeof value !== "string") return null;
  const match = /^https:\/\/github\.com\/([^/]+\/[^/]+)\/issues\/([1-9][0-9]*)$/.exec(value);
  return match && REPOS.has(match[1]) && Number.isSafeInteger(Number(match[2])) ? value : null;
}

function hasPullRequest(workflow) {
  return Array.isArray(workflow?.links) && workflow.links.some((link) => {
    if (link?.label !== "PR" || typeof link.url !== "string") return false;
    const match = /^https:\/\/github\.com\/([^/]+\/[^/]+)\/pull\/([1-9][0-9]*)$/.exec(link.url);
    return Boolean(match && REPOS.has(match[1]) && Number.isSafeInteger(Number(match[2])));
  });
}

function dependenciesState(item) {
  if (item?.dependenciesVerified !== true || !Array.isArray(item.dependencies)) return "unknown";
  return item.dependencies.some((dependency) => dependency?.invalid === true || dependency?.isOpen === true)
    ? "blocked"
    : "clear";
}

function action(group, actor, label, kind, reason, filter, url, eventId) {
  const result = { group, actor, label, kind, reason, filter };
  const safeUrl = issueUrl(url);
  if (safeUrl) result.issueUrl = safeUrl;
  if (["notify-owner", "finish-owner", "review-producer"].includes(kind) && typeof eventId === "string" && EVENT_ID.test(eventId)) {
    result.eventId = eventId;
  }
  return result;
}

function checkStatus(url, reason = "Current issue and workflow evidence must be refreshed before acting.") {
  return action("decision", "You", "Check status", "check-status", reason, "decision", url);
}

function chatAction(workflow, url, reason) {
  if (workflow?.deepseek?.route === "chat") {
    return action("chat", "ChatGPT", "Prepare DeepSeek in ChatGPT", "prepare-deepseek",
      "ChatGPT reviews the issue and prepares its DeepSeek task. Execution requires exact task approval.", "deepseek", url);
  }
  return action("chat", "ChatGPT", "Review in ChatGPT", "review-chat", reason, "chat", url);
}

function ownerHandoff({ bound, canPair, url, eventId, kind = "continue-owner", group = "decision", reason }) {
  if (bound) {
    const labels = {
      "notify-owner": ["Ask Codex to check", "blocked"],
      "finish-owner": ["Ask Codex to finish", "approval"],
      "ask-owner-prepare": ["Ask Codex to prepare review", "approval"],
    };
    const [label, filter] = labels[kind] ?? ["Continue in Codex", "working"];
    const exactEvent = typeof eventId === "string" && EVENT_ID.test(eventId);
    const operation = ["notify-owner", "finish-owner"].includes(kind) && !exactEvent ? "continue-owner" : kind;
    return action(group, "Codex", label, operation, reason, filter, url, eventId);
  }
  if (!canPair) return checkStatus(url, "Find the original owner before sending a handoff.");
  return action(group, "Codex", "Pair original owner", "pair-owner",
    "Ask the matched existing Codex chat to confirm it owns this ticket.",
    group === "blocked" ? "blocked" : "working", url);
}

function knownNoClaim(codex) {
  return codex?.state === "unclaimed" || (codex?.state === "unknown" && codex.reason === NO_CLAIM_REASON);
}

function grandfatheredWork(workflow) {
  return Array.isArray(workflow?.chips)
    && workflow.chips.some((chip) => chip?.name === "Chat" && chip?.state === "grandfathered");
}

function deliveredAction(item, options, url) {
  if (item.acceptance === "Producer") {
    if (!options.hasProducerChecklist || !options.eventId || !options.ownerBound) {
      return ownerHandoff({
        bound: options.ownerBound === true,
        canPair: options.canPair,
        url,
        kind: "ask-owner-prepare",
        group: "finish",
        reason: "Producer acceptance is needed, but no concrete review checklist is recorded.",
      });
    }
    return action("decision", "Producer", "Review and approve", "review-producer",
      "Verified merge and smoke are ready for the recorded Producer checklist.", "approval", url, options.eventId);
  }
  if (["Automated", "External"].includes(item.acceptance)) {
    return ownerHandoff({
      bound: options.ownerBound === true,
      canPair: options.canPair,
      url,
      eventId: options.eventId,
      kind: "finish-owner",
      group: "finish",
      reason: "Verified merge and post-merge smoke are ready for authorized acceptance by the original owner.",
    });
  }
  return checkStatus(url, "Delivery is verified, but the issue's acceptance owner is missing or unrecognized.");
}

export function derivePrimaryAction(item, workflow, {
  projectFresh = false,
  workflowFresh = false,
  chatFresh = false,
  codexFresh = false,
  prFresh = false,
  ciFresh = false,
  ownerBound = false,
  canPair = false,
  activeTurnFresh = false,
  eventId,
  hasProducerChecklist = false,
} = {}) {
  const url = issueUrl(item?.url);
  if (!url) return checkStatus(null, "A canonical VERA issue identity is unavailable.");
  if (url === QUEUE_CONTROL_URL) {
    return action("decision", "You", "Open queue status", "open-queue",
      "Use the CI control issue for queue status and supported owner commands.", "working", url);
  }
  if (!projectFresh || item.evidenceConflict === true) return checkStatus(url, "The Project snapshot is stale, conflicting, or unavailable.");
  if (item.status === "Done") {
    return action("done", "None", "Done", "none", "The Project marks this issue Done.", "done", url);
  }

  const dependencies = dependenciesState(item);
  if (dependencies === "unknown") return checkStatus(url, "Dependencies have not been freshly verified.");
  if (dependencies === "blocked") {
    return action("blocked", "Dependency", "Blocked by dependency", "none",
      "Complete or verify the open prerequisite before starting or resuming work.", "blocked", url);
  }
  if (item.status === "Blocked") {
    return action("blocked", "ChatGPT", "Review blocker", "review-blocker",
      "The issue is Blocked without an open dependency; review the recorded blocker in ChatGPT.", "blocked", url);
  }
  if (!workflowFresh) return checkStatus(url);
  const chatApproved = workflow?.chat?.state === "approved" || grandfatheredWork(workflow);
  const ci = workflow?.ci?.state;
  const hasPr = prFresh && hasPullRequest(workflow);
  const hasClaim = codexFresh && workflow?.codex?.state === "claimed";
  const knownWork = hasPr || hasClaim || ownerBound === true;

  if (hasPr && !ciFresh) return checkStatus(url, "The linked pull request has no fresh CI delivery state.");
  if (hasPr && ciFresh && ci === "delivered") return deliveredAction(item, { ownerBound, canPair, eventId, hasProducerChecklist }, url);
  if (hasPr && ciFresh && ci === "failed-paused") {
    return ownerHandoff({
      bound: ownerBound === true,
      canPair,
      url,
      eventId,
      kind: "notify-owner",
      group: "blocked",
      reason: "CI is failed or paused; ask the original owner to inspect current authoritative status.",
    });
  }
  if (hasPr && ciFresh && ["waiting", "validating", "smoke-running"].includes(ci)) {
    const label = ci === "waiting" ? "Awaiting CI" : ci === "smoke-running" ? "Post-merge smoke running" : "CI running";
    const reason = ci === "waiting" ? "The verified pull request is waiting for the CI queue."
      : ci === "smoke-running" ? "The exact CI workflow is running post-merge smoke; delivery is not recorded yet."
        : "The exact pull request is undergoing CI validation; validation alone is not delivery.";
    return action("ci", "CI", label, "none", reason, "working", url);
  }
  if (activeTurnFresh) {
    return action("working", "Codex", "Working", "none",
      "A fresh active owner turn is verified.", "working", url);
  }
  if (knownWork) {
    return ownerHandoff({
      bound: ownerBound === true,
      canPair,
      url,
      kind: ci === "failed-paused" ? "notify-owner" : "continue-owner",
      group: ci === "failed-paused" ? "blocked" : "decision",
      eventId,
      reason: "A claim or pull request exists, but no verified active owner turn is available.",
    });
  }

  if (item.status === "Inbox" || item.status === "Backlog") {
    return chatAction(workflow, url, "Review scope and acceptance before starting this issue.");
  }
  if (item.status === "Ready" && workflow?.deepseek?.route === "chat") {
    return chatAction(workflow, url, "Prepare this coding issue in ChatGPT.");
  }
  if (!chatFresh || !codexFresh || !prFresh) {
    return checkStatus(url, "Approval, claim, or pull request history could not be verified.");
  }
  if (item.status === "Ready" && knownNoClaim(workflow?.codex)) {
    if (!chatApproved) {
      return chatAction(workflow, url, "A current Producer Chat approval is required before starting work.");
    }
    return action("start", "Codex", "Start with Codex", "start-codex",
      "The issue is Ready, dependencies and current approval are verified, and no owner or pull request exists.", "codex", url);
  }
  if (workflow?.codex?.state === "unknown") {
    return checkStatus(url, "Ownership evidence is unknown; confirm no competing owner before starting.");
  }
  if (item.status === "In progress") {
    return checkStatus(url, "The roadmap says In progress, but no current owner, pull request, or active turn is verified.");
  }
  if (item.status === "In review") {
    return checkStatus(url, "The roadmap says In review, but no delivered merge and smoke or current review target is verified.");
  }
  return checkStatus(url, "No safe advancing action can be derived from the current issue state.");
}

