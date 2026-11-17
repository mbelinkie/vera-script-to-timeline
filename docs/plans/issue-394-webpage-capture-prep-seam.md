# #394 public webpage capture — Prep Media handoff boundary

The current `script-document/v2` accepts `pictureKind: "capture"` with
`source: {"kind":"url", "url":"https://..."}` in narration, visual-only and
supporting visual payloads. The authored URL is *intent*, not a verified media
source. It cannot bypass the existing compiler's exact `OccurrenceMediaResolutionV2`
and `PreparedMediaBindingV1` requirements.

`@vera/public-page-capture` exposes `preparePublicWebpageVisuals` (phase-1
bounded integration) for trusted Prep Media hosts. It accepts the frozen
`ScriptDocumentV2`, project root, current principal, versioned visible authored
reference and existing authorized `CaptureService`. It enforces the #39 URL
admission policy, requests a stable idempotent one-shot capture, and returns a
**build-only** projected document and per-occurrence outcome. The #39 worker
still owns Chromium, DNS, egress restrictions, immutable revisions and object
publication. No network requests happen in the builder.

For a ready revision the boundary verifies the capture/project/profile and
artifact identities, selects the revision for each authored occurrence,
reads through the service's fresh permission/visible-reference checks, hashes
the raster and publishes a project-scoped immutable `Webpage Captures/` still
with receipt. Another build reads the same pinned revision and verified bytes
without requesting a new job. A queued/review-required/failed capture becomes
an explicitly labelled placeholder in the build-only projection, with a
separate reason in the outcome. URLs refused by #39's parser have a generic
safe label, avoiding credentials in diagnostics. The original authored document
is unchanged, including each row's timing. Failing authorization or a digest
mismatch **refuses** rather than silently substituting a placeholder.

## Missing live build integration

The current Python `MediaStagePort` in
`python/vera_timeline_agent/build_media_stage.py` begins with *already frozen*
`source:<mediaReferenceId>` files, independently qualified stream indices and
source descriptors. There is no existing authorized build-host entry point
that provides #39 `CaptureService`, a current writer and visible occurrence
reference, and then maps a raster to an independently verified
`OccurrenceMediaResolutionV2`/`PreparedMediaBindingV1` for the frozen build.
This phase does **not** manufacture those hashes, bypass source sufficiency or
pretend a PNG path alone proves Resolve delivery. Connecting that host seam
and conducting one actual Resolve save/reopen are required before claiming the
issue's complete end-to-end acceptance. This explicitly avoids implementing
the unrelated Prep Media editor UI (#319) or building the broader #82 host.

Deterministic focused evidence:
`packages/public-page-capture/test/prep-media.test.ts`, plus existing compiler
capture-still golden fixtures under
`tests/data/authoring_v2/issue_173/compiler/`. Phase 2 independently performs
the full fast gate, integrity/authorization mutation checks and self-review.
