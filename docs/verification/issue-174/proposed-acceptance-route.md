# Proposed #174 hybrid evidence exception — not approved

The accepted policy's cloud eligibility item 3 requires a candidate to change
no media-processing path. #174 changes an FFmpeg/FFprobe adapter, so it is
outside that activated scope. Its issue also explicitly requires full
`npm run validate`. The historical 581-test log has no original exit receipt,
and the current adapter differs. Neither that log nor #196's green runs
qualifies #174. The Producer prohibited a new blanket local full suite.

The coordinator proposes this **ticket-specific exception**, for Producer
review. It does not change global policy or supply acceptance by itself:

1. Global regression coverage: a complete full Ubuntu `Validate` run on the
   exact delivered integration tree, with real exit 0, all required tests,
   no unapproved skips and complete artifact-sourced inventory/provenance.
   Evaluate it from a clean accepted-main checkout with the existing approved
   validator and profile, scope `excluding-media-sensitive`. Require actual
   PASS with profile digest
   `1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`.
   Check controls, runtime/tool inputs, runner, tree, artifacts, attempt history
   and any prior failure dispositions. Draft CI may run as extra evidence;
   it is not currently an approved substitute for #174's full criterion.
2. Changed media boundary: retain the actual serial Mac evidence. All 84
   issue-owned tests passed on adapter hash
   `60c09d800a7137cbb5d896541dd318819616f414468db39c340af477e6904802`.
   Preserve the 24-case installed-tool qualification, 98-hash/decoded-media
   verifier, actual public qualified-ledger/exact reuse, clean pinned install,
   fast gate, frozen/generated audits and exact-source Claude technical PASS.
   Prove consumed inputs and tool identities still match the delivered tree;
   any relevant change invalidates reuse and needs fresh affected evidence.
3. Human judgment: execute the README's exact-artifact visible/audible
   checklist and retain the real operator result. Synthetic measurements or
   cloud evidence cannot certify this gate.

What remains: explicit Producer approval of this proposed #174 exception;
own exact-tree complete cloud run and accepted-main validator PASS; delivered
integration/input equivalence; and actual visible/audible judgment. Failed,
partial, skipped, stale or mismatched runs remain failures or gaps. No timeout,
assertion, inventory, frozen or privacy boundary is relaxed.

Until the Producer approves a route and its evidence actually passes, keep
#174 open, the PR draft and unmerged, and the full criterion unresolved.
No new blanket local full suite, source changes, cloud-acceptance claim or
policy amendment is authorized by this proposal.
