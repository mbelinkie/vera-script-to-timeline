# #8 repaired graph-persistence candidate — standard64 native build verified

Automated verification is complete. Producer explicitly authorized “install
repaired preflight”; the repaired Graphics release and new standard64 preflight
request are now installed and verified. The interruption happened after the
successful file swap/audit; “resume” reverified it without reinstalling.
The new standard64 native build now verifies successfully after save/reopen.
Render, visual acceptance and issue closure are not claimed. Preserve both
failed native targets and all old evidence.
The consumed old build request is safely archived outside the plugin root.
The new preflight passed. Producer then explicitly authorized only standard64
`d6c79d790514` and confirmed External Scripting None. Its new build request is
installed and was invoked once by the operator. It is now consumed: DO NOT
launch this installed build request again.

## First case — native verification and badge/text visual check passed

Native result: out/issue8/native-evidence-75325e0/standard-64/result-4b014c521d0849ffada659641dbf59fd.json,
SHA256 `6ba3859e6b5114d3447063c060b8eb7900469330d7e21117391966b358db7168`.
Status verified/verifiedtrue, zero discrepancies, one graphic observation,
verifiedAfterReopentrue, V4/start0/duration64, expected Finland/2024 semantic
snapshot and blank overrides. Studio21.1.1build10, injected3.14.7, verifier3.12.14.
Result companion hash and exact request/release/attestation bindings all pass.
This is actual native evidence, not an offline replay. The agent did not run
Resolve. Retained checkpoint: out/issue8/repaired-standard-64-native-checkpoint.json.

In the saved/reopened target ending d6c79d790514, play the V4 graphic and check
the Finland badge, authored automatic text, and entrance/exit without visible
errors; retain a render for frame-accurate 48-frame entrance/16-frame exit review.
Do not run Graphics again. Six other native cases, six-case visual/render
evidence and changed-build isolation remain pending. No acceptance is inferred
from the operator saying only that the launcher ran. Historical installation
sequence below records earlier stages; the latest result supersedes its
not-yet-executed statements.

### Operator feedback after inspection — not full visual acceptance

Producer reports disabling V5 to see V4, seeing the Finland Windows95man
badge, manually extending V4 with the graphic extending too, and an undesirable
full-atlas timeline thumbnail. Retained screenshot:
out/issue8/standard64-atlas-thumbnail-operator.png, SHA256
27a0c71279e929b562125a53a56ec964fce43a598fb707ee442ee2419b1712a1.

Both original and Transport manifests explicitly contain the authored
UNRESOLVED VISUAL: Choose an opening visual placeholder on V5/start0/duration64,
above V4. A small read-only manifest assertion reproduces that overlap. It is
not a Fusion-generated warning or proof that graphic placement failed. This
test scaffold should have been disclosed before the visual checklist. Isolate
V4 from this known placeholder for visual inspection/render; do not delete or
silently alter the frozen compiler package.

The atlas-backed seed clip is documented in the approved plan and package
writer. Screenshot shows the atlas in clip thumbnails, not in final output;
the exact Resolve thumbnail-selection mechanism/remedy is still unverified.
Separate bounded investigation [#221](https://github.com/mbelinkie/vera-script-to-timeline/issues/221)
was filed Inbox only after open/closed duplicate searches. No implementation
or #8 scope expansion is authorized; thumbnail polish does not gate #8.

The historical verified native receipt remains valid for the saved/reopened
state it checked, but the Producer subsequently changed track enablement and
clip duration. Do not represent the current modified timeline as an untouched
64-frame case or the manual extension as 120-frame timing acceptance. Do not
rerun the consumed request or silently restore/edit the target. Text, rendered
badge pixels, original frame-accurate animation and remaining cases are still
unaccepted at that checkpoint. Producer subsequently confirmed:
“The text appears. This test passes.” Record the Finland badge and authored
automatic-text visual check as accepted for this target. Receipt:
out/issue8/standard64-producer-visual-acceptance.json. This resolves the text
question, without converting the manually extended timeline into an untouched
64-frame timing/render sample. Remaining render, timing, six native cases and
changed-build isolation gates still apply.

Next case is overrides64, The Code / Nemo, target
VERA Delivery 88000000-0000-4000-8000-000000000002 959ff2d2d1a0.
Its source-bound preflight request is already prepared. Wait for closed Resolve
and request-install approval before swapping the consumed standard64 request.
No overrides64 build authorization is inferred from this visual acceptance.

## Current installed request — overrides64 preflight, not build

Operator has now run this preflight once: statuspreflight_passed, no
discrepancies, Studio21.1.1build10/injected3.14.7/verifier3.12.14, finished
2026-10-16T03:47:35.394858+00:00. Actual result
out/issue8/native-evidence-75325e0/overrides-64/result-b22ab8677791495bbb0091fc12ac697a.json
SHA2561a61cca1442066d49a35cd1c82620f301355c86e441bd27f2cf04f5850128272
matches companion and exact installed request/release/graphic attestation
bindings. Receipt: out/issue8/overrides64-preflight-checkpoint.json. No project
creation/graphic observation or build authorization inferred. Next: quit Resolve
and explicitly authorize overrides64 target959ff2d2d1a0 plus current None before
any build-request preparation/install. Do not repeat this successful preflight.

Producer said “install next preflight”, then “closed”. First process check
still found Resolve, so no mutation happened then. After “closed”, checks and
immediate guarded swap confirmed Resolve absent. Archived consumed standard64
build request outside discovery to out/issue8/installed-request-archive/standard-64-build-75325e0.json,
retaining d5306b7a...; copied only overrides64 preflight request mode0400.
Installed SHA256 b640ae07b9d4ec87dbae4c75eeeac4c459499ceafd7df47b585303c1639f3fe6.
Releaseb00dccc6..., all11 source hashes/sizes and exact file/directory closure
unchanged; all15 package-file hashes and Transport attestation checked. Prior
standard64 result unchanged; next evidence directory absent. Receipt:
out/issue8/overrides64-preflight-installation.json. No settings/project/native
operation or new build authorization occurred.

Next operator starts Resolve fresh, keeps External Scripting None, opens the
ORIGINAL separate saved disposable current project/timeline on Edit (not any
generated VERA build target), then Workspace > Workflow Integrations > VERA
Graphics v1 ONCE. Expect preflight_passed for target959ff2d2d1a0, with no new
project creation. Return result or first error; do not rerun if uncertain.
Only after successful preflight and explicit exact-target approval may a build
request be prepared/installed. Historical installed-standard64 statements below
refer to earlier stages; this overrides64 preflight is now the active request.

## Qualifying evidence

Tested clean commit `75325e01015ff5b5285acbc980bf78e16a49ae1a`, tree
`66bcb7f43c7edae66afa9da03a29a7572a19c6a2`. Production/test/config/lock/
contract/fixture bytes equal the reviewed source; only completed-evidence
checkpoint text followed review. Source stayed unchanged throughout the run.

Command: `VITEST_MAX_WORKERS=1 PYTEST_ADDOPTS=--durations=25 npm run validate`.
Node24.19.0/npm11.17.0/uv0.12.5, locked CPython3.12.14, darwin-x64,
FFmpeg/FFprobe8.1.2. Durable exit0; all729Python cases passed4965.39s
(1:22:45), no skips/deselections,439contracts/23files,1tooling,6progress,
23roadmap and32cloud cases. Generated-currentness, lint and types all passed;
Ruff427formatted files, mypy132files.

- Full log: `out/issue8/validate-full-graph-persistence.log`, SHA256
  `721d1191590ba5e538e73403523bc3d7e94c65933aa78a4667bafcc631c41906`.
- Actual exit receipt: `out/issue8/validate-full-graph-persistence-exit.json`,
  SHA256 `3edd82d4e49f89c30270dee752ac018539f4dc6848d7a33b1553404e6f8b58af`.
- Adversarial Claude review: GO/no blockers, durable exit0; log
  `out/issue8/claude-graph-persistence-review.txt`, SHA256
  `7227e20720fd04524770fc1f63578e3b864ebf8ad1b1b63efd07561222e6bad0`.
- Affected126 and fast484Python/439contracts passed before review. Original
  red tests, integer-candidate failed authentic replay and native failures
  remain retained, never relabeled. Corrected exact-source-bound actual
  witness replay passes offline; this is not another native execution.

Post-run Git comparison to the tested commit was clean; frozen audits against
7cb942e/4e31565/8ef9f864 passed again. All active validation/media jobs drained.
#8 explicitly released the heavy slot in its owning chat. Validation timer is
PAUSED. The independent closure-notification timer stays active, and will tell
“steward for Sweden sample sequence” only after actual Closed/Done acceptance.

## Prepared artifacts

Paths are relative to `/Users/matthewbelinkie/.codex/worktrees/46d4/VERA Script to Timeline`.

- Release: `out/issue8/graphics-release-75325e0`.
- Manifest: `out/issue8/graphics-release-75325e0/vera-graphics-v1/release.json`,
  SHA256 `b00dccc6023e4e39f101bf71a133d871ebcf9c758e398fc11f36897661253aa3`.
- Handoffs: `out/issue8/handoffs-75325e0/<case>/{graphic,transport}.json`.
- Requests: `out/issue8/requests-75325e0/<case>-preflight.json`.
- Native evidence: `out/issue8/native-evidence-75325e0/<case>`;
  standard64 contains its successful preflight and verified native build.
- Complete preparation receipt: `out/issue8/operator-preparation-75325e0.json`,
  SHA256 `fb576191a222491b7aad2d8020d71504a37bd152bcb19f77b1563803b2a87448`.
- Preparation log: `out/issue8/operator-preparation-75325e0.log`, SHA256
  `c71383296b9ffd7c23037d77e4d5245cf7a67be20634eae2f1e3f40f4c13f65e`;
  separate durable exit receipt is0.

Exact release inventory and all11declared source files match the tested
checkout. Only studio_graphics_runtime.py differs from the old release. All
seven original packages stayed byte-identical during independent full-envelope
and Transport verification. All seven initial requests were preflight,
authorizationfalse, externalScriptingnull. The separately authorized standard64
build request below is the only exception; the other six remain unauthorized.
New runtime/launcher import from the exact bundle under
CPython3.14.7 `-I -B -S`, with no site packages; all11copied files pass focused
Rufflint/format. This covers the new equivalent copies without another full run.

| Case | Fresh project and timeline target |
| --- | --- |
| standard-64 | VERA Delivery 88000000-0000-4000-8000-000000000001 d6c79d790514 |
| overrides-64 | VERA Delivery 88000000-0000-4000-8000-000000000002 959ff2d2d1a0 |
| otis-64 | VERA Delivery 88000000-0000-4000-8000-000000000003 953d849f3f63 |
| standard-120 | VERA Delivery 88000000-0000-4000-8000-000000000004 7eda6f4deb70 |
| overrides-120 | VERA Delivery 88000000-0000-4000-8000-000000000005 ca5ffaf154a3 |
| otis-120 | VERA Delivery 88000000-0000-4000-8000-000000000006 d09981d245c5 |
| revised-120 | VERA Delivery 88000000-0000-4000-8000-000000000007 512372ce6db1 |

UUIDs still identify the same immutable compiled packages, but each attestation
has a new target nonce. None is the old failed target or an overwrite request.

## Retained operator sequence — authorized standard64 build (now completed)

1. Installation is complete under “install repaired preflight”. Resolve was
   closed before and after the swap and on resumed audit. Exact old Graphics
   entries/request are preserved in out/issue8/installation-archive-75325e0,
   outside plugin discovery. Only the two Graphics entries were replaced;
   all11declared files and exact file/directory closure match the tested release.
   Unrelated plugin entry inode/mode/size/mtime stayed unchanged. No settings,
   project or native action occurred. Request mode0400, actionpreflight,
   authorizationfalse, externalScriptingnull. Receipt:
   out/issue8/repaired-installation-receipt.json.
2. Fresh preflight passed on Studio21.1.1build10, injected Python3.14.7,
   finished2026-10-16T00:36:50.365721+00:00. Result
   out/issue8/native-evidence-75325e0/standard-64/result-3acb1885052842db9a62dbf6af18c49d.json,
   SHA256 b1ec6ef45984efeeb364f0ab66360ccb409c72e0355f8d2d0077fec80d101569.
   No discrepancies; readonly preflight did not create a project.
3. Producer explicitly said “Authorize standard-64 d6c79d790514; External
   Scripting is None”. With Resolve closed, prepared the new build request
   through the existing production CLI and archived the installed successful
   preflight request in out/issue8/installed-request-archive/standard-64-preflight-75325e0.json.
   Installed only the authorized request, mode0400. Exact source/inventory,
   release, handoff, old request and result hashes rechecked before/after.
   Producer now starts Resolve fresh, keeps None, opens the ORIGINAL separate
   saved disposable current project/timeline on Edit (neither failed target),
   then Workspace > Workflow Integrations > VERA Graphics v1 ONCE.
   Expected: creates only the new standard64 target above, saves/reopens and
   verifies it. Return the result path or first error; never rerun an uncertain
   invocation. Neither failed target may be reused or repaired.
4. New actual native verification at64/120frames, all semantic configurations,
   save/reopen, built-in badge/atlas pixels, renders/visual judgment and
   changed-build isolation remain required under the operator checklist. Keep
   #8 In review until that External evidence and required visual acceptance exist.

Installed release is now b00dccc6023e4e39f101bf71a133d871ebcf9c758e398fc11f36897661253aa3;
installed BUILD request isd5306b7a8a2dafb05951d184097a09c33ef1735107ccd0c3837187b57da6219d.
Archived successful preflight request retains21813459351e0863918c1e209cd6a8c2a56a3e5801b17db852d601360e221aa8.
Archived old release/request retain hashes f955e0f4.../6c00fb4a... exactly.
All pre-swap, post-swap and resumed-audit logs pass. Resolve was not launched
by the agent; the operator's later verified build result is recorded above.
Exact authorization and request-only
swap are retained in out/issue8/repaired-standard-64-build-authorization.json.
The earlier installation/preflight records describe their historical stage,
not this later explicit build authorization. Actual native/visual acceptance
and all remaining cases are still pending; #8 remains open.
