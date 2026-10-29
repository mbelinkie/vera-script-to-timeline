# Frozen selective outbound plans and continuation

Issue [#328](https://github.com/mbelinkie/vera-script-to-timeline/issues/328)
provides a small execution seam for #104/#157. It does not add their production
UI, conflict classifier, finishing preservation (#327), or music runtime (#100).

## Public seams

`@vera/contracts/selective-outbound` accepts semantic changes, each containing
one or more edits under one selection ID. A structural multi-edit and a
spanning-audio change each count once. Safe selection excludes blocked items;
clear selection cannot submit. Selection can be serialized independently of
navigation or component lifetime.

`freezeOutbound` copies the changes, sorts them in document order, and commits
the source revision, target identity, prior baseline, every selected/skipped/
blocked disposition, and edit payload to a canonical SHA-256 plan hash.
`startOutbound` and `loadOutbound` retain that exact plan and validate the
ordered outcome/receipt chain. Retrying consumes the saved attempt rather than
recomputing selection from a newer document.

`executeOutbound` takes an exclusive `OutboundStore` and an `OutboundAdapter`:

- `observe` independently reads current source, target and content fingerprint.
- `apply` receives an entire semantic unit and the stable plan/change key.
- `verify` independently checks the exact receipt against current native state.
- `reconcile` distinguishes a known unapplied operation, a verified applied
  operation, and an unknown outcome. Unknown must refuse another mutation.

The adapter owns the actual operation's capability and whole-unit readback;
representing arbitrary edit payloads does not make Resolve support them.
Earlier verified changes must read back before continuation. An uncertain
marker is durable before each mutation. A failure stops the plan and retains
later items as unattempted. Only the save that verifies the final selected
item also advances the baseline. Excluded items remain explicitly skipped or
blocked, rather than being accepted back into the source.

`@vera/contracts/selective-outbound-file-store` is the local journal used by
the native proof. It serializes ownership with an exclusive directory lock,
fsyncs a complete replacement, then atomically renames it. It refuses a new
plan, verified-receipt replacement, uncertainty reset, or completed-attempt
replacement. An abandoned lock requires inspection and is never cleared
automatically. Each replacement has a unique name; interrupted replacement
files remain retained without blocking a later authorized save.

## Evidence boundaries

The domain fixture has three selected changes, one skipped and one blocked.
It includes one structural multi-edit and one document-wide audio identity.
Its adapter has actual instrumented state and independently checked receipts;
this is domain evidence, not a Resolve capability claim.

The separate native harness is
`packages/contracts/src/issue-328-native-proof.ts`, with the bounded adapter in
`scripts/issue328_native_bridge.py`. It calls the same `executeOutbound`.
The supported experiment is two 24-frame video-only cut appends to one
duplicate of an issue-owned synthetic timeline, with failure before append 2
and a saved/reloaded retry. The original timeline stays unchanged and current
at normal command boundaries. Per-append start/result records prevent replay
after an unknown native call. Native receipts bind exact project/timeline identity,
media hashes, source bounds and timeline geometry. Reopening must retain both
the duplicate and the original.

The proof requires one exclusive Resolve operator. Its own bridge commands
share a host lock and recheck the current target before appending; Resolve's
current-timeline append API is not an atomic guard against a person switching
timelines between calls. No concurrent manual editing is qualified. Setup
accepts no loaded project, or an explicitly opted-in UID for the exact
empty `Untitled Project`, paired with a freshly captured full settings map
in a local `{uid, settings}` JSON snapshot. Two fresh checks require the same
settings, no timelines/current timeline, root clips/subfolders, gallery stills/color groups,
render jobs or active render before creation. After close, reopen similarly
requires the same new empty-project UID and full settings on both checks before
loading the saved issue-owned project. Finite whole-number floats normalize to
integers only for JSON transport; other values and all keys remain exact. It cannot unload another nonempty project. Each append requires a successful `SaveProject` acknowledgment and
fresh in-memory readback before its finished receipt. This acknowledgment is not
an independent disk-persistence proof; the actual close/load check is separate.

A killed or timed-out command may leave the duplicate selected or the project
closed. It remains an unknown operation, with no baseline promotion or automatic
cleanup/replay; inspect the application and retained records before any further
native work. A durable host marker blocks subsequent bridge commands before
connection after an interrupted process; the executor cannot automatically
reconcile against a potentially live earlier RPC. A signal handler calling more
native APIs would not establish that an earlier native call had drained. The qualified full-source append requests `[0,24)`; its 24-frame source EOF
reads back as source end 23 while record end is 24 and duration is 24. This is
a bounded EOF convention, not permission to accept arbitrary endpoint drift.
Both source files independently decode to 24 frames at 24 fps, 640×360, video only.

The snapshot is a trusted experimental input, captured by the sole operator
immediately after observing a fresh startup/default or closing a known saved
project, before editing. The harness binds that expected state; it does not
attest the provenance of an arbitrary supplied snapshot file. A changed default
must not be relabeled as fresh. This qualification does not cover admitting
arbitrary preexisting default projects.

This experiment introduces no transitions, audio processing, rendering, source
replacement or arbitrary human finishing. It does not prove that those
operations can be combined atomically. Production adapters must independently
qualify their capabilities and preserve or refuse affected unknown work.

## Results

The 43 focused TypeScript tests and 40 offline Python bridge tests pass. The
actual native continuation passed on **DaVinci Resolve Studio 21.1.1 build 10**,
Intel Mac, external scripting **Local**, through bundled ResolvePython. This is
the delta against RK-17's selected-timeline readback, RK-20's no-replay recovery,
and RK-42's distinction between domain intent and native execution.

The synthetic project `VERA_328_c291b4cd` retained project UID
`11bea5e8-1061-41e9-8e30-2a55609478fe`, original UID
`d87329af-8651-4bf2-a357-299e2a191d05`, and duplicate target UID
`96f288b5-7167-4ebb-9935-61a809796be4` through save/close/reopen.
The frozen plan hash remained
`ee5a81438531e9bfd3f2a8e1aba2762b6e1c7e3f629fb6eab6115916b126ca3d`.

| Stage | Native target | Attempt / baseline |
| --- | --- | --- |
| Setup | Red `[0,24)` duplicate | Two selected cut appends; original baseline |
| Injected failure before item 2 | Red `[0,24)`, blue `[24,48)` | Blue verified, red failed; original baseline retained |
| New-process journal reload and retry | Adds red `[48,72)` on the same target | Both verified; baseline advances to final fingerprint |
| Save/close/reopen | Same project, original, target and source identities; exact geometry | Original unchanged and current |
| Repeat completed retry | Still exactly three clips | Attempt and every native operation record byte-identical |

The baseline stayed `4a526bf8…` after the boundary failure, while current target
fingerprint was `ee8ac669…`; completion atomically set both to `d46713ea…`.
An independent final API read found one 24-frame red clip on the original and
exactly three 24-frame red/blue/red clips on the duplicate, with source start 0,
source end 23, record starts 0/24/48 and record ends 24/48/72. No active render
remained. The previously released #119 project was saved and preserved.

Two earlier setup attempts remain retained: the first stopped before import
because native frame rate was numeric `24.0`, and the second stopped after a
23-frame initial cut exposed the exclusive append argument convention. The
fix compares exact numeric settings and requests end frame 24; neither stopped
target was reused or deleted. The offline append fake was corrected to model
the measured exclusive request endpoint. This run does not render/decode the
native timeline, kill a live native RPC, qualify interior source endpoints, or
prove arbitrary structural, audio or finishing operations. Those limits remain
separate from the positive cut-only continuation result.


The final fast gate passed on `71f56411`, including 1,988 Python cases. A bounded
Claude delta review found that an otherwise empty default project could still
hold edited settings or gallery stills. The follow-up binds the full fresh
settings snapshot and rejects stills; 40 focused bridge tests, Ruff, contracts
TypeScript typecheck and ESLint passed. The affected native admission and reopen
checks then passed on a separate synthetic guard-only target. The original
completed proof project was restored and independently observed with the same
final fingerprint and original current. The frozen attempt was not rewritten
to accept a changed bridge hash. This rechecks only the new admission guard;
the earlier cut/receipt mechanism and its evidence are unchanged. A final
color-group inventory refusal passed 40 focused tests and actual empty-project
readback, followed by restoration of the same completed target fingerprint.
The review request to authenticate arbitrary operator-supplied snapshots is
outside the explicitly trusted fresh-capture precondition above; that boundary
is documented rather than claimed as an implemented provenance attestation.

One bounded DeepSeek task over the frozen 26-case suite cost approximately
USD0.205 in three rounds. Although its final candidate passed that suite and
TypeScript, independent inspection rejected it: it changed a returned skipped
outcome to unattempted and admitted an unsafe uncertain-recovery path. The
delivered executor is the owner's replacement, with independent readback of
saved completions, current-target checks after reconciliation, immutable
results, and a final whole-prefix verification before baseline advancement.

Two test corrections preserve stronger behavioral assertions: the explicitly
skipped change remains skipped after failure of the last selected item, and a
waiting concurrent caller must cause **no adapter activity** rather than
requiring the active caller to use an arbitrary fixed number of observations.
The original frozen suite and model outputs remain separate from the delivered
tests. Neither the model score nor the offline fake-Resolve tests establish
actual native continuation or finishing/audio capabilities.
