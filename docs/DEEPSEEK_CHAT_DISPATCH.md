# Chat → GitHub → Mac dispatch (staged; disabled)

[Issue #396](https://github.com/mbelinkie/vera-script-to-timeline/issues/396)
continues on [Draft PR #397](https://github.com/mbelinkie/vera-script-to-timeline/pull/397).
The transport reuses the existing private bounded controller and lifetime USD10
ledger. The legacy personal-account GitHub Actions runner stays offline.

## Boundaries

The `issue_comment` workflow runs trusted default-branch code on `ubuntu-latest`
with read-only contents/issues permissions. It validates the exact
`/deepseek dispatch` comment, actor, open issue, classification, four opt-in
labels, handoff and canonical #378 review. It creates no local receipt and
never invokes the Mac adapter. No private credentials or worker output enter
GitHub Actions.

The separate Mac receiver makes outbound public GitHub reads. It has no incoming
listener or GitHub write token. It repeats the live authorization checks,
validates the private manifest, reserves one receipt per issue, then repeats
review/issue/comment/source and local manifest/build checks before invocation.
The receiver accepts only `live_enabled: false` and supplies explicit mock mode.
It cannot start a paid job. Its per-task ceiling is USD0.25; the existing private
controller retains its single lifetime USD10 ledger and live budget gates.

All four labels are required: `chat-reviewed`, `deepseek-eligible`,
`deepseek-ready`, `deepseek-dispatch`. Exactly one `type:implementation` or
`type:bug` is allowed. Pending review/escalation, design/non-coding types,
`deepseek-excluded`, another execution owner and `execution:codex/design/human`
veto dispatch. Ready status, labels, dashboard rendering and navigation never
start a job. #401 owns the renderer; this PR changes no renderer files.

## Shared private contract

Both processes read the same owner-approved read-only file (mode `0400`) under a
private directory (mode `0700`):
`~/.local/share/vera/deepseek/tasks/issue-N.json`.
It uses the adapter's existing `schema: 1` fields: `issue`, `repository`,
`base_sha`, `editable_file`, `editable_sha256`, `frozen_files`, `edit_scope`,
absolute `checks` vectors, `source_repo`, bounded `max_rounds` and
`max_output_tokens`, `task_cap_usd`, `task_instructions`, `operator_approved`
and `public_synthetic_only`.

The transport extension adds `transport_contract: "VERA_DEEPSEEK_RECEIVER_V1"`,
the exact `dispatch_comment_id`, `adapter_sha256`, `live_enabled: false` and a
bounded preapproved `mock_replacement`. `base_sha` must equal current GitHub
`main`; the runner bytes must match the approved adapter hash. The adapter
must verify `VERA_DEEPSEEK_MANIFEST_SHA256`, `VERA_DEEPSEEK_SOURCE_SHA`, comment
identity and `VERA_DEEPSEEK_EXECUTION_MODE=mock` before candidate preparation.
The receiver rechecks the same manifest/build immediately before invocation.

The previously installed adapter has no mock path and ignores the manifest hash;
it is incompatible with this contract. A private staged update is required.
Its candidate checks must use native deny-by-default Seatbelt confinement:
only the disposable candidate is writable, system runtimes and the candidate
are readable, and private home/controller/ledger files, network and Mach service
access remain denied. The trusted controller keeps credentials and ledger access
outside the candidate process. No private adapter source is published here.

## One authorized synthetic proof

On 2026-11-02 the Producer authorized one no-provider-call proof **after review
and protected delivery**. That authorization permits no paid mode. The target
still needs its own exact current canonical Chat review; the implementation
owner must not manufacture that approval record.

1. Complete review and protected PR delivery. Install only the reviewed private
   adapter build; preserve existing credentials, historical state and ledger.
   Keep repository and persistent local enable settings false. Use a separate
   clone of the public repository for `source_repo`, with no personal media or
   private configuration copied into the candidate.
2. Prepare a dedicated public synthetic issue using
   `scripts/fixtures/deepseek-proof`. Finalize its DeepSeek Handoff with the
   delivered source revision, one editable fixture and frozen check before its
   independent Chat approval. `target.py` intentionally fails `check.py` until
   the preapproved mock replacement changes its return value to `"after"`.
3. Initialize the receiver cursor with one explicit enabled poll **before**
   posting the dispatch command. A first poll only saves the newest comment ID;
   it intentionally ignores all existing comments. No scheduled poller is
   installed by this PR.
4. Post the separately authorized exact command, prepare the immutable manifest
   bound to that comment ID and approved adapter build, then run one enabled
   poll. The trusted adapter uses its cross-campaign lock, creates an isolated
   candidate, applies the approved mock replacement and runs frozen checks.
   Mock mode must never reach credential/provider code or write reservations.
5. Verify private candidate/check results, exact allowed diff and frozen hashes,
   unchanged lifetime ledger bytes, receipt identity and duplicate refusal.
   `worker-returned` alone proves only process exit, not candidate acceptance.
6. Restore disabled defaults. Record concise public evidence with no private
   paths/content. The candidate stays unmerged for independent integration.

## Receipts and recovery

[Manual recovery](DEEPSEEK_RECOVERY.md) defines #415's separate new-trial
approval and reconciliation contract. It does not enable this receiver or
permit replay of an existing dispatch receipt.

Receipts live under `~/.codex/deepseek-dispatch-receipts/issue-N/receipt.json`.
Parent and issue directories must be owner-owned, private and regular directories.
Exclusive directory creation reserves an issue once; atomic replacement prevents
receipt writes from following a substituted file symlink. Worker stdout/stderr
are suppressed. Timeout/error retains the receipt and candidate; no automatic
retry, receipt deletion, legacy trial reset or ledger reset is permitted.

A leftover receiver lock requires explicit reconciliation before another poll.
Removing an approval label prevents future calls when observed; REST reads cannot
provide an atomic transaction with a local process launch. The final repeated
checks narrow that race. Incomplete history, changed revision/build/manifest,
API errors, unavailable sandbox and uncertain outcomes fail closed.

## Evidence and remaining gates

Focused receiver/dispatch tests use temporary state, mock GitHub reads and a
stub runner. The fixture's red baseline/green replacement were checked in a
temporary directory. These checks do not prove the installed adapter or live
GitHub-to-Mac transport. The new contract and private staged adapter require
independent review and fresh exact-head CI before delivery. The one external
synthetic proof and Producer setup acceptance remain outstanding. No provider
request or receiver activation has been performed by this implementation.

Historical installation/ledger observations are in
[the issue checkpoint](https://github.com/mbelinkie/vera-script-to-timeline/issues/396#issuecomment-6580646227).
Provider charges, model/pricing and all historical/pending spend require separate
reconciliation and explicit authorization before any future paid pilot.
