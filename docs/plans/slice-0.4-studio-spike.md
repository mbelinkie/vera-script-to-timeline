# Slice 0.4 — Resolve Studio scripting spike

## Bounded scope

Add a reusable Python API and CLI that consume the producer-accepted Slice
0.2 package. The API detects local Resolve installation facts without making
an API connection, verifies the package, and performs a nonmutating connected
preflight before any project mutation. In explicitly selected Studio mode,
and only after that preflight passes, it uses the installed public Resolve 21
scripting API to create a uniquely named project and bins, import the five
accepted media files, configure the manifest timeline settings and adjustable
track map, place three trimmed videos, one still, and the synthetic narration
at their exact manifest frames, request one named Fusion title and add the manifest
marker with custom data, save, close/reopen, and verify the observable result.

Detection reports OS/version/architecture, application path, install source,
bundle version/build, Mac App Store receipt presence, scripting module, and
installed documentation before connection. Product name/edition, live
version/build, and scripting availability are reported only after connection.
Every result separates detected facts, API observations, discrepancies, and
requirements the installed public API cannot prove.

## Explicit exclusions

- No edits to `/contracts`, `/fixtures`, generated contract outputs, accepted
  Slice 0.2 tests, or accepted Slice 0.2 test data.
- No Resolve UI automation, application launch, rendering, upload, deletion,
  overwrite/update of an existing project, or manipulation of a separate
  checkout or research-project data.
- No claim that the locally installed standard Resolve bundle is Studio or
  externally connectable until a real connected producer run observes it.
- No private API and no invented evidence for Fusion title selection,
  placement, duration, or any other property the public API cannot prove.

## Contracts, fixtures, and dependencies

This slice consumes the frozen `TimelineManifest v1` and the accepted Slice
0.2 package without changing either. New tests build temporary copies through
the accepted package API and use strict injected adapters; no frozen file is
rewritten. No dependency is added: plist/platform/path detection uses the
Python standard library, and the vendor module is dynamically loaded only in
the explicitly authorized connected path.

## Automated checks

- Prove Free delivery returns after package verification without importing,
  connecting to, or invoking the Resolve API.
- Prove Studio stops without mutation for Free edition, App Store install,
  missing module, failed/disabled connection, and incomplete/nonconforming
  preflight, with actionable diagnostics. Report the connected version without
  inventing a minimum supported version before producer evidence exists.
- Prove the available nonmutating project-manager/current-project probes and
  project-name collision check precede the first mutation, report the build
  surfaces they cannot exercise, and ensure every failure before that boundary
  produces zero project mutation.
- Prove failures after the mutation boundary report that a partial project may
  remain instead of describing the run as a safe, nonmutating stop.
- With strict doubles, verify exact project/bin/import/settings/track/event/
  marker/save/reopen/verification calls, exact media identities and record/source
  frames,
  adjustable settings and track maps, and discrepancies/manual-completion
  results for public-API gaps including stock Fusion-title proof.
- Exercise the CLI's detection, nonmutating preflight, and Free safety
  paths without requiring Resolve or launching its UI.
- Run focused pytest, Ruff, strict mypy, full `npm run validate`, a frozen-file
  boundary audit against the accepted base, and final diff review.

## Producer acceptance

1. From locked installs, generate/reverify the accepted Slice 0.2 package.
2. Run the documented `detect` command and confirm the objective local facts;
   this command must not connect to Resolve.
3. Run the documented Free command and confirm it stops at the verified
   package without a Resolve connection.
4. Manually start the supported standard desktop Resolve Studio installation,
   enable external local scripting in Resolve preferences, open a current
   project on a documented timeline page such as Edit, and run the exact
   documented Studio `preflight` command. Review its detected versus observed
   facts and capability/manual-completion results.
5. Run the documented Studio `build` command once, watch the newly named spike
   project/timeline appear, then inspect its bins, tracks, five manifest media
   placements, requested Fusion title, marker/custom-data result, saved/reopened
   state, and verification output. Record the real observation and evidence in
   `CAPABILITIES.md`; producer observation remains authoritative and is the
   only action that can accept the slice.
