#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { NotificationOutbox, REPOSITORY, renderReport } from "./ci-notification-outbox.mjs";
import { consumeEvent, inspectCli } from "./ci-notification-consumer.mjs";
import { loadOrigin, publicBinding, findOriginForEvent, loadDeliveryAudit, saveDeliveryAudit } from "./ci-notification-origin.mjs";
import { decodeDocument, validateBinding, verifyRemoteEvent } from "./ci-notification-verify.mjs";

const root = `/repos/${REPOSITORY}`;
const ID = /^[0-9a-f]{64}$/;

/** Uses the existing local GitHub sign-in; the report consumer permits GET only. */
export class LocalGitHub {
  constructor({ registration = false, runner = spawnSync } = {}) {
    this.repository = REPOSITORY;
    this.registration = registration;
    this.runner = runner;
  }
  async api(method, url, body) {
    if (!url.startsWith(root + "/") || /[\r\n]/.test(url) ||
        (method !== "GET" && (!this.registration || !["POST", "PUT"].includes(method)))) throw new Error("Unsupported notification GitHub operation");
    const args = ["api", "--method", method, url];
    if (body !== undefined) args.push("--input", "-");
    const result = this.runner("gh", args, { encoding: "utf8", input: body === undefined ? undefined : JSON.stringify(body), timeout: 30000, maxBuffer: 4 * 1024 * 1024 });
    if (result.error || result.signal || result.status !== 0) {
      const error = new Error("Authenticated notification GitHub request unavailable");
      const status = /HTTP (\d{3})/.exec(result.stderr ?? "");
      if (status) error.status = Number(status[1]);
      else error.code = "offline";
      throw error;
    }
    if (!result.stdout.trim()) return null;
    try { return JSON.parse(result.stdout); }
    catch { throw new Error("Invalid notification GitHub response"); }
  }
}

export async function registerPublicOrigin(launchId, { github = new LocalGitHub({ registration: true }), directory, env = process.env } = {}) {
  if (!ID.test(launchId)) throw new Error("Invalid opaque launch ID");
  const record = loadOrigin(launchId, directory);
  if (!record || record.threadId !== env.CODEX_THREAD_ID) throw new Error("Registration requires the captured original runtime");
  const binding = validateBinding(publicBinding(record));
  const pull = await github.api("GET", `${root}/pulls/${record.pr}`);
  if (pull.state !== "open" || pull.base?.ref !== "main" || pull.head?.repo?.full_name !== REPOSITORY ||
      pull.base?.repo?.full_name !== REPOSITORY || pull.head?.ref !== record.branch) throw new Error("Origin PR no longer matches the registered branch");
  // Compare-and-swap with null forbids replacement of another launch's binding.
  return new NotificationOutbox(github).writeDocument(`registrations/pr-${record.pr}.json`, binding, { expectedSha: null });
}

export async function readManualEvent(eventId, { github = new LocalGitHub(), directory, now = Date.now } = {}) {
  if (!ID.test(eventId)) throw new Error("Invalid event ID");
  const stored = await new NotificationOutbox(github).read(eventId);
  if (!stored) throw new Error("No authenticated CI event found; open the PR's checks and Actions run manually");
  const { event } = stored;
  let independentlyVerified = false;
  const result = await consumeEvent(event, {
    verify: async (candidate) => {
      const verified = await verifyRemoteEvent(github, candidate);
      independentlyVerified = true;
      return verified;
    },
    findOrigin: async (verified) => {
      if (verified.bindingSha === null) return null;
      const binding = validateBinding(decodeDocument(await github.api("GET", `${root}/git/blobs/${verified.bindingSha}`)), { pr: verified.pr });
      return findOriginForEvent({ ...verified, branch: binding.branch }, directory);
    },
    loadAudit: () => loadDeliveryAudit(eventId, directory),
    saveAudit: (audit, previous) => saveDeliveryAudit(eventId, audit, previous, directory),
    now,
  });
  const report = independentlyVerified ? renderReport(event) :
    `CI notification has not been independently verified. Review [the workflow attempt](${event.runUrl}) and [PR #${event.pr}](https://github.com/${REPOSITORY}/pull/${event.pr}) manually. No delivery, review or acceptance is confirmed.`;
  return { eventId, result, report };
}

export async function main(argv = process.argv.slice(2)) {
  if (argv.length === 3 && argv[0] === "register" && argv[1] === "--launch") {
    await registerPublicOrigin(argv[2]);
    console.log("Public CI correlation registered; the local chat identifier remains private. Automatic delivery is disabled.");
  } else if (argv.length === 3 && argv[0] === "review" && argv[1] === "--event") {
    const reviewed = await readManualEvent(argv[2]);
    const status = { ...reviewed.result };
    delete status.navigation;
    console.log(JSON.stringify({ eventId: reviewed.eventId, ...status }));
    console.log(reviewed.report);
    // This command runs locally; this private URL never enters the public report.
    if (reviewed.result.navigation) console.log("Open the original chat (navigation only): " + reviewed.result.navigation);
  } else if (argv.length === 2 && argv[0] === "inspect-cli") {
    console.log(JSON.stringify(inspectCli(argv[1])));
  } else throw new Error("Usage: ci-notification-mac.mjs register --launch <opaque-id> | review --event <event-id> | inspect-cli <executable>");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(() => {
    console.error("CI notification unavailable; open the PR checks and Actions run for manual review. No Codex message was sent.");
    process.exitCode = 1;
  });
}
