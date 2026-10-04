# Claude checkpoint 8: finished visual file workflow

Read-only review. Do not edit files, run commands, post comments or invoke
native tools. Review BOTH the completed segment and the bounded next plan.
The row-box policy settled in checkpoint 7 remains authoritative.

Completed segment: `packages/contracts/src/issue-144-proof-cli.ts`,
`python/vera_timeline_agent/roundtrip_proof.py`, corresponding
`issue-144-proof-cli.test.ts`, `issue-144-test-inputs.ts` and
`tests/test_issue144_proof_session.py`. Existing `roundtrip_build.py` now binds
these new source files into its implementation snapshot. Accepted compiler,
contracts, fixtures, Studio/job sources and accepted tests are unchanged.

The semantic CLI emits canonical result/artifact strings and byte/source/lock
hashes; no file writes. The host calls the actual compiler/package/jobs/assembly,
captures through an explicit injected or file-staged boundary, requires nonce
and request-hash binding and equal adjacent observations, retains verified
occurrence UIDs, freezes decisions/revisions, builds a fresh target and verifies
before atomic baseline promotion. It defaults to no native provider.

Own safety tests found three defects before this review: first baseline could
accept replacement occurrence identity; symlink parents allowed capture intent
to escape its directory; status CLI lacked a status field. Corrections require
exact complete eventId/itemUid/mediaUid inventory from native identity, guard
all proof writes and give explicit bound/unbound/action-required results.
Saved decision replay now rederives the actual semantic result from frozen
inputs and rechecks its baseline, sources and canonical artifacts. Rebuild
also obtains a fresh observation matching the accepted decision. Tests cover
changed saved receipts, stale nonce, cached response, absent boundaries,
lost create response and interruption just after pointer publication.

Please inspect especially:

1. Any seam still accepting fabricated authoring echoes, unproven first
   occurrence identity, stale observation or mismatched evidence lane.
2. Immutable publication, symlink/path containment, process-fault handling,
   capture consumption and same-decision replay/recovery. Local rereads detect
   observed drift; no atomic capture or ABA guarantee is claimed.
3. Canonical bytes, actual compiler authority, baseline/native/package hashes,
   stale decisions and promotion. Does crash recovery preserve one baseline
   advance and avoid duplicate native create? Are receipts trusted too much?
4. Keep synthetic injected tests distinct from #145 real acceptance. This is
   a visual-only segment; no spoken omission, real WI observation/link/render,
   provider generation or production human-work preservation is implied.
5. Next audio plan: prove the original audible omission through complete
   structural routing plus a full verified program render; require explicit
   text decision; obtain one freshly generated whole-row temp recording and
   fresh marks via a bounded generation handoff; recompile local anchors and
   translate following boxes intact. No old-audio splice, paid/cloud call or
   manual rewrite substitute. Tests must exercise changed text and preserve
   an untouched following row's audio/source ranges/relative cuts. Review the
   smallest viable handoff using the accepted narration boundary, without
   introducing a parallel synthesis framework.

Report concrete findings with file references, severity, minimal fixes and any
remaining qualification/readiness constraints. Static review is advisory and
does not count as independent tests, native evidence or acceptance.
