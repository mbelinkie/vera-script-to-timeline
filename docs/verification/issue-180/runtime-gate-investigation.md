# Existing CLI timeout investigation

Acceptance remains pending; these observations are not a passing full gate.

Full gate attempt 1 failed six existing CLI cases only on the unchanged
5,000 ms deadline. Attempt 2 failed twelve existing CLI cases on the same
deadline: 390 of 402 contract tests passed, including all 82 issue-180 cases.
No failed assertion or changed golden was reported. The frozen v1 CLI paths
do not import the modified v2 implementation. Both attempts' complete status
and losslessly compressed logs are retained here.

The tight replay probe is:
`node docs/verification/issue-180/cli-replay-probe.mjs uncached`.
It invokes the actual #144 compiler CLI twice on frozen v1 fixtures, asserts
successful results and byte equality, and fails when the pair exceeds the
existing 5,000 ms gate. It reproduced the failure at 11,477.7 ms.

Ranked hypotheses were host resource contention, repeated Node/TypeScript
startup cost, and a shared toolchain mismatch. Exact locked tools and 43
source/lockfile/golden hashes matched the tested snapshot, and all 6,270
protected files matched the accepted baseline. The varying failed cases and
varying call latency support contention rather than a semantic regression.
They do not identify a specific competing application or authorize stopping it.

An environment-only Node compilation-cache probe produced identical SHA-256
output but still exceeded the deadline at 5,889.0 ms and 7,914.8 ms. The exact
existing omission-finalization test also timed out with this cache (9,811 ms).
Node documents the cache as a compilation optimization, with a coverage
precision limitation: https://nodejs.org/download/release/v24.18.0/docs/api/module.html#module-compile-cache.
The full validation launcher was not changed to use it.

An isolated cached CLI call measured with `/usr/bin/time -l` took 8.30 s wall,
1.99 s user CPU, 1.61 s system CPU, 73,592,832 bytes maximum resident size,
8,176 page faults and 38,809 involuntary context switches. Read-only host
samples reported 16 logical CPUs, 16 GiB RAM, and load averages of
`12.02 / 26.98 / 30.45`, then `22.19 / 27.49 / 30.35`.
This is supporting environment evidence, not proof of a product defect.

The application-policy probe used the local `taskpolicy(8)` manual and
`/usr/sbin/taskpolicy -a node ... uncached`; its pair still failed at
7,873.3 ms with identical output. No other process was altered.

All four replay measurements share stdout SHA-256
`c5e25097b9126717c75807b7751c748da12faf4ede1ebd5f9a2213f135312aa8`.
JSON measurements and the assert-based probe are retained alongside this note.
No accepted test, timeout, fixture, golden, dependency, production code or
full-gate execution setting was changed to make a failure pass. A complete
unchanged gate must still pass before Automated closure.

Later capacity checkpoint: the uncached pair passed in 2,370.9 ms with the
same stdout SHA-256 (`cli-replay-capacity-recovered.json`). The exact existing
omission-finalization test still exceeded 5,000 ms without the cache (5,677 ms),
then passed with the cache (3,910 ms; one selected test, fourteen unselected).
This justifies retrying the complete gate with Node's standard compilation
cache enabled and recorded in status/tool profile. All full-suite selections,
assertions, default deadlines, schema and byte gates remain intact. This is
the only adopted environment optimization; no coverage gate is configured.
