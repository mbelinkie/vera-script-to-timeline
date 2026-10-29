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
replacement. An abandoned lock or replacement file requires inspection; it is
never cleared automatically.

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
at command boundaries. Per-append start/result records prevent replay after an
unknown native call. Native receipts bind exact project/timeline identity,
media hashes, source bounds and timeline geometry. Reopening must retain both
the duplicate and the original.

This experiment introduces no transitions, audio processing, rendering, source
replacement or arbitrary human finishing. It does not prove that those
operations can be combined atomically. Production adapters must independently
qualify their capabilities and preserve or refuse affected unknown work.

## Results

Implementation and verification are in progress. No native success is claimed
by the domain tests or by the existence of this harness.
