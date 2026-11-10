# #499 helper completion — Conductor phase 25, document Phase 6/12

**Current verdict: BLOCKED, not phase-done.** This phase preserves original
adopted PR #474, branch `zodex/499-adopt-pr474`, historical phases 1–19 and all
native intents, UIDs, unknown outcomes and receipts. It has **not** launched
an actual native M4 Roll, a four-stage native run, or strict #312 acceptance.

## Immutable scope and offline work

- The full unchanged `.pipeline/499/issue-499-vera-helper-completion.md` was
  read before work; SHA-256 verified exactly
  `816b5dd17611d5b8198a453ce6fe687d12c201f2438a2d6d88ed6a8e5617be18`.
- Starting adopted PR head: `c5ae173193c2d5165ada16da2ac354a6baecb7bc`.
  This is an addition to the existing code, not a new implementation or branch.
- New `resolve_test_bench_conductor_launch.py` provides one immutable,
  short-lived Conductor request, exact installed helper actor/source pin,
  case-private config/authority refs, independent `launchctl bootstrap`
  dispatch in the GUI user domain with an explicit non-restarting Aqua plist,
  a one-use fsynced launch claim, and a separate read-only verifier. A focus
  request has **no** native authority or edit-stage entrypoint. The complete
  M4 entrypoint delegates to the original four-stage controller, with checked
  expected config and authority SHA-256 at the actual full-loop admission and
  independently verified queue receipts before a positive result.
- One dispatch/launch claim can be consumed only once. `unknown-after-claim`
  or `unknown-dispatch` cannot be retried even if the process or native result
  disappears. The detached dispatcher is not a test result. Read-only probes
  distinguish pending submission, live runner and claimed-UNKNOWN. `verify` requires
  the exact original result, immutable launch/complete-loop intents and an
  original M4 job ID resolved from the same plan. It does not expire an old
  completed audit or require an unchanged installed helper on a later day.
- Simulated full four-stage controller and failure paths are exercised with
  injected native edges. The synthetic A policy additionally runs the **real
  TypeScript product inference and accepted revision** through the production
  Python bridge. Real media/session construction and all independent MOV/PCM
  verification remain subject to a later physical campaign; these simulations
  are **not** native acceptance receipts.

## Independent review and corrections

The mandatory independent read-only Claude Opus review was executed against
the initial Conductor source/test diff. Its seven concrete findings were:
expired historical verification, config/authority time-of-check/time-of-use
drift, adoption of a foreign completed M4 job, same-root flock deadlock,
crash-after-claim misreporting, unsupported focus window names, and loose
canonical/UNKNOWN audit verification. All seven were addressed in the code;
  new negative tests exercise the changes. A separate Opus delta review found
  five additional lifecycle/provenance/reporting concerns with the original
  `launchctl submit` approach. The implementation switched to explicit
  `bootstrap gui/<uid>` using an Aqua-only plist (`KeepAlive=false`) with a
  pinned Python executable, working directory and PYTHONPATH; it now disallows
  multiple request roots pointing at one native case and distinguishes
  submitted-unclaimed, in-progress and audit-invalid states. This new Mac path
  is tested via injected launchd calls, **not** physically demonstrated yet.
  Raw reviewer outputs and test logs are in `.pipeline/499/phase25-*`.

## Offline verification

- Final targeted Conductor/full-loop suite: **62 passed**.
- Final eight-suite GUI helper, M4 queue/runner, revision, edited stage,
  complete-loop and Conductor regression: **280 passed**.
- Ruff lint and format checks: PASS on both modified production Python files
  and the new Conductor tests. Focused mypy for all three: PASS.
- Git whitespace/diff check: PASS. Source graph, test logs, both review reports
  and planned checkpoint HEAD are to be pinned in the ticket handoff.
- `validate:fast` is explicitly the helper-plan Phase 8 gate, not this Phase 6
  gate. No claim of full repo `validate:fast` PASS is made here.

## Physical no-edit focus readiness: BLOCKED

Read-only checks through the authenticated Mac Bridge showed the signed
`org.vera.resolve-test-bench.gui` Aqua LaunchAgent **running**, with its
helper executable, but **no DaVinci Resolve GUI process**. A `ResolvePython`
background process was present; this is **not** an equivalent desktop PID or
an eligible exact disposable window. The active Mac repository checkout is
`feature/vera-master-roadmap-live-dashboard` at
  `09da6b15ae7fb9144b1c66fe21304c414d49003a`, not the frozen phase-25
  adopted-PR checkout. The Mac launchd domain was observed read-only and the
  supported submit syntax inspected before switching to a safer non-restarting
  Aqua bootstrap approach. An actual signed, exact-window
Conductor→runner focus rehearsal has **not** been performed.

**Do not** guess a PID/title, start an unknown previously used Resolve
project, reuse a consumed request, or claim that an injected `launchctl`
test is a physical no-edit PASS. Bring up a separate verified disposable
Resolve window with no other native case owner, have the Conductor deploy the
exact frozen adopted-PR checkout/build into the Mac Aqua session and issue
one fresh bounded focus-only request from another foreground application.
The signed helper must reply with the exact PID, window, source/actor and
foreground/menu observations; the detached runner must yield an independently
authenticated result. Until all that evidence exists, **remain in phase 25**;
never emit `phase-done` or advance phase 26.

## Acceptance boundary

The evidence for simulated behavior is useful but **insufficient for Phase 6
PASS**. In particular there is no actual no-edit Conductor launch/focus proof
and no frozen Mac runner checkout result. This is a partial, safe checkpoint.
Original PR #474 push, merge and issue transitions remain Conductor-only.
