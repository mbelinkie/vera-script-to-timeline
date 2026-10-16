# #192 first fast validation timeout

Fast1 againstbbcfba8b799f42d20b91fac49cca69ef8b704058 naturally exited1
without signal, all owned jobs drained. Immutable logSHA256
b88216fead89bb108b8c11e556614753b69b20b4d0f382dccea4c1cc70522fe5.
Generated contracts are current; all TS lint/types passed. Contract Vitest:
463 passed,1 failed,22 files; tooling Vitest1 passed. The failure is the
existing #144 omission bridge's finalization test exceeding unchanged5000ms
(call5823ms). Remaining Node and Python fast phases were not reached.

The exact failing test and its direct proof CLI/transform/compiler imports
are unchanged from accepted #190 bd6048. No #192 import is on that path.
A one-off host snapshot showed Chrome renderer46%CPU, WindowServer27% and
CodexGPU25%, with no competing validation/pytest job. This is supporting host
load evidence, not proof of the timing cause. Other possible mechanisms are
cold subprocess/module startup and test-order/resource pressure; these predict
a narrower warmed serial invocation will pass without any source change.

One focused invocation of the exact failed test on the same source/tools and
unchanged5000ms timeout passes in2010ms; the other14 tests are deliberately
not selected, not supplied as passing coverage. Retained focused57 receipt/
logSHA6c717103d8f9df5d2cf7e116bafef2cdf0c8342469180701c42d4e1dd7f063b2.
The existing test catches the timeout and checks exact compiler artifacts;
no new duplicate regression test or debug production instrumentation is needed.

No code, fixture, assertion, timeout, worker count, dependency or config fix
is justified by this isolated result. Fast1 remains failed. One whole fast
rerun is justified by the now-passing focused timing check and current idle
test queue; if the same resource failure repeats, stop identical retries and
retain a host-capacity blocker instead of weakening the gate. No host app is
closed or killed. Complete final acceptance still requires full evidence.

Runtime7's35-test pass is unaffected: executable/test/config/lock inputs
remain identical; this disposition is not read by those commands. Independent
Claude review has not started and awaits an actual complete fast pass.
