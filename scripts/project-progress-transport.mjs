import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { promisify } from "node:util";
import { lstat, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { DEFAULT_DIRECTORY, loadOrigin, publicOwnerKey } from "./ci-notification-origin.mjs";
import { ACTION_HOME, attestLegacyPair, readLegacyPairRecord } from "./project-progress-pair.mjs";

const exec = promisify(execFile);
export { ACTION_HOME, attestLegacyPair };
const CHROME_HELPER = path.join(ACTION_HOME, "VERA Dashboard Helper.app", "Contents", "MacOS", "vera-dashboard-helper");
const CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex";
const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const FIRST_DASHBOARD_PREVIEW = Date.parse("2026-11-03T18:03:10.174Z");
const CHAT_THREAD = /^https:\/\/chatgpt\.com\/c\/[a-zA-Z0-9_-]{8,128}$/;
const MAX_OUTPUT = 4 * 1024 * 1024;

export async function runTool(command, args, { cwd, timeout = 30_000 } = {}) {
  return (await exec(command, args, { cwd, timeout, maxBuffer: MAX_OUTPUT, encoding: "utf8" })).stdout;
}

export async function localOrigins(directory = DEFAULT_DIRECTORY) {
  const entries = await readdir(directory).catch(error => {
    if (error?.code === "ENOENT") return [];
    throw error;
  });
  if (entries.length > 2000) throw new Error("Private owner registry exceeded its read limit");
  return entries.filter(name => /^[a-f0-9]{64}\.json$/.test(name))
    .map(name => loadOrigin(name.slice(0, -5), directory)).filter(Boolean);
}

export function matchOrigin(origins, { repository, number, claim, pr = null }) {
  if (claim?.state !== "active") return null;
  const matches = origins.filter(origin => origin.repository === repository && origin.issue === number
    && origin.branch === claim.branch && matchesOwnerClaim(origin.threadId, claim)
    && (pr === null || origin.pr === pr));
  return matches.length === 1 ? matches[0] : null;
}

export function matchesOwnerClaim(threadId, claim) {
  return UUID.test(threadId ?? "") && claim?.state === "active"
    && [threadId, publicOwnerKey(threadId)].includes(claim.task);
}

export function isLegacyOwnerClaim(claim) {
  const startedAt = Date.parse(claim?.startedAt);
  return claim?.state === "active" && Number.isFinite(startedAt) && startedAt < FIRST_DASHBOARD_PREVIEW;
}

export async function readLegacyPair({ directory = ACTION_HOME, ...options } = {}) {
  return readLegacyPairRecord({ ...options, directory });
}

export async function readProducerChecklist({ issueUrl, revision, pr, origin }) {
  if (!SHA256.test(origin?.launchId ?? "") || origin.pr !== pr?.number) return null;
  const directory = path.join(ACTION_HOME, "producer-reviews");
  const filename = path.join(directory, `${origin.launchId}.json`);
  try {
    const [parent, file] = await Promise.all([lstat(directory), lstat(filename)]);
    if (!parent.isDirectory() || !file.isFile() || file.size > 8192
        || [parent, file].some(info => info.uid !== process.getuid() || (info.mode & 0o077) !== 0)) return null;
    const raw = await readFile(filename, "utf8");
    const { issue, issueRevision, prNumber, head, threadId, url, steps } = JSON.parse(raw);
    if (issue !== issueUrl || issueRevision !== revision || prNumber !== pr.number || head !== pr.head
        || threadId !== origin.threadId || !Array.isArray(steps) || steps.length < 1 || steps.length > 6
        || steps.some(step => typeof step !== "string" || !step.trim() || step.length > 400)) return null;
    const preview = new URL(url);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(preview.hostname);
    if (preview.username || preview.password || (preview.protocol !== "https:" && !(local && preview.protocol === "http:"))) return null;
    return { url: preview.href, steps, digest: createHash("sha256").update(raw).digest("hex") };
  } catch { return null; }
}

export async function sendChatPrompt(prompt, request, promptPath) {
  await writeFile(promptPath, prompt, { mode: 0o600, flag: "wx" });
  let result;
  try {
    const raw = await runTool(CHROME_HELPER, ["submit", promptPath, request], { timeout: 270_000 });
    result = JSON.parse(raw);
  } catch (error) {
    if (error?.code === "ENOENT") return { status: "refused", message: "Build the VERA Dashboard Helper on this Mac first." };
    return { status: "unknown", message: "ChatGPT did not return a receipt. Check the open Chrome chat before trying again." };
  }
  if (result?.requestNonce !== request || result.mode !== "submit" || typeof result.sendInvoked !== "boolean") {
    return { status: "unknown", message: "ChatGPT returned an unreadable receipt. Check the Chrome chat before trying again." };
  }
  const openUrl = CHAT_THREAD.test(result.threadURL ?? "") ? result.threadURL : undefined;
  if (result.ok === true && result.sendInvoked && result.promptObserved && result.assistantResponseObserved && openUrl) {
    return { status: "observed", message: result.pinState === "pinned"
      ? "ChatGPT replied and the new chat is pinned." : "ChatGPT replied. Pinning was not confirmed.", openUrl };
  }
  if (result.sendInvoked) return { status: result.promptObserved ? "sent" : "unknown",
    message: result.promptObserved ? "The prompt was sent. A reply is not confirmed yet."
      : "Send was attempted. Check the Chrome chat before trying again.", openUrl };
  const reasons = {
    accessibility_permission_required: "Enable Accessibility for VERA Dashboard Helper in System Settings, then refresh.",
    composer_has_existing_draft: "Chrome has an unsent ChatGPT draft. Finish it before trying again.",
    chrome_unavailable: "Chrome is unavailable on this Mac.",
    high_effort_unverified: "The draft is open in Chrome. Set Thinking effort to High before sending.",
    prompt_verification_failed: "Chrome opened the draft, but the helper could not verify its text. Review it before sending.",
  };
  if (result.draftOpened === true || ["high_effort_unverified", "prompt_verification_failed", "send_button_not_unique_or_enabled", "send_action_unavailable"].includes(result.reason)) {
    return { status: "draft", reason: result.reason, message: reasons[result.reason] ?? "Chrome opened the draft, but automatic sending stopped. Review the chat before trying again." };
  }
  return { status: "refused", message: reasons[result.reason] ?? "ChatGPT did not show the expected composer. No prompt was sent." };
}

export async function seedCodexOwner({ cwd, model, effort, request }) {
  if (!SHA256.test(request)) throw new Error("Invalid owner request");
  const ack = `VERA_READY_${request.slice(0, 16)}`;
  const stdout = await runTool(CODEX, ["exec", "--json", "-C", cwd, "-m", model, "-c",
    `model_reasoning_effort=${JSON.stringify(effort)}`,
    `Reply exactly ${ack}. Use no tools, do not inspect or edit any file, and do no implementation work.`], { cwd, timeout: 90_000 });
  const events = stdout.trim().split("\n").map(line => JSON.parse(line));
  const ids = events.filter(event => event.type === "thread.started").map(event => event.thread_id);
  const replies = events.filter(event => event.type === "item.completed" && event.item?.type === "agent_message");
  if (ids.length !== 1 || !UUID.test(ids[0]) || replies.at(-1)?.item.text.trim() !== ack
      || !events.some(event => event.type === "turn.completed")) throw new Error("Codex did not confirm the prepared chat");
  return ids[0];
}

export async function queueAndOpenOwner(threadId, prompt) {
  if (!UUID.test(threadId)) throw new Error("A verified local owner is required");
  const stdout = await runTool(CODEX, ["queue", "--thread", threadId, "--message", prompt]);
  const receipt = /^Queued message ([a-f0-9-]{36}) for thread ([a-f0-9-]{36})\.$/m.exec(stdout);
  if (!receipt || !UUID.test(receipt[1]) || receipt[2] !== threadId) throw new Error("Codex queue receipt did not match the owner");
  try {
    await runTool("/usr/bin/open", [`codex://threads/${threadId}`]);
    return { status: "queued", message: "Message queued. Codex was asked to open the original chat; a response is not confirmed yet." };
  } catch {
    return { status: "queued", message: "Message queued, but the app did not open. Open the original chat to pick it up." };
  }
}

export async function ownerReceipt(filename, request, threadId) {
  try {
    const record = JSON.parse(await readFile(filename, "utf8"));
    return record.request === request && record.threadId === threadId && Number.isFinite(Date.parse(record.observedAt));
  } catch { return false; }
}
