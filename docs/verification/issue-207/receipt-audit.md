# #207 — existing-receipt and baseline audit

Read-only audit, 2026-10-14. No Resolve connection or getter was invoked.

## Verified assignment and baseline

App `list_threads` identifies this chat as
`01a13a9a-6438-7cc1-8b22-c879e37d31d4`, title
`#207 Define trusted read-only Resolve…`, exact 7e73 cwd. No inherited environment
identity was used. Initial worktree was clean/detached at
`deaa75c90b5486e500cb69266faa7bdf09697efc`; `git ls-remote --symref origin HEAD
refs/heads/main` independently returned that hash and remote default `main`.

`npm run roadmap -- inspect 207` confirmed Ready, Sol/high, Size S, P2,
Resolve Integration, Acceptance Producer, no existing claim, and #109/#177/#190
Closed/Done. The first mutation was successful exact-profile claim for this
chat/`codex/issue-207-target-identity-handoff`; the local branch was then created.
Account df07 ordinary usage allowed, primary 24%, secondary 79% used at entry.
This does not grant a later phase or native action.

## Evidence inspected and precise gap

| Retained boundary | Finding | Why it cannot bootstrap this operation |
| --- | --- | --- |
| [#109 accepted result](https://github.com/mbelinkie/vera-script-to-timeline/issues/109#issuecomment-6117134458), local `out/issue109/native-evidence/result-d787c44f67a142c4b145bddae9322185.json` in e7e2 | Independently read actual bytes and rehashed SHA256 `ec802ea507524cc821b0215f989d7b01dd235796700f9e7ee10fee009be86797`. Recursive key audit found project/timeline names, no UID fields. | Accepted source uses `GetUniqueId` internally, but its result does not retain those identifiers. Acceptance cannot be retroactively expanded. |
| [#109 plan](../../plans/issue-109-injected-delivery.md), `workflow_delivery.py` | New-target assembly, UID guards, None operator statement, saved/reopened verification. | Creates a new target after its own authority; no name-bound existing-target identity receipt. |
| [#177 accepted interface](../issue-177/README.md), [plan](../../plans/issue-177-v2-package-studio.md) | Public package/attestation and injected v2 loader. Planned new-target names and raw byte pins. | Package identity is not current Resolve identity; adapter readiness is not actual target evidence. |
| [#190 plan](../../plans/issue-190-v2-proof-bridge.md), `roundtrip_v2_native.py` | `delivery-complete.json` stores UIDs after guarded, separately authorized successful new-target delivery; evidence level `injected_execution_unqualified`. Recovery reads retained lineage only. | No previously retained actual completion for this selected target was supplied. Creating one now would cross the excluded mutation/qualification boundary. |
| `roundtrip_native.py`, `roundtrip_wi.py` | Synthetic #144 identity records and full structural reads within the existing proof lane. | Synthetic evidence is ineligible; the full reader exceeds the finite getter allowlist and requires its own proof/target authority. |
| #204 `native_qualification_v2.py` at f582 checkpoint below | Closed authority requires prior exact project/timeline names and UIDs. Runtime later rechecks them. | Result is downstream observation, including failed observations; using it to populate prior authority is circular trust. |

The actual #109 names are both
`VERA Delivery 13000000-0000-4000-8000-000000000036 3d52aae2aa40`.
These are evidence of its accepted historical run, not selection or current
authorization. No claim is made about the target currently open in Resolve.
Saved/nonproduction/None are operator attestations; runtime product/version and
names/UIDs are observations. Neither names nor hashes prove human authorization.

## Existing proposal and shared seam

Read only from the clean #204 checkout f582:
`docs/plans/issue-204-target-identity-handoff-note.md`, proposed CN-204-ID1,
and `docs/verification/issue-204/{operator-handoff,review-disposition}.md`.
Observed HEAD `de4ed9bb27748958bfa8720b60f0369fbad2e6c1`, clean branch
`codex/issue-204-native-preflight`.
That owner retained actual independent GO of production source
`724a829f6913eec7f939597c454c54aec5407058`, result SHA256
`7777cf850b1678ee59639cbea81d79153a27dd027a87c532cee794ad7b8a999f`,
and a later test/document checkpoint with unchanged production pins. These are
the owner's retained claims, not a new #207 review or rerun. No #204 source changed.

Its prepared host release SHA256 is
`d4ec949a5a197a54bc58c969bcb2655553064e4600fb11c6ba2f748bf6f33d66`;
no installed identity authority or receipt was supplied. New runtime bytes will
invalidate it. The new [CN-207-ID1](../../plans/issue-207-target-identity-handoff.md)
reuses that proposal's finite operation, adds exact receipt-consumption,
freshness/replay and ownership decisions, and replaces its unbound approval
wording. Neither proposal has been Producer-accepted in this task.

Direct `git diff --name-status` from accepted main to de4ed9b confirms the four
#204 runtime files, new #204 test and pinned CN-178-Q1 note are missing/changed
on main. The design's explicit source adoption is necessary; accepting #207
does not make #204 merged. A composed #208 tree needs its own review/evidence.

Remote default/main was rechecked after #192 closed:
`017e7cfb350bf8f2608d08e27fac5b9b72a5809e`. Its full diff from deaa75c adds
#192's core/tests/evidence and changes `roundtrip_v2_native.py`. The restricted
diff over the six named #204 prerequisite paths is empty. Thus there is no
observed overlapping path in this adoption; it does not prove runtime integration
or replace #208 checks. Preserve accepted #192's entire delta when composing.

This is an audit of the supplied accepted flows and retained result, not a
claim to inventory every private receipt on the machine. If an independently
audited receipt for the chosen target is later supplied, verify its actual bytes,
lineage, scope and freshness before considering reuse; do not silently treat
an arbitrary four-field JSON object as one.
