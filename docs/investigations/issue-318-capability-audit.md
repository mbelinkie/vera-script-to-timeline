# S03/S05 capability audit — #318

Audit date: 2026-10-25. Source baseline: `6f5d73f4e96af6b7709c853c2af15c78bc5183aa`
(`origin/main`, freshly fetched at launch). This report audits current retained
authoring and outbound-review promises; it does not resume design or certify
the finished application. [Issue #318](https://github.com/mbelinkie/vera-script-to-timeline/issues/318)
owns this finite audit. #33 and #147 are historical inputs, not current
capability certificates.

## Evidence rules

- **W — working:** executable implementation supports the stated bounded claim.
- **M — mechanism proved, integration unfinished:** domain tests or external
  runtime evidence prove the specified mechanism; the consuming app seam is open.
- **U — unproved:** evidence does not establish the promised operation. An
  unimplemented ordinary app feature is not evidence of impossibility.
- **X — unsupported in the tested route:** a measured refusal or omission;
  other routes remain possible.
- **D — Producer-deferred:** a recorded product decision, not an engineering
  assumption or a failed test disguised as acceptance.

Each row must name its scope, evidence, limit and existing or missing owner.
HTML is a source of promises, not runtime proof. A schema is not an operation;
an inbound observation is not outbound placement; a successful disposable
probe is not production compiler/package integration.

## Initial established boundaries

The [#292 runtime report](issue-292-transitions.md) qualifies named native and
Fusion transition subsets on Studio 21.1.1 build 10, macOS Intel. It proves
specific duration/alignment/control/save-reopen/output behavior, including
picture-only preservation of the fixture's narration. It does not qualify all
installed transitions or all controls. The production portable verifier still
rejects OTIO transitions. #88 owns production library integration. Universal
installed discovery is explicitly deferred beyond V1; a verified expandable
library is the adopted scope.

The [2026-10-25 Producer decision](https://github.com/mbelinkie/vera-script-to-timeline/issues/164#issuecomment-6399451899)
requires automatic zoom on every image, customizable in settings, with native
Resolve capabilities first and immutable prior builds preserved. [PR #317](https://github.com/mbelinkie/vera-script-to-timeline/pull/317)
is pending at this snapshot. API declarations for Dynamic Zoom are leads, not
proof of framing, retiming, persistence or edition support. #164 remains the
motion/focus owner; #319 owns the existing missing public-capture-to-timeline
integration. Neither is delivered by this audit.

## Coverage and delivery state

This first pushed checkpoint pins the scope and the first verified limits.
The complete source register, action matrix, design-impact brief and finite
proof handoff are being assembled on this branch. No functional design
clearance follows from this checkpoint. Existing #125/#128 owners and holds
remain in place; #310's provisional Sorting/Stash proof remains its owner's
work.
