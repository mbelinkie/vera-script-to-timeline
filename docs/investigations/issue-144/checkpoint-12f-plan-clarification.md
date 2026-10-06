# Checkpoint 12f: resolve the generation-input record question

Please review this narrow clarification before generation wiring. Do not edit or
execute services; same model/account/session and quota stop condition. Your full
checkpoint12f plan review found one question: justify or drop the proposed
generation intent. Here is the precise gap it closes and the smaller formulation.

The cache/proof locks are sufficient for concurrency. No extra reservation,
lock, state machine or store is proposed. Rename the one immutable file to
`generation-inputs.json` in the existing decision directory, written with the
existing `publish_immutable_output` while holding the existing proof lock.

It binds the actual revised row and service's actual request identity, adapter,
normalizer profile/tool fingerprint and proof-local cache to this accepted
decision before the first `replace_row_narration` call. The specific failure is:
provider synthesis succeeds and the accepted service publishes its cache;
execution stops before the complete handoff file is retained; on resume the
injected voice/profile/provider-input/normalizer selection changes. The service
then computes a *different* request or normalization key. Its lock correctly
deduplicates identical keys, but does not bind those different keys to the same
already accepted decision, so it could make another provider request or produce
different handoff bytes. The absent handoff cannot reject that drift yet.

The immutable input record detects that mismatch before service execution even
in this gap. For an unchanged input record, retry delegates to the real service's
cache/lock, as reviewed; it does not substitute for it. Once the full handoff
exists, replay also requires the actual retained synthesis/asset entries and
source/timing/audio bytes to remain verified before actual cache-backed handoff
reverification and every pure finalization call. Historical replay cannot create
a missing input record/handoff/generation against a stale pointer.

This preserves the plan's explicit requirement that a changed retained service
selection refuses before another provider request, including interruption before
the handoff is saved. File/hash consistency is not qualification or acceptance:
the actual decision/evidence/report/text and actual service/cache are still
rederived. No new concurrency mechanism. Confirm whether this resolves your sole
plan finding, or identify a smaller existing record that covers this exact gap.
