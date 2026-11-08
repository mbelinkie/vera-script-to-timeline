// Shared with the Mac's separate vera-conductor/lib/session-guard.mjs.
// Does NOT pretend to own Zodex command handles: only the Zodex service can release them.
import { randomUUID } from 'node:crypto';

const ACTIVE_STAGES = new Set(['briefing', 'building', 'fixing']);
const CAPACITY = 64;
const WARN = 48;
const PAUSE = 56;
const MAX_RECORDS = 256;

export function createSessionGuard({ state, query, now = Date.now, log = () => {},
  capacity = CAPACITY, warnAt = WARN, pauseAt = PAUSE, id = randomUUID } = {}) {
  if (!(Number.isInteger(capacity) && Number.isInteger(warnAt) && Number.isInteger(pauseAt)
      && capacity > pauseAt && pauseAt > warnAt && warnAt >= 0)) throw new Error('Invalid Zodex session thresholds');
  state.commandExecutions ??= {};
  state.commandCapacity ??= null;
  let reservationQueue = Promise.resolve();

  const current = () => Object.values(state.commandExecutions);
  function checkpoint(usage) {
    const checkedAt = now();
    const valid = usage && Number.isSafeInteger(usage.used) && usage.used >= 0
      && (usage.limit == null || (Number.isSafeInteger(usage.limit) && usage.limit > 0));
    // Never interpret an unknown/failed count as zero. A Zodex session leak may not
    // be reflected in active_process_count, so this is launch protection, NOT cleanup.
    const used = valid ? usage.used : null;
    const limit = valid ? (usage.limit ?? capacity) : capacity;
    const warning = used !== null && used >= Math.min(warnAt, limit);
    const blocked = used === null || used >= Math.min(pauseAt, limit);
    state.commandCapacity = {
      used, limit, warnAt, pauseAt, warning, blocked, checkedAt,
      source: valid ? (usage.source || 'zodex-local-active-process-count') : 'unavailable',
      limitation: 'Service does not expose owned session handles or scoped termination',
    };
    if (warning || blocked) log(`Zodex capacity ${used ?? 'unknown'}/${limit}: ${blocked ? 'pausing launches' : 'warning'}`);
    return state.commandCapacity;
  }

  async function refresh() {
    try { return checkpoint(await query()); }
    catch (error) { log(`Zodex session-capacity query failed: ${error.message}`); return checkpoint(null); }
  }

  function prune() {
    const entries = current().sort((a, b) => (a.issuedAt ?? 0) - (b.issuedAt ?? 0));
    // Never prune an unverified active execution just because it is old.
    for (const item of entries) {
      if (Object.keys(state.commandExecutions).length <= MAX_RECORDS) break;
      if (item.state === 'closed' || item.state === 'launch-failed') delete state.commandExecutions[item.executionId];
    }
  }

  async function reserveOne(ticket) {
    const usage = await refresh();
    if (usage.blocked) throw new Error(`Zodex session capacity ${usage.used ?? 'unknown'}/${usage.limit}; new chats paused (no sessions terminated)`);
    // One runner can reserve multiple launches before Zodex reports the processes.
    // Account for unreflected reservations, and serialize this calculation.
    const pending = current().filter(x => (x.state === 'reserved' || x.state === 'launched')
      && now() - x.issuedAt < 2 * 60_000).length;
    if (usage.used + pending >= Math.min(pauseAt, usage.limit))
      throw new Error(`Zodex launch reservations at capacity (${usage.used}+${pending}/${usage.limit})`);
    const executionId = id();
    if (!/^[a-f0-9-]{20,64}$/i.test(executionId) || state.commandExecutions[executionId]) throw new Error('Duplicate/invalid execution identity');
    const entry = {
      executionId, owner: 'vera-conductor', key: ticket.key, issue: ticket.number,
      phase: ticket.phase == null ? null : ticket.phase + 1,
      stage: ticket.stage, agentId: null, sessionHandle: null, pid: null,
      issuedAt: now(), launchedAt: null, endedAt: null, lastObservedAt: null,
      state: 'reserved', tabId: null, exitCode: null, terminationReason: null,
      cleanup: 'service-required',
    };
    state.commandExecutions[executionId] = entry;
    prune();
    return entry;
  }

  function reserve(ticket) {
    const next = reservationQueue.then(() => reserveOne(ticket));
    reservationQueue = next.catch(() => {});
    return next;
  }

  function launched(executionId, tabId) {
    const entry = state.commandExecutions[executionId];
    if (!entry || entry.state !== 'reserved') return false;
    entry.state = 'launched'; entry.launchedAt = now(); entry.tabId = tabId ?? null;
    return true;
  }

  function launchFailed(executionId) {
    const entry = state.commandExecutions[executionId];
    if (!entry || entry.state !== 'reserved') return false;
    entry.state = 'launch-failed'; entry.endedAt = now(); entry.cleanup = 'not-started';
    return true;
  }

  // Reports originate in a chat and are untrusted; they are never authorization to
  // signal a PID or release someone else's command. The execution ID and ticket
  // must match an existing conductor reservation. Final states cannot regress.
  function report(ticket, input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) return false;
    const entry = state.commandExecutions[input.executionId];
    if (!entry || entry.key !== ticket.key || entry.owner !== 'vera-conductor'
        || ['closed', 'launch-failed', 'ended-reported'].includes(entry.state)) return false;
    const phase = ticket.phase == null ? null : ticket.phase + 1;
    if (phase !== entry.phase) return false;
    if (typeof input.agentId === 'string' && /^[a-z0-9]{4,16}$/i.test(input.agentId)) entry.agentId = input.agentId;
    if (typeof input.sessionHandle === 'string' && /^[a-zA-Z0-9_-]{4,128}$/.test(input.sessionHandle)) entry.sessionHandle = input.sessionHandle;
    if (Number.isSafeInteger(input.pid) && input.pid > 0) entry.pid = input.pid;
    if (entry.state === 'unverified-orphan' && input.state === 'running') return false;
    if (input.state === 'running' || input.state === 'exited' || input.state === 'failed' || input.state === 'timed-out') {
      entry.lastObservedAt = now();
      if (input.state === 'running') {
        if (entry.state !== 'ended-reported') entry.state = 'running-reported';
      } else {
        entry.state = 'ended-reported'; entry.endedAt ??= now();
        if (Number.isSafeInteger(input.exitCode)) entry.exitCode = input.exitCode;
        entry.terminationReason = input.state;
        entry.cleanup = 'unverified-service-release';
      }
    }
    return true;
  }

  // Reconciliation cannot prove service release: state is marked uncertain on handoff,
  // crash or restart, not removed or killed. Preserves silent overnight executions.
  function reconcile(tickets) {
    const byKey = new Map(Object.values(tickets).map(t => [t.key, t]));
    for (const entry of current()) {
      if (['closed', 'launch-failed', 'ended-reported'].includes(entry.state)) continue;
      const ticket = byKey.get(entry.key);
      if (!ticket || !ACTIVE_STAGES.has(ticket.stage) ||
          (ticket.phase == null ? null : ticket.phase + 1) !== entry.phase) {
        entry.state = 'unverified-orphan';
        entry.cleanup = 'service-required';
      }
    }
    prune();
  }

  // Without per-execution liveness, only proof that the WHOLE service has zero
  // active processes can justify automatic same-phase recovery. A terminal
  // report for one handle is insufficient if a second command is still alive.
  // A stale age or quiet stdout is never proof. Never kill other agents.
  function recoverySafe(ticket) {
    const relevant = current().filter(x => x.key === ticket.key &&
      x.phase === (ticket.phase == null ? null : ticket.phase + 1));
    const entry = relevant.at(-1);
    const safe = state.commandCapacity?.used === 0 && state.commandCapacity?.blocked === false;
    if (!safe && entry) entry.recoveryDeferredAt = now();
    return safe;
  }

  function snapshot() {
    const records = current();
    return { ...state.commandCapacity,
      tracked: records.length,
      uncertain: records.filter(x => x.state === 'unverified-orphan' || x.state === 'launched' || x.state === 'running-reported').length,
      serviceCleanupAvailable: false,
      records: records.slice(-24).map(x => ({ ...x })),
    };
  }

  return { refresh, reserve, launched, launchFailed, report, reconcile, recoverySafe, snapshot };
}
