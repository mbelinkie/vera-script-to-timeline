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
requires no project currently loaded, so it cannot unload another project's
unsaved work. Each append must save and read back before its finished receipt.

A killed or timed-out command may leave the duplicate selected or the project
closed. It remains an unknown operation, with no baseline promotion or automatic
cleanup/replay; inspect the application and retained records before any further
native work. A signal handler calling more native APIs would not establish that
an earlier native call had drained. Source-end convention and the final actual
save/reopen remain native qualification checks, not widened fake-test tolerances.

This experiment introduces no transitions, audio processing, rendering, source
replacement or arbitrary human finishing. It does not prove that those
operations can be combined atomically. Production adapters must independently
qualify their capabilities and preserve or refuse affected unknown work.

## Results

The reusable domain executor, selection/plan operations, file journal and
native bridge are implemented. The 43 focused TypeScript tests and 21 offline
Python bridge tests pass. Native continuation is **pending**: the existing Resolve process
was present, but Local scripting could not connect and the supported launcher
timed out. No synthetic media or target was created by this proof. Existing
application state was preserved. This is not negative capability evidence for
the append route, nor a completed External result.

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
