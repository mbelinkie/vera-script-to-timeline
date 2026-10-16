# Checkpoint 10 verified interface and evidence boundary

`verify_omission_evidence(root, baseline_hash=..., target=..., row_id=...,
evidence_level=...)` is a read-only issue-owned building block. It does not
advance ProofSession, edit the script, synthesize, call Resolve or render.
Expected baseline hash, native target and authoring row must come from a trusted
proof caller. Arbitrary JSON IDs cannot establish those external facts.

Literal files are `profile.json`, `baseline.json`, `observation-a.json`,
`observation-b.json`, `calibration.json`, `render.json`, plus source and complete
program WAV paths referenced by profile/receipts. They use the existing strict
JSON loader (duplicate keys/non-finite/out-of-range integers refuse). Local
relative paths only, regular independent files, no symlink parents/hardlinks,
bounded payloads and complete PCM16/24 mono sources/stereo programs at 48k.
The domain is 25fps, 1920 samples/frame, bounded 3 million samples per channel,
at most 8 independent sources, at most 64 token supports/source and 65 segments.

A profile declares one unique source/row binding per source and complete ordered
sample supports. Both raw-file and full decoded-sample aliases refuse. The
current trusted positive injection uses generator declarations; this does not
qualify real support intervals. A source may have no speech supports (the
retained pilot/bed), but its full route must still stay unchanged. This is a
bounded evidence profile, not a product music feature or general authoring rule.

Observation envelopes bind target/extent and a complete route/source inventory.
Each route has fixed neutral gain/pan, enabled/unmuted/unsoloed state, no effects
or sends and destination stereo-program; the program has neutral gain, no FX
and no limiter. Every occurrence is enabled/online at 100%, with exact integer
source/record ranges of equal length, no reversed/overlapping/repeated source
interval or duplicate UID. These synthetic graph declarations are a trusted
test assumption, not independently authenticated live getters. Retained mode
can label route/program controls unobserved and cannot become supported.

All baseline supports must be whole and unique. Every retained support must be
whole exactly once and in order. Exactly one contiguous interior interval in
the selected source may have no intersection with any observed source segment;
first/last/partial/duplicate/noncontiguous edits and whole-route loss refuse.
Other routes are compared in full. A unique source-support decomposition does
not prove native occurrence ancestry. UID signatures never establish it.

Receipt settings bind full extent, stereo PCM sample width/rate, baseline/profile
and observation hashes, exact queued/polled/completed job ID and output hash.
Calibration and edited jobs must differ. Complete decoded samples must match
receipt extent/settings. This is internal consistency, not genuine render proof.

Route/channel gains are fit only against the unchanged full reference, bounded
to [0.25,1.5], and reused without fitting the edited output. Every channel gets
a whole-program RMS and every sliding 20ms/960-sample residual check (.0004/.006).
Known shifted words or other routes may occupy the old omitted-word output
window; no silence is required there. Quiet/short unknown overlays can pass the
numbers. The tests deliberately retain that limitation; numeric agreement is
never a standalone speech-absence classifier.

The deterministic report binds actual input file hashes, source segments, all
selected support retention facts, target/token IDs, channel/calibration metrics,
fixed gains, implementation hash and explicit limitations. `reportHash` hashes
the issue-owned report without itself using the host receipt serializer; it is
not a canonical ScriptDocument hash. All read files are checked again before a
positive/consistent return. A source-bound refusal is deterministic on fixed
inputs, but its diagnostic never authorizes a revision.

Only `synthetic_injected` can return `supported` in this segment.
`retained_consistency` always returns `consistent_unqualified`, even when every
structural/numeric test passes. `real_issue145` refuses until independent source
support/route/current-build/observer/render qualification exists. An operator
file saying verified=true cannot open that lane. A wholly self-consistent forged
file bundle remains outside a file protocol's detection power.

The retained W1 test verifies original publication and decoded hashes, every
support from the source manifest, full base.mov embedded PCM equivalence, equal
native pre/post observations and exact observed source/record intervals. It uses
synthetic replay targets/row IDs/baseline/reference/render receipt envelopes;
those are reconstruction inputs, not genuine native receipts or a live proof
baseline. Original historical measurement scripts/results are unchanged. The
retained verdict is support/render consistency only. No native/cloud actions.

Checkpoint10 is not #144 completion. The canonical omission/decision/composition,
whole-row handoff wiring, fresh build IDs/materialization, real WI guarded entry,
integrated three-edit proof and operator runbook remain. #145 qualifies live
standalone routing/captures/supports/rendering and executes the actual run.
