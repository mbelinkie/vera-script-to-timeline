# #512 Phase 3 — read-only incident reporting and inventory

## Scope and command

The new pure-Python CLI `vera_timeline_agent.resolve_test_bench_incident_report`
imports only the v1 diagnostics contract/writer constants and Python standard
library. It **never imports Resolve, a carrier, the native verifier or a host**,
never starts or replays an operation, never opens media, and never writes an
original record or signs a receipt. Run from the #512 worktree:

```sh
# Historical seventh case: a retained prior Mac audit, NOT a new Mac verification.
uv run python -m vera_timeline_agent.resolve_test_bench_incident_report \
  --seventh-map "$PWD/docs/verification/issue-512-seventh-case-map.json" \
  --format markdown

# A NEW case (owner-only absolute case/stage directory, exact identity).
# Repeat --case-root for distinct stages of the SAME case, at most 8 roots.
uv run python -m vera_timeline_agent.resolve_test_bench_incident_report \
  --case-id <case-id> --case-root /absolute/private/new-stage-root \
  --format json
```

JSON and Markdown expose case and source/actor pin identities, stage counts,
last writer-reported verified/ingested action, next pending/first missing
boundary, per-stage event order/UTC/monotonic deltas, bounded evidence inventory
and explicit unknowns. The source-map mode is narrowly constrained to the
frozen **seventh** case; the JSON report includes the SHA-256 of the map **read
in this invocation**. The Mac native files referenced by that prior audit are
not mounted in the #512 Linux worktree and their hashes are not fabricated.

## Seventh-case baseline

The **prior Mac postmortem** authenticated and ingested native actions 0–4
(`construct`, `save_reopen`, `capture_pre`, `queue_render`, `start_render`).
The original operation 5 `poll_render` request was absent; so were all four
signed M4 stage receipts. The historical result is **M4 0/4**, strict #312
not run, `unknown-after-claim`, original one-use case **spent**. This reporter
never says the missing poll caused the crash: the swallowed root exception
remains unknown. Phase 4 must re-read the original Mac case with no effects
and compare independently before #499 considers a newly authorized attempt 8.

## Trust and privacy boundaries

- Only explicitly supplied, absolute, owner-private case roots are read.
  Directory descriptors use `O_DIRECTORY|O_NOFOLLOW`, files use
  `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, with optional `O_NOATIME`. No symlinks,
  nonregular records, foreign owners, group/world-readable private files,
  extra filenames, gaps, broken SHA-256 chains, identity/pin switches, or
  noncanonical/oversized v1 records are accepted.
- Record quota: 8192 records/chain, 8192 bytes/record, at most 8 stage roots.
  The reader never repairs malformed records, reorders events, or includes
  absolute source/media paths or raw exception locals in its output.
- `evidence` references expose **only** `role`, SHA-256, `sizeBytes`, optional
  SHA-256 of a locator. Phase 3 expands `DiagnosticJournal.emit` to accept
  these already-vetted references; neither reader nor writer opens/duplicates
  the referenced MOV/PCM. Private diagnostic record bytes are hashed by this
  invocation and marked `verifiedByReader=true`; external artifact hashes
  are **reported claims**, `verifiedByReader=false` until an independent
  external verifier authenticates the original artifact.
- A diagnostic with `proofLayer=signed_m4_receipt` is still **not a verified M4
  receipt**. The native signed-original verifier is deliberately not called.
  Thus the generic report says `UNPROVEN: 0/4 independently verified by this
  reader`, not success. The historical seventh-case map explicitly records
  0/4 **in the prior audit**, also marked not freshly authenticated here.
- Wall-clock UTC is for presentation, not elapsed calculation or causal
  ordering. Elapsed time is computed only for nondecreasing monotonic values
  within the same PID and consecutive records; a PID switch or monotonic
  rollback makes elapsed unknown. Boot identity is not independently attested.
- Missing records, original MOV/PCM content, signed receipts, failure root
  causes, actual source/actor currentness, and #510 originating-thread ACKs
  are **never inferred**. No reader output creates authorization to retry.

## Test evidence and handoff

The focused tests cover exception/crash UNKNOWN after five ingested host actions,
safe MOV/PCM hash pointers, signed-diagnostic-versus-M4 separation,
malformed/torn/oversized/cross-case/symlink/permission/record-gap records,
stale/broken chains, wrong roots, clock rollback/process change, source-map
tampering, quotas, no effect or source/journal rewrite, and both output formats.
Full local validation status is logged separately in
`.pipeline/512/validate-fast-phase3.log` (ticket folder, not in the PR).

**Integration:** #499 owner/Conductor adopts the #512 contract, journal,
reporter, and source-pinned phase 2 hooks into its original adopted PR #474
after source/currentness review. No #512 agent edits #499 worktree or produces
another native case. Phase 4 independently validates on Mac and hands off.
