#!/usr/bin/env python3
# ruff: noqa: E501 -- embedded JavaScript snippets retain upstream source formatting.
"""Idempotently install VERA conductor session protection into its separate Mac runtime.

Do not touch config.json, state.json, pipeline folders, or the running process. Imports
will be picked up by the NEXT normal conductor start; active phases are unaffected.
"""

import argparse
import os
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def replace_once(source, old, new, name):
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError(
            f"{name}: expected one insertion point, found {source.count(old)}"
        )
    return source.replace(old, new, 1)


def patch_zodex(source):
    point = "  return {\n    running,\n"
    replacement = """  return {
    running,

    // Status is global active *processes*, not occupied command-session handles.
    // It cannot reclaim leaked handles or identify their owner.
    async sessionUsage() {
      const result = await inContainer(["zodex", "local", "status", "--json"], { timeoutMs: 15_000 });
      if (result.code !== 0) return null;
      try {
        const data = JSON.parse(result.stdout);
        if (data.state !== "running" || data.runtime?.health?.mcp_ready !== true
            || !Number.isSafeInteger(data.active_process_count) || data.active_process_count < 0) return null;
        return { used: data.active_process_count, limit: config.zodexSessionCapacity ?? 64,
          source: "zodex-local-active-process-count" };
      } catch { return null; }
    },
"""
    return replace_once(source, point, replacement, "zodex.mjs")


def patch_engine(source):
    source = replace_once(
        source,
        'import { newNonce, sign, verify } from "./signing.mjs";',
        'import { newNonce, sign, verify } from "./signing.mjs";\nimport { createSessionGuard } from "./session-guard.mjs";',
        "engine import",
    )
    point = "  const now = () => deps.now();\n"
    replacement = (
        point
        + """  const sessionGuard = createSessionGuard({ state, query: () => zodex.sessionUsage(), now, log,
    capacity: config.zodexSessionCapacity ?? 64,
    warnAt: config.zodexSessionWarnAt ?? 48,
    pauseAt: config.zodexSessionPauseAt ?? 56 });
"""
    )
    source = replace_once(source, point, replacement, "engine guard")
    point = """  async function startPhase(ticket, prompt, note) {
    await needZodex();"""
    replacement = """  async function startPhase(ticket, prompt, note) {
    await needZodex();
    // Fail before archiving an existing handoff when no command capacity exists.
    if ((await sessionGuard.refresh()).blocked) throw new Error("Zodex capacity unavailable; phase start deferred");"""
    source = replace_once(source, point, replacement, "engine phase preflight")
    point = """    async build(ticket) {
      await needZodex();"""
    replacement = """    async build(ticket) {
      await needZodex();
      // Avoid claiming an issue or archiving a valid handoff under capacity pressure.
      if ((await sessionGuard.refresh()).blocked) throw new Error("Zodex capacity unavailable; build deferred");"""
    source = replace_once(source, point, replacement, "engine build preflight")
    point = """  async function launch(ticket, prompt) {
    const { tabId } = await launcher.open(prompt);
    if (ticket.tabId) await launcher.close(ticket.tabId).catch(() => {});
    ticket.tabId = tabId;
  }"""
    replacement = """  async function launch(ticket, prompt) {
    const execution = await sessionGuard.reserve(ticket);
    // Durable reservation BEFORE the external browser side effect. The single-run
    // lease prevents another conductor from overwriting this record.
    await save(state);
    const reportPath = ticketPaths(config, ticket.repo, ticket.number, ticket.title).containerRepo
      + `/.pipeline/${ticket.number}/command-session.json`;
    const safety = `\\n\\nZodex command lifecycle (execution ${execution.executionId}): `
      + `If exec_command returns status=running, immediately record its session_handle, agent ID, PID if available, and state=running in ${reportPath} as JSON with executionId=${execution.executionId}. `
      + `Poll that exact handle until terminal and update the JSON state to exited, failed, or timed-out with exitCode. `
      + `Do not abandon running handles, start an unlimited stream of commands, or terminate any other agent's session. `
      + `A long quiet healthy command is not abandoned merely because it is old.`;
    try {
      const { tabId } = await launcher.open(prompt + safety);
      sessionGuard.launched(execution.executionId, tabId);
      await save(state);
      if (ticket.tabId) await launcher.close(ticket.tabId).catch(() => {});
      ticket.tabId = tabId;
    } catch (error) {
      sessionGuard.launchFailed(execution.executionId);
      await save(state);
      throw error;
    }
  }"""
    source = replace_once(source, point, replacement, "engine launch")
    point = """  async function tick({ force = false } = {}) {
    pruneNonces();"""
    replacement = """  async function tick({ force = false } = {}) {
    pruneNonces();
    await sessionGuard.refresh();
    for (const ticket of Object.values(state.tickets)) {
      const report = await files.readJson(`${hostTicket(ticket)}/command-session.json`).catch(() => null);
      sessionGuard.report(ticket, report);
    }
    sessionGuard.reconcile(state.tickets);"""
    # Upgrade the first installed variant without appending a second tick loop.
    prior = """    for (const ticket of Object.values(state.tickets)) {
      if (ACTIVE.has(ticket.stage)) {
        const report = await files.readJson(`${hostTicket(ticket)}/command-session.json`).catch(() => null);
        sessionGuard.report(ticket, report);
      }
    }"""
    current = """    for (const ticket of Object.values(state.tickets)) {
      const report = await files.readJson(`${hostTicket(ticket)}/command-session.json`).catch(() => null);
      sessionGuard.report(ticket, report);
    }"""
    if prior in source:
        source = source.replace(prior, current, 1)
    source = replace_once(source, point, replacement, "engine tick")
    point = """    const used = ticket.recoveries[phase] ?? 0;
    if (config.autoRecover && used < config.maxAutoRecoveries) {"""
    replacement = """    const used = ticket.recoveries[phase] ?? 0;
    if (!sessionGuard.recoverySafe(ticket)) {
      // Silent long-running tests are healthy until positively proven otherwise.
      if (shouldAlert(`session-recovery:${ticket.key}`, 60))
        log(`${ticket.key}: automatic recovery deferred; command status unverified and Zodex has active processes`);
      return;
    }
    if (config.autoRecover && used < config.maxAutoRecoveries) {"""
    source = replace_once(source, point, replacement, "engine safe recovery")
    point = """      tickets, ready, brief, notReady,
      history: state.history.slice(0, 12)"""
    replacement = """      tickets, ready, brief, notReady,
      commandCapacity: sessionGuard.snapshot(),
      history: state.history.slice(0, 12)"""
    source = replace_once(source, point, replacement, "engine snapshot")
    return source


def patch_config(source):
    point = """  maxActiveChats: 2,
"""
    replacement = (
        point
        + """  zodexSessionCapacity: 64, // service hard ceiling
  zodexSessionWarnAt: 48,
  zodexSessionPauseAt: 56, // reserve capacity for recovery/diagnostics
"""
    )
    return replace_once(source, point, replacement, "config defaults")


def patch_entry(source):
    point = """    if (state.offer) console.log(`\\nOffered:"""
    replacement = """    const cap = state.commandCapacity;
    console.log(`\\nZodex command processes: ${cap?.used ?? "unknown"}/${cap?.limit ?? config.zodexSessionCapacity ?? 64}`
      + ` (${cap?.blocked ? "LAUNCHES PAUSED" : cap?.warning ? "WARNING" : "not under pressure"}); last checked ${cap?.checkedAt ? new Date(cap.checkedAt).toISOString() : "never"}`);
    const entries = Object.values(state.commandExecutions ?? {});
    console.log(`Tracked conductor executions: ${entries.length}, possible orphans: ${entries.filter(e => e.state === "unverified-orphan").length}; service-level cleanup unavailable`);
    if (state.offer) console.log(`\\nOffered:"""
    return replace_once(source, point, replacement, "status diagnostics")


def patch_test(source):
    point = """      ensureRunning: async () => zodexState,
"""
    replacement = (
        point
        + """      sessionUsage: async () => ({ used: 0, limit: 64 }),
"""
    )
    return replace_once(source, point, replacement, "fake zodex API")


def prepare(root):
    transformations = {
        "lib/zodex.mjs": patch_zodex,
        "lib/engine.mjs": patch_engine,
        "lib/config.mjs": patch_config,
        "conductor.mjs": patch_entry,
        "test/engine.test.mjs": patch_test,
    }
    changed = {}
    for name, transform in transformations.items():
        target = root / name
        old = target.read_text()
        new = transform(old)
        if old != new:
            changed[target] = new
    helper = root / "lib/session-guard.mjs"
    content = (HERE / "session-guard.mjs").read_text()
    if not helper.exists() or helper.read_text() != content:
        changed[helper] = content
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        type=Path,
        help="absolute path to the separate Mac vera-conductor directory",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir() or not (root / "lib/engine.mjs").is_file():
        raise SystemExit("Conductor directory not found; nothing changed")
    changes = prepare(root)  # fail all preconditions BEFORE writing anything
    for target in changes:
        print(
            ("WOULD UPDATE" if args.dry_run else "UPDATING")
            + " "
            + str(target.relative_to(root))
        )
    if args.dry_run:
        return
    for target, content in changes.items():
        old_mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
        if target.exists():
            backup = target.with_name(target.name + ".pre-session-safety.bak")
            if not backup.exists():
                shutil.copy2(target, backup)
        fd, name = tempfile.mkstemp(prefix=".session-safety-", dir=target.parent)
        try:
            os.fchmod(fd, old_mode)
            with os.fdopen(fd, "w") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    print(f"Installed {len(changes)} files. NO conductor restart performed.")


if __name__ == "__main__":
    main()
