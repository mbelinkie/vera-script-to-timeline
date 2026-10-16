# Checkpoint 10 proposed plan: bounded non-transcript omission evidence

Checkpoint 9's whole-row generation handoff has completed Claude plan, segment
and correction reviews. Its isolated full validation is running on fixed source.
This next plan is for review only; audio-gate implementation has not started.

## Scope

Implement one issue-owned read-only audio-evidence verifier, before wiring
omission decisions into ProofSession. Inputs are an immutable source-support /
mix qualification profile, baseline and two equal edited audio observations,
verified complete program PCM and the render receipt binding its exact target,
observations, settings, extent, job and byte hashes. Use strict existing host
JSON/file parsing. No transcript operation, native action, provider call, new
package dependency or frozen-contract/fixture/accepted-test change.

This is a closed supported profile, not a general speech detector or arbitrary
Fairlight graph. Require 25 fps, 48k integer sample/frame relations, 100% speed,
complete known occurrence/source inventories, exact source bytes/channels,
known fixed per-route gains and complete render extent. Unknown controls,
effects, routes, incomplete getters, offline sources, new sources, extra
occurrences, disabled routes, nonlinear processing or drift refuse. Do not turn
missing native facts into defaults. Require explicit source-support provenance:
fixture-generator declarations are labeled synthetic; a real source needs
independently verified supports, not provider-derived word-end assumptions.

Check every route containing the target source's speech. The omitted contiguous
interior token support must have zero intersection with all retained source
intervals; every retained token's complete support must remain exactly once and
in order. Partial head/tail, duplicate support and removal of a whole narration
route refuse. Source-bound uniqueness is not a claim of clip ancestry: copied
UIDs/signatures cannot resolve an ambiguous row/source binding. Bind the target
row/source through the verified baseline map and require a unique supported
decomposition. Unknown lineage affecting that mapping stays unsupported.

Reconstruct the complete stereo program independently from the verified source
samples and observed record/source intervals. Calibrate bounded gains ONLY from
an unchanged reference, never fit the edited program. Compare each channel
individually using complete-program RMS and every sliding 20ms window. Preserve
known neighboring/other-route material even when it lands in the old omitted
word's output window; the gate does not require silence in that window.

The retained W1 measurements (`retained-w1-boundary-measurements.json`) suggest
RMS .0004 / 20ms .006 for that specific source/build mix. They are consistency
limits, never an absence classifier. Quiet/tiny overlays can pass them. A
positive requires independently qualified closed routing plus discrete full
support excision; tolerances alone never qualify deletion. Report the numerical
limitation alongside the result. Do not claim every arbitrary unobserved quiet
residue can be detected by PCM comparison.

## Evidence and live-readiness distinction

Use #141 publication records with both published and decoded hashes for W1
source/support manifest, equal settled native snapshots, render job/settings and
complete outputs. Project only observed getter values; do not convert missing
status to a default. Preserve observed exclusive intervals (A1 [0,99),
[150,399) at records [0,99), [100,349)), actual 399-frame render extent, and
source-support samples for Charlie [216000,234932). Do not rewrite configured
400-frame ranges into observed results. Treat embedded `base.mov` A1 and the
standalone `a1_alpha.wav` as equivalent only after hash-bound full decoding
comparison, not filename similarity.

The historical collector did NOT attest arbitrary Solo/bus/sends/FX state.
W1's structural support excision and bounded rendered consistency are retained
observations; do not relabel them as complete live routing qualification. The
automated positive gate is exercised with honestly synthetic injected, complete
known-route inputs derived from the retained case. #145 must independently
qualify the actual standalone narration topology, every relevant route/control,
support source, initial inspector/capture adapter and complete render on its
selected build. Unobservable routing/support is a named readiness blocker;
#144 never fills it with an operator file saying "verified": true. There is no
live positive, native automation claim or lower-coverage substitute here.

Render receipt job/settings/extent/hash consistency is not cryptographic proof
that a genuine render occurred. #145's real render-job polling, output readback
and receipt constructor require the same independent review/current-build
qualification as the initial inspector/capture adapter. Validate a strict
receipt shape and all internal bindings; a self-consistent fabricated receipt
cannot be detected from those fields alone. The existing W1/W3 mapping-mute
readback/output disagreement is a concrete reason to require these output and
qualification checks, rather than trusting control labels.

The A3 fixture bed exercises complete-mix attribution; this does not add product
music authoring, cross-row music validation or music reconciliation to #144.

## Minimal implementation and tests

New `roundtrip_audio.py` and issue-owned tests/data/provenance. Reuse the current
hash/WAV/decoder/reconstruction math where practical. If extracting helpers from
the issue-owned measurement script, preserve its historical source at the
original commit and state the new code hashes; never change historical result
artifacts or imply old measurements used the new helper. Add verifier/source
inventory bytes to the proof snapshot only after checkpoint9 validation finishes.

Test first: synthetic complete-route omission; retained W1 support/reconstruction
consistency separately labeled; picture-only retains the word; disabled A1 is
not a phrase edit; partial head/tail and residual source on another track refuse;
unknown route/control/identity/hash/source, invalid speed/extent, ambiguous
source/row mapping, stale adjacent snapshots and render/source tampering refuse.
Also reject a claimed render job/settings/extent whose complete decoded bytes
do not match the receipt's bindings; do not mislabel this internal-consistency
check as proof against every fabricated native receipt.
Include opposite-channel residue, unchanged-neighbor attribution, gains outside
qualification and quiet/tiny residual probes that explicitly demonstrate the
numeric limitation instead of falsely passing a generic absence classifier.

Return a deterministic hash-bound evidence report with supported/refused status,
target row/token IDs, exact support/decomposition facts, source/profile/observation
and render hashes, and numerical diagnostics/limitations. No canonical script
is modified here. Claude reviews the plan before code and the completed verifier
before integrating semantic omission/canonical composition and the generation
handoff. Existing move/trim input binding remains unchanged in this segment.

## Acceptance

Automated checks for this verifier and the existing narration/build boundaries;
retain failures/corrections and exact runtime/counts. No producer deterministic
retest. Complete explicit omission decision/revision, composed fresh build IDs,
guarded WI entry, integrated three-edit proof and operator runbook remain #144
work. Real native/input/provider qualification remains #148/#145. Missing live
facts remain named readiness blockers, not silently invented evidence.
