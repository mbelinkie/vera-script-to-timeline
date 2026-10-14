# #208 independent review disposition — delta GO, real-app gate held

Actual Opus 5.5/high review on `b2bd045` returned **NO-GO**. It ran with safe
mode, strict MCP, empty tools and no session persistence using CLI 2.1.299.
Exit zero is reviewer execution evidence, not approval. Exact source/context,
actual model usage, result/exit hashes and raw findings are in `claude-r1/`.
Result SHA256:
`0ea6592198829eb7cc42c7ef192e3f569e7fa871cf57c0d44c5a4ee6b82b582f`.
Consumed source and HEAD were unchanged. No external acceptance follows.

## Blocking findings

- **B1:** Installed verification now owns only the declared v2 launcher and
  `vera-delivery-v2` subtree. Preserve neighboring v1/vendor plugins and the
  accepted safe regular `.DS_Store` tolerance. Undeclared code and symlinks
  inside the owned subtree still refuse. New synthetic tests include both
  actual bootstrap branches in a shared directory and retained neighbors.
- **B2:** Retain strict negative wall/monotonic interval refusal; replace the
  two-microsecond-only elapsed comparison with a bounded 500 ppm calendar-rate
  allowance plus two microseconds for datetime sampling precision. Evidence
  and precise limits are in `clock-evidence.md`. No fixed half-second step
  tolerance is added. ±50 ppm over 1800 seconds passes; actual negative steps
  and elapsed shortfalls beyond the supported bound refuse. Larger clock
  corrections remain uncertainty requiring fresh capture; no deadline changes.
- **B3:** Completed receipts validate original identity authority at the
  historical result finish, and separately verify issue/start/read/finish
  chronology. Live capture/bootstrap/guards still validate current expiry.
  Consumers retain `min(capability issue+1800, result finish+1800)`. Synthetic
  coverage exercises capture at T0+8 minutes, authority issuance and real
  capability controller at T0+31 minutes, then refusal after result expiry.
- **B4:** The embedded bootstrap now returns normally from its refusal helper.
  It never raises `SystemExit`. Subprocess tests no longer catch that exception
  and assert control returns after both retained identity/capability refusals.

The first blocker reproduction run failed five cases and passed three in
4.86 seconds. After the fixes those eight cases passed in 6.72 seconds.
Expanded checks exposed false clock refusals and two test setup defects:
cross-schema v1 consumption properly refused on closed authority fields before
version dispatch, and the second fake authority needed its own 0700 parent.
Expected refusal reasons and private-root setup were corrected; no assertion,
inventory, timeout, accepted test or authority boundary was relaxed. Failed
scrubbed iteration logs are retained in JSON envelopes with raw-output hashes.

## Applicable non-blocking findings

- **N1:** A final capability provenance/clock failure preserves its native
  outcome in Console. It cannot publish a successful hash receipt or supply
  qualification; refusal retention may be unavailable after provenance drift.
  The operator retains Console output and starts fresh. Do not invent a success
  or write through a changed unsafe binding to guarantee a report path.
- **N2:** Bootstrap request parsing now applies bounded regular single-link
  reads and strict JSON parsing before all finite dispatch, including ordinary
  #177 and v1 routes. This is an intentional fail-closed routing tightening.
  Their schemas, product/capability/build guards and accepted test bytes remain
  unchanged; connected ordinary-routing regressions must pass on this candidate.
- **N3:** Original identity failure is printed before refusal publication so a
  storage failure cannot discard its reason. Printed partial data is not a
  completed consumable receipt; original lineage and result/hash publication
  remain required.
- **N4:** Operator checklist now names private parent permissions, immutable
  installed request mode/link count, exact installed-root spelling and TCC
  access. These prerequisites are manual; no agent permission or installation
  action has been taken.
- **N5:** Hash acknowledgement/flags/typed confirmation are local procedural
  provenance. They neither authenticate a human nor exclude hostile same-user
  fabrication. The accepted operator trust boundary stays explicit.
- **N6:** The exact declared inventory copies remain intentionally finite;
  AST equality covers the independently checked bootstrap validator and tests
  check the connected release. Drift fails closed. No general inventory service
  or dependency is added.

New coverage includes matching unsafe authority/request bootstrap bindings,
actual capability bootstrap success/loaded residue/replay/retained refusal,
receipt/UID/expiry/approval/confirmation/marker/source/release/cross-schema
tampering before getters, individual CLI confirmation flags and wrong typed
confirmation/hash acknowledgement, complete getter order and blank UID refusal.
All remain synthetic and never qualify the installed Studio runtime.

Accepted CN-207-ID1, adopted #204 tests, frozen/shared/generated/lock boundaries,
ordinary #177 capability/build guards and accepted #190/#192 native sources stay
unchanged. New runtime pins invalidate the old #204 release.

## Actual delta review and handoff

Actual Opus 5.5/high delta review returned **GO** on
`1b49081fe40271695a91e9136f3f6106332f8da4`. Its result SHA256 is
`24eecea00521cab681e2daa0506b7c7abd97d473233c2bfbeed7ef188005b67b`.
`claude-r2/` retains the result, exact context pins, startup and exit receipts.
The reviewer resolved B1–B4 and found no defect blocking the operator handoff.
The reviewer ran no tests; the fast pass is owner evidence. Review GO supplies
neither installation authority nor External acceptance.

After GO, both validator copies received only the same comment correction:
negative sampled intervals refuse, while sufficiently small between-sample
steps can be indistinguishable from supported rate/sampling uncertainty.
Their ASTs match the reviewed commit. No clock algorithm or deadline changed.
A forward wall-clock correction can conservatively distort receipt age;
uncertain clock behavior requires fresh capture. Runtime qualification remains
unobserved. The checklist now states Resolve-user ownership/readability and
that printed partial failures are not consumable receipts. The shared-root
import-shadowing watch item remains an actual-runtime observation requirement.

Additional synthetic coverage checks protected-output noncreation, a request
bound to another valid authority, and expiry during capability preflight.
The affected run passed nine cases; fresh lint, format and complete Python
type checks passed. The [handoff](operator/README.md) pins the fresh release
and records behavior equivalence and these remaining gates. Actual installed
identity and #204 capability reports still precede final full validation.
