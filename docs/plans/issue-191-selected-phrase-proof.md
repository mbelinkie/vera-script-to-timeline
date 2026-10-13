# #191 — selected phrase proof and whole-row replacement

Owner: gpt-6.1-sol/high, chat `01a12bbf-7390-7be0-bab1-e34a7387f292`,
branch `codex/issue-191-selected-phrase-proof`, baseline
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`. Reinspection found Ready,
Automated, exact routing, no claim and all #189/#180/#173/#144 dependencies
Closed/Done. Claim preceded every mutation. Shared Git branch setup required
filesystem permission after the claim; no implementation preceded setup.

Authority is the Producer-accepted #189 plan at
`094b1ca4d21dbaf063993ac33c7bb818d26941d5`, SHA256
`7fc7f361062fb35f7bf8bc1afdbc4b5cf6e72b21af27bcb873af0919560228d2`,
especially §§4–6 and CN-189-A/B. Acceptance is recorded in source chat
`01a12b05-bb8c-76d1-acd5-634ca5fda4b6`; plan-era “proposed” wording is
historical. #180 accepted handoff is `4c92884665629b283ce679f9ffc51859a32239e6`;
#173 tested compiler handoff is `96fd70f573c3eaa1fc2b342de87ee9df00c64eaa`;
#144 is `d167f3533c237bf01995dd794458b3945599e842`. Pin each separately.

## Scope and boundaries

New proof-only siblings: selected-window audio verifier, pure v2 omission
transform and immutable narration request/replay/fresh sparse-evidence handoff.
Only new issue-owned synthetic tests and sanitized documentation are added.
Shared contracts/generated types, fixtures, goldens and accepted tests: none.
No dependencies added: existing PCM/metrics, cache/service, v2 validator and
compiler are reused. #189 supplies evidence meaning; #180 sparse boundaries;
#173 compiler/audio interfaces; #144 immutable request/preservation patterns.

The trusted receipt-authentication port must verify actual independent review,
complete native observations and owned render intent/effect/completion. It is
required and has no default or operator boolean. Tests inject a fake authority.
The audio result always labels itself local consistency, never real/native
qualification. #190/#178/#145 supply that authority and external evidence.
Version/shape, identity, PCM, unknown controls, geometry and complete-channel
residual checks precede any verified result. Supported controls are direct mono
duplication/stereo playback, fixed observed gain, zero pan and no effects,
automation, sends or unknown controls. Routes cannot alias source PCM.

The pure transform requires a current hash-bound edit and explicit decision
hash; its caller authenticates and accepts the evidence. Removed anchor owners
refuse, never move to a guessed word. Surviving text ranges refresh only their
exact affinity-aware quotes. All unrelated blocks and provenance survive.
Whole-row generation uses existing NarrationService/cache with immutable
configuration, authorization, intent and receipt. An uncertain missing synthesis
cache refuses replay. Fresh sparse evidence is authenticated against new audio;
provider-derived ends are never substituted. Compilation follows verified
handoff and is repeated byte-for-byte with input preservation checks.
This bounded profile also requires a different provider timing hash. Identical
empty timing payloads conservatively refuse; fresh sparse review alone cannot
override that freshness check.

Exclusions: real marking/acoustic review, private originals/data, original R16
mutation, native Resolve/render action, provider/cloud call, upload, migration,
production UI/inbound and general timing engine. Do not start #190/#192.

## Checks and acceptance

Issue-owned PCM tests independently construct expected full stereo renders and
exercise picture-only, clipped-neighbor, extra-cut, unknown-control/route,
partial, stale, aliased, receipt and unrelated-audio refusals. Pure transform
tests cover every v2 anchor owner, UTF-16, punctuation, stale state, preservation
and deterministic output. Fake service tests cover immutable inputs, cache
replay, uncertain no-double-synthesis, fresh bytes/text/revision/timing and
preservation of old assets/other rows. Fresh exact boundaries must compile;
stale or missing boundaries must refuse.

Run focused tests; `npm run validate:fast` during implementation; audit frozen
baseline/source/generated/privacy/diff boundaries; then, with no other heavy
test run, `VITEST_MAX_WORKERS=1 npm run validate` on committed delivered source.
Retain exact revision, commands/results/hashes and walkthrough. Automated
acceptance requires all gates, roadmap review/complete and independent
Closed/Done reinspection. No producer repetition of deterministic checks.
The producer additionally requires a Claude CLI antagonist review before
closure. Supply the exact checked commit, issue requirements, relevant diff and
source context and retained passing evidence. Retain findings and disposition;
fix substantive findings, rerun affected checks and obtain Claude re-review.
An unavailable or failed CLI leaves that review gate unmet.

Later #145 checklist remains: independent original supports and source/mix
listening, an actually frame-safe native lift, provider identity/consent/privacy/
cost authorization and actual whole-row call, authenticated pristine/edited/
rebuilt complete renders, native route/control inventory, new media handles
and actual rebuild/save/reopen qualification through #190/#178.

## Forecast

After the first 20 synthetic audio checks passed: 2–4 hours active work remain,
medium confidence. Main uncertainty is fresh narration replay/sparse-boundary
handoff and integration review. Reassess at fake-service/compiler integration.
Full validation historically takes about 50 minutes; that wait is separate.
No external approval or native/provider wait belongs to this implementation.

After fake-service/compiler integration and independent review: 40 focused
Python checks passed and one decoder-message expectation needed correction.
Fresh-timing and malformed-WAV review findings are fixed and independently
rechecked. Remaining active work is about 30–60 minutes, medium confidence,
plus the serial full-gate wait. Narration tests are marked slow because they
repeatedly invoke the external Node compiler; they remain in full acceptance.

Capacity correction: accepted #189 uses source frame 2756 (more than 5.5 million
48-kHz samples), despite its 2,216,214-sample programme. Reusing the v1 decoder's
3-million source cap cannot support that geometry. The v2 sibling therefore
keeps the programme cap but reads complete sources up to 16 million samples/
128 MiB, with a 32-million channel-sample aggregate budget and at most 16
sources. This is a bounded source decoder, not a timing engine. The added
late-source regression is slow-marked for large PCM decoding; full acceptance
still includes it. The interrupted first full gate supplies no acceptance.
