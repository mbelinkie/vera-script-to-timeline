# #215 output observation and revision bridge

The 2026-10-19 issue scope supersedes the earlier recorded-audio qualification.
Continue in PR #269 on `claude/215-generated-narration-bridge`, using the
fresh Polly baseline and automatic timing from merged #182. Complete #215 and
stop; #145 retains the later Producer creative/listening acceptance.

## Product path

The host proof and TypeScript bridge consume authenticated native readback,
derive bounded proposals, record explicit decisions and compile a separate
canonical revision. Original document AND dependency guards, source/target/job
identity, currentness, one-use reservations and uncertain-run recovery remain
required. No AI rewrite or manually authored omission proposal substitutes for
observed geometry.

All audible test sources derive from campaign-generated Polly speech. A moves
a picture boundary without changing narration. B trims linked AV from 91 to 67
frames and shifts the downstream occurrence, using the replacement preparation's
honest requirement key; geometry alone cannot imply word deletion. C identifies
a uniquely supported omitted word from measured timing and frame-snapped native
geometry. Ambiguous, partial and straddling cuts refuse. D disables an item and
must refuse safely. Explicit proposal rejection preserves canonical text and
makes no provider request.

After accepted C inference, the product's NarrationService regenerates the
entire revised row, derives automatic timing and seals the replacement handoff.
The accepted canonical revision compiles the new audio's actual duration and
reflows dependent picture placements. It never cuts or stitches the old speech
for the rebuild. Unchanged narration reuses its asset. The existing Matthew
Neural voice, provider_terms_accepted policy and $1 cumulative campaign cap
apply; C's expected call is about $0.003. Uncertain attempts are never blindly
resent. Known failures before dispatch (credentials/client/input or a cap race)
leave the request retryable without recording an uncertain send. No live
provider calls run in CI.

## Native qualification

Use only installed product flows on issue-owned disposable Resolve targets.
Each positive chain requires pristine and edited observations/renders, explicit
acceptance, a fresh revised package and a new-target rebuild verified after
save/reopen. C compares against its NEW generated source and timing. A/B require
no synthesis. D and rejection require no synthesis or unsafe state change.
Preserve all old attempts and media, especially VERA215B04 and its retained job.
Do not use raw Resolve scripting or Fairlight/Deliver UI fallbacks.

Measured evidence at matrix admission is replayed from the existing local cache
using raw provider PCM, normalized WAV, provider timing and the frozen compiled
block with the generator's fixed default parameters. Supplied evidence and
measurement artifacts must match that replay; their mutual hash consistency
alone is not proof of machine measurement. Consumed
cache files remain bound by admission currentness checks.

Fixture track indices must be contiguous per media kind before native construct.
The shared fixture uses source-audio track 2 beside narration track 1; B adds its
second narration track at 2 and explicitly places source-audio at 3. Keep the
native contiguity refusal intact.

Fractional narration EOF uses the admitted WAV's hash-bound sample count and
sample-accurate native time getters when the integer getter omits its final
fractional frame. This covers intact narration and a surviving edited EOF
segment; ordinary frame edges, source audio and drift remain strict.

The fixed PCM prediction prescribes Studio 21.1.1's 72-sample linear audio edge
ramps, with its algorithm identity included in each pre-render commitment.
Resolve's reference manual documents 1.5 ms Soft Fades between adjacent clips;
the real B render additionally exhibits that exact envelope at programme edges.
The model is fixed before rendering and never estimated from a candidate
output. Settings snapshots do not expose the Soft Fades control, so the result
does not certify that setting. Actual renders must still satisfy the limits.
The pair's audio-distinction check excludes those prescribed edge ramps, so a
new fade alone cannot establish a meaningful audio edit. Each render's own
residual comparison still checks every sample.

Only `bounded_output_residual_consistency` is claimed. Internal controls,
continuous control stability and causal exclusivity remain unverified. Existing
per-channel limits stay programme RMS <=0.0004 and maximum sliding 960-sample
RMS <=0.006, zero lag, unity gain, no fitting.

## Verification and delivery

Run focused Python/TypeScript checks, local `validate:fast`, one read-only
Claude CLI review and GitHub Actions full Validate. Never run full validate on
the Mac. Retain the native results and #145 handoff, post one concise External
result, and merge only on green CI. Confirm the merge before completing #215.
No uploads, original-media mutation or #145 execution are part of this issue.
