# Resolve knowledge guide

Reconciled 2026-10-27 for [#338](https://github.com/mbelinkie/vera-script-to-timeline/issues/338).
Source baseline: `068bee17402c90e4678351b2a390be6c9d4c7b47`.
This is a collection of bounded findings, not a new runtime certification.
The [source ledger](RESOLVE_KNOWLEDGE_SOURCES.md) records collection coverage.

## How to use and maintain this guide

Before planning a new native experiment, find the capability below and state
the unanswered delta. Reuse the unchanged finding; check only assumptions the
proposed change affects. The issue owner who learns something updates or
supersedes its finding in the same PR/handoff. Keep IDs stable and link the
original evidence. A short result is enough.

Each entry combines **conclusion/status**, **evidence and envelope**, and
**reuse/delta**. Evidence classes are **API** (declaration), **synthetic**
(unit/mock/replay), **native** (actual installed-app output), and **product**
(actual normal VERA path). These classes are not interchangeable. Unknown
metadata stays unknown. Unless an entry says otherwise, its reconciliation
date is the guide date; native claims apply only to the stated edition/build,
route and fixture. A historical successful run does not authorize a current
target or waive byte-integrity, identity, freshness or one-use checks.

## Source clocks and precision

### RK-10 — Sample correlation is useful but can legitimately refuse

**Conditional / synthetic and retained-input measurement.** [#297 / PR #299](https://github.com/mbelinkie/vera-script-to-timeline/pull/299)
added sample-domain alignment for same-rate mono normalization; differing-rate
sources retain the envelope route. A strong or zero-lag estimate alone does not
admit word boundaries: mismatch, ambiguity, local drift, inserted/deleted samples,
silence, negative/collapsed starts and missing audible support still refuse.
Resolve edition/version is inapplicable to this host measurement. The retained
48 kHz Inworld rows still refused this route; this was not a positive native
delivery result. RK-11 adds a separate qualified-clock route rather than
relaxing correlation thresholds.

**Reuse/delta:** carry forward measurement semantics for the same transform,
algorithm and byte-bound timing. A changed rate/filter/profile/tool needs its
affected alignment test and provenance check; do not synthesize again merely
because a retained asset failed measurement.

### RK-11 — Exact PCM replay and a qualified clock establish different facts

**Proved within limits / product plus transform-source evidence.**
[#300 report](investigations/issue-300-normalization.md), delivered by
[PR #301](https://github.com/mbelinkie/vera-script-to-timeline/pull/301) at
`129608010d11c9b05f129a0ec28209113504299a`, qualifies the default v2 graph on
FFmpeg **8.1.2**, mono **48 kHz**, no padding, with actual second-pass
`normalization_type=linear`. Reviewed filter semantics plus contiguous,
same-coordinate sample traces establish the clock. Exact replay separately
establishes that the bound raw/timing/profile/tool inputs reproduce the complete
cached PCM. Requested `linear=true` alone is insufficient because loudnorm can
fall back to dynamic mode. Version-3 measurement admits this route; older
measurement documents are historical, not current package admission.

**Reuse/delta:** use the same qualified graph/fingerprint and whole-PCM checks.
New FFmpeg semantics require source review and a clock trace, not a full Resolve
campaign. Other versions/modes/profiles keep the independent-correlation route;
44.1→48 kHz is not qualified by this same-rate result.

### RK-12 — Word onset, audible end and authored picture boundary are distinct

**Proved bounded resolution / product, with one explicit product decision.**
The [#300 placement audit](investigations/issue-300-normalization.md#retained-input-result)
found four word anchors plus a row-start placement, not the previously reported
five stale anchors. Qualified measurement resolved one missing end; another
still lacked acoustic support. The Producer approved moving that picture
boundary to the following onset in a new snapshot. No structural provider end,
frame edge or agreeing aligners became an audible end. Both narration rows
remained whole. The guarded Studio **21.1.1** build (build number unreported in
this report), at **24000/1001**, verified eleven events/media after save/reopen.

**Reuse/delta:** reuse admitted unchanged timing and the explicit revised
anchor. For a newly requested after-word edge, check that edge's acoustic
support or obtain an authored anchor choice; do not repair timings by nudging.
The earlier [#289 timing study](investigations/issue-289-timing-study.md) is
historical; its unfinished recovery protocol is superseded by the later scope,
not accepted acoustic evidence.

### RK-13 — Fractional source readback needs its actual clock

**Conditional / product.** The same [#300 report](investigations/issue-300-normalization.md)
qualifies the retained 24000/1001 narration/video mapping and authenticated
one-frame images. Precise source times, identity, rational rate and bound
sample/frame extent are checked together; observed integer getter rounding is
not permission for an arbitrary tolerance. Stills use their actual source rate;
scaling precedes anchor properties because scaling can reset them. Neutral
anchor offsets are zero. Fractional video-backed held frames with multiple
decoded source frames remain refused before adapter creation. Integer-rate
delivery retains exact getter checks.

**Reuse/delta:** preserve the exact derivation/frame map and precision rule.
A new conversion or held-frame class needs a source-clock/decoded-frame delta,
not rediscovery of OTIO import. See RK-30 for unmerged #312 corrections to a
different output verifier; that draft cannot broaden this accepted envelope.

## Waiting, recovery and current operations

### RK-20 — Resume waiting; never replay an uncertain mutation

**Proved bounded / product and independent native readback.**
[#302 / PR #306](https://github.com/mbelinkie/vera-script-to-timeline/pull/306)
completed the normal guarded build on Studio **21.1.1**, Intel Mac, with explicit
external scripting **Local**. Reservation-to-exit was **250.95 seconds**;
the same operation remained observable beyond 60 seconds, then verified eleven
events/media, zero discrepancies and save/close/reopen. Repeated parent start
returned the same terminal result without a second target. This was one short
package observation, not a benchmark. [Measured report](verification/issue-302-guarded-parent.md).

Follow [the parent runbook](resolve-parent-delivery-v2.md) for state meanings.
`live` can be waited on; `unknown` or infrastructure failure needs inspection.
`terminal` alone can contain a failed build; success requires matching final
evidence with `verified: true`. A legacy start-only request is consumed and has
no liveness proof. The parent resumes waiting, not partial Resolve mutations.
The earlier Media-page/empty-target preflight refusal and two legacy timed-out
attempts remain negative/incomplete evidence, not superseded successful runs.

**Reuse/delta:** reuse this parent for an unchanged guarded build exceeding a
caller window. A new execution route needs dispatch/liveness/identity tests;
render completion and process-restart recovery are separate questions. Fresh
attestation, one-use request, current target and host reservation checks still
run for each operation.

## Current #312 / #313 handoff

Collection of earlier delivery, output and observation findings is in progress
in this PR. The full issue will include those findings and the final source
dispositions before it is ready for merge.
