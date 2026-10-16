# Slice 1.6 — Production Studio assembly plan

> Live status and routing: [GitHub issue #34](https://github.com/mbelinkie/vera-script-to-timeline/issues/34). This plan bounds implementation and acceptance evidence.

## Scope

Consume exactly one already-verified Slice 1.4 Authoring Project through the
supported Resolve Studio Python API. Before any connection or project mutation,
re-run package verification. After nonmutating Studio preflight, create a new
project and timeline derived from the package build ID; create deterministic
bins/tracks, import package-local media, place every manifest event and marker,
save, reopen, and compare the observable timeline to the same manifest used by
Resolve Free.

## Exclusions

- No changes to shared contracts, fixtures, accepted goldens, package artifacts,
  compiler semantics, UI automation, render/upload, in-place updates, or
  production/research data.
- No Fusion graphics product placement. `TimelineManifest v1` has no graphics
  event contract; the accepted #3 pinned-template capability remains a separate,
  fail-closed seam and is not silently represented as an ordinary timeline event.

## Contracts, data, and dependency

- The verified import package is read-only input. Its manifest, report, media,
  OTIO, instructions, and receipt remain byte-for-byte unchanged.
- Tests create a temporary synthetic package and use an injected public-API
  adapter. Real acceptance uses one dedicated Producer project only.
- Dependency: #3 is closed and Done. Its approved pinned-template capability is
  preserved without adding a curated-graphics contract.
- No dependency is added; the implementation reuses the existing package
  verifier and accepted Slice 0.4 public Resolve adapter.
- The assembly path also recognizes the retained #3 local baseline: the default
  Blackmagic bundle at Resolve Studio 21.1.0 build 14 with its installed
  scripting module. Connected API identity must still agree exactly; other
  receipt, documentation, edition, version, or installation states fail closed.

## Automated evidence

- Package tampering stops before a Resolve adapter is constructed.
- Unsupported target collision and preflight failures stop before mutation.
- A build forwards package-local source identities, every manifest event,
  deterministic bins/tracks, and markers to the adapter, then retains explicit
  reopened verification discrepancies and partial-target identity.
- The adapter has no UI-automation fallback. Full repository validation must
  pass without frozen-boundary drift.

## Producer acceptance

1. Keep the complete verified Authoring Project intact and open its sole
   `Builds/<build-id>/package-verification.json`. Confirm `ready_to_import` and
   the manifest/report hashes.
2. In Resolve Free, import that package's `timeline.otio` using its retained
   instructions. Record the observed tracks, event ranges, markers, and media
   identities; do not alter an existing timeline.
3. Manually open supported standard desktop Resolve Studio, enable local
   external scripting, leave it on a timeline page, and run the documented
   nonmutating preflight command below.
4. Run the documented build command once. Inspect the new build-named project
   and timeline, then reopen it and compare its JSON verification result with
   the manifest and the Resolve Free observation. A failed result names the
   retained partial target; do not overwrite it.
5. Confirm no existing project or timeline was overwritten. Reply
   `Accepted production Studio assembly slice.` or report the first mismatch.
