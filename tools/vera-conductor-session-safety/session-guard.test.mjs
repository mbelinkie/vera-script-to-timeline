import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createSessionGuard } from './session-guard.mjs';

function setup({ used = 1, capacity = 64, warnAt = 48, pauseAt = 56, state = {}, query } = {}) {
  let clock = 1_800_000_000_000;
  const events = [];
  const make = () => createSessionGuard({ state, capacity, warnAt, pauseAt, query: query ?? (async () => ({ used })),
    now: () => clock, log: message => events.push(message) });
  const t = (number = 159, phase = 0, stage = 'building') =>
    ({ key: `vera-script-to-timeline#${number}`, number, phase, stage });
  return { state, events, make, t, advance: ms => { clock += ms; }, usage: value => { used = value; } };
}

test('normal completion retains metadata, exit code and prevents duplicate cleanup', async () => {
  const h = setup(); const g = h.make(); const ticket = h.t();
  const e = await g.reserve(ticket);
  assert.equal(g.launched(e.executionId, 123), true);
  assert.equal(g.report(ticket, { executionId: e.executionId, agentId: 'abcd', sessionHandle: 'zodex007', pid: 932,
    state: 'exited', exitCode: 0 }), true);
  assert.equal(g.report(ticket, { executionId: e.executionId, state: 'running' }), false);
  assert.equal(h.state.commandExecutions[e.executionId].exitCode, 0);
  assert.equal(h.state.commandExecutions[e.executionId].state, 'ended-reported');
  g.reconcile({}); assert.equal(h.state.commandExecutions[e.executionId].state, 'ended-reported');
});

test('failed and timed-out commands do not regress on delayed running notifications', async () => {
  for (const status of ['failed', 'timed-out']) {
    const h = setup(); const g = h.make(); const ticket = h.t(); const e = await g.reserve(ticket);
    g.launched(e.executionId); g.report(ticket, { executionId: e.executionId, state: 'running' });
    g.report(ticket, { executionId: e.executionId, state: status, exitCode: 124 });
    g.report(ticket, { executionId: e.executionId, state: 'running' });
    assert.equal(h.state.commandExecutions[e.executionId].terminationReason, status);
  }
});

test('commands that finish without a caller poll stay uncertain and are never killed', async () => {
  const h = setup(); const g = h.make(); const ticket = h.t(); const e = await g.reserve(ticket);
  g.launched(e.executionId); h.advance(90 * 60_000);
  g.reconcile({ [ticket.key]: ticket });
  assert.equal(h.state.commandExecutions[e.executionId].state, 'launched');
  assert.equal(g.snapshot().serviceCleanupAvailable, false);
  g.reconcile({});
  assert.equal(h.state.commandExecutions[e.executionId].state, 'unverified-orphan');
  assert.equal(h.state.commandExecutions[e.executionId].cleanup, 'service-required');
});

test('a crashed agent and conductor restart retain execution identity', async () => {
  const h = setup(); const first = h.make(); const ticket = h.t(312); const e = await first.reserve(ticket);
  first.launched(e.executionId, 19);
  const restarted = h.make(); restarted.reconcile({ [ticket.key]: ticket });
  assert.equal(restarted.snapshot().records[0].executionId, e.executionId);
  restarted.reconcile({}); restarted.reconcile({});
  assert.equal(restarted.snapshot().records[0].state, 'unverified-orphan');
});

test('multiple agents cannot spoof each other or claim an unrelated session', async () => {
  const h = setup(); const g = h.make(); const a = h.t(159); const b = h.t(312);
  const ea = await g.reserve(a); const eb = await g.reserve(b);
  assert.equal(g.report(a, { executionId: eb.executionId, sessionHandle: 'othersession', state: 'exited' }), false);
  assert.equal(g.report(b, { executionId: ea.executionId, pid: 99, state: 'exited' }), false);
  assert.equal(g.report(a, { executionId: ea.executionId, agentId: 'Aaaa', state: 'running' }), true);
  assert.equal(h.state.commandExecutions[eb.executionId].sessionHandle, null);
  assert.equal(h.state.commandExecutions[eb.executionId].pid, null);
});

test('silent but healthy overnight commands do not expire by age', async () => {
  const h = setup(); const g = h.make(); const ticket = h.t(448); const e = await g.reserve(ticket);
  g.launched(e.executionId); h.advance(12 * 60 * 60_000);
  g.reconcile({ [ticket.key]: ticket });
  assert.equal(h.state.commandExecutions[e.executionId].state, 'launched');
  assert.equal(g.recoverySafe(ticket), false);
  assert.equal(h.state.commandExecutions[e.executionId].recoveryDeferredAt != null, true);
  h.usage(0); await g.refresh();
  assert.equal(g.recoverySafe(ticket), true);
});

test('cancellation/restart report races are terminal and idempotent', async () => {
  const h = setup(); const g = h.make(); const ticket = h.t(); const e = await g.reserve(ticket);
  g.launched(e.executionId);
  assert.equal(g.report(ticket, { executionId: e.executionId, state: 'timed-out', exitCode: 124 }), true);
  assert.equal(g.report(ticket, { executionId: e.executionId, state: 'exited', exitCode: 0 }), false);
  assert.equal(h.state.commandExecutions[e.executionId].exitCode, 124);
});

test('capacity warns at 48, stops at 56, resumes after actual usage drops', async () => {
  const h = setup({ used: 48 }); const g = h.make();
  const e = await g.reserve(h.t()); assert.equal(g.snapshot().warning, true);
  g.launched(e.executionId);
  h.usage(56); await assert.rejects(g.reserve(h.t(312)), /capacity/);
  assert.equal(g.snapshot().used, 56);
  h.usage(64); await assert.rejects(g.reserve(h.t(312)), /capacity/);
  assert.equal(g.snapshot().used, 64);
  h.advance(3 * 60_000); h.usage(2);
  assert.ok((await g.reserve(h.t(312))).executionId);
});

test('parallel reservation respects the stop threshold without spawning 64 commands', async () => {
  const h = setup({ used: 54 }); const g = h.make();
  const results = await Promise.allSettled(Array.from({ length: 8 }, (_, i) => g.reserve(h.t(i + 1))));
  assert.equal(results.filter(x => x.status === 'fulfilled').length, 2);
  assert.equal(results.filter(x => x.status === 'rejected').length, 6);
});

test('failed telemetry fails closed; launch failures are recorded but not killed', async () => {
  const h = setup({ query: async () => { throw new Error('unreachable'); } });
  await assert.rejects(h.make().reserve(h.t()), /unknown/);
  assert.equal(h.state.commandCapacity.blocked, true);
  const other = setup(); const g = other.make(); const e = await g.reserve(other.t());
  assert.equal(g.launchFailed(e.executionId), true);
  assert.equal(g.launchFailed(e.executionId), false);
  assert.equal(other.state.commandExecutions[e.executionId].cleanup, 'not-started');
});

test('a late terminal report after stage transition can reconcile a known handle', async () => {
  const h = setup(); const g = h.make(); const ticket = h.t(); const e = await g.reserve(ticket);
  g.launched(e.executionId);
  g.reconcile({ [ticket.key]: { ...ticket, stage: 'blocked' } });
  assert.equal(h.state.commandExecutions[e.executionId].state, 'unverified-orphan');
  assert.equal(g.report(ticket, { executionId: e.executionId, state: 'running' }), false);
  assert.equal(g.report(ticket, { executionId: e.executionId, state: 'exited', exitCode: 0 }), true);
  assert.equal(h.state.commandExecutions[e.executionId].state, 'ended-reported');
});
