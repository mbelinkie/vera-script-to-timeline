# #292 — installed picture-transition capability proof

Status: investigation in progress, 2026-10-24. This document does not clear
the transition capability hold on #125 or #61.

## Boundaries

This issue tests installed inventory/control discovery and precise declared
picture-transition execution together. It adds no production chooser or engine.
Only issue-owned disposable synthetic fixtures may be mutated. Existing
Producer projects, media and plugins are preserved.

The live issue's current product intent supersedes the old §8.5 default-policy
assumptions: new visual boundaries start as cuts, effects are explicitly added,
and installed effects must not be silently replaced or reduced to a fixed trio.

## Initial observations

- Baseline: `origin/main` at `cc9566672f4d9b97b484cf651b479a5e7044f94e`.
- Connector reports Resolve 21.1.1 installed and not running before probes.
- Connector metadata advertises `TimelineItem.AddTransition` with
  simple/fusion/ofx/audio categories. This is a lead, not runtime evidence.
- Installed official Scripting README (last updated 31 Aug 2026) has no
  `Transition` match. Runtime and alternative routes still need checking.
- Installed official Fusion Templates README documents transition macros,
  exposed controls, template paths and a restart to refresh templates.
- Current portable import-package verifier rejects OTIO transition items;
  existing cut-only acceptance is not transition acceptance.

## Remaining evidence

Exclusive runtime access; actual edition/build/platform; Effects Library versus
automation inventory; native and installed Fusion/custom representatives;
metadata completeness; declared boundary/type/duration/alignment/option;
duration/option update; save/reopen; output; short handles and neighboring trim;
independent inbound observability; safe unavailable/ambiguous states; concise
supported/unsupported/ambiguous matrix and #88/#61/#125 handoff.
