# #204 — installed read-only native capability preflight

Owner `01a1386b-1bc1-77d3-9390-bbc345b1c091`, gpt-6.1-sol/high,
branch `codex/issue-204-native-preflight`, f582 worktree. Starting readiness
commit `e4eac7c0009f88d8cd63da6cf5e520f884c2710b` preserves accepted main
`bd6048b02604954df037bf0b2dd01906e986d19d`. Claimed through roadmap at
2026-10-14T03:42:34.549Z after Ready/External/S, exact profile, no claim and
#109/#110/#156/#177/#190 CLOSED/Done were independently verified.

## Scope before implementation

Implement only CN-178-Q1 stage one approved by the Producer's exact
`Approve staged CN-178-Q1` reply. Note SHA-256:
`c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740`.
The separate privately retained approval receipt is read-only. #178 remains
unclaimed; this prerequisite supplies a factual gap report, not qualification.

Own new `native_qualification_v2.py`, minimal `workflow_v2_cli.py` and
`workflow_v2_launcher.py` dispatch plus `integrations/resolve/VERA Delivery v2.py`
bootstrap, new `tests/test_issue204_native_preflight.py`, this plan and operator
handoff. Existing `workflow_v2.py`, #190/#192 `roundtrip_v2_native.py` and
`roundtrip_v2_records.py`, accepted tests, shared contracts, generated types,
fixtures, goldens and locks remain read-only. No library dependency is added:
the installed controller uses stdlib and existing immutable-file publishing.
Generator impact: none. Ordinary delivery guards remain intact.

No `qualify_build`, setter, project/timeline creation, import/placement,
save/close/reopen/export, queue/start/render, external connection/UI fallback,
provider, research/private-media change or general render service. Only
getters on the already saved exact operator-named NONproduction target.

## Closed stage-one records and local trust

Use CN-178-Q1's record names with a finite stage-one field set:

- `vera-native-qualification-authority/v1`: `schemaVersion`, `issueNumber=204`,
  `action=capability_preflight`, `operator` (nonempty name), `issuedAt` (timezone
  timestamp), `invocationId` (UUID), `issuer` (locked CPython/tool identity),
  `binding`, `confirmations`. Binding contains `releaseRoot`, `releaseSha256`,
  `repositoryRoot`, `repositorySourcePins`, `target`, `evidenceDir`,
  `approvalPath`, `approvalSha256`. Confirmations are exactly explicit read-only,
  already-saved disposable nonproduction target and External Scripting None.
- `vera-native-qualification-request/v1`: `schemaVersion`, `issueNumber=204`,
  `action=capability_preflight`, the exact binding above, `authorityPath`,
  `authoritySha256`. No target creation or package/attestation fields exist in
  this stage. Unsupported operations and extra fields refuse before getters.
- `vera-native-qualification-result/v1`: unqualified/unverified result with
  request/authority/release/source/approval identities, actual runtime/target,
  source-tagged raw getter observations, complete visibility-gap tables,
  explicit stop reasons and immutable result/hash references. It grants no
  future native effect.

All records have exact keys; hashes are raw lowercase 64-hex SHA-256. Target
has exactly four nonempty bounded strings: project/timeline UID and name.
Paths are absolute regular paths without ancestor symlinks. Evidence is a
separate bound private directory outside repository/installed code and the
authority/approval inputs. JSON rejects duplicate keys, nonfinite numbers,
oversized records and unsupported scalars. Source pins cover the complete
declared installed runtime, bootstrap and owning host preparation tools.

Trust follows #109's local operator-command model, not remote credentials.
The operator explicitly issues a separate target-specific authority through
`capability-authorize` with the retained Producer approval, exact target and
read-only/saved/nonproduction/None confirmations. This is an operator step;
the agent must not invent or issue it. `capability-request` only consumes an
existing independently issued authority; it cannot issue one by hashing JSON.
The installed consumer rechecks receipt semantics, exact binding, tool/source
identity and current target before and after getter groups. A merely matching
hash, no-op verifier or method-name enumeration is not authority or success.

## Observations and truthful gaps

Read product/version, target identity, complete project/timeline settings,
tracks/subtypes/enabled/locked, item UID/properties/speed/enable/channel-map,
format/codec/resolution dictionaries and the existing queue. Getter absence,
exceptions, wrong scalar types, partial fields or changing context are retained
as explicit unsupported/ambiguous facts. Only finite documented getter names
may be invoked. Bound inventories prevent runaway enumeration.

Every #190 programme and route field appears for clip/track/bus/master as
applicable: enable/mute/solo/gain/pan/effects/sends/automation/destination/channel
map and programme limiter. Clip property visibility is not effective whole-route
truth. Missing bus/master/track mixer getters remain unsupported; no zero or
empty default is manufactured. PCM/picture candidate settings and optional
queue fields are separately classified; empty queue means no exercised evidence.

Retain #110's exact historical limitation: on Studio21.1.0/14 its WAV/lpcm
format enumeration existed but the format/codec setter failed; EQ/dynamics
current state was operator-only. Reuse those as reasons to preserve unproven
states, not as current21.1.1/10 results or permission to apply a preset.

## Checks and operator acceptance

Write new tests before the controller where practical, but do not execute
them during #192's reservation. Cover independent authority absence/mismatch,
request/release/source drift, duplicate JSON/symlinks, unsupported action,
wrong Studio version and target drift; all mutators are traps. Cover missing
and incomplete getters without fabricated defaults, loaded runtime/undeclared
release files, immutable refusal/report preservation and ordinary delivery
guard regressions through unchanged accepted tests.

After explicit grant: locked focused tests/fast checks, mandatory adversarial
Claude review of identity/path/source/request/authority/native seams, fix/delta
review, then final qualifying full evidence under VERIFICATION_POLICY. Record
actual exits, source/input/tool/environment/inventory hashes; next necessary
costly pytest includes `--durations=25`. Native External acceptance cannot be
replaced by cloud or fake tests. No commands have run for this stage yet.

Operator acceptance: follow the new handoff's exact release/authority/request
hashes and #109 quit/archive/copy/restart flow; save the named disposable target
manually, confirm None, launch once. Retain actual version/source/target-bound
gap report or first-boundary refusal and unchanged target evidence. Review
mandatory control and PCM/picture gaps. Any build/render follow-up needs a new
bounded owning decision after that real report; #204 never closes #178.

Entry usage 60% five-hour and 69% weekly used, below the >=97% stop threshold.
Static implementation may overlap #192 with disjoint ownership. Validation,
Claude, installation and every Resolve/media job remain held for explicit
coordinator grant. No owner polling, extra agent or automation is added.

## Static checkpoint after explicit resume

The coordinator relayed the 3%-remaining safe stop after the initial controller,
test file and plan edit. The Producer subsequently said `resume` directly in
this chat. A separate usage read was 72% five-hour/58% weekly used on account
`76e395df-e4f8-4a1a-a63b-3de3fb5abca5`; this was human-authorized continuation,
not automatic account-change resume. Latest static-phase read: 88%/60% used.
The actual #204 claim/branch still matched this chat and In progress.

Static draft now includes the controller, explicit operator authority command,
request consumer, existing installed launcher dispatch/bootstrap provenance,
truthful complete-control/candidate-render gaps and new refusal/preservation
tests. The operator handoff is
`docs/verification/issue-204/operator-handoff.md`. No module changed in #192's
`roundtrip_v2_native`/`roundtrip_v2_records` ownership. No ordinary delivery
guard, frozen fixture/test/contract/generated output or lock was edited.

No tests, compilation/import self-checks, formatting/lint/types, fast/full,
Claude, media/probe, installation or Resolve call has run. This code is a
draft, not a passing candidate. Next authorized check phase must first format
and inspect strict types/style, run the new tests and existing #177 handoff/
delivery/release regressions under the locked toolchain, fix findings, perform
the required adversarial review and obtain final qualifying evidence. Source
hashes are retained in `docs/verification/issue-204/static-checkpoint.json`;
these identify saved bytes, not validation results.

All owned jobs: none started, none live, nothing to drain. Heavy grant remains
absent. The static checkpoint does not release or inspect #192's jobs. Operator
identity/UID selection, separate authority issuance, installation/launch and
real unqualified gap evidence remain pending. The target UID handoff must come
from an existing audited result; if unavailable, return the exact missing
readiness boundary before preparing authority. Never guess or run a console
fallback. #204 and #178 remain open; no successor is dispatched.
