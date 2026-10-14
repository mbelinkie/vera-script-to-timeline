# Pending #202 dependency delta

The #202 owner relayed provisional commit
`5ec08503d4c04f9d660592db7251fe8b94c1b7d8` on 2026-10-13, after integration
of accepted #190 mainbd6048b. Reported core raw SHA256:
`368d0f5ed125db82a87e7a3056b190664d07814ec348da8e29068ec400778631`.

Reported API signatures and #191 staged binding are unchanged. Comparison now
uses block/slot labels and separate source summaries; complete impact remains
hash-bound. Proposal hashes change, invalidating prior77/e66 proposal snapshots.
Fresh combined-tree tests must regenerate proposals/decisions through the public
core, never patch hashes or reuse old acceptance snapshots.

Reported ten focused tests passed; affected fast validation is live, initial
Claude GO is retained, and this delta is not yet reviewed/accepted. These are
owner-reported statuses, not #192 execution evidence. #202 retains the heavy slot.

This commit is **not imported** into #192 and is **not treated as accepted**.
The current imported core remains77b82, provisional. Wait for explicit accepted
handoff or coordinator-authorized draft import, preserve exact source/API deltas,
and invalidate affected receipts before checks. No polling, check job, Ready/claim,
merge or closure is authorized by this notification.
