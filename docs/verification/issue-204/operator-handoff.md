# #204 — read-only operator handoff (runtime gate held)

The source at724a829 has passing focused/fast development checks and independent
Claude delta GO. A concrete release is prepared below. Installation and actual
preflight still require the exact trusted UID handoff, operator-issued authority
and coordinator/runtime grant. Final full validation follows actual External
evidence and any runtime fixes. No installation, authority/request, native report
or External acceptance has been produced.

## Prepared exact artifact and remaining identity gate

Release prepared from unchanged reviewed production bytes:
`out/issue204/operator-r1/release/` in this f582 worktree. Manifest raw SHA-256:
`d4ec949a5a197a54bc58c969bcb2655553064e4600fb11c6ba2f748bf6f33d66`.
It contains `VERA Delivery v2.py` and declared `vera-delivery-v2/` runtime.
Source and release inventory/hashes are retained in `operator-preparation.json`.
Host release preparation exited0; no files were copied into Resolve.

Known audited nonproduction target names from #109 are both:
`VERA Delivery 13000000-0000-4000-8000-000000000036 3d52aae2aa40`.
Its exact accepted native result hash is
`ec802ea507524cc821b0215f989d7b01dd235796700f9e7ee10fee009be86797`;
the actual file was rehashed and its identity keys inspected. It does NOT
contain project/timeline UIDs. Thus this artifact alone cannot complete the
authority. No guessed UIDs, failed-#204 observations or arbitrary scripting
may supply the missing identities. Coordinator/Producer must select a trusted
existing audited UID handoff for an already saved disposable target, or make a
separately bounded identity-handoff decision. This handoff adds no discovery
operation or authority to perform one.

The bounded proposed resolution is
[CN-204-ID1](../../plans/issue-204-target-identity-handoff-note.md). It would let
the operator supply only the two visible names; an explicitly approved installed
read-only identity step would retain the UIDs for the subsequent preflight.
This proposal is not implemented or approved. Do not present the commands below
as ready until that identity gate has actually been resolved.

## What the operator can do now

1. Choose an already saved disposable NONproduction project and timeline in
   Resolve; provide their exact visible names. The known accepted #109 synthetic
   target above is a candidate, not a substitute for operator selection.
2. Confirm External Scripting is None and that the requested work is read-only.
3. Review the proposed identity-handoff decision. Do not discover invisible
   UIDs, paste a console script, install the current release or launch #204 yet.

Agent preparation is complete for the current reviewed release and evidence.
After an approved identity route and runtime grant, the agent provides exact
ready files/paths and concrete operator steps. The only pending Producer
decision is the bounded trusted-identity route; the commands below are internal
reference for that later agent preparation, not a current copy-and-run handoff.

## Exact scope and selection

Use the delivered `codex/issue-204-native-preflight` revision with locked
Node24.19.0/npm11.17.0/uv0.12.5/CPython3.12.14. The installed controller is
stdlib-only. Retain the original readiness commit and approved CN-178-Q1 note
hash `c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740`.
No ordinary fractional/source-audio delivery guard is amended by #204.

Choose a previously saved, already existing, disposable NONproduction project
and timeline. All four exact identifiers are required: project/timeline names
and UIDs. Reuse a retained audited installed-flow result identifying that same
target if available; do not invent UIDs from names, obtain them by arbitrary
console/MCP scripting, or substitute a production target. If there is no
trusted identifier handoff for the chosen target, stop before authority
preparation and return that precise missing boundary to the coordinator.
The product preflight checks those identifiers; it never searches for, selects,
creates or saves a target on the operator's behalf.

Use a fresh private attempt directory outside this repository and installed
plugin root. The prepared release, authority/request and `native-evidence/`
must remain separately identifiable. Evidence cannot contain any source,
approval or authority input. Keep the checked repository and prepared release
unchanged and readable by Resolve throughout the run.

## Preparation after grant

1. Agent prepares the reproducible release through the existing command,
   supplying a fresh absolute release directory:

   ```sh
   rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli release --output <absolute-private-release-directory>
   ```

   Retain release manifest/hash and all declared source hashes. The new
   controller is an explicit inventory entry, not an extra file added later.
   Expected: immutable v2 release; no Resolve connection or installation.

2. After the agent supplies identifiers from the approved handoff, the operator
   reviews them, saves that disposable target,
   confirms External Scripting None, and explicitly issues its independent
   read-only authority through the public command. Replace bracketed values
   with the actual retained names/UIDs/absolute paths, never guessed values:

   ```sh
   rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli capability-authorize --release <release-directory> --approval "/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation/issue-145/advance-inputs/issue178-producer-cn178q1-approval.json" --operator <operator-name> --project-uid <exact-project-uid> --timeline-uid <exact-timeline-uid> --project-name <exact-project-name> --timeline-name <exact-timeline-name> --output <new-authority-path> --evidence-dir <new-evidence-directory> --confirm-saved-disposable-nonproduction --confirm-read-only --external-scripting-none
   ```

   This explicit operator step is a local trust handoff following #109. It is
   not a cryptographically signed credential or a claim that saved/nonproduction
   status is independently discoverable. Request preparation does not issue
   this receipt. The agent must not supply the confirmations for the operator.

3. Prepare a request consuming that separately issued immutable authority:

   ```sh
   rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli capability-request <authority-path> --output <new-request-path>
   ```

   Expected: exact request/authority/release/source/approval/target binding.
   Missing/mismatched authority, changed source or wrong paths refuses without
   getters. Retain hashes. No package/media/narration work is involved.

## Installation and one actual read-only launch

4. Follow [#109's quit/archive/copy/restart flow](../../resolve-workflow-integration-v1.md)
   using this release's `VERA Delivery v2.py` and `vera-delivery-v2/` entries.
   Archive previous owned v2 entries together outside the plugin root; preserve
   existing v1/plugins. Copy the exact request as `vera-delivery-v2/request.json`.
   Never merge source directories or relaunch an already loaded VERA runtime.
   Retain actual installed inventory/release/request hashes and private file
   permissions. No agent installer or external connection fallback is provided.

5. Operator opens Studio, confirms None, restarts as necessary and opens the
   same saved disposable target. Record names/UIDs from the audited handoff and
   current timeline/source state. Launch **Workspace > Workflow Integrations >
   VERA Delivery v2** once without concurrent interaction.
   Expected: `bootstrap-started-*.json` binds source/request/authority before
   imports, then `started-*.json`, `result-*.json`, `hashes-*.json` retain the
   actual injected runtime, supported21.1.1/build10, target and getter facts.
   An integrity failure retains `bootstrap-refusal-*.json` when the safe private
   directory is available; otherwise retain the Console's refusal text without
   running another script.

6. Inspect the actual `result-*.json`. Both `qualified` and `verified` stay
   false; `futureEffectsAuthorized` stays false. Supported getter visibility is
   distinct from full route/control or render qualification. An unavailable
   method/partial scalar remains unsupported/ambiguous. If current identity
   drifts, version differs or an input changes, expect `stopped_safely` with
   source-tagged evidence up to that boundary. No target setter, save, import,
   export, queue insertion or render start is called. Do not infer a pass from
   lack of a process or a menu launch alone.

7. Review every programme/clip/track/bus/master gap plus PCM/picture format,
   codec, resolution and existing queue-field visibility. Empty queue means no
   candidate exercised. #110's earlier WAV setter refusal remains historical;
   this enumeration cannot resolve it. Unknown mixer effects/sends/automation/
   destination must stop future #190 capture/render until an exact accepted
   reader/consumer is supplied. Record the actual remaining route question.

8. Confirm the existing target's source/timeline/settings stayed unchanged and
   no production target was involved. Retain actual version/product/build,
   injection/interpreter, operator None confirmation, installed and host source
   hashes, request/authority/approval, raw getter facts, gap table, result/hash
   records and the operator confirmation. Reply `Accepted #204 read-only
   capability preflight, target <names/UIDs>, report <filename/hash>; existing
   target unchanged` or identify the first failing boundary and retained report.
   A reproducible fail-closed boundary can satisfy #204's factual investigation,
   but it cannot close #178 or authorize a build/render follow-up.

Coordinator then decides a bounded remaining owner/scope from actual evidence.
No successor, capability activation, native qualification, renderer, provider
or #145 human acceptance follows automatically from this handoff.
