# VERA conductor: Zodex command-session exhaustion (2026-11-07)

## Incident and architectural finding

Zodex previously refused new `exec_command` calls with **64 running command sessions**.
The conductor is **not** the command service. The live conductor is the separate,
Mac-local `~/Desktop/ONGOING/vera-conductor` Node application; it launches ChatGPT
browser tabs, and those chats independently call the Zodex MCP command service in
Colima. Neither its pre-existing `lib/engine.mjs` nor `lib/zodex.mjs` launched
MCP command sessions or received their handles. It only inspected Zodex's durable
invocation history to estimate chat activity. Consequently, the old conductor
had no command ownership table, count guard, release API, or restart reconciliation
and could launch replacement chats while old commands might still be running.

**What cannot be established retrospectively:** After the user's machine restart,
the former 64 session handles cannot be enumerated. We cannot prove how many
were still-running OS processes versus completed processes retaining an MCP
handle. Zodex Local currently exposes `zodex local status --json`
(`active_process_count`, global) and `zodex local history --format json`
(durable invocation records), but no API for enumerating occupied session handles
or releasing them by owning agent. `history clear` is **not** command-session
cleanup. Never use `zodex local stop`, global process killing, or clearing history
as a substitute for scoped cleanup.

## Installed conductor-side protection

The tracked source, tests and idempotent deployment tool live in
`tools/vera-conductor-session-safety/`. The installer patches the Mac-local
conductor in place with a backup beside each modified file, without restarting
it or changing any pipeline state. Run from the Mac with:

```bash
python3 "$HOME/Desktop/ONGOING/VERA Script to Timeline/tools/vera-conductor-session-safety/install.py" \
  "$HOME/Desktop/ONGOING/vera-conductor" --dry-run
```

The working development worktree may also be used until merged.
Once the tracked code is on `main`, run the same command without `--dry-run` to
install. Verify with `cd ~/Desktop/ONGOING/vera-conductor && node --test test/*.test.mjs`.
It takes effect **on the next conductor process start**, not by killing a live
runner. A controlled conductor restart does **not** restart Zodex or ticket phases,
but check that no launch is in progress first. Never restart a Zodex container
or its command service merely to activate this guard.

- Conductor `zodex.sessionUsage()` queries the existing operator CLI with a
  15-second timeout. Unknown/unhealthy status blocks **new chat launches**;
  never silently assumes zero processes. The command exits promptly; it does
  not retain a persistent shell session.
- Defaults: `zodexSessionCapacity=64`, `zodexSessionWarnAt=48`,
  `zodexSessionPauseAt=56`. They are configurable in conductor `config.json`.
  Reservations are serialized and counted until the service can reflect them,
  preventing concurrent local launches from oversubscribing the reserve.
- Before launching a chat, an execution ID and owning conductor ticket/issue,
  phase, stage, timestamps and available identifiers are written atomically to
  conductor `state.json`. Launch failures are recorded, as are last reported
  agent ID, Zodex session handle, PID, exit code and end state when the chat
  supplies them. The prompts ask agents to poll every running command to exit
  and to write `/work/<repo>/.pipeline/<issue>/command-session.json` for the
  current execution. The report is untrusted and cannot authorize a kill.
- The running conductor checks the report and capacity on each normal tick,
  retains unverified orphan metadata across restarts, and does **not** retire
  session evidence just because the chat is old. It defers automatic same-phase
  recovery when *any* Zodex processes are active, because it cannot attribute
  those processes to an individual execution. When the service confirms **zero**
  active processes, recovery can proceed under the existing 15-minute idle and
  bounded-retry policy.
- `node conductor.mjs status` and `GET /api/state` (the existing authenticated
  board API) expose current usage, threshold state, tracked executions and
  uncertain cleanup status. The installer preserves `#159` and all other
  handoffs, worktrees and unrelated sessions. It does not terminate processes.

## Limits requiring a Zodex service change

**This is a protective conductor fix, not a complete service-level cure.**
`active_process_count` is the number of observed live processes, **not** the
number of occupied command-session slots. If exited-but-unpolled session handles
still consume the 64-slot registry, the conductor cannot detect the discrepancy,
release those handles, or guarantee free capacity. Nor can it prove whether a
specific stale handle remains live, even when an agent reports a PID. The full
acceptance criterion (a completed or abandoned command cannot consume a slot
permanently) therefore still requires changes to the external Zodex service:

1. On **process exit**, atomically move output/exit code to a bounded durable
   completed-results store and release live-session capacity, with or without a
   client poll. Handle timeout, crash, disconnect and duplicate exit/cancel races.
2. Add **out-of-band** read-only enumeration of active and completed handles,
   with owner agent/chat, process identity plus birth marker, execution ID,
   issue/phase metadata where supplied and timestamps. It must work at 64/64.
3. Add scoped, authenticated terminate/release-by-handle restricted to the
   original owner/lease; verify exact process identity and actual termination,
   never use PID alone, age alone or process-name matching. Preserve unrelated
   work and finished output.
4. Expose occupied-session count independently of OS active-process count so
   the conductor's 48/56 capacity gate can use the real bottleneck.

Until these APIs ship, do **not** describe orphan cleanup as automatic. A
capacity warning is a conservative prevention measure; orphan reclamation is
service-owned and unverified. At an actual 64/64 lockout, gather read-only
operator status/history and escalate a scoped service fix; never indiscriminately
restart or kill other agents.

## Verification

- `node --test tools/vera-conductor-session-safety/session-guard.test.mjs`:
  11 bounded synthetic cases: normal/failed/timed-out/unpolled commands,
  concurrent reservations, restart/crash, healthy overnight activity, late
  cancellation races, duplicate cleanup, capacity and unrelated owner isolation.
- Installer tested twice on an isolated conductor copy. Existing conductor
  `node --test test/*.test.mjs` remained green (80 tests) on the copy and on
  the actual Mac-local code after installation. No 64-command reproduction.
- Verify on every deployment: compare `/api/state.commandCapacity` with
  `docker exec zodex zodex local status --json` and test a new launch only with
  an authorized, disposable ticket. Check the existing ticket state after
  a controlled runner restart. No existing phase or branch is a smoke fixture.
